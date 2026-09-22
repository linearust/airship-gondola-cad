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
from gondola.contracts.drive import (
    FACE_WIDTH_MM,
    MODULE_MM,
    SELECTED_DRIVE,
    drive_for_document,
)
from gondola.parts import propulsion, rail
from gondola.print_export import geometry_comparison, mesh_checks, print_shape

from .evidence import overlap_failures
from .geometry import (
    belongs_to_group,
    intersection_volume,
    translation_sweep,
)
from .propulsion_evidence import PROPULSION_EVIDENCE_COUNTS, propulsion_evidence_check

TOL = 1e-5


def gear_mesh_check(
    driver,
    output,
    *,
    module,
    driver_teeth,
    output_teeth,
    minimum_face_overlap,
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
        "axis_position_tolerance_mm": TOL,
        "tooth_face_overlap_mm": face_overlap,
        "minimum_face_overlap_mm": minimum_face_overlap,
        "standard_involute_contact_ratio": contact_ratio,
        "minimum_contact_ratio": minimum_contact_ratio,
        "scope": "Saved gear position, actual tooth-band axial overlap and theoretical unshifted 20-degree involute contact ratio. Tooth approximation, backlash, tooth strength and operational servo fit remain unqualified.",
        "passed": abs(distance - expected_distance) <= TOL
        and face_overlap >= minimum_face_overlap - TOL
        and contact_ratio >= minimum_contact_ratio - TOL,
    }


def drive_motion_check(doc, prefix):
    """Exercise native bounded output and the selected opposite input rotation."""
    configuration = drive_for_document(doc)
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
            input_angle = -output_angle / configuration.ratio
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
        "gear_configuration": configuration.key,
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
    driver = doc.getObject(prefix + "DriverGear")
    output = doc.getObject(prefix + "OutputGear")
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


