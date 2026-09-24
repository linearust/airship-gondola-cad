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
from gondola.config import (
    ARTIFACT_STEM,
    BASELINE_FILE,
    BASELINE_SHA256,
    OUTPUT_DIR,
    REPO_ROOT,
)
from gondola.contracts.design import (
    EXPECTED_INVENTORY,
    MANUFACTURING_DECISION,
    MODULE_STATIONS,
    SCOPED_LISTED_EQUIPMENT_MASS_G,
    release_status,
)
from gondola.parts import rail
from gondola.print_export import geometry_comparison
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
    "OpticalMountParts",
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


def module_control_bindings(doc):
    """Bind controls by stable object identity, never registry list position."""
    modules = list(doc.DesignRegistry.Modules)
    names = [obj.Name for obj in modules]
    expected = [station.object_name for station in MODULE_STATIONS]
    controls = [station.clamp_control for station in MODULE_STATIONS]
    if (
        not expected
        or len(set(expected)) != len(expected)
        or len(set(controls)) != len(controls)
        or len(set(names)) != len(names)
        or set(names) != set(expected)
    ):
        raise ValueError("Registered modules do not match the unique station contract")
    if any(name not in doc.AssemblySettings.PropertiesList for name in controls):
        raise ValueError("A registered module has no native clamp approach control")
    by_name = {obj.Name: obj for obj in modules}
    return [(station, by_name[station.object_name]) for station in MODULE_STATIONS]


def module_clamp_pose(station, module, approach):
    """A clamp side is carrier-local; its seated offset follows carrier yaw."""
    if approach not in ("PositiveY", "NegativeY"):
        raise ValueError("Unknown local rail-clamp approach")
    local_side = 1 if approach == "PositiveY" else -1
    world_side = local_side * station.transverse_sign
    expected_y = world_side * rail.CLAMP_SHIFT_Y
    rotation_matches = module.Placement.Rotation.isSame(
        App.Rotation(App.Vector(0, 0, 1), station.yaw_deg), 1e-7
    )
    return {
        "local_approach_side_y": local_side,
        "world_approach_side_y": world_side,
        "expected_seated_y_mm": expected_y,
        "result_y_mm": module.Placement.Base.y,
        "expected_carrier_yaw_deg": station.yaw_deg,
        "carrier_rotation_matches": rotation_matches,
        "passed": rotation_matches and abs(module.Placement.Base.y - expected_y) < TOL,
    }


