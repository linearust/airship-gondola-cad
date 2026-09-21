"""Recompute local propulsion fit and removal evidence from current geometry.

Rigid envelopes preserve explicit OEM fit, clamp grip and load limitations.
The checks cover supported gearing, separate shafts, positive bearing capture
and practical disassembly geometry without certifying physical operation.
"""

import json
import math
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

from gondola.cad import (
    translated_shape,
    world_shape,
)
from gondola.config import ARTIFACT_STEM, OUTPUT_DIR
from gondola.parts import propulsion, rail
from gondola.print_export import geometry_comparison, mesh_checks, print_shape

from .evidence import overlap_failures
from .geometry import (
    belongs_to_group,
    certify_translation_clearance,
    intersection_volume,
    translation_sweep,
)

TOL = 1e-5


def gear_mesh_check(
    driver,
    output,
    *,
    module,
    driver_teeth,
    output_teeth,
    minimum_face_overlap,
    maximum_centre_adjustment=0.19,
    minimum_contact_ratio=1.3,
):
    """Measure tooth-face engagement independently of the protruding gear hubs.

    The assemblies use parallel Y axes. An annular section near each pitch
    circle isolates actual tooth material; a hub overlapping another hub must
    not pass as an engaged gear pair. This is a positioning check, not tooth
    strength, backlash or loaded mesh qualification. The independent contact
    ratio screen uses the standard unshifted 20-degree involute dimensions.
    """
    sections = []
    for shape, teeth in ((driver, driver_teeth), (output, output_teeth)):
        if shape.isNull() or not shape.isValid() or not shape.Solids:
            return {"passed": False, "error": "Missing or invalid gear solid"}
        bounds = shape.optimalBoundingBox(False, False)
        centre_x = (bounds.XMin + bounds.XMax) / 2
        centre_z = (bounds.ZMin + bounds.ZMax) / 2
        pitch_radius = module * teeth / 2
        origin = App.Vector(centre_x, bounds.YMin - 1, centre_z)
        annulus = Part.makeCylinder(
            pitch_radius + module,
            bounds.YLength + 2,
            origin,
            App.Vector(0, 1, 0),
        ).cut(
            Part.makeCylinder(
                pitch_radius - module / 4,
                bounds.YLength + 2,
                origin,
                App.Vector(0, 1, 0),
            )
        )
        teeth_section = shape.common(annulus)
        if teeth_section.isNull() or abs(teeth_section.Volume) < TOL:
            return {"passed": False, "error": "No material at the gear pitch circle"}
        tooth_bounds = teeth_section.optimalBoundingBox(False, False)
        sections.append(
            {
                "axis_xz_mm": [centre_x, centre_z],
                "tooth_face_y_mm": [tooth_bounds.YMin, tooth_bounds.YMax],
                "pitch_radius_mm": pitch_radius,
            }
        )
    first, second = sections
    distance = math.dist(first["axis_xz_mm"], second["axis_xz_mm"])
    expected_distance = module * (driver_teeth + output_teeth) / 2
    face_overlap = min(first["tooth_face_y_mm"][1], second["tooth_face_y_mm"][1]) - max(
        first["tooth_face_y_mm"][0], second["tooth_face_y_mm"][0]
    )
    pressure_angle = math.radians(20)
    pitch_radii = [module * teeth / 2 for teeth in (driver_teeth, output_teeth)]
    base_radii = [radius * math.cos(pressure_angle) for radius in pitch_radii]
    tip_radii = [radius + module for radius in pitch_radii]
    approach_recess = sum(
        math.sqrt(tip * tip - base * base) for tip, base in zip(tip_radii, base_radii)
    )
    contact_path = approach_recess - math.sqrt(
        max(0.0, distance * distance - sum(base_radii) ** 2)
    )
    contact_ratio = contact_path / (math.pi * module * math.cos(pressure_angle))
    return {
        "driver": first,
        "output": second,
        "axis_distance_mm": distance,
        "nominal_axis_distance_mm": expected_distance,
        "maximum_axis_distance_mm": expected_distance + maximum_centre_adjustment,
        "tooth_face_overlap_mm": face_overlap,
        "minimum_face_overlap_mm": minimum_face_overlap,
        "standard_involute_contact_ratio": contact_ratio,
        "minimum_contact_ratio": minimum_contact_ratio,
        "scope": "Saved gear position, actual tooth-band axial overlap and theoretical unshifted 20-degree involute contact ratio. Tooth approximation, backlash, tooth strength and operational servo fit remain unqualified.",
        "passed": expected_distance - TOL
        <= distance
        <= expected_distance + maximum_centre_adjustment + TOL
        and face_overlap >= minimum_face_overlap - TOL
        and contact_ratio >= minimum_contact_ratio - TOL,
    }


