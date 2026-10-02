"""Unmodified manufacturer horn and external-hex M1 coupling evidence.

A PASS establishes nominal geometry and limited registration, not delivered
concentricity, installed seating, printed fit, preload, strength or gear runout.
"""

import json

import FreeCAD as App
import Part

from gondola.cad import world_shape
from gondola.contracts import servo_horns
from gondola.contracts.drive import drive_for_document
from gondola.parts import servo_coupling as coupling

from .geometry import certify_translation_clearance
from .propulsion_service import (
    continuous_path,
    driver_service_segment_check,
    fastener_service_check,
    module_service_shapes,
    retained_obstacles,
    servo_lateral_service_check,
)
from .servo_module import (
    driver_gear_service_waypoints,
    input_jack_backoff_vector,
    input_shaft_service_waypoints,
    park_output_rotor_for_input_service,
    servo_service_preparation_check,
    servo_unit_service_waypoints,
)

TOL = 1e-5
V = App.Vector


def coupling_frame(doc, prefix):
    """Map horn-local geometry through the actual mirrored input-drive parents."""
    mirror = App.Rotation(V(0, 0, 1), 180 if prefix == "Starboard" else 0)
    return (
        doc.getObject(prefix + "InputDrive")
        .getGlobalPlacement()
        .multiply(App.Placement(V(), mirror))
        .multiply(App.Placement(V(0, coupling.HORN_BOTTOM_Y, 0), App.Rotation()))
    )


def _difference(first, second):
    return abs(first.cut(second).Volume) + abs(second.cut(first).Volume)


def _plane_contact(first, second, y):
    plane = Part.Face(
        Part.makePolygon(
            [
                V(x, y, z)
                for x, z in ((-20, -20), (25, -20), (25, 20), (-20, 20), (-20, -20))
            ]
        )
    )
    return first.common(plane).common(second.common(plane)).Area


def nut_recess_check(adapter, x, allowance):
    """Saved floor, radial float and minimum-nut turn barriers, independent of cutters."""
    rows = []
    radial_limit = 0.1 + allowance
    for offset in (-radial_limit, 0.0, radial_limit):
        for transverse in (-0.1, 0.0, 0.1):
            nut = coupling._hex_along_axis(
                2.4, 0.8, (x + offset, 6.0, transverse), (0, 1, 0)
            )
            overlap = abs(nut.common(adapter).Volume)
            turns = []
            for angle in (-30, 30):
                turned = nut.copy()
                turned.rotate(V(x + offset, 0, transverse), V(0, 1, 0), angle)
                turns.append(abs(turned.common(adapter).Volume))
            rows.append(
                {
                    "centre_offset_xz_mm": [offset, transverse],
                    "aligned_overlap_mm3": overlap,
                    "turn_30deg_obstruction_mm3": turns,
                    "passed": overlap < TOL and min(turns) > TOL,
                }
            )
    floors = []
    for z in (-1.05, 1.05):
        line = Part.makeLine(V(x, 3.5, z), V(x, 6.0, z))
        floors.append(adapter.common(line).Length)
    return {
        "minimum_nut_af_mm": 2.4,
        "centre_cases": rows,
        "retained_floor_lengths_mm": floors,
        "scope": "Nominal unchamfered minimum-nut screens, not torque or physical fit qualification. Shallow engagement must be checked against actual nut chamfers and printed flat spacing; no axial captivity.",
        "passed": all(row["passed"] for row in rows)
        and all(abs(length - 2.5) < TOL for length in floors),
    }