def fixed_servo_datum_check(doc, prefix):
    """Require the fixed servo axis, common frame and selected holder identities."""
    mount = doc.getObject(prefix + "ServoMount")
    if mount is None:
        return {"passed": False, "error": "Missing fixed servo mount datum"}
    configuration = drive_for_document(doc)
    sign = 1 if prefix == "Port" else -1
    expected = App.Vector(sign * configuration.input_x_mm, 0, configuration.input_z_mm)
    error = (mount.Placement.Base - expected).Length
    expressions = [
        str(path)
        for path, _ in mount.ExpressionEngine
        if str(path).lstrip(".").startswith("Placement")
    ]
    frame_sku = getattr(doc.PropulsionFixedFrame, "PrintSKU", None)
    holder_sku = getattr(doc.getObject(prefix + "ServoHolder"), "PrintSKU", None)
    return {
        "pod": prefix,
        "gear_configuration": configuration.key,
        "expected_input_axis_mm": list(expected),
        "actual_input_axis_mm": list(mount.Placement.Base),
        "datum_position_error_mm": error,
        "placement_expressions": expressions,
        "expected_frame_sku": configuration.frame_sku,
        "actual_frame_sku": frame_sku,
        "expected_holder_sku": configuration.servo_holder_sku,
        "actual_holder_sku": holder_sku,
        "scope": "Fixed servo datum on a replaceable holder against the common output-bearing frame; no adjustable mount. Physical printed fit and mesh remain unqualified.",
        "passed": error < TOL
        and mount.Placement.Rotation.isSame(App.Rotation(), 1e-7)
        and not expressions
        and "MeshClearance" not in mount.PropertiesList
        and frame_sku == configuration.frame_sku
        and holder_sku == configuration.servo_holder_sku,
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


def _planar_contact_area(first, second):
    area = 0.0
    for face in first.Faces:
        if type(face.Surface).__name__ != "Plane":
            continue
        normal = face.normalAt(0, 0)
        for seat in second.Faces:
            if type(seat.Surface).__name__ != "Plane":
                continue
            if (
                abs(abs(normal.dot(seat.normalAt(0, 0))) - 1) < 1e-7
                and abs((face.CenterOfMass - seat.CenterOfMass).dot(normal)) < 1e-7
            ):
                area += face.common(seat).Area
    return area


def clamp_fastener_check(clamp, bolt, nut, *, thread_diameter=2.0, nut_height=1.2):
    """Require seated bolt/nut bearing faces and a complete nominal metric nut core.

    This checks assembly geometry only. A tightened split clamp's shaft torque
    capacity, creep and axial grip are not established by a rigid CAD model.
    """
    contacts = []
    for name, fastener in (("Bolt", bolt), ("Nut", nut)):
        area = _planar_contact_area(fastener, clamp)
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


def direct_adapter_fit_check(doc, prefix):
    """Check the purchased bore, full spigot engagement and bought-horn capture."""
    from gondola.parts import servo_coupling as coupling

    mount = doc.getObject(prefix + "ServoMount")
    sign = 1 if prefix == "Port" else -1
    parts = {
        suffix: world_shape(doc.getObject(prefix + suffix))
        for suffix in (
            "DriverGear",
            "ServoHorn",
            "HornGearAdapter",
            "HornGearRetainer",
            "HornGearClampBolt",
            "HornGearClampNut",
        )
    }
    axis = App.Vector(0, sign, 0)
    origin = App.Vector(0, sign * propulsion.GEAR_HUB_START_Y, 0)
    bore = Part.makeCylinder(3.5, 8, origin, axis)
    ring = Part.makeCylinder(3.8, 8, origin, axis).cut(bore)
    spigot = Part.makeCylinder(
        coupling.SPIGOT_DIAMETER / 2, coupling.SPIGOT_LENGTH, origin, axis
    ).cut(
        Part.makeCylinder(
            coupling.SPIGOT_BORE_DIAMETER / 2, coupling.SPIGOT_LENGTH, origin, axis
        )
    )
    for shape in (bore, ring, spigot):
        shape.Placement = mount.getGlobalPlacement().multiply(shape.Placement)
    bore_intrusion = intersection_volume(bore, parts["DriverGear"])
    missing_hub = abs(ring.cut(parts["DriverGear"]).Volume)
    missing_spigot = abs(spigot.cut(parts["HornGearAdapter"]).Volume)
    rows = []
    names = list(parts)
    for index, name in enumerate(names):
        for other in names[index + 1 :]:
            rows.append(
                {
                    "parts": [prefix + name, prefix + other],
                    "intersection_mm3": intersection_volume(parts[name], parts[other]),
                }
            )
    capture = {
        name: _planar_contact_area(parts["ServoHorn"], parts[name])
        for name in ("HornGearAdapter", "HornGearRetainer")
    }
    return {
        "pod": prefix,
        "gear_bore_mm": 7,
        "gear_bore_intrusion_mm3": bore_intrusion,
        "missing_gear_hub_ring_mm3": missing_hub,
        "missing_spigot_mm3": missing_spigot,
        "internal_pairs": rows,
        "nominal_horn_contact_area_mm2": capture,
        "scope": "Neutral nominal geometry: 7mm bought bore, complete hollow spigot engagement, no internal part intersections and horn contact on both printed capture faces. Set-screw preload, finishing tolerance, concentricity under load and servo radial-load capacity remain physical checks.",
        "passed": bore_intrusion < TOL
        and missing_hub < TOL
        and missing_spigot < TOL
        and all(row["intersection_mm3"] < TOL for row in rows)
        and all(area > 1 for area in capture.values()),
    }


def servo_mount_check(doc, prefix):
    """Require seated stock ear fasteners and a collision-free removable holder."""
    frame = world_shape(doc.PropulsionFixedFrame)
    holder = world_shape(doc.getObject(prefix + "ServoHolder"))
    servo = world_shape(doc.getObject(prefix + "Servo"))
    frame_overlap = intersection_volume(frame, servo)
    holder_overlap = intersection_volume(holder, servo)
    clamps = Part.makeCompound([holder, servo])
    rows = []
    for suffix in ("Lower", "Upper"):
        name = prefix + "ServoEar" + suffix
        rows.append(
            {
                "bolt": name + "Bolt",
                **clamp_fastener_check(
                    clamps,
                    world_shape(doc.getObject(name + "Bolt")),
                    world_shape(doc.getObject(name + "Nut")),
                    thread_diameter=1.6,
                    nut_height=1.3,
                ),
            }
        )
    return {
        "pod": prefix,
        "servo_frame_intersection_mm3": frame_overlap,
        "servo_holder_intersection_mm3": holder_overlap,
        "cases": rows,
        "scope": "The two published X06 ears bear on the removable holder using M1.6 fasteners. The separate M2 holder joint retains this complete assembly. Nominal rigid contact is not proof of clamp torque or actual case fit.",
        "passed": frame_overlap < TOL
        and holder_overlap < TOL
        and all(row["passed"] for row in rows),
    }


def holder_mount_check(doc, prefix):
    """Check a fixed face/ledge/end-stop joint and both seated M2 fasteners."""
    holder_object = doc.getObject(prefix + "ServoHolder")
    if holder_object is None:
        return {"pod": prefix, "passed": False, "error": "Missing servo holder"}
    frame = world_shape(doc.PropulsionFixedFrame)
    holder = world_shape(holder_object)
    overlap = intersection_volume(frame, holder)
    contact_area = _planar_contact_area(frame, holder)
    sign = 1 if prefix == "Port" else -1
    rotation = doc.MainPropulsionModule.getGlobalPlacement().Rotation
    registers = []
    for feature, local_delta in (
        ("mating_face", (0, sign * 0.05, 0)),
        ("support_ledge", (0, 0, -0.05)),
        ("end_stop", (-sign * 0.05, 0, 0)),
    ):
        delta = rotation.multVec(App.Vector(*local_delta))
        blocking = intersection_volume(translated_shape(holder, *delta), frame)
        registers.append(
            {
                "feature": feature,
                "blocking_intersection_mm3": blocking,
                "passed": blocking > TOL,
            }
        )
    clamps = Part.makeCompound([frame, holder])
    cases = []
    for suffix in ("Negative", "Positive"):
        name = prefix + "HolderMount" + suffix
        cases.append(
            {
                "bolt": name + "Bolt",
                **clamp_fastener_check(
                    clamps,
                    world_shape(doc.getObject(name + "Bolt")),
                    world_shape(doc.getObject(name + "Nut")),
                ),
            }
        )
    return {
        "pod": prefix,
        "holder": holder_object.Name,
        "holder_frame_intersection_mm3": overlap,
        "nominal_mating_contact_area_mm2": contact_area,
        "registration_faces": registers,
        "cases": cases,
        "scope": "Nominal broad mating face, support ledge and one lateral stop with two seated M2 fasteners. Open opposite sides avoid a closed precision pocket. Contact and directional blocking do not establish printed tolerance, clamp stiffness or repeatability.",
        "passed": overlap < TOL
        and contact_area > 1
        and all(row["passed"] for row in registers + cases),
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
    rows = []
    try:
        for index in range(49):
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
                    "minimum_z_mm": minimum_z,
                    "collisions": collisions,
                    "passed": not collisions and minimum_z >= -TOL,
                }
            )
    finally:
        pod.Tilt = original_tilt
        doc.recompute()
    return {
        "pod": prefix,
        "moving_objects": [obj.Name for obj in moving],
        "fixed_objects": [obj.Name for obj in fixed],
        "relative_motion_pairs_checked_per_pose": len(output_moving)
        * len(input_moving),
        "poses": rows,
        "scope": "49 sampled coupled-output/input positions at the fixed nominal center distance, including both bounded rotation endpoints. Checks live fixed obstacles and every output-pod/input-drive pair, including gear teeth; no gear-pair exclusion. Not a continuous rigid-body or connected-wire sweep proof.",
        "passed": bool(moving) and all(row["passed"] for row in rows),
    }


