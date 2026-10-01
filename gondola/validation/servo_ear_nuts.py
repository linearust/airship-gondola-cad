"""Actual shallow servo-ear nut seats, independent of the pocket builder.

The open ear passage still permits assembly. Capture prevents nominal nut
rotation, not axial loss, loosening, or an unqualified tightening torque.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import mirrored_y, world_shape

from .geometry import TOL

V = App.Vector


def _hex(af, y, length, z):
    radius = af / math.sqrt(3)
    points = [
        V(radius * math.cos(math.radians(a)), y, z + radius * math.sin(math.radians(a)))
        for a in range(0, 360, 60)
    ]
    return Part.Face(Part.makePolygon(points + [points[0]])).extrude(V(0, length, 0))


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
                "passed": max(
                    shape_difference, overlap, missing_floor, missing_seat, missing_rim
                )
                < TOL
                and rotation_block > 0.01,
            }
        )
    return {
        "pod": prefix,
        "cases": rows,
        "nut_axially_captive": False,
        "scope": "Nominal AF3.2 M1.6 nuts in AF3.4 by 0.5mm rear seats, with 4.5mm remaining wall and open ear passages. Remove screws first on the bench, then lift nuts from the pockets. Actual nut chamfers, finished clearance, shallow flank engagement and torque retention require a production-process fit check.",
        "passed": all(row["passed"] for row in rows),
    }
