"""Independent read-only saved-assembly audit of the current gondola.

This audit tests rigid CAD envelopes. It does not certify friction retention,
metric-thread strength, printed running fits, tape adhesion or hinge fatigue.
"""

import json
import os
import sys
from pathlib import Path

import FreeCAD as App
import Mesh
import Part

from gondola.bundle import print_artifact_paths
from gondola.cad import (
    translated_shape,
    world_shape,
)
from gondola.config import ARTIFACT_SCHEMA_VERSION, ARTIFACT_STEM, OUTPUT_DIR, REPO_ROOT
from gondola.contracts.design import (
    DESIGN_REVISION,
    EXCLUDED_EQUIPMENT,
    EXPECTED_INVENTORY,
    HARDWARE_MATERIALS,
    MANUFACTURING_DECISION,
    MAX_PRINT_PART_DIMENSION_MM,
    PUBLISHED_PROCESS_SIZE_MM,
    PURCHASED_HARDWARE_QUANTITIES,
    SCOPED_LISTED_EQUIPMENT_MASS_G,
    release_status,
)
from gondola.contracts.drive import GEARS, SELECTED_DRIVE, drive_for_document
from gondola.mass_budget import mass_budget
from gondola.parts import equipment_mounts as mounts
from gondola.parts import propulsion
from gondola.print_export import (
    MESH_PARAMETERS,
    PRINT_PROCESS_DESCRIPTION,
    SIZE_NUMERICAL_TOLERANCE_MM,
    geometry_comparison,
    local_part_dimensions,
    mesh_from_shape,
    print_entry_inventory_check,
    print_entry_manufacturing_check,
    print_shape,
    print_size_declaration_check,
    print_solid_comparison,
)
from gondola.print_materials import print_specification
from gondola.procurement import purchase_code
from gondola.provenance import file_sha256, source_fingerprint

from . import manufacturing, propulsion_wiring
from .equipment import mounting_check
from .evidence import overlap_failures
from .geometry import (
    belongs_to_group,
    compare_mesh_surfaces,
    intersection_volume,
    local_shape,
)
from .propulsion_evidence import PROPULSION_EVIDENCE_COUNTS, propulsion_evidence_check
from .rail_access import rail_attachment_service
from .rail_mount import rail_check

TOL = 1e-5
V = App.Vector


def expected_pair(a, b, first_shape=None, second_shape=None):
    for prefix in ("Port", "Starboard"):
        if {a.Name, b.Name} == {prefix + "Shaft", prefix + "PropellerDisk"}:
            return "Motor shaft enters the conservative propeller hub envelope"
        if {a.Name, b.Name} == {prefix + "ServoHorn", prefix + "Servo"}:
            if first_shape is None or second_shape is None:
                return None
            from .servo_interface import horn_spline_contact

            horn, servo = (
                (first_shape, second_shape)
                if a.Name.endswith("ServoHorn")
                else (second_shape, first_shape)
            )
            group = a.Document.getObject(prefix + "InputDrive")
            if group is None:
                return None
            frame = group.getGlobalPlacement()
            contact = horn_spline_contact(
                horn, servo, frame.Base, frame.Rotation.multVec(V(0, 1, 0))
            )
            if contact["passed"]:
                return "OEM female spline teeth lie within the sourced smooth servo spline envelope; actual tooth fit is unverified"
    return None


def pair_collisions(items, fixed=()):
    """Bounding-box broad phase preserves every spatially nearby solid."""
    collisions = []
    for index, (name, shape) in enumerate(items):
        for other_name, other in list(fixed) + list(items[index + 1 :]):
            vol = intersection_volume(shape, other)
            if vol > TOL:
                collisions.append(
                    {"first": name, "second": other_name, "intersection_mm3": vol}
                )
    return collisions


def path_checks(moving, fixed, vectors):
    rows = []
    for vector in vectors:
        hits = []
        for name, shape in moving:
            moved_shape = translated_shape(shape, *vector)
            for other_name, other in fixed:
                overlap_volume = intersection_volume(moved_shape, other)
                if overlap_volume > TOL:
                    hits.append(
                        {
                            "moving": name,
                            "fixed": other_name,
                            "intersection_mm3": overlap_volume,
                        }
                    )
        rows.append({"translation_mm": list(vector), "collisions": hits})
    return {"samples": rows, "passed": all(not r["collisions"] for r in rows)}


def neutral_check(objects, shapes):
    unexpected, expected = [], []
    for i, obj in enumerate(objects):
        for other in objects[i + 1 :]:
            volume = intersection_volume(shapes[obj.Name], shapes[other.Name])
            if volume <= TOL:
                continue
            row = {"first": obj.Name, "second": other.Name, "intersection_mm3": volume}
            reason = expected_pair(obj, other, shapes[obj.Name], shapes[other.Name])
            if reason:
                row["reason"] = reason
                expected.append(row)
            else:
                unexpected.append(row)
    return {
        "unexpected": unexpected,
        "intentional_reference_envelopes": expected,
        "passed": not unexpected,
    }


