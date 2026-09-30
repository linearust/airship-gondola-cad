"""User decisions and unresolved interfaces consumed by CAD and the CLI.

Part geometry belongs to gondola/parts; published interface dimensions belong to
the other contract modules. Geometric test success never changes release status.
"""

import math
from collections import Counter
from dataclasses import asdict, dataclass

from .drive import SELECTED_DRIVE
from .equipment_interfaces import (
    FC_ELECTRICAL_EVIDENCE,
    FC_LISTED_MASS_G,
    FC_MODEL,
    X06_DATASHEET_SOURCE,
    X06_MANUFACTURER_SOURCE,
    flight_controller_contract,
)
from .equipment_options import get_navigation_profile, get_radio_profile
from .fasteners import KIT_MATERIAL
from .optical_sensors import get_sensor_profile
from .power_options import power_option_contract
from .servo_horns import SELECTED_BY_SIDE
from .servo_horns import profile as horn_profile

CREALLO_GUIDE_URL = "https://creallo.com/ko/guide/design-spec-guide"
DESIGN_REVISION = "BN"
# Nominal local part dimensions, before print rotation; not delivered-size tolerance.
MAX_PRINT_PART_DIMENSION_MM = 340.0
# Chosen assembly length is independent of the supplier-screening size limit.
RAIL_LENGTH_MM = 300.0
# User's 2026-09-29 manufacturing review requires at least this nominal rail
# attachment thickness; actual delivered dimensions/curvature remain unmeasured.
RAIL_BASE_THICKNESS_MM = 1.5
# Project structural interface, independent of the FC mounting-hole pattern.
STACK_PITCH_MM = 45.0
STACK_ANCHOR_CENTRES = tuple(
    (sign * STACK_PITCH_MM / 2, sign * STACK_PITCH_MM / 2) for sign in (-1, 1)
)
STACK_ANCHOR_LOCATIONS = (
    " and ".join(f"({x:g}, {y:g})" for x, y in STACK_ANCHOR_CENTRES) + " mm"
)
PUBLISHED_PROCESS_SIZE_MM = {"SLS": [340, 340, 600], "MJF": [380, 380, 280]}
MANUFACTURING_DECISION = {
    "reviewed_on": "2026-09-30",
    "supplier": "Creallo",
    "material": "Unfilled PA12 design basis; supplier grade/process/finish agreement pending. Do not substitute fibre-filled grades without redesign and renewed flexure qualification.",
    "preferred_process": None,
    "candidate_processes": ["SLS", "MJF"],
    "maximum_nominal_part_dimension_mm": MAX_PRINT_PART_DIMENSION_MM,
    "part_size_rule": f"Each local part bounding-box dimension before print rotation and each oriented export dimension must be at most {MAX_PRINT_PART_DIMENSION_MM:g} mm. Apply to every installed print and coupon; additionally screen oriented exports against both published process envelopes. This nominal CAD limit is not a guarantee of delivered dimensions.",
    "nominal_rail_length_mm": RAIL_LENGTH_MM,
    "rationale": "PA12 is Creallo's documented functional powder-bed nylon and suits open integral supports and the rail flexure trial. Neither SLS nor MJF is established as superior for this assembly; choose with the supplier using fit, stiffness, straightness and mass requirements. A material/process change requires renewed fit and flexure qualification.",
    "supplier_process_policy": "Creallo integrates SLS/MJF quotations and selects the process unless separately agreed. No process is preselected here. Confirm the actual PA12 grade, process and finish before printing matched coupons and full parts.",
    "size_guide_scope": "Published maximum fabrication sizes include split-and-join manufacture. They are screening bounds, not guaranteed one-piece machine capacity or acceptance.",
    "qualification": "Not qualified: obtain one-piece acceptance and review rail flexures, straightness, curvature, fatigue and seated mounting fit. Use the same agreed unfilled PA12 process/material/finish and corresponding feature orientation for coupons and full parts. Verify the optical carrier foot and pitch seat for flatness, pointing stability and creep with actual fasteners.",
    "nominal_general_functional_wall_mm": 1.5,
    "nominal_rail_flexure_mm": RAIL_BASE_THICKNESS_MM,
    "flexure_exception": "The rail base and tape wings use the user-reported manufacturing-review minimum of 1.5 mm nominal. The narrow base remains a functional flexure, not a generic broad plate; actual thickness, full-length curvature, tape retention and fatigue remain unqualified. Gaps between slotted walls permit bending without thinning the base:6mm beside the longer central wall and12mm elsewhere. The reinforced centre preserves the broad propulsion support and FC wiring distance. This does not establish whole-rail stiffness or a qualified bend radius.",
    "dfam_basis": "Prefer simple integral load-bearing sections and accessible through-features. Retain openings for assembly, wiring or motion; omit lightening windows that leave fragile narrow ligaments for negligible system-level benefit. SLS/MJF powder supports overhangs; do not introduce splits solely from FDM/SLA support-angle rules. Keep powder-removal access to holes and pockets. Do not add lattice infill or sealed hollow regions; avoid extra fine struts and trapped powder.",
    "sources": {
        "dimensions_and_tolerances": CREALLO_GUIDE_URL,
        "process_policy": "https://creallo.com/ko/blog/posts/sls-mjf-integration-update",
        "process_capability": "https://creallo.com/ko/capability/process/3DP/SLS",
        "pa12_material": "https://creallo.com/ko/capability/material/SLS/SLSPA12",
        "design_guide": "https://creallo.com/ko/guide/3d-printing-design-guide",
        "lattice_and_powder_removal": "https://creallo.com/ko/guide/lattice-structure-3d-printing-dfam",
    },
}