def holder_mount_fastener_names(prefix):
    return {
        prefix + "HolderMount" + side + kind
        for side in ("Negative", "Positive")
        for kind in ("Bolt", "Nut")
    }


def driver_lateral_service_check(shape, start, end, obstacles, spec, sign):
    """Bound the toothed disk and smaller hub separately during lateral release.

    A single bounding box fills the empty corners around the large gear and
    falsely hits the retained small gear. These exact swept cylinders enclose
    the complete bought gear; containment of the actual CAD is checked first.
    """
    axis = App.Vector(0, sign, 0)
    x, z = sign * spec.input_x_mm, spec.input_z_mm
    reference, swept = [], []
    for y, height, radius in (
        (propulsion.GEAR_HUB_START_Y, 5, spec.driver.hub_diameter_mm / 2),
        (
            propulsion.GEAR_FACE_START_Y,
            FACE_WIDTH_MM,
            MODULE_MM * (spec.driver.teeth + 2) / 2,
        ),
    ):
        origin = App.Vector(x, sign * y, z)
        cylinder = Part.makeCylinder(radius, height, origin, axis)
        reference.append(cylinder)
        first = translated_shape(cylinder, *start)
        last = translated_shape(cylinder, *end)
        bridge = Part.makeBox(
            abs(end[0] - start[0]),
            height,
            2 * radius,
            App.Vector(
                x + min(start[0], end[0]),
                min(sign * y, sign * (y + height)) + start[1],
                z - radius + start[2],
            ),
        )
        swept.append(first.fuse(last).fuse(bridge))
    envelope = reference[0].fuse(reference[1])
    outside = abs(shape.cut(envelope).Volume)
    sweep = swept[0].fuse(swept[1])
    hits = {
        name: intersection_volume(sweep, other) for name, other in obstacles.items()
    }
    axial_invariance = start[1:] == end[1:] and abs(end[0] - start[0]) > TOL
    return {
        "obstacles": sorted(obstacles),
        "segments": [
            {
                "start_mm": list(start),
                "end_mm": list(end),
                "method": "continuous tooth-disk and hub swept-cylinder union",
                "intersection_mm3": hits,
                "passed": all(value < TOL for value in hits.values()),
            }
        ],
        "gear_outside_reference_envelope_mm3": outside,
        "passed": axial_invariance
        and outside < TOL
        and all(value < TOL for value in hits.values()),
    }


