"""MTF-02P envelope and keepouts in the adjustable sensor tray's local frame.

The lens origins and FOV axis definitions remain unpublished. Expanding the
whole front face is a conservative design assumption, not camera calibration.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import create_reference, set_property
from gondola.contracts import equipment_interfaces as interfaces

from . import optical_mount as mount
from .equipment_metadata import add_interface_metadata, create_wiring_reserve
from .wiring_reserves import device_connector_contract

V = App.Vector
SOURCE = interfaces.MTF02P_SOURCE
PRODUCT_SOURCE = interfaces.MTF02P_PRODUCT_SOURCE
DIMENSION_SOURCE = interfaces.MTF02P_DIMENSION_IMAGE
ORIENTATION_SOURCE = "https://micoair.cn/api/media/file/docs/2026/07/66f6639242746-8204f1d31b-afb417fc40.webp"
SIZE_MM = interfaces.MTF02P_SIZE_MM
MASS_G = interfaces.MTF02P_MASS_G
FLOW_FOV_DEG = interfaces.MTF02P_FLOW_FOV_DEG
TOF_FOV_DEG = interfaces.MTF02P_TOF_FOV_DEG
SENSOR_BOTTOM_Z = mount.TRAY_TOP_Z + mount.ADHESIVE_ALLOWANCE
OPTICAL_RESERVE_LENGTH_MM = 400.0
CONNECTOR_TRAVEL_MM = 12.0


def envelope_shape():
    length, width, height = SIZE_MM
    return Part.makeBox(
        length, width, height, V(-length / 2, -width / 2, SENSOR_BOTTOM_Z)
    )


def optical_reserve_shape():
    """Cover the full modeled-gondola depth, checked separately by projection."""
    length, width, height = SIZE_MM
    sections = []
    for distance in (0.0, OPTICAL_RESERVE_LENGTH_MM):
        expansion = distance * math.tan(math.radians(FLOW_FOV_DEG / 2))
        half_x, half_y = length / 2 + expansion, width / 2 + expansion
        z = SENSOR_BOTTOM_Z + height + distance
        points = [
            V(-half_x, -half_y, z),
            V(half_x, -half_y, z),
            V(half_x, half_y, z),
            V(-half_x, half_y, z),
        ]
        sections.append(Part.makePolygon(points + [points[0]]))
    return Part.makeLoft(sections, True, True)


def connector_reserve_shape():
    length, width, height = SIZE_MM
    return Part.makeBox(
        CONNECTOR_TRAVEL_MM, width, height, V(length / 2, -width / 2, SENSOR_BOTTOM_Z)
    )


def connector_contract():
    return {
        **device_connector_contract("MTF02P"),
        "parent_frame": "OpticalPitchStage",
        "outward_axis": "+X",
        "edge_width_mm": SIZE_MM[1],
        "edge_height_mm": SIZE_MM[2],
        "design_outward_travel_mm": CONNECTOR_TRAVEL_MM,
        "operating_scope": "The source drawing's connector edge is tray-local +X. The whole edge follows both manual tilt axes and the selected host carrier; actual connector Y/Z and firmware yaw remain to verify.",
        "withdrawal_scope": "Continuous 12mm lane is a design allowance, not a measured withdrawal stroke or cable bend radius. Leave slack for both manual axes, then secure the fixed lead with a purchased tie. Disconnect before sliding/removing the module.",
    }


def build_sensor(doc, pitch_stage):
    sensor = create_reference(
        doc,
        pitch_stage,
        "ModuleMTF02PEnvelope",
        "MTF-02P | independently leveled optical face",
        envelope_shape(),
        "Published21.6x16x6.5mm envelope,1.5g; no confirmed mounting holes. Use insulating adhesive on the18x12mm tray with1mm nominal allowance. Optical face is local+Z; manually align to downward vertical at the intended flight trim, then lock both axes. This is not active gravity stabilization. Match actual board yaw and firmware orientation; ArduPilot/PX4 and INAV published forward references differ180deg. Backside contact, adhesive retention and actual lens/connector datums remain unmeasured.",
        SOURCE,
    )
    add_interface_metadata(sensor, "MTF02P")
    for name, value in (
        ("ProductSource", PRODUCT_SOURCE),
        ("DimensionDrawingSource", DIMENSION_SOURCE),
        ("FirmwareOrientationSource", ORIENTATION_SOURCE),
    ):
        set_property(sensor, name, value)
    set_property(sensor, "ListedMassGrams", MASS_G, "App::PropertyFloat")
    set_property(sensor, "OpticalDirection", V(0, 0, 1), "App::PropertyVector")
    set_property(sensor, "PlannedConnectorDirection", V(1, 0, 0), "App::PropertyVector")
    set_property(sensor, "PublishedOpticalFlowFOV", FLOW_FOV_DEG, "App::PropertyAngle")
    set_property(sensor, "PublishedToFFOV", TOF_FOV_DEG, "App::PropertyAngle")
    set_property(sensor, "OpticalOriginsMeasured", False, "App::PropertyBool")
    optical = create_reference(
        doc,
        pitch_stage,
        "MTF02POpticalClearanceReserve",
        "MTF-02P full modeled-gondola optical screen",
        optical_reserve_shape(),
        "Whole21.6x16mm front face expands21deg per side in both axes for400mm along tray+Z, following both manual tilt axes. Validation checks the modeled gondola fits inside this forward screening depth, and screens a conservative full-adjustment bound against external parts. The published42deg FOV has no confirmed angular-axis definition or lens origin; this remains a conservative assumption. No full-range ground-visibility, real cable or physical optical calibration is claimed.",
        SOURCE,
    )
    optical.Role = "Clearance"
    optical.Label = "RESERVE | MTF-02P optical field, follows tray"
    set_property(
        optical,
        "ReservedOpticalDistance",
        OPTICAL_RESERVE_LENGTH_MM,
        "App::PropertyLength",
    )
    set_property(optical, "OpticalDirection", V(0, 0, 1), "App::PropertyVector")
    set_property(optical, "InstalledOpticalFieldVerified", False, "App::PropertyBool")
    connector = create_wiring_reserve(
        doc,
        pitch_stage,
        "MTF02PConnectorReserve",
        connector_reserve_shape(),
        connector_contract(),
    )
    return [sensor], [optical, connector]
