"""Minimal equipment carriers with one integral common rail shoe each."""

import functools
import json
import math

import FreeCAD as App
import Part

from gondola.cad import box, create_printed_part, set_property, union
from gondola.contracts import equipment_interfaces as interfaces

from . import rail, stack_interface

V = App.Vector
DECK_BOTTOM_Z = stack_interface.HOST_DECK_BOTTOM_Z
DECK_THICKNESS = stack_interface.DECK_THICKNESS
SUPPORT_FACE_Z = DECK_BOTTOM_Z + DECK_THICKNESS
MOUNT_HOLE_DIAMETER = 2.6
MOUNT_PAD_DIAMETER = 6.5
FC_CENTRE_XY = (0.0, 0.0)
FC_ROTATION_DEG = -45.0
FC_AXIS_OFFSET = interfaces.FC_HOLE_PITCH / math.sqrt(2)
FC_HOLE_CENTRES = (
    (-FC_AXIS_OFFSET, 0.0),
    (0.0, -FC_AXIS_OFFSET),
    (0.0, FC_AXIS_OFFSET),
    (FC_AXIS_OFFSET, 0.0),
)
# Navigation and the onboard radio share one plain accessory plate, independently
# movable along the rail. These are accessory-local, not FC-carrier coordinates.
NAVIGATION_CENTRE_XY = (14.0, -24.0)
PAS_HOLE_CENTRES = tuple(
    (x + NAVIGATION_CENTRE_XY[0], y + NAVIGATION_CENTRE_XY[1])
    for x, y in interfaces.PAS_HOLE_CENTRES
)
RADIO_CENTRE_XY = (14.0, 21.0)
GPS_ADHESIVE_SIZE = (18.0, 14.0)
RADIO_ADHESIVE_SIZE = (22.0, 14.0)
ACCESSORY_DECK_SIZE = (36.0, 78.0)
ACCESSORY_DECK_CENTRE_XY = (14.0, -4.0)
MOUNT_NAMES = {
    "battery": "BatteryMount",
    "electronics": "ElectronicsMount",
    "accessory": "AccessoryMount",
}
BATTERY_DECK_SIZE = (34.0, 52.0)
ELECTRONICS_DECK_SIZE = (44.0, 44.0)
# Two bores cross the original battery tape strip. Three uninterrupted patches
# retain useful adhesive contact without disguising those standard holes.
BATTERY_ADHESIVE_REGIONS = (
    ((0.0, 0.0), (16.0, 20.0)),
    ((0.0, -21.0), (16.0, 10.0)),
    ((0.0, 21.0), (16.0, 10.0)),
)
STANDARD_PATTERNS = {
    "battery": ((20.0, 35.0),),
    "electronics": ((20.0, 35.0), (30.5, 0.0)),
    "accessory": ((20.0, 35.0),),
}
STANDARD_PATTERN_DATUM = {
    "battery": (0.0, 0.0),
    "electronics": (0.0, 0.0),
    "accessory": (15.0, -24.0),
}
BATTERY_PLACEMENT_CONTRACT = {
    "centre_x_limit_mm": 5.0,
    "centre_y_limit_mm": 4.0,
    "maximum_size_mm": [66, 18, 17],
    "minimum_stack_tower_gap_mm": 1.5,
    "frame": "Battery carrier XY; pack long axis along Y, nominal 1mm adhesive allowance",
    "qualification": "Geometric placement envelope only. Actual pack size, adhesive contact and retention remain unverified. For larger trim changes move the carrier along the rail and recheck module clearances; do not push the pack into the integral optical tower.",
}
FC_WIRING_CLEARANCE = 8.0
FC_WIRING_CORRIDOR_WIDTH = 8.0
FC_WIRING_CORRIDOR_CENTRE_Y = 9.0
PAS_SERVICE_CLEARANCE = 4.0
ADHESIVE_ALLOWANCE = 1.0
PRINT_ROTATION = App.Rotation(V(1, 0, 0), 180)


def _deck(size, centre):
    return box(
        size[0],
        size[1],
        DECK_THICKNESS,
        (centre[0] - size[0] / 2, centre[1] - size[1] / 2, DECK_BOTTOM_Z),
    )


