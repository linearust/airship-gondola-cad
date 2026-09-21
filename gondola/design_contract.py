"""User decisions and unresolved interfaces consumed by CAD and the CLI.

Dimensions belong to parts/*.py. This contract records decisions that geometry
alone cannot reveal. Geometric test success must never change release status.
"""

from dataclasses import asdict, dataclass

NOTION_URL = "https://app.notion.com/p/3de264c511c680d193fcd373405765c7"
NOTION_LAST_EDITED = "2026-09-20T07:25:14.031Z"
CREALLO_GUIDE_URL = "https://creallo.com/ko/guide/design-spec-guide"
DESIGN_REVISION = "O"
# User's nominal CAD length ceiling; part geometry consumes this requirement.
RAIL_LENGTH_MM = 340.0
PUBLISHED_PROCESS_SIZE_MM = {"SLS": [340, 340, 600], "MJF": [380, 380, 280]}
MANUFACTURING_DECISION = {
    "reviewed_on": "2026-09-20",
    "supplier": "Creallo",
    "material": "PA12",
    "preferred_process": "SLS",
    "alternative_process": "MJF subject to supplier agreement and fit trials",
    "nominal_rail_length_mm": RAIL_LENGTH_MM,
    "rationale": "SLS is a suitable prototype candidate; published supplier evidence does not require MJF for this design. Adopt the user's 340 mm length ceiling.",
    "supplier_process_policy": "SLS/MJF quotations are integrated; Creallo selects the process unless a specific process is separately agreed. Request SLS for the initial fit trial.",
    "size_guide_scope": "Published maximum fabrication sizes include split-and-join manufacture. They are screening bounds, not guaranteed one-piece machine capacity or acceptance.",
    "qualification": "Not qualified: obtain one-piece acceptance and review 1.2 mm functional flexures, straightness, curvature, fatigue and sliding fit. Use the same agreed process/material/finish for coupons and full parts.",
    "nominal_general_functional_wall_mm": 1.5,
    "nominal_rail_flexure_mm": 1.2,
    "flexure_exception": "The narrow 1.2 mm flexure is intentionally below the 1.5 mm general wall target; supplier review and full-length bend/fatigue testing remain mandatory. Longer 4.5 mm reliefs offset some added bending stiffness.",
    "sources": {
        "dimensions_and_tolerances": CREALLO_GUIDE_URL,
        "process_policy": "https://creallo.com/ko/blog/posts/sls-mjf-integration-update",
        "process_capability": "https://creallo.com/ko/capability/process/3DP/SLS",
        "wall_thickness": "https://creallo.com/ko/blog/posts/importance-of-thickness-in-3d-printing-processes",
    },
}


# Scoped selection from the source BOM, not measured all-up flight mass.
# Keep quantity and unit mass together; prints, hardware, wires and tape are excluded.
@dataclass(frozen=True)
class EquipmentSelection:
    model: str
    quantity: int
    listed_unit_mass_g: float


