"""Published equipment interfaces, without CAD or assumed mounting-stack heights.

Hole coordinates use the centre of each published mounting pattern/plan envelope.
No PCB bearing plane, screw length or damper compression is inferred from photos.
"""

FC_SOURCE = "https://micoair.cn/zh/docs/flight-controller/micoair743-aio-series/micoair743v2-aio-35a-manual"
FC_DIMENSION_SOURCE = "https://store.micoair.com/wp-content/uploads/2026/05/MicoAir743v2-AIO-35A_spec5.webp"
FC_PACKAGE_SOURCE = "https://store.micoair.com/wp-content/uploads/2026/05/MicoAir743v2-AIO-35A_spec6.webp"
FC_SIZE_MM = (36.0, 36.0, 8.0)
FC_HOLE_PITCH = 25.5
FC_HOLE_DIAMETER = 3.0
FC_HOLE_CENTRES = tuple((x, y) for x in (-12.75, 12.75) for y in (-12.75, 12.75))

PAS_SOURCE = (
    "https://ftp.nooploop.com/downloads/linktrack/LinkTrack_Datasheet_V2.3_zh.pdf"
)
PAS_SIZE_MM = (27.0, 32.0, 7.0)
PAS_HOLE_DIAMETER = 2.2
PAS_HOLE_PITCH = 23.0
PAS_HOLE_CENTRES = ((-11.5, -9.3), (11.5, -9.3))

LR_SOURCE = "https://micoair.cn/zh/docs/telemetry/lr900/lr900-telemetry"
LR_SIZE_MM = (29.5, 13.0, 9.0)
MTF02P_SOURCE = "https://micoair.cn/zh/docs/sensors/sensors/mtf-02-02p-sensors"
MTF02P_PRODUCT_SOURCE = "https://micoair.com/optical_range_sensor_mtf-02p/"
MTF02P_DIMENSION_IMAGE = "https://micoair.cn/api/media/file/docs/2026/07/66f661b664e82-df0e9d69d2-971f59dd57.webp"
MTF02P_PORT_IMAGE = "https://micoair.cn/api/media/file/docs/2026/07/66f66374dd95c-852bf87918-83cf12d631.webp"
MTF02P_SIZE_MM = (21.6, 16.0, 6.5)
MTF02P_MASS_G = 1.5
MTF02P_FLOW_FOV_DEG = 42.0
MTF02P_TOF_FOV_DEG = 2.0

JST_SH_SOURCE = "https://www.jst-mfg.com/product/pdf/eng/eSH.pdf"
JST_GH_SOURCE = "https://www.jst-mfg.com/product/pdf/eng/eGH.pdf"
XT30U_SOURCE = "https://www.china-amass.com/biao/268.html"
XT30U_FEMALE_DRAWING = (
    "https://www.china-amass.com/ueditor/php/upload/image/20251028/1761638904203736.png"
)
XT30U_MALE_DRAWING = (
    "https://www.china-amass.com/ueditor/php/upload/image/20251028/1761638917743053.png"
)
XT30U_MATED_DRAWING = (
    "https://www.china-amass.com/ueditor/php/upload/image/20251028/1761638924618397.png"
)
FC_PORT_IMAGE = "https://micoair.cn/api/media/file/docs/2026/09/micoair743-aio-35a-1-01-1-df3dbd14ac.webp"
LR_PORT_IMAGE = "https://micoair.cn/api/media/file/docs/2026/07/669f74a433137-ed5c3462e6-6d69324222.webp"
SERVO_SOURCE = "https://kstservos.com/products/x06-v6-0-hv-micro-digital-metal-gear-glider-1-8kg-torque-servo-motor"
X06_MANUFACTURER_SOURCE = "https://www.kstsz.com/kstsz_Product_2063755473.html"
X06_DATASHEET_SOURCE = "https://cdn.shopify.com/s/files/1/0570/1766/3541/files/X06_V6.0_Technical_Specifcation.pdf?v=1700472290"
# KST May 2023 drawing; nominal dimensions, not printed fit clearances.
# Longitudinal datum is the case end nearest the output spline; transverse datum
# is the case centreline. Depths below the case top exclude the projecting spline.
X06_CASE_SIZE_MM = (20.0, 7.0, 16.6)
X06_CASE_TOLERANCE_MM = 0.2
X06_OVERALL_HEIGHT_MM = 19.3
X06_EAR_SPAN_MM = 28.0
X06_EAR_HOLE_PITCH_MM = 24.0
X06_EAR_HOLE_DIAMETER_MM = 2.0
X06_OUTPUT_FROM_CASE_END_MM = 5.0
X06_EAR_TOP_FROM_CASE_TOP_MM = 3.7
X06_EAR_UNDERSIDE_FROM_CASE_TOP_MM = 4.7
HORN_SOURCE = (
    "https://kstservos.com/products/0415-13-aluminium-servo-arm-for-4mm-15t-servo"
)
HORN_DRAWING_SOURCE = "https://cdn.shopify.com/s/files/1/0712/1472/7353/files/15T-4mm_0415.13.png?v=1764920833"

