"""Rigid capture of the purchased nominal 3 x 6 x 2.5 bearing.

A fixed circular seat locates the bearing radially; a rear shoulder and
removable keeper limit axial motion. The keeper screw clamps the frame,
not the bearing. No spring arms or radial clamp are used.

The nominal diameter-6 seat is a finish-to-fit locating datum, not a
guaranteed SLS/MJF slip fit. There is no designed radial shake or press fit.
Match the production coupon to the received bearing/process. Finish or
reprint an unsuitable seat; never force a bearing in or tighten away play.
The broad keeper guides prevent gross rotation, not precision centering:
the 0.1 mm nominal clearance is a trial fit, not automatic centering. Align
the aperture on the actual bearing before tightening, and check
outer-ring contact and free rotation at both axial limits.
"""

import FreeCAD as App
import Part

from gondola.cad import box, translated_shape, union

from . import nut_guides

BEARING_RADIUS = 3.0
BEARING_WIDTH = 2.5
SEAT_RADIUS = BEARING_RADIUS
SHIELD_OPENING_DIAMETER = 5.6
GUIDE_START_Y = -2.0
SHOULDER_START_Y = BEARING_WIDTH
SHOULDER_THICKNESS = 1.5
BODY_HALF_WIDTH = 6.5
BODY_BOTTOM_Z = -23.0
BODY_TOP_Z = 4.8
KEEPER_FRONT_Y = -2.0
KEEPER_STOP_Y = -0.5
KEEPER_HALF_WIDTH = 4.5
KEEPER_BOTTOM_Z = -21.5
KEEPER_TOP_Z = 4.5
KEEPER_GUIDE_CLEARANCE = 0.1
KEEPER_FOOT_TOP_Z = -5.0
KEEPER_FOOT_BACK_Y = 1.5
KEEPER_SCREW_Z = -18.0
KEEPER_SCREW_SEAT_Y = 0.0
KEEPER_SCREW_LENGTH = 6.0
BODY_REAR_Y = SHOULDER_START_Y + SHOULDER_THICKNESS
KEEPER_NUT_SEAT_Y = BODY_REAR_Y - nut_guides.POCKET_DEPTH
KEEPER_HEAD_CLEARANCE_RADIUS = 2.5


def _cylinder(radius, start_y, length, z=0.0):
    return Part.makeCylinder(
        radius, length, App.Vector(0, start_y, z), App.Vector(0, 1, 0)
    )


def keeper_pocket_tool():
    """Open-front guides and a deeper nest for the continuous keeper backing."""
    half = KEEPER_HALF_WIDTH + KEEPER_GUIDE_CLEARANCE
    bottom = KEEPER_BOTTOM_Z - KEEPER_GUIDE_CLEARANCE
    return union(
        [
            box(
                2 * half,
                KEEPER_STOP_Y - KEEPER_FRONT_Y + 0.1,
                BODY_TOP_Z - bottom + 0.1,
                (-half, KEEPER_FRONT_Y - 0.1, bottom),
            ),
            box(
                2 * half,
                KEEPER_FOOT_BACK_Y - KEEPER_FRONT_Y + 0.1,
                KEEPER_FOOT_TOP_Z + KEEPER_GUIDE_CLEARANCE - bottom,
                (-half, KEEPER_FRONT_Y - 0.1, bottom),
            ),
        ]
    )


def nut_pocket_tool():
    """Cut through both the housing and any adjoining post stock."""
    pocket = nut_guides.pocket_tool()
    pocket.Placement = App.Placement(
        App.Vector(0, KEEPER_NUT_SEAT_Y, KEEPER_SCREW_Z),
        App.Rotation(App.Vector(0, 0, 1), App.Vector(0, 1, 0)),
    )
    return pocket


def post_clearance_tool():
    """Cut the seat, keeper nest and fastener path before adjoining post union."""
    return union(
        [
            _cylinder(
                SEAT_RADIUS, GUIDE_START_Y - 0.1, SHOULDER_START_Y - GUIDE_START_Y + 0.1
            ),
            _cylinder(
                SHIELD_OPENING_DIAMETER / 2,
                GUIDE_START_Y - 0.1,
                BODY_REAR_Y - GUIDE_START_Y + 0.2,
            ),
            keeper_pocket_tool(),
            nut_pocket_tool(),
            _cylinder(
                1.1,
                GUIDE_START_Y - 0.1,
                BODY_REAR_Y - GUIDE_START_Y + 0.2,
                KEEPER_SCREW_Z,
            ),
        ]
    )


