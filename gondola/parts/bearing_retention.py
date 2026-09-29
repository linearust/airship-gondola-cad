"""Rigid capture of the purchased nominal 3 x 6 x 2.5 bearing.

A fixed circular seat locates the bearing radially; a rear shoulder and
removable keeper limit axial motion. The keeper screw clamps the frame,
not the bearing. No spring arms or radial clamp are used.

Nominal allowances are trial dimensions, not a guaranteed SLS/MJF fit.
Match the production coupon to the received bearing/process. Finish or
reprint an unsuitable seat; never force a bearing in or tighten away play.
The broad keeper guides prevent gross rotation, not precision centering:
center the aperture on the actual bearing before tightening, and check
outer-ring contact and free rotation at both axial limits.
"""

import FreeCAD as App
import Part

from gondola.cad import box, translated_shape, union

BEARING_RADIUS = 3.0
BEARING_WIDTH = 2.5
SEAT_RADIUS = 3.05
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
KEEPER_GUIDE_CLEARANCE = 0.2
KEEPER_FOOT_TOP_Z = -14.0
KEEPER_FOOT_BACK_Y = 1.5
KEEPER_SCREW_Z = -18.0
KEEPER_SCREW_SEAT_Y = 0.0
KEEPER_SCREW_LENGTH = 6.0
KEEPER_NUT_SEAT_Y = SHOULDER_START_Y + SHOULDER_THICKNESS
KEEPER_HEAD_CLEARANCE_RADIUS = 2.5


def _cylinder(radius, start_y, length, z=0.0):
    return Part.makeCylinder(
        radius, length, App.Vector(0, start_y, z), App.Vector(0, 1, 0)
    )


def keeper_pocket_tool():
    """Open-front broad guides and a deeper seat for the recessed screw foot."""
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
                KEEPER_NUT_SEAT_Y - GUIDE_START_Y + 0.2,
            ),
            keeper_pocket_tool(),
            _cylinder(
                1.1,
                GUIDE_START_Y - 0.1,
                KEEPER_NUT_SEAT_Y - GUIDE_START_Y + 0.2,
                KEEPER_SCREW_Z,
            ),
        ]
    )


def fixed_body_shape():
    """Rigid seat/shoulder, wide keeper guides and a solid screw seat."""
    body = box(
        2 * BODY_HALF_WIDTH,
        KEEPER_NUT_SEAT_Y - GUIDE_START_Y,
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
    """Simple plate and thick lower screw foot; no elastic/radial clamp."""
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
        "nominal_diametral_clearance_mm": 2 * (SEAT_RADIUS - BEARING_RADIUS),
        "scope": "Nominal rigid capture only. Coupon-match the actual bearing and keeper; verify radial fit, ring lands, shields, cap alignment, no preload, fastener retention and loaded motion. General PA12 tolerance is not absorbed by the nominal seat allowance. No strength or physical fit qualification.",
    }
    zero_keys = [k for k in metrics if k.endswith("_mm3") and "overtravel" not in k]
    metrics["passed"] = (
        metrics["valid_single_solid"]
        and metrics["valid_keeper_solid"]
        and metrics["inward_overtravel_block_mm3"] > 0.01
        and metrics["outward_overtravel_block_mm3"] > 0.01
        and all(metrics[k] < 1e-7 for k in zero_keys)
    )
    return metrics