def hardware_check(registry):
    purchased_parts = list(registry.HardwareParts)
    printed_parts = list(registry.PrintedParts) + list(registry.FitCoupons)
    rows = []
    printed_names = {o.Name for o in printed_parts}
    for obj in purchased_parts:
        standard = str(getattr(obj, "ThreadStandard", ""))
        sku = str(getattr(obj, "HardwareSKU", ""))
        thread_diameter = float(obj.NominalThreadDiameter.Value)
        thread_pitch = float(obj.ThreadPitch.Value)
        if sku.startswith("M3"):
            expected_diameter, expected_pitch = 3.0, 0.5
            thread_description_matches = "M3" in standard
        elif sku.startswith("M2"):
            expected_diameter, expected_pitch = 2.0, 0.4
            thread_description_matches = "M2" in standard
        elif sku.startswith("M1_6"):
            expected_diameter, expected_pitch = 1.6, 0.35
            thread_description_matches = "M1.6" in standard
        elif sku.startswith("M1_4"):
            expected_diameter, expected_pitch = 1.4, 0.3
            thread_description_matches = "M1.4" in standard
        elif sku in {gear.sku for gear in GEARS.values()}:
            expected_diameter, expected_pitch = 3.0, 0.5
            thread_description_matches = "M3" in standard
        else:
            expected_diameter, expected_pitch = 0.0, 0.0
            thread_description_matches = "unthreaded" in standard.lower()
        thread_metadata_matches = (
            thread_description_matches
            and abs(thread_diameter - expected_diameter) < TOL
            and abs(thread_pitch - expected_pitch) < TOL
        )
        material_matches = (
            sku in HARDWARE_MATERIALS
            and str(getattr(obj, "MaterialSelection", "")) == HARDWARE_MATERIALS[sku]
        )
        excluded = obj.Name not in printed_names and not bool(
            getattr(obj, "PrintPart", False)
        )
        row = {
            "part": obj.Name,
            "sku": sku,
            "thread_standard": standard,
            "thread_metadata_matches_part": thread_metadata_matches,
            "interface_specification_present": thread_metadata_matches,
            "material_matches_purchase_specification": material_matches,
            "excluded_from_print_registry": excluded,
            "passed": thread_metadata_matches
            and excluded
            and bool(sku)
            and material_matches,
        }
        rows.append(row)
    clamp_names = {o.Name for o in registry.RailLocks}
    source = Path(registry.Document.FileName)
    bom = json.loads((source.parent / (source.stem + "_hardware_bom.json")).read_text())
    bom_instance_names = [name for row in bom["items"] for name in row["instances"]]
    material_rows = []
    for row in bom["items"]:
        materials = {
            str(getattr(registry.Document.getObject(name), "MaterialSelection", ""))
            for name in row["instances"]
        }
        material_rows.append(
            {
                "purchase_code": row.get("purchase_code", row["sku"]),
                "quantity": row["quantity"],
                "materials": sorted(materials),
                "passed": len(materials) == 1
                and row["quantity"] == len(row["instances"]),
            }
        )
    bom_inventory_matches = (
        len(bom_instance_names) == len(purchased_parts)
        and len(set(bom_instance_names)) == len(purchased_parts)
        and set(bom_instance_names) == {o.Name for o in purchased_parts}
        and all(row["passed"] for row in material_rows)
    )
    expected_purchases = {
        purchase_code(sku, HARDWARE_MATERIALS[sku]): quantity
        for sku, quantity in PURCHASED_HARDWARE_QUANTITIES.items()
    }
    purchase_counts = {row["purchase_code"]: row["quantity"] for row in bom["items"]}
    return {
        "purchased_item_count": len(purchased_parts),
        "parts": rows,
        "bill_of_materials": {
            "material_specific_purchases": material_rows,
            "every_hardware_object_included_once": bom_inventory_matches,
            "declared_purchase_specifications": purchase_counts == expected_purchases,
        },
        "all_rail_clamps_are_purchased": clamp_names
        <= {o.Name for o in purchased_parts},
        "thread_retention_simulated": False,
        "passed": bool(rows)
        and all(r["passed"] for r in rows)
        and bom_inventory_matches
        and purchase_counts == expected_purchases
        and clamp_names <= {o.Name for o in purchased_parts},
    }


