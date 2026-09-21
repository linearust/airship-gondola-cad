"""Independent read-only saved-assembly audit of the current gondola.

This audit tests rigid CAD envelopes. It does not certify friction retention,
metric-thread strength, printed running fits, tape adhesion or hinge fatigue.
"""

import itertools
import json
import math
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
    CREALLO_GUIDE_URL,
    DESIGN_REVISION,
    EXCLUDED_EQUIPMENT,
    EXPECTED_INVENTORY,
    HARDWARE_MATERIALS,
    MANUFACTURING_DECISION,
    MODULE_STATIONS,
    NOTION_LAST_EDITED,
    NOTION_URL,
    PUBLISHED_PROCESS_SIZE_MM,
    PURCHASED_HARDWARE_QUANTITIES,
    SCOPED_LISTED_EQUIPMENT_MASS_G,
    release_status,
)
from gondola.mass_budget import mass_budget
from gondola.parts import equipment_mounts as mounts
from gondola.parts import propulsion, rail, stack_interface
from gondola.print_export import (
    MESH_PARAMETERS,
    geometry_comparison,
    mesh_from_shape,
    print_entry_inventory_check,
    print_shape,
)
from gondola.procurement import purchase_code
from gondola.provenance import file_sha256, source_fingerprint

from .baseline import module_control_bindings
from .equipment import mounting_check
from .evidence import overlap_failures
from .geometry import (
    belongs_to_group,
    compare_mesh_surfaces,
    intersection_volume,
    local_shape,
)

TOL = 1e-5
V = App.Vector


def expected_pair(a, b):
    for prefix in ("Port", "Starboard"):
        if {a.Name, b.Name} == {prefix + "Shaft", prefix + "PropellerDisk"}:
            return "Motor shaft enters the conservative propeller hub envelope"
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
            reason = expected_pair(obj, other)
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


def rail_shoe_section(shapes, centre_y=0):
    """Isolate actual printed capture material below the board/frame deck."""
    compound = Part.makeCompound(shapes)
    bounds = compound.optimalBoundingBox(False, False)
    band = Part.makeBox(
        bounds.XLength + 2,
        rail.SHOE_WIDTH,
        rail.HEAD_TOP + rail.CLEARANCE - rail.SHOE_BOTTOM,
        V(bounds.XMin - 1, centre_y - rail.SHOE_WIDTH / 2, rail.SHOE_BOTTOM),
    )
    return compound.common(band)


