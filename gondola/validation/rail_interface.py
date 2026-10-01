"""Validation-local mount identities and canonical attachment frames.

These reviewed literals deliberately remain independent of production builders.
Solid witnesses and contact checks stay in their respective validators.
"""

import FreeCAD as App

MOUNT_BINDINGS = (
    ("BatteryMount", "BatteryEquipmentModule", "battery", 0.0, 16.0),
    ("ElectronicsMount", "ElectronicsEquipmentModule", "electronics", 0.0, 16.0),
    ("AccessoryMount", "AccessoryEquipmentModule", "accessory", 0.0, 16.0),
    ("PropulsionFixedFrame", "MainPropulsionModule", None, 15.0, 40.0),
)


def mount_binding(module_name):
    return next((row for row in MOUNT_BINDINGS if row[1] == module_name), None)


def attachment_sites(module_name, offset=0):
    """Require the literal second clamp rather than infer it from saved hardware."""
    if module_name == "MainPropulsionModule":
        return (
            {"prefix": "", "x_offset": 15.0, "side": 1},
            {"prefix": "Opposite", "x_offset": -15.0, "side": -1},
        )
    return ({"prefix": "", "x_offset": offset, "side": 1},)


def site_placement(site):
    return App.Placement(
        App.Vector(site["x_offset"], 0, 0),
        App.Rotation(App.Vector(0, 0, 1), 180 if site["side"] < 0 else 0),
    )
