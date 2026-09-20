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
FC_INCLUDED_DAMPER_THREAD = "M2"
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
