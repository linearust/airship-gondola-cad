"""Optional power portal clamped through the common square carrier slot array.

The carrier has no dedicated portal holes. Two opposed feet use existing outer
M2 slots; accepted seated registration includes their full available travel.
Physical clamp retention, print flatness and PA12 creep remain unqualified.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import box, set_property, union
from gondola.contracts import fasteners
from gondola.contracts.design import (
    STACK_ANCHOR_CENTRES,
    STACK_PITCH_MM,
)

from . import mounting_plate, mounting_slots, purchased_hardware

V = App.Vector
PITCH_MM = STACK_PITCH_MM
ANCHOR_CENTRES = STACK_ANCHOR_CENTRES
DECK_THICKNESS = mounting_plate.THICKNESS_MM
TOP_BEAM_THICKNESS = 3.0
HOST_DECK_BOTTOM_Z = mounting_plate.CARRIER_BOTTOM_Z
HOST_SUPPORT_Z = mounting_plate.CARRIER_SUPPORT_Z
TOWER_HEIGHT = 32.0
STACK_TOP_Z = HOST_SUPPORT_Z + TOWER_HEIGHT
FOOT_THICKNESS = 2.0
FOOT_WIDTH = 13.0
FOOT_LENGTH = 9.0
FOOT_INBOARD_Y = 4.0
FOOT_INBOARD_CHAMFER = 5.0
FIXED_LEG_INNER = -1.4
FIXED_LEG_THICKNESS = 2.0
LEG_WIDTH = 8.0
CLAMP_HOLE_DIAMETER = 2.6
CLAMP_SCREW_LENGTH = 8.0
DIMENSION_ALLOWANCE = 0.3
MINIMUM_RECEIVED_BOLT_DIAMETER = 1.8
# The relative foot-hole/host-slot axis allowance includes radial clearance in
# both printed features. Slot length itself is a separate, coupled constraint.
HOST_SLOT_WIDTH = next(
    row["width_mm"] for row in mounting_slots.rows() if row["family"] == "side"
)
COMBINED_AXIS_CLEARANCE = (
    (CLAMP_HOLE_DIAMETER + HOST_SLOT_WIDTH) / 2
    + DIMENSION_ALLOWANCE
    - MINIMUM_RECEIVED_BOLT_DIAMETER
)
CLAMP_CENTRES = tuple(
    (sign * mounting_slots.SIDE_X, sign * mounting_slots.SIDE_Y_RANGE[1])
    for sign in (-1, 1)
)
HOST_SLOT_TRAVEL = mounting_slots.SIDE_Y_RANGE[1] - mounting_slots.SIDE_Y_RANGE[0]
REGISTRATION_CELLS = 256
MECHANICAL_HOSTS = {
    "BatteryEquipmentModule": "BatteryMount",
    "ElectronicsEquipmentModule": "ElectronicsMount",
    "AccessoryEquipmentModule": "AccessoryMount",
}
HOST_ORIGINS_XY = {name: (0.0, 0.0) for name in MECHANICAL_HOSTS}


def host_origin_xy(host_name=None):
    """Common attachment datum in a carrier, accepting its group or print name."""
    if host_name is None:
        return (0.0, 0.0)
    for group, part in MECHANICAL_HOSTS.items():
        if host_name in (group, part):
            return HOST_ORIGINS_XY[group]
    raise ValueError("Unknown structural stack host: " + str(host_name))


def host_placement(host_name, z=HOST_SUPPORT_Z):
    """Local placement of the common mechanical datum, not a device fit claim."""
    return App.Placement(V(*host_origin_xy(host_name), z), App.Rotation())


def clamp_fit_contract():
    return {
        "dimension_allowance_each_printed_dimension_mm": DIMENSION_ALLOWANCE,
        "foot_clearance_hole_diameter_mm": CLAMP_HOLE_DIAMETER,
        "host_slot_width_mm": HOST_SLOT_WIDTH,
        "maximum_accepted_hole_or_slot_width_mm": CLAMP_HOLE_DIAMETER
        + DIMENSION_ALLOWANCE,
        "minimum_received_screw_crest_diameter_mm": MINIMUM_RECEIVED_BOLT_DIAMETER,
        "combined_axis_clearance_from_slot_centreline_mm": COMBINED_AXIS_CLEARANCE,
        "host_slot_centre_travel_mm": HOST_SLOT_TRAVEL,
        "nominal_position": "Opposed slot outer endpoints at (+27,+23) and (-27,-23) mm",
        "registration_scope": "Both foot axes must simultaneously fit the opposed carrier slots. Full slot travel plus printed clearance is enclosed by the continuous XY/yaw bound; this is not a circular-host-hole locating joint. Feet seat before tightening, with no operating axial gap.",
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
        "concentric_head_land_across_maximum_slot_width_mm": (
            3.5 - HOST_SLOT_WIDTH - DIMENSION_ALLOWANCE
        )
        / 2,
        "bearing_scope": "Underside bolt heads bridge a slot rather than a circular bore; the two transverse lands are the bearing surfaces. Minimum flat head diameter 3.5 mm and accepted slot width at most 2.9 mm provide only 0.3 mm per side when centred. Eccentric heads, tilted seating, indentation and PA12 creep need physical inspection; CAD does not qualify bearing pressure or clamp retention.",
        "assembly": "Centre the portal above the host, seat both feet and hand-snug both M2 clamps. Reject rocking or slip under wire loads. Slot end positions are assembly datums, not precision stops or an operating adjustment mechanism.",
        "service": "Remove the carrier from the rail and support it on a bench. Support the platform, remove the two nuts from above and withdraw the screws below before lifting vertically. Balloon clearance, arbitrary tilted extraction and loose-flight operation are not claimed.",
    }


def interface_contract(host_name=None):
    return {
        "standard": "Optional power portal on the common square carrier's opposed outer M2 slots",
        "industry_standard_claimed": False,
        "anchor_spacing_mm": math.sqrt(2) * PITCH_MM,
        "clamp_axis_spacing_mm": 2 * math.hypot(*CLAMP_CENTRES[0]),
        "anchor_centres_xy_mm": ANCHOR_CENTRES,
        "clamp_centres_xy_mm": CLAMP_CENTRES,
        "printed_deck_thickness_mm": DECK_THICKNESS,
        "host_support_z_mm": HOST_SUPPORT_Z,
        "integral_tower_height_mm": TOWER_HEIGHT,
        "tower_foot_thickness_mm": FOOT_THICKNESS,
        "tower_foot_size_xy_mm": [FOOT_WIDTH, FOOT_LENGTH],
        "tower_foot_inward_corner_chamfer_mm": FOOT_INBOARD_CHAMFER,
        "fixed_load_leg_section_mm": [FIXED_LEG_THICKNESS, LEG_WIDTH],
        "top_beam_section_mm": [TOP_BEAM_THICKNESS, LEG_WIDTH],
        "tower_attachment": "Two integral 13 x 9 x 2 mm feet seat within the 64 mm square carrier. An inward 5 mm corner relief retains the complete diagonal leg root while avoiding unnecessary inboard material. Two existing-kit M2x8 screws pass upward through the common outer slots and circular foot bores; ordinary M2 hex nuts sit above. No dedicated host holes, washers, ears or locating pieces.",
        "portal_top_beam_bottom_z_mm": STACK_TOP_Z,
        "power_deck_bottom_z_mm": STACK_TOP_Z + TOP_BEAM_THICKNESS - DECK_THICKNESS,
        "mechanical_hosts": dict(MECHANICAL_HOSTS),
        "carrier_datum_xy_mm": host_origin_xy(host_name),
        "mechanical_host_datums_xy_mm": dict(HOST_ORIGINS_XY),
        "scope": "Optional power platform only; the compact optical head has its own one-axis interface. Shared host slots do not qualify concurrent modules, wiring, access or tether loads. The saved optional-power screening determines permitted installed arrangements.",
        "load_path": "Carrier plate -> two directly clamped feet -> opposed diagonal legs -> integral beam and power deck. Loads bypass FC dampers, PCB and battery. Clamp friction retention remains unqualified.",
        "clamp_fit": clamp_fit_contract(),
    }


def _radial(shape, x, y):
    result = shape.copy()
    result.rotate(V(), V(0, 0, 1), math.degrees(math.atan2(y, x)))
    return result


def _hole_cut(shape, bottom, depth, origin=(0.0, 0.0)):
    for cx, cy in CLAMP_CENTRES:
        x, y = cx + origin[0], cy + origin[1]
        shape = shape.cut(
            Part.makeCylinder(CLAMP_HOLE_DIAMETER / 2, depth, V(x, y, bottom))
        )
    return shape.removeSplitter()


def annotate_interface(obj, host_name=None):
    set_property(
        obj,
        "StackInterfaceContract",
        json.dumps(interface_contract(host_name), sort_keys=True),
    )
    set_property(obj, "StackFitVerified", False, "App::PropertyBool")


def _fixed_leg_shape(radius):
    return box(
        FIXED_LEG_THICKNESS,
        LEG_WIDTH,
        TOWER_HEIGHT,
        (radius + FIXED_LEG_INNER, -LEG_WIDTH / 2, -TOWER_HEIGHT),
    )


def foot_outline_shape(index, *, bottom=-TOWER_HEIGHT, thickness=FOOT_THICKNESS):
    """One rectangular foot with an inward corner cut for inboard clearance."""
    x, y = ANCHOR_CENTRES[index]
    direction = math.copysign(1, x)
    centre_x = x + direction * 2.5
    centre_y = y + direction * 0.5
    shape = box(
        FOOT_WIDTH,
        FOOT_LENGTH,
        thickness,
        (centre_x - FOOT_WIDTH / 2, centre_y - FOOT_LENGTH / 2, bottom),
    )
    if FOOT_INBOARD_CHAMFER:
        direction = math.copysign(1, x)
        tip = V(
            centre_x - direction * FOOT_WIDTH / 2,
            y - direction * FOOT_INBOARD_Y,
            bottom - 1,
        )
        chamfer = Part.Face(
            Part.makePolygon(
                [
                    tip,
                    tip + V(direction * FOOT_INBOARD_CHAMFER, 0, 0),
                    tip + V(0, direction * FOOT_INBOARD_CHAMFER, 0),
                    tip,
                ]
            )
        ).extrude(V(0, 0, thickness + 2))
        shape = shape.cut(chamfer)
    return shape.removeSplitter()


def foot_shape(index, *, bottom=-TOWER_HEIGHT, thickness=FOOT_THICKNESS):
    """Complete foot/contact template including its structural clearance bore."""
    return _hole_cut(
        foot_outline_shape(index, bottom=bottom, thickness=thickness),
        bottom - 1,
        thickness + 2,
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
    """One diagonal portal with broad feet contained by the carrier plate."""
    pieces = []
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        pieces.extend(
            [
                _radial(
                    union([_top_beam_half(radius), _fixed_leg_shape(radius)]), x, y
                ),
                foot_shape(index),
            ]
        )
    return _hole_cut(union(pieces), -TOWER_HEIGHT - 1, FOOT_THICKNESS + 2)


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


def registration_cells():
    """Continuous conservative cells for the opposed slot/round-foot-hole pair.

    Each combined slot/circular-hole allowance is enclosed by a capsule's XY
    rectangle. At angle theta, opposed axis displacements are +(dx,dy) and
    -(dx,dy). Their translation intersections are |tx| <= g-|dx| and
    |ty| <= min(g-dy, travel+g+dy). Angular cell padding bounds dx/dy continuously;
    it is not a pose sample. The initial angle interval encloses the complete
    displacement disk of either slot. Only the near-nominal assembly branch is
    relevant; 180-degree installation is the identical opposed portal pose.
    """
    g, travel = COMBINED_AXIS_CLEARANCE, HOST_SLOT_TRAVEL
    x, y = CLAMP_CENTRES[1]
    radius = math.hypot(x, y)
    maximum_displacement = math.hypot(g, travel + g)
    maximum_angle = 2 * math.asin(maximum_displacement / (2 * radius))
    step = 2 * maximum_angle / REGISTRATION_CELLS
    error = radius * step / 2
    for index in range(REGISTRATION_CELLS):
        angle = -maximum_angle + (index + 0.5) * step
        c, s = math.cos(angle), math.sin(angle)
        dx, dy = x * c - y * s - x, x * s + y * c - y
        tx = g - max(0.0, abs(dx) - error)
        ty = min(g - dy, travel + g + dy) + error
        if tx >= 0 and ty >= 0:
            yield angle, step / 2, tx, ty


def rigid_float_shape_bound(shape, *, alignment_degrees=0.0):
    """Enclose every seated slot registration without treating slots as bores."""
    alignment = math.radians(alignment_degrees)
    aligned = shape.copy()
    aligned.rotate(V(), V(0, 0, 1), -alignment_degrees)
    bounds = aligned.BoundBox
    points = [
        (x, y) for x in (bounds.XMin, bounds.XMax) for y in (bounds.YMin, bounds.YMax)
    ]
    radius = max(math.hypot(x, y) for x, y in points)
    xs, ys = [], []
    for angle, half_step, tx, ty in registration_cells():
        padding = radius * half_step + 1e-8
        # A world-axis translation rectangle rotated into the chosen frame.
        ex = abs(math.cos(alignment)) * tx + abs(math.sin(alignment)) * ty
        ey = abs(math.sin(alignment)) * tx + abs(math.cos(alignment)) * ty
        c, s = math.cos(angle), math.sin(angle)
        for x, y in points:
            px, py = x * c - y * s, x * s + y * c
            xs.extend((px - ex - padding, px + ex + padding))
            ys.extend((py - ey - padding, py + ey + padding))
    envelope = box(
        max(xs) - min(xs),
        max(ys) - min(ys),
        bounds.ZLength,
        (min(xs), min(ys), bounds.ZMin),
    )
    envelope.rotate(V(), V(0, 0, 1), alignment_degrees)
    return envelope


def foot_float_shape_bound(index):
    """Intersect two complete bounds to preserve the inward foot relief."""
    foot = foot_shape(index)
    return (
        rigid_float_shape_bound(foot)
        .common(rigid_float_shape_bound(foot, alignment_degrees=45))
        .removeSplitter()
    )


def rigid_float_component_bounds():
    rows = []
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        rows.append(
            (
                f"load_leg_{index}",
                union(
                    [
                        rigid_float_shape_bound(
                            _radial(_fixed_leg_shape(radius), x, y)
                        ),
                        foot_float_shape_bound(index),
                    ]
                ),
            )
        )
        rows.append(
            (
                f"top_beam_half_{index}",
                rigid_float_shape_bound(_radial(_top_beam_half(radius), x, y)),
            )
        )
    return rows


def clamp_hardware_float_bounds():
    """Contain loose radial fastener placement plus every seated slot pose."""
    rows = []
    bottom = -TOWER_HEIGHT - DECK_THICKNESS
    # Hardware may move inside the foot bore as well as with the platform.
    local_gap = (
        CLAMP_HOLE_DIAMETER + DIMENSION_ALLOWANCE - MINIMUM_RECEIVED_BOLT_DIAMETER
    ) / 2
    for index, (x, y) in enumerate(CLAMP_CENTRES):
        bolt = union(
            [
                Part.makeCylinder(
                    purchased_hardware.SCREW_HEAD_DIAMETER / 2 + local_gap,
                    purchased_hardware.SCREW_HEAD_HEIGHT,
                    V(x, y, bottom - purchased_hardware.SCREW_HEAD_HEIGHT),
                ),
                Part.makeCylinder(
                    purchased_hardware.THREAD_DIAMETER / 2 + local_gap,
                    CLAMP_SCREW_LENGTH,
                    V(x, y, bottom),
                ),
            ]
        )
        nut = Part.makeCylinder(
            purchased_hardware.HEX_NUT_AF / math.sqrt(3) + local_gap,
            purchased_hardware.HEX_NUT_HEIGHT,
            V(x, y, -TOWER_HEIGHT + FOOT_THICKNESS),
        )
        rows.extend(
            (
                (f"Bolt{index}", rigid_float_shape_bound(bolt)),
                (f"Nut{index}", rigid_float_shape_bound(nut)),
            )
        )
    return rows