def drive_motion_check(doc, prefix):
    """Exercise native bounded output and opposite one-third input rotations."""
    pod = doc.getObject(prefix + "Pod")
    drive = doc.getObject(prefix + "InputDrive")
    if pod is None or drive is None:
        return {"passed": False, "error": "Missing output pod or input drive"}
    original_tilt = float(pod.Tilt)
    rows = []
    endpoint_rotations = {}
    try:
        for requested in (-999, -180, -90, 0, 90, 180, 999):
            pod.Tilt = requested
            doc.recompute()
            output_angle = min(180.0, max(-180.0, requested))
            input_angle = -output_angle / 3
            output_matches = pod.Placement.Rotation.isSame(
                App.Rotation(App.Vector(0, 1, 0), output_angle), 1e-7
            )
            input_matches = drive.Placement.Rotation.isSame(
                App.Rotation(App.Vector(0, 1, 0), input_angle), 1e-7
            )
            if requested in (-180, 180):
                endpoint_rotations[requested] = drive.Placement.Rotation
            rows.append(
                {
                    "requested_output_deg": requested,
                    "bounded_output_deg": output_angle,
                    "required_servo_deg": input_angle,
                    "output_rotation_matches": output_matches,
                    "input_rotation_matches": input_matches,
                    "passed": output_matches and input_matches,
                }
            )
    finally:
        pod.Tilt = original_tilt
        doc.recompute()
    distinct_endpoints = not endpoint_rotations[-180].isSame(
        endpoint_rotations[180], 1e-7
    )
    return {
        "pod": prefix,
        "cases": rows,
        "opposite_output_endpoints_keep_distinct_input_positions": distinct_endpoints,
        "scope": "Native expressions and declared kinematic ratio only; physical servo endpoint calibration and motor-lead travel remain unverified.",
        "passed": distinct_endpoints and all(row["passed"] for row in rows),
    }


def gear_rotation_check(doc, prefix):
    """Screen actual tooth solids at distinct phases spanning one output tooth.

    The end stops are also included. These sampled CAD positions supplement
    the native ratio check; they do not certify a continuous contact ratio or
    real backlash under load.
    """
    pod = doc.getObject(prefix + "Pod")
    driver = doc.getObject(prefix + "DriverGear60T")
    output = doc.getObject(prefix + "OutputGear20T")
    if any(obj is None for obj in (pod, driver, output)):
        return {"passed": False, "error": "Missing gear pair or output pod"}
    original_tilt = float(pod.Tilt)
    rows = []
    try:
        for angle in (-180, 0, 0.37, 1.1, 3.7, 7.33, 11.5, 15.25, 18, 180):
            pod.Tilt = angle
            doc.recompute()
            volume = intersection_volume(world_shape(driver), world_shape(output))
            rows.append(
                {
                    "output_angle_deg": angle,
                    "tooth_solid_intersection_mm3": volume,
                    "passed": volume < TOL,
                }
            )
    finally:
        pod.Tilt = original_tilt
        doc.recompute()
    return {
        "pod": prefix,
        "sampled_tooth_phases": rows,
        "continuous_mesh_qualified": False,
        "passed": all(row["passed"] for row in rows),
    }


def mesh_adjustment_check(doc, prefix):
    """Bound the native adjustment and check both operating mesh extremes."""
    pod = doc.getObject(prefix + "Pod")
    cartridge = doc.getObject(prefix + "InputCartridge")
    original_tilt = float(pod.Tilt)
    original_adjustment = float(cartridge.MeshClearance.Value)
    rows = []
    phase_checks = []
    sign = 1 if prefix == "Port" else -1
    try:
        pod.Tilt = 0
        for requested in (-999, 0, 0.19, 999):
            cartridge.MeshClearance = requested
            doc.recompute()
            expected = min(0.19, max(0, requested))
            base = cartridge.Placement.Base
            measured = math.hypot(base.x, base.z - propulsion.PIVOT_Z) - 20
            expected_x = sign * propulsion.INPUT_AXIS_X * (1 + expected / 20)
            expected_z = propulsion.PIVOT_Z + (
                propulsion.INPUT_AXIS_Z - propulsion.PIVOT_Z
            ) * (1 + expected / 20)
            line_error = math.hypot(base.x - expected_x, base.z - expected_z)
            mesh = gear_mesh_check(
                world_shape(doc.getObject(prefix + "DriverGear60T")),
                world_shape(doc.getObject(prefix + "OutputGear20T")),
                module=0.5,
                driver_teeth=60,
                output_teeth=20,
                minimum_face_overlap=3,
            )
            rows.append(
                {
                    "requested_radial_clearance_mm": requested,
                    "bounded_adjustment_mm": expected,
                    "actual_adjustment_mm": measured,
                    "radial_position_error_mm": line_error,
                    "mesh": mesh,
                    "passed": abs(measured - expected) < TOL
                    and line_error < TOL
                    and mesh["passed"],
                }
            )
            if requested in (0, 0.19):
                phase_checks.append(
                    {"mesh_clearance_mm": expected, **gear_rotation_check(doc, prefix)}
                )
    finally:
        pod.Tilt = original_tilt
        cartridge.MeshClearance = original_adjustment
        doc.recompute()
    return {
        "pod": prefix,
        "cases": rows,
        "tooth_phase_checks": phase_checks,
        "passed": all(row["passed"] for row in rows + phase_checks),
    }