def servo_lateral_service_check(shape, start, end, obstacles):
    """Partition the actual servo at its axial steps before continuous sweeping.

    The ear tips do not extend along the whole case depth. Sweeping one box
    around case, ears and spline fills those absent corners. Axial slabs from
    the live shape preserve them, and a coverage check prevents missing solid.
    """
    bounds = shape.BoundBox
    planes = sorted({round(vertex.Point.y, 9) for vertex in shape.Vertexes})
    pieces, segments = [], []
    for low, high in zip(planes, planes[1:]):
        if high - low < TOL:
            continue
        slab = shape.common(
            Part.makeBox(
                bounds.XLength + 2,
                high - low,
                bounds.ZLength + 2,
                App.Vector(bounds.XMin - 1, low, bounds.ZMin - 1),
            )
        )
        if abs(slab.Volume) < TOL:
            continue
        pieces.append(slab)
        result = continuous_path(slab, [start, end], obstacles)
        segments.extend(
            {"source_axial_slab_mm": [low, high], **row} for row in result["segments"]
        )
    covered = Part.makeCompound(pieces)
    missing = abs(shape.cut(covered).Volume) if pieces else abs(shape.Volume)
    return {
        "obstacles": sorted(obstacles),
        "segments": segments,
        "uncovered_servo_volume_mm3": missing,
        "passed": bool(segments)
        and missing < TOL
        and all(row["passed"] for row in segments),
    }