def factory_opening_check(horn, adapter):
    """Independent literal bores, retained OEM rings and printed inter-hole stock."""
    factory = []
    for x, radius in ((4.5, 0.4), (6.8, 0.5), (10.0, 0.5), (13.2, 0.5)):
        bore = Part.makeCylinder(radius, 2.0, V(x, 1.5, 0), V(0, 1, 0))
        ring = Part.makeCylinder(radius + 0.1, 2.0, V(x, 1.5, 0), V(0, 1, 0)).cut(bore)
        blocked = abs(horn.common(bore).Volume)
        missing = abs(ring.cut(horn).Volume)
        factory.append(
            {
                "x_mm": x,
                "diameter_mm": 2 * radius,
                "blocked_mm3": blocked,
                "missing_ring_mm3": missing,
                "passed": blocked < TOL and missing < TOL,
            }
        )
    openings = []
    for x, elongation in ((6.8, 0.0), (10.0, 0.2), (13.2, 0.3)):
        cylinders = [
            Part.makeCylinder(0.6, 3.6, V(x + shift, 3.5, 0), V(0, 1, 0))
            for shift in (-elongation, elongation)
        ]
        opening = cylinders[0].fuse(cylinders[1])
        if elongation:
            opening = opening.fuse(
                Part.makeBox(2 * elongation, 3.6, 1.2, V(x - elongation, 3.5, -0.6))
            )
        blockage = abs(adapter.common(opening).Volume)
        capture = nut_recess_check(adapter, x, elongation)
        openings.append(
            {
                "x_mm": x,
                "blocked_mm3": blockage,
                "candidate_nut_capture": capture,
                "passed": blockage < TOL and capture["passed"],
            }
        )
    webs = []
    for xmin, xmax, width in ((7.4, 9.2, 1.8), (10.8, 12.3, 1.5)):
        stock = Part.makeBox(width, 2.5, 1.2, V(xmin, 3.5, -0.6))
        missing = abs(stock.cut(adapter).Volume)
        webs.append(
            {
                "x_range_mm": [xmin, xmax],
                "width_mm": width,
                "missing_stock_mm3": missing,
                "passed": missing < TOL,
            }
        )
    return {
        "factory_holes": factory,
        "adapter_openings": openings,
        "retained_floor_webs": webs,
        "inner_0_8_hole_M1_compatible": False,
        "scope": "Literal nominal geometry only; optional middle opening is not an installed third bolt or verified three-bolt service configuration.",
        "passed": all(r["passed"] for r in factory + openings + webs),
    }