def bearing_stack_check(bearing, shaft, seat, cap):
    """Check a nominal MR63ZZ seat, coaxial through-shaft and two-sided capture.

    The bearing reference is a 3 × 6 × 2.5 mm annular stock envelope. The outer
    ring is retained by the printed seat and removable cap. Shaft grip is a
    separate clamp check; these clearances do not prove a friction fit or load
    capacity.
    """
    if any(shape.isNull() for shape in (bearing, shaft, seat)):
        return {"passed": False, "error": "Missing bearing, shaft or fixed seat"}
    bounds = bearing.optimalBoundingBox(False, False)
    centre_x = (bounds.XMin + bounds.XMax) / 2
    centre_z = (bounds.ZMin + bounds.ZMax) / 2
    origin = App.Vector(centre_x, bounds.YMin, centre_z)
    axis = App.Vector(0, 1, 0)
    expected_bearing = Part.makeCylinder(3, 2.5, origin, axis).cut(
        Part.makeCylinder(1.5, 2.5, origin, axis)
    )
    bearing_comparison = geometry_comparison(bearing, expected_bearing)
    shaft_bounds = shaft.optimalBoundingBox(False, False)
    shaft_axis_error = math.hypot(
        (shaft_bounds.XMin + shaft_bounds.XMax) / 2 - centre_x,
        (shaft_bounds.ZMin + shaft_bounds.ZMax) / 2 - centre_z,
    )
    shaft_coverage = min(bounds.YMax, shaft_bounds.YMax) - max(
        bounds.YMin, shaft_bounds.YMin
    )
    seat_hit = intersection_volume(bearing, seat)
    cap_hit = 0 if cap.isNull() else intersection_volume(bearing, cap)
    shaft_hit = intersection_volume(bearing, shaft)
    retainers = seat if cap.isNull() else Part.makeCompound([seat, cap])
    capture_rows = []
    for direction in (-1, 1):
        moved = translated_shape(bearing, y=direction)
        blocking_volume = intersection_volume(moved, retainers)
        capture_rows.append(
            {
                "translation_y_mm": direction,
                "blocking_intersection_mm3": blocking_volume,
                "passed": blocking_volume > TOL,
            }
        )
    return {
        "stock_shape_comparison": bearing_comparison,
        "shaft_axis_error_mm": shaft_axis_error,
        "shaft_through_bearing_length_mm": shaft_coverage,
        "bearing_seat_overlap_mm3": seat_hit,
        "bearing_cap_overlap_mm3": cap_hit,
        "bearing_shaft_overlap_mm3": shaft_hit,
        "axial_capture": capture_rows,
        "scope": "Nominal MR63ZZ envelope, coaxial shaft coverage and bidirectional outer-ring capture. Printed fits, bearing race contact, clamp grip and loads require a physical trial.",
        "passed": bearing_comparison["difference_mm3"] < TOL
        and shaft_axis_error < TOL
        and shaft_coverage >= 2.5 - TOL
        and seat_hit < TOL
        and cap_hit < TOL
        and shaft_hit < TOL
        and not cap.isNull()
        and all(row["passed"] for row in capture_rows),
    }


def clamp_fastener_check(clamp, bolt, nut, *, thread_diameter=2.0, nut_height=1.2):
    """Require seated bolt/nut bearing faces and a complete nominal metric nut core.

    This checks assembly geometry only. A tightened split clamp's shaft torque
    capacity, creep and axial grip are not established by a rigid CAD model.
    """
    contacts = []
    for name, fastener in (("Bolt", bolt), ("Nut", nut)):
        area = 0.0
        for face in fastener.Faces:
            if type(face.Surface).__name__ != "Plane":
                continue
            normal = face.normalAt(0, 0)
            for seat_face in clamp.Faces:
                if type(seat_face.Surface).__name__ != "Plane":
                    continue
                if (
                    abs(abs(normal.dot(seat_face.normalAt(0, 0))) - 1) < 1e-7
                    and abs((face.CenterOfMass - seat_face.CenterOfMass).dot(normal))
                    < 1e-7
                ):
                    area += face.common(seat_face).Area
        contacts.append(
            {"part": name, "bearing_contact_area_mm2": area, "passed": area > TOL}
        )
    bore_surfaces = [
        face.Surface
        for face in nut.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - thread_diameter / 2) < TOL
    ]
    if not bore_surfaces:
        return {
            "contacts": contacts,
            "passed": False,
            "error": "Missing metric nut bore",
        }
    bore = bore_surfaces[0]
    axis = bore.Axis
    projections = [vertex.Point.dot(axis) for vertex in nut.Vertexes]
    low, high = min(projections), max(projections)
    origin = bore.Center + axis * (low - bore.Center.dot(axis))
    core = Part.makeCylinder(thread_diameter * 0.4, high - low, origin, axis)
    missing_core = abs(core.cut(bolt).Volume)
    clamp_overlap = intersection_volume(clamp, bolt) + intersection_volume(clamp, nut)
    return {
        "contacts": contacts,
        "nut_engagement_length_mm": high - low,
        "missing_bolt_thread_core_mm3": missing_core,
        "fastener_clamp_overlap_mm3": clamp_overlap,
        "scope": "Nominal seated metric fasteners with full nut core; no helical-thread, preload, shaft-friction or printed-clamp strength qualification.",
        "passed": all(row["passed"] for row in contacts)
        and missing_core < TOL
        and high - low >= nut_height - TOL
        and clamp_overlap < TOL,
    }


def output_stub_check(shaft, motor, pivot_y):
    """Keep each purchased output stub clear of the central propulsion motor."""
    bounds = shaft.optimalBoundingBox(False, False)
    stays_on_one_side = bounds.YMax < pivot_y - TOL or bounds.YMin > pivot_y + TOL
    volume = intersection_volume(shaft, motor)
    clearance = shaft.distToShape(motor)[0]
    return {
        "shaft_y_bounds_mm": [bounds.YMin, bounds.YMax],
        "pivot_y_mm": pivot_y,
        "separate_stub_on_one_side": stays_on_one_side,
        "motor_overlap_mm3": volume,
        "motor_gap_mm": clearance,
        "minimum_motor_gap_mm": 0.3,
        "passed": stays_on_one_side and volume < TOL and clearance >= 0.3 - TOL,
    }