def equipment_scope_check(doc, registry, objects, shapes):
    forbidden = [
        o.Name
        for o in registry.ReferenceParts
        if any(token in o.Name.lower() for token in ("yaw", "finservo", "hl3604"))
    ]
    reserves = []
    expected = (
        "XT30ServiceReserve",
        "CapacitorServiceReserve",
        "PortPhaseLeadLoopReserve",
        "StarboardPhaseLeadLoopReserve",
        "FCWiringClearanceReserve",
        "RadioNegativeXConnectorReserve",
        "RadioPositiveXConnectorReserve",
        "PASConnectorReserve",
        "MTF02PConnectorReserve",
    )
    for name in expected:
        obj = doc.getObject(name)
        if obj is None:
            reserves.append({"part": name, "passed": False, "error": "missing"})
            continue
        shape = world_shape(obj)
        hits = pair_collisions(
            [(name, shape)], [(o.Name, shapes[o.Name]) for o in objects]
        )
        reserves.append(
            {
                "part": name,
                "role": str(getattr(obj, "Role", "")),
                "physical_geometry_collisions": hits,
                "minimum_z_mm": shape.BoundBox.ZMin,
                "planning_only": True,
                "passed": obj in registry.ClearanceVolumes
                and obj not in registry.ReferenceParts
                and obj not in registry.PrintedParts
                and shape.BoundBox.ZMin >= 0
                and not hits,
            }
        )
    return {
        "user_scope_exclusions": EXCLUDED_EQUIPMENT,
        "scoped_listed_equipment_mass_g": float(
            registry.ScopedListedEquipmentMassGrams
        ),
        "not_all_up_mass": True,
        "excluded_device_references_found": forbidden,
        "new_electrical_space_reservations": reserves,
        "cable_and_OEM_limitations": "Reserve shapes are not measured components, flexible cable routing or proof of cable slack at bounded ±180 degrees. OEM motor retention and measured X06 horn connection remain unresolved.",
        "passed": not forbidden
        and abs(
            float(registry.ScopedListedEquipmentMassGrams)
            - SCOPED_LISTED_EQUIPMENT_MASS_G
        )
        < TOL
        and all(row["passed"] for row in reserves),
    }


def tilt_check(doc, registry, objects):
    rows = []
    pods = list(registry.TiltingPods)
    for pod in pods:
        moving = [o for o in objects if belongs_to_group(o, pod)]
        fixed = [o for o in objects if o not in moving]
        other_placements = {o.Name: o.Placement.copy() for o in pods if o != pod}
        hits, independent, minimum_z = [], True, float("inf")
        original_tilt = float(pod.Tilt)
        try:
            for angle in range(-180, 181, 5):
                pod.Tilt = angle
                doc.recompute()
                independent &= all(
                    o.Placement.isSame(other_placements[o.Name], 1e-7)
                    for o in pods
                    if o != pod
                )
                # The input drive follows this pose; query its live placement
                # once per pose, then reuse each shape across output members.
                fixed_shapes = {other.Name: world_shape(other) for other in fixed}
                for obj in moving:
                    moving_shape = world_shape(obj)
                    minimum_z = min(
                        minimum_z, moving_shape.optimalBoundingBox(False, False).ZMin
                    )
                    for other in fixed:
                        if expected_pair(
                            obj, other, moving_shape, fixed_shapes[other.Name]
                        ):
                            continue
                        overlap_volume = intersection_volume(
                            moving_shape, fixed_shapes[other.Name]
                        )
                        if overlap_volume > TOL:
                            hits.append(
                                {
                                    "angle_deg": angle,
                                    "moving": obj.Name,
                                    "fixed": other.Name,
                                    "intersection_mm3": overlap_volume,
                                }
                            )
        finally:
            pod.Tilt = original_tilt
            doc.recompute()
        rows.append(
            {
                "pod": pod.Name,
                "poses": 73,
                "independent": independent,
                "minimum_z_mm": minimum_z,
                "collisions": hits,
                "passed": independent and not hits and minimum_z >= -TOL,
            }
        )
    return {"pods": rows, "passed": len(rows) == 2 and all(r["passed"] for r in rows)}


