"""User decisions and unresolved interfaces consumed by CAD and the CLI.

Part geometry belongs to gondola/parts; published interface dimensions belong to
the other contract modules. Geometric test success never changes release status.
"""

import math
from collections import Counter
from dataclasses import asdict, dataclass
from numbers import Real

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
from .fasteners import KIT_MATERIAL, RAIL_FASTENER_MATERIAL
from .optical_sensors import get_sensor_profile
from .power_options import power_option_contract
from .rail_attachments import module_attachment_pattern
from .servo_horns import SELECTED_BY_SIDE, preparation_note
from .servo_horns import profile as horn_profile

CREALLO_GUIDE_URL = "https://creallo.com/ko/guide/design-spec-guide"
DESIGN_REVISION = "CK"
# Nominal local part dimensions, before print rotation; not delivered-size tolerance.
MAX_PRINT_PART_DIMENSION_MM = 340.0
# Chosen assembly length is independent of the supplier-screening size limit.
RAIL_LENGTH_MM = 300.0
# User's 2026-09-29 manufacturing review requires at least this nominal rail
# attachment thickness; actual delivered dimensions/curvature remain unmeasured.
RAIL_BASE_THICKNESS_MM = 1.5
# Project structural interface, independent of the FC mounting-hole pattern.
STACK_PITCH_MM = 40.0
STACK_ANCHOR_CENTRES = tuple(
    (sign * STACK_PITCH_MM / 2, sign * STACK_PITCH_MM / 2) for sign in (-1, 1)
)
STACK_ANCHOR_LOCATIONS = (
    " and ".join(f"({x:g}, {y:g})" for x, y in STACK_ANCHOR_CENTRES) + " mm"
)
PUBLISHED_PROCESS_SIZE_MM = {"SLS": [340, 340, 600], "MJF": [380, 380, 280]}
MANUFACTURING_DECISION = {
    "reviewed_on": "2026-10-02",
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
    "qualification": "Not qualified: obtain one-piece acceptance and review rail flexures, straightness, curvature, fatigue and seated mounting fit. Use the same agreed unfilled PA12 process/material/finish and corresponding feature orientation for coupons and full parts. Verify the common instrument pitch joint and fixed sensor bracket for flatness, pointing stability and creep with actual fasteners.",
    "nominal_general_functional_wall_mm": 1.5,
    "nominal_rail_flexure_mm": RAIL_BASE_THICKNESS_MM,
    "flexure_exception": "The rail base and tape wings retain the user-reported manufacturing-review minimum of 1.5 mm nominal. Eleven equal18mm walls on28mm pitch leave10mm wall gaps and8mm clear gaps between R1 end-root transitions above the continuous base. Local10mm side-contact zones retain intended +/-3mm straight-rail travel per station. All shoes share flat wall-top contacts and the same side fit. Ordinary carriers follow one wall; the two walls beneath the rigid propulsion frame must be coplanar. Bending occurs beyond its paired footprint, not independently beneath it. Do not cut bend grooves below the 1.5 mm base minimum; compact rigid attachment footprints instead. Read the rail contract for geometry and permitted poses. Actual curvature, contact fit, adhesion, stiffness and fatigue remain unqualified.",
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
    "fc_and_accessory_carriers": "Battery and navigation use two identical fixed square carriers. The separate FC/optical levelling variant retains their square hole pattern and rail interface, with an integral sensor bridge on its moving plate and a separate pitch base. The complete carriers are not interchangeable parts. Hole compatibility is not a payload rating.",
    "rail_and_carriers": "Five M3x10 pairs attach three equipment modules and the paired propulsion support to the rail. The FC instrument platform has two additional M3 joint pairs. Local rail trim remains nominally +/-3mm per station; curvature, adhesion, fit and loaded retention require physical trials.",
    "integrated_servo_and_output_support": "Servo supports and input/output-bearing beds form one fixed frame. The 9.5mm bearing-support beam meets the central servo plinth without the former underside step; no upper tie or broad linking plate. The7.4x20.4mm window provides0.2mm nominal clearance per face around the7x20mm case. The published+0.2mm overall case allowance leaves0.1mm per face when centred, before printing error. Finish the printed window for snug hand assembly without compressing the case; ear joints provide the operating clamp. Each35mm input shaft has a16mm proximal flat and a round distal journal supported by one external bearing. Follow the checked shaft-first service sequence after output-gear unmeshing; remove the loose driver before the servo/horn/adapter. Keep the M1 horn joints and OEM centre screw installed. The input axes remain16mm from the output axes atZ50. Check the complete service path, leads, mesh and loaded support deflection. A closed planar frame and an added shaft support do not qualify alignment, load sharing or strength; no detachable printed servo bridge or added closure hardware.",
    "bearings_and_frame": "Six generic3x6x2.5 bearings are required: two inboard output bearings and one external input-shaft bearing per side. Four were previously confirmed purchased; verify two additional matching bearings or spares. Each existing housing cap extends to retain all three bearings on that side. Two aligned M2x10 bolt/ordinary M2 nut pairs retain each cap; locating keys and hard lands remain. The input wing is set back for gear and shaft-clamp access; its root is rounded without filling the service path. Tighten the cap onto its hard frame lands, never squeeze the bearings to hide loose seats. Nominal diameter6 seats require production-process fit qualification and coaxiality checks, including alignment of the input bearing with the servo/horn shaft axis. Outer-ring shoulders retain the bearings; separate broad gear/frame and carrier/frame stops bound output-shaft travel without shield contact. No bought spacer, push-on ring or outboard idler shaft. Actual shield/race lands, endplay, clamp slip, post compliance, load sharing and strength remain unqualified.",
    "motor_carriers_and_frame": "Independent rotating carriers remain shaft-supported from the inboard side only. The rear motor plate joins the protective ring at the keyed root and an opposite integral return arm, reducing the unsupported ring span without an outer bearing, shaft or added hardware. Preserve clearance through bounded rotation, wire-loop allowance and positive axial stops. Motor mounting face X=-5mm is a printed datum; actual propeller seating and full blade sweep remain unresolved. The current guard serves nominal40mm propellers;50mm is only a replacement-space provision requiring a new rotor. Ring impact resistance and loaded stiffness remain unqualified.",
    "horn_and_adapter": preparation_note()
    + " Keep the purchased spline, OEM centre screw, shaft-stop floor and gear/stub planes. Adapter openings and nut clearance accommodate fitting before tightening, not operating looseness. Follow the coupling contract for actual geometry and ordered service; source dimensions do not qualify strength or runout.",
    "optical_head": "The optical support is integral with the FC levelling carrier, centred below the FC in its local frame. FC and sensor share one setup-only pitch axis; no separate optical print, foot fasteners, optical joint or self-levelling mechanism. Preserve both sensor envelopes and field clearance; verify adhesive, printed seating and creep.",
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
            quantities["M1_HEX_NUT"] += 2
    return dict(quantities)


RAIL_ATTACHMENT_COUNT = 5

PURCHASED_HARDWARE_QUANTITIES = {
    "M3X10_BUTTON_HEAD": RAIL_ATTACHMENT_COUNT,
    "M3_HEX_NUT": RAIL_ATTACHMENT_COUNT + 2,
    "M3X16_BUTTON_HEAD": 2,
    "M2X12_BUTTON_HEAD": 2,
    "M2X6_BUTTON_HEAD": 2,
    "M2X10_BUTTON_HEAD": 4,
    "M2_HEX_NUT": 8,
    "M1_6X8_PAN_HEAD_KIT": 4,
    "M1_6_HEX_NUT_DIN934": 4,
    SELECTED_DRIVE.driver.sku: 2,
    SELECTED_DRIVE.output.sku: 2,
    "BEARING_3X6X2_5": 6,
    "SS304_CUT3_L42_FLAT5_GRIP11_A0": 2,
    "SS304_CUT3_L35_FLAT16_A0": 2,
    **_selected_horn_hardware(),
}

HARDWARE_MATERIALS = {
    "M3X10_BUTTON_HEAD": RAIL_FASTENER_MATERIAL,
    "M3X16_BUTTON_HEAD": RAIL_FASTENER_MATERIAL,
    "M3_HEX_NUT": RAIL_FASTENER_MATERIAL,
    "M2X8_BUTTON_HEAD": KIT_MATERIAL,
    "M2X6_BUTTON_HEAD": KIT_MATERIAL,
    "M2X10_BUTTON_HEAD": KIT_MATERIAL,
    "M2X12_BUTTON_HEAD": KIT_MATERIAL,
    "M2_HEX_NUT": KIT_MATERIAL,
    "M1_6X8_PAN_HEAD_KIT": "304 stainless steel (seller claim)",
    "M1_6_HEX_NUT_DIN934": "304 stainless steel (seller claim)",
    SELECTED_DRIVE.driver.sku: "Aluminium alloy (seller claim; steel attribute conflicts)",
    SELECTED_DRIVE.output.sku: "Copper alloy (seller claim)",
    "BEARING_3X6X2_5": "Bearing steel",
    "SS304_CUT3_L42_FLAT5_GRIP11_A0": "304 stainless steel (seller claim)",
    "SS304_CUT3_L35_FLAT16_A0": "304 stainless steel (seller claim)",
    "KST_X06_STOCK_HALF_ARM_1": "Supplied horn material unverified",
    "M1X6_HEX_HEAD": "Unverified metal",
    "M1_HEX_NUT": "Unverified metal",
}

EXPECTED_INVENTORY = {
    "rails": 1,
    "equipment_mounts": 3,
    "tilting_propulsors": 2,
    "installed_prints": 12,
    "optical_mount_parts": 0,
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
    "layout": "Three main mass regions: central propulsion, battery on +X, electronics on -X. FC and optical sensor share one integral adjustable carrier; navigation and Mini use a separate fixed carrier. The initial FC station remains X=-82mm: moving to the adjacent -56mm station intersects reserved FC wiring with the servo drive during pitch adjustment. Neither this station nor the heavy propulsion assembly establishes whole-vehicle CG. Locate the rail on the hull lower centreline and measure the complete vehicle CG with its actual envelope, battery and harness before final trim.",
    "trim": "Default stations are a wiring and clearance arrangement, not a verified mass balance. Adjust the battery carrier within its supported slot or relocate it to another wall segment for the actual pack or an empty carrier with external power; weigh the complete assembly and recheck cable slack, clearances and support after trim. Connector hardware remains unselected; optional electrical supply plans are defined separately in contracts/power_options.py.",
    "electronics": "The FC upper plate and all its references follow InstrumentPitchStage on the electronics rail base. Its local device coordinates retain the existing 8mm underbody wiring allowance. The carrier rail frame yaw and FC local yaw remain design markers; identify actual board arrow and IMU origin before firmware setup. The navigation/radio carrier remains fixed.",
    "optical": "One MTF-02P or MTF-01P is rigidly located below the FC on the same upper platform, with coincident envelope centre lines in local X/Y. Align the platform to the defined vehicle reference attitude and lock before use. The sensor follows body attitude in flight. Exact optical/IMU origins and firmware orientation remain to measure; common mounting does not justify zero offsets.",
    "service": "Disconnect harnesses and support modules. For bare FC replacement, first return InstrumentPitchStage to its 0-degree maintenance pose, remove the actual FC mounting hardware, slide the board local +X60mm and then lift local +Z32mm through the integral bridge. Re-establish and lock the body-reference angle after service. No assembled FC fastener stack or tool beyond the reserved head columns is certified. Loosen every shared M3 pair for local trim; remain within all foot support intervals. For propulsion removal, extract both screw/nut pairs, slide the whole supported module +X10 mm along the rail and lift Z30 mm to clear the FC carrier. This unclamped removal stroke is not an operating CG position. Keep both propulsion shoes seated during trim; no automatic centring. Carriers use one side pair; at the selected layout the FC carrier slides world -X4 mm before Z30 lift, while the accessory carrier must slide world -X9 mm before Z30 lift. Hold it throughout removal because its shoe partly leaves the rail end. Only the battery carrier lifts directly. These temporary removal positions are not operating positions. Equipment stays mounted, but revalidate full tool/fastener/removal access after any layout change.",
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
            "Hook-and-loop straps or small cable ties wrap existing frame members; select width and quantity after routing, without dedicated printed tie holes. Route around the solid bearing-post roots and keep the recessed side rail screw and open nut-window access paths clear. Keep strap buckles and tie heads outside moving parts and do not pull the phase-wire loop taut. No assumed route through the bearing posts.",
            "Flexible pre-crimped SH/GH pigtails, insulating heat-shrink and strain relief; select wire gauge and lengths for the actual load and route.",
            "XT30-family pigtail compatible with the purchased battery; compact AMASS XT30U is the dimensional reference, not confirmation of the supplied battery connector variant.",
        ],
        "seller_or_completed_harness_verified": False,
        "stock_replacement_decision": "Use owned M2/M3 hardware, GH1.25 connectors, the selected micro-screw kit for servo ears, unmodified manufacturer X06 stock half arm1 on both sides, owned M1 hex hardware for horn attachment, purchased gears, nominal3mm 304 rods and3x6x2.5 bearings. Owned M1 lengths, external-head size, metal grade and delivered fit remain unmeasured. Use declared acceptance envelopes, not assumed universal head dimensions. Do not print a replacement spline. No bearing spacers. Optional Matek boards use insulating adhesive or straps on the battery carrier or optional platform; no invented PCB holes.",
    }