def tilt_clearance_check(doc, module, prefix):
    """Move both coupled groups and inspect live shapes against the fixed parts."""
    pod = doc.getObject(prefix + "Pod")
    drive = doc.getObject(prefix + "InputDrive")
    objects = module["printed"] + module["hardware"] + module["references"]
    moving = [
        obj
        for obj in objects
        if belongs_to_group(obj, pod) or belongs_to_group(obj, drive)
    ]
    output_moving = [obj for obj in moving if belongs_to_group(obj, pod)]
    input_moving = [obj for obj in moving if belongs_to_group(obj, drive)]
    fixed = [obj for obj in objects if obj not in moving]
    original_tilt = float(pod.Tilt)
    cartridge = doc.getObject(prefix + "InputCartridge")
    original_clearance = float(cartridge.MeshClearance.Value)
    rows = []
    try:
        for clearance, index in ((c, i) for c in (0, 0.19) for i in range(49)):
            cartridge.MeshClearance = clearance
            angle = -180 + index * 7.5
            pod.Tilt = angle
            doc.recompute()
            fixed_shapes = {obj.Name: world_shape(obj) for obj in fixed}
            moving_shapes = {obj.Name: world_shape(obj) for obj in moving}
            collisions = []
            minimum_z = float("inf")
            for obj in moving:
                shape = moving_shapes[obj.Name]
                minimum_z = min(minimum_z, shape.optimalBoundingBox(False, False).ZMin)
                for name, obstacle in fixed_shapes.items():
                    volume = intersection_volume(shape, obstacle)
                    if volume > TOL:
                        collisions.append(
                            {
                                "moving": obj.Name,
                                "fixed": name,
                                "intersection_mm3": volume,
                            }
                        )
            for output_object in output_moving:
                for input_object in input_moving:
                    volume = intersection_volume(
                        moving_shapes[output_object.Name],
                        moving_shapes[input_object.Name],
                    )
                    if volume > TOL:
                        collisions.append(
                            {
                                "moving": output_object.Name,
                                "other_moving": input_object.Name,
                                "intersection_mm3": volume,
                            }
                        )
            rows.append(
                {
                    "output_angle_deg": angle,
                    "mesh_clearance_mm": clearance,
                    "minimum_z_mm": minimum_z,
                    "collisions": collisions,
                    "passed": not collisions and minimum_z >= -TOL,
                }
            )
    finally:
        pod.Tilt = original_tilt
        cartridge.MeshClearance = original_clearance
        doc.recompute()
    return {
        "pod": prefix,
        "moving_objects": [obj.Name for obj in moving],
        "fixed_objects": [obj.Name for obj in fixed],
        "relative_motion_pairs_checked_per_pose": len(output_moving)
        * len(input_moving),
        "poses": rows,
        "scope": "49 sampled coupled-output/input positions at each of both radial mesh-clearance extremes, including both bounded rotation endpoints. Checks live fixed obstacles and every output-pod/input-drive pair, including gear teeth; no gear-pair exclusion. Not a continuous rigid-body or connected-wire sweep proof.",
        "passed": bool(moving) and all(row["passed"] for row in rows),
    }


def input_cartridge_service_check(doc, module, prefix):
    """Remove the output gear, slide the released cartridge sideways and lift.

    This is a sampled bench-service path after removing the propulsion module
    from its rail. The adjacent vehicle equipment is outside this local audit.
    """
    cartridge = doc.getObject(prefix + "InputCartridge")
    sign = 1 if prefix == "Port" else -1
    objects = module["printed"] + module["hardware"] + module["references"]
    released = {
        obj.Name for obj in objects if obj.Name.startswith(prefix + "InputMount")
    }
    removed = released | {prefix + "OutputGear20T"}
    moving = {
        obj.Name: world_shape(obj)
        for obj in objects
        if belongs_to_group(obj, cartridge) and obj.Name not in removed
    }
    fixed = {
        obj.Name: world_shape(obj)
        for obj in objects
        if not belongs_to_group(obj, cartridge) and obj.Name not in removed
    }
    waypoints = (
        (0, 0, 0),
        (sign * 40, 0, 0),
        (sign * 40, 0, 35),
    )
    rows = []
    for start, end in zip(waypoints, waypoints[1:]):
        for index in range(11):
            translation = tuple(a + (b - a) * index / 10 for a, b in zip(start, end))
            collisions = []
            for name, shape in moving.items():
                placed = translated_shape(shape, *translation)
                for other_name, obstacle in fixed.items():
                    volume = intersection_volume(placed, obstacle)
                    if volume > TOL:
                        collisions.append(
                            {
                                "moving": name,
                                "fixed": other_name,
                                "intersection_mm3": volume,
                            }
                        )
            rows.append(
                {
                    "translation_mm": list(translation),
                    "collisions": collisions,
                    "passed": not collisions,
                }
            )
    return {
        "cartridge": cartridge.Name,
        "released_fasteners": sorted(released),
        "removed_physical_parts": sorted(removed),
        "waypoints_mm": [list(point) for point in waypoints],
        "sampled_positions": rows,
        "scope": "Propulsion module removed from rail and leads disconnected. Release the output gear's included set screw and remove that gear along its separately checked axial path, then remove both input-cartridge bolt/nut pairs. Side translation and lift are sampled 22 times; not a continuous rigid-body or connected-harness proof.",
        "passed": len(released) == 4 and all(row["passed"] for row in rows),
    }


