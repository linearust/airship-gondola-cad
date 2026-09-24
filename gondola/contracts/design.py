"""User decisions and unresolved interfaces consumed by CAD and the CLI.

Part geometry belongs to gondola/parts; published interface dimensions belong to
the other contract modules. Geometric test success never changes release status.
"""

from dataclasses import asdict, dataclass

from .drive import SELECTED_DRIVE
from .equipment_interfaces import X06_DATASHEET_SOURCE, X06_MANUFACTURER_SOURCE
from .fasteners import KIT_MATERIAL

NOTION_URL = "https://app.notion.com/p/3e3ee52b5792806c94acc1f798594bad"
NOTION_LAST_EDITED = "2026-09-22T05:48:39.341Z"
CREALLO_GUIDE_URL = "https://creallo.com/ko/guide/design-spec-guide"
DESIGN_REVISION = "AO"
# Nominal local part dimensions, before print rotation; not delivered-size tolerance.
MAX_PRINT_PART_DIMENSION_MM = 340.0
RAIL_LENGTH_MM = MAX_PRINT_PART_DIMENSION_MM
# Project structural interface, independent of the FC mounting-hole pattern.
STACK_PITCH_MM = 48.0
STACK_ANCHOR_CENTRES = tuple(
    (sign * STACK_PITCH_MM / 2, sign * STACK_PITCH_MM / 2) for sign in (-1, 1)
)
STACK_ANCHOR_LOCATIONS = (
    " and ".join(f"({x:g}, {y:g})" for x, y in STACK_ANCHOR_CENTRES) + " mm"
)
PUBLISHED_PROCESS_SIZE_MM = {"SLS": [340, 340, 600], "MJF": [380, 380, 280]}
MANUFACTURING_DECISION = {
    "reviewed_on": "2026-09-23",
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
    "qualification": "Not qualified: obtain one-piece acceptance and review rail flexures, straightness, curvature, fatigue and sliding fit. Use the same agreed unfilled PA12 process/material/finish and corresponding feature orientation for coupons and full parts. Verify the optical tower's broad clamped seats for flatness, pointing stability and creep with actual fasteners.",
    "nominal_general_functional_wall_mm": 1.5,
    "nominal_rail_flexure_mm": 1.2,
    "flexure_exception": "The narrow 1.2 mm flexure is intentionally below the 1.5 mm general wall target; supplier review and full-length bend/fatigue testing remain mandatory. Longer 4.5 mm reliefs offset some added bending stiffness.",
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
    "rail_and_carriers": "Carriers slide for trim and detach for assembly; each shoe is integral with its equipment deck or common propulsion frame. Match the close-running T-head width and height with the existing rail/shoe coupons before printing the complete carriers. The fit should move with deliberate hand pressure without perceptible rocking or free sliding; raw print tolerance cannot guarantee that acceptance. Keep the web relieved rather than creating a competing tight datum. The existing M2 clamp remains additional position retention against the solid head; verify actual screw-tip bearing and PA12 creep. Geometry alone does not establish insertion or holding force. Preserve checked L-key access without piercing the bearing posts.",
    "servo_bridge_and_frame": "Both servos and complete input drives leave as one bench-service module after removing the two small output gears and two M2 mount pairs. Output shafts, captured bearings and motor carriers stay installed. Both servo windows share one thick central upright, directly supported through the central bridge plate by the frame's broad central seat. Two broad straight arms join its outer mounting feet while unused side regions remain open. Two rectangular local seats and fixed X/Y datums retain the existing M2 mounting arrangement. Check all seating planes for flatness; do not pull a warped part into contact with its screws.",
    "bearings_and_frame": "Four 3x6x2.5 ball bearings are captured at their outer rings by integral outer shoulders and releasable inward PA12 latches. No bought bearing spacers, push-on rings, separate caps or cap fasteners. Continuous seats and remaining fixed guide sectors support the bearings; separate carrier/frame stops limit rotor travel. Insert or release bearings with the carrier and shafts removed; qualify the full-size coupon for actual fit, shield clearance, latch deflection, release access and creep before manufacturing the frame.",
    "motor_carriers_and_frame": "Independent powered rotation; each carrier already integrates the motor plate, guard, struts and shaft clamps.",
    "horn_and_adapter": "Use each X06 supplied horn with its genuine spline and OEM centre screw. A one-piece flat adapter blank is locally prepared with the actual horn using the centring jig and documented machining zone. The displayed prepared horn is an acceptance example, not measured supplied hardware. Do not reproduce a spline or assume the old 0415.13 outline. Preserve coaxial registration and gear plane, adequate edge distances and two-way torque retention. Original screw access and the ordered coupling removal path remain required. No separate rear strap or permanent alignment jig.",
    "optical_head": "Three printed parts provide two independently lockable manual alignment axes. The base is one open rectangular portal with its top beam flush with the two legs; broad feet clamp directly onto either host with two ordinary M2x8 screws and M2 hex nuts. Remove the host carrier from the rail for bench access to the foot fasteners, then lift the complete tower for service or transfer. No designed axial seating gap; clearance holes allow registration before tightening. Both foot clamps and angle clamps retain fasteners because optical pointing requires stable contact and friction. Physical retention and creep require testing.",
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
    "MG-A01 M10 Ultra",
    "servo Y harness (separate user project)",
)
PURCHASED_HARDWARE_QUANTITIES = {
    "M2X8_BUTTON_HEAD": 13,
    "M2X6_BUTTON_HEAD": 2,
    "M2_HEX_NUT": 15,
    "M1_6X8_PAN_HEAD_KIT": 8,
    "M1_6_HEX_NUT_DIN934": 8,
    SELECTED_DRIVE.driver.sku: 2,
    SELECTED_DRIVE.output.sku: 2,
    "BEARING_3X6X2_5": 4,
    "SS304_CUT3_L24_FLAT5_A0": 2,
    "SS304_CUT3_L14": 2,
    "SS304_CUT3_L18_FLAT18_A0": 2,
    "KST_X06_SUPPLIED_HORN": 2,
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
    "SS304_CUT3_L24_FLAT5_A0": "304 stainless steel (seller claim)",
    "SS304_CUT3_L14": "304 stainless steel (seller claim)",
    "SS304_CUT3_L18_FLAT18_A0": "304 stainless steel (seller claim)",
    "KST_X06_SUPPLIED_HORN": "Supplied horn material unverified",
}