def control_behavior(doc):
    """Exercise saved native expressions without relying on source proxies."""
    try:
        bindings = module_control_bindings(doc)
    except (AttributeError, ValueError) as error:
        return {
            "cases": [],
            "module_control_mapping_valid": False,
            "error": str(error),
            "passed": False,
        }
    modules = [module for _, module in bindings]
    pods = list(doc.DesignRegistry.TiltingPods)
    if len(pods) != EXPECTED_INVENTORY["tilting_propulsors"] or len(
        {pod.Name for pod in pods}
    ) != len(pods):
        return {"cases": [], "error": "Tilting pod inventory mismatch", "passed": False}
    clamp_names = [station.clamp_control for station, _ in bindings]
    originals = {name: str(getattr(doc.AssemblySettings, name)) for name in clamp_names}
    rows = []
    try:
        for station, module in bindings:
            key = station.clamp_control
            other_modules = {
                other.Name: other.Placement.copy()
                for other in modules
                if other != module
            }
            for value in ("PositiveY", "NegativeY"):
                setattr(doc.AssemblySettings, key, value)
                doc.recompute()
                pose = module_clamp_pose(station, module, value)
                rows.append(
                    {
                        "object": module.Name,
                        "property": key,
                        "input": value,
                        **pose,
                        "other_modules_unchanged": all(
                            doc.getObject(name).Placement.isSame(placement, 1e-7)
                            for name, placement in other_modules.items()
                        ),
                        "passed": pose["passed"]
                        and all(
                            doc.getObject(name).Placement.isSame(placement, 1e-7)
                            for name, placement in other_modules.items()
                        ),
                    }
                )
    finally:
        for key, value in originals.items():
            setattr(doc.AssemblySettings, key, value)
        doc.recompute()
    for pod in pods:
        original = float(pod.Tilt)
        other_pods = {
            other.Name: other.Placement.copy() for other in pods if other != pod
        }
        try:
            for requested, expected in (
                (-999, -180),
                (-75, -75),
                (0, 0),
                (75, 75),
                (999, 180),
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
        other_modules = {
            other.Name: other.Placement.copy() for other in modules if other != module
        }
        try:
            module.RailPositionX = original + 18
            doc.recompute()
            rows.append(
                {
                    "object": module.Name,
                    "property": "RailPositionX",
                    "input": original + 18,
                    "result_x_mm": module.Placement.Base.x,
                    "other_modules_unchanged": all(
                        doc.getObject(name).Placement.isSame(placement, 1e-7)
                        for name, placement in other_modules.items()
                    ),
                    "passed": abs(module.Placement.Base.x - original - 18) < TOL
                    and all(
                        doc.getObject(name).Placement.isSame(placement, 1e-7)
                        for name, placement in other_modules.items()
                    ),
                }
            )
        finally:
            module.RailPositionX = original
            doc.recompute()
    optical = doc.getObject("OpticalFlowModule")
    roll = doc.getObject("OpticalRollStage")
    pitch = doc.getObject("OpticalPitchStage")
    if any(obj is None for obj in (optical, roll, pitch)):
        return {
            "cases": rows,
            "module_control_mapping_valid": True,
            "error": "Missing independent optical roll/pitch stages",
            "passed": False,
        }
    for property_name, stage, axis, origin, other_stage, expected_parent in (
        ("Roll", roll, App.Vector(1, 0, 0), App.Vector(0, 0, 8), pitch, optical),
        ("Pitch", pitch, App.Vector(0, 1, 0), App.Vector(0, 0, 10), roll, roll),
    ):
        if not {property_name, "MinimumAngle", "MaximumAngle"}.issubset(
            stage.PropertiesList
        ):
            return {
                "cases": rows,
                "error": "Missing optical angle control",
                "passed": False,
            }
        original = float(getattr(stage, property_name))
        other_placement = other_stage.Placement.copy()
        module_placements = {module.Name: module.Placement.copy() for module in modules}
        optical_placement = optical.getGlobalPlacement()
        declared_limits_match = (
            abs(float(stage.MinimumAngle) + 20) < TOL
            and abs(float(stage.MaximumAngle) - 20) < TOL
        )
        try:
            for requested, expected in (
                (-999, -20),
                (-10, -10),
                (0, 0),
                (10, 10),
                (999, 20),
            ):
                setattr(stage, property_name, requested)
                doc.recompute()
                independent = (
                    other_stage.Placement.isSame(other_placement, 1e-7)
                    and optical.getGlobalPlacement().isSame(optical_placement, 1e-7)
                    and all(
                        doc.getObject(name).Placement.isSame(placement, 1e-7)
                        for name, placement in module_placements.items()
                    )
                )
                stage_pose_matches = stage.Placement.isSame(
                    App.Placement(origin, App.Rotation(axis, expected)), 1e-7
                )
                parent_matches = stage.getParentGeoFeatureGroup() == expected_parent
                rows.append(
                    {
                        "object": stage.Name,
                        "property": property_name,
                        "input": requested,
                        "expected_bounded_angle_deg": expected,
                        "stage": stage.Name,
                        "stage_local_placement_matches": stage_pose_matches,
                        "stage_parent_matches": parent_matches,
                        "declared_limits_match": declared_limits_match,
                        "other_axis_and_modules_unchanged": independent,
                        "passed": stage_pose_matches
                        and parent_matches
                        and declared_limits_match
                        and independent,
                    }
                )
        finally:
            setattr(stage, property_name, original)
            doc.recompute()
    expected_cases = (
        3 * len(bindings) + 5 * EXPECTED_INVENTORY["tilting_propulsors"] + 10
    )
    return {
        "cases": rows,
        "module_control_mapping_valid": True,
        "expected_case_count": expected_cases,
        "passed": len(rows) == expected_cases and all(row["passed"] for row in rows),
    }


def unresolved_scope(doc):
    registry = doc.DesignRegistry
    couplings = [
        doc.getObject(prefix + suffix)
        for prefix in ("Port", "Starboard")
        for suffix in ("HornGearAdapter",)
    ]
    horns = [doc.getObject(prefix + "ServoHorn") for prefix in ("Port", "Starboard")]
    forbidden = [
        obj.Name
        for obj in registry.ReferenceParts
        if any(token in obj.Name.lower() for token in ("yaw", "finservo", "hl3604"))
    ]
    coupling_ok = all(
        obj is not None
        and obj in registry.PrintedParts
        and obj not in registry.ClearanceVolumes
        and obj not in registry.HardwareParts
        and "unqualified" in str(getattr(obj, "ManufacturingStatus", "")).lower()
        for obj in couplings
    ) and all(
        obj is not None
        and obj in registry.HardwareParts
        and obj not in registry.PrintedParts
        and str(getattr(obj, "HardwareSKU", "")) == "KST_X06_SUPPLIED_HORN"
        for obj in horns
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
        "horn_adapters_use_bought_splines_and_unqualified_printed_parts": coupling_ok,
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
        "ReferenceMassGrams",
        "ReferenceMassSource",
        "ShapeModelNotes",
        "SourceURL",
        "PurchaseSearchQuery",
        "PurchaseSearchURL",
        "PurchaseRequirements",
        "PurchaseCandidateURL",
        "PurchaseEvidenceNotes",
        "PurchasingStatus",
        "ManufacturingRoute",
        "MountingStackVerified",
        "InstallationYawInCarrier",
        "PCBHeightMeasured",
        "InstalledOpticalFieldVerified",
        "InstalledConnectorFitVerified",
        "ConnectorEvidence",
        "FlightControllerContract",
        "NavigationProfile",
        "RadioProfile",
        "WiringContract",
        "MountContract",
        "ModulePlacementContract",
        "OpticalMountContract",
        "StackInterfaceContract",
        "BatteryPlacementContract",
        "RailFitContract",
        "StackHostName",
        "StackFitVerified",
        "HoldingTorqueVerified",
        "SelfLevelling",
        "MinimumAngle",
        "MaximumAngle",
        "StackEnd",
        "FDMPrintValidated",
        "GearConfiguration",
        "DriveContract",
        "AfterPrintPreparation",
        "SuppliedHornMeasured",
    )
    values = {}
    for name in fields:
        if name in obj.PropertiesList:
            value = getattr(obj, name)
            values[name] = float(value.Value) if hasattr(value, "Value") else value
    return values


def native_interface_metadata(doc):
    """Include non-solid containers that declare attachment and qualification."""
    result = {}
    for obj in doc.Objects:
        metadata = procurement_and_scope_metadata(obj)
        if metadata:
            result[obj.Name] = metadata
    return result


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
    blank_presence = hasattr(actual, "PrintBlankShape") == hasattr(
        expected, "PrintBlankShape"
    )
    blank = None
    if hasattr(actual, "PrintBlankShape") and hasattr(expected, "PrintBlankShape"):
        blank = geometry_comparison(actual.PrintBlankShape, expected.PrintBlankShape)
    same_blank = blank_presence and (
        blank is None
        or all(
            blank[field] < TOL
            for field in (
                "difference_mm3",
                "bounds_difference_mm",
                "volume_difference_mm3",
            )
        )
    )
    return {
        "object": actual.Name,
        "print_blank_unchanged": same_blank,
        "print_blank_comparison": blank,
        "local_shape": local,
        "world_shape": world,
        "object_type_unchanged": same_type,
        "world_placement_unchanged": same_placement,
        "solid_count_unchanged": same_solids,
        "procurement_and_scope_metadata_unchanged": same_metadata,
        "current_procurement_and_scope_metadata": actual_metadata,
        "baseline_procurement_and_scope_metadata": expected_metadata,
        "passed": same_type
        and same_blank
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
    source = (
        Path(source).resolve() if source else OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")
    )
    baseline = Path(baseline).resolve() if baseline else BASELINE
    if source.resolve() == baseline.resolve():
        raise ValueError("Regression source must be distinct from the frozen baseline.")
    before = {
        os.path.relpath(path, REPO_ROOT): file_sha256(path)
        for path in (source, baseline)
    }
    if before[os.path.relpath(baseline, REPO_ROOT)] != BASELINE_SHA256:
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
        current_metadata = native_interface_metadata(current)
        previous_metadata = native_interface_metadata(previous)
        controls = control_behavior(current)
        scope = unresolved_scope(current)
        report = {
            "source": os.path.relpath(source, REPO_ROOT),
            "baseline": os.path.relpath(baseline, REPO_ROOT),
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
            "native_interface_metadata_unchanged": current_metadata
            == previous_metadata,
            "native_interface_metadata_changes": [
                {
                    "object": name,
                    "current": current_metadata.get(name),
                    "baseline": previous_metadata.get(name),
                }
                for name in sorted(set(current_metadata) | set(previous_metadata))
                if current_metadata.get(name) != previous_metadata.get(name)
            ],
            "native_control_behavior": controls,
            "unresolved_scope": scope,
        }
    finally:
        for doc in reversed(docs):
            App.closeDocument(doc.Name)
    report["file_hashes_after"] = {
        os.path.relpath(path, REPO_ROOT): file_sha256(path)
        for path in (source, baseline)
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
        and report["native_interface_metadata_unchanged"]
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