def battery_check(doc, objects):
    """Screen the declared pack translation range, including its continuous sweep."""
    battery = doc.ModuleBatteryEnvelope
    contract = mounts.BATTERY_PLACEMENT_CONTRACT
    x_limit = contract["centre_x_limit_mm"]
    y_limit = contract["centre_y_limit_mm"]
    maximum_size = tuple(contract["maximum_size_mm"])
    original = tuple(
        float(getattr(battery, name).Value)
        for name in ("Length", "Width", "Height", "CentreX", "CentreY")
    )
    try:
        native_contract = json.loads(str(battery.BatteryPlacementContract))
    except (AttributeError, TypeError, ValueError):
        native_contract = None
    saved_placement = {
        "size_mm": list(original[:3]),
        "local_centre_xy_mm": list(original[3:]),
        "within_declared_size": all(
            0 < actual <= maximum + TOL
            for actual, maximum in zip(original[:3], maximum_size)
        ),
        "within_declared_centre_limits": (
            abs(original[3]) <= x_limit + TOL and abs(original[4]) <= y_limit + TOL
        ),
        "long_axis_along_y": abs(battery.InPlaneRotation.Value - 90) < TOL,
        "bottom_matches_adhesive_allowance": abs(
            battery.BottomZ.Value - mounts.SUPPORT_FACE_Z - mounts.ADHESIVE_ALLOWANCE
        )
        < TOL,
        "native_contract_matches": native_contract == contract,
    }
    saved_placement["passed"] = all(
        saved_placement[key]
        for key in (
            "within_declared_size",
            "within_declared_centre_limits",
            "long_axis_along_y",
            "bottom_matches_adhesive_allowance",
            "native_contract_matches",
        )
    )
    obstacles = [(obj.Name, world_shape(obj)) for obj in objects if obj != battery]
    parent = battery.getParentGeoFeatureGroup()
    # The union of every axis-aligned maximum pack translated throughout the
    # allowed XY rectangle is exactly this box, not merely sampled end poses.
    length, width, height = maximum_size
    swept = Part.makeBox(width + 2 * x_limit, length + 2 * y_limit, height)
    swept.Placement = parent.getGlobalPlacement().multiply(
        App.Placement(
            V(
                -width / 2 - x_limit,
                -length / 2 - y_limit,
                mounts.SUPPORT_FACE_Z + mounts.ADHESIVE_ALLOWANCE,
            ),
            App.Rotation(),
        )
    )
    swept_hits = [
        name for name, shape in obstacles if intersection_volume(swept, shape) > TOL
    ]
    tower_names = {"OpticalMountBase"}
    tower_gaps = [
        {"object": name, "minimum_gap_mm": swept.distToShape(shape)[0]}
        for name, shape in obstacles
        if name in tower_names
    ]
    from gondola.parts import optical_interface

    float_rows = []
    tower = next((obj for obj in objects if obj.Name == "OpticalMountBase"), None)
    component_bounds = optical_interface.base_component_proxies()
    expected_components = {name for name, _ in component_bounds}
    if tower is not None:
        for component, envelope in component_bounds:
            envelope = optical_interface.registration_bound(envelope)
            envelope.Placement = tower.getGlobalPlacement().multiply(envelope.Placement)
            gap = swept.distToShape(envelope)[0]
            float_rows.append(
                {
                    "component": component,
                    "minimum_gap_mm": gap,
                    "passed": gap >= contract["minimum_stack_tower_gap_mm"] - TOL,
                }
            )
    continuous = {
        "method": "Exact maximum-pack translation envelope over the entire declared XY rectangle",
        "local_size_mm": [width + 2 * x_limit, length + 2 * y_limit, height],
        "collisions": swept_hits,
        "stack_tower_gaps": tower_gaps,
        "tower_clamped_registration_gaps": float_rows,
        "tower_registration_scope": "Conservative XY/yaw assembly-registration component envelopes of the compact carrier foot and straight optical post at the selected host/side. Assembly clearance is not deliberate operating looseness; qualify foot seating, pointing retention and clamp friction.",
        "required_stack_tower_gap_mm": contract["minimum_stack_tower_gap_mm"],
        "passed": not swept_hits
        and bool(expected_components)
        and {row["component"] for row in float_rows} == expected_components
        and all(row["passed"] for row in float_rows)
        and {row["object"] for row in tower_gaps} == tower_names
        and all(
            row["minimum_gap_mm"] >= contract["minimum_stack_tower_gap_mm"] - TOL
            for row in tower_gaps
        ),
    }
    rows = []
    try:
        for size in ((61, 16, 15), maximum_size):
            battery.Length, battery.Width, battery.Height = size
            for x in (-x_limit, 0, x_limit):
                for y in (-y_limit, 0, y_limit):
                    battery.CentreX, battery.CentreY = x, y
                    doc.recompute()
                    shape = world_shape(battery)
                    hits = [
                        name
                        for name, fixed in obstacles
                        if intersection_volume(shape, fixed) > TOL
                    ]
                    row = {
                        "size_mm": list(size),
                        "local_centre_xy_mm": [x, y],
                        "collisions": hits,
                    }
                    bounds = shape.optimalBoundingBox(False, False)
                    orientation = (
                        abs(bounds.XLength - size[1]) < TOL
                        and abs(bounds.YLength - size[0]) < TOL
                    )
                    covered = abs(shape.cut(swept).Volume) < TOL
                    rows.append(
                        dict(
                            row,
                            long_axis_along_y=orientation,
                            covered_by_continuous_envelope=covered,
                            passed=not hits and orientation and covered,
                        )
                    )
    finally:
        (
            battery.Length,
            battery.Width,
            battery.Height,
            battery.CentreX,
            battery.CentreY,
        ) = original
        doc.recompute()
    return {
        "contract": contract,
        "saved_placement": saved_placement,
        "cases": rows,
        "continuous_translation": continuous,
        "scope": "Pack geometry within the declared translation limits only; move the rail carrier for larger trim changes. Actual adhesive contact, selected pack and retention remain unqualified.",
        "passed": saved_placement["passed"]
        and continuous["passed"]
        and len(rows) == 18
        and all(row["passed"] for row in rows),
    }