def continuous_path(shape, waypoints, obstacles):
    """Check every point of a piecewise translation, not just its waypoints."""
    rows = []
    for start, end in zip(waypoints, waypoints[1:]):
        placed = translated_shape(shape, *start)
        swept, method = translation_sweep(
            placed, tuple(b - a for a, b in zip(start, end))
        )
        collisions = {
            name: intersection_volume(swept, obstacle)
            for name, obstacle in obstacles.items()
        }
        rows.append(
            {
                "start_mm": list(start),
                "end_mm": list(end),
                "method": method,
                "intersection_mm3": collisions,
                "passed": all(v < TOL for v in collisions.values()),
            }
        )
    return {
        "obstacles": sorted(obstacles),
        "segments": rows,
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }


def horn_clamp_service_check(doc, module, prefix):
    """Certify ordered separation of both halves on the detached cartridge."""
    cartridge = doc.getObject(prefix + "InputCartridge")
    pod = doc.getObject(prefix + "Pod")
    original_tilt = float(pod.Tilt)
    original_clearance = float(cartridge.MeshClearance.Value)
    try:
        pod.Tilt = 0
        cartridge.MeshClearance = 0
        doc.recompute()
        shapes = {
            obj.Name: world_shape(obj)
            for obj in module["printed"] + module["hardware"] + module["references"]
            if belongs_to_group(obj, cartridge)
        }
    finally:
        pod.Tilt = original_tilt
        cartridge.MeshClearance = original_clearance
        doc.recompute()
    removed = {
        prefix + "HornClamp" + suffix
        for suffix in ("BladeBolt", "BladeNut", "ShaftBolt", "ShaftNut")
    }
    sign = 1 if prefix == "Port" else -1
    rows = []
    for suffix, waypoints in (
        ("Upper", ((0, 0, 0), (0, 0, 25))),
        ("Lower", ((0, 0, 0), (0, 0, -3), (sign * 35, 0, -3))),
    ):
        name = prefix + "HornClamp" + suffix
        obstacles = {
            key: shape for key, shape in shapes.items() if key not in removed | {name}
        }
        segments = [
            {
                "start_mm": list(start),
                "end_mm": list(end),
                **certify_translation_clearance(
                    translated_shape(shapes[name], *start),
                    tuple(b - a for a, b in zip(start, end)),
                    obstacles,
                ),
            }
            for start, end in zip(waypoints, waypoints[1:])
        ]
        rows.append(
            {
                "part": name,
                "removed_local_parts": sorted(removed),
                "segments": segments,
                "scope": "Detach the input cartridge using its checked gear-first path and set the input drive to neutral. Remove both coupling bolt/nut pairs using their checked paths. Remove the upper half before the lower half. Servo, bought horn, input shaft, bearings and driver gear stay installed. Continuous translation clearance is certified by distance bounds; this does not qualify clamp closure, torque or manipulation of flexible wiring.",
                "passed": all(segment["passed"] for segment in segments),
            }
        )
        removed.add(name)
    return rows


def rail_key_access_check(doc, module):
    """Check the complete module in both rail-key approaches and mesh extremes."""
    cartridges = [
        doc.getObject(prefix + "InputCartridge") for prefix in ("Port", "Starboard")
    ]
    original_clearances = [float(obj.MeshClearance.Value) for obj in cartridges]
    objects = module["printed"] + module["hardware"] + module["references"]
    screw_bounds = rail.set_screw_shape().optimalBoundingBox(False, False)
    rows = []
    try:
        for clearance in (0, 0.19):
            for cartridge in cartridges:
                cartridge.MeshClearance = clearance
            doc.recompute()
            shapes = {obj.Name: world_shape(obj) for obj in objects}
            for side in (1, -1):
                tool = Part.makeCylinder(
                    1.0,
                    65,
                    App.Vector(0, screw_bounds.YMax + 0.1, rail.CLAMP_Z),
                    App.Vector(0, 1, 0),
                )
                if side < 0:
                    tool = rail.half_turn(tool)
                tool.Placement = (
                    module["group"].getGlobalPlacement().multiply(tool.Placement)
                )
                collisions = [
                    {"part": name, "intersection_mm3": volume}
                    for name, shape in shapes.items()
                    if (volume := intersection_volume(tool, shape)) > TOL
                ]
                rows.append(
                    {
                        "approach_side_y": side,
                        "mesh_clearance_mm": clearance,
                        "tool_radius_mm": 1.0,
                        "tool_length_mm": 65.0,
                        "checked_objects": sorted(shapes),
                        "collisions": collisions,
                        "scope": "Oversized straight rail-key reservation against every installed local print, bought part and equipment reference at both mesh extremes. Actual key handle and neighboring rail modules are covered only by separate assembly/service checks.",
                        "passed": bool(shapes) and not collisions,
                    }
                )
    finally:
        for cartridge, original in zip(cartridges, original_clearances):
            cartridge.MeshClearance = original
        doc.recompute()
    return rows