# Retained splits have assembly, motion or requested replacement functions.
# Reconsider these reasons when redesigning; this is not a fixed part-count target.
PART_SEPARATION_REASONS = {
    "fc_and_accessory_carriers": "Three identical square carriers have one flat L support and an accessible transverse M2 pair. Retain standard device slots, a usable central mounting hole, FC underbody wiring space, interchangeable navigation and the optical head. Side access permits rail adjustment without removing the carried device. Actual fastener contact, adhesion and retention need physical checks.",
    "rail_and_carriers": "One flexible rail has three paired tape wings and slotted vertical wall segments. Thin underside adhesive distributes local loads; optional over-wing tape reinforces attachment. Each integral L mount seats on the wall top and against one side; an exposed M2x8 screw/nut pair clamps broad surfaces without bending opposed ears. Loosen to trim continuously within one supported slot; remove the bolt before moving between segments or lifting the loaded module. Slot limits keep the complete contact foot on a wall. No printed threads, T undercuts, captive pockets or operating looseness. Keep the1.5mm base and qualify actual curved support, friction, creep and adhesion.",
    "servo_bridge_and_frame": "Both servos and complete input drives leave as one bench-service module after removing the two small output gears and two M2 mount pairs. Output shafts, captured bearings and motor carriers stay installed. Both servo windows share one thick central upright, directly supported through the central bridge plate by the frame's broad central seat. Two broad straight arms join its outer mounting feet while unused side regions remain open. Both outboard seats and the central seat share one Z plane; the bridge underside is flat across these contacts. Unilateral X/Y datums locate it, and two existing M2x8 pairs clamp its plain 2 mm plate without head counterbores. Check the common seating plane for flatness; do not pull a warped part into contact with its screws.",
    "bearings_and_frame": "Retain the four purchased generic 3x6x2.5 bearings for this iteration. Each rotor has two bearings at 70 mm centre spacing and 10 mm shaft grips; driven/idler rods remain 34/20 mm. A fixed round seat and integral rear shoulder locate each bearing; one identical removable front keeper per bearing uses one M2x6 screw and ordinary M2 nut. Broad pocket guides prevent keeper rotation. Tighten the keeper against its frame seat, not the bearing; no radial clamp or bearing preload is intended. The nominal diameter6.1 seat has a continuous bore across the full bearing width and requires process-matched coupon fit/finishing; reject radial rocking. The diameter5.6 keeper opening and0.5mm inward float require actual outer-ring/shield and axial-fit checks. Keeper fronts preserve the separate nominal +/-0.5mm carrier stops. Remove the carrier and shafts before bearing service; no latch deflection or two-blade release is required. No bought bearing spacers, push-on rings or replacement bearings. This is not a multiple-size housing; two bearings do not eliminate overhang bending or fit sensitivity.",
    "motor_carriers_and_frame": "Independent powered rotation; each carrier integrates the motor plate, guard, struts and shaft clamps. The selected carrier remains for 40 mm propellers, with a 50 mm outside / 46 mm inside guard. A separately checked symmetric replacement-rotor space allowance supports planning for a future 50 mm propeller carrier; it does not establish unknown motor, propeller, mounting, wiring or thrust compatibility. Replace the carrier rather than fitting a 50 mm blade into the present guard.",
    "horn_and_adapter": "One rounded, tapered adapter follows the selected manufacturer X06 stock plastic half arm 1 on both sides, retaining the root and nut-bearing lands. Preserve the supplied STEP geometry and factory hole axes; enlarge only the existing diameter-1mm holes at radii6.8/13.2mm to1.5mm for rear M1.4x8 screws and front M1.4 nuts. A near diameter1.8mm round hole limits translation; a far1.8x2.4mm radial slot accommodates hole-pitch error without leaving both joints free along the arm. The nominal diameter7mm root uses an open diameter7.3mm seat; its0.15mm radial clearance is assembly allowance, not certified concentricity. Keep the purchased spline, OEM centre retaining screw, full shaft-stop floor, gear/stub planes and ordered removal. Tighten both joints before operation. Resin, mass, actual seating, runout, clamping and reversing-load strength remain unmeasured.",
    "optical_head": "Two prints provide one lockable manual pitch-Y axis. A small rectangular foot and straight pitch post attach to an existing universal carrier side slot with an integral locating tongue and one M2 pair; one more pair clamps pitch. The tongue limits assembly yaw without extending below the deck; the screw locks the seated foot. It does not self-level or remove the need to align before tightening. No dedicated optical rail shoe or additional universal carrier is needed. Use the checked host/edge configurations and validate complete sensor, service and power clearances after relocation. Rail centring does not correct roll or actively level the sensor. Qualify foot seating, pointing retention and PA12 creep.",
}