def servo_assembly_service_check(doc, module, prefix):
    """Remove the whole servo/driver holder while retaining the output assembly."""
    mount = doc.getObject(prefix + "ServoMount")
    sign = 1 if prefix == "Port" else -1
    objects = module["printed"] + module["hardware"] + module["references"]
    released = holder_mount_fastener_names(prefix)
    moving = {
        obj.Name: world_shape(obj)
        for obj in objects
        if belongs_to_group(obj, mount) and obj.Name not in released
    }
    fixed = {
        obj.Name: world_shape(obj)
        for obj in objects
        if not belongs_to_group(obj, mount) and obj.Name not in released
    }
    # Sweep in the module frame: the conservative fallback uses axis-aligned
    # bounds and must not grow merely because the whole gondola is rotated.
    placement = module["group"].getGlobalPlacement()
    inverse = placement.inverse()
    for shape in (*moving.values(), *fixed.values()):
        shape.Placement = inverse.multiply(shape.Placement)
    inward = -sign * propulsion.HOLDER_RELEASE_INBOARD
    outward = sign * propulsion.HOLDER_RELEASE_OUTWARD
    waypoints = [(0, 0, 0), (0, inward, 0), (outward, inward, 0)]
    rows = []
    for name, shape in moving.items():
        if name == prefix + "DriverGear":
            axial = continuous_path(shape, waypoints[:2], fixed)
            lateral = driver_lateral_service_check(
                shape,
                waypoints[1],
                waypoints[2],
                fixed,
                drive_for_document(doc),
                sign,
            )
            result = {
                "obstacles": axial["obstacles"],
                "segments": axial["segments"] + lateral["segments"],
                "gear_outside_reference_envelope_mm3": lateral[
                    "gear_outside_reference_envelope_mm3"
                ],
                "passed": axial["passed"] and lateral["passed"],
            }
        elif name == prefix + "Servo":
            axial = continuous_path(shape, waypoints[:2], fixed)
            lateral = servo_lateral_service_check(
                shape, waypoints[1], waypoints[2], fixed
            )
            result = {
                "obstacles": axial["obstacles"],
                "segments": axial["segments"] + lateral["segments"],
                "uncovered_servo_volume_mm3": lateral["uncovered_servo_volume_mm3"],
                "passed": axial["passed"] and lateral["passed"],
            }
        else:
            result = continuous_path(shape, waypoints, fixed)
        rows.append({"part": name, **result})
    return {
        "servo_mount": mount.Name,
        "released_fasteners": sorted(released),
        "retained_output_gear": prefix + "OutputGear",
        "moving_parts": sorted(moving),
        "coordinate_frame": "propulsion module",
        "waypoints_mm": [list(point) for point in waypoints],
        "world_displacements_mm": [
            list(placement.Rotation.multVec(App.Vector(*point))) for point in waypoints
        ],
        "part_paths": rows,
        "scope": "Disconnect leads at neutral and remove the two holder M2 bolt/nut pairs. Move the complete holder/servo/horn/driver assembly 4mm axially inward to disengage the 3mm gear faces, then 40mm sideways outward. Servo-ear fasteners, output gear, shafts, bearings and motor remain assembled. Continuous translation envelopes include all retained local obstacles; flexible leads and handling tools are unmodeled.",
        "passed": bool(moving) and all(row["passed"] for row in rows),
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


def horn_adapter_service_check(doc, module, prefix):
    """Separate the adapter on the removed servo/holder assembly, in declared order."""
    mount = doc.getObject(prefix + "ServoMount")
    shapes = {
        obj.Name: world_shape(obj)
        for obj in module["printed"] + module["hardware"] + module["references"]
        if belongs_to_group(obj, mount)
        and obj.Name not in holder_mount_fastener_names(prefix)
    }
    sign = 1 if prefix == "Port" else -1
    removed = {
        prefix + "DriverGear",
        prefix + "HornGearClampBolt",
        prefix + "HornGearClampNut",
    }
    rows = []
    for suffix, delta in (
        ("HornGearAdapter", (0, sign * 25, 0)),
        ("HornGearRetainer", (sign * 30, 0, 0)),
    ):
        name = prefix + suffix
        obstacles = {
            key: shape for key, shape in shapes.items() if key not in removed | {name}
        }
        result = continuous_path(shapes[name], [(0, 0, 0), delta], obstacles)
        rows.append(
            {
                "part": name,
                "removed_local_parts": sorted(removed),
                "translation_mm": list(delta),
                **result,
                "scope": "After checked whole-holder removal, remove the driver gear axially and release the single adapter fastener. Pull the front adapter forward off the installed horn, then slide its rear retainer sideways. The stock horn and servo stay together; remove the adapter before servicing the unmodeled OEM retaining screw.",
            }
        )
        removed.add(name)
    return rows


def rail_key_access_check(doc, module):
    """Check the complete fixed module in both rail-key approaches."""
    objects = module["printed"] + module["hardware"] + module["references"]
    screw_bounds = rail.set_screw_shape().optimalBoundingBox(False, False)
    shapes = {obj.Name: world_shape(obj) for obj in objects}
    rows = []
    for side in (1, -1):
        tool = Part.makeCylinder(
            1.0,
            65,
            App.Vector(0, screw_bounds.YMax + 0.1, rail.CLAMP_Z),
            App.Vector(0, 1, 0),
        )
        if side < 0:
            tool = rail.half_turn(tool)
        tool.Placement = module["group"].getGlobalPlacement().multiply(tool.Placement)
        collisions = [
            {"part": name, "intersection_mm3": volume}
            for name, shape in shapes.items()
            if (volume := intersection_volume(tool, shape)) > TOL
        ]
        rows.append(
            {
                "approach_side_y": side,
                "tool_radius_mm": 1.0,
                "tool_length_mm": 65.0,
                "checked_objects": sorted(shapes),
                "collisions": collisions,
                "scope": "Oversized straight rail-key reservation against every installed local print, bought part and equipment reference. Actual key handle and neighboring rail modules are covered only by separate assembly/service checks.",
                "passed": bool(shapes) and not collisions,
            }
        )
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


def _service_obstacles(physical, excluded, *, members=None):
    """Retain installed obstacles within the declared whole-module or bench scope."""
    return {
        name: shape
        for name, shape in physical.items()
        if name not in excluded and (members is None or name in members)
    }


def _record_rail_fit_checks(report, frame, physical):
    """Audit both seated rail interfaces and continuous nut loading."""
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


def _record_drive_motion_checks(report, doc, module, physical, prefix):
    """Keep native motion, meshing and coupled service evidence together."""
    configuration = drive_for_document(doc)
    report["drive_motion"].append(drive_motion_check(doc, prefix))
    report["fixed_servo_datum"].append(fixed_servo_datum_check(doc, prefix))
    report["servo_mounts"].append(servo_mount_check(doc, prefix))
    report["holder_mounts"].append(holder_mount_check(doc, prefix))
    report["direct_adapter_fit"].append(direct_adapter_fit_check(doc, prefix))
    report["gear_rotation"].append(gear_rotation_check(doc, prefix))
    report["gear_mesh_alignment"].append(
        {
            "pod": prefix,
            **gear_mesh_check(
                physical[prefix + "DriverGear"],
                physical[prefix + "OutputGear"],
                module=MODULE_MM,
                driver_teeth=configuration.driver.teeth,
                output_teeth=configuration.output.teeth,
                minimum_face_overlap=FACE_WIDTH_MM,
            ),
        }
    )
    report["tilt_clearance"].append(tilt_clearance_check(doc, module, prefix))
    report["servo_assembly_removal"].append(
        servo_assembly_service_check(doc, module, prefix)
    )
    report["horn_adapter_service"].extend(
        horn_adapter_service_check(doc, module, prefix)
    )


def _record_output_stub_checks(report, prefix, pod, physical, frame):
    """Check the two separate output stubs and describe their bearing stacks."""
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
        excluded = {shaft_name, prefix + "OutputGear"}
        report["shaft_service"].append(
            {
                "shaft": shaft_name,
                "excluded_physical_parts": sorted(excluded),
                "scope": "Remove the output gear and release its supplied set screw, loosen the carrier split clamp, then withdraw this separate stub axially. Nominal unclamped bore; not clamp closure or grip proof.",
                **continuous_path(
                    physical[shaft_name],
                    [(0, 0, 0), (0, side * 45, 0)],
                    _service_obstacles(physical, excluded),
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
            )
        )
    return bearing_specs


def _record_bearing_checks(report, prefix, physical, bearing_specs):
    """Check the four retained output bearings and their extraction paths."""
    for bearing_name, shaft_name, seat, cap_name, direction in bearing_specs:
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
            prefix + "OutputGear",
        }
        report["bearing_service"].append(
            {
                "bearing": bearing_name,
                "excluded_physical_parts": sorted(excluded),
                "scope": "Remove the output gear, this stub shaft and its outer-race cap/fasteners before extracting the bearing. All other parts stay installed; bearing fit forces remain unmodeled.",
                **continuous_path(
                    physical[bearing_name],
                    [(0, 0, 0), (0, direction * 35, 0)],
                    _service_obstacles(physical, excluded),
                ),
            }
        )


def _record_drive_service_checks(report, prefix, sign, physical, servo_names):
    """Audit gears on their declared installed or removed-servo assembly."""
    for suffix, direction, bench in (
        ("OutputGear", -sign, False),
        ("DriverGear", sign, True),
    ):
        name = prefix + suffix
        excluded = {name}
        report["gear_service"].append(
            {
                "gear": name,
                "scope": "Release the included radial set screw before axial withdrawal. Driver gear is serviced on the removed servo/holder assembly; all remaining local parts stay installed. Set-screw tip/length and driver access are unmodeled release gates.",
                **continuous_path(
                    physical[name],
                    [(0, 0, 0), (0, direction * 35, 0)],
                    _service_obstacles(
                        physical, excluded, members=servo_names if bench else None
                    ),
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
                    _service_obstacles(physical, excluded),
                ),
            }
        )


def _record_drive_checks(report, doc, module, objects, physical, frame, prefix, sign):
    """Collect direct input-drive and separately supported output evidence."""
    pod = doc.getObject(prefix + "Pod")
    mount = doc.getObject(prefix + "ServoMount")
    _record_drive_motion_checks(report, doc, module, physical, prefix)
    servo_names = {
        obj.Name for obj in objects if belongs_to_group(obj, mount)
    } - holder_mount_fastener_names(prefix)
    bearing_specs = _record_output_stub_checks(report, prefix, pod, physical, frame)
    _record_bearing_checks(report, prefix, physical, bearing_specs)
    _record_drive_service_checks(report, prefix, sign, physical, servo_names)


def _record_fastener_checks(report, doc, module, objects, physical):
    """Verify installed fastener seats, engagement and ordered access routes."""
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
        dependencies = []
        service_group = module["group"].Name
        prerequisites = "Other local propulsion parts stay installed at neutral tilt."
        if "HornGearClamp" in bolt.Name:
            prefix = "Port" if bolt.Name.startswith("Port") else "Starboard"
            mount = doc.getObject(prefix + "ServoMount")
            service_parts = {
                obj.Name for obj in objects if belongs_to_group(obj, mount)
            }
            service_group = mount.Name
            service_excluded.add(prefix + "DriverGear")
            prerequisites = "Remove the complete servo assembly via its checked side path, then remove the driver gear axially before releasing the adapter bolt/nut."
            for key, field, name in (
                ("servo_assembly_removal", "servo_mount", mount.Name),
                ("gear_service", "gear", prefix + "DriverGear"),
            ):
                matches = [row for row in report[key] if row.get(field) == name]
                dependencies.append(
                    {
                        "check": key,
                        "object": name,
                        "passed": len(matches) == 1 and matches[0]["passed"],
                    }
                )
        service = fastener_service_check(
            physical[bolt.Name],
            nut,
            _service_obstacles(physical, service_excluded, members=service_parts),
            thread_diameter=thread_diameter,
        )
        report["fastener_service"].append(
            {
                "bolt": bolt.Name,
                "nut": nut_name,
                "assembly_prerequisites": prerequisites,
                "service_group": service_group,
                "service_dependencies": dependencies,
                "retained_service_parts": sorted(service_parts - service_excluded),
                "removed_local_parts": sorted(service_excluded),
                **service,
                "passed": service["passed"]
                and all(row["passed"] for row in dependencies),
            }
        )


def _record_print_checks(report, module, physical):
    """Measure functional walls and check every printable solid and mesh."""
    wall_probes = propulsion.manufacturing_wall_probes(
        drive=drive_for_document(module["group"].Document)
    ) + [
        (
            "guard_radial",
            "PortMotorCarrier",
            (12, 80, propulsion.PIVOT_Z + 22.79),
            (12, 80, propulsion.PIVOT_Z + 24.31),
            1.5,
        ),
    ]
    from gondola.parts import servo_coupling as coupling

    spec = drive_for_document(module["group"].Document)
    x, z = spec.input_x_mm, spec.input_z_mm
    wall_probes.extend(
        [
            (
                "direct_spigot_radial_wall",
                "PortHornGearAdapter",
                (x + coupling.SPIGOT_BORE_DIAMETER / 2 - 0.01, 42, z),
                (x + coupling.SPIGOT_DIAMETER / 2 + 0.01, 42, z),
                (coupling.SPIGOT_DIAMETER - coupling.SPIGOT_BORE_DIAMETER) / 2,
            ),
            (
                "horn_rear_retainer",
                "PortHornGearRetainer",
                (x + 8, coupling.HORN_BOTTOM_Y + coupling.RETAINER_BACK_Y - 0.01, z),
                (
                    x + 8,
                    coupling.HORN_BOTTOM_Y
                    + coupling.RETAINER_BACK_Y
                    + coupling.RETAINER_THICKNESS
                    + 0.01,
                    z,
                ),
                coupling.RETAINER_THICKNESS,
            ),
        ]
    )
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
                "passed": abs(thickness - expected) < TOL and thickness >= 1.5 - TOL,
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
                and check["single_closed_solid"]
                and check["watertight_mesh"]
                and check["mesh_components"] == 1,
            }
        )