SELECTED_EQUIPMENT = (
    EquipmentSelection("MicoAir743v2 AIO35A", 1, 10.0),
    EquipmentSelection(
        "2S 450mAh LiPo (provisional; requested range 450–2000mAh)", 1, 28.4
    ),
    EquipmentSelection("Happymodel RS1102 10000KV", 2, 2.8),
    EquipmentSelection("Gemfan1610 40mm 2-blade CW/CCW", 2, 0.241),
    EquipmentSelection("DSpower DS-M005 300deg", 2, 2.0),
    EquipmentSelection("MicoAir MTF-02P", 1, 1.5),
    EquipmentSelection("LR900-A", 1, 4.0),
    EquipmentSelection("LinkTrack P-AS", 1, 3.45),
)
SCOPED_LISTED_EQUIPMENT_MASS_G = round(
    sum(item.quantity * item.listed_unit_mass_g for item in SELECTED_EQUIPMENT), 3
)
# Preserve conflicting primary evidence instead of selecting an electrical rating.
SOURCE_DISCREPANCIES = {
    "servo_case_dimensions": {
        "manufacturer_drawing_mm": [16.05, 8.3, 17.2],
        "manufacturer_product_page_mm": [16.2, 8.3, 17.4],
        "drawing_evidence": "references/ds_m005_dimensions.jpg",
        "product_url": "https://www.dspowerservo.com/ds-m005-mini-servo-product/",
        "status": "Retain the larger published case envelope. Published ear axes and underside datum are separate drawing evidence; verify dimensions on the supplied servo.",
    },
    "servo_supply_voltage": {
        "manufacturer_label_v": [3.7, 4.2],
        "manufacturer_product_page_v": [3.7, 5.0],
        "confirmed_product_url": "https://www.dspowerservo.com/ds-m005-mini-servo-product/",
        "notion_listed_v": [3.7, 5.0],
        "evidence": "references/ds_m005_voltage_label.jpg",
        "status": "verify actual servo voltage before electrical integration",
    },
    "linktrack_power": {
        "datasheet_w": 1.39,
        "notion_selection_guide_w": 1.30,
        "evidence": "references/linktrack_datasheet_v2_3_zh.pdf",
        "status": "provisional; measure selected operating mode",
    },
}

# These parts were deliberately excluded by the user, even if present in the BOM.
EXCLUDED_EQUIPMENT = (
    "yaw_motor",
    "fins",
    "fin_servos",
    "360_degree_servo_option",
)
PURCHASED_HARDWARE_QUANTITIES = {
    "M2X14_SOCKET_CAP": 4,
    "M2X8_SOCKET_CAP": 2,
    "M2X5_PA66_PAN_HEAD": 8,
    "M2_FF_PA66_AF4_L25": 4,
    "M2x6_ISO4026_DIN913": 3,
    "M2_HEX_NUT": 6,
    "M2_SQUARE_NUT_DIN562": 3,
    "M2_WASHER_2.2_5_0.3": 20,
    "M3_WASHER_3.2_9_0.8": 4,
}
HARDWARE_MATERIALS = {
    sku: "Nylon PA66"
    if sku in ("M2_FF_PA66_AF4_L25", "M2X5_PA66_PAN_HEAD")
    else "A2 stainless steel"
    for sku in PURCHASED_HARDWARE_QUANTITIES
}

EXPECTED_INVENTORY = {
    "rails": 1,
    "equipment_mounts": 2,
    "tilting_propulsors": 2,
    "installed_prints": 13,
    "optical_mount_parts": 3,
    "fit_coupons": 2,
    "purchased_hardware": sum(PURCHASED_HARDWARE_QUANTITIES.values()),
    "purchased_hardware_types": len(PURCHASED_HARDWARE_QUANTITIES),
    "unique_print_files": 11,
}

OPTICAL_STACK_HOST = "BatteryEquipmentModule"