# Scoped selection from the source BOM, not measured all-up flight mass.
# None means unmeasured, not zero. Prints, hardware, wires and tape are excluded.
@dataclass(frozen=True)
class EquipmentSelection:
    model: str
    quantity: int
    listed_unit_mass_g: float | None


def equipment_selection(navigation_key=None, radio_key=None, sensor_key=None):
    """Count one device per region and a selected external antenna once."""
    navigation = get_navigation_profile(navigation_key)
    radio = get_radio_profile(radio_key)
    sensor = get_sensor_profile(sensor_key)
    equipment = (
        EquipmentSelection(FC_MODEL, 1, FC_LISTED_MASS_G),
        EquipmentSelection("Tattu 2S 450mAh 75C XT30 long pack", 1, None),
        EquipmentSelection("Happymodel RS1102 10000KV", 2, 2.8),
        EquipmentSelection("Gemfan1610 40mm 2-blade CW/CCW", 2, 0.241),
        EquipmentSelection("KST X06 V6.0 regular mounting tabs", 2, 6.0),
        EquipmentSelection("MicoAir " + sensor.model, 1, sensor.mass_g),
        EquipmentSelection(radio.model, 1, radio.mass_g),
        EquipmentSelection(navigation.model, 1, navigation.mass_g),
    )
    if navigation.external_antenna:
        antenna = navigation.external_antenna
        equipment += (EquipmentSelection(antenna.model, 1, antenna.mass_g),)
    return equipment


SELECTED_EQUIPMENT = equipment_selection()
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
    "fc_input_power": {
        "input_claims": FC_ELECTRICAL_EVIDENCE["input_claims"],
        "selected_battery_cells": 2,
        "compatibility_status": FC_ELECTRICAL_EVIDENCE["compatibility_status"],
        "selected_input_confirmation": FC_ELECTRICAL_EVIDENCE[
            "selected_input_confirmation"
        ],
        "status": "Historical official 45A sources conflict on 2S support. The user confirmed the selected board supports 2S on 2026-09-29; retain the existing battery. The exact hardware revision, minimum voltage and suspected recent model change are not established. Installed loads and firmware still require checks.",
    },
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
    "servo Y harness (separate user project)",
)


def _selected_horn_hardware():
    quantities = Counter()
    for side in SELECTED_BY_SIDE:
        selected = horn_profile(side=side)
        quantities[selected.sku] += 1
        quantities[selected.screw_sku] += 2
        if not selected.threaded:
            quantities["M1_4_HEX_NUT_DIN934"] += 2
    return dict(quantities)


PURCHASED_HARDWARE_QUANTITIES = {
    "M2X8_BUTTON_HEAD": 12,
    "M2X6_BUTTON_HEAD": 6,
    "M2_HEX_NUT": 18,
    "M1_6X8_PAN_HEAD_KIT": 4,
    "M1_6_HEX_NUT_DIN934": 4,
    SELECTED_DRIVE.driver.sku: 2,
    SELECTED_DRIVE.output.sku: 2,
    "BEARING_3X6X2_5": 4,
    "SS304_CUT3_L34_FLAT5_A0": 2,
    "SS304_CUT3_L20": 2,
    "SS304_CUT3_L18_FLAT18_A0": 2,
    **_selected_horn_hardware(),
}

