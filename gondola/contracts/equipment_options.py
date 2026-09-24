"""Mutually exclusive navigation and radio choices on shared equipment supports.

Profiles describe nominal purchased equipment, not adhesive strength, RF
performance or an installed antenna location. The parts layer owns placement.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AntennaReference:
    model: str
    diameter_mm: float
    length_mm: float
    mass_g: float
    source: str


@dataclass(frozen=True)
class NavigationProfile:
    key: str
    model: str
    interface_key: str
    size_mm: tuple[float, float, float]
    mass_g: float
    connector_type: str
    connector_catalog_key: str
    connector_axes: tuple[str, ...]
    connector_band_width_mm: float
    source: str
    dimension_source: str
    port_source: str
    mounting_hole_centres_mm: tuple[tuple[float, float], ...] = ()
    mounting_hole_diameter_mm: float | None = None
    external_antenna: AntennaReference | None = None

    def contract(self):
        return {
            **asdict(self),
            "region": "navigation",
            "installation": "Install one navigation module only. P-AS retains its confirmed mounting axes; GPS alternatives use insulating adhesive on the shared support. No extra GPS bracket or fasteners are implied. Verify actual underside contact, component pressure, retention and connector access.",
            "dimension_scope": "Nominal X/Y/Z body envelope in the source drawing frame; no measured PCB bearing plane, compressed adhesive thickness or installed connector datum. Listed mass is the module only; a separately listed external antenna is not included.",
            "external_antenna_installations": (
                ["direct_sma", "remote_sma"] if self.external_antenna else []
            ),
            "antenna_scope": "External antenna dimensions and mass are separate reference metadata. Both direct SMA and remote SMA installation are allowed for MG-F10-A. A direct antenna on the shared pad points along local +Z, away from the balloon and downward; mechanical clearance does not establish useful GNSS reception in that orientation. Prefer a remote upward antenna location when GPS reception matters, including outdoor use. That off-gondola location, cable length and retention are not modeled or qualified. A direct-antenna clearance reservation is conservative, not a measured SMA centre or seating datum; verify its space, tape support and connector loads with actual hardware.",
            "electrical_scope": "P-AS uses its selected UART integration; GPS alternatives require the corresponding UART GPS and I2C compass connections and firmware configuration. Mechanical interchangeability does not establish protocol, pinout, heading, indoor GNSS availability or RF compatibility.",
            "retention_verified": False,
            "installed_port_datums_verified": False,
            "rf_performance_verified": False,
        }


@dataclass(frozen=True)
class RadioProfile:
    key: str
    model: str
    interface_key: str
    size_mm: tuple[float, float, float]
    mass_g: float
    connector_type: str
    connector_catalog_key: str
    connector_axes: tuple[str, ...]
    source: str
    dimension_source: str
    port_source: str
    antenna_connector: str
    has_usb: bool
    max_average_power_w: float
    supply_voltage_v: tuple[float, float] = (4.5, 5.0)
    uart_logic_v: float = 3.3

    def contract(self):
        return {
            **asdict(self),
            "region": "radio",
            "installation": "Install one onboard radio only on the existing insulating-adhesive support. Trim adhesive to supported contact, check actual underside components, heat dissipation and retention; no radio-specific printed pocket or mounting holes are inferred.",
            "dimension_scope": "Nominal body envelope only. LR900-A excludes its SMA socket and antenna; LR24-F-Mini excludes the external antenna and flexible pigtail. Listed module masses are not complete installed radio-system masses.",
            "connector_scope": "Both complete long-axis ends receive conservative access allowances; exact connector XYZ, IPEX cable mating space, plugged leads and bends remain unmeasured. GH1.25-4P and SH1.0-4P are different interfaces; verify the selected pin labels and cross TX/RX.",
            "electrical_scope": "Published maximum average power is a reference, not a peak-current limit or proof of the FC's shared 5V capacity. LR900 and LR24 require matching-family ground equipment; the full-size LR24-F is ground equipment, not an additional onboard module.",
            "retention_verified": False,
            "installed_port_datums_verified": False,
            "rf_performance_verified": False,
        }


PAS_SOURCE = (
    "https://ftp.nooploop.com/downloads/linktrack/LinkTrack_Datasheet_V2.3_zh.pdf"
)
MGF10_DIMENSIONS = (
    "https://micoair.cn/api/media/file/docs/2026/07/670a2bdd48e84-5d41a070a6.png"
)
LR24_SPECIFICATIONS = (
    "https://store.micoair.com/wp-content/uploads/2025/01/LR24_params.webp"
)

NAVIGATION_PROFILES = {
    "PAS": NavigationProfile(
        key="PAS",
        model="LinkTrack P-AS",
        interface_key="PAS",
        size_mm=(27.0, 32.0, 7.0),
        mass_g=3.45,
        connector_type="GH1.25-4P",
        connector_catalog_key="JST_GH_4P",
        connector_axes=("-Y",),
        connector_band_width_mm=19.0,
        source=PAS_SOURCE,
        dimension_source=PAS_SOURCE,
        port_source=PAS_SOURCE,
        mounting_hole_centres_mm=((-11.5, -9.3), (11.5, -9.3)),
        mounting_hole_diameter_mm=2.2,
    ),
    "MGA01": NavigationProfile(
        key="MGA01",
        model="MicoAir MG-A01 / M10 Ultra",
        interface_key="MGA01",
        size_mm=(25.0, 25.0, 8.0),
        mass_g=12.0,
        connector_type="SH1.0-6P",
        connector_catalog_key="JST_SH_6P",
        connector_axes=("-Y",),
        connector_band_width_mm=25.0,
        source="https://micoair.cn/zh/docs/gps-rtk/gps",
        dimension_source="https://micoair.cn/api/media/file/docs/2026/07/66a20fad7f8af-b764097238-3c14051a33.webp",
        port_source="https://micoair.cn/api/media/file/docs/2026/07/66a21138a03b7-e888424f70-9252767bfd.webp",
    ),
    "MGF10A": NavigationProfile(
        key="MGF10A",
        model="MicoAir MG-F10-A (external helix)",
        interface_key="MGF10A",
        size_mm=(22.0, 34.0, 13.4),
        mass_g=6.0,
        connector_type="SH1.0-6P",
        connector_catalog_key="JST_SH_6P",
        connector_axes=("-Y",),
        connector_band_width_mm=22.0,
        source="https://micoair.cn/zh/docs/gps-rtk/mg-f10/mg-f10-a-gnss",
        dimension_source=MGF10_DIMENSIONS,
        port_source="https://micoair.cn/api/media/file/docs/2026/07/670a2cf93e54a-f112ee7037.png",
        external_antenna=AntennaReference(
            model="MG-F10 external SMA quad helix",
            diameter_mm=28.0,
            length_mm=59.3,
            mass_g=15.0,
            source=MGF10_DIMENSIONS,
        ),
    ),
}

RADIO_PROFILES = {
    "LR900A": RadioProfile(
        key="LR900A",
        model="LR900-A",
        interface_key="LR",
        size_mm=(29.5, 13.0, 9.0),
        mass_g=4.0,
        connector_type="GH1.25-4P",
        connector_catalog_key="JST_GH_4P",
        connector_axes=("-X", "+X"),
        source="https://micoair.cn/zh/docs/telemetry/lr900/lr900-telemetry",
        dimension_source="https://micoair.cn/api/media/file/docs/2026/07/684040d2a4f02-0f3856feb4-010837e548.webp",
        port_source="https://micoair.cn/api/media/file/docs/2026/07/669f74a433137-ed5c3462e6-6d69324222.webp",
        antenna_connector="SMA, external thread/female centre contact",
        has_usb=True,
        max_average_power_w=0.30,
    ),
    "LR24FMINI": RadioProfile(
        key="LR24FMINI",
        model="LR24-F-Mini",
        interface_key="LR24FMINI",
        size_mm=(24.0, 18.2, 5.8),
        mass_g=2.5,
        connector_type="SH1.0-4P",
        connector_catalog_key="JST_SH_4P",
        connector_axes=("-X", "+X"),
        source="https://micoair.cn/zh/docs/telemetry/lr24/lr24-telemetry",
        dimension_source="https://store.micoair.com/wp-content/uploads/2025/01/LR24_size.webp",
        port_source="https://micoair.cn/api/media/file/docs/2026/07/66a0c156834c9-2fc5d7c4ba-76f5fe2816.webp",
        antenna_connector="IPEX1",
        has_usb=False,
        max_average_power_w=2.0,
    ),
}

SELECTED_NAVIGATION_KEY = "PAS"
SELECTED_RADIO_KEY = "LR900A"


def get_navigation_profile(key=None):
    key = SELECTED_NAVIGATION_KEY if key is None else key
    try:
        return NAVIGATION_PROFILES[key]
    except (KeyError, TypeError) as error:
        raise ValueError(f"Unsupported navigation module: {key!r}") from error


def get_radio_profile(key=None):
    key = SELECTED_RADIO_KEY if key is None else key
    try:
        return RADIO_PROFILES[key]
    except (KeyError, TypeError) as error:
        raise ValueError(f"Unsupported onboard radio: {key!r}") from error
