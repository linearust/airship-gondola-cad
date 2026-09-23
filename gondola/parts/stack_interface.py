"""Common optical tower with two directly clamped broad seating feet.

Clearance holes permit assembly registration. Both feet must seat before their
ordinary M2 fasteners are tightened; no operating axial gap or snap preload is
specified. Physical clamp retention, print flatness and PA12 creep need testing.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, box, set_property, union
from gondola.contracts import fasteners
from gondola.contracts.design import (
    STACK_ANCHOR_CENTRES,
    STACK_ANCHOR_LOCATIONS,
    STACK_PITCH_MM,
)
from gondola.contracts.hardware import HEX_NUT_SOURCE, STACK_SCREW_SOURCE

from . import purchased_hardware

V = App.Vector
PITCH_MM = STACK_PITCH_MM
ANCHOR_CENTRES = STACK_ANCHOR_CENTRES
ARM_WIDTH = 5.0
DECK_THICKNESS = 2.0
TOP_BEAM_THICKNESS = 3.0
HOST_DECK_BOTTOM_Z = 10.2
HOST_SUPPORT_Z = HOST_DECK_BOTTOM_Z + DECK_THICKNESS
TOWER_HEIGHT = 32.0
STACK_TOP_Z = HOST_SUPPORT_Z + TOWER_HEIGHT
FOOT_THICKNESS = 2.0
FOOT_INNER_OFFSET = -3.6
FOOT_OUTER_OFFSET = 7.3
FIXED_LEG_INNER = -1.4
FIXED_LEG_THICKNESS = 2.0
LEG_WIDTH = 8.0
HOST_SEAT_OUTER = 8.0
HOST_SEAT_WIDTH = 8.0
CLAMP_AXIS_OFFSET = 4.0
CLAMP_HOLE_DIAMETER = 2.6
CLAMP_SCREW_LENGTH = 8.0
DIMENSION_ALLOWANCE = 0.3
MINIMUM_RECEIVED_BOLT_DIAMETER = 1.8
MAX_RADIAL_FLOAT = (
    CLAMP_HOLE_DIAMETER + DIMENSION_ALLOWANCE - MINIMUM_RECEIVED_BOLT_DIAMETER
)
CLAMP_CENTRES = tuple(
    (
        x * (1 + CLAMP_AXIS_OFFSET / math.hypot(x, y)),
        y * (1 + CLAMP_AXIS_OFFSET / math.hypot(x, y)),
    )
    for x, y in ANCHOR_CENTRES
)
SUPPORTED_HOSTS = {
    "BatteryEquipmentModule": "BatteryMount",
    "ElectronicsEquipmentModule": "ElectronicsMount",
}


def clamp_fit_contract():
    return {
        "dimension_allowance_each_printed_dimension_mm": DIMENSION_ALLOWANCE,
        "clearance_hole_diameter_mm": CLAMP_HOLE_DIAMETER,
        "maximum_accepted_hole_diameter_mm": CLAMP_HOLE_DIAMETER + DIMENSION_ALLOWANCE,
        "minimum_received_screw_crest_diameter_mm": MINIMUM_RECEIVED_BOLT_DIAMETER,
        "maximum_seated_registration_axis_offset_mm": MAX_RADIAL_FLOAT,
        "nominal_axial_seating_gap_mm": 0.0,
        "printed_grip_mm": DECK_THICKNESS + FOOT_THICKNESS,
        "screw_length_mm": CLAMP_SCREW_LENGTH,
        "nut_height_mm": fasteners.HEX_NUT_HEIGHT,
        "nominal_tip_projection_mm": CLAMP_SCREW_LENGTH
        - DECK_THICKNESS
        - FOOT_THICKNESS
        - fasteners.HEX_NUT_HEIGHT,
        "tip_projection_with_both_prints_0_3mm_thicker_mm": CLAMP_SCREW_LENGTH
        - DECK_THICKNESS
        - FOOT_THICKNESS
        - 2 * DIMENSION_ALLOWANCE
        - fasteners.HEX_NUT_HEIGHT,
        "minimum_received_flat_head_bearing_diameter_mm": 3.5,
        "concentric_flat_head_radial_land_at_maximum_hole_mm": (
            3.5 - CLAMP_HOLE_DIAMETER - DIMENSION_ALLOWANCE
        )
        / 2,
        "concentric_nut_radial_land_at_maximum_hole_mm": (
            fasteners.HEX_NUT_MIN_AF - CLAMP_HOLE_DIAMETER - DIMENSION_ALLOWANCE
        )
        / 2,
        "bearing_scope": "The listed radial lands assume concentric hardware and holes. At maximum accepted hole/screw clearance the screw may be eccentric by 0.55 mm within each hole, so a continuous all-around head or nut bearing land is not guaranteed. Inspect actual contact and reject edge tipping, local indentation or pull-through; CAD does not qualify bearing pressure or PA12 clamp creep.",
        "pointing_acceptance": "Seat both broad feet directly on the carrier and hand-snug both M2 clamps while holding the tower square. No adhesive anti-rattle pad or elastic latch is required or specified. Reject rocking, a foot that does not fully seat, or slip under cable loads; inspect print flatness and actual fastener dimensions. Clearance holes locate only approximately until the clamp friction is established. Holding torque, vibration retention, strength and PA12 creep remain unqualified.",
        "loosened_state": "Not an operating pointing datum. Perform foot-fastener service with the carrier removed from the rail and supported on a bench; envelope clearance is not modeled. Support tower upright; remove both nuts and withdraw screws downward before lifting the complete tower. No arbitrary tilted removal or loosened-flight clearance is claimed.",
    }


def interface_contract():
    return {
        "standard": f"Project structural stack: rigid legs at {STACK_ANCHOR_LOCATIONS}, two outboard M2 clamps",
        "industry_standard_claimed": False,
        "axis_spacing_mm": math.sqrt(2) * PITCH_MM,
        "anchor_centres_xy_mm": ANCHOR_CENTRES,
        "clamp_centres_xy_mm": CLAMP_CENTRES,
        "printed_deck_thickness_mm": DECK_THICKNESS,
        "host_support_z_mm": HOST_SUPPORT_Z,
        "integral_tower_height_mm": TOWER_HEIGHT,
        "tower_foot_thickness_mm": FOOT_THICKNESS,
        "fixed_load_leg_section_mm": [FIXED_LEG_THICKNESS, LEG_WIDTH],
        "top_beam_section_mm": [TOP_BEAM_THICKNESS, LEG_WIDTH],
        "top_beam_overhang_past_legs_mm": 0.0,
        "tower_attachment": "Two broad integral 2 mm feet seat directly on 2 mm carrier tabs. Two existing-kit M2x8 screws enter from below; ordinary M2 hex nuts sit above the feet. No washers, spring fingers, precision locating tongues or anti-rattle pads.",
        "service": "Disconnect sensor wiring, remove the carrier from the rail and support it on a bench; the balloon surface is not modeled and underside access on the balloon is not claimed. Support the tower upright, hold each exposed nut from the outboard side, undo each screw with a 1.5 mm key from below, remove both nuts and withdraw both screws downward. Lift the complete tower along optical +Z before servicing the host device. Re-seat and tighten both feet, then reinstall and retrim the carrier before use.",
        "stack_platform_bottom_z_mm": STACK_TOP_Z,
        "supported_hosts": list(SUPPORTED_HOSTS),
        "load_path": "Carrier tabs -> directly clamped broad tower feet -> two rigid legs -> one straight rectangular beam supporting the optical pivot. Beam ends are flush with the leg outer faces; there are no unused top branches. No stack load passes through FC dampers, PCB or battery. Bolt preload seats the contacts; friction retention is not qualified by CAD.",
        "clamp_fit": clamp_fit_contract(),
    }


def _radial(shape, x, y):
    result = shape.copy()
    result.rotate(V(), V(0, 0, 1), math.degrees(math.atan2(y, x)))
    return result


def _hole_cut(shape, bottom, depth):
    for x, y in CLAMP_CENTRES:
        shape = shape.cut(
            Part.makeCylinder(CLAMP_HOLE_DIAMETER / 2, depth, V(x, y, bottom))
        )
    return shape.removeSplitter()


def platform_shape():
    pieces = []
    for x, y in ANCHOR_CENTRES:
        radius = math.hypot(x, y)
        arm = box(
            radius + HOST_SEAT_OUTER, ARM_WIDTH, DECK_THICKNESS, (0, -ARM_WIDTH / 2, 0)
        )
        seat = box(
            HOST_SEAT_OUTER - FOOT_INNER_OFFSET,
            HOST_SEAT_WIDTH,
            DECK_THICKNESS,
            (radius + FOOT_INNER_OFFSET, -HOST_SEAT_WIDTH / 2, 0),
        )
        pieces.append(_radial(union([arm, seat]), x, y))
    return _hole_cut(union(pieces), -1, DECK_THICKNESS + 2)


def add_host_interface(shape):
    platform = platform_shape()
    platform.translate(V(0, 0, HOST_DECK_BOTTOM_Z))
    return _hole_cut(shape.fuse(platform), HOST_DECK_BOTTOM_Z - 1, DECK_THICKNESS + 2)


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


def _fixed_leg_pieces(radius):
    return (
        box(
            FIXED_LEG_THICKNESS,
            LEG_WIDTH,
            TOWER_HEIGHT,
            (radius + FIXED_LEG_INNER, -LEG_WIDTH / 2, -TOWER_HEIGHT),
        ),
        box(
            FOOT_OUTER_OFFSET - FOOT_INNER_OFFSET,
            HOST_SEAT_WIDTH,
            FOOT_THICKNESS,
            (radius + FOOT_INNER_OFFSET, -HOST_SEAT_WIDTH / 2, -TOWER_HEIGHT),
        ),
    )


def _top_beam_half(radius):
    """One half of a continuous beam ending flush with the leg outer face."""
    return box(
        radius + FIXED_LEG_INNER + FIXED_LEG_THICKNESS,
        LEG_WIDTH,
        TOP_BEAM_THICKNESS,
        (0, -LEG_WIDTH / 2, 0),
    )


def tower_shape():
    """Open rectangular portal; outboard foot material stays only at the feet."""
    pieces = []
    for x, y in ANCHOR_CENTRES:
        radius = math.hypot(x, y)
        pieces.append(
            _radial(union([_top_beam_half(radius), *_fixed_leg_pieces(radius)]), x, y)
        )
    return _hole_cut(union(pieces), -TOWER_HEIGHT - 1, FOOT_THICKNESS + 2)


def build_stack_hardware(doc, group):
    objects = []
    for index, (x, y) in enumerate(CLAMP_CENTRES):
        for kind, shape, z, sku, source in (
            (
                "Bolt",
                purchased_hardware.screw_shape(CLAMP_SCREW_LENGTH),
                -TOWER_HEIGHT - DECK_THICKNESS,
                "M2X8_BUTTON_HEAD",
                STACK_SCREW_SOURCE,
            ),
            (
                "Nut",
                purchased_hardware.hex_nut_shape(),
                -TOWER_HEIGHT + FOOT_THICKNESS,
                "M2_HEX_NUT",
                HEX_NUT_SOURCE,
            ),
        ):
            local = shape.copy()
            local.translate(V(x, y, z))
            obj = purchased_hardware.add_hardware(
                doc,
                group,
                f"OpticalStackFoot{kind}{index}",
                f"BUY | optical tower foot {index + 1} {kind.lower()}",
                local,
                sku,
                "Two directly seated 2 mm prints; M2x8 from below and M2 hex nut above. No washer. 4 mm nominal grip, full 1.6 mm nut engagement and 2.4 mm nominal projection. Both prints 0.3 mm thicker leave 1.8 mm before screw-length/nut tolerances. Require measured flat head bearing diameter >=3.5 mm, hole <=2.9 mm and screw crest diameter >=1.8 mm. Physical clamp, print flatness and PA12 creep unverified.",
                source,
                fasteners.KIT_MATERIAL,
            )
            set_property(obj, "StackEnd", index, "App::PropertyInteger")
            objects.append(obj)
    return objects


def is_removable_head_part(obj, stack):
    return belongs_to_group(obj, stack)


def clamp_tool_reservations():
    """Simple access envelopes in tower coordinates, not measured tool bodies."""
    rows = []
    for index, (x, y) in enumerate(CLAMP_CENTRES):
        radius = math.hypot(x, y)
        key = Part.makeCylinder(
            3, 20, V(radius, 0, -TOWER_HEIGHT - DECK_THICKNESS - 22)
        )
        nut = box(10, 8, 4, (radius - 2.5, -4, -TOWER_HEIGHT + FOOT_THICKNESS))
        rows.extend(
            ((f"key_{index}", _radial(key, x, y)), (f"nut_{index}", _radial(nut, x, y)))
        )
    return rows


def manufacturing_wall_probes():
    rows = []
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius, angle = math.hypot(x, y), math.atan2(y, x)

        def point(radial, tangent, z):
            return (
                (radius + radial) * math.cos(angle) - tangent * math.sin(angle),
                (radius + radial) * math.sin(angle) + tangent * math.cos(angle),
                z,
            )

        rows.extend(
            [
                (
                    f"optical_top_beam_{index}",
                    "OpticalMountBase",
                    (x / 2, y / 2, -0.01),
                    (x / 2, y / 2, TOP_BEAM_THICKNESS + 0.01),
                    TOP_BEAM_THICKNESS,
                ),
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
                    f"optical_rigid_foot_{index}",
                    "OpticalMountBase",
                    point(2.8, 3, -TOWER_HEIGHT - 0.01),
                    point(2.8, 3, -TOWER_HEIGHT + FOOT_THICKNESS + 0.01),
                    FOOT_THICKNESS,
                ),
            ]
        )
        for host_name in SUPPORTED_HOSTS.values():
            rows.append(
                (
                    f"{host_name}_clamp_tab_{index}",
                    host_name,
                    point(2.8, 3, HOST_DECK_BOTTOM_Z - 0.01),
                    point(2.8, 3, HOST_SUPPORT_Z + 0.01),
                    DECK_THICKNESS,
                )
            )
    return rows


def rigid_float_shape_bound(shape):
    """Bound seated XY/yaw registration from two circular clearance-hole pairs.

    The screw axis can move in BOTH printed holes. Relative axis error is at
    most (maximum hole diameter - minimum accepted screw crest diameter).
    For opposed axes at +/-R, |t+d|<=g and |t-d|<=g imply |t|²+|d|²<=g².
    This enclosing disk intentionally relaxes the exact lens. No axial motion
    is added: feet must seat and be clamped before accepting optical pointing.
    """
    gap = MAX_RADIAL_FLOAT
    radius = math.hypot(*CLAMP_CENTRES[0])
    maximum_angle = 2 * math.asin(gap / (2 * radius))
    aligned = shape.copy()
    aligned.rotate(V(), V(0, 0, 1), -45)
    bounds = aligned.BoundBox
    points = [
        (x, y) for x in (bounds.XMin, bounds.XMax) for y in (bounds.YMin, bounds.YMax)
    ]
    max_radius = max(math.hypot(x, y) for x, y in points)
    xs, ys = [], []
    count, step = 64, maximum_angle / 64
    for index in range(count):
        displacement = 2 * radius * math.sin(index * step / 2)
        translation = math.sqrt(max(0, gap**2 - displacement**2))
        padding = max_radius * step / 2 + 1e-8
        for sign in (-1, 1):
            theta = sign * (index + 0.5) * step
            c, s = math.cos(theta), math.sin(theta)
            for x, y in points:
                px, py = x * c - y * s, x * s + y * c
                xs.extend((px - translation - padding, px + translation + padding))
                ys.extend((py - translation - padding, py + translation + padding))
    envelope = box(
        max(xs) - min(xs),
        max(ys) - min(ys),
        bounds.ZLength,
        (min(xs), min(ys), bounds.ZMin),
    )
    envelope.rotate(V(), V(0, 0, 1), 45)
    return envelope


def rigid_float_component_bounds():
    """Bound two legs and two analytical halves of the single integral beam."""
    rows = []
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        beam_half = _top_beam_half(radius)
        rows.append(
            (
                f"load_leg_{index}",
                union(
                    [
                        rigid_float_shape_bound(_radial(piece, x, y))
                        for piece in _fixed_leg_pieces(radius)
                    ]
                ),
            )
        )
        rows.append(
            (
                f"top_beam_half_{index}",
                rigid_float_shape_bound(_radial(beam_half, x, y)),
            )
        )
    return rows