def fixed_body_shape():
    """Rigid seat/shoulder and a shallow M2 pocket within the rear face."""
    body = box(
        2 * BODY_HALF_WIDTH,
        BODY_REAR_Y - GUIDE_START_Y,
        BODY_TOP_Z - BODY_BOTTOM_Z,
        (-BODY_HALF_WIDTH, GUIDE_START_Y, BODY_BOTTOM_Z),
    )
    return body.cut(post_clearance_tool()).removeSplitter()


def cup_shape():
    """Fixed housing only; the keeper is a separately replaceable solid."""
    shape = fixed_body_shape()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Bearing cup must remain one valid connected solid")
    return shape


def keeper_shape():
    """Symmetric thick backing below the ring; no extra fastener or clamp.

    The backing extends from the recessed screw foot to 5 mm below the
    bearing axis. Its front plane stays flush with the outer-ring plate,
    preserving the carrier stops and inward removal path. The upper plate
    and circular bearing guide keep their existing axial/radial allowances.
    """
    body = union(
        [
            box(
                2 * KEEPER_HALF_WIDTH,
                KEEPER_STOP_Y - KEEPER_FRONT_Y,
                KEEPER_TOP_Z - KEEPER_BOTTOM_Z,
                (-KEEPER_HALF_WIDTH, KEEPER_FRONT_Y, KEEPER_BOTTOM_Z),
            ),
            box(
                2 * KEEPER_HALF_WIDTH,
                KEEPER_FOOT_BACK_Y - KEEPER_FRONT_Y,
                KEEPER_FOOT_TOP_Z - KEEPER_BOTTOM_Z,
                (-KEEPER_HALF_WIDTH, KEEPER_FRONT_Y, KEEPER_BOTTOM_Z),
            ),
        ]
    )
    cuts = [
        _cylinder(
            SHIELD_OPENING_DIAMETER / 2,
            KEEPER_FRONT_Y - 0.1,
            KEEPER_STOP_Y - KEEPER_FRONT_Y + 0.2,
        ),
        _cylinder(
            1.1,
            KEEPER_FRONT_Y - 0.1,
            KEEPER_FOOT_BACK_Y - KEEPER_FRONT_Y + 0.2,
            KEEPER_SCREW_Z,
        ),
        _cylinder(
            KEEPER_HEAD_CLEARANCE_RADIUS,
            KEEPER_FRONT_Y - 0.1,
            KEEPER_SCREW_SEAT_Y - KEEPER_FRONT_Y + 0.1,
            KEEPER_SCREW_Z,
        ),
    ]
    shape = body.cut(union(cuts)).removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Bearing keeper must remain one valid connected solid")
    return shape


def coupon_shape():
    """Production cup on a handling foot, used with a production keeper."""
    return union([cup_shape(), box(18, 10, 3, (-9, -4, BODY_BOTTOM_Z - 3))])


