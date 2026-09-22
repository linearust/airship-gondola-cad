"""User decisions and unresolved interfaces consumed by CAD and the CLI.

Part geometry belongs to gondola/parts; published interface dimensions belong to
the other contract modules. Geometric test success never changes release status.
"""

from dataclasses import asdict, dataclass

from .drive import SELECTED_DRIVE
from .equipment_interfaces import X06_DATASHEET_SOURCE, X06_MANUFACTURER_SOURCE

NOTION_URL = "https://app.notion.com/p/3de264c511c680d193fcd373405765c7"
NOTION_LAST_EDITED = "2026-09-20T07:25:14.031Z"
CREALLO_GUIDE_URL = "https://creallo.com/ko/guide/design-spec-guide"
DESIGN_REVISION = "U"
# User's nominal CAD length ceiling; part geometry consumes this requirement.
RAIL_LENGTH_MM = 340.0
# Project structural interface, independent of the FC mounting-hole pattern.
STACK_PITCH_MM = 44.0
STACK_HOLE_CENTRES = tuple(
    (sign * STACK_PITCH_MM / 2, sign * STACK_PITCH_MM / 2) for sign in (-1, 1)
)
STACK_AXIS_LOCATIONS = (
    " and ".join(f"({x:g}, {y:g})" for x, y in STACK_HOLE_CENTRES) + " mm"
)
PUBLISHED_PROCESS_SIZE_MM = {"SLS": [340, 340, 600], "MJF": [380, 380, 280]}
MANUFACTURING_DECISION = {
    "reviewed_on": "2026-09-20",
    "supplier": "Creallo",
    "material": "PA12; final process/material agreement pending",
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
# None means unmeasured, not zero. Prints, hardware, wires and tape are excluded.
@dataclass(frozen=True)
class EquipmentSelection:
    model: str
    quantity: int
    listed_unit_mass_g: float | None


SELECTED_EQUIPMENT = (
    EquipmentSelection("MicoAir743v2 AIO35A", 1, 10.0),
    EquipmentSelection("Tattu 2S 450mAh 75C XT30 long pack", 1, None),
    EquipmentSelection("Happymodel RS1102 10000KV", 2, 2.8),
    EquipmentSelection("Gemfan1610 40mm 2-blade CW/CCW", 2, 0.241),
    EquipmentSelection("KST X06 V6.0 regular mounting tabs", 2, 6.0),
    EquipmentSelection("MicoAir MTF-02P", 1, 1.5),
    EquipmentSelection("LR900-A", 1, None),
    EquipmentSelection("LinkTrack P-AS", 1, 3.45),
)
SCOPED_LISTED_EQUIPMENT_MASS_G = round(
    sum(
        item.quantity * item.listed_unit_mass_g
        for item in SELECTED_EQUIPMENT
        if item.listed_unit_mass_g is not None
    ),
    3,
)
# Preserve conflicting primary evidence; do not silently tighten supplier tolerance.
SOURCE_DISCREPANCIES = {
    "servo_case_tolerance": {
        "manufacturer_drawing_plus_minus_mm": 0.2,
        "manufacturer_product_page_plus_minus_mm": 0.1,
        "drawing_evidence": "references/kst_x06_v6_datasheet.pdf",
        "sources": [X06_DATASHEET_SOURCE, X06_MANUFACTURER_SOURCE],
        "status": "Use the May 2023 X06 V6.0 drawing's larger case tolerance; verify the supplied servo before manufacturing its fitted support.",
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
)
PURCHASED_HARDWARE_QUANTITIES = {
    "M2X8_SOCKET_CAP": 10,
    "M1_6X8_CHEESE_HEAD": 4,
    "M1_6_HEX_NUT_DIN934": 4,
    "M2X5_PA66_PAN_HEAD": 6,
    "M2_FF_PA66_AF4_L25": 2,
    "M2x6_ISO4026_DIN913": 3,
    "M2_SQUARE_NUT_DIN562": 15,
    SELECTED_DRIVE.driver.sku: 2,
    SELECTED_DRIVE.output.sku: 2,
    "MR63ZZ": 4,
    "PSFU3-24-FC5-A3": 2,
    "PSFU3-14": 2,
    "KST_0415_13": 2,
}

HARDWARE_MATERIALS = {
    sku: (
        "Nylon PA66"
        if sku in ("M2_FF_PA66_AF4_L25", "M2X5_PA66_PAN_HEAD")
        else "POM"
        if sku.startswith("GEABP")
        else "SUJ2-equivalent hard-chrome steel"
        if sku.startswith("PSFU")
        else "Bearing steel"
        if sku == "MR63ZZ"
        else "Aluminium alloy (grade unspecified)"
        if sku == "KST_0415_13"
        else "A2 stainless steel"
    )
    for sku in PURCHASED_HARDWARE_QUANTITIES
}

EXPECTED_INVENTORY = {
    "rails": 1,
    "equipment_mounts": 2,
    "tilting_propulsors": 2,
    "installed_prints": 17,
    "optical_mount_parts": 3,
    "fit_coupons": 4,
    "purchased_hardware": sum(PURCHASED_HARDWARE_QUANTITIES.values()),
    "purchased_hardware_types": len(PURCHASED_HARDWARE_QUANTITIES),
    "unique_print_files": 14,
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
    "stock_replacement_decision": "Use stock harness parts, fasteners, spacers, dampers, KST 0415.13 horns, gears, shafts, bearings and cable ties. Print the rail, carriers, supports and direct horn-to-gear adapters. Retain the bought horn spline and original retaining screw; qualify the adapter fit and clamping with actual parts.",
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
        f"Calibrate each X06 around nominal ±{180 / SELECTED_DRIVE.ratio:g}deg servo motion for the {SELECTED_DRIVE.driver.teeth}T-to-{SELECTED_DRIVE.output.teeth}T speed-increasing pair's opposite-sign ±180deg output target. Verify loaded travel and gear/horn clocking; small travel shortfall is acceptable, with no extra commanded travel margin required. Endpoints must be measured separately; programming cannot overcome a mechanical stop or inadequate torque. Never wrap endpoints or command continuous rotation.",
    ),
    UnresolvedInterface(
        "servo_power_and_load",
        f"Verify the selected X06 supply and PWM configuration, gear side load and measured output torque. The {SELECTED_DRIVE.ratio:g}:1 angle increase divides ideal output torque by {SELECTED_DRIVE.ratio:g} before losses; the direct gear transmits its mesh force to the servo output support, whose external radial-load capacity is unpublished.",
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
        "Verify the selected KST 0415.13 horn's seating and original X06 retaining screw, printed horn-adapter fit, concentric 7mm gear-bore seating and gear retention on the printed spigot. The horn's published spline class and blade dimensions support the nominal torque path, not proven installed fit, backlash or retention. The direct driver loads the servo output bearings; no external radial-load rating is published. Check loaded deflection, backlash and both-direction retention.",
    ),
    UnresolvedInterface(
        "servo_ear_retention",
        "X06 drawing publishes two diameter 2 mm ear holes at 24 mm pitch and ear surfaces 3.7/4.7 mm below the case top. Verify actual ear contact, case tolerance, selected mounting screws and engagement before fastening.",
    ),
    UnresolvedInterface(
        "gear_mesh_and_shaft_retention",
        f"Check the purchased {SELECTED_DRIVE.driver.teeth}T/{SELECTED_DRIVE.output.teeth}T POM pair at nominal {SELECTED_DRIVE.center_distance_mm:g} mm centre distance, backlash, centre alignment, set-screw retention and PA12 creep. Use the matching integral propulsion frame for the selected gear pair; changing ratio requires replacement driver gears and the complete frame, followed by a complete rebuild and validation. No cartridge mount or mesh-adjustment slot remains; servo ear clearance, printed-position error and PA12 creep still affect the mesh. Measure centre distance and backlash with the actual parts before operation. If fit is unsuitable, correct and reprint the frame; do not elongate its holes or force the mesh. Qualify MR63ZZ shaft/housing fits, inner-ring-only abutments, axial retention and preload. PSFU3 h5 is not guaranteed to slip into every bearing; a straight shaft has no inherent axial retainer.",
    ),
    UnresolvedInterface(
        "electronic_mounting_stack",
        "FC and P-AS hole XY are confirmed. Measure PCB bearing planes, supplied FC M2x7.5 silicone sleeve geometry, purchased spacer lengths and screw engagement. Preserve at least the allocated 8mm FC underbody wiring clearance; no completed mounting stack is claimed.",
    ),
    UnresolvedInterface(
        "physical_retention",
        "Loaded tests of tape, friction clamps, PA12 flexure life and bearing supports.",
    ),
    UnresolvedInterface(
        "moving_wires",
        "Actual phase-lead slack/strain relief through bounded ±180deg output motion; reserved loops are not routing proof and endpoints must not wrap.",
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
        "Weigh the selected Tattu battery, onboard LR900-A, prints, drive hardware, wiring, connectors and adhesive. Unknown battery/radio masses are excluded from the known equipment subtotal, not assigned zero mass.",
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
            "RS1102 motor mounting screws and OEM X06 horn-retaining screws: lengths, heads and actual engagement remain unverified. Selected stock horns and modeled adapter hardware are included.",
            "Tape, adhesive, wiring, connectors, insulation, strain relief, antennas, capacitor and other unmodeled accessories.",
        ],
        "unmodeled_wiring_purchase_plan": WIRING_PURCHASE_PLAN,
        "release_status": release_status(),
    }


def project_status():
    return {
        "design_revision": DESIGN_REVISION,
        "units": "mm",
        "printed_material": "PA12; SLS preferred for fit trial, supplier process agreement pending",
        "manufacturing_decision": MANUFACTURING_DECISION,
        "structural_design_basis": "Ultralight indoor LTA gondola; lower stiffness than a sub-250g multirotor is accepted. Prefer integral printable carriers and fixed replacement parts over tolerance-adjustment mechanisms. Retain separable parts for assembly/service and purposeful rail/optical alignment. Minimize hardware and unsupported strength claims; physical retention remains unverified.",
        "scope": f"Indoor LTA blimp gondola including MTF-02P: one flexible rail, two independently geared X06 main propulsors with bounded ±180deg output targets, a compact battery mount and one open electronics carrier, sharing an interchangeable manually aligned optical stack. Each purchased {SELECTED_DRIVE.driver.teeth}T driver turns a {SELECTED_DRIVE.output.teeth}T output gear; no yaw motor or fin hardware is included.",
        "selected_drive": SELECTED_DRIVE.contract(),
        "attachment": "Single-sided tape OVER side wings onto balloon; keep running head and flex gaps clear.",
        "battery_attachment": "Adhesive hook-and-loop on a compact continuous deck; separate structural stack pads outside the adhesive footprint; 90deg in-plane orientation. Battery centre allowance +/-5mm X, +/-4mm Y; larger trim changes require rail-carrier repositioning and a new clearance check.",
        "equipment": [asdict(item) for item in SELECTED_EQUIPMENT],
        "scoped_listed_equipment_mass_g": SCOPED_LISTED_EQUIPMENT_MASS_G,
        "equipment_mass_scope": "Known listed device masses only; battery and radio are unmeasured. Excludes printed parts, drive hardware, wiring and other accessories; not an all-up mass or complete equipment subtotal.",
        "source_discrepancies": SOURCE_DISCREPANCIES,
        "excluded_equipment": EXCLUDED_EQUIPMENT,
        "inventory": EXPECTED_INVENTORY,
        "wiring_purchase_plan": WIRING_PURCHASE_PLAN,
        "optical_stack_host": OPTICAL_STACK_HOST,
        "optical_stack_scope": f"Common structural two-axis diagonal M2 interface at {STACK_AXIS_LOCATIONS} on battery and electronics carriers; two bought 25mm PA66 spacers support a manually locked two-axis optical head. Independent of the FC soft-mount stack.",
        "module_stations": [asdict(item) for item in MODULE_STATIONS],
        "notion_source": NOTION_URL,
        "notion_last_edited": NOTION_LAST_EDITED,
        **release_status(),
    }
