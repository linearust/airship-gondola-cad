"""Selected X06 in servo-axis coordinates, shared by its body and support.

The output axis is +Y, the case's long direction is Z, and the near case end
is above the axis. Published dimensions come from equipment_interfaces; the
horn-to-case gap and transverse ear outline remain design allowances. This is
one selected servo interface, not an interchangeable-servo fit guarantee.
"""

import FreeCAD as App
import Part

from gondola.cad import box
from gondola.contracts import equipment_interfaces as interfaces

from . import servo_coupling

CASE_LENGTH, CASE_WIDTH, CASE_DEPTH = interfaces.X06_CASE_SIZE_MM
CASE_TOP_Z = interfaces.X06_OUTPUT_FROM_CASE_END_MM
CASE_BOTTOM_Z = CASE_TOP_Z - CASE_LENGTH
CASE_CENTRE_Z = (CASE_TOP_Z + CASE_BOTTOM_Z) / 2
EAR_CENTRES_Z = tuple(
    CASE_CENTRE_Z + sign * interfaces.X06_EAR_HOLE_PITCH_MM / 2 for sign in (-1, 1)
)
EAR_THICKNESS = (
    interfaces.X06_EAR_UNDERSIDE_FROM_CASE_TOP_MM
    - interfaces.X06_EAR_TOP_FROM_CASE_TOP_MM
)
EAR_HEIGHT = (interfaces.X06_EAR_SPAN_MM - CASE_LENGTH) / 2
HORN_CASE_GAP = 0.2


def case_front_y():
    return servo_coupling.HORN_BOTTOM_Y - HORN_CASE_GAP


def case_rear_y():
    return case_front_y() - CASE_DEPTH


def ear_seat_y():
    """Rear ear face touching the front of the printed mounting wall."""
    return case_front_y() - interfaces.X06_EAR_UNDERSIDE_FROM_CASE_TOP_MM


def ear_head_y():
    return case_front_y() - interfaces.X06_EAR_TOP_FROM_CASE_TOP_MM


def shape():
    """Nominal case, conservative full-width ears and a smooth spline envelope."""
    front = case_front_y()
    body = box(
        CASE_WIDTH,
        CASE_DEPTH,
        CASE_LENGTH,
        (-CASE_WIDTH / 2, case_rear_y(), CASE_BOTTOM_Z),
    )
    for centre_z in EAR_CENTRES_Z:
        ear = box(
            CASE_WIDTH,
            EAR_THICKNESS,
            EAR_HEIGHT,
            (-CASE_WIDTH / 2, ear_seat_y(), centre_z - EAR_HEIGHT / 2),
        ).cut(
            Part.makeCylinder(
                interfaces.X06_EAR_HOLE_DIAMETER_MM / 2,
                EAR_THICKNESS + 0.2,
                App.Vector(0, ear_seat_y() - 0.1, centre_z),
                App.Vector(0, 1, 0),
            )
        )
        body = body.fuse(ear)
    return body.fuse(
        Part.makeCylinder(
            interfaces.X06_SPLINE_DIAMETER_MM / 2,
            interfaces.X06_OVERALL_HEIGHT_MM - CASE_DEPTH,
            App.Vector(0, front, 0),
            App.Vector(0, 1, 0),
        )
    )
