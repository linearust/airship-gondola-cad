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
from .motion_clearance import carrier_axial_travel, carrier_metal_clearance_check
from .propulsion_evidence import PROPULSION_EVIDENCE_COUNTS, propulsion_evidence_check
from .propulsion_service import (
    continuous_path,
    driver_lateral_service_check,
    fastener_service_check,
    module_service_shapes,
    retained_obstacles,
)
from .rail_access import rail_key_service_check
from .relative_motion import relative_motion_check
from .servo_module import bridge_joint_check, servo_module_service_check

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
    output_axial_travel=(0.0, 0.0),
    minimum_face_overlap_under_travel=None,
):
    """Measure tooth-face engagement independently of the protruding gear hubs.

    The assemblies use parallel Y axes. An annular section near each pitch
    circle isolates actual tooth material; a hub overlapping another hub must
    not pass as an engaged gear pair. This is a positioning check, not tooth
    strength, backlash or loaded mesh qualification. The independent contact
    ratio screen uses the standard unshifted 20-degree involute dimensions.
    """
    travel = tuple(float(value) for value in output_axial_travel)
    if (
        len(travel) != 2
        or not all(math.isfinite(value) for value in travel)
        or not travel[0] <= 0 <= travel[1]
    ):
        raise ValueError("Axial travel must be finite negative/positive bounds.")
    if minimum_face_overlap_under_travel is None:
        minimum_face_overlap_under_travel = minimum_face_overlap
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
    # Interval overlap is concave in axial translation. Its minimum over the
    # complete permitted travel therefore occurs at one of the two endpoints.
    travel_overlaps = [
        min(first["tooth_face_y_mm"][1], second["tooth_face_y_mm"][1] + shift)
        - max(first["tooth_face_y_mm"][0], second["tooth_face_y_mm"][0] + shift)
        for shift in travel
    ]
    minimum_travel_overlap = min(travel_overlaps)
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
        "output_axial_travel_mm": list(travel),
        "tooth_face_overlap_at_travel_limits_mm": travel_overlaps,
        "minimum_tooth_face_overlap_under_travel_mm": minimum_travel_overlap,
        "required_face_overlap_under_travel_mm": minimum_face_overlap_under_travel,
        "standard_involute_contact_ratio": contact_ratio,
        "minimum_contact_ratio": minimum_contact_ratio,
        "scope": "Saved gear position, actual tooth-band axial overlap throughout the declared output axial travel, and theoretical unshifted 20-degree involute contact ratio. The overlap requirement is a geometric design reserve, not a tooth-strength rating. Tooth approximation, backlash, tooth strength and operational servo fit remain unqualified.",
        "passed": abs(distance - expected_distance) <= TOL
        and face_overlap >= minimum_face_overlap - TOL
        and minimum_travel_overlap >= minimum_face_overlap_under_travel - TOL
        and contact_ratio >= minimum_contact_ratio - TOL,
    }


