"""Gear engagement, native bounded motion and fixed servo-axis evidence.

These checks are independent of propulsion report and service orchestration.
Nominal geometry does not establish actual backlash, torque or physical fit.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import world_shape
from gondola.contracts.drive import FACE_WIDTH_MM, MODULE_MM, drive_for_document

from .geometry import intersection_volume
from .motion_clearance import carrier_axial_travel

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
