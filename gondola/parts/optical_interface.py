"""Compact optical foot on the middle slot of an existing equipment carrier."""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import box, set_property, union
from gondola.contracts import fasteners
from gondola.contracts.hardware import HEX_NUT_SOURCE, STACK_SCREW_SOURCE

from . import mounting_plate, purchased_hardware, slot_bearing

V = App.Vector
HOST_SUPPORT_Z = mounting_plate.CARRIER_SUPPORT_Z
HOST_OFFSET_X = 27.0
FOOT_SIZE_MM = (8.0, 18.0)
FOOT_THICKNESS = 2.0
NUT_RECESS_DEPTH = 0.5
NUT_RECESS_AF = 4.25
FOOT_NUT_SEAT_Z = FOOT_THICKNESS - NUT_RECESS_DEPTH
# Retain the positive-Y joint's existing object identity; the negative joint
# is replaced by a broad rigid locator, not a spring or interference fit.
CLAMP_CENTRES = {1: (0.0, 5.0)}
HOST_SLOT_WIDTH = 2.6
CLAMP_HOLE_DIAMETER = 2.2
CLAMP_SCREW_LENGTH = 8.0
LOCATOR_WIDTH = 2.4
LOCATOR_END_CENTRES_Y = (-5.0, 1.0)
LOCATOR_DEPTH = 1.2
DEFAULT_HOST = "BatteryEquipmentModule"
DEFAULT_SIDE = "PositiveX"
SUPPORTED_HOSTS = {
    "BatteryEquipmentModule": "BatteryMount",
    "ElectronicsEquipmentModule": "ElectronicsMount",
    "AccessoryEquipmentModule": "AccessoryMount",
}
SIDES = ("PositiveX", "NegativeX")
# Retain the prior conservative assembly envelope; it is not operating play.
# With +/-0.3 mm total-size variation, a 2.1 mm-wide locator with a 5.7 mm
# straight centreline inside a 2.9 mm slot limits yaw to asin(0.8 / 5.7),
# below this 12.71-degree bound. The positive-end screw bounds longitudinal
# translation. Full foot seating and a tightened clamp are still required.
DIMENSION_ALLOWANCE = 0.3
MINIMUM_RECEIVED_BOLT_DIAMETER = 1.8
MAX_REGISTRATION_ERROR = (
    HOST_SLOT_WIDTH + DIMENSION_ALLOWANCE - MINIMUM_RECEIVED_BOLT_DIAMETER
)
REGISTRATION_HALF_PITCH = 5.0
MAX_REGISTRATION_YAW_RAD = math.asin(MAX_REGISTRATION_ERROR / REGISTRATION_HALF_PITCH)
MAX_REGISTRATION_X = MAX_REGISTRATION_ERROR
MAX_REGISTRATION_Y = MAX_REGISTRATION_ERROR + REGISTRATION_HALF_PITCH * (
    1 - math.cos(MAX_REGISTRATION_YAW_RAD)
)


def placement(side=DEFAULT_SIDE):
    if side not in SIDES:
        raise ValueError("Unknown optical carrier side: " + str(side))
    sign = 1 if side == "PositiveX" else -1
    return App.Placement(
        V(sign * HOST_OFFSET_X, 0, HOST_SUPPORT_Z),
        App.Rotation(V(0, 0, 1), 0 if sign == 1 else 180),
    )


def foot_shape():
    width, length = FOOT_SIZE_MM
    shape = union(
        [
            box(width, length, FOOT_THICKNESS, (-width / 2, -length / 2, 0)),
            locator_shape(),
        ]
    )
    for x, y in CLAMP_CENTRES.values():
        shape = shape.cut(
            Part.makeCylinder(CLAMP_HOLE_DIAMETER / 2, FOOT_THICKNESS + 2, V(x, y, -1))
        )
        recess = purchased_hardware.hex_prism(NUT_RECESS_AF, NUT_RECESS_DEPTH + 0.1)
        recess.translate(V(x, y, FOOT_NUT_SEAT_Z))
        shape = shape.cut(recess)
    return shape.removeSplitter()