def rail_check(registry, shapes):
    objects = list(registry.RailSegments)
    rows = []
    for obj in objects:
        rail_shape = local_shape(obj)
        comparison = geometry_comparison(rail_shape, rail.rail_shape())
        base_samples = []
        sample_count = math.ceil(rail.LENGTH / 3)
        for index in range(sample_count):
            x = -rail.LENGTH / 2 + (index + 0.5) * rail.LENGTH / sample_count
            base_samples.append(
                {
                    "x_mm": x,
                    "in_unbroken_base": rail_shape.isInside(V(x, 0, 0.5), TOL, True),
                }
            )
        relief_samples = []
        relief_range = math.ceil(rail.LENGTH / rail.LAND_PITCH)
        for i in range(-relief_range, relief_range + 1):
            x = (i + 0.5) * rail.LAND_PITCH
            if abs(x) >= rail.LENGTH / 2:
                continue
            relief_samples.append(
                {
                    "x_mm": x,
                    "base_present": rail_shape.isInside(V(x, 0, 0.5), TOL, True),
                    "head_absent": not rail_shape.isInside(V(x, 0, 6.2), TOL, True),
                }
            )
        bounds = rail_shape.optimalBoundingBox(False, False)
        pad_rows = []
        for x in rail.PAD_CENTRES:
            pad = rail.rounded_plate(x)
            pad_bounds = pad.optimalBoundingBox(False, False)
            margin = min(pad_bounds.XMin - bounds.XMin, bounds.XMax - pad_bounds.XMax)
            missing_volume = abs(pad.cut(rail_shape).Volume)
            pad_rows.append(
                {
                    "centre_x_mm": x,
                    "pad_x_bounds_mm": [pad_bounds.XMin, pad_bounds.XMax],
                    "nearest_rail_end_margin_mm": margin,
                    "missing_pad_material_mm3": missing_volume,
                    "passed": margin >= -TOL and missing_volume < TOL,
                }
            )
        rail_world_bounds = shapes[obj.Name].optimalBoundingBox(False, False)
        installed_shoes = []
        for module in registry.Modules:
            shoe = rail_shoe_section(
                [
                    shapes[part.Name]
                    for part in registry.PrintedParts
                    if belongs_to_group(part, module)
                ],
                module.Placement.Base.y,
            )
            shoe_bounds = shoe.optimalBoundingBox(False, False)
            margin = min(
                shoe_bounds.XMin - rail_world_bounds.XMin,
                rail_world_bounds.XMax - shoe_bounds.XMax,
            )
            installed_shoes.append(
                {
                    "module": module.Name,
                    "actual_capture_material_x_bounds_mm": [
                        shoe_bounds.XMin,
                        shoe_bounds.XMax,
                    ],
                    "nearest_rail_end_margin_mm": margin,
                    "passed": shoe.Volume > TOL and margin >= -TOL,
                }
            )
        rows.append(
            {
                "object": obj.Name,
                "source_comparison": comparison,
                "size_mm": [bounds.XLength, bounds.YLength, bounds.ZLength],
                "unbroken_base_samples": base_samples,
                "relief_samples": relief_samples,
                "pad_end_margins": pad_rows,
                "installed_shoe_end_margins": installed_shoes,
                "fully_supported_nominal_shoe_centre_x_range_mm": [
                    bounds.XMin + rail.SHOE_LENGTH / 2,
                    bounds.XMax - rail.SHOE_LENGTH / 2,
                ],
                "single_valid_solid": rail_shape.isValid()
                and len(rail_shape.Solids) == 1,
                "passed": rail_shape.isValid()
                and len(rail_shape.Solids) == 1
                and comparison["difference_mm3"] < TOL
                and abs(bounds.XLength - rail.LENGTH) < TOL
                and all(row["passed"] for row in pad_rows + installed_shoes)
                and all(r["in_unbroken_base"] for r in base_samples)
                and all(r["base_present"] and r["head_absent"] for r in relief_samples),
            }
        )
    nominal_shoe = rail.shoe_shape()
    rail_section = rail.rail_shape(72, (-27, 27))
    tapes = [(o.Name, shapes[o.Name]) for o in registry.TapeReferences]
    phase_rows = []
    # An entire relief pitch, including half-millimetre offsets, checks that
    # the rigid short shoe bridges each gap throughout the sliding phase.
    for j in range(37):
        x = j * 0.5
        shoe = translated_shape(nominal_shoe, x=x)
        phase_rows.append(
            {
                "phase_x_mm": x,
                "slide_intersection_mm3": intersection_volume(shoe, rail_section),
                "lift_1mm_blocking_mm3": intersection_volume(
                    translated_shape(shoe, z=1), rail_section
                ),
                "lateral_1mm_blocking_mm3": intersection_volume(
                    translated_shape(shoe, y=1), rail_section
                ),
            }
        )
    nut_rotation = []
    for angle in (-45, 45):
        nut = rail.nut_shape().copy()
        nut.rotate(V(0, 0, rail.CLAMP_Z), V(0, 1, 0), angle)
        vol = intersection_volume(nut, nominal_shoe)
        nut_rotation.append(
            {
                "rotation_about_constrained_screw_axis_deg": angle,
                "blocking_intersection_mm3": vol,
                "blocked": vol > TOL,
            }
        )
    # Screen antirotation using the smallest published nut and a slot
    # enlarged by the supplier's 0.3 mm dimensional tolerance.
    pocket_tolerance = 0.3
    largest_slot = rail.NUT_POCKET_AF + pocket_tolerance
    smallest_slot = rail.NUT_POCKET_AF - pocket_tolerance
    tolerance_shoe = nominal_shoe.cut(rail.nut_pocket_void(largest_slot))
    tolerance_shoe = tolerance_shoe.cut(
        rail.half_turn(rail.nut_pocket_void(largest_slot))
    )
    tolerance_rotations = []
    for angle in (-45, 45):
        smallest_nut = rail.nut_shape(
            rail.fasteners.SQUARE_NUT_MIN_AF, rail.fasteners.SQUARE_NUT_MIN_HEIGHT
        )
        smallest_nut.rotate(V(0, 0, rail.CLAMP_Z), V(0, 1, 0), angle)
        vol = intersection_volume(smallest_nut, tolerance_shoe)
        tolerance_rotations.append(
            {
                "rotation_deg": angle,
                "blocking_intersection_mm3": vol,
                "passed": vol > TOL,
            }
        )
    minimum_diagonal = rail.fasteners.SQUARE_NUT_MIN_AF * math.sqrt(2)
    insertion_clearance = smallest_slot - rail.NUT_AF
    tolerance_capture = {
        "square_nut_af_range_mm": [rail.fasteners.SQUARE_NUT_MIN_AF, rail.NUT_AF],
        "square_nut_thickness_range_mm": [
            rail.fasteners.SQUARE_NUT_MIN_HEIGHT,
            rail.NUT_THICKNESS,
        ],
        "slot_width_range_mm": [smallest_slot, largest_slot],
        "minimum_total_insertion_clearance_mm": insertion_clearance,
        "minimum_square_diagonal_mm": minimum_diagonal,
        "rotation_blocking_width_margin_mm": minimum_diagonal - largest_slot,
        "minimum_geometric_thread_turns": rail.fasteners.SQUARE_NUT_MIN_HEIGHT
        / rail.fasteners.THREAD_PITCH,
        "rotation_cases": tolerance_rotations,
        "scope": "Size-only tolerance screen for a square nut with unchamfered corners and a straight slot. Actual corners, distortion, thread engagement, torque and PA12 bearing strength require coupon and load testing; no strength qualification.",
        "passed": insertion_clearance >= pocket_tolerance - TOL
        and minimum_diagonal > largest_slot + TOL
        and all(row["passed"] for row in tolerance_rotations),
    }
    tape_rows = []
    for name, shape in tapes:
        bounds = shape.optimalBoundingBox(False, False)
        centre = shape.CenterOfMass
        inner = min(abs(bounds.YMin), abs(bounds.YMax))
        tape_rows.append(
            {
                "tape": name,
                "minimum_z_mm": bounds.ZMin,
                "central_rail_head_clearance_y_mm": inner - rail.HEAD_WIDTH / 2,
                "x_width_mm": bounds.XLength,
                "centre_x_mm": centre.x,
                "rail_intersection_mm3": (
                    intersection_volume(shape, shapes[objects[0].Name])
                    if objects
                    else -1
                ),
                "passed": bounds.ZMin >= -TOL
                and inner >= 6 - TOL
                and bounds.XLength <= rail.PAD_LENGTH + TOL,
            }
        )
    return {
        "rail_count": len(objects),
        "rails": rows,
        "sliding_phase_checks": phase_rows,
        "nominal_nut_rotation_blocking": nut_rotation,
        "square_nut_tolerance_capture": tolerance_capture,
        "tape_over_wing_checks": tape_rows,
        "head_is_uninterrupted": False,
        "one_piece_unbroken_base": True,
        "passed": len(objects) == 1
        and all(r["passed"] for r in rows + tape_rows)
        and len(tape_rows) == 2 * len(rail.PAD_CENTRES)
        and all(r["blocked"] for r in nut_rotation)
        and tolerance_capture["passed"]
        and all(
            r["slide_intersection_mm3"] < TOL
            and r["lift_1mm_blocking_mm3"] > TOL
            and r["lateral_1mm_blocking_mm3"] > TOL
            for r in phase_rows
        ),
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
        if sku.startswith("M2"):
            expected_diameter, expected_pitch = 2.0, 0.4
            thread_description_matches = "M2" in standard
        elif sku.startswith("M1_6"):
            expected_diameter, expected_pitch = 1.6, 0.35
            thread_description_matches = "M1.6" in standard
        elif sku.startswith("GEABP"):
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


def module_removal_plan(modules, exit_directions=None):
    """Remove the outermost module toward each requested rail end first."""
    modules = list(modules)
    directions = {
        module.Name: 1 if module.Placement.Base.x > 1 else -1 for module in modules
    }
    if exit_directions is not None:
        if set(exit_directions) != set(directions) or any(
            value not in (-1, 1) for value in exit_directions.values()
        ):
            raise ValueError("Provide exactly one -1/+1 rail exit for every module")
        directions = dict(exit_directions)
    ordered = sorted(
        modules,
        key=lambda m: (
            directions[m.Name],
            -directions[m.Name] * m.Placement.Base.x,
            m.Name,
        ),
    )
    return [(module, directions[module.Name]) for module in ordered]


def module_service(registry, objects, shapes):
    try:
        bindings = module_control_bindings(registry.Document)
    except (AttributeError, ValueError) as error:
        return {"modules": [], "passed": False, "error": str(error)}
    service_rows, removed_names = [], set()
    sequence = module_removal_plan(module for _, module in bindings)
    for module, direction in sequence:
        members = [o for o in objects if belongs_to_group(o, module)]
        clamps = [o for o in registry.RailLocks if belongs_to_group(o, module)]
        screw = next(o for o in clamps if "Screw" in o.Name)
        nut = next(o for o in clamps if "Nut" in o.Name)
        fixed = [
            (o.Name, shapes[o.Name])
            for o in objects
            if o != screw and o.Name not in removed_names
        ]
        side = 1 if module.Placement.Base.y > 0 else -1
        screw_release = path_checks(
            [(screw.Name, shapes[screw.Name])],
            fixed,
            [(0, side * y, 0) for y in (0, 0.25, 0.5, 1, rail.RELEASE_TRAVEL)],
        )
        nut_obstacles = [
            (o.Name, shapes[o.Name])
            for o in objects
            if o not in (screw, nut) and o.Name not in removed_names
        ]
        nut_load = path_checks(
            [(nut.Name, shapes[nut.Name])],
            nut_obstacles,
            [(side * x, 0, 0) for x in (0, 1, 2, 4, 6, 9, 12, 18, 24)],
        )
        # Tool cylinder deliberately exceeds the circumradius of the 0.9mm A/F
        # hex key. It checks an accessible straight side approach only.
        screw_bounds = shapes[screw.Name].optimalBoundingBox(False, False)
        screw_centre_x = (screw_bounds.XMin + screw_bounds.XMax) / 2
        tool_y = screw_bounds.YMax + 0.1 if side > 0 else screw_bounds.YMin - 0.1
        tool = Part.makeCylinder(
            1.0, 65, V(screw_centre_x, tool_y, rail.CLAMP_Z), V(0, side, 0)
        )
        tool_hits = [
            {
                "part": o.Name,
                "intersection_mm3": intersection_volume(tool, shapes[o.Name]),
            }
            for o in objects
            if o not in (screw, nut)
            and o.Name not in removed_names
            and intersection_volume(tool, shapes[o.Name]) > TOL
        ]
        moving = [
            (
                o.Name,
                translated_shape(
                    shapes[o.Name], y=side * rail.RELEASE_TRAVEL if o == screw else 0
                ),
            )
            for o in members
        ]
        obstacles = [
            (o.Name, shapes[o.Name])
            for o in objects
            if o not in members and o.Name not in removed_names
        ]
        centre_release = path_checks(
            moving, obstacles, [(0, side * y, 0) for y in (0, -0.15, -0.3, -0.45)]
        )
        moving = [
            (name, translated_shape(s, y=-side * rail.CLAMP_SHIFT_Y))
            for name, s in moving
        ]
        target_x = direction * (rail.LENGTH / 2 + rail.SHOE_LENGTH / 2 + 2)
        travel = target_x - module.Placement.Base.x
        distances = sorted(
            set(
                [0.0, abs(travel)]
                + [float(x) for x in range(0, int(abs(travel)) + 1, 6)]
            )
        )
        slide = path_checks(
            moving, obstacles, [(math.copysign(d, travel), 0, 0) for d in distances]
        )
        moved = [(name, translated_shape(s, x=travel)) for name, s in moving]
        printed_names = {obj.Name for obj in registry.PrintedParts}
        exited_shoe = rail_shoe_section(
            [shape for name, shape in moved if name in printed_names]
        )
        exited_bounds = exited_shoe.optimalBoundingBox(False, False)
        rail_bounds = Part.makeCompound(
            [shapes[obj.Name] for obj in registry.RailSegments]
        ).optimalBoundingBox(False, False)
        end_gap = (
            exited_bounds.XMin - rail_bounds.XMax
            if direction > 0
            else rail_bounds.XMin - exited_bounds.XMax
        )
        end_exit = {
            "actual_capture_material_x_bounds_mm": [
                exited_bounds.XMin,
                exited_bounds.XMax,
            ],
            "rail_x_bounds_mm": [rail_bounds.XMin, rail_bounds.XMax],
            "axial_clearance_before_lifting_mm": end_gap,
            "required_clearance_mm": 2.0,
            "passed": exited_shoe.Volume > TOL and end_gap >= 2 - TOL,
        }
        lift = path_checks(
            moved, obstacles, [(0, 0, z) for z in (0, 0.5, 1, 2, 4, 8, 16, 32)]
        )
        # No key or positive axial tooth: an ideal frictionless CAD model must
        # not be misconstrued as demonstrating axial holding force.
        phase_x = module.Placement.Base.x % rail.LAND_PITCH
        land_offset = min(phase_x, rail.LAND_PITCH - phase_x)
        row = {
            "module": module.Name,
            "removed_before_this_step": sorted(removed_names),
            "clamp_screw": screw.Name,
            "clamp_nut": nut.Name,
            "approach_side_y": side,
            "screw_release_three_turns": screw_release,
            "nut_insertion_before_screw": nut_load,
            "straight_hex_key_approach_collisions": tool_hits,
            "recentering_after_loosening": centre_release,
            "end_slide": slide,
            "lift_after_end_exit": lift,
            "recommended_exit_direction_x": direction,
            "module_centre_at_exit_x_mm": target_x,
            "shoe_fully_past_rail_end": end_exit,
            "clamp_land_centre_offset_mm": land_offset,
            "axial_lock_type": "Friction clamp only; no numerical holding-force proof",
            "passed": screw_release["passed"]
            and nut_load["passed"]
            and not tool_hits
            and centre_release["passed"]
            and slide["passed"]
            and end_exit["passed"]
            and lift["passed"]
            and land_offset <= rail.CLAMP_LAND_OFFSET + TOL,
        }
        service_rows.append(row)
        print(
            json.dumps(
                {
                    "module_service_complete": module.Name,
                    "passed": row["passed"],
                    "exit_direction_x": direction,
                }
            ),
            flush=True,
        )
        removed_names.update(o.Name for o in members)
    return {
        "removal_order": [m.Name for m, _ in sequence],
        "modules": service_rows,
        "scope": "Disconnect external leads first. Sampled bare-module positions along straight saved-rail removal paths, not a connected-harness or continuous-motion proof. Curved-rail sliding, real screwdriver access, clamp force and tape adhesion require a physical trial.",
        "passed": len(service_rows) == len(MODULE_STATIONS)
        and all(r["passed"] for r in service_rows),
    }


def bidirectional_service(doc, registry, objects):
    try:
        bindings = module_control_bindings(doc)
    except (AttributeError, ValueError) as error:
        return {"passed": False, "error": str(error)}
    controls = [station.clamp_control for station, _ in bindings]
    modules = [module for _, module in bindings]
    original = {name: str(getattr(doc.AssemblySettings, name)) for name in controls}
    combinations, services = [], []
    try:
        for choices in itertools.product(
            ("PositiveY", "NegativeY"), repeat=len(bindings)
        ):
            for name, choice in zip(controls, choices):
                setattr(doc.AssemblySettings, name, choice)
            doc.recompute()
            shapes = {o.Name: world_shape(o) for o in objects}
            neutral = neutral_check(objects, shapes)
            poses = []
            for module, choice in zip(modules, choices):
                side = 1 if choice == "PositiveY" else -1
                clamps = [o for o in registry.RailLocks if belongs_to_group(o, module)]
                expected_rot = App.Rotation(V(0, 0, 1), 0 if side > 0 else 180)
                poses.append(
                    {
                        "module": module.Name,
                        "control": choice,
                        "seated_y_mm": module.Placement.Base.y,
                        "hardware_rotation_matches": all(
                            o.Placement.Rotation.isSame(expected_rot, 1e-7)
                            for o in clamps
                        ),
                        "passed": abs(
                            module.Placement.Base.y - side * rail.CLAMP_SHIFT_Y
                        )
                        < TOL
                        and len(clamps) == 2
                        and all(
                            o.Placement.Rotation.isSame(expected_rot, 1e-7)
                            for o in clamps
                        ),
                    }
                )
            combinations.append(
                {
                    "choices": dict(zip(controls, choices)),
                    "native_poses": poses,
                    "neutral_assembly": neutral,
                    "passed": neutral["passed"] and all(p["passed"] for p in poses),
                }
            )
            if len(set(choices)) == 1:
                services.append(
                    {
                        "approach": choices[0],
                        **module_service(registry, objects, shapes),
                    }
                )
        # Dedicated equipment supports may be asymmetric. Their actual shared
        # capture/nut geometry must still be exact, not just non-interfering.
        shoe = rail.shoe_shape()
        shoe_box = Part.makeBox(
            rail.SHOE_LENGTH,
            rail.SHOE_WIDTH,
            rail.TOP_Z - rail.SHOE_BOTTOM,
            V(-rail.SHOE_LENGTH / 2, -rail.SHOE_WIDTH / 2, rail.SHOE_BOTTOM),
        )
        captures = []
        for obj in list(registry.EquipmentMounts) + [doc.PropulsionFixedFrame]:
            actual = local_shape(obj).common(shoe_box)
            comparison = geometry_comparison(actual, shoe)
            captures.append({"part": obj.Name, **comparison})
        symmetry = []
        rotated = shoe.copy()
        rotated.rotate(V(), V(0, 0, 1), 180)
        symmetry.append(
            {"part": "common_shoe_source", **geometry_comparison(shoe, rotated)}
        )
        return {
            "native_approach_combinations": combinations,
            "full_service_sequences": services,
            "common_shoe_half_turn_symmetry": symmetry,
            "saved_integral_shoes_match_source": captures,
            "unused_port_has_no_extra_hardware": len(registry.RailLocks)
            == 2 * len(bindings),
            "scope": "Choice is made before clamp assembly. Changing the enum is not a physical screw-transfer path. Each port separately has a nut loading, tool approach, loosening and end-removal route.",
            "passed": len(combinations) == 2 ** len(bindings)
            and len(services) == 2
            and all(row["passed"] for row in combinations + services)
            and len(captures) == len(bindings)
            and all(
                row["difference_mm3"] < TOL
                and row["bounds_difference_mm"] < TOL
                and row["volume_difference_mm3"] < TOL
                for row in symmetry + captures
            )
            and len(registry.RailLocks) == 2 * len(bindings),
        }
    finally:
        for name, choice in original.items():
            setattr(doc.AssemblySettings, name, choice)
        doc.recompute()


def planar_wall_regions(shape, maximum=1.51001):
    """Opposed parallel planar faces plus interior samples, not a medial-axis proof."""
    planes = [
        (i, f, f.normalAt(0, 0), f.CenterOfMass)
        for i, f in enumerate(shape.Faces)
        if type(f.Surface).__name__ == "Plane"
    ]
    found = []
    for index, (i, first, normal, point) in enumerate(planes):
        for k, second, other_normal, other_point in planes[index + 1 :]:
            if normal.dot(other_normal) > -0.999999:
                continue
            thickness = -(other_point - point).dot(normal)
            if not 1e-4 < thickness < maximum:
                continue
            projected = first.copy()
            projected.translate(-normal * thickness)
            common = projected.common(second)
            if common.Area < 1e-5:
                continue
            interiors = []
            for face in common.Faces:
                points, triangles = face.tessellate(0.5)
                for triangle in triangles[:10]:
                    sample = (
                        sum((points[t] for t in triangle), V()) / 3
                        + normal * thickness / 2
                    )
                    if shape.isInside(sample, 1e-6, False):
                        interiors.append([sample.x, sample.y, sample.z])
            if interiors:
                found.append(
                    {
                        "faces": [i, k],
                        "material_thickness_mm": thickness,
                        "projected_overlap_area_mm2": common.Area,
                        "interior_samples_mm": interiors[:2],
                    }
                )
    return found


def line_wall(shape, a, b):
    result = shape.common(Part.makeLine(V(*a), V(*b)))
    return sum(edge.Length for edge in result.Edges)


def manufacturing_review(doc, registry):
    from gondola.parts import optical_mount

    probes = []
    seen_skus = set()
    for obj in registry.PrintedParts:
        if obj in registry.RailSegments or obj.PrintSKU in seen_skus:
            continue
        seen_skus.add(obj.PrintSKU)
        shape = local_shape(obj)
        regions = planar_wall_regions(shape)
        probes.append(
            {
                "part": obj.Name,
                "planar_material_regions_up_to_1p51mm": regions,
                "no_detected_planar_wall_under_1p5mm": all(
                    row["material_thickness_mm"] >= 1.5 - TOL for row in regions
                ),
            }
        )
    analytic = [
        (
            "rail_functional_flexure_thickness",
            "ContinuousRail",
            (9, 0, -0.01),
            (9, 0, 1.3),
            1.2,
        ),
        (
            "tape_wing_thickness",
            "ContinuousRail",
            (0, 12, -0.01),
            (0, 12, 1.3),
            1.2,
        ),
        ("guard_radial_wall", "PortMotorCarrier", (12, 0, 22.79), (12, 0, 24.31), 1.5),
        (
            "battery_mount_deck_thickness",
            "BatteryMount",
            (0, 20, mounts.DECK_BOTTOM_Z - 0.01),
            (0, 20, mounts.SUPPORT_FACE_Z + 0.01),
            mounts.DECK_THICKNESS,
        ),
        (
            "bare_shoe_nut_pocket_roof",
            "PropulsionFixedFrame",
            (4, 8.0, 8.49),
            (4, 8.0, 10.21),
            1.7,
        ),
        (
            "frame_foot_thickness",
            "PropulsionFixedFrame",
            (8.0, 80, propulsion.BASE_Z - 0.01),
            (8.0, 80, propulsion.BASE_Z + propulsion.FOOT_THICKNESS + 0.01),
            propulsion.FOOT_THICKNESS,
        ),
        (
            "optical_base_pivot_wall",
            "OpticalMountBase",
            (-1.51, 0, 4),
            (0.01, 0, 4),
            1.5,
        ),
        (
            "optical_roll_bracket_wall",
            "OpticalRollBracket",
            (-0.01, -1, 5),
            (1.51, -1, 5),
            1.5,
        ),
        (
            "optical_tray_neck_wall",
            "OpticalSensorTray",
            (0, -0.01, 3.8),
            (0, 1.51, 3.8),
            1.5,
        ),
        (
            "optical_tray_deck_thickness",
            "OpticalSensorTray",
            (0, 4, optical_mount.TRAY_BOTTOM_Z - 0.01),
            (0, 4, optical_mount.TRAY_TOP_Z + 0.01),
            optical_mount.TRAY_TOP_Z - optical_mount.TRAY_BOTTOM_Z,
        ),
    ]
    measurements = []
    probes_with_frames = [(probe, False) for probe in analytic] + [
        (probe, True) for probe in propulsion.manufacturing_wall_probes()
    ]
    for (feature, name, start, end, expected), module_coordinates in probes_with_frames:
        obj = doc.getObject(name)
        shape = local_shape(obj)
        if module_coordinates:
            shape = world_shape(obj)
            shape.Placement = (
                doc.MainPropulsionModule.getGlobalPlacement()
                .inverse()
                .multiply(shape.Placement)
            )
        actual = line_wall(shape, start, end)
        measurements.append(
            {
                "feature": feature,
                "part": name,
                "sample_line_mm": [start, end],
                "coordinate_frame": "propulsion module"
                if module_coordinates
                else "part local",
                "measured_material_length_mm": actual,
                "nominal_expected_mm": expected,
                "passed": abs(actual - expected) < TOL,
            }
        )
    exception = str(getattr(registry.RailSegments[0], "ManufacturingException", ""))
    return {
        "source": CREALLO_GUIDE_URL,
        "published_sls_mjf_pa12_thin_broad_guidance_mm": [
            [50, 1.0],
            [100, 1.5],
            [150, 2.0],
            ["200+", 3.0],
        ],
        "wall_guidance_source": MANUFACTURING_DECISION["sources"]["wall_thickness"],
        "guide_scope": f"Thin and broad plate-like parts in SLS/MJF. This is not a blanket 3 mm wall requirement for every small feature, nor permission to claim the {rail.LENGTH:g} mm flexure automatically compliant.",
        "generic_nylon_minimum_mm": 0.8,
        "general_functional_wall_target_mm": 1.5,
        "rail_flexure_target_mm": rail.PAD_THICKNESS,
        "short_50mm_guidance_mm": 1.0,
        "equipment_mount_assessment": {
            "deck_mm": mounts.DECK_THICKNESS,
            "load_path_arm_width_mm": mounts.ARM_WIDTH,
            "hole_pad_diameter_mm": mounts.MOUNT_PAD_DIAMETER,
            "contracts": [
                mounts.mount_contract(kind) for kind in ("battery", "electronics")
            ],
            "independent_optical_mount_contract": optical_mount.mount_contract(),
        },
        "rail_functional_flexure_exception": exception,
        "supplier_acceptance_status": "Not yet confirmed: 1.2 mm narrow flexure, tape wings and one-piece manufacture require quote review.",
        "opposed_planar_face_screen": probes,
        "actual_feature_measurements": measurements,
        "wall_screen_limits": "Sampled opposed planar faces and explicit line probes only. Fillet/taper/cylindrical transitions are not exhaustively certified as a global minimum-wall field. No strength or fatigue qualification.",
        "powder_removal": "Open rail channel, through nut entries, open support arms and through journals; depowder before installing hardware. No sealed hollow print is claimed.",
        "tolerance": {
            "dimensional_percent": 0.3,
            "minimum_absolute_mm": 0.3,
            "rail_nominal_total_gap_mm": 0.9,
            "size_only_worst_case_total_gap_mm": 0.3,
            "not_a_GDT_position_or_actual_fit_guarantee": True,
        },
        "blanket_guide_compliance_claimed": False,
        "passed": bool(exception)
        and "1.2mm" in exception
        and all(row["no_detected_planar_wall_under_1p5mm"] for row in probes)
        and all(row["passed"] for row in measurements),
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
        "LR900NegativeXConnectorReserve",
        "LR900PositiveXConnectorReserve",
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
        "expected_source": NOTION_URL,
        "expected_source_last_edited": NOTION_LAST_EDITED,
        "user_scope_exclusions": EXCLUDED_EQUIPMENT,
        "source": str(registry.NotionSource),
        "source_last_edited": str(registry.NotionLastEdited),
        "scoped_listed_equipment_mass_g": float(
            registry.ScopedListedEquipmentMassGrams
        ),
        "not_all_up_mass": True,
        "excluded_device_references_found": forbidden,
        "new_electrical_space_reservations": reserves,
        "cable_and_OEM_limitations": "Reserve shapes are not measured components, flexible cable routing or proof of cable slack at bounded ±180 degrees. OEM motor retention and measured X06 horn connection remain unresolved.",
        "passed": not forbidden
        and str(registry.NotionSource) == NOTION_URL
        and str(registry.NotionLastEdited) == NOTION_LAST_EDITED
        and abs(
            float(registry.ScopedListedEquipmentMassGrams)
            - SCOPED_LISTED_EQUIPMENT_MASS_G
        )
        < TOL
        and all(row["passed"] for row in reserves),
    }


def tilt_check(doc, registry, objects, shapes):
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
                        if expected_pair(obj, other):
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
    column_names = {
        f"OpticalStackSpacer{index}"
        for index in range(len(stack_interface.HOLE_CENTRES))
    }
    column_gaps = [
        {"object": name, "minimum_gap_mm": swept.distToShape(shape)[0]}
        for name, shape in obstacles
        if name in column_names
    ]
    continuous = {
        "method": "Exact maximum-pack translation envelope over the entire declared XY rectangle",
        "local_size_mm": [width + 2 * x_limit, length + 2 * y_limit, height],
        "collisions": swept_hits,
        "stack_column_gaps": column_gaps,
        "required_stack_column_gap_mm": contract["minimum_stack_column_gap_mm"],
        "passed": not swept_hits
        and {row["object"] for row in column_gaps} == column_names
        and all(
            row["minimum_gap_mm"] >= contract["minimum_stack_column_gap_mm"] - TOL
            for row in column_gaps
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
    }
    identity["passed"] = (
        identity["schema_version"] == ARTIFACT_SCHEMA_VERSION
        and identity["manifest_source_fingerprint"] == fingerprint
        and identity["native_source_fingerprint"] == fingerprint
        and identity["mesh_parameters"] == MESH_PARAMETERS
        and identity["release_status_matches_contract"]
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
        master = print_shape(instances[0])
        equivalence = []
        for obj in instances[1:]:
            comparison = geometry_comparison(master, print_shape(obj))
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
        step_comparison = geometry_comparison(master, step)
        step_matches = (
            step.isValid()
            and len(step.Solids) == 1
            and all(
                step_comparison[key] < TOL
                for key in (
                    "difference_mm3",
                    "volume_difference_mm3",
                    "bounds_difference_mm",
                )
            )
        )
        bb = mesh.BoundBox
        sizes = [bb.XLength, bb.YLength, bb.ZLength]
        published_size_checks = {
            process: all(d <= limit + TOL for d, limit in zip(sizes, limits))
            for process, limits in PUBLISHED_PROCESS_SIZE_MM.items()
        }
        good = (
            master.isValid()
            and len(master.Solids) == 1
            and mesh.isSolid()
            and mesh.countComponents() == 1
            and hashes_match
            and mesh_matches
            and step_matches
            and all(published_size_checks.values())
            and entry["quantity"] == len(instances)
            and native_inventory["passed"]
            and all(r["difference_mm3"] < TOL for r in equivalence)
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
                "quantity": entry["quantity"],
                "native_inventory": native_inventory,
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
        reference = propulsion.build_propulsion_module(reference_doc)
        reference_doc.recompute()
        expected_print_count = len(reference["printed"])
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
    meshes = evidence.get("geometry", [])
    required_cases = {
        "drive_motion": 2,
        "mesh_adjustment": 2,
        "gear_mesh_alignment": 2,
        "gear_rotation": 2,
        "bearing_stacks": 8,
        "output_stub_clearance": 4,
        "shaft_service": 6,
        "bearing_service": 8,
        "gear_service": 4,
        "input_cartridge_removal": 2,
        "horn_clamp_service": 4,
        "rail_key_access": 4,
        "fastener_stacks": PURCHASED_HARDWARE_QUANTITIES["M2X8_SOCKET_CAP"]
        + PURCHASED_HARDWARE_QUANTITIES["M1_6X8_CHEESE_HEAD"],
        "fastener_service": PURCHASED_HARDWARE_QUANTITIES["M2X8_SOCKET_CAP"]
        + PURCHASED_HARDWARE_QUANTITIES["M1_6X8_CHEESE_HEAD"],
        "motor_and_prop_insertion": 4,
        "continuous_nut_loading": 2,
        "tilt_clearance": 2,
    }
    evidence_inventory = {
        key: {"expected": count, "actual": len(evidence.get(key, []))}
        for key, count in required_cases.items()
    }
    evidence_ok = (
        evidence.get("passed", False)
        and all(row["expected"] == row["actual"] for row in evidence_inventory.values())
        and len(meshes) == expected_print_count
        and all(
            row["valid_brep"]
            and row["solid_count"] == 1
            and row["watertight_mesh"]
            and row["mesh_components"] == 1
            for row in meshes
        )
        and evidence.get("all_bought_parts_excluded_from_prints", False)
    )
    return {
        "source_file": os.path.relpath(path, REPO_ROOT),
        "source_sha256": file_sha256(path),
        "saved_shape_source_comparisons": comparisons,
        "local_overlap_failures": volume_failures,
        "local_checks": evidence,
        "required_evidence_inventory": evidence_inventory,
        "scope": "Recomputed geared-drive mesh, bearings, split output shafts, bounded motion and ordered service paths. Sample fits, loaded retention, cable travel and OEM fastening remain physical qualification requirements.",
        "passed": evidence_ok
        and not volume_failures
        and all(row["passed"] for row in comparisons),
    }


def validate(source=None):
    source = (
        Path(source).resolve() if source else OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")
    )
    from .propulsion import validate as validate_propulsion

    validate_propulsion(source)
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
            "Checking complete end-removal sequence and clamp/nut/tool access",
            flush=True,
        )
        report["module_service"] = bidirectional_service(doc, r, objects)
        print("Checking independent tilt and equipment service clearances", flush=True)
        report["independent_tilt"] = tilt_check(doc, r, objects, shapes)
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
        report["pa12_manufacturing_review"] = manufacturing_review(doc, r)
        report["notion_scope_and_reserves"] = equipment_scope_check(
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
            "purchased_hardware",
            "assembly_inventory",
            "module_service",
            "independent_tilt",
            "continuous_external_rotor_sweeps",
            "battery_reference_fit",
            "print_export",
            "local_propulsion_evidence",
            "pa12_manufacturing_review",
            "notion_scope_and_reserves",
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
