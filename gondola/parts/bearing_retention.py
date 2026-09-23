"""Integral, releasable outer-ring capture for the nominal 3 x 6 x 2.5 bearing.

The canonical bearing occupies Y0..2.5 and is inserted from negative Y. Two
long, external vertical arms carry the inboard hooks; the bearing runs in a
fixed seat, not in those arms. ``release_mm`` shears each arm outwards to model
an insertion/removal configuration. It is a kinematic clearance envelope,
never an elastic simulation or a prediction of insertion force or fatigue.

Print and cycle the process-matched coupon before committing a full frame.
The 0.2 mm axial gap and 0.2 mm radial outer-ring overlap are nominal trial
geometry, smaller than general PA12 process tolerance. Received ring lands,
seat fit, spring recovery, creep and shield clearance require physical checks.
"""

import FreeCAD as App
import Part

from gondola.cad import box, translated_shape, union

BEARING_RADIUS = 3.0
BEARING_WIDTH = 2.5
SHIELD_OPENING_DIAMETER = 5.6
GUIDE_START_Y = -2.0
SHOULDER_START_Y = BEARING_WIDTH
SHOULDER_THICKNESS = 1.5
BODY_HALF_WIDTH = 4.8
BODY_BOTTOM_Z = -12.0
BODY_TOP_Z = 4.8
HOOK_FRONT_Y = -1.7
HOOK_STOP_Y = -0.2
HOOK_HALF_HEIGHT = 1.5
POCKET_BACK_Y = 0.4
POCKET_HALF_HEIGHT = 2.1
ARM_INNER_X = 5.8
ARM_THICKNESS = 1.5
ARM_ROOT_Z = -10.5
RELEASE_MM = 0.4


def _cylinder(radius, start_y, length):
    return Part.makeCylinder(
        radius, length, App.Vector(0, start_y, 0), App.Vector(0, 1, 0)
    )


def _side(shape, side):
    if side not in (-1, 1):
        raise ValueError("Bearing hook side must be -1 or +1")
    return shape.mirror(App.Vector(), App.Vector(1, 0, 0)) if side < 0 else shape


def post_clearance_tool():
    """Cut this from an adjoining post *before* fusing ``cup_shape``.

    The two front pockets must remain open. Fusing an unrelieved post behind a
    cup would quietly turn the movable hooks back into rigid interference.
    """
    tools = [
        _cylinder(BEARING_RADIUS, GUIDE_START_Y - 0.1, 4.6),
        _cylinder(SHIELD_OPENING_DIAMETER / 2, GUIDE_START_Y - 0.1, 6.2),
    ]
    for side in (-1, 1):
        tools.append(
            _side(
                box(
                    3.9,
                    POCKET_BACK_Y - GUIDE_START_Y + 0.1,
                    POCKET_HALF_HEIGHT * 2,
                    (2.0, GUIDE_START_Y - 0.1, -POCKET_HALF_HEIGHT),
                ),
                side,
            )
        )
    return union(tools)


def fixed_body_shape():
    """Broad fixed seat and outer shoulder, plus the two beam root anchors."""
    body = box(
        2 * BODY_HALF_WIDTH,
        SHOULDER_START_Y + SHOULDER_THICKNESS - GUIDE_START_Y,
        BODY_TOP_Z - BODY_BOTTOM_Z,
        (-BODY_HALF_WIDTH, GUIDE_START_Y, BODY_BOTTOM_Z),
    )
    anchors = [body]
    for side in (-1, 1):
        anchors.append(
            _side(
                box(
                    ARM_INNER_X + ARM_THICKNESS - 4.0,
                    SHOULDER_START_Y + SHOULDER_THICKNESS - HOOK_FRONT_Y,
                    ARM_ROOT_Z - BODY_BOTTOM_Z,
                    (4.0, HOOK_FRONT_Y, BODY_BOTTOM_Z),
                ),
                side,
            )
        )
    return union(anchors).cut(post_clearance_tool()).removeSplitter()


def hook_shape(side, release_mm=0.0):
    """One root-attached arm and hook; release is an explicit nominal pose.

    Displacement is ``release_mm`` at Z0 and zero at the beam root. This simple
    shear preserves connectivity, but does not imply a real cantilever bends
    linearly or that printed PA12 can survive this deflection.
    """
    if not 0 <= release_mm <= RELEASE_MM:
        raise ValueError(f"Modelled hook release must be 0..{RELEASE_MM} mm")
    beam = box(
        ARM_THICKNESS,
        HOOK_STOP_Y - HOOK_FRONT_Y,
        HOOK_HALF_HEIGHT - ARM_ROOT_Z,
        (ARM_INNER_X, HOOK_FRONT_Y, ARM_ROOT_Z),
    )
    hook = box(
        ARM_INNER_X + ARM_THICKNESS,
        HOOK_STOP_Y - HOOK_FRONT_Y,
        2 * HOOK_HALF_HEIGHT,
        (0, HOOK_FRONT_Y, -HOOK_HALF_HEIGHT),
    )
    hook = hook.cut(_cylinder(SHIELD_OPENING_DIAMETER / 2, -1.8, 1.7))
    # No thin insertion ramp: pre-open both arms with the release tools before
    # inserting the bearing. The square hook keeps its full 1.5 mm thickness.
    arm = union([beam, hook])
    if release_mm:
        matrix = App.Matrix()
        matrix.A13 = release_mm / -ARM_ROOT_Z
        matrix.A14 = release_mm
        arm = arm.transformGeometry(matrix)
    return _side(arm, side)


def cup_shape(release_mm=0.0):
    """One printable solid, at rest or in the explicitly modelled release pose."""
    shape = union(
        [fixed_body_shape(), hook_shape(-1, release_mm), hook_shape(1, release_mm)]
    )
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Bearing cup must remain one valid connected solid")
    return shape