def nut_recess_contract():
    return {
        "depth_mm": NUT_RECESS_DEPTH,
        "across_flats_mm": NUT_RECESS_AF,
        "remaining_floor_mm": FOOT_NUT_SEAT_Z,
        "finished_flat_gap_acceptance_mm": [4.15, 4.3],
        "scope": "Ordinary M2 hex nuts only. Shallow open pockets restrain turning without raised guides; they do not retain a loose nut axially or qualify tightening torque. Check received nut chamfers and flank engagement, finish for free insertion and full floor seating, and reject a freely rotating nut or damaged floor. The finished range is an acceptance target, not guaranteed PA12 process tolerance.",
    }


def locator_shape():
    """Shallow capsule enters only the slot; it never clips beneath the plate."""
    radius = LOCATOR_WIDTH / 2
    low, high = LOCATOR_END_CENTRES_Y
    return union(
        [
            box(
                LOCATOR_WIDTH, high - low, LOCATOR_DEPTH, (-radius, low, -LOCATOR_DEPTH)
            ),
            *(
                Part.makeCylinder(radius, LOCATOR_DEPTH, V(0, y, -LOCATOR_DEPTH))
                for y in (low, high)
            ),
        ]
    ).removeSplitter()


def interface_contract():
    return {
        "mechanism": "One M2 clamp and an integral rigid locating tongue in an existing carrier middle-side slot",
        "industry_standard_claimed": False,
        "supported_carriers": SUPPORTED_HOSTS,
        "default_host": DEFAULT_HOST,
        "default_side": DEFAULT_SIDE,
        "host_offset_x_mm": HOST_OFFSET_X,
        "host_support_z_mm": HOST_SUPPORT_Z,
        "foot_size_mm": (*FOOT_SIZE_MM, FOOT_THICKNESS),
        "foot_bolt_centres_xy_mm": tuple(CLAMP_CENTRES.values()),
        "locator": {
            "width_mm": LOCATOR_WIDTH,
            "end_centres_y_mm": LOCATOR_END_CENTRES_Y,
            "depth_mm": LOCATOR_DEPTH,
            "nominal_slot_side_clearance_mm": (HOST_SLOT_WIDTH - LOCATOR_WIDTH) / 2,
            "nominal_recess_above_carrier_underside_mm": mounting_plate.THICKNESS_MM
            - LOCATOR_DEPTH,
            "dimensional_screen_recess_mm": mounting_plate.THICKNESS_MM
            - DIMENSION_ALLOWANCE
            - LOCATOR_DEPTH
            - DIMENSION_ALLOWANCE,
            "scope": "Rigid location only; no latch, interference or elastic preload. The 1.2 mm projection is a shallow locator, not an unsupported structural wall. The nominal side gap is 0.1 mm; +/-0.3 mm size variation can cause interference. Finish high spots for snug hand insertion without rocking; reprint an oversized slot or undersized tongue. The foot must sit flat on both support strips before tightening; never pull an interfering tongue into its slot with the screw. Verify the actual tongue remains above the carrier underside.",
        },
        "clearance_hole_diameter_mm": CLAMP_HOLE_DIAMETER,
        "host_interface": "Existing x=+/-27 mm middle side slot; one screw at local y=+5 mm and the locating tongue toward negative Y. Same foot on either X edge, rotated 180 degrees on NegativeX. No optical-specific carrier holes or additional carrier.",
        "hardware": "One M2x8 button-head screw from below the plate and ordinary M2 nut in a shallow foot recess; one further identical pair locks the pitch ears. No washers.",
        **slot_bearing.contract(
            HOST_SLOT_WIDTH + DIMENSION_ALLOWANCE, MINIMUM_RECEIVED_BOLT_DIAMETER
        ),
        "nut_recess": nut_recess_contract(),
        "nominal_grip_mm": mounting_plate.THICKNESS_MM + FOOT_NUT_SEAT_Z,
        "nominal_bolt_tip_projection_mm": CLAMP_SCREW_LENGTH
        - mounting_plate.THICKNESS_MM
        - FOOT_NUT_SEAT_Z
        - fasteners.HEX_NUT_HEIGHT,
        "registration": {
            "printed_hole_and_slot_width_allowance_mm": DIMENSION_ALLOWANCE,
            "minimum_received_screw_diameter_mm": MINIMUM_RECEIVED_BOLT_DIAMETER,
            "conservative_xy_translation_mm": (MAX_REGISTRATION_X, MAX_REGISTRATION_Y),
            "maximum_yaw_bound_deg": math.degrees(MAX_REGISTRATION_YAW_RAD),
            "scope": "Conservative collision allowance bounded by the tongue width/length and positive-end screw, assuming full planar seating. This includes positions that fail head-bearing acceptance; admissible assembly additionally requires screw centring within 0.1 mm across the slot and retained lands after tightening. Hand-align and lock the screw; this is not operating looseness, automatic alignment or a pointing specification. Width/length size screening does not include slot-end location, feature-position error or warpage. Inspect the actual features; these bounds are not an all-process tolerance guarantee.",
        },
        "relocation": "Move the same foot to a free middle side slot on an existing carrier and recheck populated device, wiring and optical fields. Carrier and side compatibility alone do not establish a clear view or simultaneous power-platform fit.",
        "service": "Disconnect the sensor and bench-support the carrier off the rail. Remove the exposed foot nut and withdraw its screw downward, then lift the mount vertically to clear the 1.2 mm tongue. Remove obstructing equipment first if the selected populated host blocks access. No powered transfer or connected-cable service is modeled.",
        "qualification": "Nominal geometry only. Check actual print fit, full head/nut bearing, preload, PA12 creep, adhesive retention and pointing. The manual pitch joint does not self-level.",
    }