def fc_wiring_reserve_shape():
    """Our eight-mm free-height corridor, open at both X ends below the FC.

    This is a design allowance beneath the whole component envelope, not a measured
    connector model or a manufacturer-specified spacer/PCB bearing-plane height.
    """
    half_length = interfaces.FC_SIZE_MM[0] / math.sqrt(2)
    return box(
        half_length * 2,
        FC_WIRING_CORRIDOR_WIDTH,
        FC_WIRING_CLEARANCE,
        (
            -half_length,
            FC_WIRING_CORRIDOR_CENTRE_Y - FC_WIRING_CORRIDOR_WIDTH / 2,
            SUPPORT_FACE_Z,
        ),
    )


def mount_hole_centres(kind):
    if kind not in MOUNT_NAMES:
        raise ValueError("Unknown equipment mount kind: " + str(kind))
    return {
        "battery": (),
        "electronics": FC_HOLE_CENTRES,
        "accessory": PAS_HOLE_CENTRES,
    }[kind]


def standard_hole_rows(kind):
    if kind not in MOUNT_NAMES:
        raise ValueError("Unknown equipment mount kind: " + str(kind))
    return stack_interface.board_hole_rows(
        STANDARD_PATTERNS[kind], STANDARD_PATTERN_DATUM[kind]
    )


def standard_hole_shapes(
    kind, bottom=DECK_BOTTOM_Z - 1, depth=DECK_THICKNESS + 2, *, border=0.0
):
    return stack_interface.board_hole_shapes(
        standard_hole_rows(kind), bottom, depth, border=border
    )


@functools.lru_cache(None)
def mount_shape(kind):
    holes = mount_hole_centres(kind)
    size, centre = {
        "battery": (BATTERY_DECK_SIZE, (0.0, 0.0)),
        "electronics": (ELECTRONICS_DECK_SIZE, (0.0, 0.0)),
        "accessory": (ACCESSORY_DECK_SIZE, ACCESSORY_DECK_CENTRE_XY),
    }[kind]
    pieces = [_deck(size, centre)]
    pieces.append(rail.shoe_shape())
    # Raise only equipment decks. The rail mating shape and propulsion shoe stay
    # unchanged; a plain solid bridge joins the existing shoe top to the deck.
    pieces.append(
        box(
            rail.SHOE_LENGTH,
            rail.SHOE_WIDTH,
            DECK_BOTTOM_Z - rail.TOP_Z + 0.2,
            (-rail.SHOE_LENGTH / 2, -rail.SHOE_WIDTH / 2, rail.TOP_Z - 0.1),
        )
    )
    shape = union(pieces)
    shape = stack_interface.add_host_interface(shape, MOUNT_NAMES[kind])
    for x, y in holes:
        shape = shape.cut(
            Part.makeCylinder(
                MOUNT_HOLE_DIAMETER / 2,
                DECK_THICKNESS + 2,
                V(x, y, DECK_BOTTOM_Z - 1),
            )
        )
    for hole in standard_hole_shapes(kind):
        shape = shape.cut(hole)
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Equipment mount is not one valid solid: " + kind)
    return shape


