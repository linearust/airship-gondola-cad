"""Two compact closed servo frames seated directly on the central plinth.

The case window has nominal clearance on all four faces. The two ear fasteners
locate the installed servo. Remove the input shaft and loose driver before
withdrawing the servo axially; no separate upper link or closure is required.
Nominal closed sections do not establish stiffness or a strength rating.
"""

import FreeCAD as App
import Part

from gondola.cad import box, mirrored_y, union
from gondola.contracts.drive import DRIVE_INWARD_OFFSET_MM, SELECTED_DRIVE
from gondola.contracts.rail_attachments import PROPULSION_ATTACHMENT

from . import servo_envelope
from .servo_envelope import case_front_y as case_front_y

V = App.Vector
MOUNT_DEPTH = 5.0
EAR_NUT_POCKET_AF = 3.4
EAR_NUT_POCKET_DEPTH = 0.5
EAR_NUT_GRIP = MOUNT_DEPTH + servo_envelope.EAR_THICKNESS - EAR_NUT_POCKET_DEPTH
CRADLE_TOP_FROM_AXIS = 10.2
CASE_CLEARANCE = 0.2
CASE_WINDOW_WIDTH = servo_envelope.CASE_WIDTH + 2 * CASE_CLEARANCE
CASE_WINDOW_HEIGHT = servo_envelope.CASE_LENGTH + 2 * CASE_CLEARANCE
CRADLE_WEB_THICKNESS = 3.0
CRADLE_FLOOR_Z = 29.5
REAR_LEAD_DEPARTURE = 1.8
REAR_LEAD_ALLOWANCE = 13.9
# Rail service validators use these contract-owned datums.
CONNECTOR_PLATE_BOTTOM_Z = PROPULSION_ATTACHMENT.seat_z_mm
SHARED_SCREW_LENGTH = PROPULSION_ATTACHMENT.screw_length_mm


def opposite(shape):
    return mirrored_y(shape.mirror(V(), V(1, 0, 0)), -1)


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


def _ear_nut_pockets(drive):
    """Rear hex seats preserve window-connected ear slots and4.5mm floors."""
    from .purchased_hardware import hex_prism

    rear = servo_envelope.ear_seat_y() - MOUNT_DEPTH
    cuts = []
    for hole_z in servo_envelope.EAR_CENTRES_Z:
        pocket = hex_prism(EAR_NUT_POCKET_AF, EAR_NUT_POCKET_DEPTH + 0.1)
        pocket.Placement = App.Placement(
            V(drive.input_x_mm, rear - 0.1, drive.input_z_mm + hole_z),
            App.Rotation(V(0, 0, 1), V(0, 1, 0)),
        )
        cuts.append(pocket)
    return union(cuts)


def integrated_cradle_shape(drive=SELECTED_DRIVE):
    """Compact closed walls directly seated on the full-width central plinth.

    Remove both output gears, withdraw the input stub and loose driver, then
    release the ear pairs. The servo/horn/adapter moves forwardY13 and outwardX.
    Finish tight printed windows; never force the case or clamp it in compression.
    """
    x, z = drive.input_x_mm, drive.input_z_mm
    window_inner_x = x - servo_envelope.CASE_WIDTH / 2 - CASE_CLEARANCE
    inboard_x = window_inner_x - CRADLE_WEB_THICKNESS
    outer_x = window_inner_x + CASE_WINDOW_WIDTH + CRADLE_WEB_THICKNESS
    rear_y = servo_envelope.ear_seat_y() - MOUNT_DEPTH
    body = box(
        outer_x - inboard_x,
        MOUNT_DEPTH,
        z + CRADLE_TOP_FROM_AXIS - CRADLE_FLOOR_Z,
        (inboard_x, rear_y, CRADLE_FLOOR_Z),
    )
    window = box(
        CASE_WINDOW_WIDTH,
        MOUNT_DEPTH + 2,
        CASE_WINDOW_HEIGHT,
        (
            window_inner_x,
            rear_y - 1,
            z + servo_envelope.CASE_CENTRE_Z - CASE_WINDOW_HEIGHT / 2,
        ),
    )
    body = body.cut(window).cut(_ear_clearance(drive)).cut(_ear_nut_pockets(drive))
    body.translate(V(0, -DRIVE_INWARD_OFFSET_MM, 0))
    result = union([body, opposite(body)])
    result = result.removeSplitter()
    if not result.isValid() or len(result.Solids) != 2:
        raise RuntimeError(
            "Servo supports must form two valid solids before central plinth union"
        )
    return result
