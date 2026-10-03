"""Integral optical bridge on the dedicated FC and optical levelling carrier."""

import json
import math

import FreeCAD as App

from gondola.cad import box, create_group, set_property, union
from gondola.contracts.optical_attachment import DEFAULT_HOST

from . import optical_interface

V = App.Vector
TRAY_SIZE_MM = (18.0, 12.0)
TRAY_BOTTOM_Z = 42.0
TRAY_TOP_Z = 44.0
ADHESIVE_ALLOWANCE = 1.0


def optical_support_shape():
    """Two opposite corner posts and one straight diagonal bridge clear the FC."""
    pieces = [box(4, 4, 22, (x, y, 19)) for x, y in ((-31.5, -31.5), (27.5, 27.5))]
    length = 62 * math.sqrt(2)
    roof = box(length, 5, 3, (-length / 2, -2.5, 41))
    roof.rotate(V(), V(0, 0, 1), 45)
    pieces.extend([roof, box(18, 12, 2, (-9, -6, TRAY_BOTTOM_Z))])
    return union(pieces).removeSplitter()


def mount_contract():
    return {
        "mechanism": "Optical bridge integral with the dedicated FC and optical levelling carrier",
        "attachment_mode": "instrument",
        "adjustment_degrees_of_freedom": 0,
        "shared_adjustment_control": "InstrumentPitchStage.Pitch",
        "self_levelling": False,
        "holding_torque_verified": False,
        "physical_angle_stops_modeled": False,
        "support_part": "ElectronicsMount",
        "tray_origin_in_module_mm": (0.0, 0.0, 0.0),
        "attachment_interface": optical_interface.interface_contract(),
        "tray_size_mm": TRAY_SIZE_MM,
        "tray_bottom_z_in_sensor_frame_mm": TRAY_BOTTOM_Z,
        "tray_top_z_in_sensor_frame_mm": TRAY_TOP_Z,
        "adhesive_allowance_mm": ADHESIVE_ALLOWANCE,
        "support_sections_mm": {
            "opposite_corner_post": (4.0, 4.0),
            "diagonal_roof_bar": (5.0, 3.0),
        },
        "hardware": "No optical bridge fasteners or separate printed optical tray. The upper carrier and sensor share the existing two M3 instrument joints.",
        "assembly": "Attach one sensor to the integral pad using insulating adhesive clear of both optical apertures and connector. Release the sensor adhesive and lift along local +Z for sensor replacement. For FC service, set the common pitch stage to neutral 0 degrees, remove its actual mounting hardware, disconnect leads, slide the bare board along local +X through the open bridge, then lift. Restore and verify the calibrated body-reference setup angle before operation.",
        "adjustment": "FC and sensor move together on InstrumentPitchStage. Align to the vehicle reference attitude and lock before operation. Disconnect leads before adjustment, regenerate the motor-lead planning route and check actual slack; no active stabilization.",
        "sensor_interface": "Continuous 18x12 mm insulating adhesive pad at stage XY0 and Z44 for either MTF-01P or MTF-02P. Optical face is local +Z. Actual rear contact, retention, aperture origins and connector fit remain unverified; no invented sensor fixing holes.",
    }


def build_optical_mount(doc, host):
    """Create sensor reference frames; its printed support belongs to ElectronicsMount."""
    if host.Document != doc or host.Name != DEFAULT_HOST:
        raise ValueError(
            "Optical sensor requires InstrumentPitchStage in the same document"
        )
    group = create_group(
        doc, "OpticalFlowModule", "Optical flow | integral carrier support"
    )
    host.addObject(group)
    group.Placement = optical_interface.placement()
    set_property(group, "OpticalAttachmentMode", "instrument")
    group.setEditorMode("OpticalAttachmentMode", 1)
    set_property(
        group, "OpticalMountContract", json.dumps(mount_contract(), sort_keys=True)
    )
    set_property(
        group,
        "AdjustmentControls",
        "InstrumentPitchStage.Pitch; shared locked setup angle",
    )
    set_property(group, "HoldingTorqueVerified", False, "App::PropertyBool")
    set_property(group, "SelfLevelling", False, "App::PropertyBool")
    optical_interface.annotate_interface(group)
    frame = create_group(
        doc, "OpticalSensorFrame", "Optical sensor | fixed to integral carrier"
    )
    group.addObject(frame)
    return {"group": group, "sensor_frame": frame, "printed": [], "hardware": []}
