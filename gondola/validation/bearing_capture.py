"""Saved-geometry proof of spacerless, outer-ring-only bearing capture."""

import math

import FreeCAD as App
import Part

from gondola.cad import box, translated_shape, union
from gondola.parts import bearing_retention
from gondola.print_export import geometry_comparison

from .geometry import intersection_volume

TOL = 1e-5


def _annulus(inner, outer, start_y, length, x=0, z=0):
    axis = App.Vector(0, 1, 0)
    origin = App.Vector(x, start_y, z)
    return Part.makeCylinder(outer, length, origin, axis).cut(
        Part.makeCylinder(inner, length, origin, axis)
    )


def _normalise_capture(seat, keeper, origin):
    """Recover fixed-frame roll from the keeper's actual offset screw hole."""
    holes = [
        face.Surface
        for face in keeper.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - 1.1) < TOL
        and abs(abs(face.Surface.Axis.y) - 1) < TOL
    ]
    if not holes:
        return None
    hole = holes[0]
    offset = hole.Center - origin
    angle = -math.degrees(math.atan2(-offset.x, -offset.z))
    normalised = []
    for shape in (seat, keeper):
        candidate = translated_shape(shape, -origin.x, -origin.y, -origin.z)
        candidate.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
        normalised.append(candidate)
    return normalised


def keeper_alignment_sensitivity(keeper):
    """Screen prescribed lateral errors against the unmeasured shield envelope.

    The guide pocket is anti-rotation support, not a precision centering datum.
    Tightening the keeper screw does not automatically centre its opening.
    """
    shield = Part.makeCylinder(2.7, 8, App.Vector(0, -3, 0), App.Vector(0, 1, 0))
    rows = []
    for offset in (0.0, 0.05, 0.1, 0.2, 0.25):
        collisions = [
            intersection_volume(translated_shape(keeper, x=dx, z=dz), shield)
            for dx, dz in ((offset, 0), (-offset, 0), (0, offset), (0, -offset))
        ]
        rows.append(
            {
                "prescribed_radial_offset_mm": offset,
                "nominal_radial_gap_mm": round(2.8 - 2.7 - offset, 8),
                "positive_nominal_gap": 2.8 - 2.7 - offset > TOL,
                "maximum_hypothetical_shield_penetration_mm3": max(collisions),
                "all_cardinal_offsets_clear": max(collisions) < TOL,
            }
        )
    by_offset = {row["prescribed_radial_offset_mm"]: row for row in rows}
    return {
        "cases": rows,
        "nominal_shield_envelope_overlap_mm3": by_offset[0.0][
            "maximum_hypothetical_shield_penetration_mm3"
        ],
        "scope": "Cardinal relative-error sensitivity only. Ø5.4 shield envelope is unmeasured. The nominal diameter-6 seat has no designed bearing radial allowance; its finished physical fit must still be checked. The 0.10 mm keeper guide allowance alone can consume the 0.10 mm nominal shield gap. The guide does not automatically align the aperture. Non-overlap at 0.10 mm is mathematical tangency, not positive clearance or physical qualification. Align the aperture, inspect the actual ring land and shield, then check free rotation at both axial limits after tightening. Manufacturing error, loaded displacement and actual ring geometry remain unqualified.",
        "passed": by_offset[0.0]["all_cardinal_offsets_clear"]
        and by_offset[0.05]["all_cardinal_offsets_clear"]
        and not by_offset[0.2]["all_cardinal_offsets_clear"],
    }


def keeper_backing_check(seat, keeper):
    """Screen the saved symmetric backing and remaining frame load paths.

    These independent witnesses establish material continuity, not stiffness
    or strength. The lower screw stays outside the rotating carrier envelope.
    """
    backing = box(8.8, 3.3, 8.8, (-4.4, -1.9, -13.9))
    side_paths = union([box(1.8, 3.3, 16.3, (x, -1.9, -21.4)) for x in (-4.4, 2.6)])
    frame_back = box(8.8, 2.3, 8.8, (-4.4, 1.6, -13.9))
    frame_sides = union([box(1.6, 5.8, 8.8, (x, -1.9, -13.9)) for x in (-6.4, 4.8)])
    mirrored = keeper.mirror(App.Vector(), App.Vector(1, 0, 0))
    report = {
        "missing_continuous_keeper_backing_mm3": backing.cut(keeper).Volume,
        "missing_keeper_to_screw_side_paths_mm3": side_paths.cut(keeper).Volume,
        "missing_frame_backing_mm3": frame_back.cut(seat).Volume,
        "missing_frame_side_walls_mm3": frame_sides.cut(seat).Volume,
        "keeper_lateral_asymmetry_mm3": keeper.cut(mirrored).Volume
        + mirrored.cut(keeper).Volume,
        "scope": "Saved nominal geometry. A 3.5 mm thick, 9 mm wide backing extends to 5 mm below the bearing axis, reducing the unsupported thin section without changing its front stop plane or adding hardware. Two continuous side paths join the backing to the lower screw foot. The frame retains side walls and a rear wall outside the deeper open pocket. These material witnesses are not structural, fatigue, creep or physical-fit qualification; the one lower screw still gives an offset axial load path.",
    }
    report["passed"] = all(
        value < TOL for key, value in report.items() if key.endswith("_mm3")
    )
    return report


