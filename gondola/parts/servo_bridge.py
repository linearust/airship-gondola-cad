"""Replaceable paired-servo saddle with two opposed shared rail clamps.

A broad roof seats on the output frame and two short side guides form an open
U saddle. Half-turn paired M3 cheeks distribute the clamp load at 34 mm spacing.
No blind keys trap the module; bench removal requires clearing the driven shafts.
"""

import FreeCAD as App
import Part

from gondola.cad import box, mirrored_y, union
from gondola.contracts.drive import SELECTED_DRIVE
from gondola.contracts.rail_attachments import PROPULSION_ATTACHMENT

from . import rail, servo_envelope
from .servo_envelope import case_front_y as case_front_y

V = App.Vector
MOUNT_DEPTH = 5.0
CASE_CLEARANCE = 0.5
CASE_WINDOW_WIDTH = servo_envelope.CASE_WIDTH + 2 * CASE_CLEARANCE
CASE_WINDOW_HEIGHT = servo_envelope.CASE_LENGTH + 2 * CASE_CLEARANCE
SIDE_WALL = 3.0
CRADLE_WIDTH = CASE_WINDOW_WIDTH + 2 * SIDE_WALL
REAR_LEAD_ALLOWANCE = 13.9
SEAT_Z = 12.5
CONNECTOR_PLATE_BOTTOM_Z, CONNECTOR_PLATE_THICKNESS = SEAT_Z, 2.0
FRAME_BOTTOM_Z = 2.2
CENTRAL_SEAT_LENGTH, CENTRAL_SEAT_WIDTH = 18.0, 22.0
CLAMP_AXIS_X = PROPULSION_ATTACHMENT.half_spacing_mm
CHEEK_START_X, CHEEK_END_X = 9.0, 29.0
CHEEK_THICKNESS = PROPULSION_ATTACHMENT.extra_cheek_mm
CHEEK_CONTACT_Y = rail.MOUNT_OUTER_Y
CHEEK_OUTER_Y = CHEEK_CONTACT_Y - CHEEK_THICKNESS
GUIDE_CLEARANCE = 0.2
GUIDE_INNER_Y = CENTRAL_SEAT_WIDTH / 2 + GUIDE_CLEARANCE
GUIDE_OUTER_Y = GUIDE_INNER_Y + 2.0
GUIDE_BOTTOM_Z = 8.0
ROOF_HALF_LENGTH = 19.0
SHARED_SCREW_LENGTH = PROPULSION_ATTACHMENT.screw_length_mm
SHAFT_SERVICE_SHIFTS = {
    "PortOutputShaftNegative": 12.0,
    "StarboardOutputShaftPositive": -12.0,
}
SERVICE_WAYPOINTS = ((0, 0, 0), (0, 0, 11.0), (80, 0, 11.0))


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
    y = servo_envelope.ear_seat_y() - MOUNT_DEPTH
    if abs(y + MOUNT_DEPTH / 2) > 1e-7:
        raise ValueError("Paired servo ears must share the central mounting wall")
    width = bulkhead_width(drive)
    return box(
        width, MOUNT_DEPTH, drive.input_z_mm + 10.1 - SEAT_Z, (-width / 2, y, SEAT_Z)
    )


def cut_shared_bolt_passage(shape):
    for sign in (-1, 1):
        shape = shape.cut(
            Part.makeCylinder(
                rail.SLOT_HEIGHT / 2,
                CHEEK_THICKNESS + rail.MOUNT_LEG_THICKNESS + rail.WEB_THICKNESS + 2,
                V(sign * CLAMP_AXIS_X, sign * (CHEEK_OUTER_Y - 1), rail.BOLT_AXIS_Z),
                V(0, sign, 0),
            )
        )
    return shape.removeSplitter()


def bridge_blank_blocks(drive=SELECTED_DRIVE):
    """Exact axis-aligned stock; usable independently for continuous service sweeps."""
    top = SEAT_Z + CONNECTOR_PLATE_THICKNESS
    return (
        _cradle_blank(drive),
        box(
            2 * ROOF_HALF_LENGTH,
            2 * GUIDE_OUTER_Y,
            CONNECTOR_PLATE_THICKNESS,
            (-ROOF_HALF_LENGTH, -GUIDE_OUTER_Y, SEAT_Z),
        ),
        box(
            CHEEK_END_X - CHEEK_START_X,
            CHEEK_THICKNESS,
            SEAT_Z - FRAME_BOTTOM_Z,
            (CHEEK_START_X, CHEEK_OUTER_Y, FRAME_BOTTOM_Z),
        ),
        box(
            CHEEK_END_X - CHEEK_START_X,
            CHEEK_THICKNESS,
            SEAT_Z - FRAME_BOTTOM_Z,
            (-CHEEK_END_X, -CHEEK_CONTACT_Y, FRAME_BOTTOM_Z),
        ),
        box(
            CENTRAL_SEAT_LENGTH,
            GUIDE_OUTER_Y - GUIDE_INNER_Y,
            top - GUIDE_BOTTOM_Z,
            (-CENTRAL_SEAT_LENGTH / 2, GUIDE_INNER_Y, GUIDE_BOTTOM_Z),
        ),
        box(
            CENTRAL_SEAT_LENGTH,
            GUIDE_OUTER_Y - GUIDE_INNER_Y,
            top - GUIDE_BOTTOM_Z,
            (-CENTRAL_SEAT_LENGTH / 2, -GUIDE_OUTER_Y, GUIDE_BOTTOM_Z),
        ),
    )


def bridge_blank(drive=SELECTED_DRIVE):
    """Conservative stock with servo windows and clamp passages filled."""
    return union(bridge_blank_blocks(drive)).removeSplitter()


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
    void = _ear_clearance(drive)
    bridge = cut_shared_bolt_passage(bridge.cut(void).cut(opposite(void)))
    head_cut = rail.head_recess_shape(CHEEK_OUTER_Y, x=CLAMP_AXIS_X)
    return bridge.cut(head_cut).cut(opposite(head_cut)).removeSplitter()
