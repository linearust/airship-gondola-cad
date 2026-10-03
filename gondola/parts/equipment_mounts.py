"""Shared plate pattern; two fixed carriers and one adjustable instrument carrier."""

import functools
import json
import math

import FreeCAD as App

from gondola.cad import box, create_printed_part, set_property, union
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
# Two short straight supports leave the centre accessory bore open below the deck.
SUPPORT_X_RANGES_MM = ((-8.0, -3.0), (3.0, 8.0))
SUPPORT_Y_RANGE_MM = (-2.5, 2.5)
PAS_CENTRE_XY = (0.0, 9.3)
GPS_CENTRE_XY = (0.0, -2.2)
PAS_HOLE_CENTRES = tuple(
    (x + PAS_CENTRE_XY[0], y + PAS_CENTRE_XY[1]) for x, y in interfaces.PAS_HOLE_CENTRES
)
COMMON_FIXED_HOLE_CENTRES = mounting_plate.FIXED_HOLE_CENTRES
# Keep diagonal stack-foot hardware accessible.
RADIO_CENTRE_XY = (26.0, -17.0)
RADIO_YAW_DEG = 90.0
GPS_ADHESIVE_REGIONS = (
    ((0.0, -6.5), (12.0, 5.0)),
    ((0.0, 6.5), (12.0, 5.0)),
)
RADIO_ADHESIVE_REGIONS = (
    ((23.0, -12.0), (5.0, 12.0)),
    ((30.5, -13.5), (4.0, 15.0)),
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
# Four uninterrupted patches preserve 304 mm² around the centre bore.
BATTERY_ADHESIVE_REGIONS = (
    ((0.0, -7.0), (12.0, 6.0)),
    ((0.0, 7.0), (12.0, 6.0)),
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
        "scope": "Twelve outer slots on four sides of a 54 mm slot-centre square within the 66 mm deck. Each side has centre-travel intervals -19 to -13, -5 to 5, and 13 to 19 mm from its midpoint. This is a project provision, not an industry PCB standard. Optional power feet use their separately reviewed positions within this array. Installed bodies and hardware can obstruct a chosen position. No arbitrary extension load, head fit, tightening torque or spacer height is qualified by a slot alone.",
    }


def common_plate_contract():
    return {
        "deck_size_mm": (*COMMON_DECK_SIZE, DECK_THICKNESS),
        "deck_centre_xy_mm": (0.0, 0.0),
        "outline_corner_radius_mm": mounting_plate.CORNER_RADIUS_MM,
        "central_support": {
            "profile": "two centred rectangular supports with an open centre",
            "x_ranges_mm": SUPPORT_X_RANGES_MM,
            "y_range_mm": SUPPORT_Y_RANGE_MM,
            "height_mm": DECK_BOTTOM_Z - rail.MOUNT_TOP_Z,
            "z_range_mm": (rail.MOUNT_TOP_Z, DECK_BOTTOM_Z),
            "scope": "Two symmetrically centred integral supports connect the deck to the U-shaped rail-shoe roof. Their 6 mm central gap preserves access below the centre bore; the declared deck-to-roof height limits screw-head, nut and tip clearance. No centre nut pocket or separate spacer. Geometry does not qualify strength or creep.",
        },
        "complete_carrier_half_turn_symmetric": False,
        "plate_quarter_turn_and_xy_mirror_symmetric": True,
        "fc_hole_centres_xy_mm": FC_HOLE_CENTRES,
        "pas_hole_centres_xy_mm": PAS_HOLE_CENTRES,
        "device_bore_diameter_mm": MOUNT_HOLE_DIAMETER,
        "standard_mounting": mounting_slots.contract(),
        "expansion": expansion_contract(),
        "fixed_bore_count": len(COMMON_FIXED_HOLE_CENTRES),
        "fc_slot_count": len(FC_HOLE_CENTRES),
        "centre_through_bore_diameter_mm": mounting_plate.CENTRE_HOLE_DIAMETER_MM,
        "slot_count": len(mounting_slots.rows()),
        "scope": "One66mm rounded-square plate with one2.6mm central bore and40 shared slots. Four short FC slots retain the nominal25.5mm axes within square pitches25..26mm and full6.5mm bearing-face sweeps except the intentional openings. Optical side-middle slots remain. P-AS uses the23mm opposed axial endpoints with its declared positive-Y offset. The deck has quarter-turn and X/Y mirror symmetry; its U rail shoe is directional. Two fixed carriers share one print; the adjustable FC carrier and optional power deck share its plate template. Optional Pi5/A8 provisions are alternative mounting patterns, not populated-device, fastener, electrical, strength or simultaneous-installation qualification.",
    }


def centre_mount_contract():
    return {
        "centre_xy_mm": (0.0, 0.0),
        "fastener": "Optional M2 accessory hardware; not a rail attachment",
        "clearance_bore_diameter_mm": mounting_plate.CENTRE_HOLE_DIAMETER_MM,
        "under_deck_gap_mm": DECK_BOTTOM_Z - rail.MOUNT_TOP_Z,
        "carrier_nut_pocket": False,
        "available_as_spare_accessory_mount": True,
        "qualification": f"The deck bore is open into a 6 mm wide, {DECK_BOTTOM_Z - rail.MOUNT_TOP_Z:g} mm high support gap. The nominal 2 mm M2 head and 1.6 mm nut envelopes fit below the raised deck. Select accessory head/nut height and screw length against that gap and inspect actual insertion access. The U-shoe roof remains beneath the bore, so this is not an unrestricted through-stack or a qualified tool path. Covering equipment can obstruct access. Rail position is secured independently by the recessed transverse M3 fastener.",
    }


@functools.lru_cache(maxsize=1)
def _common_mount_shape():
    pieces = [mounting_plate.shape(), rail.mount_base_shape()]
    for left, right in SUPPORT_X_RANGES_MM:
        pieces.append(
            box(
                right - left,
                SUPPORT_Y_RANGE_MM[1] - SUPPORT_Y_RANGE_MM[0],
                DECK_BOTTOM_Z - rail.MOUNT_TOP_Z + 0.2,
                (left, SUPPORT_Y_RANGE_MM[0], rail.MOUNT_TOP_Z - 0.1),
            )
        )
    shape = union(pieces)
    for hole in mounting_plate.cutters(DECK_BOTTOM_Z - 0.01, DECK_THICKNESS + 0.02):
        shape = shape.cut(hole)
    shape = shape.removeSplitter()
    from .edge_blends import fillet_selected, near

    # Preserve the entire six-mm accessory corridor between X=-3 and X=3.
    # Upper outer roots spread into the deck; lower roots spread only in Y.
    shape = fillet_selected(
        shape,
        0.5,
        lambda e, b: (
            near(b.ZMin, DECK_BOTTOM_Z)
            and near(b.ZLength, 0)
            and near(e.Length, 5)
            and (
                (
                    near(b.YLength, 0)
                    and near(abs(b.YMin), 2.5)
                    and b.XMin >= -8.01
                    and b.XMax <= 8.01
                )
                or (near(b.XLength, 0) and near(abs(b.XMin), 8) and near(b.YLength, 5))
            )
        ),
        6,
        "Equipment support upper outer roots",
    )
    shape = fillet_selected(
        shape,
        0.5,
        lambda e, b: (
            near(b.ZMin, rail.MOUNT_TOP_Z)
            and near(b.ZLength, 0)
            and near(b.YLength, 0)
            and near(abs(b.YMin), 2.5)
            and near(b.XLength, 5)
            and b.XMin >= -8.01
            and b.XMax <= 8.01
        ),
        4,
        "Equipment support lower Y roots",
    )
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Common equipment mount is not one valid solid")
    return shape


def mount_shape(kind):
    """Return an independent copy of the common carrier for a supported role."""
    if kind not in MOUNT_NAMES:
        raise ValueError("Unknown equipment mount kind: " + str(kind))
    if kind == "electronics":
        from .instrument_mount import upper_shape

        return upper_shape()
    return _common_mount_shape().copy()


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
        "battery": "Universal carrier in battery role. Four declared continuous adhesive regions retain 304 mm2 clear of the centre bore and other openings. The common outer slots support separately screened optional power feet, as on the other carriers.",
        "electronics": "Universal carrier in FC role. Confirmed FC holes and 8 mm underbody wiring reservation remain; the same symmetric plate outline and spare patterns exist on every carrier.",
        "accessory": "Universal navigation carrier. P-AS uses local centre(0,+9.3); mutually exclusive GPS alternatives retain centre(0,-2.2) and their adhesive support. The Mini body is centred at (26,-17) with its long axis along carrier Y. Two continuous insulating-adhesive strips, 5 x 12 mm at (23,-12) and 4 x 15 mm at (30.5,-13.5), lie on the rail-facing face on opposite sides of the outer slot row. Each strip has complete carrier backing and nominal body overlap. This retains 120 mm2 total available contact while leaving the middle slot open. The relocated body and unchanged-size connector reserves clear the optional portal hardware registration and service bounds. The allocation is not a qualified minimum holding area. No separate radio plate, tab or pocket. Populated face and connector access face the balloon; actual envelope curvature, plug height, underside components, antenna and retention remain unverified. Remove the carrier for bench service. The outer common slots also accept the separately screened optional power platform. The optical foot can use an existing middle side slot; occupied host/side and power combinations need their composed clearance checks.",
    }
    contract = {
        "kind": kind,
        "shared_print_sku": COMMON_PRINT_SKU,
        "common_plate": common_plate_contract(),
        "centre_accessory_mount": centre_mount_contract(),
        "expansion_mounting": expansion_contract(),
        "physical_fixed_hole_centres_xy_mm": COMMON_FIXED_HOLE_CENTRES,
        "stack_interface": stack_interface.interface_contract(MOUNT_NAMES[kind]),
        "standard_mounting": mounting_slots.contract(),
        "deck_bottom_z_mm": DECK_BOTTOM_Z,
        "deck_thickness_mm": DECK_THICKNESS,
        "support_face_z_mm": SUPPORT_FACE_Z,
        "integral_side_clamped_u_shoe": True,
        "deck_underside_to_rail_web_mm": DECK_BOTTOM_Z - rail.WEB_TOP_Z,
        "future_fastener_scope": "The deck_underside_to_rail_web_mm value describes vertical planning clearance only; a chosen screw head consumes part of it. Hole/slot positions alone do not select a head, nut, spacer length, board body or wiring arrangement. Check the chosen hardware against the base, board and neighboring devices; spare slot fasteners are not installed BOM items.",
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
        "hole_interface_scope": "Four short radial slots preserve the nominal25.5mm FC axes and allow25..26mm square patterns at45deg; clamp the selected mounting stack before use. The P-AS's published two axes lie at endpoints of opposed axial slots at23mm spacing after the declared navigation shift; generic axial travel ends at26mm to preserve FC bearing support. M2 openings are2.6mm wide, a printed clearance choice rather than the OEM hole diameter. Slot seats have continuous side lands, not full circular annuli. No printed threads or device posts.",
        "unresolved_mounting_stack": "Use purchased M2 hardware and OEM FC silicone dampers. Actual PCB bearing planes, damper compression, spacer and bolt lengths remain pending; these purchased parts are not generated at invented elevations.",
        "clearance_scope": "FC 8 mm and P-AS 4 mm are design reservations below conservative component envelopes, not manufacturer mounting-height requirements. Inspect cable access, adhesive contact, clamp strength and actual fit before use. A plain plate does not establish device underside flatness, adhesion or loaded helix stiffness.",
    }

    if kind == "electronics":
        from . import instrument_mount

        contract.update(
            shared_print_sku="InstrumentCarrier",
            integral_side_clamped_u_shoe=False,
            instrument_mount=instrument_mount.mount_contract(),
            support_path_scope="The common plate is integral with a rotating lug. A separate lower U-shoe/yoke supports it on the same rail interface. FC and the fixed optical bracket share this plate and its setup-only pitch control.",
        )
        contract["common_plate"]["central_support"] = {
            "profile": "integral rotating lug with separated upper ribs",
            "scope": "Centre accessory bore remains available above the moving support; validate actual chosen screw/head/nut access against saved geometry. This upper plate has no integral rail shoe.",
        }
        contract["centre_accessory_mount"] = {
            "centre_xy_mm": (0.0, 0.0),
            "clearance_bore_diameter_mm": mounting_plate.CENTRE_HOLE_DIAMETER_MM,
            "available_as_spare_accessory_mount": True,
            "scope": "A common M2 centre bore; select accessory fasteners against the rotating support below it. No preselected mounting stack or unrestricted through-stack.",
        }
        contract.pop("deck_underside_to_rail_web_mm")
        contract["future_fastener_scope"] = (
            "Accessory hardware must clear the rotating lug, fixed yoke and rail over the entire allowed pitch range. Hole compatibility alone does not qualify a populated stack."
        )
    return contract


def build_mount(doc, parent, kind):
    if kind == "electronics":
        raise ValueError(
            "Use instrument_mount.build_mount for the two-part FC platform"
        )
    contract = mount_contract(kind)
    name = MOUNT_NAMES[kind]
    notes = (
        "Universal PA12 SLS/MJF carrier: print two identical copies for battery and navigation; the FC uses an adjustable support. "
        f"Centred66x66mm deck with {len(mounting_slots.rows())} symmetric mounting slots, including four FC slots, and one central M2 bore. "
        "One recessed transverse M3x10 screw and a nut on the opposite2mm bearing floor in an open-bottom anti-rotation recess clamp the integral U-shoe to the rail wall. "
        "The upper seat and two sides surround the rail wall; loosen the side screw to adjust within a supported rail segment. "
        f"Two short deck supports preserve the centre accessory bore, with a {DECK_BOTTOM_Z - rail.MOUNT_TOP_Z:g} mm under-deck gap; accessory head/nut height and screw-tip length must fit that space. "
        "Keep the declared adhesive regions and underside slot head paths clear. "
        "Physical clamping, adhesive retention, wiring and device stacks remain unverified."
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