WIRING_PURCHASE_PLAN = wiring_purchase_plan()


@dataclass(frozen=True)
class ModuleStation:
    object_name: str
    x_mm: float
    yaw_deg: int = 0
    attachment_offset_x_mm: float = 0.0
    contact_length_mm: float = 16.0

    @property
    def attachment_pattern(self):
        return module_attachment_pattern(self.object_name)

    @property
    def attachment_offsets_x_mm(self):
        return tuple(
            site["x_offset"]
            for site in self.attachment_pattern.sites(self.attachment_offset_x_mm)
        )

    def __post_init__(self):
        if self.yaw_deg not in (0, 180):
            raise ValueError("Rail module orientation must be 0 or 180 degrees")
        values = (self.x_mm, self.attachment_offset_x_mm, self.contact_length_mm)
        if any(
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(value)
            for value in values
        ):
            raise ValueError(
                "Module positions and contact length must be finite numbers"
            )
        if self.contact_length_mm <= 0:
            raise ValueError("Contact length must be positive")
        self.attachment_pattern.sites(self.attachment_offset_x_mm)


def module_stations():
    """Four rail modules; the optical sensor shares the FC instrument platform."""
    stations = (
        ModuleStation("BatteryEquipmentModule", 84),
        ModuleStation(
            "MainPropulsionModule",
            14.0,
            attachment_offset_x_mm=14.0,
            contact_length_mm=44,
        ),
        ModuleStation("ElectronicsEquipmentModule", -82, 180),
        ModuleStation("AccessoryEquipmentModule", -140, 180),
    )
    return stations


