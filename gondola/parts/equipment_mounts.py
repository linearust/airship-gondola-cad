"""One universal plate/rail-shoe print, installed in three equipment roles."""

import functools
import json
import math

import FreeCAD as App
import Part

from gondola.cad import box, create_printed_part, set_property, union
from gondola.contracts import equipment_interfaces as interfaces

from . import mounting_slots, rail, stack_interface

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
# All three carriers use the same local mechanical datum and physical print.
# Equipment selection/placement is role-specific; the spare slots are not.
COMMON_PRINT_SKU = "UniversalEquipmentCarrier"
COMMON_DECK_SIZE = (54.0, 74.0)
DECK_CORNER_RADIUS = 3.0
NAVIGATION_CENTRE_XY = (0.0, 0.0)
PAS_HOLE_CENTRES = interfaces.PAS_HOLE_CENTRES
COMMON_DEVICE_HOLE_CENTRES = FC_HOLE_CENTRES + PAS_HOLE_CENTRES
# Keep both the rail-clamp key path and diagonal stack-foot hardware accessible.
RADIO_CENTRE_XY = (-15.0, 28.0)
GPS_ADHESIVE_SIZE = (18.0, 14.0)
RADIO_ADHESIVE_SIZE = (22.0, 14.0)
ACCESSORY_DECK_SIZE = COMMON_DECK_SIZE
ACCESSORY_DECK_CENTRE_XY = (0.0, 0.0)
BATTERY_DECK_SIZE = COMMON_DECK_SIZE
ELECTRONICS_DECK_SIZE = COMMON_DECK_SIZE
MOUNT_NAMES = {
    "battery": "BatteryMount",
    "electronics": "ElectronicsMount",
    "accessory": "AccessoryMount",
}
# Keep continuous contact regions clear of every device bore and spare slot.
# The redistributed three battery patches retain the previous 512 mm² total.
BATTERY_ADHESIVE_REGIONS = (
    ((0.0, 0.0), (16.0, 18.0)),
    ((0.0, -23.0), (16.0, 7.0)),
    ((0.0, 23.0), (16.0, 7.0)),
)
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


def standard_slot_rows(kind):
    if kind not in MOUNT_NAMES:
        raise ValueError("Unknown equipment mount kind: " + str(kind))
    return [row for row in mounting_slots.rows() if row["family"] != "side"]


def standard_slot_shapes(
    kind, bottom=DECK_BOTTOM_Z - 1, depth=DECK_THICKNESS + 2, *, border=0.0
):
    return [
        mounting_slots.shape(row, bottom, depth, border=border)
        for row in standard_slot_rows(kind)
    ]


def expansion_slot_rows():
    return [row for row in mounting_slots.rows() if row["family"] == "side"]


def expansion_slot_shapes(
    bottom=DECK_BOTTOM_Z - 1, depth=DECK_THICKNESS + 2, *, border=0.0
):
    return [
        mounting_slots.shape(row, bottom, depth, border=border)
        for row in expansion_slot_rows()
    ]


def common_plate_cutters(bottom, depth):
    """Six verified device bores and ten shared slots, independent of support."""
    return [
        Part.makeCylinder(MOUNT_HOLE_DIAMETER / 2, depth, V(x, y, bottom))
        for x, y in COMMON_DEVICE_HOLE_CENTRES
    ] + mounting_slots.shapes(bottom, depth)


def expansion_contract():
    return {
        "industry_standard_claimed": False,
        "row_spacing_mm": 2 * mounting_slots.SIDE_X,
        "centre_travel_y_mm": mounting_slots.SIDE_Y_RANGE,
        "slots": expansion_slot_rows(),
        "fastener": "M2",
        "slot_width_mm": MOUNT_HOLE_DIAMETER,
        "scope": "Two continuous rounded side slots replace six discrete expansion holes. Their 46 mm row spacing is a project provision, not an industry PCB pattern. The centre can move +/-9 mm along each row before clamping. Installed bodies and hardware can obstruct a chosen position. No arbitrary extension load, head fit, tightening torque or spacer height is qualified by a slot alone.",
    }