def mount_contract(kind):
    holes = mount_hole_centres(kind)
    adhesive_pads = {
        "battery": [
            {
                "device": "battery",
                "centre_xy_mm": centre,
                "size_mm": size,
            }
            for centre, size in BATTERY_ADHESIVE_REGIONS
        ],
        "electronics": [],
        "accessory": [
            {
                "device": "LR24-F-Mini",
                "centre_xy_mm": RADIO_CENTRE_XY,
                "size_mm": RADIO_ADHESIVE_SIZE,
            },
            {
                "device": "MG-A01 / M10 Ultra or MG-F10-A",
                "centre_xy_mm": NAVIGATION_CENTRE_XY,
                "size_mm": GPS_ADHESIVE_SIZE,
            },
        ],
    }
    scope = {
        "battery": "One plain rectangular deck and integral rail shoe, with a centred 20 mm M2 pattern. Two standard holes interrupt the old tape strip; three declared continuous adhesive regions remain. The optical tower uses separate structural anchors.",
        "electronics": "One flat square deck, confirmed FC holes, common 20 mm M2 and 30.5 mm M3 patterns, integral rail shoe and separate structural tower anchors. No navigation or radio extensions.",
        "accessory": "One rectangular plate and integral rail shoe, with a 20 mm M2 pattern in the navigation bay. Two confirmed P-AS holes share the navigation region with mutually exclusive taped GPS alternatives. The radio and selected navigation device use separate regions. The common structural attachment is shifted +16.5 mm local Y to clear the Mini; only separately validated optional power platforms may use it. This plate is not an optical-stack host.",
    }
    return {
        "kind": kind,
        "stack_interface": stack_interface.interface_contract(MOUNT_NAMES[kind]),
        "standard_mounting": stack_interface.board_pattern_contract(
            STANDARD_PATTERNS[kind], STANDARD_PATTERN_DATUM[kind]
        ),
        "deck_bottom_z_mm": DECK_BOTTOM_Z,
        "deck_thickness_mm": DECK_THICKNESS,
        "support_face_z_mm": SUPPORT_FACE_Z,
        "integral_common_rail_shoe": True,
        "deck_underside_to_rail_head_mm": DECK_BOTTOM_Z - rail.HEAD_TOP,
        "future_fastener_scope": "The deck underside is 3 mm above the rail head: a nominal 2 mm head leaves 1 mm vertical clearance. Hole pitch alone does not select a head, nut, spacer length, board body or wiring arrangement. Check the chosen hardware against the shoe, board and neighboring devices; generic holes are not installed BOM items.",
        "mount_hole_centres_xy_mm": list(holes),
        "mount_hole_diameter_mm": MOUNT_HOLE_DIAMETER,
        "mount_pad_diameter_mm": MOUNT_PAD_DIAMETER,
        "electronics_deck_size_mm": ELECTRONICS_DECK_SIZE
        if kind == "electronics"
        else None,
        "accessory_deck_size_mm": ACCESSORY_DECK_SIZE if kind == "accessory" else None,
        "accessory_deck_centre_xy_mm": ACCESSORY_DECK_CENTRE_XY
        if kind == "accessory"
        else None,
        "support_path_scope": scope[kind],
        "continuous_adhesive_pads": adhesive_pads[kind],
        "fc_wiring_clearance_mm": FC_WIRING_CLEARANCE,
        "fc_wiring_corridor_width_mm": FC_WIRING_CORRIDOR_WIDTH,
        "fc_wiring_corridor_centre_y_mm": FC_WIRING_CORRIDOR_CENTRE_Y,
        "pas_service_clearance_mm": PAS_SERVICE_CLEARANCE,
        "hole_interface_scope": "Device-specific holes preserve verified XY axes; the separate standard_mounting contract defines additional common patterns. Diameter 2.6 mm is our M2 clearance choice, not the original device hole diameter. No printed threads or device posts.",
        "unresolved_mounting_stack": "Use purchased M2 hardware and OEM FC silicone dampers. Actual PCB bearing planes, damper compression, spacer and bolt lengths remain pending; these purchased parts are not generated at invented elevations.",
        "clearance_scope": "FC 8 mm and P-AS 4 mm are design reservations below conservative component envelopes, not manufacturer mounting-height requirements. Inspect cable access, adhesive contact, clamp strength and actual fit before use. A plain plate does not establish device underside flatness, adhesion or loaded helix stiffness.",
    }


def build_mount(doc, parent, kind):
    contract = mount_contract(kind)
    name = MOUNT_NAMES[kind]
    notes = (
        "One integral common rail shoe; PA12 SLS/MJF. "
        + contract["support_path_scope"]
        + " "
        + contract["clearance_scope"]
    )
    obj = create_printed_part(
        doc,
        parent,
        name,
        "PRINT | " + name,
        mount_shape(kind).copy(),
        PRINT_ROTATION,
        notes,
    )
    set_property(obj, "Role", "Printed equipment carrier")
    set_property(obj, "PrintSKU", name)
    set_property(obj, "MountKind", kind)
    stack_interface.annotate_interface(obj, name)
    set_property(obj, "MountContract", json.dumps(contract, sort_keys=True))
    set_property(obj, "PrintProcess", "PA12 SLS or MJF")
    set_property(obj, "HalfTurnSymmetric", kind == "battery", "App::PropertyBool")
    set_property(obj, "PrintSupportsRequired", False, "App::PropertyBool", "Printing")
    set_property(obj, "FDMPrintValidated", False, "App::PropertyBool", "Printing")
    set_property(obj, "MountingStackVerified", False, "App::PropertyBool")
    set_property(obj, "EquipmentFaceZ", SUPPORT_FACE_Z, "App::PropertyLength")
    set_property(
        obj, "SourceURL", interfaces.FC_SOURCE if kind == "electronics" else rail.SOURCE
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
            [V(x, y, DECK_BOTTOM_Z) for x, y in mount_hole_centres(kind)],
            "App::PropertyVectorList",
        )
        set_property(
            obj, "MountHoleDiameter", MOUNT_HOLE_DIAMETER, "App::PropertyLength"
        )
    return obj