def export_check(source, registry):
    """Read back every STL/STEP and bind exported geometry to current CAD/source."""
    folder = source.parent / (source.stem + "_print_parts")
    manifest = json.loads((folder / "print_manifest.json").read_text())
    # Reject path traversal and duplicate files before opening manifest paths.
    print_artifact_paths(source.parent, source.stem, manifest)
    fingerprint = source_fingerprint()
    identity = {
        "schema_version": manifest.get("schema_version"),
        "manifest_source_fingerprint": manifest.get("source_fingerprint"),
        "native_source_fingerprint": str(getattr(registry, "SourceFingerprint", "")),
        "current_source_fingerprint": fingerprint,
        "mesh_parameters": manifest.get("mesh_parameters"),
        "release_status_matches_contract": manifest.get("release_status")
        == release_status(),
        "size_policy_matches_contract": manifest.get("maximum_print_part_dimension_mm")
        == MAX_PRINT_PART_DIMENSION_MM
        and manifest.get("size_numerical_tolerance_mm") == SIZE_NUMERICAL_TOLERANCE_MM
        and manifest.get("published_fabrication_size_mm") == PUBLISHED_PROCESS_SIZE_MM,
        "process_decision_matches_contract": manifest.get("manufacturing_decision")
        == MANUFACTURING_DECISION
        and manifest.get("process") == PRINT_PROCESS_DESCRIPTION
        and manifest.get("manufacturing") == print_specification(),
    }
    identity["passed"] = (
        identity["schema_version"] == ARTIFACT_SCHEMA_VERSION
        and identity["manifest_source_fingerprint"] == fingerprint
        and identity["native_source_fingerprint"] == fingerprint
        and identity["mesh_parameters"] == MESH_PARAMETERS
        and identity["release_status_matches_contract"]
        and identity["size_policy_matches_contract"]
        and identity["process_decision_matches_contract"]
    )
    printed = list(registry.PrintedParts) + list(registry.FitCoupons)
    names = {o.Name for o in printed}
    bought_names = {o.Name for o in registry.HardwareParts}
    rows, exported_names = [], []
    for entry in manifest["parts"]:
        native_inventory = print_entry_inventory_check(
            entry, registry.PrintedParts, registry.FitCoupons
        )
        instances = [registry.Document.getObject(name) for name in entry["instances"]]
        exported_names.extend(entry["instances"])
        if not instances or any(obj is None for obj in instances):
            rows.append(
                {
                    "sku": entry["sku"],
                    "passed": False,
                    "error": "Missing native print instance",
                }
            )
            continue
        oriented_shapes = {obj.Name: print_shape(obj) for obj in instances}
        manufacturing_matches = print_entry_manufacturing_check(entry, instances)
        master = oriented_shapes[instances[0].Name]
        local_sizes = {obj.Name: local_part_dimensions(obj) for obj in instances}
        export_sizes = {}
        for name, shape in oriented_shapes.items():
            bounds = shape.optimalBoundingBox(False, False)
            export_sizes[name] = [bounds.XLength, bounds.YLength, bounds.ZLength]
        equivalence = []
        for obj in instances[1:]:
            comparison = print_solid_comparison(master, oriented_shapes[obj.Name], TOL)
            equivalence.append({"part": obj.Name, **comparison})
        mesh_path, step_path = folder / entry["file"], folder / entry["step_file"]
        actual_hashes = {
            "file_sha256": file_sha256(mesh_path),
            "step_sha256": file_sha256(step_path),
        }
        hashes_match = all(
            entry.get(key) == value for key, value in actual_hashes.items()
        )
        mesh = Mesh.Mesh(str(mesh_path))
        regenerated_mesh = mesh_from_shape(master)
        mesh_comparison = compare_mesh_surfaces(mesh, regenerated_mesh)
        mesh_matches = mesh_comparison["passed"]
        step = Part.Shape()
        step.read(str(step_path))
        step_comparison = print_solid_comparison(master, step, TOL)
        step_matches = step_comparison["passed"]
        bb = mesh.BoundBox
        sizes = [bb.XLength, bb.YLength, bb.ZLength]
        size_evidence = print_size_declaration_check(
            entry, local_sizes, export_sizes, sizes
        )
        published_size_checks = size_evidence["actual_stl_size_checks"][
            "within_published_fabrication_size"
        ]
        good = (
            master.isValid()
            and len(master.Solids) == 1
            and mesh.isSolid()
            and mesh.countComponents() == 1
            and hashes_match
            and mesh_matches
            and step_matches
            and size_evidence["passed"]
            and entry["quantity"] == len(instances)
            and native_inventory["passed"]
            and manufacturing_matches
            and all(r["passed"] for r in equivalence)
            and not (set(entry["instances"]) & bought_names)
        )
        rows.append(
            {
                "sku": entry["sku"],
                "export_hashes": actual_hashes,
                "hashes_match_manifest": hashes_match,
                "stl_surface_matches_saved_native_part": mesh_matches,
                "stl_surface_comparison": mesh_comparison,
                "step_matches_saved_native_part": step_matches,
                "step_geometry_comparison": step_comparison,
                "actual_stl_bounds_mm": sizes,
                "watertight_mesh": mesh.isSolid(),
                "mesh_components": mesh.countComponents(),
                "within_published_fabrication_size": published_size_checks,
                "size_evidence": size_evidence,
                "quantity": entry["quantity"],
                "native_inventory": native_inventory,
                "manufacturing_matches": manufacturing_matches,
                "deduplicated_geometry": equivalence,
                "passed": good,
            }
        )
    count = sum(r["quantity"] for r in manifest["parts"])
    each_once = len(exported_names) == len(names) and set(exported_names) == names
    return {
        "process": "SLS/MJF powder-bed PA12",
        "supplier_single_piece_acceptance_still_required": True,
        "published_fabrication_size_mm": PUBLISHED_PROCESS_SIZE_MM,
        "maximum_print_part_dimension_mm": MAX_PRINT_PART_DIMENSION_MM,
        "published_size_guide_scope": MANUFACTURING_DECISION["size_guide_scope"],
        "one_piece_machine_fit_proven": False,
        "source_identity": identity,
        "unique_stl_count": len(rows),
        "installed_printed_count": len(registry.PrintedParts),
        "coupon_count": len(registry.FitCoupons),
        "parts": rows,
        "quantity_sum": count,
        "every_print_object_exported_once": each_once,
        "no_purchased_hardware_in_stls": not bool(set(exported_names) & bought_names),
        "passed": identity["passed"]
        and bool(rows)
        and all(r["passed"] for r in rows)
        and count == len(printed)
        and each_once
        and not (set(exported_names) & bought_names),
    }