def gear_engagement_check(doc, prefix, axial_stops=None):
    """Bind actual installed gear faces to the actual output travel stops."""
    configuration = drive_for_document(doc)
    stops = (
        axial_stops if axial_stops is not None else carrier_axial_travel(doc, prefix)
    )
    row = {"pod": prefix, "axial_stops": stops}
    gears = [doc.getObject(prefix + suffix) for suffix in ("DriverGear", "OutputGear")]
    if not stops["passed"] or any(obj is None for obj in gears):
        return {
            **row,
            "passed": False,
            "error": "Missing gears or unproven axial stops",
        }
    inverse = doc.MainPropulsionModule.getGlobalPlacement().inverse()
    shapes = []
    for obj in gears:
        shape = world_shape(obj)
        shape.Placement = inverse.multiply(shape.Placement)
        shapes.append(shape)
    return {
        **row,
        **gear_mesh_check(
            *shapes,
            module=MODULE_MM,
            driver_teeth=configuration.driver.teeth,
            output_teeth=configuration.output.teeth,
            minimum_face_overlap=FACE_WIDTH_MM,
            output_axial_travel=(-stops["negative_mm"], stops["positive_mm"]),
            # A geometric reserve, not a tooth-strength rating.
            minimum_face_overlap_under_travel=0.8 * FACE_WIDTH_MM,
        ),
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
    """Check the actual module-relative axis, including every parent placement."""
    mount = doc.getObject(prefix + "ServoMount")
    if mount is None:
        return {"passed": False, "error": "Missing fixed servo mount datum"}
    configuration = drive_for_document(doc)
    sign = 1 if prefix == "Port" else -1
    expected = App.Vector(sign * configuration.input_x_mm, 0, configuration.input_z_mm)
    actual = (
        doc.MainPropulsionModule.getGlobalPlacement()
        .inverse()
        .multiply(mount.getGlobalPlacement())
    )
    error = (actual.Base - expected).Length
    expressions = [
        str(path)
        for path, _ in mount.ExpressionEngine
        if str(path).lstrip(".").startswith("Placement")
    ]
    frame_sku = getattr(doc.PropulsionFixedFrame, "PrintSKU", None)
    bridge_sku = getattr(doc.ServoDriveBridge, "PrintSKU", None)
    return {
        "pod": prefix,
        "gear_configuration": configuration.key,
        "expected_input_axis_mm": list(expected),
        "actual_input_axis_mm": list(actual.Base),
        "datum_position_error_mm": error,
        "placement_expressions": expressions,
        "expected_frame_sku": configuration.frame_sku,
        "actual_frame_sku": frame_sku,
        "expected_bridge_sku": configuration.bridge_sku,
        "actual_bridge_sku": bridge_sku,
        "scope": "Actual servo axis relative to the complete propulsion module, including the removable bridge's parent placement. A ratio-specific bridge seats on the common output frame; no adjustment slots. Physical printed seating and mesh remain unqualified.",
        "passed": error < TOL
        and actual.Rotation.isSame(App.Rotation(), 1e-7)
        and not expressions
        and "MeshClearance" not in mount.PropertiesList
        and frame_sku == configuration.frame_sku
        and bridge_sku == configuration.bridge_sku,
    }


def bearing_stack_check(bearing, shaft, seat, spacer, carrier, *, opposite_travel):
    """Check one inward-opening cup in coordinates with its opening toward -Y.

    The integral outer shoulder blocks outward motion. Inward motion is bounded
    by the bought inner-ring spacer and the carrier's separately proven frame
    stop. Both rings and the complete radial journal remain in the cup throughout
    that travel. Annular CAD bearing geometry cannot certify a received shield.
    """
    shapes = (bearing, shaft, seat, spacer, carrier)
    if any(shape.isNull() or not shape.isValid() for shape in shapes):
        return {"passed": False, "error": "Missing or invalid bearing-stack solid"}
    if (
        opposite_travel is None
        or not math.isfinite(opposite_travel)
        or opposite_travel < 0
    ):
        return {"passed": False, "error": "Unproven carrier axial stop"}
    bounds = bearing.optimalBoundingBox(False, False)
    x, z = bounds.Center.x, bounds.Center.z
    axis = App.Vector(0, 1, 0)
    origin = App.Vector(x, bounds.YMin, z)
    expected = Part.makeCylinder(3, 2.5, origin, axis).cut(
        Part.makeCylinder(1.5, 2.5, origin, axis)
    )
    comparison = geometry_comparison(bearing, expected)
    shaft_bounds = shaft.optimalBoundingBox(False, False)
    axis_error = math.hypot(shaft_bounds.Center.x - x, shaft_bounds.Center.z - z)
    coverage = min(bounds.YMax, shaft_bounds.YMax) - max(bounds.YMin, shaft_bounds.YMin)
    bore_faces = [
        face
        for face in seat.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - 3) < TOL
        and abs(abs(face.Surface.Axis.y) - 1) < TOL
        and math.hypot(face.Surface.Center.x - x, face.Surface.Center.z - z) < TOL
        and min(face.BoundBox.YMax, bounds.YMax) - max(face.BoundBox.YMin, bounds.YMin)
        >= 2.5 - TOL
    ]
    if len(bore_faces) != 1:
        return {
            "passed": False,
            "error": "Missing unique coaxial complete bearing guide",
        }
    guide = bore_faces[0].BoundBox
    spacer_bounds = spacer.optimalBoundingBox(False, False)
    end = spacer_bounds.YMax
    contact_faces = [
        face
        for face in spacer.Faces
        if type(face.Surface).__name__ == "Plane"
        and abs(abs(face.normalAt(0, 0).y) - 1) < TOL
        and abs(face.CenterOfMass.y - end) < TOL
    ]
    if not contact_faces:
        return {"passed": False, "error": "Missing spacer inner-ring contact face"}
    contact = Part.makeCompound(contact_faces)
    contact_bounds = contact.optimalBoundingBox(False, False)
    contact_radius = max(
        abs(contact_bounds.XMin - x),
        abs(contact_bounds.XMax - x),
        abs(contact_bounds.ZMin - z),
        abs(contact_bounds.ZMax - z),
    )
    spacer_axis_error = math.hypot(
        spacer_bounds.Center.x - x, spacer_bounds.Center.z - z
    )
    gap = bounds.YMin - end
    maximum_inward = gap + opposite_travel
    if maximum_inward < 0:
        return {"passed": False, "error": "Spacer passes the bearing inner face"}
    remaining_guide = bounds.YMin - maximum_inward - guide.YMin

    def annular_wall(inner, outer, start, length):
        position = App.Vector(x, start, z)
        return Part.makeCylinder(outer, length, position, axis).cut(
            Part.makeCylinder(inner, length, position, axis)
        )

    guide_witness = annular_wall(
        3.01, 3.2, bounds.YMin - maximum_inward, bounds.YLength + maximum_inward
    )
    outer_shoulder_witness = annular_wall(2.85, 2.95, bounds.YMax + 0.01, 0.5)
    missing_guide_wall = abs(guide_witness.cut(seat).Volume)
    missing_outer_shoulder = abs(outer_shoulder_witness.cut(seat).Volume)
    at_limit = translated_shape(bearing, y=-maximum_inward)
    spacer_at_limit = translated_shape(spacer, y=-opposite_travel)
    carrier_contact = _planar_contact_area(spacer, carrier)
    inner_contact = _planar_contact_area(at_limit, spacer_at_limit)
    # The nominal generic bearing borrows only a comparison abutment limit:
    # <=Ø3.7 inner ring, >=Ø5.4 outer housing opening. With a <=Ø3.1 spacer
    # bore on a measured Ø3 shaft, 0.05 mm radial eccentricity must also fit.
    maximum_radial_eccentricity = 0.05
    beyond = translated_shape(at_limit, y=-0.1)
    inner_block = intersection_volume(beyond, spacer_at_limit)
    outward_block = intersection_volume(translated_shape(bearing, y=0.1), seat)
    guide_span = [guide.YMin, guide.YMax]
    outside_bearing_motion = (
        intersection_volume(
            translation_sweep(bearing, (0, -maximum_inward, 0))[0], seat
        )
        if maximum_inward >= 0
        else float("inf")
    )
    overlaps = {
        "bearing_seat_overlap_mm3": intersection_volume(bearing, seat),
        "bearing_shaft_overlap_mm3": intersection_volume(bearing, shaft),
        "bearing_spacer_overlap_mm3": intersection_volume(bearing, spacer),
        "spacer_shaft_overlap_mm3": intersection_volume(spacer, shaft),
        "spacer_carrier_overlap_mm3": intersection_volume(spacer, carrier),
        "bearing_travel_seat_overlap_mm3": outside_bearing_motion,
    }
    return {
        "stock_shape_comparison": comparison,
        "shaft_axis_error_mm": axis_error,
        "shaft_through_bearing_length_mm": coverage,
        "guide_interval_y_mm": guide_span,
        "bearing_interval_y_mm": [bounds.YMin, bounds.YMax],
        "spacer_carrier_contact_area_mm2": carrier_contact,
        "spacer_axis_error_mm": spacer_axis_error,
        "spacer_contact_radius_mm": contact_radius,
        "spacer_bore_eccentricity_allowance_mm": maximum_radial_eccentricity,
        "comparison_inner_abutment_radius_max_mm": 1.85,
        "nominal_spacer_to_inner_ring_gap_mm": gap,
        "opposite_carrier_travel_mm": opposite_travel,
        "maximum_bearing_inward_travel_mm": maximum_inward,
        "full_bearing_guide_reserve_mm": remaining_guide,
        "missing_complete_guide_wall_mm3": missing_guide_wall,
        "missing_complete_outer_shoulder_mm3": missing_outer_shoulder,
        "inner_ring_contact_at_inward_limit_mm2": inner_contact,
        "axial_capture": [
            {
                "direction": "outward",
                "blocking_intersection_mm3": outward_block,
                "passed": outward_block > TOL,
            },
            {
                "direction": "inward",
                "blocking_intersection_mm3": inner_block,
                "passed": inner_block > TOL,
            },
        ],
        **overlaps,
        "scope": "Nominal complete bearing envelope retained outward by an integral cup shoulder and inward through its inner ring, a bought flanged spacer and the independently proven carrier/frame stop. The bearing may slide inward while retaining full radial guide engagement. The 3.7 mm comparison inner-land limit and 0.05 mm spacer eccentricity allowance require received-bearing and shaft checks; no shield identity, preload, fits, rolling axial capacity or PA12 creep is qualified.",
        "passed": comparison["difference_mm3"] < TOL
        and axis_error < TOL
        and coverage >= 2.5 - TOL
        and abs(bounds.YMax - guide.YMax) < TOL
        and guide.YLength >= 4 - TOL
        and spacer_axis_error < TOL
        and contact_radius + maximum_radial_eccentricity <= 1.85 + TOL
        and carrier_contact > 1
        and inner_contact > 1.0
        and gap >= 0.2 - TOL
        and remaining_guide >= 0.3 - TOL
        and missing_guide_wall < TOL
        and missing_outer_shoulder < TOL
        and outward_block > TOL
        and inner_block > TOL
        and all(value < TOL for value in overlaps.values()),
    }


