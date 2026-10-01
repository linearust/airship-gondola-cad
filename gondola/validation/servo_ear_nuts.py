"""Actual shallow servo-ear nut seats, independent of the pocket builder.

The open ear passage still permits assembly. Capture prevents nominal nut
rotation, not axial loss, loosening, or an unqualified tightening torque.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import mirrored_y, world_shape

from .geometry import TOL, translation_sweep

V = App.Vector


def _hex(af, y, length, z):
    radius = af / math.sqrt(3)
    points = [
        V(radius * math.cos(math.radians(a)), y, z + radius * math.sin(math.radians(a)))
        for a in range(0, 360, 60)
    ]
    return Part.Face(Part.makePolygon(points + [points[0]])).extrude(V(0, length, 0))


def _nut_size_range_check(bridge, z):
    """Independent DIN 934 size bounds, not a measured purchased-lot claim.

    Axial insertion is swept continuously. Transverse clearance and rotation
    stops are sampled at centre and eight points on the nominal 0.1mm float
    boundary; neither friction nor the received nut's chamfer is inferred.
    """
    offsets = [(0.0, 0.0)] + [
        (0.1 * math.cos(i * math.pi / 4), 0.1 * math.sin(i * math.pi / 4))
        for i in range(8)
    ]
    maximum = _hex(3.2, -2.0, -1.3, z)
    minimum = _hex(3.02, -2.0, -1.05, z)
    fits, stops = [], []
    for dx, dz in offsets:
        nut = maximum.copy()
        nut.translate(V(dx, 0, dz))
        swept, method = translation_sweep(nut, (0, -2, 0))
        overlap = abs(swept.common(bridge).Volume)
        fits.append(
            {
                "axis_offset_xz_mm": [dx, dz],
                "maximum_nut_insertion_removal_overlap_mm3": overlap,
                "method": method,
                "passed": overlap < TOL,
            }
        )
        for angle in (-30, 30):
            nut = minimum.copy()
            nut.rotate(V(0, 0, z), V(0, 1, 0), angle)
            nut.translate(V(dx, 0, dz))
            block = abs(nut.common(bridge).Volume)
            stops.append(
                {
                    "axis_offset_xz_mm": [dx, dz],
                    "attempted_rotation_deg": angle,
                    "rotation_stop_penetration_mm3": block,
                    "passed": block > TOL,
                }
            )
    return {
        "maximum_nut_af_height_mm": [3.2, 1.3],
        "minimum_nut_af_height_mm": [3.02, 1.05],
        "sampled_axis_float_radius_mm": 0.1,
        "maximum_nut_free_insertion": fits,
        "minimum_nut_rotation_stops": stops,
        "passed": all(row["passed"] for row in fits + stops),
    }


def servo_ear_nut_check(doc, prefix):
    """Measure both installed nuts in their servo-axis frame, including parents."""
    names = ["ServoDriveBridge", prefix + "ServoMount"] + [
        prefix + "ServoEar" + side + "Nut" for side in ("Lower", "Upper")
    ]
    missing = [name for name in names if doc.getObject(name) is None]
    if missing:
        return {"passed": False, "missing_parts": missing, "pod": prefix}
    mount = doc.getObject(prefix + "ServoMount")
    inverse = mount.getGlobalPlacement().inverse()

    def local(name):
        shape = world_shape(doc.getObject(name))
        shape.Placement = inverse.multiply(shape.Placement)
        return mirrored_y(shape, -1) if prefix == "Starboard" else shape

    bridge = local("ServoDriveBridge")
    rows = []
    for side, z, opening in (("Lower", -17.0, 1), ("Upper", 7.0, -1)):
        nut = local(prefix + "ServoEar" + side + "Nut")
        expected = _hex(3.2, -2.0, -1.3, z).cut(
            Part.makeCylinder(0.8, 1.5, V(0, -3.4, z), V(0, 1, 0))
        )
        bore = Part.makeCylinder(1.1, 4.7, V(0, -2.1, z), V(0, 1, 0))
        slot = Part.makeBox(2.2, 4.7, 2.2, V(-1.1, -2.1, z if opening > 0 else z - 2.2))
        floor = _hex(3.4, -2.0, 4.5, z).cut(bore).cut(slot)
        seat = _hex(3.2, -2.0, 0.05, z).cut(bore).cut(slot)
        # Preserve a full 1.5mm outer rim opposite the intentional case-side
        # opening, including the shallow rear capture layer.
        rim = Part.makeBox(
            3.4, 0.5, 1.5, V(-1.7, -2.5, z + 1.7 if opening < 0 else z - 3.2)
        )
        rotated = nut.copy()
        rotated.rotate(V(0, 0, z), V(0, 1, 0), 30)
        shape_difference = abs(nut.cut(expected).Volume) + abs(expected.cut(nut).Volume)
        overlap = abs(nut.common(bridge).Volume)
        missing_floor = abs(floor.cut(bridge).Volume)
        missing_seat = abs(seat.cut(bridge).Volume)
        missing_rim = abs(rim.cut(bridge).Volume)
        rotation_block = abs(rotated.common(bridge).Volume)
        size_range = _nut_size_range_check(bridge, z)
        rows.append(
            {
                "nut": prefix + "ServoEar" + side + "Nut",
                "capture_depth_mm": 0.5,
                "retained_wall_floor_mm": 4.5,
                "nut_shape_difference_mm3": shape_difference,
                "nut_print_intersection_mm3": overlap,
                "missing_floor_mm3": missing_floor,
                "missing_seat_mm3": missing_seat,
                "missing_outer_rim_mm3": missing_rim,
                "required_bearing_area_mm2": seat.Volume / 0.05,
                "nut_30deg_rotation_block_mm3": rotation_block,
                "nut_size_range": size_range,
                "passed": max(
                    shape_difference, overlap, missing_floor, missing_seat, missing_rim
                )
                < TOL
                and rotation_block > 0.01
                and size_range["passed"],
            }
        )
    return {
        "pod": prefix,
        "cases": rows,
        "nut_axially_captive": False,
        "scope": "AF3.4 by 0.5mm rear seats with 4.5mm remaining wall and open ear passages. DIN934 comparison bounds are AF3.02..3.2 and height1.05..1.3mm; no purchased-lot certification. Maximum nuts have continuously swept axial release at sampled transverse offsets; minimum nuts are blocked at both30deg attempts. These ideal sharp-hex checks do not establish all-angle restraint or actual chamfer engagement. Remove screws first on the bench, then lift nuts from the pockets. Finish for free insertion and full seating; actual clearance, shallow flanks and torque retention require a production-process fit check.",
        "passed": all(row["passed"] for row in rows),
    }
