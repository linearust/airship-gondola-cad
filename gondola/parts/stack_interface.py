"""Common removable optical tower with two integral PA12 positive hooks.

The CAD/print shape is the unstressed geometry at its nominal seated position. Elastic
release is screened separately; no fictitious preloaded shape is exported.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import (
    belongs_to_group,
    box,
    create_group,
    create_printed_part,
    set_property,
    union,
)
from gondola.contracts.design import (
    STACK_ANCHOR_CENTRES,
    STACK_ANCHOR_LOCATIONS,
    STACK_PITCH_MM,
)

V = App.Vector
PITCH_MM = STACK_PITCH_MM
ANCHOR_CENTRES = STACK_ANCHOR_CENTRES
ARM_WIDTH = 5.0
DECK_THICKNESS = 2.0
HOST_DECK_BOTTOM_Z = 10.2
HOST_SUPPORT_Z = HOST_DECK_BOTTOM_Z + DECK_THICKNESS
TOWER_HEIGHT = 32.0
STACK_TOP_Z = HOST_SUPPORT_Z + TOWER_HEIGHT
FOOT_THICKNESS = 1.5
FOOT_INNER_OFFSET = -3.6
FOOT_OUTER_OFFSET = 3.7
FIXED_LEG_INNER = -1.4
FIXED_LEG_THICKNESS = 2.0
GUIDE_TONGUE_DEPTH = 3.5
HOST_SEAT_EDGE = 4.5
HOST_SEAT_OUTER = 8.0
LEG_INNER_OFFSET = 5.2
LATCH_LEG_THICKNESS = 1.5
LEG_OUTER_OFFSET = LEG_INNER_OFFSET + LATCH_LEG_THICKNESS
LEG_WIDTH = 6.0
ROOT_RADIUS = 1.0
NOMINAL_CLEARANCE = 0.7
HOST_SLOT_WIDTH = LEG_WIDTH + 2 * NOMINAL_CLEARANCE
HOST_CHEEK_WIDTH = 1.5
HOST_SEAT_WIDTH = HOST_SLOT_WIDTH + 2 * HOST_CHEEK_WIDTH
HOOK_CAPTURE = 2.8
HOOK_TIP_OFFSET = HOST_SEAT_EDGE - HOOK_CAPTURE
HOOK_TIP_THICKNESS = 1.5
HOOK_RAMP_HEIGHT = 1.0
HOOK_TOP_Z = -TOWER_HEIGHT - DECK_THICKNESS - NOMINAL_CLEARANCE
HOOK_BOTTOM_Z = HOOK_TOP_Z - HOOK_TIP_THICKNESS - HOOK_RAMP_HEIGHT
DIMENSION_ALLOWANCE = 0.3
MAX_RADIAL_FLOAT = NOMINAL_CLEARANCE + 2 * DIMENSION_ALLOWANCE
YAW_RADIAL_ALLOWANCE = 0.15
MAX_RELEASE_TRAVEL = (
    HOOK_CAPTURE
    + 2 * DIMENSION_ALLOWANCE
    + MAX_RADIAL_FLOAT
    + YAW_RADIAL_ALLOWANCE
    + 0.1
)
NOMINAL_RELEASE_TRAVEL = HOOK_CAPTURE + 0.1
FREE_BEAM_LENGTH = TOWER_HEIGHT - FOOT_THICKNESS - ROOT_RADIUS
SUPPORTED_HOSTS = {
    "BatteryEquipmentModule": "BatteryMount",
    "ElectronicsEquipmentModule": "ElectronicsMount",
}


def latch_fit_contract():
    max_play = NOMINAL_CLEARANCE + 2 * DIMENSION_ALLOWANCE
    min_capture = (
        HOOK_CAPTURE - 2 * DIMENSION_ALLOWANCE - max_play - YAW_RADIAL_ALLOWANCE
    )
    return {
        "dimension_allowance_each_part_mm": DIMENSION_ALLOWANCE,
        "nominal_side_and_axial_clearance_mm": NOMINAL_CLEARANCE,
        "rigid_guide_tongue_section_mm": [FIXED_LEG_THICKNESS, LEG_WIDTH],
        "rigid_guide_hole_section_mm": [
            FIXED_LEG_THICKNESS + 2 * NOMINAL_CLEARANCE,
            LEG_WIDTH + 2 * NOMINAL_CLEARANCE,
        ],
        "rigid_guide_tongue_depth_mm": GUIDE_TONGUE_DEPTH,
        "minimum_remaining_guide_engagement_mm": GUIDE_TONGUE_DEPTH
        - DIMENSION_ALLOWANCE
        - max_play,
        "worst_axial_play_without_measured_pad_mm": max_play,
        "worst_unpadded_rock_estimate_deg": math.degrees(
            math.atan(max_play / (math.sqrt(2) * PITCH_MM))
        ),
        "minimum_capture_after_dimension_error_and_radial_float_mm": min_capture,
        "nominal_hook_capture_mm": HOOK_CAPTURE,
        "maximum_radial_float_mm": MAX_RADIAL_FLOAT,
        "yaw_radial_allowance_mm": YAW_RADIAL_ALLOWANCE,
        "nominal_release_travel_mm": NOMINAL_RELEASE_TRAVEL,
        "maximum_screened_release_travel_mm": MAX_RELEASE_TRAVEL,
        "conservative_free_beam_length_mm": FREE_BEAM_LENGTH,
        "nominal_peak_strain_screen_percent": 100
        * 1.5
        * LATCH_LEG_THICKNESS
        * NOMINAL_RELEASE_TRAVEL
        / FREE_BEAM_LENGTH**2,
        "worst_peak_strain_screen_percent": 100
        * 1.5
        * (LATCH_LEG_THICKNESS + DIMENSION_ALLOWANCE)
        * MAX_RELEASE_TRAVEL
        / (FREE_BEAM_LENGTH - 2 * DIMENSION_ALLOWANCE) ** 2,
        "strain_model": "Small-deflection constant-section cantilever screen epsilon=1.5*t*delta/L^2, including dimensional envelope; not FEA, material allowable, force, strength or cycle-life qualification.",
        "pointing_acceptance": "Flat hooks provide positive retention independently of adhesive. Their deliberately loose fit does NOT guarantee optical pointing stiffness. Fit a measured piece of the already-used adhesive consumable at broad upper bearing seats only if required to eliminate rocking, then recheck vertical aim under both axial load directions. No pad thickness, compression, material, mass or preload is invented. Do not accept a rocking sensor tower.",
        "qualification": "Print the two mating coupons in the same selected unfilled PA12 process/orientation as production; measure fit, seat, hook engagement and release, and test repeated removal and retention before releasing the full tower. No permanent flexure preload is designed. Optical +Z is away from the balloon; qualify retention and pad stability under both axial load directions. Stop if whitening, cracking, permanent set or incomplete hook engagement occurs.",
    }


def interface_contract():
    return {
        "standard": f"Project structural stack: two positive latch anchors at {STACK_ANCHOR_LOCATIONS}",
        "industry_standard_claimed": False,
        "axis_spacing_mm": math.sqrt(2) * PITCH_MM,
        "anchor_centres_xy_mm": ANCHOR_CENTRES,
        "printed_deck_thickness_mm": DECK_THICKNESS,
        "host_support_z_mm": HOST_SUPPORT_Z,
        "integral_tower_height_mm": TOWER_HEIGHT,
        "tower_foot_thickness_mm": FOOT_THICKNESS,
        "fixed_load_leg_section_mm": [FIXED_LEG_THICKNESS, LEG_WIDTH],
        "independent_latch_finger_section_mm": [LATCH_LEG_THICKNESS, LEG_WIDTH],
        "tower_attachment": "Two integral outward-release PA12 cantilever hooks engage broad open U seats, separately from rigid load legs and broad rectangular locating tongues. Rigid upper feet and flat lower hook shoulders carry opposing axial loads; no tower-foot bolts, nuts or added parts.",
        "service": "Disconnect sensor wiring and peel any anti-rattle adhesive contact. Support the tower and push it toward the carrier until the rigid feet seat and the lower hooks unload; then spread both accessible spring fingers outward only enough to clear their hooks and withdraw away from the carrier along optical +Z. Keep the legs released until the hooks pass above the host. Do not force the whole tower straight up with hooks engaged.",
        "stack_platform_bottom_z_mm": STACK_TOP_Z,
        "supported_hosts": list(SUPPORTED_HOSTS),
        "load_path": "Carrier seats -> integral tower feet/legs -> optical platform. Hooks prevent withdrawal. No stack load passes through FC dampers, PCB or battery.",
        "latch_fit": latch_fit_contract(),
    }


def _radial(shape, x, y):
    result = shape.copy()
    result.rotate(V(), V(0, 0, 1), math.degrees(math.atan2(y, x)))
    return result


def _host_seat(radius):
    tab = box(
        HOST_SEAT_OUTER - FOOT_INNER_OFFSET,
        HOST_SEAT_WIDTH,
        DECK_THICKNESS,
        (radius + FOOT_INNER_OFFSET, -HOST_SEAT_WIDTH / 2, 0),
    )
    opening = box(
        HOST_SEAT_OUTER - HOST_SEAT_EDGE + 1,
        HOST_SLOT_WIDTH,
        DECK_THICKNESS + 2,
        (radius + HOST_SEAT_EDGE, -HOST_SLOT_WIDTH / 2, -1),
    )
    guide = box(
        FIXED_LEG_THICKNESS + 2 * NOMINAL_CLEARANCE,
        LEG_WIDTH + 2 * NOMINAL_CLEARANCE,
        DECK_THICKNESS + 2,
        (
            radius + FIXED_LEG_INNER - NOMINAL_CLEARANCE,
            -LEG_WIDTH / 2 - NOMINAL_CLEARANCE,
            -1,
        ),
    )
    return tab.cut(opening).cut(guide).removeSplitter()


def platform_shape():
    pieces = []
    for x, y in ANCHOR_CENTRES:
        radius = math.hypot(x, y)
        arm = box(
            radius + HOST_SEAT_EDGE, ARM_WIDTH, DECK_THICKNESS, (0, -ARM_WIDTH / 2, 0)
        )
        piece = union([arm, _host_seat(radius)])
        guide = box(
            FIXED_LEG_THICKNESS + 2 * NOMINAL_CLEARANCE,
            LEG_WIDTH + 2 * NOMINAL_CLEARANCE,
            DECK_THICKNESS + 2,
            (
                radius + FIXED_LEG_INNER - NOMINAL_CLEARANCE,
                -LEG_WIDTH / 2 - NOMINAL_CLEARANCE,
                -1,
            ),
        )
        pieces.append(_radial(piece.cut(guide), x, y))
    return union(pieces).removeSplitter()


def add_host_interface(shape):
    platform = platform_shape()
    platform.translate(V(0, 0, HOST_DECK_BOTTOM_Z))
    combined = shape.fuse(platform)
    # Carrier arms and device decks can overlap the tabs: cut the guides last.
    for x, y in ANCHOR_CENTRES:
        radius = math.hypot(x, y)
        guide = box(
            FIXED_LEG_THICKNESS + 2 * NOMINAL_CLEARANCE,
            LEG_WIDTH + 2 * NOMINAL_CLEARANCE,
            DECK_THICKNESS + 2,
            (
                radius + FIXED_LEG_INNER - NOMINAL_CLEARANCE,
                -LEG_WIDTH / 2 - NOMINAL_CLEARANCE,
                HOST_DECK_BOTTOM_Z - 1,
            ),
        )
        combined = combined.cut(_radial(guide, x, y))
    return combined.removeSplitter()


def annotate_interface(obj):
    set_property(
        obj, "StackInterfaceContract", json.dumps(interface_contract(), sort_keys=True)
    )
    set_property(obj, "StackFitVerified", False, "App::PropertyBool")


def attach_to_host(group, host):
    if host.Name not in SUPPORTED_HOSTS or host.Document != group.Document:
        raise ValueError(
            "Optical stack requires a supported carrier in the same document"
        )
    old = group.getParentGeoFeatureGroup()
    if old is not None and old != host:
        old.removeObject(group)
    host.addObject(group)
    group.Placement = App.Placement(V(0, 0, STACK_TOP_Z), App.Rotation())
    set_property(group, "StackHostName", host.Name)
    annotate_interface(group)
    group.Document.recompute()


def _hook(radius):
    # A broad square retention face and a lower insertion ramp; the nose stays
    # 1.5 mm thick, rather than ending in an unprintable knife edge.
    points = [
        V(radius + HOOK_TIP_OFFSET, -LEG_WIDTH / 2, HOOK_TOP_Z),
        V(radius + LEG_INNER_OFFSET, -LEG_WIDTH / 2, HOOK_TOP_Z),
        V(radius + LEG_INNER_OFFSET, -LEG_WIDTH / 2, HOOK_BOTTOM_Z),
        V(radius + HOOK_TIP_OFFSET, -LEG_WIDTH / 2, HOOK_TOP_Z - HOOK_TIP_THICKNESS),
    ]
    return Part.Face(Part.makePolygon(points + [points[0]])).extrude(V(0, LEG_WIDTH, 0))


def _spring_finger(radius):
    beam = box(
        LATCH_LEG_THICKNESS,
        LEG_WIDTH,
        -HOOK_BOTTOM_Z,
        (radius + LEG_INNER_OFFSET, -LEG_WIDTH / 2, HOOK_BOTTOM_Z),
    )
    root = box(
        ROOT_RADIUS,
        LEG_WIDTH,
        ROOT_RADIUS,
        (radius + LEG_INNER_OFFSET - ROOT_RADIUS, -LEG_WIDTH / 2, -ROOT_RADIUS),
    )
    round_cut = Part.makeCylinder(
        ROOT_RADIUS,
        LEG_WIDTH + 2,
        V(radius + LEG_INNER_OFFSET - ROOT_RADIUS, -LEG_WIDTH / 2 - 1, -ROOT_RADIUS),
        V(0, 1, 0),
    )
    return union([beam, _hook(radius), root.cut(round_cut)]).removeSplitter()


def _fixed_leg_pieces(radius):
    beam = box(
        FIXED_LEG_THICKNESS,
        LEG_WIDTH,
        TOWER_HEIGHT + GUIDE_TONGUE_DEPTH,
        (radius + FIXED_LEG_INNER, -LEG_WIDTH / 2, -TOWER_HEIGHT - GUIDE_TONGUE_DEPTH),
    )
    foot = box(
        FOOT_OUTER_OFFSET - FOOT_INNER_OFFSET,
        HOST_SEAT_WIDTH,
        FOOT_THICKNESS,
        (radius + FOOT_INNER_OFFSET, -HOST_SEAT_WIDTH / 2, -TOWER_HEIGHT),
    )
    return beam, foot


def _fixed_leg(radius):
    return union(list(_fixed_leg_pieces(radius))).removeSplitter()


def _latch_leg(radius):
    return union([_fixed_leg(radius), _spring_finger(radius)]).removeSplitter()


def tower_shape():
    pieces = []
    for x, y in ANCHOR_CENTRES:
        radius = math.hypot(x, y)
        arm = box(
            radius + LEG_OUTER_OFFSET, LEG_WIDTH, DECK_THICKNESS, (0, -LEG_WIDTH / 2, 0)
        )
        pieces.append(_radial(union([arm, _latch_leg(radius)]), x, y))
    return union(pieces).removeSplitter()


def latch_release_envelopes():
    """Conservative lateral finger envelope, with the root fillet filled."""
    rows = []
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        radial = V(x / radius, y / radius, 0)
        finger = _spring_finger(radius).fuse(
            box(
                ROOT_RADIUS,
                LEG_WIDTH,
                ROOT_RADIUS,
                (radius + LEG_INNER_OFFSET - ROOT_RADIUS, -LEG_WIDTH / 2, -ROOT_RADIUS),
            )
        )
        rows.append(
            (index, _radial(finger.removeSplitter(), x, y), radial * MAX_RELEASE_TRAVEL)
        )
    return rows


def _release_tip_bounds(radius, displacement):
    """Rigid tip under a cantilever screening rotation and axial shortening.

    This deliberately uses the shorter conservative free length for rotation
    and shortening. It is a kinematic screen, not an elastic/contact solver.
    """
    pivot = V(radius + LEG_INNER_OFFSET + LATCH_LEG_THICKNESS / 2, 0, HOOK_TOP_Z)
    tip = union(
        [
            _hook(radius),
            box(
                LATCH_LEG_THICKNESS,
                LEG_WIDTH,
                HOOK_TOP_Z - HOOK_BOTTOM_Z,
                (radius + LEG_INNER_OFFSET, -LEG_WIDTH / 2, HOOK_BOTTOM_Z),
            ),
        ]
    )
    angle = 1.5 * displacement / FREE_BEAM_LENGTH
    shortening = 0.6 * displacement**2 / FREE_BEAM_LENGTH
    tip.rotate(pivot, V(0, 1, 0), -math.degrees(angle))
    tip.translate(V(displacement, 0, shortening))
    return tip.BoundBox


def hook_rotation_release_envelopes():
    """Continuous conservative interval boxes for the rotating/shortening tips.

    For every interval, a midpoint tip box is expanded by a speed bound times
    half the interval width. The speed bound includes translation, rotation of
    every tip point, and beam shortening, so the sampled boxes enclose the full
    prescribed kinematic path. No printed shape is replaced by a deflected STL.
    """
    rows = []
    intervals = 64
    step = MAX_RELEASE_TRAVEL / intervals
    tip_radius = math.hypot(
        LEG_INNER_OFFSET + LATCH_LEG_THICKNESS / 2 - HOOK_TIP_OFFSET,
        HOOK_TOP_Z - HOOK_BOTTOM_Z,
    )
    speed = (
        1
        + 1.2 * MAX_RELEASE_TRAVEL / FREE_BEAM_LENGTH
        + 1.5 * tip_radius / FREE_BEAM_LENGTH
    )
    padding = speed * step / 2 + 1e-6
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        for interval in range(intervals):
            bounds = _release_tip_bounds(radius, (interval + 0.5) * step)
            shape = box(
                bounds.XLength + 2 * padding,
                LEG_WIDTH,
                bounds.ZLength + 2 * padding,
                (bounds.XMin - padding, -LEG_WIDTH / 2, bounds.ZMin - padding),
            )
            rows.append((index, interval, _radial(shape, x, y)))
    return rows


def released_tower_envelope():
    """Rigid feet stay put; the released fingers lie outboard of the U seats."""
    pieces = []
    for x, y in ANCHOR_CENTRES:
        radius = math.hypot(x, y)
        arm = box(
            radius + LEG_OUTER_OFFSET, LEG_WIDTH, DECK_THICKNESS, (0, -LEG_WIDTH / 2, 0)
        )
        tip = _release_tip_bounds(radius, MAX_RELEASE_TRAVEL)
        # A broad fixed-root-to-released-tip finger envelope is outside the
        # host catch edge; the inner hook is represented only at released pose.
        beam = box(
            LATCH_LEG_THICKNESS + MAX_RELEASE_TRAVEL + 1,
            LEG_WIDTH,
            -HOOK_TOP_Z + 1,
            (radius + LEG_INNER_OFFSET, -LEG_WIDTH / 2, HOOK_TOP_Z - 1),
        )
        end = box(
            tip.XLength, LEG_WIDTH, tip.ZLength, (tip.XMin, -LEG_WIDTH / 2, tip.ZMin)
        )
        root = box(
            ROOT_RADIUS + LATCH_LEG_THICKNESS + MAX_RELEASE_TRAVEL,
            LEG_WIDTH,
            ROOT_RADIUS,
            (radius + LEG_INNER_OFFSET - ROOT_RADIUS, -LEG_WIDTH / 2, -ROOT_RADIUS),
        )
        pieces.append(_radial(union([arm, _fixed_leg(radius), beam, end, root]), x, y))
    return union(pieces).removeSplitter()


def latch_coupon_shapes():
    host = _host_seat(0).fuse(
        box(8, HOST_SEAT_WIDTH, DECK_THICKNESS, (-11, -HOST_SEAT_WIDTH / 2, 0))
    )
    tower = _latch_leg(0).fuse(
        box(12, LEG_WIDTH, DECK_THICKNESS, (-5.3, -LEG_WIDTH / 2, 0))
    )
    return {
        "OpticalLatchHostCoupon": host.removeSplitter(),
        "OpticalLatchTowerCoupon": tower.removeSplitter(),
    }


def is_removable_head_part(obj, stack):
    return belongs_to_group(obj, stack)


def latch_press_reservations():
    rows = []
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        shape = box(8, 10, 10, (radius + LEG_OUTER_OFFSET, -5, -TOWER_HEIGHT + 3))
        rows.append((index, _radial(shape, x, y)))
    return rows


def build_fit_coupons(doc):
    group = create_group(
        doc, "OpticalLatchFitCoupons", "Print first | PA12 optical latch and locator"
    )
    printed = []
    for name, shape in latch_coupon_shapes().items():
        anchor_rotation = App.Rotation(V(0, 0, 1), 45)
        rotation = (
            App.Rotation(V(1, 0, 0), 180).multiply(anchor_rotation)
            if "Host" in name
            else anchor_rotation
        )
        obj = create_printed_part(
            doc,
            group,
            name,
            "PRINT FIRST | " + name,
            shape,
            rotation,
            "Same dimensions and print orientation as the installed optical latch interface. Mate with the other coupon before full manufacture; confirm rigid locator fit, positive hook capture, rocking removal with a measured existing adhesive pad if needed, release force, repeated release, no permanent set and retention in both load directions. Do not infer material strain capacity or flight qualification from CAD.",
        )
        set_property(obj, "PrintSKU", name)
        set_property(obj, "Role", "Optical latch fit coupon; not installed")
        annotate_interface(obj)
        printed.append(obj)
    return {"group": group, "printed": printed}


def manufacturing_wall_probes():
    rows = []
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        angle = math.atan2(y, x)

        def point(radial, tangent, z):
            return (
                (radius + radial) * math.cos(angle) - tangent * math.sin(angle),
                (radius + radial) * math.sin(angle) + tangent * math.cos(angle),
                z,
            )

        rows.extend(
            [
                (
                    f"optical_fixed_leg_{index}",
                    "OpticalMountBase",
                    point(FIXED_LEG_INNER - 0.01, 0, -TOWER_HEIGHT / 2),
                    point(
                        FIXED_LEG_INNER + FIXED_LEG_THICKNESS + 0.01,
                        0,
                        -TOWER_HEIGHT / 2,
                    ),
                    FIXED_LEG_THICKNESS,
                ),
                (
                    f"optical_latch_finger_{index}",
                    "OpticalMountBase",
                    point(LEG_INNER_OFFSET - 0.01, 0, -TOWER_HEIGHT / 2),
                    point(LEG_OUTER_OFFSET + 0.01, 0, -TOWER_HEIGHT / 2),
                    LATCH_LEG_THICKNESS,
                ),
                (
                    f"optical_rigid_foot_{index}",
                    "OpticalMountBase",
                    point(2.8, 4, -TOWER_HEIGHT - 0.01),
                    point(2.8, 4, -TOWER_HEIGHT + FOOT_THICKNESS + 0.01),
                    FOOT_THICKNESS,
                ),
            ]
        )
        for host_name in SUPPORTED_HOSTS.values():
            rows.append(
                (
                    f"{host_name}_latch_cheek_{index}",
                    host_name,
                    point(6, HOST_SLOT_WIDTH / 2 - 0.01, HOST_DECK_BOTTOM_Z + 1),
                    point(6, HOST_SEAT_WIDTH / 2 + 0.01, HOST_DECK_BOTTOM_Z + 1),
                    HOST_CHEEK_WIDTH,
                )
            )
    return rows


def rigid_float_shape_bound(shape):
    """Enclose XY/yaw motion permitted by two opposed rigid rectangular guides.

    Translation and yaw share the finite guide clearances; their separate
    maxima cannot occur together. Interval expansion encloses every angle.
    Axial play is added in +Z. Rocking is deliberately NOT certified: measured
    anti-rattle seating and pointing acceptance remain mandatory.
    """
    gap = MAX_RADIAL_FLOAT
    a, b = FIXED_LEG_THICKNESS / 2, LEG_WIDTH / 2
    radius = math.hypot(*ANCHOR_CENTRES[0]) + FIXED_LEG_INNER + a

    def translations(theta):
        c, s = math.cos(theta), math.sin(theta)
        return (
            a + gap - a * c - b * s - radius * (1 - c),
            b + gap - a * s - b * c - radius * s,
        )

    low, high = 0.0, math.asin(gap / radius)
    for _ in range(50):
        middle = (low + high) / 2
        if min(translations(middle)) >= 0:
            low = middle
        else:
            high = middle
    maximum_angle = low
    # Work in the diagonal guide frame: global axis-aligned boxes falsely
    # fill the corner between a slim spine and the rotated FC wiring lane.
    aligned = shape.copy()
    aligned.rotate(V(), V(0, 0, 1), -45)
    bounds = aligned.BoundBox
    points = [
        (x, y) for x in (bounds.XMin, bounds.XMax) for y in (bounds.YMin, bounds.YMax)
    ]
    max_radius = max(math.hypot(x, y) for x, y in points)
    xs, ys = [], []
    count = 64
    step = maximum_angle / count
    for index in range(count):
        tr, tt = translations(index * step)
        padding = max_radius * step / 2 + 1e-8
        for sign in (-1, 1):
            theta = sign * (index + 0.5) * step
            c, s = math.cos(theta), math.sin(theta)
            for x, y in points:
                px, py = x * c - y * s, x * s + y * c
                xs.extend((px - max(tr, 0) - padding, px + max(tr, 0) + padding))
                ys.extend((py - max(tt, 0) - padding, py + max(tt, 0) + padding))
    envelope = box(
        max(xs) - min(xs),
        max(ys) - min(ys),
        bounds.ZLength + gap,
        (min(xs), min(ys), bounds.ZMin),
    )
    envelope.rotate(V(), V(0, 0, 1), 45)
    return envelope


def rigid_float_component_bounds():
    rows = []
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        arm = box(
            radius + LEG_OUTER_OFFSET, LEG_WIDTH, DECK_THICKNESS, (0, -LEG_WIDTH / 2, 0)
        )
        load_bound = union(
            [
                rigid_float_shape_bound(_radial(piece, x, y))
                for piece in _fixed_leg_pieces(radius)
            ]
        )
        rows.append((f"load_leg_{index}", load_bound))
        for kind, shape in (
            ("finger", _spring_finger(radius)),
            ("upper_arm", arm),
        ):
            rows.append(
                (f"{kind}_{index}", rigid_float_shape_bound(_radial(shape, x, y)))
            )
    return rows


def fixed_load_support_shape():
    pieces = []
    for x, y in ANCHOR_CENTRES:
        radius = math.hypot(x, y)
        arm = box(
            radius + LEG_OUTER_OFFSET, LEG_WIDTH, DECK_THICKNESS, (0, -LEG_WIDTH / 2, 0)
        )
        pieces.append(_radial(union([_fixed_leg(radius), arm]), x, y))
    return union(pieces).removeSplitter()