GEAR_SOURCE = "https://jp.misumi-ec.com/vona2/detail/110302194440/"
GEAR_CATALOG_SOURCE = "https://jp.misumi-ec.com/pdf/fa/2015/p1_1553.pdf"
SHAFT_SOURCE = "https://jp.misumi-ec.com/vona2/detail/110302634310/"
SHAFT_CATALOG_SOURCE = "https://jp.misumi-ec.com/pdf/fa/2015/p1_145.pdf"
BEARING_SOURCE = (
    "https://www.nskmicro.co.jp/products/bearing/bearing_size_pdf/single_row_mm.pdf"
)
BEARING_FIT_SOURCE = "https://www.nskmicro.co.jp/technical_info/bearing/catalog05.pdf"

PROPULSION_EVIDENCE = {
    "X06": {
        "sources": [X06_MANUFACTURER_SOURCE, SERVO_SOURCE, X06_DATASHEET_SOURCE],
        "retained_evidence": "references/kst_x06_v6_datasheet.pdf",
        "document_date": "2023-05",
        "case_size_mm": X06_CASE_SIZE_MM,
        "case_tolerance_plus_minus_mm": X06_CASE_TOLERANCE_MM,
        "overall_height_with_spline_mm": X06_OVERALL_HEIGHT_MM,
        "ear_span_mm": X06_EAR_SPAN_MM,
        "ear_hole_pitch_mm": X06_EAR_HOLE_PITCH_MM,
        "ear_hole_diameter_mm": X06_EAR_HOLE_DIAMETER_MM,
        "output_from_near_case_end_mm": X06_OUTPUT_FROM_CASE_END_MM,
        "ear_top_from_case_top_mm": X06_EAR_TOP_FROM_CASE_TOP_MM,
        "ear_underside_from_case_top_mm": X06_EAR_UNDERSIDE_FROM_CASE_TOP_MM,
        "spline_teeth": 15,
        "spline_major_diameter_mm": 3.90,
        "spline_major_tolerance_plus_minus_mm": 0.01,
        "default_travel_deg": [-60.0, 60.0],
        "position_reference_us": [1000, 1500, 2000],
        "listed_mass_g": 6.0,
        "listed_mass_tolerance_percent": 10,
        "scope": "KST-authored May 2023 drawing obtained through the distributor. Regular-tab X06 V6.0, not X06H or X06N. Ear thickness is the 4.7 minus 3.7 mm drawing datum difference. Published case tolerance is not a fit allowance. Spline major diameter does not establish horn geometry or a retaining screw thread.",
        "unknown": "Supplied plastic horn dimensions and OEM retaining screw; selected stock aluminium horn seating, loaded travel and permissible external gear load.",
    },
    "KST_0415_13": {
        "sources": [HORN_SOURCE, HORN_DRAWING_SOURCE],
        "retained_evidence": "references/kst_0415_13_horn_dimensions.png",
        "spline_class": "KST 15T-4mm",
        "hub_diameter_mm": 6.0,
        "tip_diameter_mm": 4.0,
        "tip_centre_radius_mm": 13.2,
        "overall_axial_height_mm": 3.5,
        "blade_thickness_mm": 1.6,
        "spline_recess_depth_mm": 2.5,
        "centre_clearance_diameter_mm": 2.2,
        "counterbore_diameter_mm": 4.4,
        "hole_radius_by_diameter_mm": {
            "0.8": [4.5, 8.0, 11.5],
            "1.0": [6.8, 10.0, 13.2],
        },
        "scope": "KST-authored drawing supplied through a distributor. Nominal geometry supports a conservative blade-capture pocket with explicit fit allowance; exact outline fillets, tolerances, installed seating and OEM screw head/engagement remain sample checks. The centre clearance hole is not an M2 thread specification.",
    },
    "GEABP": {
        "sources": [GEAR_SOURCE, GEAR_CATALOG_SOURCE],
        "retained_evidence": "references/misumi_geabp_catalog.pdf",
        "selected_parts": ["GEABP0.5-60-3-B-3", "GEABP0.5-20-3-B-3"],
        "module_mm": 0.5,
        "pressure_angle_deg": 20.0,
        "bore_mm": 3.0,
        "bore_tolerance": "H7",
        "face_width_mm": 3.0,
        "total_axial_length_mm": 8.0,
        "hub_extension_mm": 5.0,
        "set_screw_axis_from_hub_end_mm": 2.5,
        "driver_pitch_outside_root_hub_diameters_mm": [30.0, 31.0, 28.75, 10.0],
        "driven_pitch_outside_root_hub_diameters_mm": [10.0, 11.0, 8.75, 8.5],
        "material": "White POM; no metal hub insert for this module",
        "included_fastener": "One M3 radial set screw per standard gear, SCM435 with black oxide finish; length, tip style and tightening torque are not established here.",
        "scope": "Catalog gear dimensions support simplified purchased envelopes. Tooth contact, backlash, hub strength and printed shaft-centre tolerances require physical qualification; a nominal 20 mm centre distance is not proof of mesh.",
    },
    "PSFU3": {
        "sources": [SHAFT_SOURCE, SHAFT_CATALOG_SOURCE],
        "retained_evidence": "references/misumi_psfu_shaft_catalog.pdf",
        "diameter_mm": 3.0,
        "diameter_tolerance": "h5: 2.996 to 3.000 mm",
        "standard_length_range_mm": [10, 400],
        "standard_length_increment_mm": 1,
        "end_chamfer_max_mm": 0.2,
        "selected_order_codes": [
            "PSFU3-26-FC5-A18",
            "PSFU3-24-FC5-A3",
            "PSFU3-14",
        ],
        "factory_flat": {
            "alteration": "FC: one set-screw flat",
            "depth_for_diameter3_mm": 0.5,
            "length_mm": 5.0,
            "input_offset_from_reference_end_mm": 18.0,
            "driven_offset_from_reference_end_mm": 3.0,
            "fc_and_a_increment_mm": 1,
            "fc_max_for_diameter3_mm": 15.0,
            "a_rule": "0 or at least2mm",
            "minimum_altered_length_for_d3_to_d12_mm": 20,
            "installation": "Clock each factory flat under the actual gear's radial M3 set screw after meshing its teeth. The drawing does not specify set-screw azimuth relative to tooth phase. Keep flats outside bearing journals. Factory machining only; no manual grinding of hardened plated shafts.",
        },
        "material": "SUJ2 / EN 1.3505 equivalent hardened steel with hard chrome plating",
        "scope": "The 26mm input and24mm driven shafts use specified factory flats; the14mm idle shafts remain round. None has a shoulder, thread or inherent axial retention. Diameter tolerance does not specify length tolerance or guarantee a bearing slip fit. Supplier confirmation of the complete configured order code remains necessary.",
    },
    "MR63ZZ": {
        "sources": [BEARING_SOURCE, BEARING_FIT_SOURCE],
        "retained_evidence": [
            "references/nsk_isc_miniature_bearings.pdf",
            "references/nsk_isc_bearing_fits.pdf",
        ],
        "catalog_printed_pages": [40, 41],
        "bore_outside_width_mm": [3.0, 6.0, 2.5],
        "reference_mass_g": 0.27,
        "inner_ring_abutment_outer_diameter_max_mm": 3.7,
        "housing_abutment_opening_diameter_min_mm": 5.4,
        "abutment_fillet_max_mm": 0.1,
        "scope": "Use shielded MR63ZZ abutment columns, not open MR63 values. Large gear hubs must not touch bearing shields or outer rings. h5 is a catalog transition-fit option, not guaranteed hand assembly; printed seats are not precision H6 bores. Axial retention, fits and preload require sample verification.",
    },
}