def detailed_propulsion_evidence(doc, source):
    from .motion_clearance import carrier_metal_clearance_check
    from .propulsion import (
        bearing_post_roots_check,
        fixed_servo_datum_check,
        gear_engagement_check,
        servo_mount_check,
    )
    from .relative_motion import relative_motion_check
    from .servo_module import bridge_joint_check, servo_module_service_check

    configuration = drive_for_document(doc)
    path = source.parent / (source.stem + "_propulsion_validation.json")
    if not path.exists():
        return {
            "passed": False,
            "error": "Final local propulsion validation JSON is missing",
            "expected_file": str(path),
        }
    evidence = json.loads(path.read_text())
    comparisons = []
    # The local audit builds fresh source geometry. Bind its hardware and device
    # envelopes to the saved assembly too, so a passing new-source retention test
    # cannot endorse missing retaining material or a changed motor in the native file.
    reference_doc = App.newDocument("SavedPropulsionComparison")
    try:
        reference = propulsion.build_propulsion_module(
            reference_doc, drive=configuration
        )
        reference_doc.recompute()
        reference_print_count = len(reference["printed"])
        expected_parts = (
            reference["printed"]
            + reference["hardware"]
            + reference["references"]
            + reference["clearances"]
        )
        pairs = [(doc.getObject(obj.Name), local_shape(obj)) for obj in expected_parts]
    finally:
        App.closeDocument(reference_doc.Name)
    for obj, expected in pairs:
        if obj is None:
            comparisons.append(
                {
                    "object": "missing propulsion part",
                    "difference_mm3": None,
                    "passed": False,
                }
            )
            continue
        comparison = geometry_comparison(local_shape(obj), expected)
        comparisons.append(
            {
                "object": obj.Name,
                **comparison,
                "passed": all(
                    comparison[key] < TOL
                    for key in (
                        "difference_mm3",
                        "volume_difference_mm3",
                        "bounds_difference_mm",
                    )
                ),
            }
        )
    volume_failures = [
        {"field": row["field"], "value": row["volume_mm3"]}
        for row in overlap_failures(evidence, TOL)
    ]
    evidence_check = propulsion_evidence_check(evidence)
    saved_datums = [
        fixed_servo_datum_check(doc, prefix) for prefix in ("Port", "Starboard")
    ]
    saved_servo_mounts = [
        servo_mount_check(doc, prefix) for prefix in ("Port", "Starboard")
    ]
    saved_module = {
        "group": doc.MainPropulsionModule,
        "printed": list(doc.DesignRegistry.PrintedParts),
        "hardware": list(doc.DesignRegistry.HardwareParts),
        "references": list(doc.DesignRegistry.ReferenceParts),
    }
    saved_post_roots = bearing_post_roots_check(doc)
    saved_bridge_joint = bridge_joint_check(doc, saved_module)
    saved_servo_service = servo_module_service_check(doc, saved_module)
    saved_carrier_clearances = [
        carrier_metal_clearance_check(doc, prefix) for prefix in ("Port", "Starboard")
    ]
    saved_gear_engagement = [
        gear_engagement_check(doc, prefix) for prefix in ("Port", "Starboard")
    ]
    saved_relative_motion = relative_motion_check(
        doc,
        {
            "printed": list(doc.DesignRegistry.PrintedParts),
            "hardware": list(doc.DesignRegistry.HardwareParts),
            "references": list(doc.DesignRegistry.ReferenceParts),
        },
    )
    evidence_ok = (
        evidence.get("passed") is True
        and evidence.get("gear_configuration") == configuration.key
        and evidence_check["passed"]
        and reference_print_count == PROPULSION_EVIDENCE_COUNTS["geometry"]
        and evidence.get("all_bought_parts_excluded_from_prints") is True
    )
    return {
        "gear_configuration": configuration.key,
        "local_configuration_matches_saved": evidence.get("gear_configuration")
        == configuration.key,
        "source_file": os.path.relpath(path, REPO_ROOT),
        "source_sha256": file_sha256(path),
        "saved_servo_datums": saved_datums,
        "saved_servo_mounts": saved_servo_mounts,
        "saved_bearing_post_roots": saved_post_roots,
        "saved_bridge_joint": saved_bridge_joint,
        "saved_servo_module_service": saved_servo_service,
        "saved_carrier_metal_clearances": saved_carrier_clearances,
        "saved_gear_engagement": saved_gear_engagement,
        "saved_relative_motion": saved_relative_motion,
        "saved_shape_source_comparisons": comparisons,
        "source_reference_print_count": reference_print_count,
        "local_overlap_failures": volume_failures,
        "local_checks": evidence,
        "required_evidence_inventory": evidence_check["inventory"],
        "local_evidence_row_failures": evidence_check["row_failures"],
        "scope": "Recomputed geared-drive mesh including axial travel, bearings, split output shafts, continuous nominal cross-motion separation, carrier/metal reserves and ordered service paths. Functional contacts are classified separately. Sample fits, loaded retention, unmodeled set-screw/OEM hardware and cable travel remain physical qualification requirements.",
        "passed": evidence_ok
        and all(row["passed"] for row in saved_datums)
        and all(row["passed"] for row in saved_servo_mounts)
        and all(row["passed"] for row in saved_post_roots)
        and saved_bridge_joint["passed"]
        and saved_servo_service["passed"]
        and all(row["passed"] for row in saved_carrier_clearances)
        and all(row["passed"] for row in saved_gear_engagement)
        and saved_relative_motion["passed"]
        and not volume_failures
        and all(row["passed"] for row in comparisons),
    }


