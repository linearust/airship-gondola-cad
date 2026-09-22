"""Selected purchased gears on a replaceable paired servo bridge.

Select a complete configuration before building. A saved CAD property is an
identity record, not a live gear-ratio knob: changing it cannot change teeth.
"""

import json
import math
from dataclasses import asdict, dataclass
from types import MappingProxyType

MODULE_MM = 0.5
PRESSURE_ANGLE_DEG = 20.0
PIVOT_Z_MM = 48.2
RADIAL_X = 0.4
RADIAL_Z = -math.sqrt(1 - RADIAL_X**2)


@dataclass(frozen=True)
class GearSpec:
    teeth: int
    hub_diameter_mm: float
    bore_mm: float
    face_width_mm: float
    total_length_mm: float
    bore_tolerance: str
    sku: str
    item_url: str
    material_claim: str
    set_screw_axis_from_hub_end_mm: float | None
    measured_mass_g: float | None = None

    @property
    def hub_extension_mm(self):
        return self.total_length_mm - self.face_width_mm

    @property
    def pitch_diameter_mm(self):
        return MODULE_MM * self.teeth

    @property
    def outside_diameter_mm(self):
        return MODULE_MM * (self.teeth + 2)


GEARS = MappingProxyType(
    {
        16: GearSpec(
            teeth=16,
            hub_diameter_mm=6.5,
            bore_mm=3.0,
            face_width_mm=5.0,
            total_length_mm=10.0,
            bore_tolerance="Unspecified by seller",
            sku="ALI_KAILASH_M05_16T_B3",
            item_url="https://www.aliexpress.com/item/1005013121105173.html",
            material_claim="Copper/copper alloy in seller text; exact alloy unverified",
            set_screw_axis_from_hub_end_mm=2.5,
        ),
        48: GearSpec(
            teeth=48,
            hub_diameter_mm=12.0,
            bore_mm=3.0,
            face_width_mm=3.0,
            total_length_mm=8.0,
            bore_tolerance="H8 claimed by seller",
            sku="ALI_KAILASH_M05_48T_B3",
            item_url="https://www.aliexpress.com/item/1005011637445325.html",
            material_claim="Aluminium alloy in seller description; alloy-steel attribute conflicts",
            set_screw_axis_from_hub_end_mm=None,
        ),
    }
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
    def frame_sku(self):
        return "PropulsionFixedFrame"

    @property
    def bridge_sku(self):
        return f"ServoDriveBridge{self.driver.teeth}T"

    def contract(self):
        return {
            **asdict(self),
            "driver_sku": self.driver.sku,
            "output_sku": self.output.sku,
            "module_mm": MODULE_MM,
            "pressure_angle_deg": PRESSURE_ANGLE_DEG,
            "nominal_full_face_overlap_mm": min(
                self.driver.face_width_mm, self.output.face_width_mm
            ),
            "angle_ratio": -self.ratio,
            "nominal_center_mm": self.center_distance_mm,
            "servo_endpoint_for_180_deg": 180 / self.ratio,
            "fixed_frame_print_sku": self.frame_sku,
            "servo_bridge_print_sku": self.bridge_sku,
        }


DRIVE_CONFIGURATIONS = MappingProxyType(
    {
        "48_16": DriveSpec("48_16", GEARS[48], GEARS[16]),
    }
)
# Source-authoritative build selection. Changing this requires a reviewed native
# baseline transition; source fingerprints bind all subsequent release reports.
SELECTED_DRIVE = DRIVE_CONFIGURATIONS["48_16"]
# Effective mesh width only. Gear bodies must use their own face_width_mm.
FACE_WIDTH_MM = min(
    SELECTED_DRIVE.driver.face_width_mm, SELECTED_DRIVE.output.face_width_mm
)


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
