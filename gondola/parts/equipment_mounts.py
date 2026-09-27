"""Compact role carriers with a common rail shoe and bought FC adapter axes.

Only low carriers live here. The selected optical host is fused with its portal
by stack_interface; removing that option restores these plain carrier shapes.
"""

import functools
import json
import math

import FreeCAD as App
import Part

from gondola.cad import box, create_printed_part, set_property, union
from gondola.contracts import equipment_interfaces as interfaces
from gondola.contracts import stack_adapter as adapter_specification

from . import rail, stock_adapter

V = App.Vector
DECK_THICKNESS = 2.0
SUPPORT_FACE_Z = 13.8
FC_SUPPORT_FACE_Z = stock_adapter.PLATE_TOP_Z
DECK_BOTTOM_Z = SUPPORT_FACE_Z - DECK_THICKNESS
MOUNT_HOLE_DIAMETER = 2.6
MOUNT_PAD_DIAMETER = 6.5
FC_CENTRE_XY = (0.0, 0.0)
FC_ROTATION_DEG = -45.0
FC_AXIS_OFFSET = interfaces.FC_HOLE_PITCH / math.sqrt(2)
FC_HOLE_CENTRES = adapter_specification.COMMON_HOLE_CENTRES
FC_SADDLE_BOTTOM_Z = stock_adapter.SADDLE_BOTTOM_Z
FC_SADDLE_THICKNESS = stock_adapter.SADDLE_THICKNESS_MM
FC_SADDLE_PAD_DIAMETER = stock_adapter.SADDLE_PAD_DIAMETER_MM
FC_SADDLE_PAD_CENTRES = stock_adapter.SADDLE_PAD_CENTRES
FC_SADDLE_FIX_CENTRES = stock_adapter.SADDLE_FIX_CENTRES
FC_SADDLE_AXIS_OFFSET = 16.0 / math.sqrt(2)
FC_SADDLE_ARM_WIDTH = FC_SADDLE_PAD_DIAMETER
NAVIGATION_CENTRE_XY = (0.0, 22.0)
PAS_HOLE_CENTRES = interfaces.PAS_HOLE_CENTRES
RADIO_CENTRE_XY = (0.0, -22.0)
GPS_ADHESIVE_SIZE = (18.0, 14.0)
RADIO_ADHESIVE_SIZE = (22.0, 14.0)
ACCESSORY_DECK_SIZE = (36.0, 66.0)
ACCESSORY_DECK_CENTRE_XY = (0.0, 0.0)
BATTERY_DECK_SIZE = (22.0, 68.0)
ELECTRONICS_DECK_SIZE = (
    2 * FC_SADDLE_AXIS_OFFSET + FC_SADDLE_PAD_DIAMETER,
    2 * FC_SADDLE_AXIS_OFFSET + FC_SADDLE_PAD_DIAMETER,
)
DECK_CORNER_RADIUS = 3.0
MOUNT_NAMES = {
    "battery": "BatteryMount",
    "electronics": "ElectronicsMount",
    "accessory": "AccessoryMount",
}
PRINT_SKUS = {
    "battery": "BatteryRailCarrier",
    "electronics": "FCRailSaddle",
    "accessory": "AccessoryRailCarrier",
}
BATTERY_ADHESIVE_REGIONS = (((0.0, 0.0), (14.0, 54.0)),)
# The single spare pattern avoids P-AS bores and both adhesive patches. Adding
# centred20/16mm holes would cut contact material or crowd the rail shoe.
STANDARD_PATTERNS = {"battery": (), "electronics": (), "accessory": ((25.5, 0.0),)}
STANDARD_PATTERN_DATUM = {
    "battery": (0.0, 0.0),
    "electronics": (0.0, 0.0),
    "accessory": (0.0, -5.0),
}
BATTERY_PLACEMENT_CONTRACT = {
    "centre_x_limit_mm": 1.0,
    "centre_y_limit_mm": 1.0,
    "maximum_size_mm": [66, 18, 17],
    "minimum_stack_tower_gap_mm": 1.5,
    "frame": "Battery carrier XY; pack long axis along Y, nominal1mm adhesive allowance",
    "qualification": "Placement allowance for the declared pack envelope and adhesive patch only. Slide the whole rail carrier for larger trim changes. Actual pack size, adhesive retention and clearance to an optional integral optical portal require validation.",
}
FC_WIRING_CLEARANCE = 8.0
FC_WIRING_CORRIDOR_WIDTH = 8.0
FC_WIRING_CORRIDOR_CENTRE_Y = 9.0
PAS_SERVICE_CLEARANCE = 4.0
ADHESIVE_ALLOWANCE = 1.0
PRINT_ROTATION = App.Rotation(V(1, 0, 0), 180)


