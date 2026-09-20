"""Check frozen Rev I geometry with the approved 378-to-340 mm rail change.

Every saved shape is compared in local and world coordinates. The expected rail
is derived only from the immutable fixture; current construction code cannot
silently redefine the approved difference. All other shapes remain unchanged.
"""

import json
import os
from pathlib import Path

import FreeCAD as App
import Part

from gondola.cad import (
    world_shape,
)
from gondola.config import BASELINE_FILE, BASELINE_SHA256, OUTPUT_DIR, ROOT, STEM
from gondola.design_contract import SCOPED_LISTED_EQUIPMENT_MASS_G
from gondola.manufacturing import geometry_comparison
from gondola.provenance import file_sha256, source_fingerprint

from .geometry import local_shape

TOL = 1e-5
BASELINE = BASELINE_FILE
REGISTRY_LISTS = (
    "PrintedParts",
    "ReferenceParts",
    "ClearanceVolumes",
    "FitCoupons",
    "Modules",
    "StandardBoards",
    "StackPosts",
    "StackLocks",
    "StackWashers",
    "RailSegments",
    "RailLocks",
    "HardwareParts",
    "TapeReferences",
    "TiltingPods",
)


def shape_objects(doc):
    return {
        obj.Name: obj
        for obj in doc.Objects
        if "Shape" in obj.PropertiesList and not obj.Shape.isNull()
    }


def expressions(doc):
    return {
        obj.Name: sorted(
            (str(path), str(expression)) for path, expression in obj.ExpressionEngine
        )
        for obj in doc.Objects
        if "ExpressionEngine" in obj.PropertiesList and obj.ExpressionEngine
    }


def registry_contents(registry):
    return {
        name: [obj.Name for obj in getattr(registry, name)] for name in REGISTRY_LISTS
    }


def control_behavior(doc):
    """Exercise saved native expressions without relying on source proxies."""
    clamp_names = (
        "BatteryClampApproach",
        "PropulsionClampApproach",
        "ElectronicsClampApproach",
    )
    modules = list(doc.DesignRegistry.Modules)
    originals = {name: str(getattr(doc.AssemblySettings, name)) for name in clamp_names}
    rows = []
    try:
        for key, module in zip(clamp_names, modules):
            for value, sign in (("PositiveY", 1), ("NegativeY", -1)):
                setattr(doc.AssemblySettings, key, value)
                doc.recompute()
                rows.append(
                    {
                        "object": module.Name,
                        "property": key,
                        "input": value,
                        "result_y_mm": module.Placement.Base.y,
                        "passed": abs(module.Placement.Base.y - sign * 0.45) < TOL,
                    }
                )
    finally:
        for key, value in originals.items():
            setattr(doc.AssemblySettings, key, value)
        doc.recompute()
    for pod in doc.DesignRegistry.TiltingPods:
        original = float(pod.Tilt)
        other_pods = {
            other.Name: other.Placement.copy()
            for other in doc.DesignRegistry.TiltingPods
            if other != pod
        }
        try:
            for requested, expected in (
                (-999, -150),
                (-75, -75),
                (0, 0),
                (75, 75),
                (999, 150),
            ):
                pod.Tilt = requested
                doc.recompute()
                expected_rotation = App.Rotation(App.Vector(0, 1, 0), expected)
                independent = all(
                    doc.getObject(name).Placement.isSame(placement, 1e-7)
                    for name, placement in other_pods.items()
                )
                rows.append(
                    {
                        "object": pod.Name,
                        "property": "Tilt",
                        "input": requested,
                        "expected_bounded_angle_deg": expected,
                        "other_pod_unchanged": independent,
                        "passed": pod.Placement.Rotation.isSame(expected_rotation, 1e-7)
                        and independent,
                    }
                )
        finally:
            pod.Tilt = original
            doc.recompute()
    for module in modules:
        original = float(module.RailPositionX)
        try:
            module.RailPositionX = original + 18
            doc.recompute()
            rows.append(
                {
                    "object": module.Name,
                    "property": "RailPositionX",
                    "input": original + 18,
                    "result_x_mm": module.Placement.Base.x,
                    "passed": abs(module.Placement.Base.x - original - 18) < TOL,
                }
            )
        finally:
            module.RailPositionX = original
            doc.recompute()
    return {"cases": rows, "passed": all(row["passed"] for row in rows)}