def annotate_interface(obj):
    set_property(
        obj,
        "OpticalInterfaceContract",
        json.dumps(interface_contract(), sort_keys=True),
    )
    set_property(obj, "OpticalFitVerified", False, "App::PropertyBool")


def attach_to_host(group, host, side=DEFAULT_SIDE):
    if host.Name not in SUPPORTED_HOSTS or host.Document != group.Document:
        raise ValueError(
            "Optical mount requires a supported carrier in the same document"
        )
    pose = placement(side)
    old = group.getParentGeoFeatureGroup()
    if old is not None and old != host:
        old.removeObject(group)
    host.addObject(group)
    group.Placement = pose
    set_property(group, "CarrierHostName", host.Name)
    group.setEditorMode("CarrierHostName", 1)
    if "MountSide" not in group.PropertiesList:
        group.addProperty("App::PropertyEnumeration", "MountSide", "Carrier mounting")
        group.MountSide = list(SIDES)
    group.MountSide = side
    group.Placement.Rotation = App.Rotation(V(0, 0, 1), 1)
    group.setExpression(
        "Placement.Base.x",
        f"MountSide == 0 ? {HOST_OFFSET_X:g} mm : {-HOST_OFFSET_X:g} mm",
    )
    group.setExpression("Placement.Rotation.Angle", "MountSide == 0 ? 0 deg : 180 deg")
    annotate_interface(group)
    group.Document.recompute()


def build_hardware(doc, group):
    objects = []
    for index, (x, y) in CLAMP_CENTRES.items():
        for kind, shape, z, sku, source in (
            (
                "Bolt",
                purchased_hardware.screw_shape(CLAMP_SCREW_LENGTH),
                -mounting_plate.THICKNESS_MM,
                "M2X8_BUTTON_HEAD",
                STACK_SCREW_SOURCE,
            ),
            (
                "Nut",
                purchased_hardware.hex_nut_shape(),
                FOOT_NUT_SEAT_Z,
                "M2_HEX_NUT",
                HEX_NUT_SOURCE,
            ),
        ):
            shape = shape.copy()
            shape.translate(V(x, y, z))
            objects.append(
                purchased_hardware.add_hardware(
                    doc,
                    group,
                    f"OpticalFoot{kind}{index}",
                    f"BUY | optical carrier foot {index + 1} {kind.lower()}",
                    shape,
                    sku,
                    "One M2x8 screw through carrier and 1.5 mm foot floor under a 0.5 mm shallow ordinary M2 nut recess. Integral shallow tongue limits rotation before clamping. Bench assembly; verify free insertion, full flat seating, actual engagement and full slot bearing. No washer.",
                    source,
                    fasteners.KIT_MATERIAL,
                )
            )
    return objects