def output_bearing_stack_check(doc, prefix, suffix, axial_stops=None):
    """Normalize all real saved placements before the local capture proof."""
    from .motion_clearance import _in_pod_coordinates

    pod = doc.getObject(prefix + "Pod")
    names = [
        prefix + "OutputBearing" + suffix,
        prefix + "OutputShaft" + suffix,
        "PropulsionFixedFrame",
        prefix + "OutputBearingSpacer" + suffix,
        prefix + "MotorCarrier",
    ]
    objects = [doc.getObject(name) for name in names]
    if pod is None or any(obj is None for obj in objects):
        return {"passed": False, "error": "Missing output bearing capture component"}
    stops = (
        axial_stops if axial_stops is not None else carrier_axial_travel(doc, prefix)
    )
    if not stops.get("passed"):
        return {
            "passed": False,
            "error": "Unproven carrier/frame axial stops",
            "axial_stops": stops,
        }
    shapes = [_in_pod_coordinates(obj, pod) for obj in objects]
    if suffix == "Negative":
        for shape in shapes:
            shape.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
    return {
        "bearing": names[0],
        "spacer": names[3],
        **bearing_stack_check(
            *shapes,
            opposite_travel=stops[
                "negative_mm" if suffix == "Positive" else "positive_mm"
            ],
        ),
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


def clamp_fastener_check(clamp, bolt, nut, *, thread_diameter=2.0, nut_height=1.6):
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


def _coupling_shape_world(doc, prefix, shape):
    """Place a horn-local probe through the actual moving input-drive parents."""
    from gondola.parts import servo_coupling as coupling

    shape = shape.copy()
    shape.translate(App.Vector(0, coupling.HORN_BOTTOM_Y, 0))
    if prefix == "Starboard":
        shape.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
    drive = doc.getObject(prefix + "InputDrive")
    shape.Placement = drive.getGlobalPlacement().multiply(shape.Placement)
    return shape


def input_shaft_retention_check(doc, prefix):
    """Measure the metal stub's keyed socket, axial stop and radial jack clamp."""
    from gondola.contracts import fasteners
    from gondola.parts import purchased_hardware as hardware
    from gondola.parts import servo_coupling as coupling

    names = (
        "InputShaft",
        "InputShaftClampBolt",
        "InputShaftClampNut",
        "HornGearAdapter",
    )
    if any(doc.getObject(prefix + suffix) is None for suffix in names):
        return {"pod": prefix, "passed": False, "error": "Missing driver stub or clamp"}
    shaft, screw, nut, adapter = (
        world_shape(doc.getObject(prefix + suffix)) for suffix in names
    )
    expected_shaft = _coupling_shape_world(doc, prefix, coupling.driver_shaft_shape())
    missing_shaft = abs(expected_shaft.cut(shaft).Volume)
    extra_shaft = abs(shaft.cut(expected_shaft).Volume)
    head_probe = Part.makeCylinder(
        hardware.SCREW_HEAD_DIAMETER / 2 + 0.01,
        hardware.SCREW_HEAD_HEIGHT + 0.1,
        App.Vector(coupling.SHAFT_SCREW_HEAD_X, coupling.SHAFT_CLAMP_Y, 0),
        App.Vector(1, 0, 0),
    )
    head = screw.common(_coupling_shape_world(doc, prefix, head_probe))
    head_gap = head.distToShape(adapter)[0] if head.Volume > TOL else -1
    tip_contact = _planar_contact_area(screw, shaft)
    # Only the outer pocket wall reacts against tightening the radial screw.
    # Contact with the opposite insertion-slot wall cannot establish preload.
    seat_x, seat_y = coupling.SHAFT_NUT_SEAT_X, coupling.SHAFT_CLAMP_Y
    seat_points = [
        App.Vector(seat_x, seat_y + y, z)
        for y, z in ((-3, -3), (3, -3), (3, 3), (-3, 3))
    ]
    seat_plane = Part.Face(Part.makePolygon(seat_points + seat_points[:1]))
    retaining_wall = adapter.common(_coupling_shape_world(doc, prefix, seat_plane))
    nut_wall_contact = _planar_contact_area(nut, retaining_wall)
    # The smallest accepted nut must also encounter the saved pocket walls.
    # Keep its threaded axis fixed at the installed screw; this does not model
    # an unthreaded nut lifted through the deliberately open loading slot.
    minimum_nut = hardware.hex_prism(
        fasteners.HEX_NUT_MIN_AF, fasteners.HEX_NUT_MIN_HEIGHT
    ).cut(
        Part.makeCylinder(
            fasteners.THREAD_DIAMETER / 2,
            fasteners.HEX_NUT_MIN_HEIGHT + 0.2,
            App.Vector(0, 0, -0.1),
        )
    )
    minimum_nut.Placement = App.Placement(
        App.Vector(seat_x, seat_y, 0),
        App.Rotation(App.Vector(0, 0, 1), App.Vector(*coupling.SHAFT_BOLT_DIRECTION)),
    )
    placed_minimum_nut = _coupling_shape_world(doc, prefix, minimum_nut)
    minimum_nut_overlap = intersection_volume(placed_minimum_nut, adapter)
    minimum_nut_contact = _planar_contact_area(placed_minimum_nut, retaining_wall)
    nut_rotation_checks = []
    for angle in (-30, 30):
        rotated = minimum_nut.copy()
        rotated.rotate(App.Vector(seat_x, seat_y, 0), App.Vector(1, 0, 0), angle)
        overlap = intersection_volume(
            adapter, _coupling_shape_world(doc, prefix, rotated)
        )
        nut_rotation_checks.append(
            {
                "attempted_rotation_deg": angle,
                "pocket_probe_penetration_mm3": overlap,
                "passed": overlap > TOL,
            }
        )
    minimum_nut_capture = {
        "across_flats_mm": fasteners.HEX_NUT_MIN_AF,
        "height_mm": fasteners.HEX_NUT_MIN_HEIGHT,
        "neutral_pocket_overlap_mm3": minimum_nut_overlap,
        "retaining_wall_contact_mm2": minimum_nut_contact,
        "rotation_stop_checks": nut_rotation_checks,
        "scope": "Smallest accepted nut on the fixed threaded axis against the actual saved nominal pocket. Both 30-degree attempts must be blocked. This does not bound angular play or certify as-printed capture with +/-0.3 mm manufacturing variation, nut handling, tightening torque or PA12 strength; finish and trial the received nut.",
        "passed": minimum_nut_overlap < TOL
        and minimum_nut_contact > 1
        and all(row["passed"] for row in nut_rotation_checks),
    }
    stop_contact = _planar_contact_area(shaft, adapter)
    roof_probe = Part.makeLine(App.Vector(0, 5.2, 0), App.Vector(0, 7.1, 0))
    roof_thickness = adapter.common(
        _coupling_shape_world(doc, prefix, roof_probe)
    ).Length
    key_checks = []
    for angle in (-15, 15):
        rotated = coupling.driver_shaft_shape()
        rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
        overlap = intersection_volume(
            adapter, _coupling_shape_world(doc, prefix, rotated)
        )
        key_checks.append(
            {
                "attempted_rotation_deg": angle,
                "key_probe_penetration_mm3": overlap,
                "passed": overlap > 1e-3,
            }
        )
    stop_probe = coupling.driver_shaft_shape()
    stop_probe.translate(App.Vector(0, -0.01, 0))
    stop_overlap = intersection_volume(
        adapter, _coupling_shape_world(doc, prefix, stop_probe)
    )
    socket_probe = Part.makeCylinder(
        2,
        coupling.SHAFT_SOCKET_LENGTH,
        App.Vector(0, coupling.SHAFT_START_Y, 0),
        App.Vector(0, 1, 0),
    )
    socket_shaft = expected_shaft.common(
        _coupling_shape_world(doc, prefix, socket_probe)
    )
    missing_engagement = abs(socket_shaft.cut(shaft).Volume)
    return {
        "pod": prefix,
        "shaft_nominal_diameter_mm": coupling.SHAFT_DIAMETER,
        "shaft_length_mm": coupling.SHAFT_LENGTH,
        "filed_flat_depth_mm": coupling.SHAFT_FLAT_DEPTH,
        "socket_engagement_mm": coupling.SHAFT_SOCKET_LENGTH,
        "missing_nominal_stub_mm3": missing_shaft,
        "extra_stub_material_mm3": extra_shaft,
        "missing_socket_engagement_mm3": missing_engagement,
        "shaft_stop_contact_mm2": stop_contact,
        "stop_probe_penetration_mm3": stop_overlap,
        "key_checks": key_checks,
        "screw_tip_to_flat_contact_mm2": tip_contact,
        "nut_to_retaining_wall_contact_mm2": nut_wall_contact,
        "minimum_nut_capture": minimum_nut_capture,
        "screw_head_to_adapter_gap_mm": head_gap,
        "required_nominal_head_gap_mm": 0.5,
        "shaft_stop_roof_thickness_mm": roof_thickness,
        "scope": "Nominal metal D stub and finished printed socket; positive key engagement after clearance is taken up, axial stop, radial M2x6 screw contact and retained hex nut. The screw head must remain free to advance against the flat. Manual rod diameter/straightness/flat, nut capture, clamp preload, axial grip, actual gear set-screw retention and loaded servo deflection remain physical checks. The bore key alone is not axial retention.",
        "passed": missing_shaft < TOL
        and extra_shaft < TOL
        and socket_shaft.Volume > TOL
        and missing_engagement < TOL
        and stop_contact > 1
        and stop_overlap > 1e-5
        and all(row["passed"] for row in key_checks)
        and tip_contact > 1
        and nut_wall_contact > 1
        and minimum_nut_capture["passed"]
        and abs(head_gap - 0.5) < TOL
        and abs(roof_thickness - 1.9) < TOL
        and all(
            intersection_volume(a, b) < TOL
            for a, b in (
                (shaft, adapter),
                (screw, shaft),
                (screw, adapter),
                (nut, adapter),
                (screw, nut),
            )
        ),
    }


def horn_registration_check(doc, prefix):
    """Measure the saved horn's radial location without relying on bolt friction."""
    from gondola.parts import servo_coupling as coupling

    drive = doc.getObject(prefix + "InputDrive")
    mirror = App.Rotation(App.Vector(0, 0, 1), 180 if prefix == "Starboard" else 0)
    frame = (
        drive.getGlobalPlacement()
        .multiply(App.Placement(App.Vector(), mirror))
        .multiply(
            App.Placement(App.Vector(0, coupling.HORN_BOTTOM_Y, 0), App.Rotation())
        )
    )
    inverse = frame.inverse()
    shapes = []
    for suffix in ("ServoHorn", "HornGearAdapter"):
        shape = world_shape(doc.getObject(prefix + suffix))
        shape.Placement = inverse.multiply(shape.Placement)
        shapes.append(shape)
    horn, adapter = shapes
    rows = []
    for x, z in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        volumes = []
        for distance in (0.04, 0.1):
            moved = horn.copy()
            moved.translate(App.Vector(x * distance, 0, z * distance))
            volumes.append(intersection_volume(moved, adapter))
        rows.append(
            {
                "local_xz_direction": [x, z],
                "within_clearance_intersection_mm3": volumes[0],
                "beyond_clearance_intersection_mm3": volumes[1],
                "passed": volumes[0] < TOL and volumes[1] > 1e-4,
            }
        )
    return {
        "nominal_translation_probes": rows,
        "within_clearance_probe_mm": 0.04,
        "beyond_clearance_probe_mm": 0.1,
        "scope": "Saved rigid locating faces at the installed horn angle. The root register and short tip datum bound radial translation independently of the loose through-hole. These nominal probes do not establish print fit, a combined translation/rotation tolerance, clamp torque or physical concentricity.",
        "passed": all(row["passed"] for row in rows),
    }


def direct_adapter_fit_check(doc, prefix):
    """Preserve the actual Ø3 gear bore, metal engagement and stock-horn capture."""
    from gondola.parts import servo_coupling as coupling

    parts = {
        suffix: world_shape(doc.getObject(prefix + suffix))
        for suffix in (
            "DriverGear",
            "ServoHorn",
            "HornGearAdapter",
            "HornGearClampBolt",
            "HornGearClampNut",
            "InputShaft",
            "InputShaftClampBolt",
            "InputShaftClampNut",
        )
    }
    specification = drive_for_document(doc).driver
    origin = App.Vector(0, coupling.GEAR_START_Y, 0)
    axis = App.Vector(0, 1, 0)
    bore = Part.makeCylinder(
        specification.bore_mm / 2, specification.total_length_mm, origin, axis
    )
    ring = Part.makeCylinder(
        specification.bore_mm / 2 + 0.3, specification.total_length_mm, origin, axis
    ).cut(bore)
    bore = _coupling_shape_world(doc, prefix, bore)
    ring = _coupling_shape_world(doc, prefix, ring)
    bore_intrusion = intersection_volume(bore, parts["DriverGear"])
    missing_hub = abs(ring.cut(parts["DriverGear"]).Volume)
    adapter_in_gear_bore = intersection_volume(bore, parts["HornGearAdapter"])
    expected_shaft = _coupling_shape_world(doc, prefix, coupling.driver_shaft_shape())
    gear_journal = expected_shaft.common(bore)
    missing_gear_engagement = abs(gear_journal.cut(parts["InputShaft"]).Volume)
    projection = (
        coupling.SHAFT_START_Y
        + coupling.SHAFT_LENGTH
        - (coupling.GEAR_START_Y + specification.total_length_mm)
    )
    reserve = expected_shaft.common(
        _coupling_shape_world(
            doc,
            prefix,
            Part.makeCylinder(
                specification.bore_mm / 2,
                projection,
                App.Vector(0, coupling.GEAR_START_Y + specification.total_length_mm, 0),
                axis,
            ),
        )
    )
    missing_reserve = abs(reserve.cut(parts["InputShaft"]).Volume)
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
        for name in ("HornGearAdapter", "HornGearClampBolt")
    }
    retention = input_shaft_retention_check(doc, prefix)
    registration = horn_registration_check(doc, prefix)
    return {
        "pod": prefix,
        "gear_bore_mm": specification.bore_mm,
        "gear_bore_intrusion_mm3": bore_intrusion,
        "missing_gear_hub_ring_mm3": missing_hub,
        "printed_adapter_in_gear_bore_mm3": adapter_in_gear_bore,
        "metal_gear_engagement_mm": specification.total_length_mm,
        "missing_metal_gear_engagement_mm3": missing_gear_engagement,
        "metal_projection_beyond_gear_mm": projection,
        "missing_gear_end_reserve_mm3": missing_reserve,
        "input_shaft_retention_passed": retention["passed"],
        "horn_registration": registration,
        "internal_pairs": rows,
        "nominal_horn_contact_area_mm2": capture,
        "scope": "Selected bought Ø3 bore remains unchanged. The metal D stub spans the full 8 mm driver and projects 2 mm beyond it; this is a metal-length reserve, not a qualified axial adjustment range or arbitrary-gear compatibility. The printed adapter stays outside the bore, and the prepared Ø1.8 mm horn-tip clearance hole accepts the M1.6 clamp, whose head bears directly on the metal horn opposite the adapter. Finish fit, clamp preload, aluminium rod quality, supplied gear set screw and servo radial-load capacity remain physical checks.",
        "passed": specification.bore_mm == coupling.GEAR_BORE_DIAMETER
        and specification.total_length_mm == coupling.GEAR_LENGTH
        and bore_intrusion < TOL
        and missing_hub < TOL
        and adapter_in_gear_bore < TOL
        and gear_journal.Volume > TOL
        and missing_gear_engagement < TOL
        and abs(projection - 2) < TOL
        and reserve.Volume > TOL
        and missing_reserve < TOL
        and retention["passed"]
        and registration["passed"]
        and all(row["intersection_mm3"] < TOL for row in rows)
        and all(area > 1 for area in capture.values()),
    }


