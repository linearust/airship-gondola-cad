"""Independent read-only saved-assembly audit of the Rev I gondola.

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
from gondola.config import ARTIFACT_SCHEMA_VERSION, OUTPUT_DIR, ROOT, STEM
from gondola.design_contract import (
    CREALLO_GUIDE_URL,
    EXCLUDED_EQUIPMENT,
    EXPECTED_INVENTORY,
    NOTION_LAST_EDITED,
    NOTION_URL,
    SCOPED_LISTED_EQUIPMENT_MASS_G,
)
from gondola.manufacturing import (
    MESH_PARAMETERS,
    geometry_comparison,
    mesh_from_shape,
    print_shape,
)
from gondola.parts import metric_hardware as hardware
from gondola.parts import rail
from gondola.parts import universal_board as platform
from gondola.provenance import file_sha256, source_fingerprint

from .geometry import (
    belongs_to_group,
    compare_identical_boards,
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
            s = translated_shape(shape, *vector)
            for other_name, other in fixed:
                vol = intersection_volume(s, other)
                if vol > TOL:
                    hits.append(
                        {"moving": name, "fixed": other_name, "intersection_mm3": vol}
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


def rail_check(registry, shapes):
    objects = list(registry.RailSegments)
    rows = []
    for obj in objects:
        s = local_shape(obj)
        comparison = geometry_comparison(s, rail.rail_shape())
        base_samples = []
        for x in range(-186, 187, 3):
            base_samples.append(
                {"x_mm": x, "in_unbroken_base": s.isInside(V(x, 0, 0.5), TOL, True)}
            )
        relief_samples = []
        for i in range(-10, 10):
            x = (i + 0.5) * rail.LAND_PITCH
            relief_samples.append(
                {
                    "x_mm": x,
                    "base_present": s.isInside(V(x, 0, 0.5), TOL, True),
                    "head_absent": not s.isInside(V(x, 0, 6.2), TOL, True),
                }
            )
        bb = s.optimalBoundingBox(False, False)
        rows.append(
            {
                "object": obj.Name,
                "source_comparison": comparison,
                "size_mm": [bb.XLength, bb.YLength, bb.ZLength],
                "unbroken_base_samples": base_samples,
                "relief_samples": relief_samples,
                "single_valid_solid": s.isValid() and len(s.Solids) == 1,
                "passed": s.isValid()
                and len(s.Solids) == 1
                and comparison["difference_mm3"] < TOL
                and abs(bb.XLength - rail.LENGTH) < TOL
                and all(r["in_unbroken_base"] for r in base_samples)
                and all(r["base_present"] and r["head_absent"] for r in relief_samples),
            }
        )
    nominal = rail.shoe_shape()
    section = rail.rail_shape(72, (-27, 27))
    tapes = [(o.Name, shapes[o.Name]) for o in registry.TapeReferences]
    phase_rows = []
    # An entire relief pitch, including half-millimetre offsets, checks that
    # the rigid short shoe bridges each gap throughout the sliding phase.
    for j in range(37):
        x = j * 0.5
        shoe = translated_shape(nominal, x=x)
        phase_rows.append(
            {
                "phase_x_mm": x,
                "slide_intersection_mm3": intersection_volume(shoe, section),
                "lift_1mm_blocking_mm3": intersection_volume(
                    translated_shape(shoe, z=1), section
                ),
                "lateral_1mm_blocking_mm3": intersection_volume(
                    translated_shape(shoe, y=1), section
                ),
            }
        )
    nut_rotation = []
    for angle in (-30, 30):
        nut = rail.nut_shape().copy()
        nut.rotate(V(0, 0, rail.CLAMP_Z), V(0, 1, 0), angle)
        vol = intersection_volume(nut, nominal)
        nut_rotation.append(
            {
                "rotation_about_constrained_screw_axis_deg": angle,
                "blocking_intersection_mm3": vol,
                "blocked": vol > TOL,
            }
        )
    tape_rows = []
    for name, shape in tapes:
        bb = shape.optimalBoundingBox(False, False)
        centre = shape.CenterOfMass
        inner = min(abs(bb.YMin), abs(bb.YMax))
        tape_rows.append(
            {
                "tape": name,
                "minimum_z_mm": bb.ZMin,
                "central_rail_head_clearance_y_mm": inner - rail.HEAD_WIDTH / 2,
                "x_width_mm": bb.XLength,
                "centre_x_mm": centre.x,
                "rail_intersection_mm3": (
                    intersection_volume(shape, shapes[objects[0].Name])
                    if objects
                    else -1
                ),
                "passed": bb.ZMin >= -TOL
                and inner >= 6 - TOL
                and bb.XLength <= rail.PAD_LENGTH + TOL,
            }
        )
    return {
        "rail_count": len(objects),
        "rails": rows,
        "sliding_phase_checks": phase_rows,
        "nominal_nut_rotation_blocking": nut_rotation,
        "tape_over_wing_checks": tape_rows,
        "head_is_uninterrupted": False,
        "one_piece_unbroken_base": True,
        "passed": len(objects) == 1
        and all(r["passed"] for r in rows + tape_rows)
        and len(tape_rows) == 2 * len(rail.PAD_CENTRES)
        and all(r["blocked"] for r in nut_rotation)
        and all(
            r["slide_intersection_mm3"] < TOL
            and r["lift_1mm_blocking_mm3"] > TOL
            and r["lateral_1mm_blocking_mm3"] > TOL
            for r in phase_rows
        ),
    }


def hardware_check(registry):
    bought = list(registry.HardwareParts)
    printed = list(registry.PrintedParts) + list(registry.FitCoupons)
    bad, rows = [], []
    printed_names = {o.Name for o in printed}
    for obj in bought:
        standard = str(getattr(obj, "ThreadStandard", ""))
        sku = str(getattr(obj, "HardwareSKU", ""))
        is_metric = "M3" in standard or "M3" in sku
        excluded = obj.Name not in printed_names and not bool(
            getattr(obj, "PrintPart", False)
        )
        row = {
            "part": obj.Name,
            "sku": sku,
            "thread_standard": standard,
            "metric_specification_present": is_metric,
            "excluded_from_print_registry": excluded,
            "passed": is_metric and excluded and bool(sku),
        }
        rows.append(row)
    for obj in printed:
        if any(
            term in obj.Name
            for term in (
                "PrintedJournalPin",
                "PrintedRetainingClip",
                "RailKey",
                "StackBaseBolt",
                "StackTopNut",
            )
        ):
            bad.append(obj.Name)
    clamp_names = {o.Name for o in registry.RailLocks}
    source = Path(registry.Document.FileName)
    bom = json.loads((source.parent / (source.stem + "_hardware_bom.json")).read_text())
    bom_names = [name for row in bom["items"] for name in row["instances"]]
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
    bom_ok = (
        len(bom_names) == len(bought)
        and len(set(bom_names)) == len(bought)
        and set(bom_names) == {o.Name for o in bought}
        and all(row["passed"] for row in material_rows)
    )
    expected_purchases = {
        "M3_MF_30_PLUS_6_PA66": 4,
        "M3X6_SOCKET_CAP_A2": 4,
        "M3_HEX_NUT_A2": 11,
        "M3_WASHER_3.2_7_0.5_A2": 16,
        "M3x8_ISO4026_DIN913_A2": 3,
        "M3X16_SOCKET_CAP_A2": 4,
    }
    purchase_counts = {row["purchase_code"]: row["quantity"] for row in bom["items"]}
    return {
        "purchased_item_count": len(bought),
        "parts": rows,
        "bill_of_materials": {
            "material_specific_purchases": material_rows,
            "every_hardware_object_included_once": bom_ok,
            "six_standard_purchase_specifications": purchase_counts
            == expected_purchases,
        },
        "obsolete_printed_fasteners": bad,
        "all_rail_clamps_are_purchased": clamp_names <= {o.Name for o in bought},
        "thread_retention_simulated": False,
        "passed": bool(rows)
        and all(r["passed"] for r in rows)
        and not bad
        and bom_ok
        and purchase_counts == expected_purchases
        and clamp_names <= {o.Name for o in bought},
    }


def module_service(registry, objects, shapes):
    modules = list(registry.Modules)
    result, removed = [], set()
    # Outside equipment first; the propulsion module can then reach an end.
    sequence = sorted(
        modules,
        key=lambda m: (
            0 if m.Placement.Base.x < -1 else 1 if m.Placement.Base.x > 1 else 2
        ),
    )
    for module in sequence:
        members = [o for o in objects if belongs_to_group(o, module)]
        clamps = [o for o in registry.RailLocks if belongs_to_group(o, module)]
        screw = next(o for o in clamps if "Screw" in o.Name)
        nut = next(o for o in clamps if "Nut" in o.Name)
        fixed = [
            (o.Name, shapes[o.Name])
            for o in objects
            if o != screw and o.Name not in removed
        ]
        side = 1 if module.Placement.Base.y > 0 else -1
        screw_release = path_checks(
            [(screw.Name, shapes[screw.Name])],
            fixed,
            [(0, side * y, 0) for y in (0, 0.25, 0.5, 1, 1.5)],
        )
        nut_obstacles = [
            (o.Name, shapes[o.Name])
            for o in objects
            if o not in (screw, nut) and o.Name not in removed
        ]
        nut_load = path_checks(
            [(nut.Name, shapes[nut.Name])],
            nut_obstacles,
            [(side * x, 0, 0) for x in (0, 1, 2, 4, 6, 9, 12, 18, 24)],
        )
        # Tool cylinder deliberately exceeds the circumradius of a1.5mm A/F
        # hex key. It checks an accessible straight side approach only.
        screw_bb = shapes[screw.Name].optimalBoundingBox(False, False)
        screw_centre_x = (screw_bb.XMin + screw_bb.XMax) / 2
        tool_y = screw_bb.YMax + 0.1 if side > 0 else screw_bb.YMin - 0.1
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
            and o.Name not in removed
            and intersection_volume(tool, shapes[o.Name]) > TOL
        ]
        moving = [
            (
                o.Name,
                translated_shape(shapes[o.Name], y=side * 1.5 if o == screw else 0),
            )
            for o in members
        ]
        obstacles = [
            (o.Name, shapes[o.Name])
            for o in objects
            if o not in members and o.Name not in removed
        ]
        centre_release = path_checks(
            moving, obstacles, [(0, side * y, 0) for y in (0, -0.15, -0.3, -0.45)]
        )
        moving = [
            (name, translated_shape(s, y=-side * rail.CLAMP_SHIFT_Y))
            for name, s in moving
        ]
        direction = 1 if module.Placement.Base.x > 1 else -1
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
        lift = path_checks(
            moved, obstacles, [(0, 0, z) for z in (0, 0.5, 1, 2, 4, 8, 16, 32)]
        )
        # No key or positive axial tooth: an ideal frictionless CAD model must
        # not be misconstrued as demonstrating axial holding force.
        phase_x = module.Placement.Base.x % rail.LAND_PITCH
        land_offset = min(phase_x, rail.LAND_PITCH - phase_x)
        row = {
            "module": module.Name,
            "removed_before_this_step": sorted(removed),
            "clamp_screw": screw.Name,
            "clamp_nut": nut.Name,
            "approach_side_y": side,
            "screw_release_1p5mm_three_turns": screw_release,
            "nut_insertion_before_screw": nut_load,
            "straight_hex_key_approach_collisions": tool_hits,
            "recentering_after_loosening": centre_release,
            "end_slide": slide,
            "lift_after_end_exit": lift,
            "recommended_exit_direction_x": direction,
            "module_centre_at_exit_x_mm": target_x,
            "clamp_land_centre_offset_mm": land_offset,
            "axial_lock_type": "Friction clamp only; no numerical holding-force proof",
            "passed": screw_release["passed"]
            and nut_load["passed"]
            and not tool_hits
            and centre_release["passed"]
            and slide["passed"]
            and lift["passed"]
            and land_offset <= 5 + TOL,
        }
        result.append(row)
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
        removed.update(o.Name for o in members)
    return {
        "removal_order": [m.Name for m in sequence],
        "modules": result,
        "scope": "Straight saved-rail envelopes. Curved-rail sliding, real screwdriver access, clamp force and tape adhesion require a physical trial.",
        "passed": len(result) == 3 and all(r["passed"] for r in result),
    }


def bidirectional_service(doc, registry, objects):
    controls = (
        "BatteryClampApproach",
        "PropulsionClampApproach",
        "ElectronicsClampApproach",
    )
    modules = list(registry.Modules)
    original = {name: str(getattr(doc.AssemblySettings, name)) for name in controls}
    combinations, services = [], []
    try:
        for choices in itertools.product(("PositiveY", "NegativeY"), repeat=3):
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
        symmetry = []
        for obj in registry.StandardBoards:
            shape = local_shape(obj)
            rotated = shape.copy()
            rotated.rotate(V(), V(0, 0, 1), 180)
            comparison = geometry_comparison(shape, rotated)
            symmetry.append({"part": obj.Name, **comparison})
        shoe = rail.shoe_shape()
        rotated = shoe.copy()
        rotated.rotate(V(), V(0, 0, 1), 180)
        symmetry.append(
            {"part": "common_shoe_source", **geometry_comparison(shoe, rotated)}
        )
        return {
            "native_approach_combinations": combinations,
            "full_service_sequences": services,
            "face_up_half_turn_symmetry": symmetry,
            "unused_port_has_no_extra_hardware": len(registry.RailLocks) == 6,
            "scope": "Choice is made before clamp assembly. Changing the enum is not a physical screw-transfer path. Each port separately has a nut loading, tool approach, loosening and end-removal route.",
            "passed": len(combinations) == 8
            and len(services) == 2
            and all(row["passed"] for row in combinations + services)
            and all(row["difference_mm3"] < TOL for row in symmetry)
            and len(registry.RailLocks) == 6,
        }
    finally:
        for name, choice in original.items():
            setattr(doc.AssemblySettings, name, choice)
        doc.recompute()


def planar_wall_regions(shape, maximum=1.01001):
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
    probes = []
    for name in (
        "BatteryUniversalBoard",
        "PropulsionFixedFrame",
        "PortMotorCarrier",
        "PortJournalSleevePositive",
    ):
        shape = local_shape(doc.getObject(name))
        regions = planar_wall_regions(shape)
        probes.append(
            {
                "part": name,
                "planar_material_regions_up_to_1p01mm": regions,
                "no_detected_planar_wall_under_1mm": all(
                    row["material_thickness_mm"] >= 1 - TOL for row in regions
                ),
            }
        )
    analytic = [
        (
            "journal_D_flat_wall",
            "PortJournalSleevePositive",
            (0, 24, 1.99),
            (0, 24, 3.01),
            1.0,
        ),
        ("guard_radial_wall", "PortMotorCarrier", (12, 0, 22.79), (12, 0, 24.01), 1.2),
        (
            "board_deck_thickness",
            "BatteryUniversalBoard",
            (31.5, 0, 10.19),
            (31.5, 0, 12.21),
            2.0,
        ),
        (
            "bare_shoe_nut_pocket_roof",
            "PropulsionFixedFrame",
            (4, 8.5, 9.19),
            (4, 8.5, 10.21),
            1.0,
        ),
        (
            "frame_foot_thickness",
            "PropulsionFixedFrame",
            (5, 80, 1.99),
            (5, 80, 5.01),
            3.0,
        ),
    ]
    measurements = []
    for feature, name, start, end, expected in analytic:
        actual = line_wall(local_shape(doc.getObject(name)), start, end)
        measurements.append(
            {
                "feature": feature,
                "part": name,
                "sample_line_mm": [start, end],
                "measured_material_length_mm": actual,
                "nominal_expected_mm": expected,
                "passed": abs(actual - expected) < TOL,
            }
        )
    exception = str(getattr(registry.RailSegments[0], "ManufacturingException", ""))
    return {
        "source": CREALLO_GUIDE_URL,
        "published_sls_pa12_thin_broad_guidance_mm": [
            [50, 1.0],
            [100, 1.5],
            [150, 2.0],
            ["200+", 3.0],
        ],
        "guide_scope": "Thin and broad plate-like parts. This is not a blanket 3 mm wall requirement for every small feature, nor permission to claim the 378 mm flexure automatically compliant.",
        "generic_nylon_minimum_mm": 0.8,
        "short_50mm_guidance_mm": 1.0,
        "board_assessment": {
            "maximum_length_mm": 76,
            "deck_mm": 2,
            "grid_rib_width_mm": 1.6,
            "reference_100mm_guidance_mm": 1.5,
        },
        "rail_functional_flexure_exception": exception,
        "supplier_acceptance_status": "Not yet confirmed: 1 mm narrow flexure, tape wings and one-piece manufacture require quote review.",
        "opposed_planar_face_screen": probes,
        "actual_feature_measurements": measurements,
        "wall_screen_limits": "Sampled opposed planar faces and explicit line probes only. Fillet/taper/cylindrical transitions are not exhaustively certified as a global minimum-wall field. No strength or fatigue qualification.",
        "powder_removal": "Open rail channel, through nut entries, open grid and through journals; depowder before installing hardware. No sealed hollow print is claimed.",
        "tolerance": {
            "dimensional_percent": 0.3,
            "minimum_absolute_mm": 0.3,
            "rail_nominal_total_gap_mm": 0.9,
            "size_only_worst_case_total_gap_mm": 0.3,
            "not_a_GDT_position_or_actual_fit_guarantee": True,
        },
        "blanket_guide_compliance_claimed": False,
        "passed": bool(exception)
        and "1mm" in exception
        and all(row["no_detected_planar_wall_under_1mm"] for row in probes)
        and all(row["passed"] for row in measurements),
    }


def equipment_scope_check(doc, registry, objects, shapes):
    forbidden = [
        o.Name
        for o in registry.ReferenceParts
        if any(
            token in o.Name.lower() for token in ("mtf", "yaw", "finservo", "hl3604")
        )
    ]
    reserves = []
    expected = (
        "XT30ServiceReserve",
        "CapacitorServiceReserve",
        "PortPhaseLeadLoopReserve",
        "StarboardPhaseLeadLoopReserve",
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
        "cable_and_OEM_limitations": "Reserve shapes are not measured components, flexible cable routing or proof of cable slack at ±150 degrees. OEM motor retention, servo ears and horn-to-sleeve drive remain unresolved.",
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
        hits, independent, zmin = [], True, float("inf")
        original = float(pod.Tilt)
        try:
            for angle in range(-150, 151, 15):
                pod.Tilt = angle
                doc.recompute()
                independent &= all(
                    o.Placement.isSame(other_placements[o.Name], 1e-7)
                    for o in pods
                    if o != pod
                )
                for obj in moving:
                    s = world_shape(obj)
                    zmin = min(zmin, s.optimalBoundingBox(False, False).ZMin)
                    for other in fixed:
                        if expected_pair(obj, other):
                            continue
                        vol = intersection_volume(s, shapes[other.Name])
                        if vol > TOL:
                            hits.append(
                                {
                                    "angle_deg": angle,
                                    "moving": obj.Name,
                                    "fixed": other.Name,
                                    "intersection_mm3": vol,
                                }
                            )
        finally:
            pod.Tilt = original
            doc.recompute()
        rows.append(
            {
                "pod": pod.Name,
                "poses": 21,
                "independent": independent,
                "minimum_z_mm": zmin,
                "collisions": hits,
                "passed": independent and not hits and zmin >= -TOL,
            }
        )
    return {"pods": rows, "passed": len(rows) == 2 and all(r["passed"] for r in rows)}


def stack_check(registry, objects, shapes):
    posts = list(registry.StackPosts)
    nuts = [o for o in registry.StackLocks if "TopNut" in o.Name]
    screws = [o for o in registry.StackLocks if "Base" in o.Name]
    top_washers = [o for o in registry.StackWashers if "Top" in o.Name]
    upper = max(registry.StandardBoards, key=lambda o: o.getGlobalPlacement().Base.z)
    release_rows = []
    for obj, sign in [(o, 1) for o in nuts + top_washers] + [(o, -1) for o in screws]:
        omitted_nuts = nuts if obj in top_washers else []
        owner = next((m for m in registry.Modules if belongs_to_group(obj, m)), None)
        obstacles = [
            (o.Name, shapes[o.Name])
            for o in objects
            if o != obj
            and o not in omitted_nuts
            and (sign > 0 or (owner is not None and belongs_to_group(o, owner)))
        ]
        path = path_checks(
            [(obj.Name, shapes[obj.Name])],
            obstacles,
            [(0, 0, sign * z) for z in (0, 0.5, 1, 2, 4, 6, 8, 10)],
        )
        release_rows.append(
            {
                "part": obj.Name,
                "path": path,
                "service_condition": (
                    "Remove module from rail before underside screw service"
                    if sign < 0
                    else "Accessible from above"
                ),
                "thread_geometry_is_simplified": True,
                "passed": path["passed"],
            }
        )
    upper_devices = [
        o
        for o in registry.ReferenceParts
        if o.Name in ("ModuleLR900Envelope", "ModulePASEnvelope")
    ]
    moving_objects = [upper] + upper_devices
    omitted = moving_objects + nuts + top_washers
    lift = path_checks(
        [(o.Name, shapes[o.Name]) for o in moving_objects],
        [(o.Name, shapes[o.Name]) for o in objects if o not in omitted],
        [(0, 0, z) for z in (0, 0.5, 1, 2, 4, 6, 8, 16, 32)],
    )
    pitch = hardware.BODY_LENGTH + platform.BOARD_THICKNESS
    extra = [
        (o.Name + "_NextLevel", translated_shape(shapes[o.Name], z=pitch))
        for o in posts
    ]
    extra += [
        (upper.Name + "_NextLevel", translated_shape(shapes[upper.Name], z=pitch))
    ]
    extra += [
        (o.Name + "_Reused", translated_shape(shapes[o.Name], z=pitch))
        for o in nuts + top_washers
    ]
    fixed = [(o.Name, shapes[o.Name]) for o in objects if o not in nuts + top_washers]
    extension_hits = pair_collisions(extra, fixed)
    upper_local = translated_shape(platform.board_shape(), z=pitch)
    hypothetical = [(upper.Name, upper_local)] + [
        (
            o.Name,
            translated_shape(
                hardware.standoff_shape(),
                x,
                y,
                platform.BOARD_BOTTOM + platform.BOARD_THICKNESS,
            ),
        )
        for o, (x, y) in zip(posts, hardware.STACK_CENTRES)
    ]
    battery_rows = []
    for adhesive in (1.0, 3.0):
        pack = Part.makeBox(
            18, 66, 17, V(-9, -33, platform.BOARD_BOTTOM + 2 + adhesive)
        )
        collisions = pair_collisions([("BatteryReference", pack)], hypothetical)
        clearance = pack.distToShape(upper_local)[0]
        battery_rows.append(
            {
                "adhesive_mm": adhesive,
                "collisions": collisions,
                "upper_board_clearance_mm": clearance,
                "passed": not collisions and clearance > 0.5,
            }
        )
    return {
        "purchased_stack_contract": hardware.stack_contract(),
        "post_count": len(posts),
        "base_screw_count": len(screws),
        "top_nut_count": len(nuts),
        "washer_count": len(registry.StackWashers),
        "fastener_release_envelopes": release_rows,
        "upper_board_lift_after_top_hardware_removal": lift,
        "third_level_extension": {
            "board_pitch_mm": pitch,
            "identical_board_and_posts": True,
            "reused_top_hardware": len(nuts + top_washers),
            "collisions": extension_hits,
        },
        "maximum_battery_under_identical_upper_board": battery_rows,
        "retention_tested": False,
        "passed": len(posts) == 4
        and len(screws) == 4
        and len(nuts) == 4
        and len(registry.StackWashers) == 8
        and all(r["passed"] for r in release_rows)
        and lift["passed"]
        and not extension_hits
        and all(r["passed"] for r in battery_rows),
    }


def battery_check(doc, objects):
    battery = doc.ModuleBatteryEnvelope
    original = (
        battery.Length,
        battery.Width,
        battery.Height,
        battery.CentreX,
        battery.CentreY,
    )
    rows = []
    try:
        for size in ((61, 16, 15), (66, 18, 17)):
            battery.Length, battery.Width, battery.Height = size
            for x in (-10, -5, 0, 5, 10):
                for y in (-4, 0, 4):
                    battery.CentreX, battery.CentreY = x, y
                    doc.recompute()
                    s = world_shape(battery)
                    hits = [
                        o.Name
                        for o in objects
                        if o != battery and intersection_volume(s, world_shape(o)) > TOL
                    ]
                    bb = s.optimalBoundingBox(False, False)
                    orientation = (
                        abs(bb.XLength - size[1]) < TOL
                        and abs(bb.YLength - size[0]) < TOL
                    )
                    rows.append(
                        {
                            "size_mm": list(size),
                            "local_centre_xy_mm": [x, y],
                            "collisions": hits,
                            "long_axis_along_y": orientation,
                            "passed": not hits and orientation,
                        }
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
    return {"cases": rows, "passed": len(rows) == 30 and all(r["passed"] for r in rows)}


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
    }
    identity["passed"] = (
        identity["schema_version"] == ARTIFACT_SCHEMA_VERSION
        and identity["manifest_source_fingerprint"] == fingerprint
        and identity["native_source_fingerprint"] == fingerprint
        and identity["mesh_parameters"] == MESH_PARAMETERS
    )
    printed = list(registry.PrintedParts) + list(registry.FitCoupons)
    names = {o.Name for o in printed}
    bought_names = {o.Name for o in registry.HardwareParts}
    rows, exported_names = [], []
    for entry in manifest["parts"]:
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
        fits = all(d <= limit + TOL for d, limit in zip(sizes, (380, 380, 280)))
        fits_sls = all(d <= limit + TOL for d, limit in zip(sizes, (340, 340, 600)))
        good = (
            master.isValid()
            and len(master.Solids) == 1
            and mesh.isSolid()
            and mesh.countComponents() == 1
            and hashes_match
            and mesh_matches
            and step_matches
            and fits
            and fits_sls
            and entry["quantity"] == len(instances)
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
                "fits_nominal_380x380x280_envelope": fits,
                "fits_nominal_340x340x600_envelope": fits_sls,
                "quantity": entry["quantity"],
                "deduplicated_geometry": equivalence,
                "passed": good,
            }
        )
    count = sum(r["quantity"] for r in manifest["parts"])
    each_once = len(exported_names) == len(names) and set(exported_names) == names
    return {
        "process": "SLS/MJF powder-bed PA12; FDM downward-facet rules are not acceptance criteria",
        "supplier_single_piece_acceptance_still_required": True,
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


def beam_limitations():
    # Screening only. Actual fillets, nonuniform curvature, tape and nylon
    # creep mean this is not a fatigue/strength approval.
    nominal_gap = rail.FLEX_GAP
    free_length = max(nominal_gap - 1.0, 0.1)
    calculations = []
    for radius in (300.0, 500.0, 600.0, 1000.0):
        calculations.append(
            {
                "illustrative_radius_mm": radius,
                "one_pitch_angle_rad": rail.LAND_PITCH / radius,
                "idealized_1mm_web_strain_with_nominal_gap": rail.LAND_PITCH
                / (2 * radius * nominal_gap),
                "conservative_1mm_web_strain_with_0p5mm_roots_each_end": rail.LAND_PITCH
                / (2 * radius * free_length),
                "18mm_straight_shoe_sagitta_mm": rail.SHOE_LENGTH**2 / (8 * radius),
            }
        )
    return {
        "calculations": calculations,
        "not_acceptance_criteria": True,
        "limitations": [
            "No balloon radius has been measured.",
            "No tape adhesion, clamp friction, nylon creep or repeated-hinge life was tested.",
            "Printed tolerances are dimensional process guidance, not a local-surface or hole-position guarantee.",
            "A straight saved-model removal sweep does not establish removal while the rail is curved.",
            "The rail base is continuous; its raised capture head has flex reliefs.",
            "Supplier must accept the full rail as one piece; published maximum dimensions alone do not establish that.",
        ],
    }


def detailed_propulsion_evidence(doc, source):
    from gondola.parts import propulsion

    path = source.parent / (source.stem + "_propulsion_validation.json")
    if not path.exists():
        return {
            "passed": False,
            "error": "Final local propulsion validation JSON is missing",
            "expected_file": str(path),
        }
    evidence = json.loads(path.read_text())
    comparisons = []
    pairs = [(doc.PropulsionFixedFrame, propulsion.integral_frame_shape())]
    for prefix in ("Port", "Starboard"):
        pairs.append(
            (doc.getObject(prefix + "MotorCarrier"), propulsion.moving_carrier_shape())
        )
        for side, suffix in ((-1, "Negative"), (1, "Positive")):
            pairs.append(
                (
                    doc.getObject(prefix + "JournalSleeve" + suffix),
                    propulsion.journal_sleeve_shape(side),
                )
            )
    for obj, expected in pairs:
        comparison = geometry_comparison(local_shape(obj), expected)
        comparisons.append({"object": obj.Name, **comparison})
    volume_failures = []

    def inspect(value, location=""):
        if isinstance(value, dict):
            for key, child in value.items():
                if (
                    "overlap" in key
                    and key.endswith("mm3")
                    and isinstance(child, (int, float))
                    and abs(child) > TOL
                ):
                    volume_failures.append(
                        {"field": location + "/" + key, "value": child}
                    )
                inspect(child, location + "/" + key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                inspect(child, location + "/" + str(index))

    inspect(evidence)
    meshes = evidence.get("geometry", [])
    evidence_ok = (
        evidence.get("passed", False)
        and len(evidence.get("sleeve_service_servo_removed", [])) == 4
        and len(evidence.get("motor_and_prop_insertion", [])) == 4
        and len(meshes) == 7
        and all(
            row["valid_brep"]
            and row["solid_count"] == 1
            and row["watertight_mesh"]
            and row["mesh_components"] == 1
            for row in meshes
        )
        and evidence.get("all_hardware_A2", False)
        and evidence.get("no_rail_key_metadata", False)
    )
    return {
        "source_file": os.path.relpath(path, ROOT),
        "source_sha256": file_sha256(path),
        "saved_shape_source_comparisons": comparisons,
        "local_overlap_failures": volume_failures,
        "local_checks": evidence,
        "scope": "Fine local sleeve service requires prior servo removal on the driven sides. Actual servo horn coupling and motor fasteners remain unfinished. MJF uses powder support; FDM facet counters are informational.",
        "passed": evidence_ok
        and not volume_failures
        and all(row["difference_mm3"] < TOL for row in comparisons),
    }


def validate(source=None):
    source = Path(source).resolve() if source else OUTPUT_DIR / (STEM + ".FCStd")
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
            "revision": "I",
            "source": os.path.relpath(source, ROOT),
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
            "Checking neutral assembly, rail/tape, common boards and purchased hardware",
            flush=True,
        )
        report["neutral_assembly"] = neutral_check(objects, shapes)
        report["continuous_rail"] = rail_check(r, shapes)
        report["standard_boards"] = compare_identical_boards(list(r.StandardBoards))
        board_source = geometry_comparison(
            local_shape(r.StandardBoards[0]), platform.board_shape()
        )
        report["standard_boards"]["saved_master_matches_current_source"] = board_source
        report["standard_boards"]["passed"] &= board_source["difference_mm3"] < TOL
        report["metric_hardware"] = hardware_check(r)
        report["assembly_inventory"] = {
            "installed_printed_parts": len(printed),
            "purchased_hardware_items": len(r.HardwareParts),
            "fit_sample_prints": len(r.FitCoupons),
            "identical_board_count": len(r.StandardBoards),
            "single_rail_count": len(r.RailSegments),
            "passed": len(printed) == EXPECTED_INVENTORY["installed_prints"]
            and len(r.HardwareParts) == EXPECTED_INVENTORY["purchased_hardware"]
            and len(r.FitCoupons) == EXPECTED_INVENTORY["fit_coupons"]
            and len(r.StandardBoards) == EXPECTED_INVENTORY["identical_boards"]
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
        print("Checking independent tilt and purchased stack extension", flush=True)
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
        report["stack"] = stack_check(r, objects, shapes)
        report["battery_reference_fit"] = battery_check(doc, objects)
        print("Checking PA12 export identity and saved-file preservation", flush=True)
        report["print_export"] = export_check(source, r)
        report["local_propulsion_evidence"] = detailed_propulsion_evidence(doc, source)
        report["beam_and_service_limits"] = beam_limitations()
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
            "standard_boards",
            "metric_hardware",
            "assembly_inventory",
            "module_service",
            "independent_tilt",
            "continuous_external_rotor_sweeps",
            "stack",
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
        raise SystemExit("Rev I independent audit failed; inspect the validation JSON.")
