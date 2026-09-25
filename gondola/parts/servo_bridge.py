"""Two servo openings share one central bulkhead on an open connector plate.

All dimensions are millimetres. The common wall has thick outer columns and
a shared central web. Its supported central plate connects to the two mounting
feet through broad straight arms, leaving the unused side regions open.
"""

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
SEAT_Z = 8.7
NUT_SEAT_Z = 5.7
MOUNT_BOLT_SEAT_Z = 10.7
PAD_INNER_X, PAD_OUTER_X = 3.9, 19.5
PAD_INNER_Y, PAD_OUTER_Y = 13.5, 26.0
CONNECTOR_PLATE_BOTTOM_Z, CONNECTOR_PLATE_THICKNESS = 11.4, 2.0
CONNECTOR_PLATE_HALF_WIDTH = PAD_OUTER_X
CONNECTOR_ARM_OVERLAP = 3.0
MOUNT_HEAD_ACCESS_DIAMETER = 6.0
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
            Part.makeCylinder(1.1, 14, V(sign * BOLT_X, sign * BOLT_Y, 1), V(0, 0, 1))
        )
    return shape.removeSplitter()


def bridge_blank(drive=SELECTED_DRIVE):
    """Broad central support and two straight arms before functional openings.

    This stock also conservatively bounds the complete printed bridge during
    module removal. The side openings are real open edges, not enclosed holes.
    """
    cradle = _cradle_blank(drive)
    pad = box(
        PAD_OUTER_X - PAD_INNER_X,
        PAD_OUTER_Y - PAD_INNER_Y,
        CONNECTOR_PLATE_BOTTOM_Z - SEAT_Z,
        (PAD_INNER_X, PAD_INNER_Y, SEAT_Z),
    )
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
    return union([cradle, central_plate, arm, opposite(arm), pad, opposite(pad)])


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
    # Horn screws now withdraw from the gear side. Keep the side columns solid;
    # the former rear tool-relief scallops are no longer needed.
    # The plate sits above the complete rail-key elbow; its feet stand outside
    # the rail screw head. Neither needs a tunnel, roof notch or thin ring.
    # The lower servo nut also clears the plate, including its removal path.
    # Open top counterbores preserve the existing M2x8 screw seat and grip.
    for sign in (-1, 1):
        bridge = bridge.cut(
            Part.makeCylinder(
                MOUNT_HEAD_ACCESS_DIAMETER / 2,
                CONNECTOR_PLATE_BOTTOM_Z
                + CONNECTOR_PLATE_THICKNESS
                - MOUNT_BOLT_SEAT_Z
                + 0.1,
                V(sign * BOLT_X, sign * BOLT_Y, MOUNT_BOLT_SEAT_Z),
                V(0, 0, 1),
            )
        )
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
            # One inside Y datum avoids the servo ears and an opposed-face
            # tolerance trap. The opposite seat has no competing Y stop.
            box(width, 1.5, 5, (-PAD_OUTER_X, -PAD_INNER_Y, NUT_SEAT_Z)),
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
    # Names, coordinate index, station and deliberately broad minimum contact.
    # The joint validator measures the positive and negative Z seats separately.
    return (
        ("positive_cradle_seat", 2, SEAT_Z, 120.0),
        ("negative_cradle_seat", 2, SEAT_Z, 120.0),
        ("inside_y_datum", 1, -PAD_INNER_Y, 20.0),
        ("outside_x_datum", 0, -CONNECTOR_PLATE_HALF_WIDTH, 5.0),
        ("central_bulkhead_support", 2, CONNECTOR_PLATE_BOTTOM_Z, 300.0),
    )