def _servo_rear_body_allowance(doc, prefix):
    """Measure the rear case separately from its lower mounting ear."""
    from gondola.parts import servo_bridge

    from .relative_motion import _certify_pair, _part

    mount = doc.getObject(prefix + "ServoMount")
    group = doc.getObject("MainPropulsionModule")
    if mount is None or group is None:
        return {"passed": False, "error": "Missing servo or propulsion module"}
    canonical = mount.getGlobalPlacement().multiply(
        App.Placement(
            App.Vector(),
            App.Rotation(App.Vector(0, 0, 1), 180 if prefix == "Starboard" else 0),
        )
    )
    inverse = canonical.inverse()
    shapes = {}
    for obj in doc.Objects:
        if (
            belongs_to_group(obj, group)
            and obj.isDerivedFrom("Part::Feature")
            and getattr(obj, "Role", "") != "Clearance"
        ):
            shape = world_shape(obj)
            if shape.isNull() or not shape.isValid() or not shape.Solids:
                return {
                    "passed": False,
                    "error": "Invalid physical obstacle: " + obj.Name,
                }
            shape.Placement = inverse.multiply(shape.Placement)
            shapes[obj.Name] = shape
    if any(name not in shapes for name in (prefix + "Servo", "ServoDriveBridge")):
        return {"passed": False, "error": "Missing servo case or connecting plate"}
    rear = servo_bridge.case_front_y() - 16.6
    # Read a rear-case strip that does not contain the forward mounting ears.
    # The lower ear reaches four millimetres below the actual body.
    strip = Part.makeBox(9, 1, 40, App.Vector(-4.5, rear + 0.5, -30))
    body = shapes[prefix + "Servo"].common(strip)
    under = shapes["ServoDriveBridge"].common(
        Part.makeBox(7, 1, 40, App.Vector(-3.5, rear + 0.5, -40))
    )
    if not body.Solids or not under.Solids:
        return {"passed": False, "error": "Missing rear body strip or plate beneath it"}
    body_bounds = body.optimalBoundingBox(False, False)
    plate_bounds = under.optimalBoundingBox(False, False)
    gap = body_bounds.ZMin - plate_bounds.ZMax
    lane_end = rear - 0.1
    lane_start = lane_end - servo_bridge.REAR_LEAD_ALLOWANCE
    lane = Part.makeBox(
        body_bounds.XLength,
        servo_bridge.REAR_LEAD_ALLOWANCE,
        body_bounds.ZLength,
        App.Vector(body_bounds.XMin, lane_start, body_bounds.ZMin),
    )
    collisions = [
        {"part": name, "intersection_mm3": volume}
        for name, obstacle in shapes.items()
        if (volume := intersection_volume(lane, obstacle)) > TOL
    ]
    # Keep the complete rear lead allowance clear of both independently moving
    # input drives. Normalize each actual part to neutral without changing the
    # document, then certify every point in its bounded +/-60 degree motion.
    stationary = _part(lane, prefix + "RearLeadAllowance")
    moving_rows = []
    spec = drive_for_document(doc)
    for side in ("Port", "Starboard"):
        drive = doc.getObject(side + "InputDrive")
        if drive is None:
            return {"passed": False, "error": "Missing input drive: " + side}
        placed = drive.getGlobalPlacement()
        parent = drive.getParentGeoFeatureGroup().getGlobalPlacement()
        neutral = parent.multiply(App.Placement(drive.Placement.Base, App.Rotation()))
        to_neutral = inverse.multiply(neutral).multiply(placed.inverse())
        axis = inverse.multiply(neutral).Base
        for obj in doc.Objects:
            if obj.Name not in shapes or not belongs_to_group(obj, drive):
                continue
            shape = world_shape(obj)
            shape.Placement = to_neutral.multiply(shape.Placement)
            moving_rows.append(
                _certify_pair(
                    stationary,
                    _part(
                        shape,
                        obj.Name,
                        axis=tuple(axis),
                        rate=-1 / spec.ratio,
                        prefix=side,
                    ),
                )
            )
    return {
        "coordinate_frame": "servo axis, positive Y toward the horn",
        "rear_body_bottom_z_mm": body_bounds.ZMin,
        "servo_with_ears_bottom_z_mm": shapes[prefix + "Servo"].BoundBox.ZMin,
        "rear_body_section_mm": [body_bounds.XLength, body_bounds.ZLength],
        "plate_top_below_rear_body_z_mm": plate_bounds.ZMax,
        "rear_body_to_plate_gap_mm": gap,
        "minimum_rear_body_allowance_mm": 5.0,
        "inward_planning_volume_mm": [
            body_bounds.XLength,
            servo_bridge.REAR_LEAD_ALLOWANCE,
            body_bounds.ZLength,
        ],
        "inward_planning_y_range_mm": [lane_start, lane_end],
        "checked_physical_objects": sorted(shapes),
        "planning_volume_collisions": collisions,
        "continuous_input_drive_clearance": moving_rows,
        "scope": "Saved rear case strip excludes the lower mounting ear. Rearward planning space stops before the case rear face and never claims under-ear/nut access. Every physical input-drive part on both sides is checked through its complete bounded motion. Received lead exit position, diameter, connector and bend radius are unspecified; this rigid design allowance is not a factory cable route or installed harness qualification.",
        "passed": abs(body_bounds.ZMin + 15) < TOL
        and abs(body_bounds.ZLength - 20) < TOL
        and abs(body_bounds.XLength - 7) < TOL
        and gap >= 5.0 - TOL
        and not collisions
        and bool(moving_rows)
        and all(row["passed"] for row in moving_rows),
    }