def common_plate_contract():
    return {
        "deck_size_mm": (*COMMON_DECK_SIZE, DECK_THICKNESS),
        "deck_centre_xy_mm": (0.0, 0.0),
        "outline_corner_radius_mm": DECK_CORNER_RADIUS,
        "outline_half_turn_symmetric": True,
        "fc_hole_centres_xy_mm": FC_HOLE_CENTRES,
        "pas_hole_centres_xy_mm": PAS_HOLE_CENTRES,
        "device_bore_diameter_mm": MOUNT_HOLE_DIAMETER,
        "standard_mounting": mounting_slots.contract(),
        "expansion": expansion_contract(),
        "fixed_bore_count": len(COMMON_DEVICE_HOLE_CENTRES),
        "slot_count": len(mounting_slots.rows()),
        "scope": "One centred rounded rectangular plate with six verified device bores and ten rounded mounting slots, without projecting utility or structural clamp tabs. The three rail carriers are identical physical prints including the rail shoe and inboard structural tower clamps. The optional power deck uses the same plate template on its integral tower. The outline is symmetric; the complete part retains oriented device holes and a rail clamp, so do not infer half-turn mounting equivalence. FC/P-AS and spare patterns are alternative uses, not permission to populate overlapping equipment simultaneously. Optical sensor tray remains an uninterrupted adhesive surface.",
    }


def common_plate_shape(bottom=DECK_BOTTOM_Z):
    """One intact plate before the rail shoe or tower can mask a broken web."""
    length, width = COMMON_DECK_SIZE
    shape = box(length, width, DECK_THICKNESS, (-length / 2, -width / 2, bottom))
    vertical_edges = [
        edge for edge in shape.Edges if edge.BoundBox.ZLength > DECK_THICKNESS - 0.01
    ]
    shape = shape.makeFillet(DECK_CORNER_RADIUS, vertical_edges)
    for hole in common_plate_cutters(bottom - 1, DECK_THICKNESS + 2):
        shape = shape.cut(hole)
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Common mounting plate must be one valid solid")
    return shape


