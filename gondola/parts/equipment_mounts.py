"""One universal plate/rail-shoe print, installed in three equipment roles."""

import functools
import json
import math

import FreeCAD as App
import Part

from gondola.cad import box, create_printed_part, polygon_extrusion, set_property, union
from gondola.contracts import equipment_interfaces as interfaces

from . import mounting_plate, mounting_slots, rail, stack_interface

V = App.Vector
DECK_BOTTOM_Z = mounting_plate.CARRIER_BOTTOM_Z
DECK_THICKNESS = mounting_plate.THICKNESS_MM
SUPPORT_FACE_Z = mounting_plate.CARRIER_SUPPORT_Z
MOUNT_HOLE_DIAMETER = mounting_plate.FIXED_HOLE_DIAMETER_MM
MOUNT_PAD_DIAMETER = mounting_plate.FC_PAD_DIAMETER_MM
FC_CENTRE_XY = (0.0, 0.0)
FC_ROTATION_DEG = -45.0
FC_HOLE_CENTRES = mounting_plate.FC_HOLE_CENTRES
# All three carriers use the same local mechanical datum and physical print.
# Equipment selection/placement is role-specific; the spare slots are not.
COMMON_PRINT_SKU = "UniversalEquipmentCarrier"
COMMON_DECK_SIZE = mounting_plate.SIZE_MM
# A round section spreads the deck load while preserving the continuous
# underside head paths of the innermost 16 mm square mounting pattern.
CENTRAL_SUPPORT_DIAMETER_MM = 17.0
CENTRE_NUT_AF_MM = 4.15
CENTRE_POCKET_FLOOR_Z = 10.0
CENTRE_NUT_SEAT_Z = 12.4
CENTRE_NUT_PORT_START_X = -12.0
NAVIGATION_CENTRE_XY = (0.0, -2.2)
PAS_HOLE_CENTRES = tuple(
    (x + NAVIGATION_CENTRE_XY[0], y + NAVIGATION_CENTRE_XY[1])
    for x, y in interfaces.PAS_HOLE_CENTRES
)
COMMON_DEVICE_HOLE_CENTRES = mounting_plate.FIXED_HOLE_CENTRES
# Keep both the rail-clamp key path and diagonal stack-foot hardware accessible.
RADIO_CENTRE_XY = (26.0, -11.0)
RADIO_YAW_DEG = 90.0
GPS_ADHESIVE_REGIONS = (
    ((0.0, -5.5), (12.0, 7.0)),
    ((0.0, 5.5), (12.0, 7.0)),
)
RADIO_ADHESIVE_REGIONS = (
    ((23.0, -7.5), (4.0, 15.0)),
    ((30.0, -11.0), (3.0, 20.0)),
)
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
# Four uninterrupted patches preserve 376 mm² around the spare centre bore.
BATTERY_ADHESIVE_REGIONS = (
    ((0.0, -6.5), (12.0, 9.0)),
    ((0.0, 6.5), (12.0, 9.0)),
    ((0.0, -22.5), (16.0, 5.0)),
    ((0.0, 22.5), (16.0, 5.0)),
)
BATTERY_PLACEMENT_CONTRACT = {
    "centre_x_limit_mm": 5.0,
    "centre_y_limit_mm": 4.0,
    "maximum_size_mm": [66, 18, 17],
    "minimum_stack_tower_gap_mm": 1.5,
    "frame": "Battery carrier XY; pack long axis along Y, nominal 1mm adhesive allowance",
    "qualification": "Geometric placement envelope only; shifted packs do not necessarily cover every nominal adhesive patch. Actual pack size, contact and retention remain unverified. Use the carrier's rail travel for larger trim changes and recheck the compact optical mount and wiring.",
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


def expansion_contract():
    return {
        "industry_standard_claimed": False,
        "row_spacing_mm": 2 * mounting_slots.SIDE_X,
        "centre_travel_y_mm": mounting_slots.SIDE_Y_RANGE,
        "middle_centre_travel_y_mm": mounting_slots.SIDE_MIDDLE_Y_RANGE,
        "slots": expansion_slot_rows(),
        "slot_count": len(expansion_slot_rows()),
        "fastener": "M2",
        "slot_width_mm": MOUNT_HOLE_DIAMETER,
        "scope": "Twelve outer slots on four sides of a 54 mm square. Each side has three ten-mm centre-travel intervals: -23 to -13, -5 to 5, and 13 to 23 mm from its midpoint. This is a project provision, not an industry PCB standard. Optional power feet use their separately reviewed positions within this array. Installed bodies and hardware can obstruct a chosen position. No arbitrary extension load, head fit, tightening torque or spacer height is qualified by a slot alone.",
    }


def common_plate_contract():
    return {
        "deck_size_mm": (*COMMON_DECK_SIZE, DECK_THICKNESS),
        "deck_centre_xy_mm": (0.0, 0.0),
        "outline_corner_radius_mm": mounting_plate.CORNER_RADIUS_MM,
        "central_support": {
            "profile": "round support with one blind central nut seat and lateral port",
            "diameter_mm": CENTRAL_SUPPORT_DIAMETER_MM,
            "height_mm": DECK_BOTTOM_Z - rail.TOP_Z,
            "z_range_mm": (rail.TOP_Z, DECK_BOTTOM_Z),
            "scope": "Round support retains a solid 1.5 mm nominal floor above the rail capture under one optional centre nut seat. A single lateral loading port leaves the common M2 slot head paths open. No separate spacer; this geometric load path is not a strength or stiffness qualification.",
        },
        "outline_half_turn_symmetric": True,
        "plate_quarter_turn_and_xy_mirror_symmetric": True,
        "fc_hole_centres_xy_mm": FC_HOLE_CENTRES,
        "pas_hole_centres_xy_mm": PAS_HOLE_CENTRES,
        "device_bore_diameter_mm": MOUNT_HOLE_DIAMETER,
        "standard_mounting": mounting_slots.contract(),
        "expansion": expansion_contract(),
        "fixed_bore_count": len(COMMON_DEVICE_HOLE_CENTRES),
        "fixed_fc_bore_count": len(FC_HOLE_CENTRES),
        "spare_centre_bore_diameter_mm": mounting_plate.CENTRE_HOLE_DIAMETER_MM,
        "slot_count": len(mounting_slots.rows()),
        "scope": "One rounded square plate with four fixed FC bores, one spare centre M2 bore and the shared inner-diagonal, outer-diagonal, arc and side slot families. The outline and every mounting opening have quarter-turn and X/Y mirror symmetry; the integral rail shoe and clamp remain directional. The three rail carriers are identical physical prints. P-AS is shifted 2.2 mm along local negative Y so its verified holes use two diagonal-slot endpoints on a 23 mm square. Optional-power feet use the outer slot array directly, without special clamp bores or projecting tabs. The optional power deck shares the centre through-bore but has no carrier nut pocket. Patterns are alternative uses, not permission to populate overlapping devices simultaneously.",
    }


def centre_nut_pocket():
    """A side-loaded M2 nut seat above an intact rail-capture roof."""
    radius = CENTRE_NUT_AF_MM / math.sqrt(3)
    depth = CENTRE_NUT_SEAT_Z - CENTRE_POCKET_FLOOR_Z
    pocket = polygon_extrusion(
        [
            (
                radius * math.cos(math.radians(angle)),
                radius * math.sin(math.radians(angle)),
                CENTRE_POCKET_FLOOR_Z,
            )
            for angle in range(0, 360, 60)
        ],
        (0, 0, depth),
    )
    return pocket.fuse(
        box(
            -CENTRE_NUT_PORT_START_X,
            CENTRE_NUT_AF_MM,
            depth,
            (CENTRE_NUT_PORT_START_X, -CENTRE_NUT_AF_MM / 2, CENTRE_POCKET_FLOOR_Z),
        )
    )


def centre_mount_contract():
    return {
        "centre_xy_mm": (0.0, 0.0),
        "clearance_bore_diameter_mm": mounting_plate.CENTRE_HOLE_DIAMETER_MM,
        "optional_fastener": "Existing-kit M2 screw and M2 hex nut; absent from baseline BOM",
        "nut_pocket_af_mm": CENTRE_NUT_AF_MM,
        "finished_nut_pocket_af_range_mm": (4.05, 4.25),
        "nut_seat_z_mm": CENTRE_NUT_SEAT_Z,
        "pocket_floor_z_mm": CENTRE_POCKET_FLOOR_Z,
        "nominal_floor_above_rail_capture_mm": 1.5,
        "bare_plate_example_screw_length_mm": 5.0,
        "bare_plate_example_tip_projection_mm": 0.4,
        "bare_plate_example_tip_to_floor_mm": 0.4,
        "maximum_geometric_penetration_below_deck_top_mm": 5.4,
        "assembly": "Load the M2 nut horizontally from local negative X, then tighten a screw from above. Use an empty centre interface and bench access; occupied boards/battery are alternatives. The simple port stays open, so retain the loose nut until the bolt engages. No extra printed part or installed baseline fastener.",
        "length_selection": "Select under-head length minus the actual attached-part thickness for full nut engagement while leaving a measured gap above the blind floor. Nominal M2x5 through the bare plate projects 0.4 mm below the 1.6 mm nut and stops 0.4 mm above the floor. Never exceed the 5.4 mm geometric penetration from the deck top or tighten a bottomed bolt. Print and hardware tolerances can consume the nominal gap; this example is not a received-lot fit approval.",
        "qualification": "Measure the existing-kit nut and finish the 4.15 mm seat/port to 4.05..4.25 mm across flats; check antirotation, loading and screw tip clearance. The intact floor separates the bolt from the rail; it is not a puncture or overtightening guarantee. No arbitrary accessory load or clamp strength is qualified.",
    }


@functools.lru_cache(None)
def mount_shape(kind):
    if kind not in MOUNT_NAMES:
        raise ValueError("Unknown equipment mount kind: " + str(kind))
    pieces = [mounting_plate.shape(), rail.shoe_shape()]
    pieces.append(
        Part.makeCylinder(
            CENTRAL_SUPPORT_DIAMETER_MM / 2,
            DECK_BOTTOM_Z - rail.TOP_Z + 0.2,
            V(0, 0, rail.TOP_Z - 0.1),
        )
    )
    shape = union(pieces)
    # Cut again through any supporting member sharing a plate-hole position.
    for hole in mounting_plate.cutters(DECK_BOTTOM_Z - 1, DECK_THICKNESS + 2):
        shape = shape.cut(hole)
    shape = shape.cut(centre_nut_pocket())
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
            *(
                {
                    "device": "LR24-F-Mini",
                    "centre_xy_mm": centre,
                    "size_mm": size,
                    "support_face": "bottom",
                }
                for centre, size in RADIO_ADHESIVE_REGIONS
            ),
            *(
                {
                    "device": "MG-A01 / M10 Ultra or MG-F10-A",
                    "centre_xy_mm": centre,
                    "size_mm": size,
                }
                for centre, size in GPS_ADHESIVE_REGIONS
            ),
        ],
    }
    scope = {
        "battery": "Universal carrier in battery role. Four declared continuous adhesive regions retain 376 mm2 around the centre bore and other openings. The common outer slots support separately screened optional power feet, as on the other carriers.",
        "electronics": "Universal carrier in FC role. Confirmed FC holes and 8 mm underbody wiring reservation remain; the same symmetric plate outline and spare patterns exist on every carrier.",
        "accessory": "Universal navigation carrier. P-AS axes and mutually exclusive GPS alternatives share the local (0,-2.2) datum. The Mini body is centred at (26,-11) with its long axis along carrier Y. Two continuous insulating-adhesive strips, 4 x 15 mm at (23,-7.5) and 3 x 20 mm at (30,-11), lie on the rail-facing face on opposite sides of the outer slot row. Each strip has complete carrier backing and nominal body overlap. This retains 120 mm2 total available contact while leaving the new middle slot open, without moving the body or connector reserves. The body overhangs the square plate edge and clears both rail-clamp tool approaches and optional portal service reserves. The allocation is not a qualified minimum holding area. No separate radio plate, tab or pocket. Populated face and connector access face the balloon; actual envelope curvature, plug height, underside components, antenna and retention remain unverified. Remove the carrier for bench service. The outer common slots also accept the separately screened optional power platform. The optical foot can use an existing middle side slot; occupied host/side and power combinations need their composed clearance checks.",
    }
    return {
        "kind": kind,
        "shared_print_sku": COMMON_PRINT_SKU,
        "common_plate": common_plate_contract(),
        "optional_centre_mount": centre_mount_contract(),
        "expansion_mounting": expansion_contract(),
        "physical_device_hole_centres_xy_mm": COMMON_DEVICE_HOLE_CENTRES,
        "stack_interface": stack_interface.interface_contract(MOUNT_NAMES[kind]),
        "standard_mounting": mounting_slots.contract(),
        "deck_bottom_z_mm": DECK_BOTTOM_Z,
        "deck_thickness_mm": DECK_THICKNESS,
        "support_face_z_mm": SUPPORT_FACE_Z,
        "integral_common_rail_shoe": True,
        "deck_underside_to_rail_head_mm": DECK_BOTTOM_Z - rail.HEAD_TOP,
        "future_fastener_scope": "The deck_underside_to_rail_head_mm value describes vertical planning clearance only; a chosen screw head consumes part of it. Hole/slot positions alone do not select a head, nut, spacer length, board body or wiring arrangement. Check the chosen hardware against the shoe, board and neighboring devices; spare slot fasteners are not installed BOM items.",
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
        "hole_interface_scope": "Four fixed FC bores preserve the 25.5 mm pattern and complete bearing annuli. The P-AS's published two axes lie at endpoints of two shared 23 mm diagonal slots after the declared navigation shift. M2 openings are 2.6 mm wide; this is our clearance choice, not the OEM hole diameter. Slot seats have continuous side lands, not full circular annuli. No printed threads or device posts.",
        "unresolved_mounting_stack": "Use purchased M2 hardware and OEM FC silicone dampers. Actual PCB bearing planes, damper compression, spacer and bolt lengths remain pending; these purchased parts are not generated at invented elevations.",
        "clearance_scope": "FC 8 mm and P-AS 4 mm are design reservations below conservative component envelopes, not manufacturer mounting-height requirements. Inspect cable access, adhesive contact, clamp strength and actual fit before use. A plain plate does not establish device underside flatness, adhesion or loaded helix stiffness.",
    }


def build_mount(doc, parent, kind):
    contract = mount_contract(kind)
    name = MOUNT_NAMES[kind]
    notes = (
        "Universal PA12 SLS/MJF carrier: print three identical copies for battery, FC and navigation. "
        f"Centred 64 x 64 mm rounded square deck, four FC bores, one spare centre M2 bore and {len(mounting_slots.rows())} symmetric mounting slots, "
        f"integral rail shoe joined to the deck by one diameter {CENTRAL_SUPPORT_DIAMETER_MM:g} mm circular support with a blind centre nut seat and one lateral loading port. "
        "The intact floor separates an optional centre bolt from the rail; choose length to leave tip clearance. No centre hardware is installed in the baseline. Existing underside M2 slot head paths and both rail-clamp approaches stay open. Choose the occupied role at assembly. "
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
        obj,
        "CentralSupportDiameter",
        CENTRAL_SUPPORT_DIAMETER_MM,
        "App::PropertyLength",
    )
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
