"""Equipment datums and attachment reservations on the common bought carbon plate.

There are no printed equipment decks, shoes or saddles. The rail owns the two
plate clamps; optional optical/power structures are separate attachment parts.
The bought plate's unknown cutouts must never become inferred adhesive material.
"""

import math

import FreeCAD as App

from gondola.cad import box
from gondola.contracts import equipment_interfaces as interfaces
from gondola.contracts import stack_adapter as adapter_specification

from . import stock_adapter

V = App.Vector
SUPPORT_FACE_Z = stock_adapter.PLATE_TOP_Z
FC_SUPPORT_FACE_Z = SUPPORT_FACE_Z
FC_CENTRE_XY = (0.0, 0.0)
FC_ROTATION_DEG = -45.0
FC_AXIS_OFFSET = interfaces.FC_HOLE_PITCH / math.sqrt(2)
FC_HOLE_CENTRES = adapter_specification.COMMON_HOLE_CENTRES
NAVIGATION_CENTRE_XY = (24.0, 0.0)
RADIO_CENTRE_XY = (-22.0, 0.0)
PAS_HOLE_CENTRES = interfaces.PAS_HOLE_CENTRES
MOUNT_NAMES = {
    "battery": "StockBatteryAdapter",
    "electronics": "StockFCAdapter",
    "accessory": "StockNavigationAdapter",
}
RADIO_MOUNT_NAME = "StockRadioAdapter"
GPS_ADHESIVE_SIZE = (18.0, 24.0)
RADIO_ADHESIVE_SIZE = (14.0, 22.0)
BATTERY_ADHESIVE_REGIONS = (((0.0, 0.0), (18.0, 24.0)),)
FC_WIRING_CLEARANCE = 8.0
FC_WIRING_CORRIDOR_WIDTH = 8.0
FC_WIRING_CORRIDOR_CENTRE_Y = 0.0
FC_WIRING_CORRIDOR_ROTATION_DEG = 45.0
PAS_SERVICE_CLEARANCE = 0.0
INSULATING_PAD_ALLOWANCE = 3.0
ADHESIVE_ALLOWANCE = INSULATING_PAD_ALLOWANCE
BATTERY_PLACEMENT_CONTRACT = {
    "centre_x_limit_mm": 1.0,
    "centre_y_limit_mm": 1.0,
    "maximum_size_mm": [66, 18, 17],
    "minimum_stack_tower_gap_mm": 1.5,
    "frame": "Battery carbon XY; pack long axis along Y, nominal3mm insulating pad allowance",
    "qualification": "Single bought carbon support; the long pack overhangs it. The18x24mm insulating-pad rectangle is a placement reservation, not verified continuous carbon contact. Check received cutouts, pack support, strap retention, bending and any optional portal. Do not treat the pad or plate as a qualified battery tray.",
}


def _check_kind(kind):
    if kind not in MOUNT_NAMES:
        raise ValueError("Unknown equipment mounting region: " + str(kind))


def support_face_z(kind):
    _check_kind(kind)
    return SUPPORT_FACE_Z


def mount_hole_centres(kind):
    """Selected device-fastening axes; P-AS currently uses insulation and strap."""
    _check_kind(kind)
    return FC_HOLE_CENTRES if kind == "electronics" else ()


def plate_hole_rows(kind):
    """All published nominal carbon bores, without invented bearing annuli."""
    _check_kind(kind)
    return [
        {
            "plate": row["name"],
            "centre_xy_mm": (row["centre_xy_mm"][0] + x, row["centre_xy_mm"][1] + y),
            "diameter_mm": adapter_specification.HOLE_DIAMETER_MM,
            "square_pitch_mm": pitch,
            "rotation_deg": adapter_specification.COMMON_ROTATION_DEG,
            "scope": "Nominal bought through-hole; no guaranteed fit, contact land or simultaneous hardware use",
        }
        for row in stock_adapter.plate_instances(kind)
        for pitch in adapter_specification.SQUARE_PITCHES_MM
        for x, y in adapter_specification.hole_centres(
            pitch, adapter_specification.COMMON_ROTATION_DEG
        )
    ]


def fc_wiring_reserve_shape():
    """Central diagonal planning strip avoids cardinal plate-clamp/stud axes."""
    shape = box(
        interfaces.FC_SIZE_MM[0],
        FC_WIRING_CORRIDOR_WIDTH,
        FC_WIRING_CLEARANCE,
        (
            -interfaces.FC_SIZE_MM[0] / 2,
            -FC_WIRING_CORRIDOR_WIDTH / 2,
            FC_SUPPORT_FACE_Z,
        ),
    )
    shape.rotate(V(), V(0, 0, 1), FC_WIRING_CORRIDOR_ROTATION_DEG)
    return shape


