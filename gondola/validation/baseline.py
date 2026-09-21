"""Compare every saved shape and native control with the pinned approved CAD.

No current-source geometry or per-part exceptions redefine the frozen reference.
A design revision requires an explicit, reviewed fixture transition.
"""

import json
import os
from pathlib import Path

import FreeCAD as App

from gondola.cad import (
    world_shape,
)
from gondola.config import BASELINE_FILE, BASELINE_SHA256, OUTPUT_DIR, ROOT, STEM
from gondola.design_contract import (
    MANUFACTURING_DECISION,
    SCOPED_LISTED_EQUIPMENT_MASS_G,
    release_status,
)
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
    "EquipmentMounts",
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
        if any(token in obj.Name.lower() for token in ("yaw", "finservo", "hl3604"))
    ]
    coupling_ok = all(
        obj is not None
        and obj in registry.ClearanceVolumes
        and obj not in registry.PrintedParts
        and obj not in registry.HardwareParts
        and "unfinished" in str(obj.Notes).lower()
        for obj in couplings
    )
    mtf = doc.getObject("ModuleMTF02PEnvelope")
    optical = doc.getObject("MTF02POpticalClearanceReserve")
    optical_scope_ok = (
        mtf is not None
        and mtf in registry.ReferenceParts
        and mtf not in registry.PrintedParts
        and mtf not in registry.HardwareParts
        and optical is not None
        and optical in registry.ClearanceVolumes
        and optical not in registry.PrintedParts
        and optical not in registry.HardwareParts
    )
    rail_exception = str(doc.ContinuousRail.ManufacturingException)
    flexure_description = f"{MANUFACTURING_DECISION['nominal_rail_flexure_mm']:g}mm"
    status = str(registry.Status)
    try:
        native_release = json.loads(str(registry.ReleaseStatus))
    except (AttributeError, TypeError, ValueError):
        native_release = None
    release_matches = native_release == release_status()
    return {
        "scope_exclusions": str(registry.ScopeExclusions),
        "forbidden_device_references": forbidden,
        "horn_couplings_remain_unfinished_clearance_only": coupling_ok,
        "mtf02p_device_and_optical_reserve_are_reference_only": optical_scope_ok,
        "rail_flexure_exception": rail_exception,
        "qualification_status": status,
        "native_release_status_matches_contract": release_matches,
        "passed": not forbidden
        and release_matches
        and coupling_ok
        and optical_scope_ok
        and flexure_description in rail_exception.replace(" ", "")
        and "unqualified" in status.lower()
        and abs(
            float(registry.ScopedListedEquipmentMassGrams)
            - SCOPED_LISTED_EQUIPMENT_MASS_G
        )
        < TOL,
    }


def procurement_and_scope_metadata(obj):
    """Keep shape identity tied to its purchase/print role and qualification.

    Notes, labels and display settings may change without changing a part.
    These interface-bearing fields must not silently change under identical BReps.
    """
    fields = (
        "HardwareSKU",
        "PrintSKU",
        "Role",
        "PrintPart",
        "MaterialSelection",
        "ThreadStandard",
        "NominalThreadDiameter",
        "ThreadPitch",
        "SourceURL",
        "PurchaseSearchQuery",
        "PurchaseSearchURL",
        "PurchaseRequirements",
        "PurchaseCandidateURL",
        "PurchaseEvidenceNotes",
        "PurchasingStatus",
        "ManufacturingRoute",
        "MountingStackVerified",
        "PCBHeightMeasured",
        "InstalledOpticalFieldVerified",
        "FDMPrintValidated",
    )
    values = {}
    for name in fields:
        if name in obj.PropertiesList:
            value = getattr(obj, name)
            values[name] = float(value.Value) if hasattr(value, "Value") else value
    return values


def compare_shape_objects(actual, expected):
    """Compare complete local/world BReps and placement, including symmetry cases."""
    local = geometry_comparison(local_shape(actual), local_shape(expected))
    world = geometry_comparison(world_shape(actual), world_shape(expected))
    same_type = actual.TypeId == expected.TypeId
    same_placement = actual.getGlobalPlacement().isSame(
        expected.getGlobalPlacement(), 1e-7
    )
    same_solids = len(actual.Shape.Solids) == len(expected.Shape.Solids)
    actual_metadata = procurement_and_scope_metadata(actual)
    expected_metadata = procurement_and_scope_metadata(expected)
    same_metadata = actual_metadata == expected_metadata
    return {
        "object": actual.Name,
        "local_shape": local,
        "world_shape": world,
        "object_type_unchanged": same_type,
        "world_placement_unchanged": same_placement,
        "solid_count_unchanged": same_solids,
        "procurement_and_scope_metadata_unchanged": same_metadata,
        "current_procurement_and_scope_metadata": actual_metadata,
        "baseline_procurement_and_scope_metadata": expected_metadata,
        "passed": same_type
        and same_placement
        and same_solids
        and same_metadata
        and all(
            comparison["difference_mm3"] < TOL
            and comparison["bounds_difference_mm"] < TOL
            and comparison["volume_difference_mm3"] < TOL
            for comparison in (local, world)
        ),
    }


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
            "Frozen approved baseline checksum mismatch; do not regenerate the baseline from current source."
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
        rows = [
            compare_shape_objects(actual[name], expected[name])
            for name in sorted(set(actual) & set(expected))
        ]
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
            "scope": "Strict regression against the pinned approved design. Every local/world shape, placement, registry and saved native control is checked without geometry exceptions; unresolved interfaces remain unqualified.",
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