EXPECTED_INVENTORY = {
    "rails": 1,
    "equipment_mounts": 2,
    "tilting_propulsors": 2,
    "installed_prints": 12,
    "optical_mount_parts": 3,
    "fit_coupons": 4,
    "purchased_hardware": sum(PURCHASED_HARDWARE_QUANTITIES.values()),
    "purchased_hardware_types": len(PURCHASED_HARDWARE_QUANTITIES),
    "unique_print_files": 14,
}

OPTICAL_STACK_HOST = "BatteryEquipmentModule"
# Electronics turns to keep P-AS away from propulsion. Re-clock the square FC
# mounting pattern to retain the prior world-heading design basis; actual port
# datums and the assembled flight-controller orientation remain to be verified.
FC_INSTALLATION_LOCAL_YAW_DEG = 180.0
MODULE_LAYOUT_DECISION = {
    "layout": "Three independently positioned rail groups: propulsion near the rail centre, battery carrier on +X and FC/electronics on -X behind the neutral motors.",
    "trim": "Default stations are a wiring and clearance arrangement, not a verified mass balance. Reposition the battery carrier for the actual pack or an empty carrier with external power; weigh the complete assembly and recheck cable slack, clearances and support after trim. No PSU connector or electrical supply change is specified here.",
    "electronics": "Rotate the electronics carrier 180deg about Z so the P-AS support points away from propulsion. Rotate the FC a further 180deg relative to that carrier to preserve the earlier world-heading design basis and underbody wire-corridor side. Exact board heading, ports and firmware orientation must be checked on the physical board.",
    "optical": "Keep MTF-02P on the transferable manually aligned stack, independent of the three mass groups. Either carrier provides the same structural anchors; host changes require renewed optical field-of-view and wiring checks.",
    "service": "Keep the paired servo/input-drive module removable from the propulsion/output frame. Disconnect external harnesses before changing module stations or removing modules.",
}

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
        "Small nylon cable ties, strap width at most2.5mm, around existing frame arms; quantity after routing. Route around the solid bearing-post roots and preserve the local rail-clamp tool bay. Keep tie heads outside moving parts and do not pull the phase-wire loop taut. No printed cable clips or assumed route through the bearing posts.",
        "Flexible pre-crimped SH/GH pigtails, insulating heat-shrink and strain relief; select wire gauge and lengths for the actual load and route.",
        "XT30-family pigtail compatible with the purchased battery; compact AMASS XT30U is the dimensional reference, not confirmation of the supplied battery connector variant.",
    ],
    "seller_or_completed_harness_verified": False,
    "stock_replacement_decision": "Use already-owned M2 metal screws/nuts and GH1.25 connectors, selected micro-screw kit, OEM supplied X06 horns, gears, nominal-3mm 304 rods and 3x6x2.5 ball bearings. No purchase of bearing spacers or separate 0415.13 horns. Print the rail, carriers, integral bearing retention, removable paired-servo bridge and prepared supplied-horn adapters. The centring jig and fit coupons are bench tools, not installed parts.",
}