def released_shape(cup=None):
    """Replace the two nominal arms in an actual cup with their release poses.

    Extra material in a saved frame is deliberately retained: a refilled slot
    must not disappear merely because the ideal released model has an opening.
    ``geometry_check`` separately requires both complete nominal arms to exist.
    """
    cup = cup if cup is not None else cup_shape()
    arms = union([hook_shape(-1), hook_shape(1)])
    return union([cup.cut(arms), hook_shape(-1, RELEASE_MM), hook_shape(1, RELEASE_MM)])


def release_tool_shapes():
    """Two 0.6 mm flat-blade access envelopes, with the carrier/shaft removed.

    These represent hand tools, not installed parts. Insert in the open side
    slots below the hooks and displace the arms outward; hold both released
    while withdrawing the bearing. Do not lever on a shield or an inner ring.
    """
    tool = box(0.6, 12.0, 3.0, (4.95, -12.2, -5.0))
    return [_side(tool, side) for side in (-1, 1)]


def coupon_shape():
    """Production cup and beam roots on a plain 3 mm handling foot."""
    return union(
        [
            cup_shape(),
            box(18.0, 10.0, 3.0, (-9.0, -4.0, BODY_BOTTOM_Z - 3.0)),
        ]
    )


def geometry_check(cup=None):
    """Nominal capture/support/access evidence; no physical snap qualification.

    A continuous axial insertion sweep is intersected with the released cup.
    Intermediate release poses only check this explicit shear model. The final
    full-frame assembly must additionally verify all neighboring obstacles.
    """
    cup = cup if cup is not None else cup_shape()
    bearing = _cylinder(BEARING_RADIUS, 0, BEARING_WIDTH).cut(
        _cylinder(1.5, -0.1, BEARING_WIDTH + 0.2)
    )
    released = released_shape(cup)
    insertion = _cylinder(BEARING_RADIUS, -8.0, 10.5)
    inward = translated_shape(bearing, y=HOOK_STOP_Y)
    stop_in = cup.common(translated_shape(bearing, y=HOOK_STOP_Y - 0.05)).Volume
    stop_out = cup.common(translated_shape(bearing, y=0.05)).Volume
    guide = _cylinder(3.2, POCKET_BACK_Y, BEARING_WIDTH - POCKET_BACK_Y).cut(
        _cylinder(3.01, POCKET_BACK_Y, BEARING_WIDTH - POCKET_BACK_Y)
    )
    shield = _cylinder(2.7, -0.3, 2.9)
    tool_collision = sum(cup.common(tool).Volume for tool in release_tool_shapes())
    missing_hooks = sum(hook_shape(side).cut(cup).Volume for side in (-1, 1))
    pocket_witness = box(2.6, 0.58, 4.0, (3.1, -0.19, -2.0))
    pocket_collision = sum(
        cup.common(_side(pocket_witness, side)).Volume for side in (-1, 1)
    )
    side_slot = box(0.98, 1.48, 8.98, (4.81, -1.69, -10.49))
    side_slot_collision = sum(
        cup.common(_side(side_slot, side)).Volume for side in (-1, 1)
    )
    fixed_geometry = cup.cut(union([hook_shape(-1), hook_shape(1)]))
    release_collision = max(
        fixed_geometry.common(hook_shape(side, step * RELEASE_MM / 8)).Volume
        for side in (-1, 1)
        for step in range(9)
    )
    metrics = {
        "valid_single_solid": cup.isValid() and len(cup.Solids) == 1,
        "nominal_bearing_collision_mm3": cup.common(bearing).Volume,
        "inward_limit_bearing_collision_mm3": cup.common(inward).Volume,
        "inward_overtravel_block_mm3": stop_in,
        "outward_overtravel_block_mm3": stop_out,
        "released_continuous_insertion_collision_mm3": released.common(
            insertion
        ).Volume,
        "complete_guide_missing_mm3": guide.cut(cup).Volume,
        "complete_guide_length_mm": BEARING_WIDTH - POCKET_BACK_Y,
        "complete_guide_overlap_at_inward_limit_mm": BEARING_WIDTH
        + HOOK_STOP_Y
        - POCKET_BACK_Y,
        "shield_design_envelope_collision_mm3": cup.common(shield).Volume,
        "release_tool_collision_mm3": tool_collision,
        "hook_missing_mm3": missing_hooks,
        "hook_back_pocket_collision_mm3": pocket_collision,
        "arm_side_slot_collision_mm3": side_slot_collision,
        "sampled_release_to_fixed_body_collision_mm3": release_collision,
        "nominal_axial_endplay_mm": -HOOK_STOP_Y,
        "scope": "Nominal geometry and explicit kinematic release only. Ring-land compatibility, actual print fit, both-hook recovery, insertion force, axial retention, creep and fatigue require a process-matched coupon and installed trials. No bearing preload or elastic/strength qualification.",
    }
    metrics["passed"] = (
        metrics["valid_single_solid"]
        and stop_in > 0.01
        and stop_out > 0.01
        and all(
            metrics[key] < 1e-7
            for key in (
                "nominal_bearing_collision_mm3",
                "inward_limit_bearing_collision_mm3",
                "released_continuous_insertion_collision_mm3",
                "complete_guide_missing_mm3",
                "shield_design_envelope_collision_mm3",
                "release_tool_collision_mm3",
                "sampled_release_to_fixed_body_collision_mm3",
                "hook_missing_mm3",
                "hook_back_pocket_collision_mm3",
                "arm_side_slot_collision_mm3",
            )
        )
    )
    return metrics
