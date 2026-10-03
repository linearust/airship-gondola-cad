"""Two detachable M2 clamps on existing slots of the common instrument plate."""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import box, set_property
from gondola.contracts import fasteners
from gondola.contracts.hardware import HEX_NUT_SOURCE, STACK_SCREW_SOURCE
from gondola.contracts.optical_attachment import DEFAULT_HOST, FOOT_ORIGIN_IN_STAGE

from . import mounting_plate, purchased_hardware, slot_bearing

V = App.Vector
HOST_SUPPORT_Z = mounting_plate.CARRIER_SUPPORT_Z
FOOT_SIZE_MM = (54.0, 8.0)
FOOT_THICKNESS = 2.0
NUT_RECESS_DEPTH = 0.5
NUT_RECESS_AF = 4.25
FOOT_NUT_SEAT_Z = 1.5
CLAMP_CENTRES = {1: (-19.0, 0.0), 2: (19.0, 0.0)}
HOST_SLOT_WIDTH = 2.6
CLAMP_HOLE_DIAMETER = 2.2
CLAMP_SCREW_LENGTH = 8.0
DIMENSION_ALLOWANCE = 0.3
MINIMUM_RECEIVED_BOLT_DIAMETER = 1.8
# Each screw can move .55 mm across its maximum slot and .35 mm in its
# maximum foot bore. At 38 mm separation yaw is bounded by asin(1.8/38).
# Round outward to include the small second-order X displacement as well.
MAX_REGISTRATION_X = 1.0
MAX_REGISTRATION_Y = 1.0
MAX_REGISTRATION_YAW_RAD = math.radians(3.0)


def placement():
    return App.Placement(V(*FOOT_ORIGIN_IN_STAGE), App.Rotation())


def foot_shape():
    width, length = FOOT_SIZE_MM
    shape = box(width, length, FOOT_THICKNESS, (-width / 2, -length / 2, 0))
    # Preserve the complete FC underbody rectangle; the rear 3 mm strip
    # joins both foot pads without entering that reserved volume.
    shape = shape.cut(box(12, 5, FOOT_THICKNESS + 2, (-6, -4, -1)))
    for x, y in CLAMP_CENTRES.values():
        shape = shape.cut(Part.makeCylinder(CLAMP_HOLE_DIAMETER / 2, 4, V(x, y, -1)))
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
        "scope": "Ordinary M2 hex nuts only. Shallow open pockets restrain turning without raised guides; they do not retain loose nuts axially or qualify tightening torque. Check actual nut chamfers and flank engagement, finish for free insertion and full floor seating, and reject a freely rotating nut or damaged floor. The finished range is an acceptance target, not guaranteed PA12 process tolerance.",
    }


def interface_contract():
    return {
        "attachment_mode": "instrument",
        "mechanism": "One rigid removable optical bracket with two spaced M2 clamps on the shared instrument plate",
        "industry_standard_claimed": False,
        "default_host": DEFAULT_HOST,
        "support_part": "ElectronicsMount",
        "foot_origin_in_stage_mm": FOOT_ORIGIN_IN_STAGE,
        "foot_size_mm": (*FOOT_SIZE_MM, FOOT_THICKNESS),
        "foot_front_notch_mm": {"width": 12.0, "depth": 5.0, "rear_bridge_width": 3.0},
        "foot_bolt_centres_xy_mm": tuple(CLAMP_CENTRES.values()),
        "host_bolt_centres_xy_mm": [(-19.0, 27.0), (19.0, 27.0)],
        "clearance_hole_diameter_mm": CLAMP_HOLE_DIAMETER,
        "host_interface": "Opposed existing side-slot endpoints at plate X=-19/+19, Y=27 mm. No new plate holes, independent optical hinge, rail shoe or locating tongue.",
        "hardware": "Two M2x8 button-head screws from below the plate and two ordinary M2 nuts in shallow foot recesses. No washers.",
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
            "maximum_yaw_bound_deg": 3.0,
            "scope": "Conservative assembly collision allowance for two clamps 38 mm apart with full planar seating. Includes positions that fail head-bearing acceptance; centre each screw within 0.1 mm across its slot and verify both lands after tightening. This is not operating slack, automatic alignment or an all-process tolerance guarantee. Inspect feature position and warpage separately.",
        },
        "service": "Disconnect the sensor and support the common platform. Lift each foot nut 4.7 mm, move it 8 mm toward positive local Y, 10 mm outward in X, then lift clear. Withdraw both screws 8.2 mm below the plate, slide the complete bracket 10 mm toward positive local Y to clear the FC corner, then lift it 40 mm. Remove this bracket before FC removal; the FC and optical sensor share one manually adjusted platform.",
        "qualification": "Nominal geometry only. Verify printed fit, full head/nut bearing, actual engagement, clamping retention, PA12 creep, adhesive retention and pointing. No loaded stiffness or torque claim.",
    }