def bearing_stack_check(
    bearing, shaft, seat, carrier, keeper, *, toward_travel, away_travel
):
    """Check actual solids with this bearing's outboard direction along +Y.

    Neither the carrier nor a spacer retains the bearing. The independently
    verified carrier/frame stops bound carrier motion; the bearing itself is
    captured by a removable outer-ring keeper and one outboard shoulder.
    Carrier/shaft translation is bounded by [-away_travel, +toward_travel]
    in this normalized frame; unequal stop clearances are permitted.
    """
    if any(
        shape.isNull() or not shape.isValid()
        for shape in (bearing, shaft, seat, carrier, keeper)
    ):
        return {"passed": False, "error": "Missing or invalid bearing-stack solid"}
    if any(
        value is None or not math.isfinite(value) or value < 0
        for value in (toward_travel, away_travel)
    ):
        return {"passed": False, "error": "Unproven carrier axial stop"}
    bounds = bearing.optimalBoundingBox(False, False)
    x, z = bounds.Center.x, bounds.Center.z
    origin = App.Vector(x, bounds.YMin, z)
    expected = _annulus(1.5, 3.0, bounds.YMin, 2.5, x, z)
    comparison = geometry_comparison(bearing, expected)
    shaft_bounds = shaft.optimalBoundingBox(False, False)
    axis_error = math.hypot(shaft_bounds.Center.x - x, shaft_bounds.Center.z - z)
    inward = -bearing_retention.KEEPER_STOP_Y
    bearing_interval = [bounds.YMin - inward, bounds.YMax]
    shaft_coverage = min(bounds.YMax, shaft_bounds.YMax - away_travel) - max(
        bounds.YMin - inward, shaft_bounds.YMin + toward_travel
    )
    shaft_journal = any(
        type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - 1.5) < TOL
        and abs(abs(face.Surface.Axis.y) - 1) < TOL
        and math.hypot(face.Surface.Center.x - x, face.Surface.Center.z - z) < TOL
        and face.BoundBox.YMin <= bounds.YMin - inward - toward_travel + TOL
        and face.BoundBox.YMax >= bounds.YMax + away_travel - TOL
        for face in shaft.Faces
    )

    normalised = _normalise_capture(seat, keeper, origin)
    if normalised is None:
        return {"passed": False, "error": "Missing keeper screw-hole registration"}
    normalised_seat, normalised_keeper = normalised
    capture = bearing_retention.geometry_check(normalised_seat, normalised_keeper)
    backing = keeper_backing_check(normalised_seat, normalised_keeper)
    # A continuous annular witness excludes the assumed shield region. This
    # is only a design envelope; the delivered outer-ring land needs inspection.
    stop_slice = _annulus(2.81, 2.99, bounds.YMin - inward - 0.01, 0.01, x, z)
    contact_area = keeper.common(stop_slice).Volume / 0.01
    outer_shoulder = _annulus(2.81, 2.99, 2.51, 1.48)
    missing_shoulder = abs(outer_shoulder.cut(normalised_seat).Volume)
    bore = Part.makeCylinder(
        bearing_retention.SEAT_RADIUS,
        2.5 + inward,
        App.Vector(0, -inward, 0),
        App.Vector(0, 1, 0),
    )
    missing_bore = abs(bore.common(normalised_seat).Volume)
    guide_wall = _annulus(
        bearing_retention.SEAT_RADIUS + 0.01, 3.3, -inward, 2.5 + inward
    )
    missing_guide = abs(guide_wall.cut(normalised_seat).Volume)

    travel = _annulus(1.5, 3.0, bounds.YMin - inward, 2.5 + inward, x, z)
    overlaps = {
        "bearing_seat_overlap_mm3": intersection_volume(bearing, seat),
        "bearing_shaft_overlap_mm3": intersection_volume(bearing, shaft),
        "bearing_travel_seat_overlap_mm3": intersection_volume(travel, seat)
        + intersection_volume(travel, keeper),
    }
    # The caller verifies each carrier stop independently. Only travel toward
    # this bearing reduces the face clearance; neither stop retains the bearing.
    carrier_end = carrier.optimalBoundingBox(False, False).YMax
    carrier_gap = bounds.YMin - inward - carrier_end - toward_travel
    return {
        "stock_shape_comparison": comparison,
        "shaft_axis_error_mm": axis_error,
        "nominal_3mm_journal_covers_bearing_and_carrier_motion": shaft_journal,
        "minimum_shaft_coverage_over_bearing_motion_mm": shaft_coverage,
        "bearing_motion_interval_y_mm": bearing_interval,
        "maximum_bearing_inward_travel_mm": inward,
        "maximum_bearing_outward_travel_mm": 0.0,
        "carrier_travel_toward_bearing_mm": toward_travel,
        "carrier_travel_away_from_bearing_mm": away_travel,
        "minimum_carrier_to_bearing_face_gap_mm": carrier_gap,
        "keeper_outer_ring_contact_area_mm2": contact_area,
        "bearing_bore_intrusion_mm3": missing_bore,
        "missing_complete_guide_wall_mm3": missing_guide,
        "missing_complete_outer_shoulder_mm3": missing_shoulder,
        "capture_geometry": capture,
        "keeper_backing": backing,
        **overlaps,
        "scope": "Saved nominal solids. A rigid removable keeper and rear shoulder contact only the assumed outer-ring land. The keeper clamps against the frame, leaving 0.5 mm nominal bearing endplay. The nominal diameter-6 radial bore has no designed clearance or interference; finish the production coupon for hand insertion without rocking and reprint an oversized bore. Actual bore finishing, ring-land compatibility, free rotation, screw retention, wear and loaded fit remain unqualified. The carrier is independently bounded by assembled frame/keeper stops.",
        "passed": comparison["difference_mm3"] < TOL
        and axis_error < TOL
        and shaft_journal
        and shaft_coverage >= 2.5 + inward - TOL
        and contact_area > 3.0
        and capture["passed"]
        and backing["passed"]
        and missing_bore < TOL
        and missing_guide < TOL
        and missing_shoulder < TOL
        and carrier_gap >= 1.5 - TOL
        and all(value < TOL for value in overlaps.values()),
    }