# Connector-local dimensions, not positions on the equipment PCB. Device manuals
# name SH/GH families but do not identify the fitted manufacturer's part number.
# JST catalog dimensions therefore do not certify an unidentified compatible part.
CONNECTOR_EVIDENCE = {
    "JST_SH_4P": {
        "source": JST_SH_SOURCE,
        "retained_evidence": "references/jst_sh_connectors.pdf",
        "catalog_pages": [1, 2],
        "pitch_mm": 1.0,
        "standard_housing": "SHR-04V-S",
        "protrusion_housing": "SHR-04V-S-B",
        "standard_housing_width_mm": 5.0,
        "protrusion_housing_width_mm": 7.0,
        "housing_mating_axis_length_mm": 5.0,
        "housing_thickness_mm": 2.8,
        "side_entry_assembly_reference_depth_mm": 6.25,
        "side_entry_assembly_reference_height_mm": 2.95,
        "top_entry_assembly_reference_height_mm": 6.3,
        "wire_insulation_od_range_mm": [0.4, 0.8],
        "scope": "Nominal JST housing dimensions and catalog reference assembly dimensions. Assembly depth includes the header; it is not projection beyond a PCB edge. Installed header variant, board coordinates, withdrawal stroke, cable bend radius and compatible seller parts are unverified.",
    },
    "JST_SH_6P": {
        "source": JST_SH_SOURCE,
        "retained_evidence": "references/jst_sh_connectors.pdf",
        "catalog_pages": [1, 2],
        "pitch_mm": 1.0,
        "standard_housing": "SHR-06V-S",
        "protrusion_housing": "SHR-06V-S-B",
        "standard_housing_width_mm": 7.0,
        "protrusion_housing_width_mm": 9.0,
        "housing_mating_axis_length_mm": 5.0,
        "housing_thickness_mm": 2.8,
        "side_entry_assembly_reference_depth_mm": 6.25,
        "side_entry_assembly_reference_height_mm": 2.95,
        "top_entry_assembly_reference_height_mm": 6.3,
        "wire_insulation_od_range_mm": [0.4, 0.8],
        "scope": "Nominal JST housing dimensions and catalog reference assembly dimensions. Assembly depth includes the header; it is not projection beyond a PCB edge. Installed header variant, board coordinates, withdrawal stroke, cable bend radius and compatible seller parts are unverified.",
    },
    "JST_GH_4P": {
        "source": JST_GH_SOURCE,
        "retained_evidence": "references/jst_gh_connectors.pdf",
        "catalog_pages": [2, 3],
        "pitch_mm": 1.25,
        "housing": "GHR-04V-S",
        "housing_width_mm": 6.25,
        "housing_mating_axis_length_mm": 5.7,
        "housing_thickness_mm": 4.15,
        "header_width_mm": 8.25,
        "side_entry_assembly_reference_depth_mm": 7.15,
        "side_entry_assembly_reference_height_mm": 4.35,
        "top_entry_assembly_reference_height_mm": 7.3,
        "wire_insulation_od_range_mm": [0.76, 1.0],
        "scope": "Nominal JST housing dimensions and catalog reference assembly dimensions. Assembly depth includes the header; it is not projection beyond a PCB edge. Installed header variant, latch access, board coordinates, withdrawal stroke, cable bend radius and compatible seller parts are unverified.",
    },
    "AMASS_XT30U": {
        "source": XT30U_SOURCE,
        "drawing_sources": [
            XT30U_FEMALE_DRAWING,
            XT30U_MALE_DRAWING,
            XT30U_MATED_DRAWING,
        ],
        "retained_evidence": [
            "references/xt30u_female_dimensions.png",
            "references/xt30u_male_dimensions.png",
            "references/xt30u_mated_dimensions.png",
        ],
        "female_overall_length_mm": 12.4,
        "male_overall_length_mm": 13.7,
        "individual_length_tolerance_plus_minus_mm": 0.3,
        "mated_length_mm": 20.1,
        "mated_length_tolerance_plus_minus_mm": 0.5,
        "mated_max_length_mm": 20.6,
        "mated_cross_section_mm": [10.2, 5.6],
        "cross_section_tolerance_plus_minus_mm": [0.3, 0.3],
        "mated_max_cross_section_mm": [10.5, 5.9],
        "withdrawal_stroke_mm": None,
        "scope": "AMASS XT30U two-pole wire connector dimensions including solder terminals, excluding soldered wires and insulation. Cross-section width comes from the individual connector drawings; mated height and length come from the mating drawing. No cable bend radius, heat-shrink envelope, mounting datum or manufacturer withdrawal stroke is published here.",
    },
}