def validate(source=None):
    from .equipment_options import compatibility_check

    source = (
        Path(source).resolve() if source else OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")
    )
    from .propulsion import validate as validate_propulsion

    before = {source.name: file_sha256(source)}
    fingerprint_before = source_fingerprint()
    manifest = json.loads(
        (
            source.parent / (source.stem + "_print_parts") / "print_manifest.json"
        ).read_text()
    )
    artifact_paths = print_artifact_paths(source.parent, source.stem, manifest)
    artifact_hashes_before = {
        name: file_sha256(path) for name, path in artifact_paths.items()
    }
    doc = App.openDocument(str(source), hidden=True)
    try:
        doc.recompute()
        configuration = drive_for_document(doc)
        if configuration != SELECTED_DRIVE:
            raise ValueError(
                "Saved gear configuration differs from the source-selected design; "
                "rebuild and review the configured baseline before full validation."
            )
        validate_propulsion(source, drive=configuration)
        r = doc.DesignRegistry
        printed = list(r.PrintedParts)
        objects = list(
            dict.fromkeys(
                printed
                + list(r.ReferenceParts)
                + list(r.HardwareParts)
                + list(r.TapeReferences)
            )
        )
        shapes = {o.Name: world_shape(o) for o in objects}
        report = {
            "gear_configuration": configuration.key,
            "revision": DESIGN_REVISION,
            "mass_budget": mass_budget(r.PrintedParts, r.HardwareParts),
            "source": os.path.relpath(source, REPO_ROOT),
            "scope": "Independent saved-file rigid-envelope audit; no strength, friction, fit, tape or flight qualification. Local propulsion evidence is recomputed from current source on every run.",
            "source_hashes_before": before,
            "source_fingerprint": fingerprint_before,
            "artifact_hashes_before": artifact_hashes_before,
            "invalid_geometry": [
                o.Name
                for o in objects + list(r.FitCoupons)
                if o.Shape.isNull() or not o.Shape.isValid()
            ],
            "non_single_print_solids": [
                o.Name for o in printed + list(r.FitCoupons) if len(o.Shape.Solids) != 1
            ],
            "below_balloon_plane": [
                o.Name
                for o in objects
                if shapes[o.Name].optimalBoundingBox(False, False).ZMin < -TOL
            ],
        }
        print(
            "Checking neutral assembly, rail/tape, dedicated mounts and purchased hardware",
            flush=True,
        )
        report["neutral_assembly"] = neutral_check(objects, shapes)
        report["continuous_rail"] = rail_check(r, shapes)
        report["equipment_mounts"] = mounting_check(doc)
        report["equipment_options"] = compatibility_check(doc)
        report["propulsion_wire_planning"] = propulsion_wiring.check(doc)
        report["purchased_hardware"] = hardware_check(r)
        report["assembly_inventory"] = {
            "installed_printed_parts": len(printed),
            "purchased_hardware_items": len(r.HardwareParts),
            "fit_sample_prints": len(r.FitCoupons),
            "equipment_mount_count": len(r.EquipmentMounts),
            "single_rail_count": len(r.RailSegments),
            "passed": len(printed) == EXPECTED_INVENTORY["installed_prints"]
            and len(r.HardwareParts) == EXPECTED_INVENTORY["purchased_hardware"]
            and len(r.FitCoupons) == EXPECTED_INVENTORY["fit_coupons"]
            and len(r.EquipmentMounts) == EXPECTED_INVENTORY["equipment_mounts"]
            and len(r.RailSegments) == EXPECTED_INVENTORY["rails"],
        }
        print(
            json.dumps(
                {
                    "neutral_passed": report["neutral_assembly"]["passed"],
                    "unexpected": report["neutral_assembly"]["unexpected"],
                }
            ),
            flush=True,
        )
        print(
            "Checking side fastener access and populated rail-module removal",
            flush=True,
        )
        report["module_service"] = rail_attachment_service(doc, r, objects)
        print("Checking independent tilt and equipment service clearances", flush=True)
        report["independent_tilt"] = tilt_check(doc, r, objects)
        external = [
            (o.Name, shapes[o.Name])
            for o in objects
            if not belongs_to_group(o, doc.MainPropulsionModule)
        ]
        sweep_rows = []
        for obj in r.ClearanceVolumes:
            if "Sweep" not in obj.Name:
                continue
            hits = pair_collisions([(obj.Name, world_shape(obj))], external)
            sweep_rows.append(
                {"sweep": obj.Name, "external_collisions": hits, "passed": not hits}
            )
        report["continuous_external_rotor_sweeps"] = {
            "checks": sweep_rows,
            "passed": len(sweep_rows) == 2 and all(row["passed"] for row in sweep_rows),
        }
        report["battery_reference_fit"] = battery_check(doc, objects)
        print("Checking PA12 export identity and saved-file preservation", flush=True)
        report["print_export"] = export_check(source, r)
        report["local_propulsion_evidence"] = detailed_propulsion_evidence(doc, source)
        report["pa12_manufacturing_review"] = manufacturing.review(doc, r)
        report["equipment_scope_and_reserves"] = equipment_scope_check(
            doc, r, objects, shapes
        )
        report["source_hashes_after"] = {source.name: file_sha256(source)}
        report["saved_files_unchanged"] = before == report["source_hashes_after"]
        report["artifact_hashes"] = {
            name: file_sha256(path) for name, path in artifact_paths.items()
        }
        report["artifacts_unchanged"] = (
            artifact_hashes_before == report["artifact_hashes"]
        )
        report["source_code_unchanged"] = fingerprint_before == source_fingerprint()
        checks = (
            "neutral_assembly",
            "continuous_rail",
            "equipment_mounts",
            "equipment_options",
            "propulsion_wire_planning",
            "purchased_hardware",
            "assembly_inventory",
            "module_service",
            "independent_tilt",
            "continuous_external_rotor_sweeps",
            "battery_reference_fit",
            "print_export",
            "local_propulsion_evidence",
            "pa12_manufacturing_review",
            "equipment_scope_and_reserves",
        )
        report["passed"] = (
            report["saved_files_unchanged"]
            and report["artifacts_unchanged"]
            and report["source_code_unchanged"]
            and not report["invalid_geometry"]
            and not report["non_single_print_solids"]
            and not report["below_balloon_plane"]
            and all(report[name]["passed"] for name in checks)
        )
        target = source.parent / (source.stem + "_validation.json")
        target.write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "report": str(target),
                    "passed": report["passed"],
                    "checks": {name: report[name]["passed"] for name in checks},
                },
                indent=2,
            ),
            flush=True,
        )
        return report
    finally:
        App.closeDocument(doc.Name)


if __name__ == "__main__":
    result = validate(sys.argv[1] if len(sys.argv) > 1 else None)
    if not result["passed"]:
        raise SystemExit(
            "Independent assembly audit failed; inspect the validation JSON."
        )
