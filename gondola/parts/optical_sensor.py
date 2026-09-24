"""One replaceable optical sensor, using the unchanged adhesive tray.

MTF02P-named native IDs are retained as stable assembly references, not a model
selection. Labels, SensorModel and all evidence/shapes describe the active model.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import create_reference, set_property
from gondola.contracts.optical_sensors import SENSOR_PROFILES, get_sensor_profile

from . import optical_mount as mount
from .equipment_metadata import add_interface_metadata
from .wiring_reserves import device_connector_contract

V = App.Vector
SENSOR_BOTTOM_Z = mount.TRAY_TOP_Z + mount.ADHESIVE_ALLOWANCE
OPTICAL_RESERVE_LENGTH_MM = 400.0
CONNECTOR_TRAVEL_MM = 12.0
SENSOR_OBJECT = "ModuleMTF02PEnvelope"
FIELD_OBJECT = "MTF02POpticalClearanceReserve"
CONNECTOR_OBJECT = "MTF02PConnectorReserve"


def _profile(profile):
    return get_sensor_profile() if profile is None else profile


def profile_for_document(doc):
    return get_sensor_profile(doc.OpticalFlowModule.SensorModel)


def envelope_shape(profile=None):
    length, width, height = _profile(profile).size_mm
    return Part.makeBox(
        length, width, height, V(-length / 2, -width / 2, SENSOR_BOTTOM_Z)
    )


def optical_reserve_shape(profile=None):
    """Enclose possible apertures anywhere in the whole body footprint/height."""
    profile = _profile(profile)
    length, width, _ = profile.size_mm
    sections = []
    for distance in (0.0, OPTICAL_RESERVE_LENGTH_MM):
        expansion = distance * math.tan(math.radians(profile.flow_fov_deg / 2))
        half_x, half_y = length / 2 + expansion, width / 2 + expansion
        z = SENSOR_BOTTOM_Z + profile.optical_origin_min_z_mm + distance
        points = [
            V(-half_x, -half_y, z),
            V(half_x, -half_y, z),
            V(half_x, half_y, z),
            V(-half_x, half_y, z),
        ]
        sections.append(Part.makePolygon(points + [points[0]]))
    return Part.makeLoft(sections, True, True)


def connector_reserve_shape(profile=None):
    profile = _profile(profile)
    length, width, height = profile.size_mm
    if profile.connector_axis == "+X":
        size, origin = (
            (CONNECTOR_TRAVEL_MM, width, height),
            (length / 2, -width / 2, SENSOR_BOTTOM_Z),
        )
    elif profile.connector_axis == "+Y":
        size, origin = (
            (length, CONNECTOR_TRAVEL_MM, height),
            (-length / 2, width / 2, SENSOR_BOTTOM_Z),
        )
    else:
        raise ValueError("Unsupported connector axis: " + profile.connector_axis)
    return Part.makeBox(*size, V(*origin))


def connector_contract(profile=None):
    profile = _profile(profile)
    return {
        **device_connector_contract(profile.key),
        "parent_frame": "OpticalPitchStage",
        "outward_axis": profile.connector_axis,
        "edge_width_mm": profile.size_mm[1 if profile.connector_axis == "+X" else 0],
        "edge_height_mm": profile.size_mm[2],
        "design_outward_travel_mm": CONNECTOR_TRAVEL_MM,
        "operating_scope": f"The {profile.model} documented connector edge is modeled as tray-local{profile.connector_axis}. The whole edge follows both manual axes and the host; actual connector datums and firmware yaw remain to verify independently for the selected sensor.",
        "withdrawal_scope": "Continuous12mm lane is a design allowance, not measured withdrawal stroke or bend radius. Leave slack for both axes and secure the fixed lead. Disconnect before removing the module. Keep ties away from all optical openings.",
    }


def _apply_objects(group, sensor, optical, connector, profile):
    contract = json.dumps(profile.contract(), sort_keys=True)
    for obj in (sensor, optical, connector):
        set_property(obj, "SensorModel", profile.key)
        set_property(obj, "SensorProfileContract", contract)
        set_property(obj, "SourceURL", profile.source)
        obj.setEditorMode("SensorModel", 1)
    set_property(group, "SensorModel", profile.key)
    group.setEditorMode("SensorModel", 1)
    sensor.Shape = envelope_shape(profile)
    sensor.Label = profile.model + " | independently leveled optical face"
    sensor.Notes = f"Published envelope{profile.size_mm}mm,{profile.mass_g:g}g. One sensor only, using the existing18x12mm tray and1mm nominal insulating adhesive allowance. No extra mount or sensor screws. Optical face is local+Z; manually align downward at flight trim and lock both axes. This is not active stabilization. Verify actual rear contact, retention, lens origins, cable clearance and the selected unit's firmware yaw; do not copy another model's orientation setting."
    add_interface_metadata(sensor, profile.key)
    for name, value in (
        ("ProductSource", profile.product_source),
        ("DimensionDrawingSource", profile.dimension_source),
        ("FirmwareOrientationSource", profile.orientation_source),
    ):
        set_property(sensor, name, value)
    for name, value, kind in (
        ("ListedMassGrams", profile.mass_g, "App::PropertyFloat"),
        ("OpticalDirection", V(0, 0, 1), "App::PropertyVector"),
        (
            "PlannedConnectorDirection",
            V(1, 0, 0) if profile.connector_axis == "+X" else V(0, 1, 0),
            "App::PropertyVector",
        ),
        ("PublishedOpticalFlowFOV", profile.flow_fov_deg, "App::PropertyAngle"),
        ("PublishedToFFOV", profile.tof_fov_deg, "App::PropertyAngle"),
        ("OpticalOriginsMeasured", False, "App::PropertyBool"),
    ):
        set_property(sensor, name, value, kind)
    optical.Shape = optical_reserve_shape(profile)
    optical.Label = "RESERVE | " + profile.model + " optical field, follows tray"
    optical.Role = "Clearance"
    optical.Notes = (
        profile.contract()["optical_screen"]
        + " Screening depth400mm; own sensor intentionally contained. No full-range visibility or physical optical calibration is claimed."
    )
    set_property(
        optical,
        "ReservedOpticalDistance",
        OPTICAL_RESERVE_LENGTH_MM,
        "App::PropertyLength",
    )
    set_property(optical, "OpticalDirection", V(0, 0, 1), "App::PropertyVector")
    set_property(optical, "InstalledOpticalFieldVerified", False, "App::PropertyBool")
    connector.Shape = connector_reserve_shape(profile)
    connector.Label = "RESERVE | " + profile.model + " connector access"
    connector.Role = "Clearance"
    connector.Notes = "Whole-edge connector access allowance; no exact header location, installed cable or certified bending radius. Disconnect leads before removal or adjustment."
    set_property(
        connector,
        "WiringContract",
        json.dumps(connector_contract(profile), sort_keys=True),
    )
    set_property(connector, "InstalledConnectorFitVerified", False, "App::PropertyBool")


def apply_profile(doc, profile):
    """Temporary compatibility probe, not a saved-BOM or release update.

    Select the source contract and rebuild for a persistent installation change.
    Validators restore the original shapes, metadata, host and angles after use.
    """
    _apply_objects(
        doc.OpticalFlowModule,
        doc.getObject(SENSOR_OBJECT),
        doc.getObject(FIELD_OBJECT),
        doc.getObject(CONNECTOR_OBJECT),
        profile,
    )
    doc.recompute()


def build_sensor(doc, pitch_stage, profile=None):
    profile = _profile(profile)
    group = pitch_stage.getParentGeoFeatureGroup().getParentGeoFeatureGroup()
    objects = [
        create_reference(doc, pitch_stage, name, name, shape, "", profile.source)
        for name, shape in (
            (SENSOR_OBJECT, envelope_shape(profile)),
            (FIELD_OBJECT, optical_reserve_shape(profile)),
            (CONNECTOR_OBJECT, connector_reserve_shape(profile)),
        )
    ]
    _apply_objects(group, *objects, profile)
    set_property(
        group, "SupportedSensorModels", list(SENSOR_PROFILES), "App::PropertyStringList"
    )
    group.setEditorMode("SupportedSensorModels", 1)
    return objects[:1], objects[1:]