def servo_mount_check(doc, prefix):
    """Require both stock ears to seat on the removable bridge without collision."""
    frame = world_shape(doc.ServoDriveBridge)
    servo = world_shape(doc.getObject(prefix + "Servo"))
    frame_overlap = intersection_volume(frame, servo)
    clamps = Part.makeCompound([frame, servo])
    rear_allowance = _servo_rear_body_allowance(doc, prefix)
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
        "rear_body_and_inward_lead_allowance": rear_allowance,
        "cases": rows,
        "scope": "The two published X06 ears bear directly on the removable bridge using M1.6 fasteners. Nominal rigid contact is not proof of clamp torque, stiffness or actual case fit.",
        "passed": frame_overlap < TOL
        and rear_allowance["passed"]
        and all(row["passed"] for row in rows),
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


def adapter_service_check(shape, waypoints, obstacles, spec, sign):
    """Fill the forward clamp voids while preserving the rear horn socket.

    The transverse shaft screw hole prevents the generic coaxial sweep from
    retaining the horn pocket. A solid block around the forward clamp is a
    conservative replacement for that region only. The live adapter must fit
    completely within this reference before its continuous sweep is accepted.
    Every retained obstacle remains checked, including the original horn.
    """
    from gondola.parts import servo_coupling as coupling

    reference = coupling.adapter_shape()
    bounds = reference.BoundBox
    # Start just beyond the rear body's front face so its boundary alone cannot
    # enlarge the clamp's measured section to the remote horn-clamp bolt tip.
    front = reference.common(
        Part.makeBox(
            bounds.XLength + 2,
            bounds.YMax - coupling.SHAFT_START_Y,
            bounds.ZLength + 2,
            App.Vector(bounds.XMin - 1, coupling.SHAFT_START_Y + 1e-4, bounds.ZMin - 1),
        )
    )
    if not front.Solids or front.Volume < TOL:
        return {"passed": False, "error": "Missing forward adapter clamp"}
    front_bounds = front.BoundBox
    filled = Part.makeBox(
        front_bounds.XLength,
        bounds.YMax - coupling.SHAFT_START_Y,
        front_bounds.ZLength,
        App.Vector(front_bounds.XMin, coupling.SHAFT_START_Y, front_bounds.ZMin),
    )
    envelope = reference.fuse(filled).removeSplitter()
    envelope.translate(App.Vector(0, coupling.HORN_BOTTOM_Y, 0))
    if sign < 0:
        envelope.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
    envelope.translate(App.Vector(sign * spec.input_x_mm, 0, spec.input_z_mm))
    outside = abs(shape.cut(envelope).Volume)
    result = continuous_path(envelope, waypoints, obstacles)
    return {
        **result,
        "adapter_outside_reference_envelope_mm3": outside,
        "reference_envelope": "Actual nominal horn socket with forward shaft-clamp voids conservatively filled; no obstacle exclusions",
        "passed": outside < TOL and result["passed"],
    }