def _complete_report(report, module):
    """Require every evidence row and its independently declared count."""
    report["all_bought_parts_excluded_from_prints"] = all(
        obj not in module["printed"] and not bool(getattr(obj, "PrintPart", False))
        for obj in module["hardware"]
    )
    evidence = propulsion_evidence_check(report)
    report["expected_evidence_counts"] = dict(PROPULSION_EVIDENCE_COUNTS)
    report["required_evidence_inventory"] = evidence["inventory"]
    report["evidence_row_failures"] = evidence["row_failures"]
    report["overlap_failures"] = overlap_failures(report, TOL)
    report["passed"] = (
        not report["overlap_failures"]
        and report["all_bought_parts_excluded_from_prints"]
        and evidence["passed"]
    )


def _write_report(report, source):
    """Persist the validation JSON and emit its completion message."""
    target = source.parent / (source.stem + "_propulsion_validation.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {"local_propulsion_report": str(target), "passed": report["passed"]}
        ),
        flush=True,
    )


def validate(source=None, *, drive=SELECTED_DRIVE):
    """Build the source mechanism and audit its actual mating and service shapes."""
    source = (
        Path(source).resolve() if source else OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")
    )
    doc = App.newDocument("PropulsionSourceAudit")
    try:
        module = propulsion.build_propulsion_module(doc, drive=drive)
        frame = world_shape(module["frame"])
        objects = module["printed"] + module["hardware"] + module["references"]
        physical = {obj.Name: world_shape(obj) for obj in objects}
        report = {
            "gear_configuration": drive_for_document(doc).key,
            "scope": "Source rigid-envelope, nominal fit and bench-service audit; OEM fit, friction retention and loaded operation remain unqualified.",
            "printed_parts": len(module["printed"]),
            "purchased_hardware": len(module["hardware"]),
            "metrics": module["metrics"],
        }
        report.update({key: [] for key in PROPULSION_EVIDENCE_COUNTS})
        _record_rail_fit_checks(report, frame, physical)
        report["rail_key_access"] = rail_key_access_check(doc, module)
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            _record_drive_checks(
                report, doc, module, objects, physical, frame, prefix, sign
            )
        _record_fastener_checks(report, doc, module, objects, physical)
        _record_print_checks(report, module, physical)
        _complete_report(report, module)
        _write_report(report, source)
        return report
    finally:
        App.closeDocument(doc.Name)