def fastener_service_check(
    bolt, nut, obstacles, *, thread_diameter=2.0, nut_lateral_direction=None
):
    """Check an ordered threaded-fastener release and its head-tool approach."""
    bore = next(
        face.Surface
        for face in nut.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - thread_diameter / 2) < TOL
    )
    axis = bore.Axis
    if (
        nut.optimalBoundingBox(False, False).Center
        - bolt.optimalBoundingBox(False, False).Center
    ).dot(axis) < 0:
        axis = -axis
    thread_points = [
        vertex.Point.dot(axis)
        for face in bolt.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - thread_diameter / 2) < TOL
        for vertex in face.Vertexes
    ]
    thread_start, thread_end = min(thread_points), max(thread_points)
    nut_start = min(vertex.Point.dot(axis) for vertex in nut.Vertexes)
    nut_travel = thread_end - nut_start + 0.2
    bolt_travel = thread_end - thread_start + 0.2
    if nut_lateral_direction is None:
        nut_waypoints = [(0, 0, 0), tuple(axis * nut_travel)]
        sequence = "Disengage the nut beyond the thread tip, then withdraw the bolt."
    else:
        offset = axis * 0.2
        lateral = App.Vector(*nut_lateral_direction) * 25
        nut_waypoints = [(0, 0, 0), tuple(offset), tuple(offset + lateral)]
        sequence = "Hold the nut and withdraw the bolt first, then move the unthreaded nut 0.2 mm away from its seat and 25 mm sideways."
    nut_path = continuous_path(nut, nut_waypoints, obstacles)
    bolt_path = continuous_path(
        bolt, [(0, 0, 0), tuple(axis * -bolt_travel)], obstacles
    )
    head_projection = min(vertex.Point.dot(axis) for vertex in bolt.Vertexes)
    tool_origin = bore.Center + axis * (head_projection - 0.1 - bore.Center.dot(axis))
    tool_radius = 1.0 if thread_diameter == 2 else 1.6
    tool = Part.makeCylinder(tool_radius, 15, tool_origin, -axis)
    tool_hits = {
        name: volume
        for name, shape in obstacles.items()
        if (volume := intersection_volume(tool, shape)) > TOL
    }
    return {
        "nut_axial_removal": nut_path,
        "bolt_axial_withdrawal": bolt_path,
        "driver_approach_collisions": tool_hits,
        "tool_reserve_radius_mm": tool_radius,
        "nut_thread_disengagement_travel_mm": nut_travel,
        "bolt_withdrawal_travel_mm": bolt_travel,
        "service_order": sequence,
        "scope": "Modeled full thread/shank withdrawal includes 0.2 mm clearance. Named obstacles stay installed at neutral tilt. Cylindrical driver reservation: 1 mm radius for M2 hex socket, 1.6 mm for M1.6 slotted head. Handling the released nut, actual blade match and wrench handling remain unverified.",
        "passed": nut_path["passed"] and bolt_path["passed"] and not tool_hits,
    }


