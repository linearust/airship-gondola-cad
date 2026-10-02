"""Independent saved-solid proof of two inboard split-housing bearings."""

import math

import FreeCAD as App
import Part

from gondola.cad import box, translated_shape, union
from gondola.print_export import geometry_comparison

from .geometry import intersection_volume

TOL = 1e-5


def split_cap_seating_check(frame, cap):
    """Require the split cap to bottom on continuous stock beside both seats."""
    witnesses = []
    for sign in (-1, 1):
        start = -8.5 if sign < 0 else 3.5
        patch = Part.Face(
            Part.makePolygon(
                [
                    App.Vector(x, y, 50)
                    for x, y in (
                        (start, 25.5),
                        (start + 5, 25.5),
                        (start + 5, 43.5),
                        (start, 43.5),
                        (start, 25.5),
                    )
                ]
            )
        )
        hole = Part.Face(
            Part.Wire(
                Part.makeCircle(
                    1.11, App.Vector(sign * 5.5, 34.5, 50), App.Vector(0, 0, 1)
                )
            )
        )
        witnesses.append(patch.cut(hole))
    witness = Part.makeCompound(witnesses)
    keys = union([box(3, 3, 1.5, (x, 28, 50)) for x in (-9, 6)]).cut(
        Part.makeCylinder(2.8, 20, App.Vector(0, 24, 50), App.Vector(0, 1, 0))
    )
    witness = witness.cut(keys)
    frame_faces = Part.makeCompound(
        [
            face
            for face in frame.Faces
            if type(face.Surface).__name__ == "Plane"
            and abs(face.CenterOfMass.z - 50) < TOL
            and face.normalAt(0, 0).z > 0.99
        ]
    )
    cap_faces = Part.makeCompound(
        [
            face
            for face in cap.Faces
            if type(face.Surface).__name__ == "Plane"
            and abs(face.CenterOfMass.z - 50) < TOL
            and face.normalAt(0, 0).z < -0.99
        ]
    )
    missing_frame = witness.cut(frame_faces).Area
    missing_cap = witness.cut(cap_faces).Area
    missing_keys = abs(keys.cut(frame).Volume)
    shifts = [
        intersection_volume(translated_shape(cap, x=x, y=y), frame)
        for x, y in ((0.05, 0), (-0.05, 0), (0, 0.05), (0, -0.05))
    ]
    return {
        "hard_seat_z_mm": 50.0,
        "hard_seat_witness_area_mm2": witness.Area,
        "missing_frame_seat_area_mm2": missing_frame,
        "missing_cap_seat_area_mm2": missing_cap,
        "missing_side_key_stock_mm3": missing_keys,
        "hypothetical_misregistration_penetration_mm3": shifts,
        "scope": "Two broad coplanar side lands must seat at the bearing centre plane before tightening. Only the actual vertical screw bores are removed from the independent witness. This checks hard seating, not preload or printed flatness.",
        "passed": missing_frame < TOL
        and missing_cap < TOL
        and missing_keys < TOL
        and min(shifts) > TOL,
    }


