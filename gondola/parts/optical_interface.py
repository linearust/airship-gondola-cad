"""Compact optical foot on the middle slot of an existing equipment carrier."""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import box, set_property
from gondola.contracts import fasteners
from gondola.contracts.hardware import HEX_NUT_SOURCE, STACK_SCREW_SOURCE

from . import mounting_plate, purchased_hardware

V = App.Vector
HOST_SUPPORT_Z = mounting_plate.CARRIER_SUPPORT_Z
HOST_OFFSET_X = 27.0
FOOT_SIZE_MM = (8.0, 16.0)
FOOT_THICKNESS = 2.0
CLAMP_CENTRES = ((0.0, -5.0), (0.0, 5.0))
CLAMP_HOLE_DIAMETER = 2.6
CLAMP_SCREW_LENGTH = 8.0
DEFAULT_HOST = "BatteryEquipmentModule"
DEFAULT_SIDE = "PositiveX"
SUPPORTED_HOSTS = {
    "BatteryEquipmentModule": "BatteryMount",
    "ElectronicsEquipmentModule": "ElectronicsMount",
    "AccessoryEquipmentModule": "AccessoryMount",
}
SIDES = ("PositiveX", "NegativeX")
# Deliberately conservative assembly registration, not permissible operating play.
DIMENSION_ALLOWANCE = 0.3
MINIMUM_RECEIVED_BOLT_DIAMETER = 1.8
MAX_REGISTRATION_ERROR = (
    CLAMP_HOLE_DIAMETER + DIMENSION_ALLOWANCE - MINIMUM_RECEIVED_BOLT_DIAMETER
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
    shape = box(*FOOT_SIZE_MM, FOOT_THICKNESS, (-4, -8, 0))
    for x, y in CLAMP_CENTRES:
        shape = shape.cut(
            Part.makeCylinder(CLAMP_HOLE_DIAMETER / 2, FOOT_THICKNESS + 2, V(x, y, -1))
        )
    return shape.removeSplitter()


def interface_contract():
    return {
        "mechanism": "Two-bolt rectangular foot on one existing carrier middle-side M2 slot",
        "industry_standard_claimed": False,
        "supported_carriers": SUPPORTED_HOSTS,
        "default_host": DEFAULT_HOST,
        "default_side": DEFAULT_SIDE,
        "host_offset_x_mm": HOST_OFFSET_X,
        "host_support_z_mm": HOST_SUPPORT_Z,
        "foot_size_mm": (*FOOT_SIZE_MM, FOOT_THICKNESS),
        "foot_bolt_centres_xy_mm": CLAMP_CENTRES,
        "clearance_hole_diameter_mm": CLAMP_HOLE_DIAMETER,
        "host_interface": "Existing x=+/-27 mm middle side slot; screw centres y=-5/+5 mm. Same foot on either X edge, rotated 180 degrees on NegativeX. No optical-specific carrier holes or additional carrier.",
        "hardware": "Two M2x8 button-head screws from below the plate, ordinary M2 nuts above the foot; one further identical pair locks the pitch ears. No washers.",
        "minimum_received_flat_head_bearing_diameter_mm": 3.5,
        "concentric_head_land_across_maximum_slot_width_mm": (
            3.5 - CLAMP_HOLE_DIAMETER - DIMENSION_ALLOWANCE
        )
        / 2,
        "bearing_scope": "Heads bridge the carrier slot on two transverse lands. Inspect actual flat bearing diameter >=3.5 mm and slot width <=2.9 mm; centred residual land is only 0.3 mm per side. No washer is modeled. Eccentric seating and PA12 clamp pressure/creep remain unqualified.",
        "nominal_grip_mm": mounting_plate.THICKNESS_MM + FOOT_THICKNESS,
        "nominal_bolt_tip_projection_mm": CLAMP_SCREW_LENGTH
        - mounting_plate.THICKNESS_MM
        - FOOT_THICKNESS
        - fasteners.HEX_NUT_HEIGHT,
        "registration": {
            "printed_hole_and_slot_width_allowance_mm": DIMENSION_ALLOWANCE,
            "minimum_received_screw_diameter_mm": MINIMUM_RECEIVED_BOLT_DIAMETER,
            "conservative_xy_translation_mm": (MAX_REGISTRATION_X, MAX_REGISTRATION_Y),
            "maximum_yaw_bound_deg": math.degrees(MAX_REGISTRATION_YAW_RAD),
            "scope": "Assembly allowance around aligned 10 mm endpoint pitches; hand-align and lock both screws. Not an operating looseness or pointing specification. Received slot length and hole pitch require measurement.",
        },
        "relocation": "Move the same foot to a free middle side slot on an existing carrier and recheck populated device, wiring and optical fields. Carrier and side compatibility alone do not establish a clear view or simultaneous power-platform fit.",
        "service": "Disconnect the sensor and bench-support the carrier off the rail. Remove both exposed nuts and withdraw screws downward, then lift the optical mount. Remove obstructing equipment first if the selected populated host blocks access. No powered transfer or connected-cable service is modeled.",
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
    for index, (x, y) in enumerate(CLAMP_CENTRES):
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
                FOOT_THICKNESS,
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
                    "M2x8 screw through carrier and 2 mm optical foot, ordinary M2 nut. Bench assembly; verify actual engagement and full slot bearing. No washer.",
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
        ("OpticalFoot", foot_shape()),
        ("OpticalPost", mount.upright_shape()),
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
