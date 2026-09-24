"""Published equipment interfaces, without CAD or assumed mounting-stack heights.

Hole coordinates use the centre of each published mounting pattern/plan envelope.
No PCB bearing plane, screw length or damper compression is inferred from photos.
"""

from copy import deepcopy

from .drive import GEARS
from .optical_sensors import SENSOR_PROFILES

FC_MODEL = "MicoAir743v2-AIO-45A"
FC_LISTED_MASS_G = 10.0
FC_ESC_FIRMWARE = "AM32"
FC_SOURCE = "https://micoair.cn/zh/docs/flight-controller/micoair743-aio-series/micoair743v2-aio-45a-manual"
FC_PRODUCT_SOURCE = "https://micoair.com/flightcontroller_micoair743v2_aio_45a/"
FC_SPECIFICATION_SOURCE = "https://store.micoair.com/wp-content/uploads/2025/03/H743V2-AIO_Specifications.webp"
FC_PACKAGE_SOURCE = (
    "https://store.micoair.com/wp-content/uploads/2025/03/H743V2-AIO_Package.webp"
)
FC_SIZE_MM = (36.0, 36.0, 8.0)
FC_HOLE_PITCH = 25.5
FC_HOLE_DIAMETER = 3.0
FC_HOLE_CENTRES = tuple(
    (x_sign * FC_HOLE_PITCH / 2, y_sign * FC_HOLE_PITCH / 2)
    for x_sign in (-1, 1)
    for y_sign in (-1, 1)
)
FC_PORT_IMAGE = "https://micoair.cn/api/media/file/docs/2026/07/67d99cd088539-3afa75c002-90182857a6.webp"
FC_ELECTRICAL_EVIDENCE = {
    "esc_firmware": FC_ESC_FIRMWARE,
    "advertised_current_per_channel_a": 45,
    "esc_channels": 4,
    "bec_outputs": [
        {"voltage_v": 5, "current_a": 2},
        {"voltage_v": 12, "current_a": 2},
    ],
    "input_claims": {
        "manual_text": {"cells": [3, 6], "voltage_v": [10, 27], "source": FC_SOURCE},
        "port_diagram": {
            "cells": [2, 6],
            "voltage_v": [5.6, 27],
            "source": FC_PORT_IMAGE,
        },
        "specification_image": {"cells": [2, 6], "source": FC_SPECIFICATION_SOURCE},
    },
    "compatibility_status": "unresolved_official_source_conflict",
    "scope": "Official 45A text and AM32-labeled port diagram disagree on minimum battery voltage. Keep both claims; neither CAD fit nor the selected product title resolves the actual revision's 2S support. Current ratings are catalog values, not this assembly's tested current or shared BEC headroom. AM32 replaces the prior Bluejay selection; verify actual firmware, motor direction, DShot and any reversible-output settings independently.",
}


def flight_controller_contract():
    """One selected board shared by native identity, inventory and verification."""
    return {
        "model": FC_MODEL,
        "listed_mass_g": FC_LISTED_MASS_G,
        "size_mm": FC_SIZE_MM,
        "hole_pitch_mm": FC_HOLE_PITCH,
        "hole_diameter_mm": FC_HOLE_DIAMETER,
        "sources": [
            FC_SOURCE,
            FC_PRODUCT_SOURCE,
            FC_SPECIFICATION_SOURCE,
            FC_PORT_IMAGE,
        ],
        "electrical": deepcopy(FC_ELECTRICAL_EVIDENCE),
    }


PAS_SOURCE = (
    "https://ftp.nooploop.com/downloads/linktrack/LinkTrack_Datasheet_V2.3_zh.pdf"
)
PAS_SIZE_MM = (27.0, 32.0, 7.0)
PAS_HOLE_DIAMETER = 2.2
PAS_HOLE_PITCH = 23.0
PAS_HOLE_CENTRES = ((-11.5, -9.3), (11.5, -9.3))