# These are bought wiring requirements, not additional modeled hardware/mass.
# Stock pre-crimped pigtails may be joined after checking the actual pinouts.
WIRING_PURCHASE_PLAN = {
    "scope": "Three onboard UART harnesses; subtract cables already supplied with devices. Lengths and finished mass remain unmeasured.",
    "uart_harnesses": [
        {
            "connection": "FC UART1 to LR900-A UART",
            "quantity": 1,
            "fc_connector": "SH1.0-6P UART1/UART6 port",
            "device_connector": "GH1.25-4P",
        },
        {
            "connection": "FC UART3 to LinkTrack P-AS UART",
            "quantity": 1,
            "fc_connector": "SH1.0-6P UART3/I2C port",
            "device_connector": "GH1.25-4P; use one of the two parallel ports",
        },
        {
            "connection": "FC UART4 to MTF-02P UART",
            "quantity": 1,
            "fc_connector": "SH1.0-4P UART4 port",
            "device_connector": "SH1.0-4P",
        },
    ],
    "connector_ends_before_subtracting_included_cables": {
        "SH1.0-6P": 2,
        "SH1.0-4P": 2,
        "GH1.25-4P": 2,
    },
    "pinout_rule": "Family/pin count does not establish pin order, voltage or a straight-through cable. Match the official device pinouts, supply requirements and TX/RX direction. Do not use the FC's 12V DJI connector as a 5V UART supply.",
    "stock_consumables": [
        "Small nylon cable ties, strap width at most2.5mm, through existing frame windows/arms; quantity after routing. Keep heads outside moving parts and do not pull the phase-wire loop taut. No printed cable clips.",
        "Flexible pre-crimped SH/GH pigtails, insulating heat-shrink and strain relief; select wire gauge and lengths for the actual load and route.",
        "XT30-family pigtail compatible with the purchased battery; compact AMASS XT30U is the dimensional reference, not confirmation of the supplied battery connector variant.",
    ],
    "seller_or_completed_harness_verified": False,
    "stock_replacement_decision": "Use stock harness parts, fasteners, spacers, dampers, horns and cable ties. Retain the custom rail/shoe and D journal torque interface; no verified stock drop-in removes their function or yields a supported mass saving.",
}


@dataclass(frozen=True)
class ModuleStation:
    object_name: str
    x_mm: float
    clamp_control: str
    default_approach: str


MODULE_STATIONS = (
    ModuleStation("BatteryEquipmentModule", -90, "BatteryClampApproach", "NegativeY"),
    ModuleStation("MainPropulsionModule", 0, "PropulsionClampApproach", "PositiveY"),
    ModuleStation(
        "ElectronicsEquipmentModule", 90, "ElectronicsClampApproach", "PositiveY"
    ),
)


@dataclass(frozen=True)
class UnresolvedInterface:
    key: str
    required_evidence: str
    status: str = "unverified"


# Update only after obtaining the stated physical or supplier evidence.
UNRESOLVED_INTERFACES = (
    UnresolvedInterface(
        "motion_endpoints",
        "Verify actual DS-M005 travel, mechanical stops and horn clocking through bounded ±150deg motion.",
    ),
    UnresolvedInterface(
        "servo_supply_voltage",
        "Resolve manufacturer label 3.7–4.2V versus user-confirmed manufacturer product page and BOM 3.7–5V against the purchased servo before powering it.",
    ),
    UnresolvedInterface(
        "rail_flexure",
        f"Creallo acceptance of one-piece {RAIL_LENGTH_MM:g}mm rail, 1.2mm flexures, curvature and depowdering.",
    ),
    UnresolvedInterface(
        "motor_mount",
        "RS1102 drawing confirms three M1.4 holes on PCD6.6; verify actual thread engagement, rear shaft/clip envelope and selected screw length before fastening.",
    ),
    UnresolvedInterface(
        "servo_drive",
        "Measured DS-M005 28T horn connection, torque transfer to D sleeve and horn retaining fastener.",
    ),
    UnresolvedInterface(
        "servo_ear_retention",
        "DS-M005 ear hole axes and underside datum are published; verify actual case offset, ear thickness, bearing contact and M1.6 clearance-fastener length.",
    ),
    UnresolvedInterface(
        "electronic_mounting_stack",
        "FC and P-AS hole XY are confirmed. Measure PCB bearing planes, supplied FC M2x7.5 silicone sleeve geometry, purchased spacer lengths and screw engagement. Preserve at least the allocated 8mm FC underbody wiring clearance; no completed mounting stack is claimed.",
    ),
    UnresolvedInterface(
        "physical_retention",
        "Loaded tests of tape, friction clamps, PA12 flexure life and printed journals.",
    ),
    UnresolvedInterface(
        "moving_wires",
        "Actual phase-lead slack/strain relief through bounded ±150deg motion; reserved loops are not routing proof.",
    ),
    UnresolvedInterface(
        "connector_and_wire_fit",
        "Verify actual port XYZ, header variants, connector engagement/latch access, cable/heat-shrink dimensions, bend radii and pinouts. Reserved lanes and the 3mm-bundle/R5 planning exits are design allowances, not manufacturer cable requirements. Disconnect leads before device or module removal.",
    ),
    UnresolvedInterface(
        "optical_sensor_installation",
        "Manually align the independent optical stack to downward vertical at flight trim, lock both axes, then verify MTF-02P lens datums, firmware yaw/position offsets, adhesive retention, connector slack and unobstructed field. Added mass does not by itself guarantee vertical alignment or active stabilization.",
    ),
    UnresolvedInterface(
        "optical_stack_retention",
        "Verify purchased M2 PA66 spacers, both-end thread depths/engagement, printed pads, pivot friction, PA12/PA66 creep, vibration loosening and cable torque. Test both stack hosts and loaded rail/tape retention; no qualified tightening torque or stiffness is claimed.",
    ),
    UnresolvedInterface(
        "finished_mass",
        "Weigh chosen battery, prints, hardware, wiring, connectors and adhesive.",
    ),
)