def unresolved_scope(doc):
    registry = doc.DesignRegistry
    couplings = [doc.getObject(prefix + "Coupling") for prefix in ("Port", "Starboard")]
    forbidden = [
        obj.Name
        for obj in registry.ReferenceParts
        if any(
            token in obj.Name.lower() for token in ("yaw", "mtf", "finservo", "hl3604")
        )
    ]
    coupling_ok = all(
        obj is not None
        and obj in registry.ClearanceVolumes
        and obj not in registry.PrintedParts
        and obj not in registry.HardwareParts
        and "unfinished" in str(obj.Notes).lower()
        for obj in couplings
    )
    rail_exception = str(doc.ContinuousRail.ManufacturingException)
    status = str(registry.Status)
    return {
        "scope_exclusions": str(registry.ScopeExclusions),
        "forbidden_device_references": forbidden,
        "horn_couplings_remain_unfinished_clearance_only": coupling_ok,
        "rail_flexure_exception": rail_exception,
        "qualification_status": status,
        "passed": not forbidden
        and coupling_ok
        and "1mm" in rail_exception
        and "unqualified" in status.lower()
        and abs(
            float(registry.ScopedListedEquipmentMassGrams)
            - SCOPED_LISTED_EQUIPMENT_MASS_G
        )
        < TOL,
    }


def approved_rail_shape(frozen_rail):
    """Shorten only the frozen rail, preserving its original section and ends.

    Keep x=-169..169, including all seven tape pads, and transplant the original
    2 mm end pieces inward by exactly 19 mm. Their new ranges (-170..-168 and
    168..170) overlap the retained rail by 1 mm. This preserves the original
    rounded base/cap ends and excludes the obsolete reliefs at x=+/-171.

    These fixed dimensions encode the approved change independently of the
    current rail generator. Never replace this with rail_shape(current_length).
    """
    bounds = frozen_rail.optimalBoundingBox(False, False)

    def section(start, stop):
        clip = Part.makeBox(
            stop - start,
            bounds.YLength + 2,
            bounds.ZLength + 2,
            App.Vector(start, bounds.YMin - 1, bounds.ZMin - 1),
        )
        return frozen_rail.common(clip)

    center = section(-169, 169)
    left = section(-189, -187)
    left.translate(App.Vector(19, 0, 0))
    right = section(187, 189)
    right.translate(App.Vector(-19, 0, 0))
    approved = center.multiFuse([left, right]).removeSplitter()
    if not approved.isValid() or len(approved.Solids) != 1:
        raise RuntimeError(
            "Approved frozen-rail transformation is not one valid solid."
        )
    return approved