def _input_drive_names(prefix):
    """Parts withdrawn together, then separated on the bench."""
    return {
        prefix + suffix
        for suffix in (
            "DriverGear",
            "HornGearAdapter",
            "InputShaft",
            "InputShaftClampBolt",
            "InputShaftClampNut",
        )
    }


def _input_service_removed(prefix):
    """Complete removal prerequisite for accessing the servo ear fasteners."""
    return _input_drive_names(prefix) | {
        prefix + suffix
        for suffix in (
            "OutputGear",
            "HornGearClampBolt",
            "HornGearClampNut",
        )
    }


def _ear_fastener_names(prefix):
    return {
        prefix + "ServoEar" + side + kind
        for side in ("Lower", "Upper")
        for kind in ("Bolt", "Nut")
    }


def _axial_then_lateral_path(shape, waypoints, obstacles, *, kind, spec, sign):
    axial = continuous_path(shape, waypoints[:2], obstacles)
    lateral = (
        driver_lateral_service_check(
            shape, waypoints[1], waypoints[2], obstacles, spec, sign
        )
        if kind == "gear"
        else servo_lateral_service_check(shape, waypoints[1], waypoints[2], obstacles)
    )
    return {
        **lateral,
        "segments": axial["segments"] + lateral["segments"],
        "passed": axial["passed"] and lateral["passed"],
    }


def _input_service_path(name, shape, waypoints, obstacles, spec, sign):
    """Select each part's conservative envelope for the ordered release path."""
    if name.endswith("DriverGear") or name.endswith("Servo"):
        return _axial_then_lateral_path(
            shape,
            waypoints,
            obstacles,
            kind="gear" if name.endswith("DriverGear") else "servo",
            spec=spec,
            sign=sign,
        )
    if name.endswith("HornGearAdapter"):
        return adapter_service_check(shape, waypoints, obstacles, spec, sign)
    return continuous_path(shape, waypoints, obstacles)


def input_drive_service_check(doc, module, prefix):
    """Release the hub-registered coupling while keeping output supports."""
    from gondola.parts import servo_coupling as coupling

    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"pod": prefix, "missing_parts": missing, "passed": False}
    sign = 1 if prefix == "Port" else -1
    gear = prefix + "OutputGear"
    released = {prefix + "HornGearClamp" + kind for kind in ("Bolt", "Nut")}
    output_path = continuous_path(
        shapes[gear],
        [(0, 0, 0), (0, -sign * 35, 0)],
        retained_obstacles(shapes, {gear}),
    )
    clamp_path = fastener_service_check(
        shapes[prefix + "HornGearClampBolt"],
        shapes[prefix + "HornGearClampNut"],
        retained_obstacles(shapes, {gear} | released),
        thread_diameter=1.6,
    )
    removed = {gear} | released
    rows = []
    moving = _input_drive_names(prefix)
    fixed = retained_obstacles(shapes, removed | moving)
    release_y = sign * coupling.ADAPTER_RELEASE_TRAVEL
    points = [(0, 0, 0), (0, release_y, 0), (sign * 40, release_y, 0)]
    spec = drive_for_document(doc)
    for name in sorted(moving):
        path = _input_service_path(name, shapes[name], points, fixed, spec, sign)
        rows.append({"part": name, "waypoints_mm": points, **path})
    return {
        "pod": prefix,
        "moving_parts": sorted(moving),
        "removed_output_gear": gear,
        "released_fasteners": sorted(released),
        "output_gear_removal": output_path,
        "adapter_clamp_release": clamp_path,
        "part_paths": rows,
        "coordinate_frame": "propulsion module",
        "retained_parts": sorted(fixed),
        "adapter_axial_release_travel_mm": coupling.ADAPTER_RELEASE_TRAVEL,
        "scope": "At neutral, free the leads and release the small gear's selected set screw; withdraw that gear inboard. Remove the M1.6 through-horn clamp bolt and nut. Move the adapter, metal stub, captive radial clamp and driver together through the reported gearward release travel to clear the horn register, then 40 mm sideways outward. The servo, its original retained horn, both output shafts, bearings and spacers remain installed. Tool and rigid-part envelopes are nominal; actual set-screw access, leads, fit forces and handling remain unqualified.",
        "passed": output_path["passed"]
        and clamp_path["passed"]
        and all(row["passed"] for row in rows),
    }


