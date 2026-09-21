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
FC_INCLUDED_DAMPER_COUNT = 4
FC_INCLUDED_DAMPER_FASTENER_SIZE = "M2"
FC_INCLUDED_DAMPER_LISTED_LENGTH = 7.5

PAS_SOURCE = (
    "https://ftp.nooploop.com/downloads/linktrack/LinkTrack_Datasheet_V2.3_zh.pdf"
)
PAS_SIZE_MM = (27.0, 32.0, 7.0)
PAS_HOLE_DIAMETER = 2.2
PAS_HOLE_PITCH = 23.0
PAS_HOLE_FROM_CONNECTOR_EDGE = 6.7
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
SERVO_SOURCE = "https://www.dspowerservo.com/ds-m005-mini-servo-product/"

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
        "sources": [SERVO_SOURCE],
        "documented_types": [],
        "catalog_references": [],
        "documented_interfaces": "The reviewed DS-M005 manufacturer page and mechanical drawing do not specify its cable connector type or cable dimensions.",
        "orientation_evidence": "No dimensioned lead-exit datum is published in the retained mechanical drawing.",
        "installed_port_centres_mm": None,
        "installed_port_datums_verified": False,
        "unknown": "Plug family, cable length/diameter, lead-exit coordinates and bend radius. Do not turn seller-specific JR or cable-length options into a manufacturer-confirmed interface.",
        "connection_limit": "Retain an explicit design routing allowance until the supplied servo lead is checked; do not fabricate an exact plug envelope or pinout.",
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
