"""User decisions and unresolved interfaces consumed by CAD and the CLI.

Dimensions belong to parts/*.py. This contract records decisions that geometry
alone cannot reveal. Geometric test success must never change release status.
"""

from dataclasses import asdict, dataclass

NOTION_URL = "https://app.notion.com/p/3de264c511c680d193fcd373405765c7"
NOTION_LAST_EDITED = "2026-09-20T07:25:14.031Z"
CREALLO_GUIDE_URL = "https://creallo.com/ko/guide/design-spec-guide"
DESIGN_REVISION = "J"
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
    "qualification": "Not qualified: obtain one-piece acceptance and review 1 mm functional flexures, straightness, curvature, fatigue and sliding fit. Use the same agreed process/material/finish for coupons and full parts.",
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
    EquipmentSelection("LR900-A", 1, 4.0),
    EquipmentSelection("LinkTrack P-AS", 1, 3.45),
)
SCOPED_LISTED_EQUIPMENT_MASS_G = round(
    sum(item.quantity * item.listed_unit_mass_g for item in SELECTED_EQUIPMENT), 3
)
# Preserve conflicting primary evidence instead of selecting an electrical rating.
SOURCE_DISCREPANCIES = {
    "servo_supply_voltage": {
        "manufacturer_label_v": [3.7, 4.2],
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
    "MTF_02P_underside_sensor",
    "360_degree_servo_option",
)
EXPECTED_INVENTORY = {
    "rails": 1,
    "identical_boards": 3,
    "tilting_propulsors": 2,
    "installed_prints": 11,
    "fit_coupons": 2,
    "purchased_hardware": 42,
    "purchased_hardware_types": 6,
    "unique_print_files": 7,
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
        "Resolve manufacturer label 3.7–4.2V versus BOM 3.7–5V against the purchased servo before powering it.",
    ),
    UnresolvedInterface(
        "rail_flexure",
        f"Creallo acceptance of one-piece {RAIL_LENGTH_MM:g}mm rail, 1mm flexures, curvature and depowdering.",
    ),
    UnresolvedInterface(
        "motor_mount",
        "Actual RS1102 screw diameter/pitch, mounting pattern and safe thread engagement.",
    ),
    UnresolvedInterface(
        "servo_drive",
        "Measured DS-M005 28T horn connection, torque transfer to D sleeve and horn retaining fastener.",
    ),
    UnresolvedInterface(
        "servo_ear_retention", "Actual servo ear fit and metric retaining fasteners."
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


def project_status():
    return {
        "design_revision": DESIGN_REVISION,
        "units": "mm",
        "printed_material": "PA12 SLS/MJF",
        "manufacturing_decision": MANUFACTURING_DECISION,
        "scope": "Gondola only: one flexible rail, two tilting main propulsors, interchangeable stackable equipment boards.",
        "attachment": "Single-sided tape OVER side wings onto balloon; keep running head and flex gaps clear.",
        "battery_attachment": "Adhesive hook-and-loop on generic board; no strap slots;90deg in-plane orientation.",
        "equipment": [asdict(item) for item in SELECTED_EQUIPMENT],
        "scoped_listed_equipment_mass_g": SCOPED_LISTED_EQUIPMENT_MASS_G,
        "source_discrepancies": SOURCE_DISCREPANCIES,
        "excluded_equipment": EXCLUDED_EQUIPMENT,
        "inventory": EXPECTED_INVENTORY,
        "module_stations": [asdict(item) for item in MODULE_STATIONS],
        "notion_source": NOTION_URL,
        "notion_last_edited": NOTION_LAST_EDITED,
        **release_status(),
    }