def servo_case_service_check(doc, module, prefix):
    """Extract the servo and stock horn after the separately checked drive release."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"pod": prefix, "missing_parts": missing, "passed": False}
    sign = 1 if prefix == "Port" else -1
    released = _ear_fastener_names(prefix)
    removed = _input_service_removed(prefix)
    fasteners = []
    for side in ("Lower", "Upper"):
        name = prefix + "ServoEar" + side
        pair = {name + "Bolt", name + "Nut"}
        fasteners.append(
            {
                "bolt": name + "Bolt",
                **fastener_service_check(
                    shapes[name + "Bolt"],
                    shapes[name + "Nut"],
                    retained_obstacles(shapes, removed | pair),
                    thread_diameter=1.6,
                ),
            }
        )
        removed.update(pair)
    moving = {prefix + "Servo", prefix + "ServoHorn"}
    fixed = retained_obstacles(shapes, removed | moving)
    points = [(0, 0, 0), (0, sign * 12.5, 0), (sign * 40, sign * 12.5, 0)]
    spec = drive_for_document(doc)
    rows = []
    for name in sorted(moving):
        path = _input_service_path(name, shapes[name], points, fixed, spec, sign)
        rows.append({"part": name, "waypoints_mm": points, **path})
    return {
        "pod": prefix,
        "frame": "PropulsionFixedFrame",
        "moving_parts": sorted(moving),
        "released_fasteners": sorted(released),
        "ear_fastener_release": fasteners,
        "required_prior_check": "input_drive_service",
        "removed_local_parts": sorted(removed),
        "retained_parts": sorted(fixed),
        "coordinate_frame": "propulsion module",
        "waypoints_mm": points,
        "part_paths": rows,
        "scope": "After the checked small-gear, through-horn clamp and adapter/driver removal, release both servo-ear bolt/nut pairs and free the leads. Move the servo with its retained original horn 12.5 mm gearward, then 40 mm sideways. The bridge, common frame and every output shaft, bearing and spacer remain installed. Reverse the paths for insertion; physical case, cable and tool fit still require a prototype.",
        "passed": all(row["passed"] for row in fasteners + rows),
    }


def rail_key_access_check(doc, module):
    """Check the finite L-key, working arc and service path on either rail side."""
    objects = module["printed"] + module["hardware"] + module["references"]
    shapes = {obj.Name: world_shape(obj) for obj in objects}
    return [
        rail_key_service_check(
            shapes, side=side, placement=module["group"].getGlobalPlacement()
        )
        for side in (1, -1)
    ]


def bearing_post_roots_check(doc):
    """Require four full-section load paths from the feet into the bearing posts."""
    frame = doc.getObject("PropulsionFixedFrame")
    if frame is None:
        return [{"passed": False, "error": "Missing output support frame"}]
    shape = frame.Shape.copy()
    shape.Placement = App.Placement()
    rows = []
    bottom, top = propulsion.BASE_Z + propulsion.FOOT_THICKNESS, 14.0
    for sign in (-1, 1):
        for local_y in (-28.5, 28.5):
            centre_y = sign * (propulsion.PIVOT_HALF_SPAN + local_y)
            witness = Part.makeBox(
                9.6,
                4.0,
                top - bottom,
                App.Vector(-4.8, centre_y - 2.0, bottom),
            )
            missing = abs(witness.cut(shape).Volume)
            rows.append(
                {
                    "side": sign,
                    "post_local_y_mm": local_y,
                    "root_section_mm": [9.6, 4.0],
                    "root_height_range_mm": [bottom, top],
                    "missing_root_material_mm3": missing,
                    "scope": "Complete nominal root section, not a stress or fatigue qualification.",
                    "passed": missing < TOL,
                }
            )
    return rows


def _record_rail_fit_checks(report, frame, physical):
    """Audit both seated rail interfaces and continuous nut loading."""
    for side, label in ((1, "positive"), (-1, "negative")):
        transform = (lambda shape: shape) if side > 0 else rail.half_turn
        report[label + "_seated_rail_overlap_mm3"] = intersection_volume(
            translated_shape(frame, y=side * rail.CLAMP_SHIFT_Y), rail.rail_shape()
        )
        for name, shape in (
            ("clamp_screw", rail.clamp_screw_shape()),
            ("clamp_nut", rail.nut_shape()),
        ):
            report[label + "_" + name + "_frame_overlap_mm3"] = intersection_volume(
                frame, transform(shape)
            )
        key = rail_key_service_check(physical, side=side)
        report[label + "_clamp_key_service"] = key
    # Fill the bore for this insertion audit. The resulting hex prism contains
    # the whole nut and has an exact planar translation sweep; a transverse
    # cylinder otherwise triggers an unnecessarily broad rectangular fallback
    # that reports the pocket's intended hex corner material as a collision.
    outer_nut = rail.hex_along_y(
        rail.NUT_AF,
        rail.NUT_POCKET_Y + rail.NUT_POCKET_DEPTH - rail.NUT_THICKNESS,
        rail.NUT_THICKNESS,
    )
    report["continuous_nut_loading"] = []
    for side in (1, -1):
        envelope = outer_nut if side > 0 else rail.half_turn(outer_nut)
        result = continuous_path(envelope, [(0, 0, 0), (side * 20, 0, 0)], physical)
        result["scope"] = (
            "Continuous outer-hex insertion envelope with the bore filled; "
            "conservative over the complete nut, with its rail bolt removed."
        )
        report["continuous_nut_loading"].append(result)


def _record_drive_motion_checks(report, doc, module, prefix):
    """Keep native motion, meshing and coupled service evidence together."""
    report["drive_motion"].append(drive_motion_check(doc, prefix))
    report["fixed_servo_datum"].append(fixed_servo_datum_check(doc, prefix))
    report["servo_mounts"].append(servo_mount_check(doc, prefix))
    report["direct_adapter_fit"].append(direct_adapter_fit_check(doc, prefix))
    report["input_shaft_retention"].append(input_shaft_retention_check(doc, prefix))
    report["gear_rotation"].append(gear_rotation_check(doc, prefix))
    carrier_clearance = carrier_metal_clearance_check(doc, prefix)
    report["carrier_metal_clearance"].append(carrier_clearance)
    axial_stops = carrier_clearance.get("axial_travel", {"passed": False})
    report["gear_mesh_alignment"].append(
        gear_engagement_check(doc, prefix, axial_stops)
    )
    report["tilt_clearance"].append(tilt_clearance_check(doc, module, prefix))
    report["input_drive_service"].append(input_drive_service_check(doc, module, prefix))
    report["servo_case_service"].append(servo_case_service_check(doc, module, prefix))


def _record_output_stub_checks(report, prefix, pod, physical, frame):
    """Check the two separate output stubs and describe their bearing stacks."""
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
                "scope": "Remove the output gear and release its selected set screw, loosen the carrier split clamp, then withdraw this separate stub axially. Nominal unclamped bore; not clamp closure or grip proof.",
                **continuous_path(
                    physical[shaft_name],
                    [(0, 0, 0), (0, side * 35, 0), (40, side * 35, 0)],
                    retained_obstacles(physical, excluded),
                ),
            }
        )


def output_carrier_service_check(doc, module, prefix):
    """Release the capless output rotor while temporarily supporting its bearings."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"pod": prefix, "missing_parts": missing, "passed": False}
    sign = 1 if prefix == "Port" else -1
    gear = prefix + "OutputGear"
    gear_path = continuous_path(
        shapes[gear],
        [(0, 0, 0), (0, -sign * 35, 0)],
        retained_obstacles(shapes, {gear}),
    )
    staged = {name: shape.copy() for name, shape in shapes.items() if name != gear}
    shaft_paths, spacer_paths = [], []
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        for stem, travel, rows in (
            ("OutputShaft", propulsion.SHAFT_ASSEMBLY_RETRACTION, shaft_paths),
            ("OutputBearingSpacer", propulsion.SPACER_ASSEMBLY_SHIFT, spacer_paths),
        ):
            name = prefix + stem + suffix
            offset = (0, side * travel, 0)
            path = continuous_path(
                staged[name], [(0, 0, 0), offset], retained_obstacles(staged, {name})
            )
            rows.append({"part": name, **path})
            staged[name] = translated_shape(staged[name], *offset)
    pod = doc.getObject(prefix + "Pod")
    excluded = (
        {prefix + "OutputShaft" + suffix for suffix in ("Negative", "Positive")}
        | {
            prefix + "OutputBearingSpacer" + suffix
            for suffix in ("Negative", "Positive")
        }
        | {gear}
    )
    moving = {
        name for name in shapes if belongs_to_group(doc.getObject(name), pod)
    } - excluded
    fixed = retained_obstacles(staged, moving)
    paths = [
        {"part": name, **continuous_path(staged[name], [(0, 0, 0), (40, 0, 0)], fixed)}
        for name in sorted(moving)
    ]
    # With the rotor removed, withdraw both stubs completely before taking a
    # spacer off the inside of its cup. The opposite side remains an obstacle.
    for name in moving:
        staged.pop(name)
    full_shaft_paths = []
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        name = prefix + "OutputShaft" + suffix
        path = continuous_path(
            staged[name],
            [(0, 0, 0), (0, side * 35, 0), (40, side * 35, 0)],
            retained_obstacles(staged, {name}),
        )
        full_shaft_paths.append({"part": name, **path})
        staged.pop(name)
    return {
        "pod": prefix,
        "moving_parts": sorted(moving),
        "removed_output_gear": gear,
        "output_gear_removal": gear_path,
        "shaft_staging": shaft_paths,
        "spacer_staging": spacer_paths,
        "carrier_removal": paths,
        "full_shaft_removal": full_shaft_paths,
        "retained_parts": sorted(fixed),
        "scope": "Unpowered bench sequence with leads freed and both shaft clamps loosened: remove the small gear, retract each stub 6.5 mm while supporting the loose bearing/spacer, move each spacer 0.3 mm outward, then slide the complete motor/carrier and its clamp fasteners 40 mm in +X. After removing the rotor, withdraw each stub 35 mm axially and 40 mm in +X, keeping the opposite shaft installed. Reverse for assembly, return spacers against the carrier, position the shafts and tighten the split clamps. Bearings, frame and paired servo module remain installed. Temporary hand support, physical fits and wrench access to loosened clamps need a prototype.",
        "passed": gear_path["passed"]
        and bool(moving)
        and all(
            row["passed"]
            for row in shaft_paths + spacer_paths + paths + full_shaft_paths
        ),
    }