def validate(source=None, baseline=None):
    fingerprint_before = source_fingerprint()
    source = Path(source).resolve() if source else OUTPUT_DIR / (STEM + ".FCStd")
    baseline = Path(baseline).resolve() if baseline else BASELINE
    if source.resolve() == baseline.resolve():
        raise ValueError("Regression source must be distinct from the frozen baseline.")
    before = {
        os.path.relpath(path, ROOT): file_sha256(path) for path in (source, baseline)
    }
    if before[os.path.relpath(baseline, ROOT)] != BASELINE_SHA256:
        raise ValueError(
            "Frozen Rev I baseline checksum mismatch; do not regenerate the baseline from current source."
        )
    docs = []
    try:
        current = App.openDocument(str(source), hidden=True)
        docs.append(current)
        previous = App.openDocument(str(baseline), hidden=True)
        docs.append(previous)
        current.recompute()
        previous.recompute()
        actual, expected = shape_objects(current), shape_objects(previous)
        names_match = set(actual) == set(expected)
        rows = []
        for name in sorted(set(actual) & set(expected)):
            expected_local = local_shape(expected[name])
            expected_world = world_shape(expected[name])
            comparison_basis = "Unmodified frozen Rev I geometry"
            if name == "ContinuousRail":
                expected_local = approved_rail_shape(expected_local)
                expected_world = expected_local.copy()
                expected_world.Placement = expected[name].getGlobalPlacement()
                comparison_basis = (
                    "Frozen Rev I rail center with original ends translated inward "
                    "19 mm each; approved total length 340 mm"
                )
            local = geometry_comparison(local_shape(actual[name]), expected_local)
            world = geometry_comparison(world_shape(actual[name]), expected_world)
            same_type = actual[name].TypeId == expected[name].TypeId
            same_placement = (
                actual[name]
                .getGlobalPlacement()
                .isSame(expected[name].getGlobalPlacement(), 1e-7)
            )
            same_solids = len(actual[name].Shape.Solids) == len(
                expected[name].Shape.Solids
            )
            rows.append(
                {
                    "object": name,
                    "comparison_basis": comparison_basis,
                    "local_shape": local,
                    "world_shape": world,
                    "object_type_unchanged": same_type,
                    "world_placement_unchanged": same_placement,
                    "solid_count_unchanged": same_solids,
                    "passed": same_type
                    and same_placement
                    and same_solids
                    and all(
                        comparison["difference_mm3"] < TOL
                        and comparison["bounds_difference_mm"] < TOL
                        and comparison["volume_difference_mm3"] < TOL
                        for comparison in (local, world)
                    ),
                }
            )
        current_registry = registry_contents(current.DesignRegistry)
        previous_registry = registry_contents(previous.DesignRegistry)
        current_expressions, previous_expressions = (
            expressions(current),
            expressions(previous),
        )
        controls = control_behavior(current)
        scope = unresolved_scope(current)
        report = {
            "source": os.path.relpath(source, ROOT),
            "baseline": os.path.relpath(baseline, ROOT),
            "scope": "Regression against frozen Rev I plus the approved 378-to-340 mm rail shortening. Every local/world shape and saved native control is checked; existing unqualified interfaces remain unqualified.",
            "approved_geometry_changes": [
                {
                    "object": "ContinuousRail",
                    "original_length_mm": 378.0,
                    "approved_length_mm": 340.0,
                    "preserved_center_x_mm": [-169.0, 169.0],
                    "original_end_sections_x_mm": [[-189.0, -187.0], [187.0, 189.0]],
                    "end_translations_x_mm": [19.0, -19.0],
                    "expected_geometry_source": "Immutable frozen Rev I fixture only",
                    "unchanged_features": "Seven tape-pad locations, T section, remaining flex reliefs, root fillets and rounded terminal profiles",
                }
            ],
            "file_hashes_before": before,
            "source_sha256": file_sha256(source),
            "source_fingerprint": fingerprint_before,
            "native_source_identity_matches": str(
                getattr(current.DesignRegistry, "SourceFingerprint", "")
            )
            == fingerprint_before,
            "baseline_sha256": file_sha256(baseline),
            "shape_names_unchanged": names_match,
            "added_shape_names": sorted(set(actual) - set(expected)),
            "missing_shape_names": sorted(set(expected) - set(actual)),
            "shape_count": len(actual),
            "shape_comparisons": rows,
            "registry_membership_unchanged": current_registry == previous_registry,
            "current_registry": current_registry,
            "baseline_registry": previous_registry,
            "native_expressions_unchanged": current_expressions == previous_expressions,
            "current_native_expressions": current_expressions,
            "baseline_native_expressions": previous_expressions,
            "native_control_behavior": controls,
            "unresolved_scope": scope,
        }
    finally:
        for doc in reversed(docs):
            App.closeDocument(doc.Name)
    report["file_hashes_after"] = {
        os.path.relpath(path, ROOT): file_sha256(path) for path in (source, baseline)
    }
    report["saved_files_unchanged"] = before == report["file_hashes_after"]
    report["source_code_unchanged"] = fingerprint_before == source_fingerprint()
    report["passed"] = (
        report["saved_files_unchanged"]
        and report["source_code_unchanged"]
        and report["native_source_identity_matches"]
        and names_match
        and bool(rows)
        and all(row["passed"] for row in rows)
        and report["registry_membership_unchanged"]
        and report["native_expressions_unchanged"]
        and controls["passed"]
        and scope["passed"]
    )
    target = source.parent / (source.stem + "_baseline_validation.json")
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "baseline_report": str(target),
                "passed": report["passed"],
                "shape_count": report["shape_count"],
                "failed_shapes": [row["object"] for row in rows if not row["passed"]],
                "native_controls_passed": controls["passed"],
                "native_expressions_unchanged": report["native_expressions_unchanged"],
            }
        ),
        flush=True,
    )
    return report