def horn_registration_check(doc, prefix):
    """Validate the selected bought profile against the one common printed part."""
    horn_obj = doc.getObject(prefix + "ServoHorn")
    if horn_obj is None or doc.getObject(prefix + "InputDrive") is None:
        return {
            "passed": False,
            "missing_objects": [prefix + "ServoHorn/InputDrive"],
            "physical_concentricity_verified": False,
        }
    try:
        profile = servo_horns.profile(str(horn_obj.HornProfile))
    except (AttributeError, KeyError):
        return {
            "passed": False,
            "error": "Missing or unsupported saved horn profile",
            "physical_concentricity_verified": False,
        }
    selection_matches = profile.key == servo_horns.profile(side=prefix).key
    try:
        saved_contract = json.loads(str(horn_obj.HornInterfaceContract))
        contract_matches = saved_contract == json.loads(
            json.dumps(coupling.assembly_contract(profile))
        )
    except (AttributeError, ValueError):
        contract_matches = False
    expected_hardware = {
        name: shape for name, shape, _ in coupling.horn_hardware_shapes(profile)
    }
    names = (
        "ServoHorn",
        "HornGearAdapter",
        *("HornGearClamp" + name for name in expected_hardware),
    )
    missing = [prefix + name for name in names if doc.getObject(prefix + name) is None]
    if missing:
        return {
            "passed": False,
            "missing_objects": missing,
            "physical_concentricity_verified": False,
        }
    obsolete = [
        name for name in ("HornCenteringJig",) if doc.getObject(name) is not None
    ]
    inverse = coupling_frame(doc, prefix).inverse()
    shapes = {}
    for suffix in names:
        shape = world_shape(doc.getObject(prefix + suffix))
        shape.Placement = inverse.multiply(shape.Placement)
        shapes[suffix] = shape
    horn, adapter = shapes["ServoHorn"], shapes["HornGearAdapter"]
    opening_check = factory_opening_check(horn, adapter)
    adapter_difference = _difference(adapter, coupling.adapter_shape())
    horn_difference = _difference(horn, coupling.horn_shape(profile))
    adapter_obj = doc.getObject(prefix + "HornGearAdapter")
    export_difference = 0.0
    if hasattr(adapter_obj, "PrintBlankShape"):
        exported = adapter_obj.PrintBlankShape.copy()
        exported.Placement = (
            inverse.multiply(adapter_obj.getGlobalPlacement())
            .multiply(adapter_obj.Placement.inverse())
            .multiply(exported.Placement)
        )
        export_difference = _difference(exported, adapter)
    rows = []
    for label, x, elongation in zip(
        ("Near", "Far"),
        profile.attachment_radii_mm,
        coupling.HORN_INSTALLED_OPENING_ALLOWANCES,
    ):
        bolt = shapes["HornGearClamp" + label + "Bolt"]
        difference = _difference(bolt, expected_hardware[label + "Bolt"])
        bearing = shapes["HornGearClamp" + label + "Nut"]
        difference += _difference(bearing, expected_hardware[label + "Nut"])
        diameter = coupling.HORN_CLAMP_THREAD_DIAMETER
        passage = Part.makeCylinder(
            diameter / 2,
            coupling.FASTENER_SEAT_Y - profile.blade_bottom_mm,
            V(x, profile.blade_bottom_mm, 0),
            V(0, 1, 0),
        )
        blocked = horn.common(passage).Volume + adapter.common(passage).Volume
        contact = _plane_contact(adapter, bearing, coupling.FASTENER_SEAT_Y)
        engagement = servo_horns.NUT_HEIGHT_MM
        rear_contact = _plane_contact(horn, bolt, profile.blade_bottom_mm)
        overlap = sum(
            first.common(second).Volume
            for first, second in (
                (bolt, adapter),
                (bolt, horn),
                (bearing, adapter),
                (bearing, horn),
                (bearing, bolt),
            )
        )
        support = []
        # Check front bearing at the actual shank-travel extremes, including
        # circular clearance; a round near hole has no added elongation.
        allowance = elongation + (coupling.SLOT_WIDTH - diameter) / 2
        for offset in (-allowance, 0.0, allowance):
            land = coupling._hex_along_axis(
                servo_horns.NUT_MIN_AF_MM,
                servo_horns.NUT_HEIGHT_MM,
                (x + offset, coupling.FASTENER_SEAT_Y, 0),
                (0, 1, 0),
            )
            area = _plane_contact(adapter, land, coupling.FASTENER_SEAT_Y)
            support.append(
                {
                    "radial_offset_mm": offset,
                    "flat_bearing_contact_mm2": area,
                    "passed": area >= 1.0,
                }
            )
        capture = nut_recess_check(adapter, x, elongation)
        rows.append(
            {
                "joint": label,
                "nut_recess_capture": capture,
                "nominal_fastener_difference_mm3": difference,
                "factory_thread_passage_blockage_mm3": blocked,
                "front_nut_to_adapter_contact_mm2": contact,
                "rear_head_to_horn_contact_mm2": rear_contact,
                "nominal_thread_engagement_mm": engagement,
                "nominal_overlap_mm3": overlap,
                "separate_nut_required": True,
                "minimum_head_support": support,
                "passed": difference < TOL
                and blocked < TOL
                and contact > 1
                and rear_contact > 1
                and overlap < TOL
                and abs(engagement - 0.8) < TOL
                and all(r["passed"] for r in support)
                and capture["passed"],
            }
        )
    collar = adapter.common(
        Part.makeBox(
            20,
            profile.height_mm - coupling.BODY_BACK_Y,
            20,
            V(-10, coupling.BODY_BACK_Y, -10),
        )
    )
    register_rows = []
    for direction in ((-1, 0), (0, -1), (0, 1)):
        moved = horn.copy()
        moved.translate(V(direction[0] * 0.4, 0, direction[1] * 0.4))
        penetration = moved.common(collar).Volume
        register_rows.append(
            {
                "horn_offset_xz_mm": [v * 0.4 for v in direction],
                "register_probe_penetration_mm3": penetration,
                "passed": penetration > TOL,
            }
        )
    seating = _plane_contact(horn, adapter, profile.height_mm)
    measured = bool(getattr(horn_obj, "PurchasedHornMeasured", True))
    axial_unknown = not bool(getattr(horn_obj, "AxialSeatingMeasured", True))
    compatibility = bool(getattr(horn_obj, "X06CompatibilityAccepted", False))
    from gondola.parts.oem_servo_horn import STEP_SHA256

    manufacturer_matches = (
        bool(getattr(horn_obj, "ManufacturerGeometryProvided", False))
        and str(getattr(horn_obj, "ManufacturerGeometrySHA256", "")) == STEP_SHA256
    )
    threads = bool(getattr(horn_obj, "FactoryThreadedHoles", True))
    preparation = bool(getattr(horn_obj, "HornPreparationRequired", True))
    return {
        "pod": prefix,
        "profile": profile.key,
        "source_selection_matches": selection_matches,
        "saved_contract_matches": contract_matches,
        "adapter_difference_mm3": adapter_difference,
        "selected_horn_difference_mm3": horn_difference,
        "print_export_difference_mm3": export_difference,
        "obsolete_horn_parts": obsolete,
        "joints": rows,
        "factory_and_adapter_openings": opening_check,
        "register_directional_stops": register_rows,
        "horn_to_adapter_seating_area_mm2": seating,
        "purchased_horn_measurement_explicitly_unknown": not measured,
        "physical_concentricity_verified": False,
        "axial_seating_explicitly_unmeasured": axial_unknown,
        "x06_compatibility_accepted": compatibility,
        "manufacturer_geometry_matches": manufacturer_matches,
        "factory_threaded_holes": threads,
        "preparation_required": preparation,
        "scope": "Saved unmodified manufacturer half arm, rear M1x6 external-hex bolts and front M1 nuts. Near round hole and far slot locate the two default joints; optional middle opening is not an installed fastener. Nominal source geometry does not qualify received Ø1 slip fit, seating, runout, strength or retention.",
        "passed": selection_matches
        and contract_matches
        and adapter_difference < TOL
        and horn_difference < TOL
        and export_difference < TOL
        and not obsolete
        and not measured
        and axial_unknown
        and compatibility
        and manufacturer_matches
        and not threads
        and not preparation
        and opening_check["passed"]
        and seating > 1
        and all(r["passed"] for r in rows + register_rows),
    }


