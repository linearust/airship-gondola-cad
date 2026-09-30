"""Replaceable paired-servo wall with a keyed cheek on the common rail clamp.

The flat central plate bears on the output frame. A shallow rectangular key on
its vertical cheek bounds X/Z movement and rotation independently of screw-hole
clearance; one shared transverse bolt clamps bridge, frame and rail together.
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
CASE_CLEARANCE = 0.5
CASE_WINDOW_WIDTH = servo_envelope.CASE_WIDTH + 2 * CASE_CLEARANCE
CASE_WINDOW_HEIGHT = servo_envelope.CASE_LENGTH + 2 * CASE_CLEARANCE
SIDE_WALL = 3.0
CRADLE_WIDTH = CASE_WINDOW_WIDTH + 2 * SIDE_WALL
REAR_LEAD_ALLOWANCE = 13.9
SEAT_Z = 11.4
CONNECTOR_PLATE_BOTTOM_Z, CONNECTOR_PLATE_THICKNESS = SEAT_Z, 2.0
FRAME_BOTTOM_Z = 2.2
CENTRAL_SEAT_LENGTH, CENTRAL_SEAT_WIDTH = 18.0, 22.0
CLAMP_AXIS_X = 12.5
CHEEK_START_X, CHEEK_END_X = 9.0, 24.5
CHEEK_THICKNESS = 3.0
CHEEK_CONTACT_Y = rail.MOUNT_OUTER_Y
CHEEK_OUTER_Y = CHEEK_CONTACT_Y - CHEEK_THICKNESS
KEY_START_X, KEY_END_X = 17.0, 22.5
KEY_BOTTOM_Z, KEY_TOP_Z = 4.0, 9.5
KEY_DEPTH = 1.0
KEY_FACE_CLEARANCE = 0.2
KEY_DEPTH_CLEARANCE = 0.2
SHARED_GRIP = CHEEK_THICKNESS + rail.MOUNT_LEG_THICKNESS + rail.WEB_THICKNESS
SHARED_SCREW_LENGTH = 12.0
SERVICE_WAYPOINTS = ((0, 0, 0), (0, -1.2, 0), (0, -1.2, 0.5), (80, -1.2, 0.5))


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


def frame_key_shape():
    """An open rectangular locating pad, not a latch or captured undercut."""
    return box(
        KEY_END_X - KEY_START_X,
        KEY_DEPTH,
        KEY_TOP_Z - KEY_BOTTOM_Z,
        (KEY_START_X, CHEEK_CONTACT_Y - KEY_DEPTH, KEY_BOTTOM_Z),
    )


def key_recess_shape():
    depth = KEY_DEPTH + KEY_DEPTH_CLEARANCE
    return box(
        KEY_END_X - KEY_START_X + 2 * KEY_FACE_CLEARANCE,
        depth + 0.1,
        KEY_TOP_Z - KEY_BOTTOM_Z + 2 * KEY_FACE_CLEARANCE,
        (
            KEY_START_X - KEY_FACE_CLEARANCE,
            CHEEK_CONTACT_Y - depth,
            KEY_BOTTOM_Z - KEY_FACE_CLEARANCE,
        ),
    )


def cut_shared_bolt_passage(shape):
    return shape.cut(
        Part.makeCylinder(
            rail.SLOT_HEIGHT / 2,
            SHARED_GRIP + 2,
            V(CLAMP_AXIS_X, CHEEK_OUTER_Y - 1, rail.BOLT_AXIS_Z),
            V(0, 1, 0),
        )
    ).removeSplitter()


def bridge_blank(drive=SELECTED_DRIVE):
    """Planar service envelope retaining the key recess and open lower L profile.

    Servo windows and round screw passages are filled to permit exact face-prism
    sweeps. The mating-key recess must remain open during the initial -Y release.
    """
    width = bulkhead_width(drive)
    plate = box(
        CHEEK_END_X + width / 2,
        CENTRAL_SEAT_WIDTH,
        CONNECTOR_PLATE_THICKNESS,
        (-width / 2, -CENTRAL_SEAT_WIDTH / 2, SEAT_Z),
    )
    cheek = box(
        CHEEK_END_X - CHEEK_START_X,
        CHEEK_THICKNESS,
        SEAT_Z + CONNECTOR_PLATE_THICKNESS - FRAME_BOTTOM_Z,
        (CHEEK_START_X, CHEEK_OUTER_Y, FRAME_BOTTOM_Z),
    )
    return (
        union([_cradle_blank(drive), plate, cheek])
        .cut(key_recess_shape())
        .removeSplitter()
    )


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
    return cut_shared_bolt_passage(bridge.cut(void).cut(opposite(void)))


def contact_planes():
    """Nominal seating contacts; key clearance is checked separately by bounds."""
    cheek_area = (
        (CHEEK_END_X - CHEEK_START_X) * (SEAT_Z - FRAME_BOTTOM_Z)
        - (KEY_END_X - KEY_START_X + 2 * KEY_FACE_CLEARANCE)
        * (KEY_TOP_Z - KEY_BOTTOM_Z + 2 * KEY_FACE_CLEARANCE)
        - math.pi * (rail.SLOT_HEIGHT / 2) ** 2
    )
    return (
        (
            "central_bulkhead_support",
            2,
            SEAT_Z,
            CENTRAL_SEAT_LENGTH * CENTRAL_SEAT_WIDTH,
            (
                -CENTRAL_SEAT_LENGTH / 2,
                -CENTRAL_SEAT_WIDTH / 2,
                CENTRAL_SEAT_LENGTH,
                CENTRAL_SEAT_WIDTH,
            ),
        ),
        ("shared_clamp_vertical_face", 1, CHEEK_CONTACT_Y, cheek_area, None),
    )
