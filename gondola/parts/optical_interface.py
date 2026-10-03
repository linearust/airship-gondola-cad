"""Nominal adhesive sensor pad integral with the instrument upper carrier."""

import json

import FreeCAD as App

from gondola.cad import set_property
from gondola.contracts.optical_attachment import (
    DEFAULT_HOST,
    SENSOR_FRAME_ORIGIN_IN_STAGE,
)

V = App.Vector


def placement():
    return App.Placement(V(*SENSOR_FRAME_ORIGIN_IN_STAGE), App.Rotation())


def interface_contract():
    return {
        "attachment_mode": "instrument",
        "mechanism": "Sensor adhesive pad and bridge integral with ElectronicsMount",
        "industry_standard_claimed": False,
        "default_host": DEFAULT_HOST,
        "support_part": "ElectronicsMount",
        "sensor_frame_origin_in_stage_mm": SENSOR_FRAME_ORIGIN_IN_STAGE,
        "pad_size_mm": (18.0, 12.0, 2.0),
        "pad_top_in_stage_mm": 44.0,
        "hardware": "No separate optical support or foot fasteners",
        "registration": "No detachable printed joint. Adhesive placement, thickness, finished pad flatness and measured sensor orientation remain unqualified.",
        "service": "Disconnect the sensor, release external retention and lift the bare sensor local +Z40 mm. The integral bridge remains on the upper carrier. FC service requires neutral 0 degrees, then uses the open local X passage after its actual mounting hardware and leads are removed. Restore and verify the calibrated body-reference setup angle before operation.",
        "qualification": "Nominal printed geometry only; verify adhesive retention, stiffness, creep, pointing and the actual IMU/optical origins. Integral support does not imply zero position offsets.",
    }


def attachment_description(optical):
    if str(getattr(optical, "OpticalAttachmentMode", "")) != "instrument":
        raise ValueError("Optical sensor requires the common instrument attachment")
    host = optical.getParentGeoFeatureGroup()
    if host is None or host.Name != DEFAULT_HOST:
        raise ValueError("Optical sensor is not attached to InstrumentPitchStage")
    return {
        "mode": "instrument",
        "host": host.Name,
        "support_part": "ElectronicsMount",
        "sensor_frame_origin_in_stage_mm": SENSOR_FRAME_ORIGIN_IN_STAGE,
    }


def annotate_interface(obj):
    set_property(
        obj,
        "OpticalInterfaceContract",
        json.dumps(interface_contract(), sort_keys=True),
    )
    set_property(obj, "OpticalFitVerified", False, "App::PropertyBool")


def registration_bound(shape):
    """The integral support has no printed-joint registration play."""
    return shape.copy()


def manufacturing_wall_probes():
    return [
        (
            "instrument_bridge_negative_post",
            "ElectronicsMount",
            (-31.51, -29.5, 30),
            (-27.49, -29.5, 30),
            4.0,
        ),
        (
            "instrument_bridge_positive_post",
            "ElectronicsMount",
            (27.49, 29.5, 30),
            (31.51, 29.5, 30),
            4.0,
        ),
        (
            "instrument_bridge_diagonal_roof",
            "ElectronicsMount",
            (15, 15, 40.99),
            (15, 15, 44.01),
            3.0,
        ),
        (
            "instrument_optical_pad",
            "ElectronicsMount",
            (6, 0, 41.99),
            (6, 0, 44.01),
            2.0,
        ),
    ]