def _check_kind(kind):
    if kind not in MOUNT_NAMES:
        raise ValueError("Unknown equipment mount kind: " + str(kind))


def fc_wiring_reserve_shape():
    """Eight-mm free-height planning corridor above the bought carbon top."""
    half_length = interfaces.FC_SIZE_MM[0] / math.sqrt(2)
    return box(
        half_length * 2,
        FC_WIRING_CORRIDOR_WIDTH,
        FC_WIRING_CLEARANCE,
        (
            -half_length,
            FC_WIRING_CORRIDOR_CENTRE_Y - FC_WIRING_CORRIDOR_WIDTH / 2,
            FC_SUPPORT_FACE_Z,
        ),
    )


def mount_hole_centres(kind):
    _check_kind(kind)
    if kind == "electronics":
        return FC_HOLE_CENTRES
    if kind == "accessory":
        cx, cy = NAVIGATION_CENTRE_XY
        return tuple((cx + x, cy + y) for x, y in PAS_HOLE_CENTRES)
    return ()


def standard_hole_rows(kind):
    _check_kind(kind)
    cx, cy = STANDARD_PATTERN_DATUM[kind]
    return [
        {
            "centre_xy_mm": (cx + x, cy + y),
            "diameter_mm": MOUNT_HOLE_DIAMETER,
            "fastener": "M2",
            "pad_diameter_mm": MOUNT_PAD_DIAMETER,
            "square_pitch_mm": pitch,
            "rotation_deg": rotation,
            "purpose": "alternative spare equipment; not simultaneous populated-device clearance",
        }
        for pitch, rotation in STANDARD_PATTERNS[kind]
        for x, y in adapter_specification.hole_centres(pitch, rotation)
    ]


def carrier_hole_rows(kind):
    _check_kind(kind)
    centres = (
        FC_SADDLE_FIX_CENTRES if kind == "electronics" else mount_hole_centres(kind)
    )
    pad = FC_SADDLE_PAD_DIAMETER if kind == "electronics" else MOUNT_PAD_DIAMETER
    return [
        {
            "centre_xy_mm": centre,
            "diameter_mm": MOUNT_HOLE_DIAMETER,
            "pad_diameter_mm": pad,
            "fastener": "M2",
            "purpose": "16mm carbon-to-saddle fixation"
            if kind == "electronics"
            else "P-AS mounting axis",
        }
        for centre in centres
    ] + standard_hole_rows(kind)


def support_face_z(kind):
    """FC rests above bought carbon; the other devices use their printed decks."""
    _check_kind(kind)
    return FC_SUPPORT_FACE_Z if kind == "electronics" else SUPPORT_FACE_Z


def _hole_shapes(rows, bottom, depth, border=0.0):
    return [
        Part.makeCylinder(
            row["diameter_mm"] / 2 + border, depth, V(*row["centre_xy_mm"], bottom)
        )
        for row in rows
    ]


def standard_hole_shapes(
    kind, bottom=DECK_BOTTOM_Z - 1, depth=DECK_THICKNESS + 2, *, border=0.0
):
    return _hole_shapes(standard_hole_rows(kind), bottom, depth, border)


def carrier_plate_bottom(kind):
    _check_kind(kind)
    return FC_SADDLE_BOTTOM_Z if kind == "electronics" else DECK_BOTTOM_Z


def carrier_plate_thickness(kind):
    _check_kind(kind)
    return FC_SADDLE_THICKNESS if kind == "electronics" else DECK_THICKNESS