def attachment_description(optical):
    if str(getattr(optical, "OpticalAttachmentMode", "")) != "instrument":
        raise ValueError("Optical bracket requires the common instrument attachment")
    host = optical.getParentGeoFeatureGroup()
    if host is None or host.Name != DEFAULT_HOST:
        raise ValueError("Optical bracket is not attached to InstrumentPitchStage")
    return {
        "mode": "instrument",
        "host": host.Name,
        "support_part": "ElectronicsMount",
        "foot_origin_in_stage_mm": FOOT_ORIGIN_IN_STAGE,
    }


def annotate_interface(obj):
    set_property(
        obj,
        "OpticalInterfaceContract",
        json.dumps(interface_contract(), sort_keys=True),
    )
    set_property(obj, "OpticalFitVerified", False, "App::PropertyBool")


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
            shape.translate(V(x, y, z))
            objects.append(
                purchased_hardware.add_hardware(
                    doc,
                    group,
                    f"OpticalFoot{kind}{index}",
                    f"BUY | optical bracket foot {index} {kind.lower()}",
                    shape,
                    sku,
                    "M2x8 through the existing 2 mm plate and 1.5 mm foot floor beneath a 0.5 mm shallow ordinary M2 nut recess. Two spaced clamps locate the rigid bracket. Verify free insertion, complete seating, received hardware engagement and both slot bearing lands. No washer.",
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
    rows = []
    for index, (x, y) in CLAMP_CENTRES.items():
        rows.extend(
            [
                (
                    f"optical_foot_{index}_nut_floor",
                    "OpticalSensorTray",
                    (x + 1.5, y, -0.01),
                    (x + 1.5, y, 2.01),
                    1.5,
                ),
                (
                    f"optical_foot_{index}_pocket_side",
                    "OpticalSensorTray",
                    (x, 2.09, 1.75),
                    (x, 4.01, 1.75),
                    1.875,
                ),
            ]
        )
    rows.extend(
        [
            (
                "optical_foot_rear_bridge",
                "OpticalSensorTray",
                (0, 0.99, 1),
                (0, 4.01, 1),
                3.0,
            ),
            (
                "optical_left_upright",
                "OpticalSensorTray",
                (-25.01, 0, 10),
                (-21.99, 0, 10),
                3.0,
            ),
            (
                "optical_right_upright",
                "OpticalSensorTray",
                (21.99, 0, 10),
                (25.01, 0, 10),
                3.0,
            ),
            ("optical_roof", "OpticalSensorTray", (15, 0, 18.49), (15, 0, 20.51), 2.0),
            (
                "optical_adhesive_pad",
                "OpticalSensorTray",
                (0, 4, 18.49),
                (0, 4, 20.51),
                2.0,
            ),
        ]
    )
    return rows


def base_component_proxies():
    # Complete literal stock enclosures, including R0.5 concave root material.
    return [
        ("OpticalFootLeft", box(21, 8, 2.5, (-27, -4, 0))),
        ("OpticalFootRight", box(21, 8, 2.5, (6, -4, 0))),
        ("OpticalFootRearBridge", box(12, 3, 2, (-6, 1, 0))),
        ("OpticalLeftSupport", box(4, 8, 17, (-25.5, -4, 2))),
        ("OpticalRightSupport", box(4, 8, 17, (21.5, -4, 2))),
        ("OpticalCrossbar", box(50, 4, 2.5, (-25, -2, 18))),
        ("OpticalAdhesivePad", box(18, 12, 2, (-9, -6, 18.5))),
    ]