def adhesive_reservations(kind):
    _check_kind(kind)
    if kind == "electronics":
        return []
    if kind == "battery":
        return [
            {
                "device": "battery",
                "plate": MOUNT_NAMES[kind],
                "centre_xy_mm": centre,
                "size_mm": size,
            }
            for centre, size in BATTERY_ADHESIVE_REGIONS
        ]
    return [
        {
            "device": "selected navigation module",
            "plate": MOUNT_NAMES[kind],
            "centre_xy_mm": NAVIGATION_CENTRE_XY,
            "size_mm": GPS_ADHESIVE_SIZE,
        },
        {
            "device": "LR24-F-Mini",
            "plate": RADIO_MOUNT_NAME,
            "centre_xy_mm": RADIO_CENTRE_XY,
            "size_mm": RADIO_ADHESIVE_SIZE,
        },
    ]


def mount_contract(kind):
    _check_kind(kind)
    return {
        "kind": kind,
        "purchased_plates": stock_adapter.plate_instances(kind),
        "printed_equipment_carrier": False,
        "common_part_sku": adapter_specification.PART_SKU,
        "plate_bottom_z_mm": stock_adapter.PLATE_BOTTOM_Z,
        "plate_thickness_mm": adapter_specification.THICKNESS_MM,
        "support_face_z_mm": SUPPORT_FACE_Z,
        "plate_holes": plate_hole_rows(kind),
        "rail_attachment": "Two opposed16mm Y axes per rotated45-degree carbon board, with downward M2x6 screws and the rail's ordinary hex-nut guides. Rail owns these clamps; there is no separate shoe, saddle or side clamp.",
        "device_fastening_axes_xy_mm": mount_hole_centres(kind),
        "fc_wiring_clearance_mm": FC_WIRING_CLEARANCE,
        "fc_underbody_corridor": {
            "width_mm": FC_WIRING_CORRIDOR_WIDTH,
            "centre_y_mm": FC_WIRING_CORRIDOR_CENTRE_Y,
            "rotation_deg": FC_WIRING_CORRIDOR_ROTATION_DEG,
            "scope": "Planning allowance only; actual connectors, wiring and insulating/damping stack remain unmeasured.",
        },
        "insulating_pad_reservations": adhesive_reservations(kind),
        "insulating_pad_nominal_thickness_mm": INSULATING_PAD_ALLOWANCE,
        "insulating_pad_compressed_limit": "Keep the device underside at least0.5mm above the measured rail-clamp head height. The modeled2mm heads require at least2.5mm compressed separation from carbon; the nominal3mm pad is an allocation, not proof of foam compression, retention, strength or electrical insulation.",
        "continuous_adhesive_contact_verified": False,
        "contact_scope": "Pad rectangles reserve device/insulation positions only. The filled square carbon model cannot prove contact area through the unknown central hole, cutouts and waist. Verify actual bonded/strapped contact, board insulation, rocking and loaded retention.",
        "navigation_attachment": "Baseline P-AS/GPS attachment uses insulating adhesive/strap. P-AS has two confirmed23mm-spaced holes, not an exact match to the stock16mm diagonal22.627mm or20/25.5mm square patterns. No new carbon or PA12 mounting holes are invented; any small-screw alignment requires a separate measured fit review.",
        "battery_attachment": BATTERY_PLACEMENT_CONTRACT,
        "fc_attachment": "Four independent25.5mm M2x20 shaft bolts/intermediate nuts on carbon. Keep the FC's lowest component envelope8mm above carbon using separately qualified insulation and dampers; no PCB or silicone compression serves as the rigid carbon-to-rail clamp stop.",
        "optional_structure": "An optical or power portal can use selected25.5mm carbon axes. Its feet, hardware and load checks belong to that option; these boards remain bought parts, never printed carrier variants.",
        "service": "Remove the FC or taped/strapped device before accessing covered plate-clamp heads from above. Keep nuts engaged during bounded fine trim. Coarse relocation across an interrupted rail bay requires lifting/reinstalling the plate; no uninterrupted sliding or captive unbolted nut is claimed.",
        "mounting_fit_verified": False,
    }


def build_mount(doc, parent, kind):
    """Build the bought plate collection and return its primary device plate."""
    result = stock_adapter.build_stock_adapter(doc, parent, kind=kind)
    return next(obj for obj in result["plates"] if obj.Name == MOUNT_NAMES[kind])