def validate(source=None):
    """Build the source mechanism and audit its actual mating and service shapes."""
    source = (
        Path(source).resolve() if source else OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")
    )
    doc = App.newDocument("PropulsionSourceAudit")
    try:
        module = propulsion.build_propulsion_module(doc)
        frame = world_shape(module["frame"])
        objects = module["printed"] + module["hardware"] + module["references"]
        physical = {obj.Name: world_shape(obj) for obj in objects}
        report = {
            "scope": "Source rigid-envelope, nominal fit and bench-service audit; OEM fit, friction retention and loaded operation remain unqualified.",
            "printed_parts": len(module["printed"]),
            "purchased_hardware": len(module["hardware"]),
            "metrics": module["metrics"],
        }
        for side, label in ((1, "positive"), (-1, "negative")):
            transform = (lambda shape: shape) if side > 0 else rail.half_turn
            report[label + "_seated_rail_overlap_mm3"] = intersection_volume(
                translated_shape(frame, y=side * rail.CLAMP_SHIFT_Y), rail.rail_shape()
            )
            for name, shape in (
                ("clamp_screw", rail.set_screw_shape()),
                ("clamp_nut", rail.nut_shape()),
            ):
                report[label + "_" + name + "_frame_overlap_mm3"] = intersection_volume(
                    frame, transform(shape)
                )
            key = Part.makeCylinder(
                0.9,
                110,
                App.Vector(0, rail.SHOE_WIDTH / 2 + 0.7, rail.CLAMP_Z),
                App.Vector(0, 1, 0),
            )
            report[label + "_clamp_driver_frame_overlap_mm3"] = intersection_volume(
                frame, transform(key)
            )
        report["continuous_nut_loading"] = [
            continuous_path(rail.nut_shape(), [(0, 0, 0), (20, 0, 0)], physical),
            continuous_path(
                rail.half_turn(rail.nut_shape()), [(0, 0, 0), (-20, 0, 0)], physical
            ),
        ]
        row_keys = (
            "drive_motion",
            "gear_mesh_alignment",
            "gear_rotation",
            "mesh_adjustment",
            "bearing_stacks",
            "output_stub_clearance",
            "shaft_service",
            "bearing_service",
            "gear_service",
            "motor_and_prop_insertion",
            "tilt_clearance",
            "input_cartridge_removal",
            "horn_clamp_service",
            "rail_key_access",
            "fastener_stacks",
            "fastener_service",
            "functional_wall_probes",
            "geometry",
        )
        report.update({key: [] for key in row_keys})
        report["rail_key_access"] = rail_key_access_check(doc, module)
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            pod = doc.getObject(prefix + "Pod")
            cartridge = doc.getObject(prefix + "InputCartridge")
            drive = doc.getObject(prefix + "InputDrive")
            report["drive_motion"].append(drive_motion_check(doc, prefix))
            report["mesh_adjustment"].append(mesh_adjustment_check(doc, prefix))
            report["gear_rotation"].append(gear_rotation_check(doc, prefix))
            report["gear_mesh_alignment"].append(
                {
                    "pod": prefix,
                    **gear_mesh_check(
                        physical[prefix + "DriverGear60T"],
                        physical[prefix + "OutputGear20T"],
                        module=0.5,
                        driver_teeth=60,
                        output_teeth=20,
                        minimum_face_overlap=3,
                    ),
                }
            )
            report["tilt_clearance"].append(tilt_clearance_check(doc, module, prefix))
            report["input_cartridge_removal"].append(
                input_cartridge_service_check(doc, module, prefix)
            )
            report["horn_clamp_service"].extend(
                horn_clamp_service_check(doc, module, prefix)
            )
            cartridge_names = {
                obj.Name for obj in objects if belongs_to_group(obj, cartridge)
            }
            drive_names = {obj.Name for obj in objects if belongs_to_group(obj, drive)}
            bearing_specs = []
            for side, suffix in ((-1, "Negative"), (1, "Positive")):
                shaft_name = prefix + "OutputShaft" + suffix
                report["output_stub_clearance"].append(
                    {
                        "shaft": shaft_name,
                        **output_stub_check(
                            physical[shaft_name],
                            physical[prefix + "Motor"],
                            pod.getGlobalPlacement().Base.y,
                        ),
                    }
                )
                excluded = {shaft_name, prefix + "OutputGear20T"}
                report["shaft_service"].append(
                    {
                        "shaft": shaft_name,
                        "excluded_physical_parts": sorted(excluded),
                        "scope": "Remove the output gear and release its supplied set screw, loosen the carrier split clamp, then withdraw this separate stub axially. Nominal unclamped bore; not clamp closure or grip proof.",
                        **continuous_path(
                            physical[shaft_name],
                            [(0, 0, 0), (0, side * 45, 0)],
                            {
                                name: shape
                                for name, shape in physical.items()
                                if name not in excluded
                            },
                        ),
                    }
                )
                bearing_specs.append(
                    (
                        prefix + "OutputBearing" + suffix,
                        shaft_name,
                        frame,
                        prefix + "OutputBearingCap" + suffix,
                        side,
                        False,
                    )
                )
            for suffix, direction in (("Inner", -sign), ("Outer", sign)):
                bearing_specs.append(
                    (
                        prefix + "InputBearing" + suffix,
                        prefix + "InputShaft",
                        physical[prefix + "InputSupport"],
                        prefix + "InputBearingCap" + suffix,
                        direction,
                        True,
                    )
                )
            for (
                bearing_name,
                shaft_name,
                seat,
                cap_name,
                direction,
                bench,
            ) in bearing_specs:
                report["bearing_stacks"].append(
                    {
                        "bearing": bearing_name,
                        **bearing_stack_check(
                            physical[bearing_name],
                            physical[shaft_name],
                            seat,
                            physical[cap_name],
                        ),
                    }
                )
                excluded = {
                    bearing_name,
                    shaft_name,
                    cap_name,
                    cap_name + "Bolt",
                    cap_name + "Nut",
                }
                if bench:
                    excluded |= drive_names | {prefix + "Servo"}
                else:
                    excluded.add(prefix + "OutputGear20T")
                obstacles = {
                    name: shape
                    for name, shape in physical.items()
                    if name not in excluded and (not bench or name in cartridge_names)
                }
                report["bearing_service"].append(
                    {
                        "bearing": bearing_name,
                        "excluded_physical_parts": sorted(excluded),
                        "scope": "Shaft and this outer-race cap/fasteners removed first. Remove the output gear before extracting an output bearing. Input-bearing operations occur on the detached cartridge after removing servo/horn and input drive attachments. All remaining local bench parts are obstacles; no bearing press-fit force is modeled.",
                        **continuous_path(
                            physical[bearing_name],
                            [(0, 0, 0), (0, direction * 35, 0)],
                            obstacles,
                        ),
                    }
                )
            excluded = {prefix + "InputShaft", prefix + "DriverGear60T"}
            report["shaft_service"].append(
                {
                    "shaft": prefix + "InputShaft",
                    "excluded_physical_parts": sorted(excluded),
                    "scope": "Detached input cartridge on bench; remove the driver gear and loosen the horn coupling's shaft clamp, then withdraw the shaft toward the former gear. Both bearing seats/caps, horn-clamp halves and servo remain installed; clamp opening and physical fit require a prototype.",
                    **continuous_path(
                        physical[prefix + "InputShaft"],
                        [(0, 0, 0), (0, sign * 40, 0)],
                        {
                            name: shape
                            for name, shape in physical.items()
                            if name in cartridge_names and name not in excluded
                        },
                    ),
                }
            )
            for suffix, direction, bench in (
                ("OutputGear20T", -sign, False),
                ("DriverGear60T", sign, True),
            ):
                name = prefix + suffix
                excluded = {name}
                report["gear_service"].append(
                    {
                        "gear": name,
                        "scope": "Release the included radial set screw before axial withdrawal. Driver gear is serviced on the detached input cartridge; all remaining local parts stay installed. Set-screw tip/length and driver access are unmodeled release gates.",
                        **continuous_path(
                            physical[name],
                            [(0, 0, 0), (0, direction * 35, 0)],
                            {
                                key: shape
                                for key, shape in physical.items()
                                if key not in excluded
                                and (not bench or key in cartridge_names)
                            },
                        ),
                    }
                )
            for suffix in ("Motor", "PropellerDisk"):
                name = prefix + suffix
                excluded = {name, prefix + "Shaft"}
                moving = physical[name]
                if suffix == "Motor":
                    moving = Part.makeCompound([moving, physical[prefix + "Shaft"]])
                    excluded.add(prefix + "PropellerDisk")
                report["motor_and_prop_insertion"].append(
                    {
                        "part": name,
                        "excluded_physical_parts": sorted(excluded),
                        "scope": "Bare motor/shaft withdraw together with propeller removed; propeller disk proxy excludes its shaft because its hub bore is unmodeled. OEM motor fastening remains unresolved.",
                        **continuous_path(
                            moving,
                            [(0, 0, 0), (30, 0, 0)],
                            {
                                key: shape
                                for key, shape in physical.items()
                                if key not in excluded
                            },
                        ),
                    }
                )
        clamp_parts = Part.makeCompound(
            [world_shape(obj) for obj in module["printed"]]
            + [physical[prefix + "Servo"] for prefix in ("Port", "Starboard")]
        )
        bolts = [
            obj
            for obj in module["hardware"]
            if obj.HardwareSKU in ("M2X8_SOCKET_CAP", "M1_6X8_CHEESE_HEAD")
        ]
        for bolt in bolts:
            nut_name = bolt.Name.removesuffix("Bolt") + "Nut"
            nut = physical[nut_name]
            thread_diameter = float(bolt.NominalThreadDiameter.Value)
            nut_height = 1.2 if thread_diameter == 2 else 1.3
            report["fastener_stacks"].append(
                {
                    "bolt": bolt.Name,
                    "nut": nut_name,
                    **clamp_fastener_check(
                        clamp_parts,
                        physical[bolt.Name],
                        nut,
                        thread_diameter=thread_diameter,
                        nut_height=nut_height,
                    ),
                }
            )
            service_excluded = {bolt.Name, nut_name}
            service_parts = set(physical)
            prerequisites = (
                "Other local propulsion parts stay installed at neutral tilt."
            )
            if "ServoEar" in bolt.Name:
                prefix = "Port" if bolt.Name.startswith("Port") else "Starboard"
                cartridge = doc.getObject(prefix + "InputCartridge")
                service_parts = {
                    obj.Name for obj in objects if belongs_to_group(obj, cartridge)
                }
                service_excluded |= {
                    prefix + "HornClamp" + suffix
                    for suffix in (
                        "Lower",
                        "Upper",
                        "BladeBolt",
                        "BladeNut",
                        "ShaftBolt",
                        "ShaftNut",
                    )
                }
                prerequisites = "Detach the input cartridge using its checked gear-first sequence. Remove both horn-clamp pairs and both halves using their separately checked service paths before releasing an OEM servo ear."
            report["fastener_service"].append(
                {
                    "bolt": bolt.Name,
                    "nut": nut_name,
                    "assembly_prerequisites": prerequisites,
                    "removed_local_parts": sorted(service_excluded),
                    **fastener_service_check(
                        physical[bolt.Name],
                        nut,
                        {
                            name: shape
                            for name, shape in physical.items()
                            if name in service_parts and name not in service_excluded
                        },
                        thread_diameter=thread_diameter,
                        nut_lateral_direction=(
                            (1 if nut.BoundBox.Center.x > 0 else -1, 0, 0)
                            if "InputMount" in bolt.Name
                            else None
                        ),
                    ),
                }
            )
        wall_probes = propulsion.manufacturing_wall_probes() + [
            (
                "guard_radial",
                "PortMotorCarrier",
                (12, 80, propulsion.PIVOT_Z + 22.79),
                (12, 80, propulsion.PIVOT_Z + 24.31),
                1.5,
            ),
        ]
        for feature, name, start, end, expected in wall_probes:
            section = physical[name].common(
                Part.makeLine(App.Vector(*start), App.Vector(*end))
            )
            thickness = sum(edge.Length for edge in section.Edges)
            report["functional_wall_probes"].append(
                {
                    "feature": feature,
                    "part": name,
                    "measured_wall_mm": thickness,
                    "expected_wall_mm": expected,
                    "passed": abs(thickness - expected) < TOL
                    and thickness >= 1.5 - TOL,
                }
            )
        for obj in module["printed"]:
            shape = print_shape(obj)
            mesh = MeshPart.meshFromShape(
                Shape=shape,
                LinearDeflection=0.03,
                AngularDeflection=0.08,
                Relative=False,
            )
            check = mesh_checks(shape, mesh)
            report["geometry"].append(
                {
                    "name": obj.Name,
                    **check,
                    "passed": check["valid_brep"]
                    and check["solid_count"] == 1
                    and check["watertight_mesh"]
                    and check["mesh_components"] == 1,
                }
            )
        report["all_bought_parts_excluded_from_prints"] = all(
            obj not in module["printed"] and not bool(getattr(obj, "PrintPart", False))
            for obj in module["hardware"]
        )
        expected_counts = {
            "drive_motion": 2,
            "gear_mesh_alignment": 2,
            "gear_rotation": 2,
            "mesh_adjustment": 2,
            "bearing_stacks": 8,
            "output_stub_clearance": 4,
            "shaft_service": 6,
            "bearing_service": 8,
            "gear_service": 4,
            "motor_and_prop_insertion": 4,
            "tilt_clearance": 2,
            "input_cartridge_removal": 2,
            "horn_clamp_service": 4,
            "rail_key_access": 4,
            "fastener_stacks": len(bolts),
            "fastener_service": len(bolts),
            "geometry": len(module["printed"]),
        }
        report["expected_evidence_counts"] = expected_counts
        report["overlap_failures"] = overlap_failures(report, TOL)
        report["passed"] = (
            not report["overlap_failures"]
            and report["all_bought_parts_excluded_from_prints"]
            and bool(bolts)
            and all(len(report[key]) == count for key, count in expected_counts.items())
            and all(
                row["passed"]
                for key in (*row_keys, "continuous_nut_loading")
                for row in report[key]
            )
        )
        target = source.parent / (source.stem + "_propulsion_validation.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {"local_propulsion_report": str(target), "passed": report["passed"]}
            ),
            flush=True,
        )
        return report
    finally:
        App.closeDocument(doc.Name)