def input_stub_grip_stock_check(shape, prefix):
    """Independent round distal journal and3.8mm accessible tip witnesses."""
    if prefix not in ("Port", "Starboard"):
        raise ValueError("Unknown servo side")
    required = Part.makeCylinder(1.5, 3.8, V(16, 37.7, 50), V(0, 1, 0))
    journal = Part.makeCylinder(1.5, 19, V(16, 22.5, 50), V(0, 1, 0))
    if prefix == "Starboard":
        required.rotate(V(), V(0, 0, 1), 180)
        journal.rotate(V(), V(0, 0, 1), 180)
    missing = abs(required.cut(shape).Volume)
    missing_journal = abs(journal.cut(shape).Volume)
    return {
        "required_tip_length_mm": 3.8,
        "missing_grip_stock_mm3": missing,
        "round_journal_axial_interval_abs_y_mm": [22.5, 41.5],
        "missing_round_journal_mm3": missing_journal,
        "scope": "LiteralØ3 round journal from|Y|22.5..41.5, beyond the proximal16mm flat. The grip witness is|Y|37.7..41.5,0.7mm beyond the fixed support end. No flat may cross the bearing journal. Nominal stock and clearance do not qualify fit, runout or grip force; never use bearing fasteners to force a misaligned shaft/horn axis.",
        "passed": missing < TOL and missing_journal < TOL,
    }


