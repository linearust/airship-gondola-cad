"""Finite, sourced gear choices sharing one radial input-cartridge interface.

Select a complete configuration before building. A saved CAD property is an
identity record, not a live gear-ratio knob: changing it cannot change teeth.
"""

import json
import math
from dataclasses import asdict, dataclass
from types import MappingProxyType

MODULE_MM = 0.5
FACE_WIDTH_MM = 3.0
PIVOT_Z_MM = 48.2
RADIAL_X = 0.4
RADIAL_Z = -math.sqrt(1 - RADIAL_X**2)
MESH_CLEARANCE_MAX_MM = 0.19
INPUT_MOUNT_HALF_SPAN = 12.5
INPUT_MOUNT_Z_MM = 8.3


@dataclass(frozen=True)
class GearSpec:
    teeth: int
    hub_diameter_mm: float

    @property
    def sku(self):
        return f"GEABP0.5-{self.teeth}-3-B-3"


GEARS = MappingProxyType(
    {20: GearSpec(20, 8.5), 60: GearSpec(60, 10.0), 64: GearSpec(64, 10.0)}
)


@dataclass(frozen=True)
class DriveSpec:
    key: str
    driver: GearSpec
    output: GearSpec

    @property
    def ratio(self):
        return self.driver.teeth / self.output.teeth

    @property
    def center_distance_mm(self):
        return MODULE_MM * (self.driver.teeth + self.output.teeth) / 2

    @property
    def input_x_mm(self):
        return RADIAL_X * self.center_distance_mm

    @property
    def input_z_mm(self):
        return PIVOT_Z_MM + RADIAL_Z * self.center_distance_mm

    @property
    def max_mesh_clearance_mm(self):
        return MESH_CLEARANCE_MAX_MM

    def contract(self):
        return {
            **asdict(self),
            "driver_sku": self.driver.sku,
            "output_sku": self.output.sku,
            "angle_ratio": -self.ratio,
            "nominal_center_mm": self.center_distance_mm,
            "servo_endpoint_for_180_deg": 180 / self.ratio,
            "mesh_clearance_max_mm": self.max_mesh_clearance_mm,
        }


DRIVE_CONFIGURATIONS = MappingProxyType(
    {
        f"{teeth}_20": DriveSpec(f"{teeth}_20", GEARS[teeth], GEARS[20])
        for teeth in (60, 64)
    }
)
# The installed bolt-guided slider accommodates every supported gear pair and
# the separately bounded fine mesh adjustment without changing the print.
INPUT_SLIDE_TRAVEL_MM = max(
    spec.center_distance_mm + spec.max_mesh_clearance_mm
    for spec in DRIVE_CONFIGURATIONS.values()
) - min(spec.center_distance_mm for spec in DRIVE_CONFIGURATIONS.values())

# Source-authoritative build selection. Changing this requires a reviewed native
# baseline transition; source fingerprints bind all subsequent release reports.
SELECTED_DRIVE = DRIVE_CONFIGURATIONS["60_20"]


def drive_for_document(doc):
    """Reject stale or tampered saved configuration metadata, without FreeCAD imports."""
    module = doc.getObject("MainPropulsionModule")
    key = getattr(module, "GearConfiguration", None)
    if key not in DRIVE_CONFIGURATIONS:
        raise ValueError(f"Unsupported or missing gear configuration: {key!r}")
    drive = DRIVE_CONFIGURATIONS[key]
    try:
        saved = json.loads(module.DriveContract)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Missing or invalid saved drive contract") from exc
    if saved != drive.contract():
        raise ValueError(
            "Saved drive contract differs from the supported configuration"
        )
    return drive