def _record_bearing_checks(report, doc, module, prefix, physical):
    """Prove capless retention and the ordered inward bearing service paths."""
    carrier_service = output_carrier_service_check(doc, module, prefix)
    report["output_carrier_service"].append(carrier_service)
    removed = (
        set(carrier_service.get("moving_parts", []))
        | {prefix + "OutputGear"}
        | {prefix + "OutputShaft" + suffix for suffix in ("Negative", "Positive")}
    )
    staged = {
        name: shape.copy() for name, shape in physical.items() if name not in removed
    }
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        spacer_name = prefix + "OutputBearingSpacer" + suffix
        staged[spacer_name] = translated_shape(
            staged[spacer_name], y=side * propulsion.SPACER_ASSEMBLY_SHIFT
        )
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        bearing_name = prefix + "OutputBearing" + suffix
        spacer_name = prefix + "OutputBearingSpacer" + suffix
        report["bearing_stacks"].append(output_bearing_stack_check(doc, prefix, suffix))
        spacer_path = continuous_path(
            staged[spacer_name],
            [(0, 0, 0), (0, -side * 35, 0)],
            retained_obstacles(staged, {spacer_name}),
        )
        report["spacer_service"].append(
            {
                "spacer": spacer_name,
                "required_prior_check": "output_carrier_service",
                **spacer_path,
                "passed": carrier_service["passed"] and spacer_path["passed"],
            }
        )
        staged.pop(spacer_name)
        path = continuous_path(
            staged[bearing_name],
            [(0, 0, 0), (0, -side * 35, 0)],
            retained_obstacles(staged, {bearing_name}),
        )
        report["bearing_service"].append(
            {
                "bearing": bearing_name,
                "required_prior_check": "output_carrier_service",
                "scope": "After the separately checked complete rotor and both-stub removal, remove this staged spacer inward, then extract its bearing inward. The opposite side remains installed until its own ordered step; the paired servo module stays installed. Actual bearing fit force is unqualified.",
                **path,
                "passed": carrier_service["passed"]
                and spacer_path["passed"]
                and path["passed"],
            }
        )
        staged.pop(bearing_name)


def _record_drive_service_checks(report, prefix, sign, physical):
    """Audit the installed output gear and the removed driver/adapter pair."""
    for suffix, direction, bench in (
        ("OutputGear", -sign, False),
        ("DriverGear", sign, True),
    ):
        name = prefix + suffix
        excluded = {name}
        report["gear_service"].append(
            {
                "gear": name,
                "scope": "Release the selected radial set screw before axial withdrawal. The output gear is removed in place. After the checked input-drive release, separate the driver from its adapter on the bench. Set-screw tip/length and actual driver access remain physical release gates.",
                **continuous_path(
                    physical[name],
                    [(0, 0, 0), (0, direction * 35, 0)],
                    retained_obstacles(
                        physical,
                        excluded,
                        members=_input_drive_names(prefix) if bench else None,
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
                    retained_obstacles(physical, excluded),
                ),
            }
        )


def _record_drive_checks(report, doc, module, physical, frame, prefix, sign):
    """Collect direct input-drive and separately supported output evidence."""
    pod = doc.getObject(prefix + "Pod")
    _record_drive_motion_checks(report, doc, module, prefix)
    _record_output_stub_checks(report, prefix, pod, physical, frame)
    _record_bearing_checks(report, doc, module, prefix, physical)
    _record_drive_service_checks(report, prefix, sign, physical)


def _record_fastener_checks(report, module, physical):
    """Verify installed fastener seats, engagement and ordered access routes."""
    clamp_parts = Part.makeCompound(
        [world_shape(obj) for obj in module["printed"]]
        + [
            physical[prefix + suffix]
            for prefix in ("Port", "Starboard")
            for suffix in ("Servo", "ServoHorn")
        ]
    )
    bolts = [
        obj
        for obj in module["hardware"]
        if obj.HardwareSKU in ("M2X8_BUTTON_HEAD", "M1_6X8_CHEESE_HEAD")
    ]
    for bolt in bolts:
        nut_name = bolt.Name.removesuffix("Bolt") + "Nut"
        nut = physical[nut_name]
        thread_diameter = float(bolt.NominalThreadDiameter.Value)
        nut_height = 1.6 if thread_diameter == 2 else 1.3
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
            service_excluded.add(prefix + "OutputGear")
            prerequisites = "Withdraw the small output gear first; the driver and complete remaining mechanism stay installed."
            matches = [
                row
                for row in report["gear_service"]
                if row["gear"] == prefix + "OutputGear"
            ]
            dependencies.append(
                {
                    "check": "gear_service",
                    "object": prefix + "OutputGear",
                    "passed": len(matches) == 1 and matches[0]["passed"],
                }
            )
        elif "ServoEar" in bolt.Name:
            prefix = "Port" if bolt.Name.startswith("Port") else "Starboard"
            service_excluded.update(_input_service_removed(prefix))
            prerequisites = "Complete the checked small-gear and adapter/driver removal, then release the servo ear fasteners."
            matches = [
                row for row in report["input_drive_service"] if row["pod"] == prefix
            ]
            dependencies.append(
                {
                    "check": "input_drive_service",
                    "object": prefix,
                    "passed": len(matches) == 1 and matches[0]["passed"],
                }
            )
        service = fastener_service_check(
            physical[bolt.Name],
            nut,
            retained_obstacles(physical, service_excluded, members=service_parts),
            thread_diameter=thread_diameter,
            nut_lateral_direction=(1 if "Port" in bolt.Name else -1, 0, 0)
            if bolt.Name.startswith("ServoBridge")
            else None,
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
            (12, propulsion.PIVOT_HALF_SPAN, propulsion.PIVOT_Z + 22.79),
            (12, propulsion.PIVOT_HALF_SPAN, propulsion.PIVOT_Z + 24.31),
            1.5,
        ),
    ]
    from gondola.parts import servo_coupling as coupling

    spec = drive_for_document(module["group"].Document)
    x, z = spec.input_x_mm, spec.input_z_mm
    wall_probes.extend(
        [
            (
                "driver_shaft_stop_roof",
                "PortHornGearAdapter",
                (x, coupling.HORN_BOTTOM_Y + 5.19, z),
                (x, coupling.HORN_BOTTOM_Y + coupling.SHAFT_START_Y + 0.01, z),
                1.9,
            ),
            (
                "driver_shaft_nut_retaining_wall",
                "PortHornGearAdapter",
                (
                    x + coupling.SHAFT_NUT_SEAT_X - 0.01,
                    coupling.HORN_BOTTOM_Y + coupling.SHAFT_CLAMP_Y + 1.5,
                    z,
                ),
                (
                    x + coupling.SHAFT_BOSS_END_X + 0.01,
                    coupling.HORN_BOTTOM_Y + coupling.SHAFT_CLAMP_Y + 1.5,
                    z,
                ),
                coupling.SHAFT_BOSS_END_X - coupling.SHAFT_NUT_SEAT_X,
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
        report["bridge_joint"].append(bridge_joint_check(doc, module))
        report["servo_module_service"].append(servo_module_service_check(doc, module))
        _record_rail_fit_checks(report, frame, physical)
        report["rail_key_access"] = rail_key_access_check(doc, module)
        report["bearing_post_roots"] = bearing_post_roots_check(doc)
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            _record_drive_checks(report, doc, module, physical, frame, prefix, sign)
        _record_fastener_checks(report, module, physical)
        _record_print_checks(report, module, physical)
        report["relative_motion"].append(relative_motion_check(doc, module))
        _complete_report(report, module)
        _write_report(report, source)
        return report
    finally:
        App.closeDocument(doc.Name)