def assembled_servo_service_check(doc, module, prefix, *, module_release=None):
    """Remove shaft and loose driver before axial servo/horn/adapter withdrawal."""
    shapes, missing = module_service_shapes(doc, module)
    required_bearings = {side + "InputBearing" for side in ("Port", "Starboard")}
    missing = sorted(set(missing) | (required_bearings - shapes.keys()))
    if missing:
        return {"passed": False, "missing_parts": missing, "pod": prefix}
    sign = 1 if prefix == "Port" else -1
    if module_release is None:
        module_release = servo_service_preparation_check(doc, module)
    removed = set(module_release.get("removed_parts", ()))
    shapes, rotor_parking = park_output_rotor_for_input_service(
        doc, module, prefix, shapes, removed
    )
    driver, shaft = prefix + "DriverGear", prefix + "InputShaft"
    jack = prefix + "InputShaftClampBolt"
    backoff = input_jack_backoff_vector(prefix)
    jack_path = continuous_path(
        shapes[jack],
        [(0, 0, 0), backoff],
        retained_obstacles(shapes, removed | {jack}),
    )
    # A small actual radial release is modeled, rather than assuming that an
    # exactly tangent screw tip permits withdrawal under its installed preload.
    shapes[jack] = shapes[jack].copy()
    shapes[jack].translate(V(*backoff))
    local_to_module = (
        module["group"]
        .getGlobalPlacement()
        .inverse()
        .multiply(coupling_frame(doc, prefix))
    )
    tool = Part.makeCylinder(
        1,
        15,
        coupling.shaft_frame_point(-9.1, coupling.SHAFT_CLAMP_Y, 0),
        coupling.shaft_frame_point(-1, 0, 0),
    )
    tool.Placement = local_to_module.multiply(tool.Placement)
    tool_obstacles = retained_obstacles(shapes, removed | {jack})
    tool_hits = {
        name: abs(tool.common(obstacle).Volume)
        for name, obstacle in tool_obstacles.items()
    }
    jack_release = {
        "bolt": jack,
        "backoff_mm": 0.2,
        "backoff_vector_mm": list(backoff),
        "bolt_release": jack_path,
        "tool_radius_mm": 1.0,
        "tool_length_mm": 15.0,
        "tool_intersections_mm3": tool_hits,
        "scope": "A2mm-diameter by15mm radial approach envelope reaches the input M2 jack. Back off its screw0.2mm along its axis; the nut remains seated. Actual hex-key engagement and turning room remain tool checks.",
        "passed": jack_path["passed"] and all(v < TOL for v in tool_hits.values()),
    }
    shaft_points = input_shaft_service_waypoints(prefix)
    shaft_path = continuous_path(
        shapes[shaft], shaft_points, retained_obstacles(shapes, removed | {shaft})
    )
    shaft_path["waypoints_mm"] = shaft_points
    jaws = Part.makeCompound(
        [
            Part.makeBox(15, 3.8, 1.5, V(14.5, 37.7, 47)),
            Part.makeBox(15, 3.8, 1.5, V(14.5, 37.7, 51.5)),
        ]
    )
    if sign < 0:
        jaws.rotate(V(), V(0, 0, 1), 180)
    grip_obstacles = retained_obstacles(shapes, removed | {shaft})
    grip_entry = continuous_path(jaws, [(sign * 60, 0, 0), (0, 0, 0)], grip_obstacles)
    grip_pull = continuous_path(jaws, shaft_points, grip_obstacles)
    grip_stock = input_stub_grip_stock_check(shapes[shaft], prefix)
    shaft_grip = {
        "jaw_box_mm": [[15, 3.8, 1.5], [15, 3.8, 1.5]],
        "nominal_round_tip_contact": "opposed tangent faces atZ48.5 and51.5",
        "shaft_tip_projection_beyond_support_mm": 4.5,
        "jaw_contact_axial_length_mm": 3.8,
        "tip_stock": grip_stock,
        "side_entry": grip_entry,
        "shaft_pull": grip_pull,
        "scope": "With this output rotor parked and input neutral, two side-entry fine-plier jaws grip3.8mm of the round tip beyond the support. Support the driver while releasing both set screws. Pull32mm axially to clear the retained input bearing and housing, then move outwardX60. Actual plier dimensions and non-damaging grip remain physical checks.",
        "passed": grip_entry["passed"] and grip_pull["passed"] and grip_stock["passed"],
    }
    removed.add(shaft)
    driver_points = driver_gear_service_waypoints(prefix)
    driver_path = driver_service_segment_check(
        shapes[driver],
        driver_points[0],
        driver_points[1],
        retained_obstacles(shapes, removed | {driver}),
        drive_for_document(doc),
        sign,
    )
    driver_path["waypoints_mm"] = driver_points
    removed.add(driver)
    ear_rows = []
    for side in ("Lower", "Upper"):
        name = prefix + "ServoEar" + side
        pair = {name + "Bolt", name + "Nut"}
        ear_rows.append(
            {
                "bolt": name + "Bolt",
                **fastener_service_check(
                    shapes[name + "Bolt"],
                    shapes[name + "Nut"],
                    retained_obstacles(shapes, removed | pair),
                    thread_diameter=1.6,
                    guided_nut=True,
                    capture_depth_mm=0.5,
                ),
            }
        )
        removed.update(pair)
    moving = {
        prefix + suffix
        for suffix in (
            "Servo",
            "ServoHorn",
            "HornGearAdapter",
            "HornGearClampNearBolt",
            "HornGearClampFarBolt",
            "HornGearClampNearNut",
            "HornGearClampFarNut",
            "InputShaftClampBolt",
            "InputShaftClampNut",
        )
    }
    fixed = retained_obstacles(shapes, removed | moving)
    points = servo_unit_service_waypoints(prefix)
    paths = []
    for name in sorted(moving):
        segments = []
        for start, end in zip(points, points[1:]):
            if name.endswith("Servo"):
                checked = servo_lateral_service_check(shapes[name], start, end, fixed)
            elif name.endswith("HornGearAdapter"):
                placed = shapes[name].copy()
                placed.translate(V(*start))
                certificate = certify_translation_clearance(
                    placed, tuple(b - a for a, b in zip(start, end)), fixed
                )
                checked = {
                    "obstacles": sorted(fixed),
                    "segments": [certificate],
                    "passed": certificate["passed"],
                }
            else:
                checked = continuous_path(shapes[name], [start, end], fixed)
            segments.append({"start_mm": list(start), "end_mm": list(end), **checked})
        path = {
            "obstacles": sorted(fixed),
            "segments": segments,
            "passed": all(row["passed"] for row in segments),
        }
        paths.append({"part": name, "waypoints_mm": points, **path})
    # The horn joints remain assembled until the remaining unit is off-frame.
    bench = moving
    # On the detached unit, preserve the stock horn and rear M1 screws.
    inverse = coupling_frame(doc, prefix).inverse()
    profile = servo_horns.profile(str(doc.getObject(prefix + "ServoHorn").HornProfile))
    local_names = {
        "horn": "ServoHorn",
        "adapter": "HornGearAdapter",
        "servo": "Servo",
        "shaft_bolt": "InputShaftClampBolt",
        "shaft_nut": "InputShaftClampNut",
        **{
            name: "HornGearClamp" + name
            for name, _, _ in coupling.horn_hardware_shapes(profile)
        },
    }
    local = {}
    for key, suffix in local_names.items():
        shape = world_shape(doc.getObject(prefix + suffix))
        shape.Placement = inverse.multiply(shape.Placement)
        local[key] = shape
    holding = []
    for x in profile.attachment_radii_mm:
        stem = Part.makeCylinder(
            servo_horns.KST_TOOL_DIAMETER_MM / 2,
            servo_horns.KST_TOOL_LENGTH_MM,
            V(x, profile.blade_bottom_mm, 0),
            V(0, -1, 0),
        )
        # Full cylinder conservatively bounds the socket exterior; omit only
        # the driven bolt occupying its internal hex socket.
        driven = "NearBolt" if x == profile.attachment_radii_mm[0] else "FarBolt"
        hits = {
            prefix + local_names[key]: stem.common(shape).Volume
            for key, shape in local.items()
            if key != driven
        }
        holding.append(
            {
                "radius_mm": x,
                "tool_diameter_mm": servo_horns.KST_TOOL_DIAMETER_MM,
                "tool_length_mm": servo_horns.KST_TOOL_LENGTH_MM,
                "minimum_servo_clearance_mm": stem.distToShape(local["servo"])[0],
                "retained_part_overlaps_mm3": hits,
                "passed": all(volume < TOL for volume in hits.values()),
            }
        )
    fasteners = []
    removed_nuts = []
    nut_release_y = (
        profile.blade_bottom_mm
        + profile.screw_length_mm
        - coupling.FASTENER_SEAT_Y
        + 0.2
    )
    # Remove outer front nut first, then inner. Rear screws remain in the horn
    # until the adapter has cleared their forward tips.
    for label in ("Far", "Near"):
        n = label + "Nut"
        nut = local[n]
        obstacles = {k: s for k, s in local.items() if k != n}
        first = continuous_path(nut, [(0, 0, 0), (0, nut_release_y, 0)], obstacles)
        x = profile.attachment_radii_mm[0 if label == "Near" else 1]
        outer = coupling._hex_along_axis(
            servo_horns.NUT_AF_MM,
            servo_horns.NUT_HEIGHT_MM,
            (x, coupling.FASTENER_SEAT_Y, 0),
            (0, 1, 0),
        )
        second = continuous_path(
            outer, [(0, nut_release_y, 0), (20, nut_release_y, 0)], obstacles
        )
        route = {
            "segments": first["segments"] + second["segments"],
            "passed": first["passed"] and second["passed"],
            "scope": "Turn the accessible rear screw while the shared trough restrains its nut; lift the nut axially clear of its recess and screw tip, then use the filled outer-hex lateral release envelope.",
        }
        x = profile.attachment_radii_mm[0 if label == "Near" else 1]
        # The rear screw first lifts the restrained nut out of its recess;
        # full-height fine-plier access is needed only after that release.
        plier_lift = coupling.HORN_NUT_RECESS_DEPTH + 0.2
        jaws = Part.makeCompound(
            [
                Part.makeBox(
                    6,
                    0.7,
                    1,
                    V(x - 0.5, coupling.FASTENER_SEAT_Y + plier_lift + 0.05, z),
                )
                for z in (-2.25, 1.25)
            ]
        )
        collisions = {
            k: jaws.common(s).Volume
            for k, s in obstacles.items()
            if jaws.common(s).Volume > TOL
        }
        fasteners.append(
            {
                "joint": label,
                "bolt": prefix + "HornGearClamp" + label + "Bolt",
                "nut": prefix + "HornGearClamp" + label + "Nut",
                "retained_parts": [prefix + local_names[k] for k in obstacles],
                "removed_prior_parts": sorted(removed) + removed_nuts.copy(),
                "removed_part": prefix + "HornGearClamp" + n,
                "front_nut_release": route,
                "fine_plier_access_after_nut_lift_mm": plier_lift,
                "fine_plier_jaw_collisions_mm3": collisions,
                "passed": route["passed"] and not collisions,
            }
        )
        local.pop(n)
        removed_nuts.append(prefix + "HornGearClamp" + n)
    adapter_moving = {"adapter", "shaft_bolt", "shaft_nut"}
    adapter_obstacles = {
        prefix + local_names[k]: shape
        for k, shape in local.items()
        if k not in adapter_moving
    }
    adapter_points = [
        (0, 0, 0),
        (0, coupling.RETAINED_BOLT_RELEASE_TRAVEL, 0),
        (40, coupling.RETAINED_BOLT_RELEASE_TRAVEL, 0),
    ]
    adapter_route = continuous_path(
        coupling.service_envelope(retain_screws=True), adapter_points, adapter_obstacles
    )
    clamp_paths = [
        {
            "part": prefix + local_names[key],
            **continuous_path(local[key], adapter_points, adapter_obstacles),
        }
        for key in ("shaft_bolt", "shaft_nut")
    ]
    adapter_route["retained_clamp_hardware_paths"] = clamp_paths
    adapter_route["passed"] = adapter_route["passed"] and all(
        row["passed"] for row in clamp_paths
    )
    passed = (
        module_release["passed"]
        and rotor_parking["passed"]
        and jack_release["passed"]
        and shaft_grip["passed"]
        and driver_path["passed"]
        and shaft_path["passed"]
        and adapter_route["passed"]
        and all(r["passed"] for r in ear_rows + paths + holding + fasteners)
    )
    return {
        "pod": prefix,
        "service_mode": "shaft_first_compact_frame",
        "preparation_passed": module_release["passed"],
        "required_prior_check": "servo_service_preparation",
        "output_rotor_parking": rotor_parking,
        "driver_gear_removal": driver_path,
        "input_stub_removal": shaft_path,
        "input_jack_release": jack_release,
        "input_stub_grip_tool": shaft_grip,
        "ear_fastener_release": ear_rows,
        "part_paths": paths,
        "moving_parts": sorted(moving),
        "removed_parts": sorted(removed | moving),
        "retained_parts": sorted(fixed),
        "bench_members": sorted(bench),
        "rear_holding_tool_off_frame": holding,
        "adapter_clamp_release": {
            "fasteners": fasteners,
            "passed": all(r["passed"] for r in fasteners),
        },
        "adapter_release_off_frame": adapter_route,
        "scope": "KST only, unpowered and leads disconnected: remove both small output gears. Leave the input neutral and park only the selected output rotor90deg about module+Y. Support the48T driver, release its unmodeled set screw and back off the input M2 jack0.2mm. Grip3.8mm of the35mm shaft's round tip beyond the input support; pull32mm forwardY then60mm outwardX. Input bearing and cap remain fixed. Remove the loose driver60mm outwardX. Withdraw the two M1.6 ear screws and lift their nuts from the shallow pockets. Keep the OEM horn and both M1 joints assembled: move servo/horn/adapter13mm forwardY through the7.4x20.4 window, then60mm outwardX; mirror translation X/Y for Starboard. Only off-frame turn rear M1 screws to release the front nuts; retain screws until the adapter clears their tips. A<=5.7mm OD x60mm rear hex nutdriver and fine pliers are off-frame envelopes. Actual gear set-screw access, tool grip, coaxiality and horn runout remain physical checks. The optional centre opening is outside this two-bolt configuration. Reverse for assembly: fit OEM spline screw before adapter, seat the servo, insert round journal and align without forcing, then tighten shaft/gear clamps. Return rotor to neutral before refitting output gears. Finish tight windows without case compression or bearing preload. Full shaft-stop floor retained; no physical retention or stiffness rating.",
        "passed": passed,
    }