@functools.lru_cache(None)
def mount_shape(kind):
    if kind not in MOUNT_NAMES:
        raise ValueError("Unknown equipment mount kind: " + str(kind))
    pieces = [common_plate_shape(), rail.shoe_shape()]
    pieces.append(
        box(
            rail.SHOE_LENGTH,
            rail.SHOE_WIDTH,
            DECK_BOTTOM_Z - rail.TOP_Z + 0.2,
            (-rail.SHOE_LENGTH / 2, -rail.SHOE_WIDTH / 2, rail.TOP_Z - 0.1),
        )
    )
    shape = stack_interface.add_host_interface(union(pieces), MOUNT_NAMES[kind])
    # Cut again through any supporting member sharing a plate-hole position.
    for hole in common_plate_cutters(DECK_BOTTOM_Z - 1, DECK_THICKNESS + 2):
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
                "support_face": "bottom",
            },
            {
                "device": "MG-A01 / M10 Ultra or MG-F10-A",
                "centre_xy_mm": NAVIGATION_CENTRE_XY,
                "size_mm": GPS_ADHESIVE_SIZE,
            },
        ],
    }
    scope = {
        "battery": "Universal carrier in battery role. Three declared continuous adhesive regions remain between the device bores and mounting slots; the structural tower datum is shared with FC/navigation carriers.",
        "electronics": "Universal carrier in FC role. Confirmed FC holes and 8 mm underbody wiring reservation remain; the same symmetric plate outline and spare patterns exist on every carrier.",
        "accessory": "Universal carrier in navigation role. Centred P-AS mounting axes or mutually exclusive taped GPS alternatives use the outer face. The Mini uses a fully supported 22 x 14 mm insulating-adhesive allocation on the opposite, rail-facing face, outboard of the rail shoe; its body has minor edge/corner overhang beyond the rounded plate. No separate radio plate, tab or pocket. The populated face and connector working direction face the balloon: actual envelope curvature, plug height, antenna and lead clearance remain unverified. Remove the carrier for bench attachment and service. The centred common tower datum accepts a separately screened optional power platform; this carrier is not an optical host.",
    }
    return {
        "kind": kind,
        "shared_print_sku": COMMON_PRINT_SKU,
        "common_plate": common_plate_contract(),
        "expansion_mounting": expansion_contract(),
        "physical_device_hole_centres_xy_mm": COMMON_DEVICE_HOLE_CENTRES,
        "stack_interface": stack_interface.interface_contract(MOUNT_NAMES[kind]),
        "standard_mounting": mounting_slots.contract(),
        "deck_bottom_z_mm": DECK_BOTTOM_Z,
        "deck_thickness_mm": DECK_THICKNESS,
        "support_face_z_mm": SUPPORT_FACE_Z,
        "integral_common_rail_shoe": True,
        "deck_underside_to_rail_head_mm": DECK_BOTTOM_Z - rail.HEAD_TOP,
        "future_fastener_scope": "The deck underside is 3 mm above the rail head: a nominal 2 mm head leaves 1 mm vertical clearance. Hole/slot positions alone do not select a head, nut, spacer length, board body or wiring arrangement. Check the chosen hardware against the shoe, board and neighboring devices; spare slot fasteners are not installed BOM items.",
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
        "hole_interface_scope": "Six device-specific bores preserve verified XY axes and bearing lands. Diameter 2.6 mm is our M2 clearance choice, not the original device hole diameter. The separate standard_mounting contract defines adjustable square-pitch and side slots. No printed threads or device posts.",
        "unresolved_mounting_stack": "Use purchased M2 hardware and OEM FC silicone dampers. Actual PCB bearing planes, damper compression, spacer and bolt lengths remain pending; these purchased parts are not generated at invented elevations.",
        "clearance_scope": "FC 8 mm and P-AS 4 mm are design reservations below conservative component envelopes, not manufacturer mounting-height requirements. Inspect cable access, adhesive contact, clamp strength and actual fit before use. A plain plate does not establish device underside flatness, adhesion or loaded helix stiffness.",
    }


def build_mount(doc, parent, kind):
    contract = mount_contract(kind)
    name = MOUNT_NAMES[kind]
    notes = (
        "Universal PA12 SLS/MJF carrier: print three identical copies for battery, FC and navigation. "
        "Centred 54 x 74 mm rounded rectangular deck, six device bores and ten shared mounting slots, "
        "integral rail shoe and inboard structural tower clamps. Choose the occupied role at assembly. "
        "Preserve the declared adhesive patches; spare slots do not qualify arbitrary simultaneous devices. "
        "No dedicated tie holes, separate radio plate, printed device spacers or added fasteners. "
        "Printed fit, clamping, adhesive retention, wiring, extension loads and actual device stacks remain unverified."
    )
    obj = create_printed_part(
        doc,
        parent,
        name,
        "PRINT | Universal carrier | " + kind,
        mount_shape(kind).copy(),
        PRINT_ROTATION,
        notes,
    )
    set_property(obj, "Role", "Printed equipment carrier")
    set_property(obj, "PrintSKU", COMMON_PRINT_SKU)
    set_property(obj, "MountKind", kind)
    stack_interface.annotate_interface(obj, name)
    set_property(obj, "MountContract", json.dumps(contract, sort_keys=True))
    set_property(obj, "PrintProcess", "PA12 SLS or MJF")
    set_property(obj, "HalfTurnSymmetric", False, "App::PropertyBool")
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
