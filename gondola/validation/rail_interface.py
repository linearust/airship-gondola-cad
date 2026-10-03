"""Validation-local mount identities and canonical attachment frames.

These reviewed literals deliberately remain independent of production builders.
Solid witnesses and contact checks stay in their respective validators.
"""

import FreeCAD as App

from gondola.cad import placed_shape
from gondola.contracts.optical_attachment import resolve_mount_mode

from .geometry import TOL, local_shape

MOUNT_BINDINGS = (
    ("BatteryMount", "BatteryEquipmentModule", "battery", 0.0, 16.0),
    ("ElectronicsMount", "ElectronicsEquipmentModule", "electronics", 0.0, 16.0),
    ("AccessoryMount", "AccessoryEquipmentModule", "accessory", 0.0, 16.0),
    ("PropulsionFixedFrame", "MainPropulsionModule", None, 14.0, 44.0),
) + (
    (("OpticalSensorTray", "OpticalFlowModule", "optical", 0.0, 16.0),)
    if resolve_mount_mode() == "rail"
    else ()
)


def mount_frame_check(obj, module):
    """Require the literal native hierarchy before normalizing a shoe frame."""
    optical = module is not None and module.Name == "OpticalFlowModule"
    stage = module.Document.getObject("OpticalPitchStage") if optical else None
    expected_parent = stage if optical else module
    parent_matches = (
        obj is not None
        and expected_parent is not None
        and obj.getParentGeoFeatureGroup() == expected_parent
    )
    identity = (
        obj is not None
        and obj.Placement.Base.Length < TOL
        and abs(obj.Placement.Rotation.Angle) < TOL
    )
    stage_matches = not optical or (
        stage is not None
        and getattr(module, "OpticalAttachmentMode", None) == "rail"
        and stage.getParentGeoFeatureGroup() == module
        and (stage.Placement.Base - App.Vector(-12, 1.25, 6.5)).Length < TOL
        and abs(stage.Placement.Rotation.Angle) < TOL
        and all(
            hasattr(stage, key) and abs(float(getattr(stage, key))) < TOL
            for key in ("Pitch", "MinimumAngle", "MaximumAngle")
        )
    )
    return {
        "expected_parent": "OpticalPitchStage"
        if optical
        else getattr(module, "Name", None),
        "parent_matches": parent_matches,
        "part_local_placement_identity": identity,
        "fixed_optical_stage_matches": stage_matches,
        "expected_optical_stage_translation_mm": [-12.0, 1.25, 6.5]
        if optical
        else None,
        "passed": parent_matches and identity and stage_matches,
    }


def mount_shape_in_module(obj, module):
    """Use saved native transforms; do not silently replace a misplaced stage."""
    relative = module.getGlobalPlacement().inverse().multiply(obj.getGlobalPlacement())
    return placed_shape(local_shape(obj), relative)


def mount_binding(module_name):
    return next((row for row in MOUNT_BINDINGS if row[1] == module_name), None)


def attachment_sites(module_name, offset=0):
    """Require the literal second clamp rather than infer it from saved hardware."""
    if module_name == "MainPropulsionModule":
        return (
            {"prefix": "", "x_offset": 14.0, "side": 1},
            {"prefix": "Opposite", "x_offset": -14.0, "side": -1},
        )
    return ({"prefix": "", "x_offset": offset, "side": 1},)


def site_placement(site):
    return App.Placement(
        App.Vector(site["x_offset"], 0, 0),
        App.Rotation(App.Vector(0, 0, 1), 180 if site["side"] < 0 else 0),
    )


def selected_mount_bindings(module_names=None):
    """Explicit nonempty subset; selection never changes the complete registry."""
    if module_names is None:
        return MOUNT_BINDINGS
    if isinstance(module_names, str):
        raise ValueError("Module selection must be a sequence of module names")
    names = tuple(module_names)
    known = {row[1] for row in MOUNT_BINDINGS}
    if not names or any(not isinstance(name, str) for name in names):
        raise ValueError("Module selection must contain known module names")
    if len(set(names)) != len(names) or not set(names).issubset(known):
        raise ValueError("Module selection contains duplicate or unknown names")
    return tuple(row for row in MOUNT_BINDINGS if row[1] in names)