MODULE_STATIONS = module_stations()


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
        "propeller_installation",
        "Actual Gemfan1610 seating on the received RS1102 and the complete blade axial sweep are unknown; the user cannot currently measure them. The sourced 5 mm dimension is hub thickness, not a qualified full-blade envelope. Keep physical seating offset and actual hub plane unset. The displayed reference case and its collision checks do not certify real propeller clearance or guard protection. Qualify the rotating carrier/guard after resolving this interface; rail, frame and electronic mounting geometry are independent of this unknown.",
    ),
    UnresolvedInterface(
        "optional_payload_installation",
        "Pi 5 and SIYI A8 mini are alternative mounting-pattern provisions, not installed baseline equipment. Check the actual M2.5 hardware bearing faces, standoffs, connector and cooling access, A8 original dampers and full gimbal motion, carrier/support loading and retention before installing either payload. Pattern fit does not establish simultaneous-device compatibility, power compatibility or a qualified payload rating.",
    ),
    UnresolvedInterface(
        "servo_drive",
        preparation_note()
        + " Verify spline/OEM screw seating, root fit, flatness and runout. The open root seat does not compensate eccentricity or a bent shaft. Finish the nominal3mm circular D-socket datum to the actual stub; check loaded grip, external servo radial load, plastic creep and reversing torque retention.",
    ),
    UnresolvedInterface(
        "optional_power_and_tether",
        "Optional tether plan: one BEC12S-PRO converts 24 V to 8 V; this rail supplies the FC/main load and the SVPDB-8S input. SVPDB supplies a separate 5 V servo rail. The upstream BEC's published 5 A output must cover both the main load and the SVPDB input, including conversion losses; installed current and thermal margins are unmeasured. Check board undersides, insulation, headers, plugs, external strap contact and cooling. Keep servo-positive wires separate from FC 5 V with common ground. The selected FC supports 2S by user confirmation; 8 V is nominally consistent with that supply class, while regulator startup/transients and loaded operation remain unverified. The FC/optical levelling carrier must clear the selected power configuration; a shared mounting pattern does not establish simultaneous fit or an unobstructed view. Straps wrap existing structure without dedicated tie holes; actual tether gauge, bend radius, tension, strain relief, whole-cable propeller/FOV clearance and loaded PA12 retention remain unverified. No live battery/tether changeover is designed.",
    ),
    UnresolvedInterface(
        "servo_ear_retention",
        "X06 nominal two diameter2mm ear holes at24mm pitch and ear surfaces3.7/4.7mm below case top. Each compact closed frame supports both ears and closely surrounds the case. Nominal window clearance is0.2mm per face, not guaranteed received-part clearance; production error and actual case size require fitting. Remove the input stub and loose driver before both ear screws/nuts, then withdraw the servo/horn/adapter axially and outward. Follow the checked side-grip tool route; a long axial puller is obstructed. Verify actual case/ear fit, hardware engagement, rear leads, support twisting and creep. The fixed frame and output bearings remain installed; rigid clearance is not installed strength.",
    ),
    UnresolvedInterface(
        "gear_mesh_and_shaft_retention",
        "Selected48T/16T m0.5 gears retain16mm nominal centre distance on an integrated fixed frame. Check assembled backlash, tooth alignment, horn/stub concentricity, set-screw retention and creep through bounded travel; another ratio or servo needs replacement geometry and renewed validation. Six generic3x6x2.5 bearings are required: two inboard output pairs and one external input bearing per side, with four bearings previously confirmed purchased. The35mm input rods retain only a16mm proximal flat; their distal bearing journals remain round. The two output rods rotate with their carriers; no outboard idle shafts. Finish process-matched nominalØ6 seats andØ3 journals to the received parts without forced insertion, preload or radial rocking. Check input-bearing coaxiality with the servo axis rather than forcing misaligned supports together. Common cap lands must seat without squeezing any of the three bearings under each cap; check outer-ring shoulders and shield clearance. Broad external stops bound rotor endplay independently of the bearing shields. Check gear and carrier clamp grip because these complete the shaft-retention path. Bearing load sharing, the one-sided rotor/post load path, loaded deflection, fatigue and PA12 creep are unqualified. Rod tolerance evidence was waived as a design blocker, not as a physical fit check; a precisionØ3 rod remains a nominally compatible fallback. Gear set-screw lengths/tips/protrusion are still unmeasured and their solids are not modeled.",
    ),
    UnresolvedInterface(
        "electronic_mounting_stack",
        "FC and P-AS hole XY are confirmed. Measure PCB bearing planes, the selected 45A package's silicone dampers, purchased spacer lengths and screw engagement. Package damper length does not define the compressed mounting stack. Preserve at least the allocated 8mm FC underbody wiring clearance; no completed mounting stack is claimed.",
    ),
    UnresolvedInterface(
        "physical_retention",
        "Trial rail/frame and bearing housing/cap fit specimens in the production PA12 process, finish and orientation. Finish only enough to seat mating faces without rocking; reprint loose or warped parts. Never pull a warped support into shape or preload bearings with fastening torque. Use five M3x10 rail pairs, plus the separately specified instrument-joint hardware. Verify owned fasteners against the declared acceptance envelopes. The paired frame shoes must seat on coplanar wall tops before fastening; accommodate balloon curvature outside that rigid region. Verify head/nut envelopes, floor thickness, thread engagement, side access, fitted curvature, grip and creep. Support the full propulsion assembly before releasing either rail pair. Do not flatten a bonded curved rail with screws. No qualified tightening torque, strength or fatigue rating.",
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
        "Align FC and optical sensor together to the defined body reference, then lock the instrument pitch joint. Verify MTF-02P/MTF-01P optical origins, model-specific orientation, IMU origin, actual offsets, adhesive and field clearance. Whole-body tilt is not mounting error; never relevel only the sensor to hide body motion. FC isolation and flexible rail motion limit the rigid-relative-frame approximation.",
    ),
    UnresolvedInterface(
        "optical_stack_retention",
        "The optical support is integral with the FC carrier. Align the complete FC/sensor platform using its M3 pivot and arc lock, then verify no rocking or drift under cable load. Finish interfering print fits before clamping; do not distort parts with screw torque. Physical stiffness, friction, creep and rail torsion remain unqualified. Disconnect leads before service.",
    ),
    UnresolvedInterface(
        "rc_and_heading_installation",
        "The cart selects a RadioMaster XR2 receiver, whose installation and harness are not represented by this CAD. The P-AS baseline still needs a selected heading reference; GPS alternatives MG-A01/M10 Ultra and MG-F10-A include compasses requiring their I2C harness, physical orientation, calibration and power-wire interference checks. Mechanical support does not qualify heading or indoor/outdoor GNSS reception. The scoped inventory excludes unselected devices and the UART purchase plan is not a complete vehicle harness list.",
    ),
    UnresolvedInterface(
        "alternative_equipment_installation",
        "Install one navigation module, LR24-F-Mini and one optical sensor; rebuild CAD/BOM after changing navigation or optical selections. Verify GPS and Mini underside contact on the accessory carrier's insulating adhesive, actual connector insertion/bend space and retention. MG-F10-A direct SMA helix is blocked in the current instrument-platform layout over the full pitch range. Remote SMA remains a conditional alternative; its off-gondola upward antenna location, cable and attachment are unmodeled and require validation. Do not treat screened module-body clearance as a complete remote-antenna installation. Verify support for the 15g helix and connector-tightening loads, or remote-cable strain relief. Check LR24-F ground pairing and the Mini's 2W maximum-average reference against the shared 5V supply; peak demand and supply margin are unmeasured. No antenna or adhesive strength is certified by a passing clearance check.",
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
            "RS1102 motor screws and OEM X06 centre screws: lengths, heads and actual engagement remain unverified. Two unmodified manufacturer half arms and four M1 horn bolt/nut pairs are included; actual owned hardware must fit the declared envelope.",
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
        "structural_design_basis": "Ultralight indoor LTA gondola; lower stiffness than a sub-250g multirotor is accepted. First integrate parts with no necessary separation, make them manufacturable, then optimize their shape. Retain splits only for demonstrated assembly, motion or requested replacement functions. Redesign when the complete assembly improves in mass, simplicity, fit or serviceability, respecting current user constraints. The supported-input design requires six generic3x6x2.5 bearings, including the four already confirmed purchased; verify two additional matching bearings or spares without substituting flanged bearings. The design requirement does not record a new purchase. Allow modest mass increases for simpler integral parts and forgiving noncritical envelopes. Integrate fixed servo and output-bearing supports; retain individual servo and rotor serviceability. Use simple clearance or short slots where they reduce fit risk without adding parts; retain functional locating, torque and bearing surfaces. Do not add elaborate adjustment mechanisms. Compare complete torque/retention paths; minimize hardware varieties and omit unnecessary washers. Physical retention remains unverified.",
        "part_separation_reasons": PART_SEPARATION_REASONS,
        "scope": f"Indoor LTA blimp gondola including one {get_sensor_profile().model}: one flexible rail, two independently geared X06 main propulsors with bounded ±180deg output targets, compact battery and FC carriers, and one simple navigation/LR24-F-Mini accessory carrier. The FC and optical head share one common manually aligned and locked instrument platform. Each purchased {SELECTED_DRIVE.driver.teeth}T driver turns a {SELECTED_DRIVE.output.teeth}T output gear; no yaw motor or fin hardware is included.",
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
        "optical_stack_scope": "FC and one optical sensor share a rigid upper platform with a setup-only local-Y pitch clamp. Align to the chosen body reference attitude, then lock both M3 joints and reroute leads. No independent optical pitch, roll correction or active leveling. Actual IMU/optical/range origins and body-frame offsets are unmeasured; do not infer them from CAD attachment datums. Pointing, printed fit, clamp retention and creep remain unqualified.",
        "module_stations": [asdict(item) for item in MODULE_STATIONS],
        "module_layout_decision": MODULE_LAYOUT_DECISION,
        **release_status(),
    }