def carrier_plate_shape(kind):
    """Carrier contact geometry only, before its integral shoe and optional portal."""
    _check_kind(kind)
    bottom, thickness = carrier_plate_bottom(kind), carrier_plate_thickness(kind)
    if kind == "electronics":
        radius = FC_SADDLE_AXIS_OFFSET
        width = FC_SADDLE_ARM_WIDTH
        shape = union(
            [
                box(2 * radius, width, thickness, (-radius, -width / 2, bottom)),
                box(width, 2 * radius, thickness, (-width / 2, -radius, bottom)),
                *[
                    Part.makeCylinder(
                        FC_SADDLE_PAD_DIAMETER / 2, thickness, V(x, y, bottom)
                    )
                    for x, y in FC_SADDLE_PAD_CENTRES
                ],
            ]
        )
    else:
        length, width = BATTERY_DECK_SIZE if kind == "battery" else ACCESSORY_DECK_SIZE
        shape = box(length, width, thickness, (-length / 2, -width / 2, bottom))
        edges = [
            edge for edge in shape.Edges if edge.BoundBox.ZLength > thickness - 0.01
        ]
        shape = shape.makeFillet(DECK_CORNER_RADIUS, edges)
    for hole in _hole_shapes(carrier_hole_rows(kind), bottom - 1, thickness + 2):
        shape = shape.cut(hole)
    return shape.removeSplitter()


@functools.lru_cache(None)
def mount_shape(kind):
    _check_kind(kind)
    pieces = [carrier_plate_shape(kind), rail.shoe_shape()]
    bottom = carrier_plate_bottom(kind)
    if bottom > rail.TOP_Z:
        length, width = (
            stock_adapter.SADDLE_STEM_SIZE_MM
            if kind == "electronics"
            else (rail.SHOE_LENGTH, rail.SHOE_WIDTH)
        )
        pieces.append(
            box(
                length,
                width,
                bottom - rail.TOP_Z + 0.2,
                (-length / 2, -width / 2, rail.TOP_Z - 0.1),
            )
        )
    shape = union(pieces)
    for hole in _hole_shapes(
        carrier_hole_rows(kind),
        rail.SHOE_BOTTOM - 1,
        support_face_z(kind) - rail.SHOE_BOTTOM + 2,
    ):
        shape = shape.cut(hole)
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Equipment carrier is not one valid solid: " + kind)
    return shape


def mount_contract(kind):
    _check_kind(kind)
    adhesive_pads = {
        "battery": [
            {
                "device": "battery",
                "centre_xy_mm": centre,
                "size_mm": size,
                "support_face": "top",
            }
            for centre, size in BATTERY_ADHESIVE_REGIONS
        ],
        "electronics": [],
        "accessory": [
            {
                "device": "LR24-F-Mini",
                "centre_xy_mm": RADIO_CENTRE_XY,
                "size_mm": RADIO_ADHESIVE_SIZE,
                "support_face": "top",
            },
            {
                "device": "MG-A01 / M10 Ultra or MG-F10-A",
                "centre_xy_mm": NAVIGATION_CENTRE_XY,
                "size_mm": GPS_ADHESIVE_SIZE,
                "support_face": "top",
            },
        ],
    }
    return {
        "kind": kind,
        "print_sku": PRINT_SKUS[kind],
        "low_carrier_only": True,
        "optical_option": "The selected battery or FC host may receive an integral optical portal as a different PrintSKU. This low carrier adds no separate tower feet, foot screws or precision locating features.",
        "plate_bottom_z_mm": carrier_plate_bottom(kind),
        "plate_thickness_mm": carrier_plate_thickness(kind),
        "support_face_z_mm": support_face_z(kind),
        "bought_fc_plate": stock_adapter.mounting_contract()
        if kind == "electronics"
        else None,
        "integral_common_rail_shoe": True,
        "mount_hole_centres_xy_mm": mount_hole_centres(kind),
        "device_hole_diameter_mm": {
            "electronics": interfaces.FC_HOLE_DIAMETER,
            "accessory": interfaces.PAS_HOLE_DIAMETER,
            "battery": None,
        }[kind],
        "carrier_hole_diameter_mm": MOUNT_HOLE_DIAMETER,
        "mount_pad_diameter_mm": FC_SADDLE_PAD_DIAMETER
        if kind == "electronics"
        else MOUNT_PAD_DIAMETER,
        "carrier_holes": carrier_hole_rows(kind),
        "standard_mounting": {
            "datum_xy_mm": STANDARD_PATTERN_DATUM[kind],
            "holes": standard_hole_rows(kind),
            "scope": "Alternative spare attachments only. These bores do not select hardware or prove simultaneous compatibility with navigation, radio or their wiring. The bought FC adapter carries25.5/20/16mm factory patterns, but this installed assembly uses16 for the saddle and25.5 for the FC;20 has no qualified use.",
        },
        "deck_size_mm": {
            "battery": BATTERY_DECK_SIZE,
            "electronics": ELECTRONICS_DECK_SIZE,
            "accessory": ACCESSORY_DECK_SIZE,
        }[kind],
        "continuous_adhesive_pads": adhesive_pads[kind],
        "fc_wiring_clearance_mm": FC_WIRING_CLEARANCE,
        "fc_wiring_corridor_width_mm": FC_WIRING_CORRIDOR_WIDTH,
        "fc_wiring_corridor_centre_y_mm": FC_WIRING_CORRIDOR_CENTRE_Y,
        "pas_service_clearance_mm": PAS_SERVICE_CLEARANCE,
        "hole_interface_scope": "PA12 bores are2.6mm clearance choices. Carbon bores remain the seller's nominal2mm. Device XY datums do not establish PCB bearing planes, compressed dampers or complete screw lengths.",
        "unresolved_mounting_stack": "Two opposed16mm screws secure carbon to the saddle; four separate25.5mm bolts and intermediate nuts support the FC soft mounting. Use insulating purchased spacers/dampers and separate upper retention; verify the whole FC lowest-component envelope remains8mm above carbon. Do not clamp PCB or silicone as the carbon stop.",
        "clearance_scope": "Role decks are deliberately smaller than some device envelopes. Declared adhesive patches are supported; device overhang alone does not prove connector, antenna, strength or attachment suitability. Bench fit and cable access remain required.",
    }


