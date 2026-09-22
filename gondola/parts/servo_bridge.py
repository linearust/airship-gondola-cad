"""One removable bridge for both servos, with two local seats on a common frame.

All dimensions are millimetres. The outer ring joins the cradles for handling;
each cradle transfers its load through the seat directly beneath it. The
unilateral locating faces are fixed datums, not mesh-adjustment slots.
"""

import FreeCAD as App
import Part

from gondola.cad import box, mirrored_y, union
from gondola.contracts.drive import SELECTED_DRIVE

from . import rail, servo_coupling

V = App.Vector
MOUNT_DEPTH = 5.0
CASE_WINDOW_WIDTH = 8.0
CASE_WINDOW_HEIGHT = 21.0
SIDE_WALL = 2.0
CRADLE_WIDTH = CASE_WINDOW_WIDTH + 2 * SIDE_WALL
SEAT_Z = 8.7
NUT_SEAT_Z = 5.7
PAD_TOP_Z = 10.7
PAD_INNER_X, PAD_OUTER_X = 1.5, 17.5
PAD_INNER_Y, PAD_OUTER_Y = 13.5, 26.0
RING_BOTTOM_Z, RING_THICKNESS = 10.4, 2.0
RING_OUTER_X = 19.5
BOLT_X, BOLT_Y = 14.5, 18.0
MOUNT_GRIP = PAD_TOP_Z - NUT_SEAT_Z


def opposite(shape):
    return mirrored_y(shape.mirror(V(), V(1, 0, 0)), -1)


def case_front_y():
    return servo_coupling.HORN_BOTTOM_Y - 0.2


def _ear_clearance(drive):
    x, z = drive.input_x_mm, drive.input_z_mm
    start_y = case_front_y() - 4.7 - MOUNT_DEPTH - 1
    cuts = []
    for hole_z, opening in ((z - 17, 1), (z + 7, -1)):
        cuts.extend(
            [
                Part.makeCylinder(
                    1.1, MOUNT_DEPTH + 2, V(x, start_y, hole_z), V(0, 1, 0)
                ),
                box(
                    2.2,
                    MOUNT_DEPTH + 2,
                    2.2,
                    (x - 1.1, start_y, hole_z if opening > 0 else hole_z - 2.2),
                ),
            ]
        )
    return union(cuts)


def _cradle_blank(drive):
    x, z = drive.input_x_mm, drive.input_z_mm
    y = case_front_y() - 4.7 - MOUNT_DEPTH
    return box(
        CRADLE_WIDTH, MOUNT_DEPTH, z + 10.1 - SEAT_Z, (x - CRADLE_WIDTH / 2, y, SEAT_Z)
    )


def _mount_holes(shape):
    for sign in (-1, 1):
        shape = shape.cut(
            Part.makeCylinder(1.1, 12, V(sign * BOLT_X, sign * BOLT_Y, 1), V(0, 0, 1))
        )
    return shape.removeSplitter()


def bridge_blank(drive=SELECTED_DRIVE):
    """Planar stock before openings; also a conservative service envelope."""
    cradle = _cradle_blank(drive)
    pad = box(
        PAD_OUTER_X - PAD_INNER_X,
        PAD_OUTER_Y - PAD_INNER_Y,
        PAD_TOP_Z - SEAT_Z,
        (PAD_INNER_X, PAD_INNER_Y, SEAT_Z),
    )
    ring = box(
        2 * RING_OUTER_X,
        2 * PAD_OUTER_Y,
        RING_THICKNESS,
        (-RING_OUTER_X, -PAD_OUTER_Y, RING_BOTTOM_Z),
    ).cut(box(2 * PAD_OUTER_X, 42, 3, (-PAD_OUTER_X, -21, RING_BOTTOM_Z - 0.4)))
    return union([cradle, opposite(cradle), pad, opposite(pad), ring])


def bridge_shape(drive=SELECTED_DRIVE):
    x, z = drive.input_x_mm, drive.input_z_mm
    y = case_front_y() - 4.7 - MOUNT_DEPTH
    window = box(
        CASE_WINDOW_WIDTH,
        MOUNT_DEPTH + 2,
        CASE_WINDOW_HEIGHT,
        (x - CASE_WINDOW_WIDTH / 2, y - 1, z - 5 - CASE_WINDOW_HEIGHT / 2),
    )
    bridge = bridge_blank(drive).cut(window).cut(opposite(window))
    # The connecting bars must not refill either sourced ear hole or its neck.
    void = _ear_clearance(drive)
    bridge = bridge.cut(void).cut(opposite(void))
    # Leave the lower M1.6 nut an open axial passage for assembly and service.
    nut_passage = box(5, 7.5, 2.2, (x - 2.5, PAD_INNER_Y, SEAT_Z - 0.1))
    return _mount_holes(bridge.cut(nut_passage).cut(opposite(nut_passage)))


def frame_seats():
    """Open nut entries and broad pads locating the removable paired drive."""
    width = PAD_OUTER_X - PAD_INNER_X
    seat = union(
        [
            box(
                width,
                PAD_OUTER_Y - PAD_INNER_Y,
                SEAT_Z - NUT_SEAT_Z,
                (PAD_INNER_X, PAD_INNER_Y, NUT_SEAT_Z),
            ),
            box(
                width,
                2,
                NUT_SEAT_Z - rail.SHOE_BOTTOM,
                (PAD_INNER_X, PAD_INNER_Y, rail.SHOE_BOTTOM),
            ),
            box(
                width,
                5.5,
                NUT_SEAT_Z - rail.SHOE_BOTTOM,
                (PAD_INNER_X, 20.5, rail.SHOE_BOTTOM),
            ),
        ]
    )
    return union(
        [
            seat,
            opposite(seat),
            # One inside Y datum avoids the servo ears and an opposed-face
            # tolerance trap. The opposite seat has no competing Y stop.
            box(width, 1.5, 5, (-PAD_OUTER_X, -PAD_INNER_Y, NUT_SEAT_Z)),
            # Put the X stop outside the complete ring: an internal stop would
            # catch the trailing beam during the checked +X removal.
            box(4, 3, 3, (-RING_OUTER_X - 2, -24, NUT_SEAT_Z)),
            box(
                2,
                3,
                RING_BOTTOM_Z + RING_THICKNESS - NUT_SEAT_Z,
                (-RING_OUTER_X - 2, -24, NUT_SEAT_Z),
            ),
        ]
    )


def finish_frame(frame):
    """Keep mounting bores and the original motor-wire corridors open."""
    frame = _mount_holes(frame)
    for sign in (-1, 1):
        frame = frame.cut(
            mirrored_y(box(6.4, 104, 4, (-3.2, rail.SHOE_WIDTH / 2, 4)), sign)
        )
        # The old 4..8 mm wire corridor otherwise leaves a 0.7 mm roof under
        # the new seating plane. Open that small inner strip completely; the
        # broad seat still supports the servo axis and most of the root pad.
        frame = frame.cut(
            mirrored_y(
                box(6.4, PAD_OUTER_Y - PAD_INNER_Y, 1, (-3.2, PAD_INNER_Y, 8)), sign
            )
        )
    return frame.removeSplitter()


def contact_planes():
    # Names, coordinate index, station and deliberately broad minimum contact.
    # The joint validator measures the positive and negative Z seats separately.
    return (
        ("positive_cradle_seat", 2, SEAT_Z, 120.0),
        ("negative_cradle_seat", 2, SEAT_Z, 120.0),
        ("inside_y_datum", 1, -PAD_INNER_Y, 20.0),
        ("outside_x_datum", 0, -RING_OUTER_X, 5.0),
    )