def registration_bound(shape):
    """Conservative XY/yaw enclosure of a shape in optical-module coordinates."""
    bounds = shape.BoundBox
    xs, ys = [], []
    limit = MAX_REGISTRATION_YAW_RAD
    for x in (bounds.XMin, bounds.XMax):
        for y in (bounds.YMin, bounds.YMax):
            angles = [-limit, limit]
            for critical in (math.atan2(-y, x), math.atan2(x, y)):
                angles.extend(
                    critical + n * math.pi
                    for n in range(-2, 3)
                    if -limit <= critical + n * math.pi <= limit
                )
            for angle in angles:
                xs.append(x * math.cos(angle) - y * math.sin(angle))
                ys.append(x * math.sin(angle) + y * math.cos(angle))
    return box(
        max(xs) - min(xs) + 2 * MAX_REGISTRATION_X,
        max(ys) - min(ys) + 2 * MAX_REGISTRATION_Y,
        bounds.ZLength,
        (min(xs) - MAX_REGISTRATION_X, min(ys) - MAX_REGISTRATION_Y, bounds.ZMin),
    )


def manufacturing_wall_probes():
    from . import optical_mount as mount

    x, y, z = mount.PIVOT_CENTRE
    return [
        (
            "optical_foot_nut_recess_floor",
            "OpticalMountBase",
            (1.5, 5.0, -0.01),
            (1.5, 5.0, FOOT_THICKNESS + 0.01),
            FOOT_NUT_SEAT_Z,
        ),
        (
            "optical_foot_nut_pocket_end_ligament",
            "OpticalMountBase",
            (0.0, 7.09, 1.75),
            (0.0, FOOT_SIZE_MM[1] / 2 + 0.01, 1.75),
            FOOT_SIZE_MM[1] / 2 - CLAMP_CENTRES[1][1] - NUT_RECESS_AF / 2,
        ),
        (
            "optical_locator_transverse_width",
            "OpticalMountBase",
            (-LOCATOR_WIDTH / 2 - 0.01, -3, -LOCATOR_DEPTH / 2),
            (LOCATOR_WIDTH / 2 + 0.01, -3, -LOCATOR_DEPTH / 2),
            LOCATOR_WIDTH,
        ),
        (
            "optical_locator_backed_by_foot",
            "OpticalMountBase",
            (0, -4, -LOCATOR_DEPTH - 0.01),
            (0, -4, FOOT_THICKNESS + 0.01),
            FOOT_THICKNESS + LOCATOR_DEPTH,
        ),
        (
            "optical_upright_thickness",
            "OpticalMountBase",
            (x, y - mount.EAR_THICKNESS - 0.01, 8),
            (x, y + 0.01, 8),
            mount.EAR_THICKNESS,
        ),
        (
            "optical_fixed_pivot_ear",
            "OpticalMountBase",
            (x, y - mount.EAR_THICKNESS - 0.01, z + 2.5),
            (x, y + 0.01, z + 2.5),
            mount.EAR_THICKNESS,
        ),
    ]


def base_component_proxies():
    from . import optical_mount as mount

    x, y, z = mount.PIVOT_CENTRE
    return [
        (
            "OpticalFoot",
            union(
                [
                    foot_shape(),
                    box(8, 0.5, 0.5, (-4, -2.5, 2)),
                    # The sloping toe's tangency also extends behind Y=2 and
                    # above Z=2.5; enclose the complete obtuse R0.5 transition.
                    box(8, 1, 1, (-4, 1.5, 2)),
                ]
            ),
        ),
        (
            "OpticalPost",
            union([mount.upright_shape(), box(8, 0.5, 1, (-4, 0, 6.5))]),
        ),
        (
            "OpticalEar",
            box(
                2 * mount.EAR_RADIUS,
                mount.EAR_THICKNESS,
                2 * mount.EAR_RADIUS,
                (x - mount.EAR_RADIUS, y - mount.EAR_THICKNESS, z - mount.EAR_RADIUS),
            ),
        ),
    ]