def release_status():
    pending = [
        asdict(item) for item in UNRESOLVED_INTERFACES if item.status != "verified"
    ]
    return {
        "stage": "fit_prototype" if pending else "interfaces_verified",
        "production_released": not pending,
        "unresolved_interfaces": pending,
    }


def hardware_bom_scope():
    """Distinguish modeled mechanism quantities from a complete purchase list."""
    return {
        "scope": "modeled_mechanism_hardware_only",
        "complete_gondola_purchase_list": False,
        "excluded_unmodeled_requirements": [
            "FC/P-AS mounting spacers, fasteners and FC dampers: actual PCB bearing planes, compressed damper dimensions and fastener lengths remain unverified.",
            "OEM motor/servo mounting fasteners, servo horns and unfinished drive couplings.",
            "Tape, adhesive, wiring, connectors, insulation, strain relief, antennas, capacitor and other unmodeled accessories.",
        ],
        "unmodeled_wiring_purchase_plan": WIRING_PURCHASE_PLAN,
        "release_status": release_status(),
    }


def project_status():
    return {
        "design_revision": DESIGN_REVISION,
        "units": "mm",
        "printed_material": "PA12 SLS/MJF",
        "manufacturing_decision": MANUFACTURING_DECISION,
        "scope": "Indoor LTA blimp gondola including MTF-02P: one flexible rail, two tilting main propulsors, a compact battery mount and one open electronics carrier with confirmed mounting-hole patterns, sharing an interchangeable manually aligned optical stack.",
        "attachment": "Single-sided tape OVER side wings onto balloon; keep running head and flex gaps clear.",
        "battery_attachment": "Adhesive hook-and-loop on a compact continuous deck; separate structural stack pads outside the adhesive footprint; 90deg in-plane orientation. Battery centre allowance +/-5mm X, +/-4mm Y; larger trim changes require rail-carrier repositioning and a new clearance check.",
        "equipment": [asdict(item) for item in SELECTED_EQUIPMENT],
        "scoped_listed_equipment_mass_g": SCOPED_LISTED_EQUIPMENT_MASS_G,
        "source_discrepancies": SOURCE_DISCREPANCIES,
        "excluded_equipment": EXCLUDED_EQUIPMENT,
        "inventory": EXPECTED_INVENTORY,
        "wiring_purchase_plan": WIRING_PURCHASE_PLAN,
        "optical_stack_host": OPTICAL_STACK_HOST,
        "optical_stack_scope": "Common structural 40x40mm M2 interface on battery and electronics carriers; four bought 25mm PA66 spacers support a manually locked two-axis optical head. Independent of the FC soft-mount stack.",
        "module_stations": [asdict(item) for item in MODULE_STATIONS],
        "notion_source": NOTION_URL,
        "notion_last_edited": NOTION_LAST_EDITED,
        **release_status(),
    }