def profile_compatibility_checks():
    """Exercise every profile on both mirrored sides without changing saved CAD."""
    from gondola.parts import propulsion, servo_envelope

    rows = []
    original = dict(servo_horns.SELECTED_BY_SIDE)
    active = App.ActiveDocument.Name if App.ActiveDocument else None
    try:
        for key, profile in servo_horns.PROFILES.items():
            servo_horns.SELECTED_BY_SIDE.update(Port=key, Starboard=key)
            doc = App.newDocument("HornProfileAudit" + key)
            try:
                module = propulsion.build_propulsion_module(doc)
                doc.recompute()
                registration = [
                    horn_registration_check(doc, p) for p in ("Port", "Starboard")
                ]
                case = servo_envelope.shape()
                case.translate(V(0, -coupling.HORN_BOTTOM_Y, 0))
                from .servo_interface import horn_spline_contact, sourced_spline_volume

                spline, spline_evidence = sourced_spline_volume(
                    case, (0, 0, 0), (0, 1, 0)
                )
                if spline is None:
                    raise ValueError(spline_evidence)
                case_and_ears = case.cut(spline)
                moving = {
                    "adapter": coupling.adapter_shape(),
                    "horn": coupling.horn_shape(profile),
                    **{n: s for n, s, _ in coupling.horn_hardware_shapes(profile)},
                }
                overlaps = []
                for angle in range(-60, 61, 5):
                    for name, shape in moving.items():
                        turned = shape.copy()
                        turned.rotate(V(), V(0, 1, 0), angle)
                        contact = (
                            horn_spline_contact(turned, case, (0, 0, 0), (0, 1, 0))
                            if name == "horn"
                            else None
                        )
                        volume = turned.common(
                            case_and_ears if name == "horn" else case
                        ).Volume
                        if volume > TOL or (
                            contact is not None and not contact["passed"]
                        ):
                            overlaps.append(
                                {"angle_deg": angle, "part": name, "volume_mm3": volume}
                            )
                module_release = servo_service_preparation_check(doc, module)
                service = [
                    assembled_servo_service_check(
                        doc, module, p, module_release=module_release
                    )
                    for p in ("Port", "Starboard")
                ]
                adapter = coupling.adapter_shape()
                web_rows = []
                for name, start, end, minimum in (
                    (
                        "slot_end_web",
                        (14.5, 5.0, 0),
                        (coupling.PLATE_X_MAX, 5.0, 0),
                        1.5,
                    ),
                    ("near_nut_socket_wall", (1.55, 8.0, 0), (2.65, 8.0, 0), 1.1),
                    (
                        "root_register_wall",
                        (-coupling.REGISTER_OUTER_RADIUS, 2.5, 0),
                        (-coupling.REGISTER_INNER_RADIUS, 2.5, 0),
                        coupling.REGISTER_OUTER_RADIUS - coupling.REGISTER_INNER_RADIUS,
                    ),
                ):
                    thickness = adapter.common(Part.makeLine(V(*start), V(*end))).Length
                    web_rows.append(
                        {
                            "feature": name,
                            "thickness_mm": thickness,
                            "minimum_mm": minimum,
                            "passed": thickness >= minimum - TOL,
                        }
                    )
                rows.append(
                    {
                        "profile": key,
                        "functional_webs": web_rows,
                        "registration": registration,
                        "servo_sweep_angles_deg": list(range(-60, 61, 5)),
                        "servo_sweep_overlaps": overlaps,
                        "conditional_service": service,
                        "scope": "Nominal profile envelopes and sampled input rotation; no elastic/runout/strength or received-part certification.",
                        "passed": not overlaps
                        and all(r["passed"] for r in registration + service + web_rows),
                    }
                )
            finally:
                App.closeDocument(doc.Name)
    finally:
        servo_horns.SELECTED_BY_SIDE.clear()
        servo_horns.SELECTED_BY_SIDE.update(original)
        if active:
            App.setActiveDocument(active)
    return rows