HARDWARE_MATERIALS = {
    "M2X8_BUTTON_HEAD": KIT_MATERIAL,
    "M2X6_BUTTON_HEAD": KIT_MATERIAL,
    "M2_HEX_NUT": KIT_MATERIAL,
    "M1_6X8_PAN_HEAD_KIT": "304 stainless steel (seller claim)",
    "M1_6_HEX_NUT_DIN934": "304 stainless steel (seller claim)",
    SELECTED_DRIVE.driver.sku: "Aluminium alloy (seller claim; steel attribute conflicts)",
    SELECTED_DRIVE.output.sku: "Copper alloy (seller claim)",
    "BEARING_3X6X2_5": "Bearing steel",
    "SS304_CUT3_L34_FLAT5_A0": "304 stainless steel (seller claim)",
    "SS304_CUT3_L20": "304 stainless steel (seller claim)",
    "SS304_CUT3_L18_FLAT18_A0": "304 stainless steel (seller claim)",
    "KST_X06_STOCK_HALF_ARM_1": "Supplied horn material unverified",
    "M1_4X8_PAN_HEAD_KIT": "304 stainless steel (seller claim)",
    "M1_4_HEX_NUT_DIN934": "Brass (seller claim; grade unspecified)",
}

EXPECTED_INVENTORY = {
    "rails": 1,
    "equipment_mounts": 3,
    "tilting_propulsors": 2,
    "installed_prints": 16,
    "optical_mount_parts": 2,
    "fit_coupons": 4,
    "purchased_hardware": sum(PURCHASED_HARDWARE_QUANTITIES.values()),
    "purchased_hardware_types": len(PURCHASED_HARDWARE_QUANTITIES),
    "unique_print_files": 13,
}

# Preserve the FC's previous world-heading basis in the 180-degree carrier.
# Navigation and radio now use a separate accessory carrier; actual port datums
# and assembled sensor/controller orientation remain to be verified.
FC_INSTALLATION_LOCAL_YAW_DEG = 180.0
MODULE_LAYOUT_DECISION = {
    "layout": "Three main mass regions use four equipment/propulsion rail modules: propulsion near the rail centre, battery on +X, and electronics on -X behind the neutral motors. The optical head attaches to an existing universal carrier and follows that carrier. The electronics region comprises independent FC and navigation carriers of the same print used by the battery; the Mini uses the rail-facing side of the navigation plate outside the central saddle.",
    "trim": "Default stations are a wiring and clearance arrangement, not a verified mass balance. Adjust the battery carrier within its supported slot or relocate it to another wall segment for the actual pack or an empty carrier with external power; weigh the complete assembly and recheck cable slack, clearances and support after trim. Connector hardware remains unselected; optional electrical supply plans are defined separately in contracts/power_options.py.",
    "electronics": "Place the universal FC carrier behind the neutral motors and the identical navigation/radio carrier farther along the same rail end. Both carriers have a nominal 180deg Z orientation. Rotate the FC a further 180deg relative to its carrier to preserve the earlier world-heading design basis and underbody wire-corridor side. The accessory carrier retains the P-AS mounting pattern and adhesive support for MG-A01 or MG-F10-A alternatives, plus the selected Mini. Exact board heading, ports, connected cable access and firmware orientation remain physical checks.",
    "optical": "One MTF-02P or MTF-01P shares the adhesive tray on a carrier-mounted manual pitch head. Default is the battery carrier positive-X edge, at the height derived from the selected carrier and optical foot. Relocation requires complete optical-view, service, power and navigation checks; a common slot interface does not qualify every host or edge.",
    "service": "Disconnect external harnesses. Hold the exposed rail nut, loosen the side bolt for local CG trim, or withdraw the bolt and remove the nut to lift the populated module. Equipment need not be removed for rail access. Validate both tool access and complete screw/nut extraction against the installed neighbours; a shared slot does not make all equipment arrangements serviceable.",
}


