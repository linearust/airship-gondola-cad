"""Replaceable paired servos on a continuous U cap around the output frame.

The flat roof and both sidewalls transfer load through two shared M3 clamps.
The raised transverse frame beam passes directly below the flat roof. Contact lands are a
coupon-fitted interface; screws must not pull an unseated or warped cap closed.
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
EAR_NUT_POCKET_AF = 3.4
EAR_NUT_POCKET_DEPTH = 0.5
EAR_NUT_GRIP = MOUNT_DEPTH + servo_envelope.EAR_THICKNESS - EAR_NUT_POCKET_DEPTH
CRADLE_TOP_FROM_AXIS = 10.2
CASE_CLEARANCE = 0.3
CASE_WINDOW_WIDTH = servo_envelope.CASE_WIDTH + 2 * CASE_CLEARANCE
CASE_WINDOW_HEIGHT = servo_envelope.CASE_LENGTH + 2 * CASE_CLEARANCE
CRADLE_WIDTH = 16.0
SIDE_WALL = (CRADLE_WIDTH - CASE_WINDOW_WIDTH) / 2
REAR_LEAD_ALLOWANCE = 13.9
SEAT_Z = PROPULSION_ATTACHMENT.seat_z_mm
CONNECTOR_PLATE_BOTTOM_Z, CONNECTOR_PLATE_THICKNESS = SEAT_Z, 2.5
CRADLE_ROOT_RADIUS = 1.0
# Outer cheeks clear tape wings; the inner frame feet seat on the rail base.
CHEEK_BOTTOM_Z = 2.2
CENTRAL_SEAT_LENGTH = PROPULSION_ATTACHMENT.contact_length_mm
CENTRAL_SEAT_WIDTH = 2 * PROPULSION_ATTACHMENT.frame_half_width_mm
CLAMP_AXIS_X = PROPULSION_ATTACHMENT.half_spacing_mm
CHEEK_THICKNESS = PROPULSION_ATTACHMENT.extra_cheek_mm
CHEEK_CONTACT_Y = -PROPULSION_ATTACHMENT.frame_half_width_mm
CHEEK_OUTER_Y = CHEEK_CONTACT_Y - CHEEK_THICKNESS
ROOF_HALF_LENGTH = CENTRAL_SEAT_LENGTH / 2
CROSSBEAM_RELIEF_HALF_X = 9.2
CROSSBEAM_RELIEF_TOP_Z = SEAT_Z
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
        width,
        MOUNT_DEPTH,
        drive.input_z_mm + CRADLE_TOP_FROM_AXIS - SEAT_Z,
        (-width / 2, y, SEAT_Z),
    )


def _ear_nut_pockets(drive):
    """Shallow rear hex seats keep the open ear passages and 4.5mm wall floor."""
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


cut_shared_bolt_passage = rail.cut_shared_bolt_passage


def _bridge_core_blocks(drive):
    """Plain stock before root blending, retaining the raised beam opening."""
    blocks = [
        _cradle_blank(drive),
        box(
            2 * ROOF_HALF_LENGTH,
            -2 * CHEEK_OUTER_Y,
            CONNECTOR_PLATE_THICKNESS,
            (-ROOF_HALF_LENGTH, CHEEK_OUTER_Y, SEAT_Z),
        ),
    ]
    for y in (CHEEK_OUTER_Y, -CHEEK_CONTACT_Y):
        for x in (-ROOF_HALF_LENGTH, CROSSBEAM_RELIEF_HALF_X):
            blocks.append(
                box(
                    ROOF_HALF_LENGTH - CROSSBEAM_RELIEF_HALF_X,
                    CHEEK_THICKNESS,
                    CROSSBEAM_RELIEF_TOP_Z - CHEEK_BOTTOM_Z,
                    (x, y, CHEEK_BOTTOM_Z),
                )
            )
    return tuple(blocks)


def bridge_blank_blocks(drive=SELECTED_DRIVE):
    """Seven conservative boxes enclose the cradle, root blends and both U legs."""
    width = bulkhead_width(drive)
    radius = CRADLE_ROOT_RADIUS
    root = box(
        width + 2 * radius,
        MOUNT_DEPTH + 2 * radius,
        radius,
        (
            -width / 2 - radius,
            -MOUNT_DEPTH / 2 - radius,
            SEAT_Z + CONNECTOR_PLATE_THICKNESS,
        ),
    )
    return (*_bridge_core_blocks(drive), root)


def bridge_blank(drive=SELECTED_DRIVE):
    """Blended stock with servo windows and clamp passages filled."""
    body = union(_bridge_core_blocks(drive)).removeSplitter()
    width = bulkhead_width(drive)
    root_z = SEAT_Z + CONNECTOR_PLATE_THICKNESS
    edges = []
    for edge in body.Edges:
        points = [vertex.Point for vertex in edge.Vertexes]
        if len(points) != 2 or not all(abs(p.z - root_z) < 1e-7 for p in points):
            continue
        if any(
            all(abs(p[axis] - position) < 1e-7 for p in points)
            for axis, position in (
                (0, -width / 2),
                (0, width / 2),
                (1, -MOUNT_DEPTH / 2),
                (1, MOUNT_DEPTH / 2),
            )
        ):
            edges.append(edge)
    if len(edges) != 4:
        raise RuntimeError("Servo cradle must expose four root edges")
    return body.makeFillet(CRADLE_ROOT_RADIUS, edges).removeSplitter()


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
    pockets = _ear_nut_pockets(drive)
    bridge = bridge.cut(pockets).cut(opposite(pockets))
    head_cut = rail.head_recess_shape(CHEEK_OUTER_Y, x=CLAMP_AXIS_X)
    # Open only the outer head-pocket depth at the nearest saddle end.
    # The complete inner head-bearing floor and opposite nut flats remain.
    head_cut = head_cut.fuse(
        box(
            ROOF_HALF_LENGTH - CLAMP_AXIS_X + 1,
            rail.HEAD_RECESS_DEPTH,
            rail.BOLT_AXIS_Z + rail.HEAD_RECESS_DIAMETER / 2 - CHEEK_BOTTOM_Z,
            (CLAMP_AXIS_X, CHEEK_OUTER_Y, CHEEK_BOTTOM_Z),
        )
    )
    nut_cut = rail.nut_pocket_shape(-CHEEK_CONTACT_Y, -CHEEK_OUTER_Y, x=CLAMP_AXIS_X)
    for cutter in (head_cut, opposite(head_cut), nut_cut, opposite(nut_cut)):
        bridge = bridge.cut(cutter)
    from .edge_blends import fillet_selected, near

    bridge = bridge.removeSplitter()
    roof_top = CONNECTOR_PLATE_BOTTOM_Z + CONNECTOR_PLATE_THICKNESS
    bridge = fillet_selected(
        bridge,
        0.5,
        lambda e, b: (
            near(b.ZMin, roof_top)
            and near(b.ZLength, 0)
            and (
                (near(b.XLength, 0) and near(abs(b.XMin), ROOF_HALF_LENGTH))
                or (near(b.YLength, 0) and near(abs(b.YMin), -CHEEK_OUTER_Y))
            )
        ),
        4,
        "Servo bridge upper outer roof rim",
    )
    # Select only the four outer cradle corners, not window or nut-pocket
    # edges. The complete mating underside and shallow nut floors stay flat.
    return fillet_selected(
        bridge,
        0.5,
        lambda e, b: (
            near(b.XLength, 0)
            and near(b.YLength, 0)
            and near(abs(b.XMin), bulkhead_width(drive) / 2)
            and near(abs(b.YMin), MOUNT_DEPTH / 2)
            and b.ZLength > 20
        ),
        4,
        "Servo bridge outer cradle corners",
    )
