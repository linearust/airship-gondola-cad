"""Rigid detachable MTF bracket on the common adjustable instrument plate."""

import json

import FreeCAD as App

from gondola.cad import box, create_group, create_printed_part, set_property, union
from gondola.contracts.optical_attachment import DEFAULT_HOST

from . import optical_interface
from .edge_blends import fillet_selected, near

V = App.Vector
TRAY_SIZE_MM = (18.0, 12.0)
TRAY_CORNER_RADIUS = 1.0
TRAY_BOTTOM_Z = 18.5
TRAY_TOP_Z = 20.5
ADHESIVE_ALLOWANCE = 1.0


def sensor_tray_shape():
    """Two-sided rigid support, continuous adhesive pad and detachable foot."""
    pad = box(18, 12, 2, (-9, -6, TRAY_BOTTOM_Z))
    pad = fillet_selected(
        pad,
        TRAY_CORNER_RADIUS,
        lambda e, b: near(b.ZLength, 2),
        4,
        "Optical adhesive pad corners",
    )
    body = union(
        [
            optical_interface.foot_shape(),
            box(3, 8, 16.5, (-25, -4, 2)),
            box(3, 8, 16.5, (22, -4, 2)),
            box(50, 4, 2, (-25, -2, TRAY_BOTTOM_Z)),
            pad,
        ]
    ).removeSplitter()
    body = fillet_selected(
        body,
        0.5,
        lambda e, b: (
            near(b.ZLength, 0)
            and near(b.XLength, 0)
            and (
                (
                    near(b.ZMin, 2)
                    and near(b.YLength, 8)
                    and any(near(b.XMin, x) for x in (-25, -22, 22, 25))
                )
                or (
                    near(b.ZMin, TRAY_BOTTOM_Z)
                    and near(b.YLength, 4)
                    and any(near(b.XMin, x) for x in (-22, 22))
                )
            )
        ),
        6,
        "Optical bracket support roots",
    )
    body = body.removeSplitter()
    if not body.isValid() or len(body.Solids) != 1:
        raise RuntimeError("Optical bracket must be one valid solid")
    return body


def mount_contract():
    return {
        "mechanism": "One rigid removable optical bracket on the shared FC and optical platform",
        "attachment_mode": "instrument",
        "adjustment_degrees_of_freedom": 0,
        "shared_adjustment_control": "InstrumentPitchStage.Pitch",
        "self_levelling": False,
        "holding_torque_verified": False,
        "physical_angle_stops_modeled": False,
        "tray_origin_in_module_mm": (0.0, 0.0, 0.0),
        "attachment_interface": optical_interface.interface_contract(),
        "tray_size_mm": TRAY_SIZE_MM,
        "tray_plan_corner_radius_mm": TRAY_CORNER_RADIUS,
        "tray_bottom_z_in_sensor_frame_mm": TRAY_BOTTOM_Z,
        "tray_top_z_in_sensor_frame_mm": TRAY_TOP_Z,
        "adhesive_allowance_mm": ADHESIVE_ALLOWANCE,
        "support_sections_mm": {
            "uprights": (3.0, 8.0),
            "crossbar": (4.0, 2.0),
            "root_radius": 0.5,
        },
        "hardware": "Two M2x8 button-head screws and two ordinary M2 nuts, in existing opposite side-slot endpoints of ElectronicsMount. No optical hinge, rail shoe, added plate holes or washers.",
        "assembly": "Seat the rigid foot flat on the common plate at Y27, align both screws with the existing X-19/+19 slot ends, and tighten only after checking complete bearing lands. For service, remove both foot pairs, slide the bracket 10 mm toward positive local Y, then lift it 40 mm; remove this bracket before lifting the FC.",
        "adjustment": "FC and optical sensor move together on InstrumentPitchStage. The bracket has no independent adjustment. Disconnect leads before adjustment and regenerate the motor-lead planning route, then verify real cable slack and clear field of view. No active stabilization or loaded retention qualification.",
        "sensor_interface": "Continuous 18x12 mm insulating adhesive pad for either MTF-01P or MTF-02P. Optical face is local +Z. Actual rear contact, retention, aperture origins and connector/wire fit remain unverified; no invented sensor fixing holes.",
    }


def build_optical_mount(doc, host):
    if host.Document != doc or host.Name != DEFAULT_HOST:
        raise ValueError(
            "Optical bracket requires InstrumentPitchStage in the same document"
        )
    group = create_group(
        doc, "OpticalFlowModule", "Optical flow | rigid shared-platform bracket"
    )
    host.addObject(group)
    group.Placement = optical_interface.placement()
    set_property(group, "OpticalAttachmentMode", "instrument")
    group.setEditorMode("OpticalAttachmentMode", 1)
    contract = json.dumps(mount_contract(), sort_keys=True)
    set_property(group, "OpticalMountContract", contract)
    set_property(
        group,
        "AdjustmentControls",
        "InstrumentPitchStage.Pitch; shared FC and optical adjustment. No independent optical control.",
    )
    set_property(group, "HoldingTorqueVerified", False, "App::PropertyBool")
    set_property(group, "SelfLevelling", False, "App::PropertyBool")
    optical_interface.annotate_interface(group)
    frame = create_group(
        doc, "OpticalSensorFrame", "Optical sensor | fixed to common platform"
    )
    group.addObject(frame)
    tray = create_printed_part(
        doc,
        frame,
        "OpticalSensorTray",
        "PRINT | rigid optical bracket",
        sensor_tray_shape(),
        App.Rotation(),
        "PA12 SLS/MJF rigid optical bracket; two M2 pairs attach its foot to the common FC plate. Shared instrument pitch only. Qualify printed fit, retention, adhesive and pointing.",
    )
    set_property(tray, "PrintSKU", "OpticalSensorTray")
    set_property(tray, "OpticalMountContract", contract)
    set_property(tray, "HoldingTorqueVerified", False, "App::PropertyBool")
    optical_interface.annotate_interface(tray)
    hardware = optical_interface.build_hardware(doc, group)
    doc.recompute()
    return {
        "group": group,
        "sensor_frame": frame,
        "printed": [tray],
        "hardware": hardware,
    }