def build_mount(doc, parent, kind):
    contract = mount_contract(kind)
    notes = (
        "Compact role-specific PA12 SLS/MJF rail carrier. The FC uses a bought carbon adapter spanning from a16mm four-pad saddle to25.5mm FC axes; battery and accessories use continuous adhesive decks. "
        "No dedicated tie holes, separate radio shelf, printed FC spacers or separate optical feet. "
        "Only the selected optical host receives an integral portal and a distinct print SKU. "
        "Received fit, adhesion, clamping, electrical insulation and actual device mounting stacks remain unverified."
    )
    obj = create_printed_part(
        doc,
        parent,
        MOUNT_NAMES[kind],
        "PRINT | " + PRINT_SKUS[kind],
        mount_shape(kind).copy(),
        PRINT_ROTATION,
        notes,
    )
    set_property(obj, "Role", "Printed equipment carrier")
    set_property(obj, "PrintSKU", PRINT_SKUS[kind])
    set_property(obj, "MountKind", kind)
    set_property(obj, "MountContract", json.dumps(contract, sort_keys=True))
    set_property(obj, "PrintProcess", "PA12 SLS or MJF")
    set_property(obj, "HalfTurnSymmetric", False, "App::PropertyBool")
    set_property(obj, "IntegralOpticalSupport", False, "App::PropertyBool")
    set_property(obj, "PrintSupportsRequired", False, "App::PropertyBool", "Printing")
    set_property(obj, "FDMPrintValidated", False, "App::PropertyBool", "Printing")
    set_property(obj, "MountingStackVerified", False, "App::PropertyBool")
    set_property(obj, "EquipmentFaceZ", support_face_z(kind), "App::PropertyLength")
    set_property(
        obj,
        "CarrierHoleCentres",
        [
            V(*row["centre_xy_mm"], carrier_plate_bottom(kind))
            for row in carrier_hole_rows(kind)
        ],
        "App::PropertyVectorList",
    )
    set_property(obj, "CarrierHoleDiameter", MOUNT_HOLE_DIAMETER, "App::PropertyLength")
    set_property(
        obj,
        "SourceURL",
        adapter_specification.PRODUCT_URL if kind == "electronics" else rail.SOURCE,
    )
    if kind in ("electronics", "accessory"):
        set_property(
            obj,
            "MountingEvidence",
            json.dumps(interfaces.MOUNTING_EVIDENCE, sort_keys=True),
        )
        set_property(
            obj,
            "MountHoleCentres",
            [V(x, y, carrier_plate_bottom(kind)) for x, y in mount_hole_centres(kind)],
            "App::PropertyVectorList",
        )
        set_property(
            obj,
            "MountHoleDiameter",
            interfaces.FC_HOLE_DIAMETER
            if kind == "electronics"
            else interfaces.PAS_HOLE_DIAMETER,
            "App::PropertyLength",
        )
        set_property(
            obj,
            "MountHoleCentresScope",
            "Device XY axes only, at an arbitrary carrier reference plane; no PCB bearing height is implied. FC25.5mm axes belong to the bought carbon adapter. CarrierHoleCentres separately lists actual PA12 bores.",
        )
    return obj
