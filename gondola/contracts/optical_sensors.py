"""Mutually exclusive optical sensors on one unchanged adhesive tray.

Change SELECTED_SENSOR_KEY and rebuild to change the installed model, equipment
mass and reservations together. Alternative compatibility is checked separately;
it does not add another installed sensor or certify adhesive/pointing retention.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OpticalSensorProfile:
    key: str
    model: str
    size_mm: tuple[float, float, float]
    mass_g: float
    flow_fov_deg: float
    tof_fov_deg: float
    connector_axis: str
    source: str
    product_source: str
    dimension_source: str
    port_source: str
    orientation_source: str
    mounting_pitch_mm: tuple[float, float] | None = None
    mounting_hole_diameter_mm: float | None = None
    optical_origin_min_z_mm: float = 0.0

    def contract(self):
        return {
            **asdict(self),
            "installation": "One sensor only, rear face on the existing18x12mm insulating adhesive tray; no extra printed mount or sensor screws. Check actual rear contact and retention. Do not route a tie or tape over optical apertures, connector or moving pivots.",
            "optical_screen": "Expand the entire footprint from the rear envelope plane by half the published42deg angle in both axes. This encloses possible lower flow apertures and raised range tubes without inventing lens datums. The source does not specify optical angular-axis conventions; this is a conservative modeled-gondola screen, not calibration.",
            "electrical": "5V supply,3.3V UART115200; verify the received SH1.0-4P pinout and selected firmware protocol/orientation before connecting. A matching connector alone does not certify a cable.",
            "retention_verified": False,
        }


SENSOR_PROFILES = {
    "MTF02P": OpticalSensorProfile(
        "MTF02P",
        "MTF-02P",
        (21.6, 16.0, 6.5),
        1.5,
        42.0,
        2.0,
        "+X",
        "https://micoair.cn/zh/docs/sensors/sensors/mtf-02-02p-sensors",
        "https://micoair.com/optical_range_sensor_mtf-02p/",
        "https://micoair.cn/api/media/file/docs/2026/07/66f661b664e82-df0e9d69d2-971f59dd57.webp",
        "https://micoair.cn/api/media/file/docs/2026/07/66f66374dd95c-852bf87918-83cf12d631.webp",
        "https://micoair.cn/api/media/file/docs/2026/07/66f6639242746-8204f1d31b-afb417fc40.webp",
    ),
    "MTF01P": OpticalSensorProfile(
        "MTF01P",
        "MTF-01P",
        (33.2, 20.8, 16.8),
        8.0,
        42.0,
        1.5,
        "+Y",
        "https://micoair.cn/zh/docs/sensors/sensors/mtf-01p-sensors",
        "https://micoair.com/optical_range_sensor_mtf-01p/",
        "https://micoair.cn/api/media/file/docs/2026/07/66b4374b5dc9c-85c984aa0c-4b3c55e69c.webp",
        "https://micoair.cn/api/media/file/docs/2026/07/66b437e3092ef-ce4191a0f2-dfd02307eb.webp",
        "https://micoair.cn/api/media/file/docs/2026/07/66b43805576df-07a5fca3b2-9ceca549ba.webp",
        (24.3, 12.0),
        2.5,
    ),
}
SELECTED_SENSOR_KEY = "MTF02P"


def get_sensor_profile(key=None):
    key = SELECTED_SENSOR_KEY if key is None else key
    try:
        return SENSOR_PROFILES[key]
    except (KeyError, TypeError) as error:
        raise ValueError(f"Unsupported optical sensor: {key!r}") from error