def split_bearing_stack_check(
    bearing, shaft, frame, cap, *, centre_y, negative_travel, positive_travel
):
    """Verify one bought bearing in a split inboard housing, in +Y coordinates.

    The housing's two halves meet at the shaft plane Z50. Each nominal 2.5 mm
    bearing has a 3 mm long radial seat, leaving 0.25 mm at each axial end.
    Shaft/carrier float is independently bounded by the rotor stops. None of
    these nominal rigid checks establishes clamp preload or physical fit.
    """
    if any(
        shape.isNull() or not shape.isValid() or not shape.Solids
        for shape in (bearing, shaft, frame, cap)
    ):
        return {"passed": False, "error": "Missing or invalid split bearing solid"}
    if centre_y not in (28.0, 41.0):
        return {"passed": False, "error": "Unknown inboard bearing station"}
    if any(
        value is None or not math.isfinite(value) or value < 0
        for value in (negative_travel, positive_travel)
    ):
        return {"passed": False, "error": "Unproven carrier axial stop"}
    expected = _annulus(1.5, 3.0, centre_y - 1.25, 2.5, z=50)
    comparison = geometry_comparison(bearing, expected)
    support = union([frame, cap])
    low, high = centre_y - 1.5, centre_y + 1.5
    travel = _annulus(1.5, 3.0, low, 3.0, z=50)
    guide = _annulus(3.01, 3.3, low, 3.0, z=50)
    shoulders = [
        _annulus(2.81, 2.99, start, 1.48, z=50) for start in (low - 1.49, high + 0.01)
    ]
    shield = Part.makeCylinder(
        2.8, 6.0, App.Vector(0, low - 1.5, 50), App.Vector(0, 1, 0)
    )
    missing_guide = abs(guide.cut(support).Volume)
    missing_shoulders = [abs(witness.cut(support).Volume) for witness in shoulders]
    bounds = shaft.optimalBoundingBox(False, False)
    axis_error = math.hypot(bounds.Center.x, bounds.Center.z - 50)
    shaft_coverage = min(high, bounds.YMax - negative_travel) - max(
        low, bounds.YMin + positive_travel
    )
    journal = any(
        type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - 1.5) < TOL
        and abs(abs(face.Surface.Axis.y) - 1) < TOL
        and math.hypot(face.Surface.Center.x, face.Surface.Center.z - 50) < TOL
        and face.BoundBox.YMin <= low - positive_travel + TOL
        and face.BoundBox.YMax >= high + negative_travel - TOL
        for face in shaft.Faces
    )
    journal_witness = Part.makeCylinder(
        1.5,
        3.0 + negative_travel + positive_travel,
        App.Vector(0, low - positive_travel, 50),
        App.Vector(0, 1, 0),
    )
    missing_journal = abs(journal_witness.cut(shaft).Volume)
    journal = journal and missing_journal < TOL
    overlaps = {
        "bearing_housing_overlap_mm3": intersection_volume(bearing, support),
        "bearing_shaft_overlap_mm3": intersection_volume(bearing, shaft),
        "bearing_travel_housing_overlap_mm3": intersection_volume(travel, support),
        "shield_passage_intrusion_mm3": intersection_volume(shield, support),
        "cap_frame_overlap_mm3": intersection_volume(cap, frame),
    }
    return {
        "stock_shape_comparison": comparison,
        "bearing_centre_y_mm": centre_y,
        "bearing_seat_y_range_mm": [low, high],
        "bearing_endplay_each_direction_mm": 0.25,
        "shaft_axis_error_mm": axis_error,
        "nominal_3mm_journal_covers_bearing_and_carrier_motion": journal,
        "missing_complete_round_journal_mm3": missing_journal,
        "minimum_shaft_coverage_over_bearing_motion_mm": shaft_coverage,
        "missing_complete_guide_wall_mm3": missing_guide,
        "missing_inner_shoulder_mm3": missing_shoulders[0],
        "missing_outer_shoulder_mm3": missing_shoulders[1],
        "assumed_shield_diameter_mm": 5.4,
        "shield_passage_diameter_mm": 5.6,
        **overlaps,
        "scope": "Actual saved 3x6x2.5 bearing, continuous diameter-6 split radial seat and two complete outer-ring shoulder witnesses. The cap seats on the fixed housing, leaving 0.5 mm total nominal bearing endplay. Shaft journal coverage includes both independent bearing float and rotor axial travel. Diameter-6 radial fit, actual ring/shield geometry, cap preload, alignment, strength and free rotation require the production coupon and received hardware; the 5.4 mm shield envelope is unmeasured.",
        "passed": comparison["difference_mm3"] < TOL
        and axis_error < TOL
        and journal
        and shaft_coverage >= 3.0 - TOL
        and missing_guide < TOL
        and all(value < TOL for value in missing_shoulders)
        and all(value < TOL for value in overlaps.values()),
    }


def _annulus(inner, outer, start_y, length, x=0, z=0):
    axis = App.Vector(0, 1, 0)
    origin = App.Vector(x, start_y, z)
    return Part.makeCylinder(outer, length, origin, axis).cut(
        Part.makeCylinder(inner, length, origin, axis)
    )
