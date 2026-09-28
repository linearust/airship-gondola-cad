"""Compact two-bolt optical pedestal on one ordinary carrier slot.

The two holes in the removable foot align with opposite ends of one shared
10 mm M2 slot. No separate host holes, tower, locator, or printed fastener.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, box, set_property
from gondola.contracts import fasteners
from gondola.contracts.hardware import HEX_NUT_SOURCE, STACK_SCREW_SOURCE

from . import purchased_hardware, stack_interface

V = App.Vector
HOST_SUPPORT_Z = stack_interface.HOST_SUPPORT_Z
DECK_THICKNESS = stack_interface.DECK_THICKNESS
HOST_ORIGIN_XY = (27.0, 18.0)
FOOT_SIZE_MM = (8.0, 16.0)
FOOT_CENTRE_X_MM = -1.0
FOOT_THICKNESS = 2.0
CLAMP_CENTRES = ((0.0, -5.0), (0.0, 5.0))
CLAMP_HOLE_DIAMETER = 2.6
CLAMP_SCREW_LENGTH = 8.0
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
SUPPORTED_HOSTS = {
    "BatteryEquipmentModule": "BatteryMount",
    "ElectronicsEquipmentModule": "ElectronicsMount",
}


def host_placement():
    return App.Placement(V(*HOST_ORIGIN_XY, HOST_SUPPORT_Z), App.Rotation())


def foot_outline_shape(*, bottom=0.0, thickness=FOOT_THICKNESS):
    return box(
        *FOOT_SIZE_MM,
        thickness,
        (FOOT_CENTRE_X_MM - FOOT_SIZE_MM[0] / 2, -FOOT_SIZE_MM[1] / 2, bottom),
    )


def foot_shape(*, bottom=0.0, thickness=FOOT_THICKNESS):
    shape = foot_outline_shape(bottom=bottom, thickness=thickness)
    for x, y in CLAMP_CENTRES:
        shape = shape.cut(
            Part.makeCylinder(
                CLAMP_HOLE_DIAMETER / 2, thickness + 2, V(x, y, bottom - 1)
            )
        )
    return shape.removeSplitter()


def interface_contract():
    return {
        "mechanism": "One compact rectangular pedestal foot on one shared M2 carrier slot",
        "industry_standard_claimed": False,
        "host_origin_xy_mm": HOST_ORIGIN_XY,
        "host_support_z_mm": HOST_SUPPORT_Z,
        "foot_size_mm": (*FOOT_SIZE_MM, FOOT_THICKNESS),
        "foot_centre_x_mm": FOOT_CENTRE_X_MM,
        "foot_bolt_centres_xy_mm": CLAMP_CENTRES,
        "host_bolt_centres_xy_mm": [
            (x + HOST_ORIGIN_XY[0], y + HOST_ORIGIN_XY[1]) for x, y in CLAMP_CENTRES
        ],
        "host_interface": "Opposite endpoints of the common carrier's x=27 mm, y=13 through 23 mm M2 slot. No optical-only hole is added to any carrier.",
        "supported_hosts": SUPPORTED_HOSTS,
        "configuration_limits": "Battery and FC carriers accept the same print. Use the battery host with a directly attached MG-F10-A helix, or with an optional accessory power platform that blocks the FC-host field. Remote antenna routing is unplaced and must be checked separately. A common mounting slot does not establish optical visibility for every populated combination.",
        "clearance_hole_diameter_mm": CLAMP_HOLE_DIAMETER,
        "screw_length_mm": CLAMP_SCREW_LENGTH,
        "hardware": "Two existing-kit M2x8 button-head screws from below and ordinary M2 hex nuts above. No washers or additional printed retainers.",
        "nominal_grip_mm": DECK_THICKNESS + FOOT_THICKNESS,
        "nominal_bolt_tip_projection_mm": CLAMP_SCREW_LENGTH
        - DECK_THICKNESS
        - FOOT_THICKNESS
        - fasteners.HEX_NUT_HEIGHT,
        "registration": {
            "printed_hole_and_slot_width_allowance_mm": DIMENSION_ALLOWANCE,
            "minimum_received_screw_diameter_mm": MINIMUM_RECEIVED_BOLT_DIAMETER,
            "relative_hole_axis_error_mm": MAX_REGISTRATION_ERROR,
            "nominal_foot_and_slot_endpoint_pitch_mm": 2 * REGISTRATION_HALF_PITCH,
            "conservative_xy_translation_mm": (MAX_REGISTRATION_X, MAX_REGISTRATION_Y),
            "maximum_yaw_bound_deg": math.degrees(MAX_REGISTRATION_YAW_RAD),
            "scope": "The common slot is only 10 mm long, matching the foot bolt pitch. Both endpoint fasteners bound travel and yaw; the listed rectangle intentionally encloses coupled clearance registration. These are assembly allowances for the illustrated near-zero facing and nominal10mm endpoint pitches, not an operating adjustment or a qualified pointing tolerance. Received hole-axis and slot-length errors require measurement; the diameter/width allowance does not certify arbitrary pitch errors.",
        },
        "assembly": "Seat the flat foot directly on the carrier, align its long edge with carrier Y and its upright/pivot toward carrier +X exactly as drawn, then hand-snug both screws while holding the exposed nuts. A 180 degree flipped installation is outside the checked registration branch. Reject rocking, overhang that prevents adequate seating, pull-through or cable-induced slip. Align the sensor downward using the single pitch clamp after positioning the rail on the balloon centreline; roll trim is not provided.",
        "service": "Disconnect the sensor, remove and bench-support the carrier, hold both nuts and withdraw the two screws downward; slide the freed nuts and complete pedestal outboard along carrier +X by 20 mm, then lift 40 mm along carrier +Z. The balloon and installed cable are not modeled. Remove the optical pedestal before lifting the host device.",
        "qualification": "Nominal fit and clearance only. Actual print flatness, slot/head bearing, hand-clamp preload, PA12 creep, adhesive retention and optical pointing remain unqualified.",
    }


def annotate_interface(obj):
    set_property(
        obj,
        "OpticalInterfaceContract",
        json.dumps(interface_contract(), sort_keys=True),
    )
    set_property(obj, "OpticalFitVerified", False, "App::PropertyBool")


def attach_to_host(group, host):
    if host.Name not in SUPPORTED_HOSTS or host.Document != group.Document:
        raise ValueError(
            "Optical pedestal requires a supported carrier in the same document"
        )
    old = group.getParentGeoFeatureGroup()
    if old is not None and old != host:
        old.removeObject(group)
    host.addObject(group)
    group.Placement = host_placement()
    set_property(group, "StackHostName", host.Name)
    annotate_interface(group)
    group.Document.recompute()


def build_hardware(doc, group):
    objects = []
    for index, (x, y) in enumerate(CLAMP_CENTRES):
        for kind, shape, z, sku, source in (
            (
                "Bolt",
                purchased_hardware.screw_shape(CLAMP_SCREW_LENGTH),
                -DECK_THICKNESS,
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
            obj = purchased_hardware.add_hardware(
                doc,
                group,
                f"OpticalFoot{kind}{index}",
                f"BUY | optical pedestal foot {index + 1} {kind.lower()}",
                shape,
                sku,
                "M2x8 screw from below and M2 hex nut above two directly seated 2 mm prints. Nominal 4 mm grip and 2.4 mm projection; verify full engagement, actual kit head bearing on the common slot and creep. No washer or printed thread.",
                source,
                fasteners.KIT_MATERIAL,
            )
            set_property(obj, "OpticalFootEnd", index, "App::PropertyInteger")
            objects.append(obj)
    return objects


def is_removable_head_part(obj, group):
    return belongs_to_group(obj, group)


def rigid_float_shape_bound(shape):
    """Enclose every endpoint-slot registration, including continuous yaw cells."""
    bounds = shape.BoundBox
    points = [
        (x, y) for x in (bounds.XMin, bounds.XMax) for y in (bounds.YMin, bounds.YMax)
    ]
    maximum_radius = max(math.hypot(x, y) for x, y in points)
    count = 64
    step = 2 * MAX_REGISTRATION_YAW_RAD / count
    padding = maximum_radius * step / 2 + 1e-8
    xs, ys = [], []
    for index in range(count):
        theta = -MAX_REGISTRATION_YAW_RAD + (index + 0.5) * step
        c, s = math.cos(theta), math.sin(theta)
        for x, y in points:
            px, py = x * c - y * s, x * s + y * c
            xs.extend(
                (px - MAX_REGISTRATION_X - padding, px + MAX_REGISTRATION_X + padding)
            )
            ys.extend(
                (py - MAX_REGISTRATION_Y - padding, py + MAX_REGISTRATION_Y + padding)
            )
    return box(
        max(xs) - min(xs),
        max(ys) - min(ys),
        bounds.ZLength,
        (min(xs), min(ys), bounds.ZMin),
    )


def pivot_registration_radius(pivot_xy):
    return math.hypot(MAX_REGISTRATION_X, MAX_REGISTRATION_Y) + 2 * math.hypot(
        *pivot_xy
    ) * math.sin(MAX_REGISTRATION_YAW_RAD / 2)


def clamp_tool_reservations():
    rows = []
    for index, (x, y) in enumerate(CLAMP_CENTRES):
        rows.extend(
            (
                (
                    f"key_{index}",
                    Part.makeCylinder(3, 20, V(x, y, -DECK_THICKNESS - 22)),
                ),
                (f"nut_{index}", box(8, 5, 4, (x - 8, y - 2.5, FOOT_THICKNESS))),
            )
        )
    return rows


def manufacturing_wall_probes():
    from . import optical_mount

    return [
        (
            "optical_foot_thickness",
            "OpticalMountBase",
            (0, -1, -0.01),
            (0, -1, FOOT_THICKNESS + 0.01),
            FOOT_THICKNESS,
        ),
        (
            "optical_upright_thickness",
            "OpticalMountBase",
            (1, -0.01, 10),
            (1, 2.01, 10),
            2.0,
        ),
        (
            "optical_fixed_pivot_ear",
            "OpticalMountBase",
            (
                optical_mount.PIVOT_CENTRE[0],
                optical_mount.PIVOT_CENTRE[1] - optical_mount.EAR_THICKNESS - 0.01,
                optical_mount.PIVOT_CENTRE[2] + 2.5,
            ),
            (
                optical_mount.PIVOT_CENTRE[0],
                optical_mount.PIVOT_CENTRE[1] + 0.01,
                optical_mount.PIVOT_CENTRE[2] + 2.5,
            ),
            optical_mount.EAR_THICKNESS,
        ),
    ]


def base_service_proxies():
    """Three simple solids enclose the base without filling its open surroundings."""
    from . import optical_mount

    x, y, z = optical_mount.PIVOT_CENTRE
    return [
        foot_outline_shape(),
        box(
            4,
            optical_mount.EAR_THICKNESS,
            z - FOOT_THICKNESS,
            (x - 3, y - optical_mount.EAR_THICKNESS, FOOT_THICKNESS),
        ),
        box(
            2 * optical_mount.EAR_RADIUS,
            optical_mount.EAR_THICKNESS,
            2 * optical_mount.EAR_RADIUS,
            (
                x - optical_mount.EAR_RADIUS,
                y - optical_mount.EAR_THICKNESS,
                z - optical_mount.EAR_RADIUS,
            ),
        ),
    ]


def rigid_float_component_bounds():
    return [
        (name, rigid_float_shape_bound(shape))
        for name, shape in zip(
            ("foot", "upright", "fixed_pitch_ear"), base_service_proxies()
        )
    ]


def permitted_hosts(*, direct_navigation_antenna=False, navigation_key=None):
    """Declared installation choices; collision evidence still must pass."""
    if direct_navigation_antenna and navigation_key == "MGF10A":
        return ("BatteryEquipmentModule",)
    return tuple(SUPPORTED_HOSTS)