# These are bought wiring requirements, not additional modeled hardware/mass.
# Stock pre-crimped pigtails may be joined after checking the actual pinouts.
def wiring_purchase_plan(navigation_key=None, radio_key=None, sensor_key=None):
    """Derive connector ends from the mutually exclusive onboard choices."""
    navigation = get_navigation_profile(navigation_key)
    radio = get_radio_profile(radio_key)
    sensor = get_sensor_profile(sensor_key)
    gps_selected = navigation.key != "PAS"
    return {
        "scope": "Three selected onboard UART harnesses; the GPS alternative also carries I2C compass signals in its six-pin harness. Subtract cables already supplied with devices. Lengths and finished mass remain unmeasured; this is not a full vehicle harness list.",
        "uart_harnesses": [
            {
                "connection": f"FC UART1 to {radio.model} UART",
                "quantity": 1,
                "fc_connector": "SH1.0-6P UART1/UART6 port",
                "device_connector": radio.connector_type,
            },
            {
                "connection": f"FC UART3{'/I2C' if gps_selected else ''} to {navigation.model}",
                "quantity": 1,
                "fc_connector": "SH1.0-6P UART3/I2C port",
                "device_connector": navigation.connector_type,
                "signal_scope": (
                    "UART GPS TX/RX plus compass I2C SCL/SDA, 5V and GND"
                    if gps_selected
                    else "UART TX/RX, 5V and GND; use one P-AS parallel port only"
                ),
            },
            {
                "connection": f"FC UART4 to {sensor.model} UART; one optical sensor only",
                "quantity": 1,
                "fc_connector": "SH1.0-4P UART4 port",
                "device_connector": "SH1.0-4P",
            },
        ],
        "connector_ends_before_subtracting_included_cables": dict(
            Counter(
                (
                    "SH1.0-6P",
                    "SH1.0-6P",
                    "SH1.0-4P",
                    "SH1.0-4P",
                    navigation.connector_type,
                    radio.connector_type,
                )
            )
        ),
        "ground_radio": "LR24-F ground unit paired with the sole selected LR24-F-Mini air unit, with matching settings and 2.4GHz antennas. The full-size F is not installed on the gondola or included in onboard inventory.",
        "radio_power_reference": {
            "maximum_average_w": radio.max_average_power_w,
            "calculated_at_5v_a": radio.max_average_power_w / 5,
            "scope": "Catalog maximum average reference, not measured peak demand or verified shared BEC headroom.",
        },
        "pinout_rule": "Family/pin count does not establish pin order, voltage or a straight-through cable. Match the official device pinouts, supply requirements and TX/RX direction. Do not use the FC's 12V DJI connector as a 5V UART supply.",
        "stock_consumables": [
            "Hook-and-loop straps or small cable ties wrap existing frame members; select width and quantity after routing, without dedicated printed tie holes. Route around the solid bearing-post roots and keep the exposed side rail screw and nut-tool paths clear. Keep strap buckles and tie heads outside moving parts and do not pull the phase-wire loop taut. No assumed route through the bearing posts.",
            "Flexible pre-crimped SH/GH pigtails, insulating heat-shrink and strain relief; select wire gauge and lengths for the actual load and route.",
            "XT30-family pigtail compatible with the purchased battery; compact AMASS XT30U is the dimensional reference, not confirmation of the supplied battery connector variant.",
        ],
        "seller_or_completed_harness_verified": False,
        "stock_replacement_decision": "Use already-owned M2 metal hardware and GH1.25 connectors, selected micro-screw kit, manufacturer X06 stock plastic half arm1 on both sides, gears, nominal-3mm 304 rods and3x6x2.5 ball bearings. The selected horn uses the manufacturer's nominal STEP geometry with only the two declared factory-hole enlargements, rear M1.4x8 screws and front M1.4 nuts; do not fabricate a replacement spline. Older metal-horn drawings are historical alternatives, not current adapter compatibility claims. No purchased bearing spacers. Optional Matek boards use insulating adhesive or straps on the vacated battery carrier or the separately screened raised platform, not invented PCB holes. Optional hardware is separate from the baseline mechanism BOM.",
    }


WIRING_PURCHASE_PLAN = wiring_purchase_plan()


@dataclass(frozen=True)
class ModuleStation:
    object_name: str
    x_mm: float
    yaw_deg: int = 0
    attachment_offset_x_mm: float = 0.0
    contact_length_mm: float = 16.0

    def __post_init__(self):
        if self.yaw_deg not in (0, 180):
            raise ValueError("Rail module orientation must be 0 or 180 degrees")
        if not all(
            math.isfinite(value) for value in (self.x_mm, self.attachment_offset_x_mm)
        ):
            raise ValueError("Module and attachment positions must be finite")
        if not math.isfinite(self.contact_length_mm) or self.contact_length_mm <= 0:
            raise ValueError("Contact length must be finite and positive")


MODULE_STATIONS = (
    ModuleStation("BatteryEquipmentModule", 100),
    ModuleStation(
        "MainPropulsionModule", -5, attachment_offset_x_mm=12.5, contact_length_mm=32
    ),
    ModuleStation("ElectronicsEquipmentModule", -60, 180),
    ModuleStation("AccessoryEquipmentModule", -140, 180),
)


@dataclass(frozen=True)
class UnresolvedInterface:
    key: str
    required_evidence: str
    status: str = "unverified"


