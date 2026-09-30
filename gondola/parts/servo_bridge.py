"""A removable paired-servo wall on one flat, openly supported plate.

All dimensions are millimetres. The common wall has thick outer columns and
a shared central web. Broad straight arms connect the central plate to two
mounting seats, all on one plane with unilateral X/Y locating faces.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import box, mirrored_y, union
from gondola.contracts.drive import SELECTED_DRIVE

from . import rail, servo_envelope
from .servo_envelope import case_front_y as case_front_y

V = App.Vector
MOUNT_DEPTH = 5.0
# The bought case is not a locating datum. Clearance around its nominal 7 x20
# section also accommodates the published +/-0.2 mm case-size tolerance.
CASE_CLEARANCE = 0.5
CASE_WINDOW_WIDTH = servo_envelope.CASE_WIDTH + 2 * CASE_CLEARANCE
CASE_WINDOW_HEIGHT = servo_envelope.CASE_LENGTH + 2 * CASE_CLEARANCE
SIDE_WALL = 3.0
CRADLE_WIDTH = CASE_WINDOW_WIDTH + 2 * SIDE_WALL
REAR_LEAD_ALLOWANCE = 13.9
SEAT_Z = 11.4
CONNECTOR_PLATE_BOTTOM_Z, CONNECTOR_PLATE_THICKNESS = SEAT_Z, 2.0
FRAME_SEAT_THICKNESS = 3.0
NUT_SEAT_Z = SEAT_Z - FRAME_SEAT_THICKNESS
MOUNT_BOLT_SEAT_Z = SEAT_Z + CONNECTOR_PLATE_THICKNESS
PAD_INNER_X, PAD_OUTER_X = 3.9, 19.5
PAD_INNER_Y, PAD_OUTER_Y = 13.5, 26.0
CONNECTOR_PLATE_HALF_WIDTH = PAD_OUTER_X
CONNECTOR_ARM_OVERLAP = 3.0
MOUNT_HOLE_DIAMETER = 2.2
BOLT_X, BOLT_Y = 14.5, 18.0
MOUNT_GRIP = MOUNT_BOLT_SEAT_Z - NUT_SEAT_Z


def opposite(shape):
    return mirrored_y(shape.mirror(V(), V(1, 0, 0)), -1)


def bulkhead_width(drive=SELECTED_DRIVE):
    return 2 * drive.input_x_mm + CRADLE_WIDTH


def _ear_clearance(drive):
    x, z = drive.input_x_mm, drive.input_z_mm
    start_y = servo_envelope.ear_seat_y() - MOUNT_DEPTH - 1
    cuts = []
    for centre_z, opening in zip(servo_envelope.EAR_CENTRES_Z, (1, -1)):
        hole_z = z + centre_z
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
    z = drive.input_z_mm
    y = servo_envelope.ear_seat_y() - MOUNT_DEPTH
    if abs(y + MOUNT_DEPTH / 2) > 1e-7:
        raise ValueError("Paired servo ears must share the central mounting wall")
    width = bulkhead_width(drive)
    return box(
        width,
        MOUNT_DEPTH,
        z + 10.1 - CONNECTOR_PLATE_BOTTOM_Z,
        (-width / 2, y, CONNECTOR_PLATE_BOTTOM_Z),
    )


def cut_mounting_holes(shape):
    for sign in (-1, 1):
        shape = shape.cut(
            Part.makeCylinder(
                MOUNT_HOLE_DIAMETER / 2,
                14,
                V(sign * BOLT_X, sign * BOLT_Y, 1),
                V(0, 0, 1),
            )
        )
    return shape.removeSplitter()


def bridge_blank(drive=SELECTED_DRIVE):
    """Broad central support and two straight arms before functional openings.

    This stock also conservatively bounds the complete printed bridge during
    module removal. The side openings are real open edges, not enclosed holes.
    """
    cradle = _cradle_blank(drive)
    width = bulkhead_width(drive)
    central_plate = box(
        width,
        rail.SHOE_WIDTH,
        CONNECTOR_PLATE_THICKNESS,
        (-width / 2, -rail.SHOE_WIDTH / 2, CONNECTOR_PLATE_BOTTOM_Z),
    )
    arm_start_y = rail.SHOE_WIDTH / 2 - CONNECTOR_ARM_OVERLAP
    arm = box(
        PAD_OUTER_X - PAD_INNER_X,
        PAD_OUTER_Y - arm_start_y,
        CONNECTOR_PLATE_THICKNESS,
        (PAD_INNER_X, arm_start_y, CONNECTOR_PLATE_BOTTOM_Z),
    )
    return union([cradle, central_plate, arm, opposite(arm)])


def bridge_shape(drive=SELECTED_DRIVE):
    x, z = drive.input_x_mm, drive.input_z_mm
    y = servo_envelope.ear_seat_y() - MOUNT_DEPTH
    window = box(
        CASE_WINDOW_WIDTH,
        MOUNT_DEPTH + 2,
        CASE_WINDOW_HEIGHT,
        (
            x - CASE_WINDOW_WIDTH / 2,
            y - 1,
            z + servo_envelope.CASE_CENTRE_Z - CASE_WINDOW_HEIGHT / 2,
        ),
    )
    bridge = bridge_blank(drive).cut(window).cut(opposite(window))
    # Retain the sourced ear axes and their open necks into the body windows.
    void = _ear_clearance(drive)
    bridge = bridge.cut(void).cut(opposite(void))
    # Remove front horn nuts/adapter on the detached servo module; rear screws
    # stay in the horn until the servo is free. Keep the side columns solid;
    # the former rear tool-relief scallops are no longer needed.
    # The plate sits above the complete rail-key elbow; its arms stand outside
    # the rail screw head. Neither needs a tunnel, roof notch or thin ring.
    # The lower servo nut also clears the plate, including its removal path.
    # Heads sit directly on the 2 mm plate; the 3 mm frame seats preserve
    # the existing M2x8 screws and 5 mm grip without stepped feet or counterbores.
    return cut_mounting_holes(bridge)


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
            # The negative outer edge locates Y without an opposed-face trap.
            # The old inner stop would occupy the now-flat connecting arm.
            box(width, 1.5, 5, (-PAD_OUTER_X, -PAD_OUTER_Y - 1.5, NUT_SEAT_Z)),
            # An outside X stop releases directly during the checked +X slide.
            box(
                2,
                3,
                CONNECTOR_PLATE_BOTTOM_Z + CONNECTOR_PLATE_THICKNESS - NUT_SEAT_Z,
                (-CONNECTOR_PLATE_HALF_WIDTH - 2, -24, NUT_SEAT_Z),
            ),
        ]
    )


def contact_planes():
    """Complete nominal contacts, with separate XY bounds for each Z support.

    A coplanar central face must not hide a missing outer seat. The optional
    region is (X start, Y start, X size, Y size) in the propulsion frame.
    """
    width = PAD_OUTER_X - PAD_INNER_X
    length = PAD_OUTER_Y - PAD_INNER_Y
    seat_area = width * length - math.pi * (MOUNT_HOLE_DIAMETER / 2) ** 2
    return (
        (
            "positive_outer_seat",
            2,
            SEAT_Z,
            seat_area,
            (PAD_INNER_X, PAD_INNER_Y, width, length),
        ),
        (
            "negative_outer_seat",
            2,
            SEAT_Z,
            seat_area,
            (-PAD_OUTER_X, -PAD_OUTER_Y, width, length),
        ),
        (
            "central_bulkhead_support",
            2,
            SEAT_Z,
            rail.SHOE_LENGTH * rail.SHOE_WIDTH,
            (
                -rail.SHOE_LENGTH / 2,
                -rail.SHOE_WIDTH / 2,
                rail.SHOE_LENGTH,
                rail.SHOE_WIDTH,
            ),
        ),
        (
            "outside_y_datum",
            1,
            -PAD_OUTER_Y,
            width * CONNECTOR_PLATE_THICKNESS,
            None,
        ),
        (
            "outside_x_datum",
            0,
            -CONNECTOR_PLATE_HALF_WIDTH,
            3 * CONNECTOR_PLATE_THICKNESS,
            None,
        ),
    )