DEVICE_CONNECTOR_EVIDENCE = {
    "FC": {
        "sources": [FC_SOURCE, FC_PORT_IMAGE],
        "retained_evidence": ["references/micoair743v2_aio35a_ports.webp"],
        "documented_types": ["SH1.0-6P", "SH1.0-4P", "USB Type-C"],
        "catalog_references": ["JST_SH_6P", "JST_SH_4P"],
        "documented_interfaces": "Three SH1.0-6P connectors: UART3/I2C, UART1/UART6, and DJI O3/O4. One SH1.0-4P connector: UART4. USB Type-C and additional solder pads are identified.",
        "orientation_evidence": "The labeled front/back port image identifies board edges and underside connectors. The simplified CAD envelope and mounting-hole axes do not register individual port datums or the pinout image's frame.",
        "installed_port_centres_mm": None,
        "installed_port_datums_verified": False,
        "unknown": "Individual port XYZ, exact header variants, plugged cable envelopes, wire bend radii and actual PCB bearing plane.",
        "connection_limit": "Port family and pin count do not establish electrical compatibility. The DJI SH1.0-6P connector supplies 12 V; it is not a general 5 V sensor connector. Use the official device pinout before choosing a harness.",
    },
    "LR": {
        "sources": [LR_SOURCE, LR_PORT_IMAGE],
        "documented_types": ["GH1.25-4P", "USB Type-C", "SMA"],
        "catalog_references": ["JST_GH_4P"],
        "documented_interfaces": "UART GH1.25-4P, USB Type-C and SMA antenna socket with external thread and female centre contact. The LR900-A body dimensions exclude the SMA socket.",
        "orientation_evidence": "The official LR900-A port image shows GH and SMA at opposite ends of the long board axis. It does not dimension their centres or register either end to the simplified CAD frame. LR900-F/P mechanical drawings are not LR900-A evidence.",
        "installed_port_centres_mm": None,
        "installed_port_datums_verified": False,
        "unknown": "LR900-A connector XYZ, SMA socket/antenna dimensions, USB plug body and actual wire bend radii.",
        "connection_limit": "Use the UART port for the FC connection. The manual identifies USB as a computer interface; same pin count as an SH connector does not make the connector families or cable pinouts interchangeable.",
    },
    "PAS": {
        "sources": [PAS_SOURCE],
        "retained_evidence": ["references/linktrack_datasheet_v2_3_zh.pdf"],
        "documented_types": ["GH1.25-4P"],
        "catalog_references": ["JST_GH_4P"],
        "documented_interfaces": "Two parallel UART GH1.25-4P ports; use one only. Figures 5 and 42 show side-entry and top-entry alternatives at the connector end.",
        "orientation_evidence": "With the drawing's antenna toward +Y, the connector end is -Y. The side-entry port opens outward toward -Y and the top-entry alternative away from its PCB face. The lower connector band is dimensioned 19 mm wide; individual port centres and their PCB Z are not dimensioned.",
        "connector_band_width_mm": 19.0,
        "installed_port_centres_mm": None,
        "installed_port_datums_verified": False,
        "unknown": "Individual port XYZ and PCB bearing plane, plugged latch access and actual wire bend radii.",
        "connection_limit": "Use one of the parallel ports and verify the chosen port's published wiring orientation; no harness pinout is inferred from housing orientation.",
    },
    "MTF02P": {
        "sources": [MTF02P_SOURCE, MTF02P_DIMENSION_IMAGE, MTF02P_PORT_IMAGE],
        "retained_evidence": [
            "references/mtf02p_dimensions.webp",
            "references/mtf02p_ports.webp",
        ],
        "documented_types": ["SH1.0-4P"],
        "catalog_references": ["JST_SH_4P"],
        "documented_interfaces": "One SH1.0-4P UART connector.",
        "orientation_evidence": "The dimension image shows the connector on the right edge of the 21.6 x 16 mm optical-face view. Calling this +X requires adopting that drawing orientation; the prior symmetric CAD envelope alone does not verify installed yaw or connector Y/Z coordinates.",
        "installed_port_centres_mm": None,
        "installed_port_datums_verified": False,
        "unknown": "Port Y/Z and header datum, plugged cable envelope, actual wire bend radius and installed sensor yaw.",
        "connection_limit": "Keep the cable outside the optical face and optical reservation. Match the official pinout and firmware orientation to the installed module.",
    },
    "SERVO": {
        "sources": [SERVO_SOURCE, X06_DATASHEET_SOURCE],
        "retained_evidence": ["references/kst_x06_v6_datasheet.pdf"],
        "documented_types": ["Three-contact PWM lead; connector family unverified"],
        "catalog_references": [],
        "documented_interfaces": "KST X06 V6.0 datasheet identifies orange signal, red supply and brown ground. The pictured three-contact connector has no dimensioned family or cable specification.",
        "orientation_evidence": "No dimensioned lead-exit datum is published in the retained mechanical drawing.",
        "installed_port_centres_mm": None,
        "installed_port_datums_verified": False,
        "unknown": "Plug family, cable length/diameter, lead-exit coordinates and bend radius; do not infer a JST, JR or other connector standard from the picture.",
        "connection_limit": "Retain an explicit design routing allowance until the supplied lead is checked. Published voltage range is 3.8–8.4 V; the supply branch and connector pin order must match the installed unit.",
    },
}