# Update only after obtaining the stated physical or supplier evidence.
UNRESOLVED_INTERFACES = (
    UnresolvedInterface(
        "fc_installed_power",
        "The user confirmed the selected 45A AM32 board's 2S support on 2026-09-29; do not reopen that selection question from older conflicting catalogs. Verify actual AM32 firmware/output setup, installed supply stability and the shared 5V/2A supply under installed loads; the 45A ESC label does not increase BEC capacity. No minimum operating voltage, hardware revision, completed power test or higher-voltage motor compatibility is inferred.",
    ),
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
        f"Creallo acceptance of one-piece {RAIL_LENGTH_MM:g}mm rail, {RAIL_BASE_THICKNESS_MM:g}mm base/wings, curvature and depowdering.",
    ),
    UnresolvedInterface(
        "motor_mount",
        "RS1102 drawing confirms three M1.4 holes on PCD6.6; verify actual thread engagement, rear shaft/clip envelope and selected screw length before fastening.",
    ),
    UnresolvedInterface(
        "servo_drive",
        "Verify the selected manufacturer X06 stock plastic half arm1 on the actual servo: spline/OEM screw seating, locating surface, flatness and runout. The supplied STEP establishes nominal geometry, not delivered tolerances, resin, mass or loaded retention. Enlarge only the existing diameter1mm holes at6.8/13.2mm to1.5mm; deburr and inspect the remaining plastic. Use two rear M1.4x8 screws/front M1.4 nuts and the near round hole/far short slot, clamped before operation. The nominal2mm arm,3.6mm printed grip and1.2mm nut give6.8mm total grip and1.2mm tip projection; check actual head/nut contact, engagement, protrusion and service clearance. The0.15mm radial open root-seat allowance and fixing clearances do not compensate a bent shaft or eccentric spline. The D-socket and nominal-3mm stub require fit and loaded grip checks. No extra input bearing is selected; external radial servo load, plastic/PA12 creep and two-way torque retention remain unqualified.",
    ),
    UnresolvedInterface(
        "optional_power_and_tether",
        "Optional tether plan: one BEC12S-PRO converts 24 V to 8 V; this rail supplies the FC/main load and the SVPDB-8S input. SVPDB supplies a separate 5 V servo rail. The upstream BEC's published 5 A output must cover both the main load and the SVPDB input, including conversion losses; installed current and thermal margins are unmeasured. Check board undersides, insulation, headers, plugs, external strap contact and cooling. Keep servo-positive wires separate from FC 5 V with common ground. The selected FC supports 2S by user confirmation; 8 V is nominally consistent with that supply class, while regulator startup/transients and loaded operation remain unverified. The optical carrier host and edge must clear the selected power configuration; a shared mounting pattern does not establish an unobstructed sensor view. Straps wrap existing structure without dedicated tie holes; actual tether gauge, bend radius, tension, strain relief, whole-cable propeller/FOV clearance and loaded PA12 retention remain unverified. No live battery/tether changeover is designed.",
    ),
    UnresolvedInterface(
        "servo_ear_retention",
        "X06 drawing publishes two diameter 2 mm ear holes at 24 mm pitch and ear surfaces 3.7/4.7 mm below the case top. Verify actual ear contact, case tolerance, selected mounting screws and engagement. Both sets of mounting ears seat on one common upright with 3 mm outside walls and a solid central web. The bridge plate bears directly on a broad central frame seat; the paired servo module remains removable. Check fore-aft bending, retained gear spacing and PA12 creep under load. Follow the checked ordered gear, coupling and servo extraction paths; free the leads and confirm the actual wire exit and handling access. Rigid CAD clearance does not establish installed stiffness or a physical assembly fit.",
    ),
    UnresolvedInterface(
        "gear_mesh_and_shaft_retention",
        f"Check the purchased {SELECTED_DRIVE.driver.teeth}T/{SELECTED_DRIVE.output.teeth}T selected seller pair at nominal {SELECTED_DRIVE.center_distance_mm:g} mm centre distance, backlash, centre alignment, set-screw retention and PA12 creep. Both servo cradles form one removable ratio-specific bridge on the common output-bearing frame. The supported configuration is 48T/16T only; another ratio or servo requires redesigned replacement parts and renewed validation. A broad central Z seat, two local mounting seats and unilateral X/Y datums establish its position; two M2 bolts clamp it without adjustment slots. The central and two outer support regions share one Z plane. Check common-face flatness and simultaneous seating; reject rocking. Servo ear clearance, seating error, print distortion and creep affect the mesh. Measure both assembled centre distances and backlash; correct/reprint the bridge if required rather than elongating holes, forcing gears or pulling a warped bridge flat with the bolts. Qualify the purchased generic 3×6×2.5 bearing and Ø3 304 rod fits, fixed round seats, rear shoulders, keyed front keepers, shield clearance and independent carrier/frame axial stops. The nominal Ø6.1 seat and0.5mm inward float are trial allowances, not compensation for the full PA12 process tolerance. Match the production cup and keeper coupons; reject radial rocking, preload, shield rubbing, keeper movement or excess endplay. Keeper M2 screws must seat the keepers firmly on the frame without squeezing the bearing. Verify actual nut engagement and service access. Remove carrier/shafts before keepers and bearings; no latch opening is required. Generic bearing dimensions beyond the boundary envelope remain unmeasured. Rod tolerance evidence is waived as a design blocker; deburr cut ends and measure before insertion, never force the shaft through bearings. A dimensionally equivalent precision Ø3 shaft is a fallback without changing nominal CAD; recheck fits and torque grip. Shaft friction retention and preload remain unqualified. Confirm purchased M3 screw lengths/tips and protrusion before running; those screw solids are not yet modeled.",
    ),
    UnresolvedInterface(
        "electronic_mounting_stack",
        "FC and P-AS hole XY are confirmed. Measure PCB bearing planes, the selected 45A package's silicone dampers, purchased spacer lengths and screw engagement. Package damper length does not define the compressed mounting stack. Preserve at least the allocated 8mm FC underbody wiring clearance; no completed mounting stack is claimed.",
    ),
    UnresolvedInterface(
        "physical_retention",
        "Trial the slotted rail and L-mount coupons in the production PA12 process/finish. The flat support must seat without rocking; no squeeze-fit ears or spring preload are specified. Tighten the side M2x8 pair against broad faces, holding the exposed standard nut. Check the received head and nut bearing areas, full thread engagement, slot edge finish, complete head/nut withdrawal, friction retention and PA12 creep. Stay within supported slot ranges; move between wall segments only with the bolt removed. A narrow continuous base and three wing pairs require loaded curved-envelope adhesion and fatigue checks. CAD clearance does not establish a tightening torque or load rating.",
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
        "Manually align the carrier-mounted optical head to downward vertical at flight trim, lock the single pitch clamp, then verify the selected MTF-02P/MTF-01P lens datums, firmware yaw/position offsets, adhesive retention, connector slack and unobstructed field. Added mass does not by itself guarantee vertical alignment or active stabilization.",
    ),
    UnresolvedInterface(
        "optical_stack_retention",
        "Seat the optical foot and its integral locating tongue in the existing carrier side slot, align it, then tighten its single M2 pair; manually align and lock the single pitch joint. Finish or reprint an interfering locator rather than pulling an unseated foot down with the screw. Verify foot seating, full nut engagement, pointing friction, PA12 creep and cable loads. No spring preload or active stabilization is assumed. Disconnect the sensor lead before removing or relocating the head. Recheck complete view cones after changing host, edge or rail station; common interfaces do not make every position acceptable.",
    ),
    UnresolvedInterface(
        "rc_and_heading_installation",
        "The cart selects a RadioMaster XR2 receiver, whose installation and harness are not represented by this CAD. The P-AS baseline still needs a selected heading reference; GPS alternatives MG-A01/M10 Ultra and MG-F10-A include compasses requiring their I2C harness, physical orientation, calibration and power-wire interference checks. Mechanical support does not qualify heading or indoor/outdoor GNSS reception. The scoped inventory excludes unselected devices and the UART purchase plan is not a complete vehicle harness list.",
    ),
    UnresolvedInterface(
        "alternative_equipment_installation",
        "Install one navigation module, LR24-F-Mini and one optical sensor; rebuild CAD/BOM after changing navigation or optical selections. Verify GPS and Mini underside contact on the accessory carrier's insulating adhesive, actual connector insertion/bend space and retention. MG-F10-A allows a direct SMA helix or remote SMA connection; direct mounting on this underside carrier points away from the balloon and downward, so its conservative clearance screen is not a reception claim. Prefer a remote upward antenna location when GPS reception matters, including outdoors; its off-gondola location, cable and attachment are unmodeled. Verify support for the 15g helix and connector-tightening loads, or remote-cable strain relief. Check LR24-F ground pairing and the Mini's 2W maximum-average reference against the shared 5V supply; peak demand and supply margin are unmeasured. No antenna or adhesive strength is certified by a passing clearance check.",
    ),
    UnresolvedInterface(
        "finished_mass",
        "Weigh the selected battery, navigation and radio modules, optical sensor, antennas, prints, drive hardware, wiring, connectors and adhesive. The subtotal uses published device masses, including LR24-F-Mini 2.5g and a separate 15g MG-F10 helix only when that navigation profile is selected. Unmeasured battery mass is excluded, not assigned zero. A changed catalog subtotal reflects the selected reference items, not measured physical weight reduction. Catalog mass is not an installed measurement.",
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
            "FC mounting spacers/fasteners and dampers, plus P-AS mounting hardware only when P-AS is selected: actual PCB bearing planes, compressed damper dimensions and fastener lengths remain unverified. GPS alternatives use insulating adhesive, not additional GPS screws.",
            "RS1102 motor mounting screws and OEM X06 horn-retaining screws: lengths, heads and actual engagement remain unverified. Two manufacturer stock plastic half arms of the same selected profile, four M1.4x8 attachment screws and four front M1.4 nuts are included with their declared preparation; older horn alternatives are outside the current inventory.",
            "Four M3 gear set screws: thread confirmed, exact length/tip/protrusion and inclusion not verified; procure later after measuring the actual hubs.",
            "Tape, adhesive, wiring, connectors, insulation, strain relief, antennas, capacitor and other unmodeled accessories. Optional power platform, Matek boards, ties and its M2 attachment hardware are supplied in the separate optional-power artifacts, not this baseline BOM.",
        ],
        "unmodeled_wiring_purchase_plan": WIRING_PURCHASE_PLAN,
        "release_status": release_status(),
    }