@dataclass(frozen=True)
class ModuleStation:
    object_name: str
    x_mm: float
    clamp_control: str
    default_approach: str
    yaw_deg: int = 0

    def __post_init__(self):
        if self.yaw_deg not in (0, 180):
            raise ValueError("Rail module orientation must be 0 or 180 degrees")

    @property
    def transverse_sign(self):
        """Convert module-local transverse directions to the fixed rail frame."""
        return 1 if self.yaw_deg == 0 else -1


MODULE_STATIONS = (
    ModuleStation("BatteryEquipmentModule", 90, "BatteryClampApproach", "NegativeY"),
    ModuleStation("MainPropulsionModule", 0, "PropulsionClampApproach", "PositiveY"),
    ModuleStation(
        "ElectronicsEquipmentModule", -72, "ElectronicsClampApproach", "PositiveY", 180
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
        "Verify the actual supplied X06 horn against the adapter preparation envelope. Keep its spline and OEM screw intact. Centre the horn and adapter with the bench jig, prepare attachment holes only in sound material with sufficient edge distance, then verify assembled runout and loaded retention in both directions. The displayed horn and fastener arrangement are a preparation example, not a measured part. Verify actual blade thickness, installed height, screw-head protrusion, safe nut engagement and OEM screw access. The D-socket and nominal-3mm 304 stub retain the original gear bore and gear plane. Direct gear loading, PA12 creep and servo output radial-load capacity remain unqualified.",
    ),
    UnresolvedInterface(
        "servo_ear_retention",
        "X06 drawing publishes two diameter 2 mm ear holes at 24 mm pitch and ear surfaces 3.7/4.7 mm below the case top. Verify actual ear contact, case tolerance, selected mounting screws and engagement. Both sets of mounting ears seat on one common upright with 3 mm outside walls and a solid central web. The bridge plate bears directly on a broad central frame seat; the paired servo module remains removable. Check fore-aft bending, retained gear spacing and PA12 creep under load. Follow the checked ordered gear, coupling and servo extraction paths; free the leads and confirm the actual wire exit and handling access. Rigid CAD clearance does not establish installed stiffness or a physical assembly fit.",
    ),
    UnresolvedInterface(
        "gear_mesh_and_shaft_retention",
        f"Check the purchased {SELECTED_DRIVE.driver.teeth}T/{SELECTED_DRIVE.output.teeth}T selected seller pair at nominal {SELECTED_DRIVE.center_distance_mm:g} mm centre distance, backlash, centre alignment, set-screw retention and PA12 creep. Both servo cradles form one removable ratio-specific bridge on the common output-bearing frame. The supported configuration is 48T/16T only; another ratio or servo requires redesigned replacement parts and renewed validation. A broad central Z seat, two local mounting seats and unilateral X/Y datums establish its position; two M2 bolts clamp it without adjustment slots. Check that the two outer seats are coplanar with each other and that all three corresponding contact faces, including the higher central seat, seat simultaneously; reject rocking. Servo ear clearance, seating error, print distortion and creep affect the mesh. Measure both assembled centre distances and backlash; correct/reprint the bridge if required rather than elongating holes, forcing gears or pulling a warped bridge flat with the bolts. Qualify the selected generic 3×6×2.5 bearing and Ø3 304 rod fits, integral outer-ring shoulders/latches, fixed guide support, shield clearance and independent carrier/frame axial stops. Measure the bearing pocket, released-latch clearance, frame spacing and carrier width together; reject preload, shield rubbing, weak latch retention or excess endplay. Follow the inward bearing insertion and retracted-shaft assembly path; printed flexure recovery and retention need a physical coupon. Rod tolerance evidence is waived as a design blocker; deburr cut ends and measure before insertion, never force the shaft through bearings. A dimensionally equivalent precision Ø3 shaft is a fallback without changing nominal CAD; recheck fits and torque grip. Shaft friction retention and preload remain unqualified. Confirm purchased M3 screw lengths/tips and protrusion before running; those screw solids are not yet modeled.",
    ),
    UnresolvedInterface(
        "electronic_mounting_stack",
        "FC and P-AS hole XY are confirmed. Measure PCB bearing planes, supplied FC M2x7.5 silicone sleeve geometry, purchased spacer lengths and screw engagement. Preserve at least the allocated 8mm FC underbody wiring clearance; no completed mounting stack is claimed.",
    ),
    UnresolvedInterface(
        "physical_retention",
        "Match and finish the rail/shoe coupons for deliberate hand insertion without perceptible rocking or free sliding; raw printing may produce either binding or excessive clearance. Correct the channel or reprint after coupon measurement rather than forcing a jammed full-length rail. Then perform loaded tests of tape, additional friction clamps, PA12 flexure life and bearing supports. The rail clamp acts across the solid T head and retains local screw-tip pressure; verify a burr-free received tip, opposed seating and no indentation or creep at the minimum useful hand tightening. No qualified tightening torque or holding force is specified. Check the selected 1.5mm L-key against the modeled short-arm access envelope and confirm the working stroke with actual socket engagement. Continuous post roots remove the former key tunnels but do not establish a strength rating.",
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
        "Seat both broad tower feet directly on the host and tighten two ordinary M2x8 screws with M2 hex nuts. Verify printed flatness, actual hole and screw dimensions, full nut engagement, holding friction and PA12 creep; no pad or spring preload is assumed. Clearance holes permit registration before tightening, not operating movement. Reject rocking or slip under cable loads and recheck vertical sensor aim and pivot friction on both hosts. Disconnect wiring and remove the host carrier from the rail for bench service; underside tool access around the balloon is not established. Support the tower, remove its nuts and withdraw the screws downward before lifting it. Reinstall the carrier, check rail retention and re-trim. Physical stiffness and retention remain unqualified.",
    ),
    UnresolvedInterface(
        "rc_and_heading_installation",
        "The cart selects a RadioMaster XR2 receiver; MG-A01 is explicitly excluded by the user. The heading-reference device remains unselected. Their mounting positions, antenna/interference clearances and harnesses are not represented by this CAD. Select and verify these interfaces separately; the scoped CAD equipment subtotal excludes them and the UART purchase plan is not a complete vehicle harness list.",
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
            "RS1102 motor mounting screws and OEM X06 horn-retaining screws: lengths, heads and actual engagement remain unverified. Supplied horns and modeled adapter hardware are included; no separate horn purchase is required.",
            "Four M3 gear set screws: thread confirmed, exact length/tip/protrusion and inclusion not verified; procure later after measuring the actual hubs.",
            "Tape, adhesive, wiring, connectors, insulation, strain relief, antennas, capacitor and other unmodeled accessories.",
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
        "structural_design_basis": "Ultralight indoor LTA gondola; lower stiffness than a sub-250g multirotor is accepted. First integrate parts with no necessary separation, make them manufacturable, then optimize their shape. Retain splits only for demonstrated assembly, motion or requested replacement functions. Existing geometry and purchased-part selections are not constraints: redesign when the complete assembly improves in mass, simplicity, fit or serviceability. Allow modest mass increases for simpler integral parts and forgiving noncritical envelopes. Preserve the intentionally removable paired-servo/input-gear module. Use simple clearance or short slots where they reduce fit risk without adding parts; retain functional locating, torque and bearing surfaces. Do not add elaborate adjustment mechanisms. Compare complete torque/retention paths; minimize hardware varieties and omit unnecessary washers. Physical retention remains unverified.",
        "part_separation_reasons": PART_SEPARATION_REASONS,
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
        "optical_stack_scope": f"Common structural tower anchors at {STACK_ANCHOR_LOCATIONS} on battery and electronics carriers; two outboard M2 clamps seat broad integral feet directly on their host. An integral PA12 tower supports a manually locked two-axis optical head, independent of the FC soft-mount stack. Actual dimensions, clearance-hole registration bounds and fastener acceptance belong to parts/stack_interface.py. Physical retention/pointing qualification remains required.",
        "module_stations": [asdict(item) for item in MODULE_STATIONS],
        "module_layout_decision": MODULE_LAYOUT_DECISION,
        "notion_source": NOTION_URL,
        "notion_last_edited": NOTION_LAST_EDITED,
        "notion_source_scope": "The retained timestamp identifies the last reviewed live page. Its mechanical BOM, adjustable gear-spacing description and PETG fabrication baseline differ from the CAD. The user deferred document discussion until design review is complete; agree proposed changes before editing Notion. No document alignment is claimed.",
        **release_status(),
    }