LR_SOURCE = "https://micoair.cn/zh/docs/telemetry/lr900/lr900-telemetry"
LR_SIZE_MM = (29.5, 13.0, 9.0)
MTF02P_SOURCE = SENSOR_PROFILES["MTF02P"].source
MTF02P_DIMENSION_IMAGE = SENSOR_PROFILES["MTF02P"].dimension_source
MTF02P_PORT_IMAGE = SENSOR_PROFILES["MTF02P"].port_source

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
X06_SPLINE_DIAMETER_MM = 3.90
HORN_SOURCE = "https://www.aliexpress.com/item/1005010458484391.html"
SHAFT_SOURCE = "https://www.aliexpress.com/item/1005007648646117.html"
BEARING_SOURCE = "https://www.aliexpress.com/item/1005007668446060.html"
BEARING_REFERENCE_SOURCE = (
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
        "spline_major_diameter_mm": X06_SPLINE_DIAMETER_MM,
        "spline_major_tolerance_plus_minus_mm": 0.01,
        "default_travel_deg": [-60.0, 60.0],
        "position_reference_us": [1000, 1500, 2000],
        "listed_mass_g": 6.0,
        "listed_mass_tolerance_percent": 10,
        "scope": "KST-authored May 2023 drawing obtained through the distributor. Regular-tab X06 V6.0, not X06H or X06N. Ear thickness is the 4.7 minus 3.7 mm drawing datum difference. Published case tolerance is not a fit allowance. Spline major diameter does not establish horn geometry or a retaining screw thread.",
        "unknown": "Supplied plastic horn dimensions and OEM retaining screw; supplied horn seating, loaded travel and permissible external gear load.",
    },
    "KST_X06_SUPPLIED_HORN": {
        "sources": [HORN_SOURCE],
        "retained_evidence": "references/cart_adaptation_review.md",
        "scope": "User-selected original supplied horn and OEM centre screw. Shape, installed seating, hole pattern, material and mass are not established. CAD depicts an explicitly bounded fit/preparation example; verify the actual supplied horn before manufacture and assembly.",
    },
    "selected_gears": {
        "sources": [gear.item_url for gear in GEARS.values()],
        "retained_evidence": [
            "references/kailash_gears_selected_evidence.md",
            "references/kailash_16t_dimensions.png",
            "references/kailash_16t_table.png",
        ],
        "module_mm": 0.5,
        "pressure_angle_deg": 20.0,
        "selected_parts": {
            str(gear.teeth): {
                "project_purchase_key": gear.sku,
                "seller": "Kailash Store",
                "item_url": gear.item_url,
                "bore_mm": gear.bore_mm,
                "bore_tolerance": gear.bore_tolerance,
                "face_width_mm": gear.face_width_mm,
                "total_axial_length_mm": gear.total_length_mm,
                "hub_extension_mm": gear.hub_extension_mm,
                "pitch_diameter_mm": gear.pitch_diameter_mm,
                "outside_diameter_mm": gear.outside_diameter_mm,
                "hub_diameter_mm": gear.hub_diameter_mm,
                "set_screw_thread": "M3",
                "set_screw_axis_from_hub_end_mm": gear.set_screw_axis_from_hub_end_mm,
                "material_claim": gear.material_claim,
                "measured_mass_g": gear.measured_mass_g,
            }
            for gear in GEARS.values()
        },
        "scope": "User-selected AliExpress options: 48T/3mm and 16T/3mm. Supplier pages and user-supplied dimension images support nominal envelopes; they do not certify the received lot. Tooth forms are nominal display geometry. The 48T plain bore is not a servo spline. Its set-screw axial position is unpublished; do not inherit the 16T drawing's 2.5mm datum. Material conflict and masses were explicitly deferred by the user; neither is a reason to change the selected parts or report them as POM. M3 screw length, point and purchase selection remain pending; check actual mesh, shaft grip and screw/tool clearance before use.",
    },
    "selected_shaft_stock": {
        "sources": [SHAFT_SOURCE],
        "seller_material_claim": "304 stainless steel",
        "nominal_diameter_mm": 3.0,
        "stock_lengths_mm": [100.0, 200.0],
        "diameter_tolerance": "Unspecified",
        "scope": "User selected nominal-3mm 304 rod options in 100/200mm stock lengths. This is not a precision h5 shaft or a factory-flat order. Cut square, deburr and check straightness, bearing fit and gear-bore fit before completing the batch. Output journals remain round with only the specified local gear-end flat; input stubs have the specified full-length flat. If fit is inadequate, substitute a measured precision nominal-3mm shaft; do not force the stock through bearings or infer a supplier tolerance.",
    },
    "selected_bearing": {
        "sources": [BEARING_SOURCE],
        "project_purchase_key": "BEARING_3X6X2_5",
        "bore_outside_width_mm": [3.0, 6.0, 2.5],
        "manufacturer": "Unverified generic seller part",
        "measured_mass_g": None,
        "scope": "User-selected 3x6x2.5mm option. Seller identity does not establish NSK/ISC manufacture, a tolerance class, mass, race-land dimensions or shield clearances. Use the retained ISC data only as the design reference below; verify the received bearing against its integral outer-ring capture and shaft before assembly.",
    },
    "MR63ZZ_design_reference": {
        "sources": [BEARING_REFERENCE_SOURCE, BEARING_FIT_SOURCE],
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
        "scope": "Comparison only: these published ISC MR63ZZ dimensions and mass do not identify or qualify the selected generic bearing. Integral shoulder/hook outer-ring contact and shield-clearance targets use this reference pending physical verification. Keep hubs off shields and outer rings; check fits, free rotation and axial capture with the received lot.",
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
        "retained_evidence": ["references/micoair743v2_aio45a_ports.webp"],
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
    "MTF01P": {
        "sources": [
            SENSOR_PROFILES["MTF01P"].source,
            SENSOR_PROFILES["MTF01P"].dimension_source,
            SENSOR_PROFILES["MTF01P"].port_source,
        ],
        "retained_evidence": [
            "references/mtf01p_dimensions.webp",
            "references/mtf01p_ports.webp",
        ],
        "documented_types": ["SH1.0-4P"],
        "catalog_references": ["JST_SH_4P"],
        "documented_interfaces": "One SH1.0-4P UART connector: GND,5V,Rx,Tx in the manufacturer pin photograph's orientation.",
        "orientation_evidence": "Connector is on a long33.2mm edge. Model long dimension as X and this edge as+Y; verify actual firmware yaw independently. Whole edge is reserved because header datums are not dimensioned.",
        "installed_port_centres_mm": None,
        "installed_port_datums_verified": False,
        "unknown": "Exact connector X/Z and header datum, plugged envelope, cable bend radius and installed sensor yaw.",
        "connection_limit": "Use only one optical sensor. Verify actual pinout; keep cable and optional ties outside all three optical apertures and both manual pivots.",
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
        "sources": [FC_SOURCE, FC_SPECIFICATION_SOURCE, FC_PACKAGE_SOURCE],
        "retained_evidence": [
            "references/micoair743v2_aio45a_specifications.webp",
            "references/micoair743v2_aio45a_package.webp",
            "references/micoair743v2_aio45a_orientation.webp",
        ],
        "verified": f"{FC_HOLE_PITCH:g} x {FC_HOLE_PITCH:g} mm hole pattern, diameter {FC_HOLE_DIAMETER:g} mm; 45 degree installation; 45A package lists four M2 x 6.6 mm silicone dampening sleeves.",
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
    "MTF01P": {
        "sources": [
            SENSOR_PROFILES["MTF01P"].source,
            SENSOR_PROFILES["MTF01P"].dimension_source,
            SENSOR_PROFILES["MTF01P"].port_source,
        ],
        "verified": "33.2x20.8x16.8mm,8g; four2.5mm mounting holes on24.3x12mm pattern; SH1.0-4P; optical-flow42deg, range1.5deg. Published maximum height includes raised optical tubes.",
        "unknown": "Actual rear flatness/adhesive strength, lens origins, plugged cable clearance and retained pointing under load.",
        "installation": "Existing18x12mm tray and insulating rear adhesive; published holes intentionally unused. Closed rear case supports this choice provisionally. No new printed adapter. Keep all optical openings free; match firmware rotation to the unit.",
    },
    "MTF02P": {
        "sources": [MTF02P_SOURCE, MTF02P_DIMENSION_IMAGE, MTF02P_PORT_IMAGE],
        "verified": "21.6 x 16 x 6.5 mm, 1.5 g; SH1.0-4P connector; optical-flow FOV 42 degrees and ToF FOV 2 degrees.",
        "unknown": "No verified mounting-hole pattern, backside adhesive contact, exact optical origins or plugged cable clearance.",
        "installation": "Insulating adhesive remains provisional. Optical face points away from the balloon; match firmware rotation to the purchased unit.",
    },
}