def project_status():
    return {
        "design_revision": DESIGN_REVISION,
        "units": "mm",
        "printed_material": "Unfilled PA12 design basis; SLS or MJF, supplier grade/process/finish agreement pending",
        "manufacturing_decision": MANUFACTURING_DECISION,
        "structural_design_basis": "Ultralight indoor LTA gondola; lower stiffness than a sub-250g multirotor is accepted. First integrate parts with no necessary separation, make them manufacturable, then optimize their shape. Retain splits only for demonstrated assembly, motion or requested replacement functions. Redesign when the complete assembly improves in mass, simplicity, fit or serviceability, respecting current user constraints. This iteration retains the four already-purchased generic 3x6x2.5 bearings; do not substitute flanged bearings or require a new bearing purchase. Allow modest mass increases for simpler integral parts and forgiving noncritical envelopes. Preserve the intentionally removable paired-servo/input-gear module. Use simple clearance or short slots where they reduce fit risk without adding parts; retain functional locating, torque and bearing surfaces. Do not add elaborate adjustment mechanisms. Compare complete torque/retention paths; minimize hardware varieties and omit unnecessary washers. Physical retention remains unverified.",
        "part_separation_reasons": PART_SEPARATION_REASONS,
        "scope": f"Indoor LTA blimp gondola including one {get_sensor_profile().model}: one flexible rail, two independently geared X06 main propulsors with bounded ±180deg output targets, compact battery and FC carriers, and one simple navigation/LR24-F-Mini accessory carrier. An existing universal carrier supports the manually aligned optical head through its side slot. Each purchased {SELECTED_DRIVE.driver.teeth}T driver turns a {SELECTED_DRIVE.output.teeth}T output gear; no yaw motor or fin hardware is included.",
        "selected_drive": SELECTED_DRIVE.contract(),
        "flight_controller": flight_controller_contract(),
        "optional_power": power_option_contract(),
        "navigation": get_navigation_profile().contract(),
        "radio": get_radio_profile().contract(),
        "attachment": "Thin double-sided adhesive under the narrow rail base distributes equipment loads; three paired wings accept optional over-tape. Keep side fasteners, slots and flex gaps accessible; qualify actual curved adhesion.",
        "battery_attachment": "Adhesive hook-and-loop uses the four continuous contact allocations on the shared slotted square deck. Optional support feet use its common outer slots outside those allocations; 90deg in-plane orientation. Battery centre allowance +/-5mm X, +/-4mm Y; larger trim changes require rail-carrier repositioning and a new clearance check.",
        "equipment": [asdict(item) for item in SELECTED_EQUIPMENT],
        "scoped_listed_equipment_mass_g": SCOPED_LISTED_EQUIPMENT_MASS_G,
        "equipment_mass_scope": "Published masses of selected devices only, plus the separate MG-F10 15g helix only when selected; alternatives and the ground radio are not double-counted. Battery mass remains unmeasured/excluded. Excludes printed parts, drive hardware, unspecified antennas, wiring and other accessories; not an all-up mass or measured installed subtotal.",
        "source_discrepancies": SOURCE_DISCREPANCIES,
        "excluded_equipment": EXCLUDED_EQUIPMENT,
        "inventory": EXPECTED_INVENTORY,
        "wiring_purchase_plan": WIRING_PURCHASE_PLAN,
        "optical_stack_scope": "One compact foot/post uses an existing universal carrier side slot and supports the adhesive tray through a manual pitch-Y clamp. There is no independent optical rail shoe. Pitch corrects longitudinal curvature only; roll is not corrected. Host, edge, optical view and optional power/navigation combinations must pass composed checks. Physical pointing, fit, retention and creep remain unqualified.",
        "module_stations": [asdict(item) for item in MODULE_STATIONS],
        "module_layout_decision": MODULE_LAYOUT_DECISION,
        **release_status(),
    }