def geometry_check(cup=None, keeper=None):
    """Nominal capture/service proof; not a physical fit qualification."""
    cup = cup if cup is not None else cup_shape()
    keeper = keeper if keeper is not None else keeper_shape()
    support = union([cup, keeper])
    bearing = _cylinder(BEARING_RADIUS, 0, BEARING_WIDTH).cut(
        _cylinder(1.5, -0.1, BEARING_WIDTH + 0.2)
    )
    inward = translated_shape(bearing, y=KEEPER_STOP_Y)
    insertion = _cylinder(BEARING_RADIUS, -8, 10.5)
    # Sweep the individual planar cross-sections: Part cannot extrude a solid.
    keeper_sweep = union(
        [
            face.extrude(App.Vector(0, -8, 0))
            for face in keeper.Faces
            if abs(face.normalAt(0, 0).y) > 0.99
        ]
        + [keeper]
    )
    guide = _cylinder(3.25, KEEPER_STOP_Y, BEARING_WIDTH - KEEPER_STOP_Y).cut(
        _cylinder(
            SEAT_RADIUS + 0.01, KEEPER_STOP_Y - 0.1, BEARING_WIDTH - KEEPER_STOP_Y + 0.2
        )
    )
    shield = _cylinder(2.7, -0.6, 3.2)
    screw_path = _cylinder(1.0, 0, 6, KEEPER_SCREW_Z)
    foot_seat = _cylinder(2.0, KEEPER_FOOT_BACK_Y, 0.05, KEEPER_SCREW_Z).cut(
        _cylinder(1.11, KEEPER_FOOT_BACK_Y - 0.1, 0.25, KEEPER_SCREW_Z)
    )
    radial_seating, radial_contacts = [], []
    for axial in (0.0, KEEPER_STOP_Y):
        for dx, dz in (
            (BEARING_RADIUS, 0),
            (-BEARING_RADIUS, 0),
            (0, BEARING_RADIUS),
            (0, -BEARING_RADIUS),
        ):
            line = Part.makeLine(
                App.Vector(dx, axial, dz),
                App.Vector(dx, axial + BEARING_WIDTH, dz),
            )
            contact = cup.common(line).Length
            radial_contacts.append(
                {
                    "reaction_line_start_xyz_mm": [dx, axial, dz],
                    "nominal_contact_length_mm": contact,
                    "required_contact_length_mm": BEARING_WIDTH,
                    "passed": abs(contact - BEARING_WIDTH) < 1e-7,
                }
            )
        for dx, dz in ((0.01, 0), (-0.01, 0), (0, 0.01), (0, -0.01)):
            shifted = translated_shape(bearing, x=dx, y=axial, z=dz)
            blocked = cup.common(shifted).Volume
            radial_seating.append(
                {
                    "bearing_offset_xyz_mm": [dx, axial, dz],
                    "radial_shift_probe_penetration_mm3": blocked,
                    "passed": blocked > 0.01,
                }
            )
    metrics = {
        "valid_single_solid": cup.isValid() and len(cup.Solids) == 1,
        "valid_keeper_solid": keeper.isValid() and len(keeper.Solids) == 1,
        "nominal_bearing_collision_mm3": support.common(bearing).Volume,
        "inward_limit_bearing_collision_mm3": support.common(inward).Volume,
        "inward_overtravel_block_mm3": keeper.common(
            translated_shape(bearing, y=KEEPER_STOP_Y - 0.05)
        ).Volume,
        "outward_overtravel_block_mm3": cup.common(
            translated_shape(bearing, y=0.05)
        ).Volume,
        "keeper_to_frame_collision_mm3": cup.common(keeper).Volume,
        "bearing_insertion_collision_mm3": cup.common(insertion).Volume,
        "keeper_removal_collision_mm3": cup.common(keeper_sweep).Volume,
        "complete_guide_missing_mm3": guide.cut(cup).Volume,
        "complete_guide_length_mm": BEARING_WIDTH - KEEPER_STOP_Y,
        "complete_guide_overlap_at_inward_limit_mm": BEARING_WIDTH,
        "shield_design_envelope_collision_mm3": support.common(shield).Volume,
        "screw_shank_collision_mm3": support.common(screw_path).Volume,
        "keeper_screw_hard_seat_missing_mm3": foot_seat.cut(cup).Volume,
        "nominal_axial_endplay_mm": -KEEPER_STOP_Y,
        "keeper_guide_clearance_per_side_mm": KEEPER_GUIDE_CLEARANCE,
        "nominal_diametral_clearance_mm": 2 * (SEAT_RADIUS - BEARING_RADIUS),
        "radial_seating_probes": radial_seating,
        "radial_seating_contacts": radial_contacts,
        "scope": "Nominal rigid capture only. The diameter-6 bore locates the nominal bearing with no radial allowance or intended interference. Coupon-match and finish the actual bore for hand insertion without rocking; reprint an oversized seat. Verify ring lands, shields, cap alignment, no preload, fastener retention and loaded motion. Nominal contact is not an as-printed PA12 fit or strength qualification.",
    }
    zero_keys = [k for k in metrics if k.endswith("_mm3") and "overtravel" not in k]
    metrics["passed"] = (
        metrics["valid_single_solid"]
        and metrics["valid_keeper_solid"]
        and metrics["inward_overtravel_block_mm3"] > 0.01
        and metrics["outward_overtravel_block_mm3"] > 0.01
        and all(row["passed"] for row in radial_seating)
        and all(row["passed"] for row in radial_contacts)
        and all(metrics[k] < 1e-7 for k in zero_keys)
    )
    return metrics