MOUNTING_EVIDENCE = {
    "FC": {
        "sources": [FC_SOURCE, FC_DIMENSION_SOURCE, FC_PACKAGE_SOURCE],
        "verified": "25.5 x 25.5 mm hole pattern, diameter 3 mm; 45 degree installation; four included M2 x 7.5 mm silicone dampening sleeves.",
        "unknown": "PCB thickness and bearing-plane elevation; sleeve outside/groove dimensions, compressed height and actual screw length. The 8 mm overall envelope does not define those interfaces.",
        "installation": "Use the purchased insulating dampers. Keep both sides and ESC MOS regions ventilated; do not cover them with foam, adhesive or wiring.",
    },
    "PAS": {
        "sources": [PAS_SOURCE],
        "verified": "Page 44 Figure 42: two diameter 2.2 mm holes, 23 mm apart, 6.7 mm from the connector-side lower envelope edge. Page 9 Figure 5 identifies M2 mounting and two parallel GH1.25 UART ports; use one port.",
        "unknown": "PCB bearing-plane elevation and fastener length. Page 19 lists 7 mm overall height while Figure 42 shows 5.3 mm; the conservative 7 mm envelope is retained.",
        "installation": "Drawing frame: width X=27, length Y=32, antenna toward +Y. Keep the antenna region clear; no unprovided antenna keepout dimension is invented.",
    },
    "LR": {
        "sources": [LR_SOURCE],
        "verified": "LR900-A 29.5 x 13 x 9 mm excludes the SMA antenna socket; UART GH1.25-4P and USB Type-C.",
        "unknown": "No verified mounting-hole pattern, underside bearing plane, SMA socket/antenna envelope or plugged cable clearance.",
        "installation": "Insulating adhesive remains provisional; the LR900-F/P mechanical model is not evidence for the LR900-A.",
    },
    "MTF02P": {
        "sources": [MTF02P_SOURCE, MTF02P_DIMENSION_IMAGE, MTF02P_PORT_IMAGE],
        "verified": "21.6 x 16 x 6.5 mm, 1.5 g; SH1.0-4P connector; optical-flow FOV 42 degrees and ToF FOV 2 degrees.",
        "unknown": "No verified mounting-hole pattern, backside adhesive contact, exact optical origins or plugged cable clearance.",
        "installation": "Insulating adhesive remains provisional. Optical face points away from the balloon; match firmware rotation to the purchased unit.",
    },
}
