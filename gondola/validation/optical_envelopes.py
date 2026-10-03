"""Conservative envelopes for the rigid optical head on the common platform."""

import math

import FreeCAD as App
import Part

from gondola.cad import placed_shape, union
from gondola.contracts.optical_sensors import SENSOR_PROFILES
from gondola.parts import optical_interface, optical_sensor

from .geometry import local_shape
from .optical_service import mount_tool_shapes, tray_stock_enclosures

V = App.Vector
PITCH_SAMPLE_ANGLES = (-20, -10, 0, 10, 20)
TOL = 1e-5
RAIL_ALIGNMENT_RESERVE_MM = 0.3
# Independent literals bind these envelopes to the actual shared mechanism.
PIVOT_MODULE = (0.0, 0.0, 27.5)
PIVOT_UPPER = (0.0, 0.0, 8.0)
OPTICAL_ORIGIN = (0.0, 27.0, 19.0)


def instrument_context(optical):
    """Fail closed before constructing a bound in an incorrect native frame."""
    if optical is None:
        raise ValueError("Missing rigid optical group")
    doc = optical.Document
    stage, module = (
        doc.getObject("InstrumentPitchStage"),
        doc.getObject("ElectronicsEquipmentModule"),
    )
    frame, tray = (
        doc.getObject("OpticalSensorFrame"),
        doc.getObject("OpticalSensorTray"),
    )
    if any(obj is None for obj in (stage, module, frame, tray)):
        raise ValueError("Missing common instrument or fixed optical frame")
    if (
        stage.getParentGeoFeatureGroup() != module
        or optical.getParentGeoFeatureGroup() != stage
        or frame.getParentGeoFeatureGroup() != optical
        or tray.getParentGeoFeatureGroup() != frame
        or not optical.Placement.isSame(
            App.Placement(V(*OPTICAL_ORIGIN), App.Rotation()), 1e-7
        )
        or not frame.Placement.isSame(App.Placement(), 1e-7)
        or not tray.Placement.isSame(App.Placement(), 1e-7)
        or list(optical.ExpressionEngine)
        or list(frame.ExpressionEngine)
        or list(tray.ExpressionEngine)
        or any(
            name in frame.PropertiesList
            for name in ("Pitch", "Roll", "MinimumAngle", "MaximumAngle")
        )
        or getattr(optical, "OpticalAttachmentMode", None) != "instrument"
        or any(
            name in optical.PropertiesList
            for name in ("Pitch", "MountSide", "CarrierHostName", "RailPositionX")
        )
        or any(
            doc.getObject(name) is not None
            for name in ("OpticalPitchStage", "OpticalRollStage", "OpticalMountBase")
        )
    ):
        raise ValueError(
            "Optical head does not rigidly follow the common instrument stage"
        )
    if not {"Pitch", "MinimumAngle", "MaximumAngle"}.issubset(stage.PropertiesList):
        raise ValueError("Missing instrument pitch controls")
    angle = float(stage.Pitch)
    if (
        not math.isfinite(angle)
        or float(stage.MinimumAngle) != -20
        or float(stage.MaximumAngle) != 20
    ):
        raise ValueError("Invalid instrument pitch domain")
    bounded = max(-20, min(20, angle))
    rotation = App.Rotation(V(0, 1, 0), bounded)
    expected = App.Placement(
        V(*PIVOT_MODULE) - rotation.multVec(V(*PIVOT_UPPER)), rotation
    )
    expressions = {
        path.lstrip("."): "".join(value.split())
        for path, value in stage.ExpressionEngine
    }
    clamp = "min(MaximumAngle;max(MinimumAngle;Pitch))"
    if not stage.Placement.isSame(expected, 1e-7) or expressions != {
        "Placement.Rotation.Angle": clamp,
        "Placement.Base.x": "-8mm*sin(" + clamp + ")",
        "Placement.Base.z": "27.5mm-8mm*cos(" + clamp + ")",
    }:
        raise ValueError("Instrument stage differs from its fixed-pivot pitch motion")
    if tray.Shape.isNull() or not tray.Shape.isValid() or len(tray.Shape.Solids) != 1:
        raise ValueError("Saved optical bracket must be one valid solid")
    return module, stage, frame, tray


def pitch_bound(shape, angle_limit_deg):
    """Exact axis-aligned enclosure of a box throughout a bounded Y rotation."""
    bounds = shape.BoundBox
    limit = math.radians(angle_limit_deg)
    xs, zs = [], []
    for x in (bounds.XMin, bounds.XMax):
        for z in (bounds.ZMin, bounds.ZMax):
            angles = [-limit, limit]
            for critical in (math.atan2(z, x), math.atan2(-x, z)):
                angles.extend(
                    critical + n * math.pi
                    for n in range(-2, 3)
                    if -limit <= critical + n * math.pi <= limit
                )
            for angle in angles:
                xs.append(x * math.cos(angle) + z * math.sin(angle))
                zs.append(-x * math.sin(angle) + z * math.cos(angle))
    return Part.makeBox(
        max(xs) - min(xs),
        bounds.YLength,
        max(zs) - min(zs),
        V(min(xs), bounds.YMin, min(zs)),
    )


def registered_instrument_bound(optical, shape):
    """Register in the foot frame, then enclose the full common-stage rotation."""
    module, _, frame, _ = instrument_context(optical)
    registered = optical_interface.registration_bound(shape)
    upper = placed_shape(registered, optical.Placement.multiply(frame.Placement))
    upper.translate(-V(*PIVOT_UPPER))
    bound = pitch_bound(upper, 20)
    bound.translate(V(*PIVOT_MODULE))
    return placed_shape(bound, module.getGlobalPlacement())


def external_field_bound(group, profile=None):
    """Contain both rectangular-field corners for every instrument pitch.

    The cone starts at the lowest transformed near-plane point. Its initial
    radius encloses every registered near-plane origin. Every forward ray is
    at most the diagonal FOV half-angle plus 20 degrees from module +Z, so the
    cone contains the complete continuous field, not only sampled centres.
    """
    profile = profile or optical_sensor.profile_for_document(group.Document)
    module, _, _, _ = instrument_context(group)
    half_x, half_y = (value / 2 for value in profile.size_mm[:2])
    front = optical_sensor.SENSOR_BOTTOM_Z + profile.optical_origin_min_z_mm
    face = Part.makeBox(2 * half_x, 2 * half_y, 1e-6, V(-half_x, -half_y, front))
    registered = optical_interface.registration_bound(face)
    registered.translate(V(*OPTICAL_ORIGIN) - V(*PIVOT_UPPER))
    near = pitch_bound(registered, 20).BoundBox
    minimum_z = near.ZMin + PIVOT_MODULE[2]
    centre_y = OPTICAL_ORIGIN[1]
    radius = (
        math.hypot(
            max(abs(near.XMin), abs(near.XMax)),
            max(abs(near.YMin - centre_y), abs(near.YMax - centre_y)),
        )
        + RAIL_ALIGNMENT_RESERVE_MM
    )
    angular_bound = math.radians(20) + math.atan(
        math.sqrt(2) * math.tan(math.radians(profile.flow_fov_deg / 2))
    )
    far = optical_interface.registration_bound(
        optical_sensor.optical_reserve_shape(profile)
    )
    far.translate(V(*OPTICAL_ORIGIN) - V(*PIVOT_UPPER))
    maximum_z = pitch_bound(far, 20).BoundBox.ZMax + PIVOT_MODULE[2]
    height = maximum_z - minimum_z
    bound = Part.makeCone(
        radius,
        radius + height * math.tan(angular_bound),
        height,
        V(0, centre_y, minimum_z),
    )
    bound = placed_shape(bound, module.getGlobalPlacement())
    return bound, {
        "minimum_front_z_in_module_frame_mm": minimum_z,
        "initial_radius_mm": radius,
        "assembly_registration_xy_mm": (
            optical_interface.MAX_REGISTRATION_X,
            optical_interface.MAX_REGISTRATION_Y,
        ),
        "assembly_registration_yaw_deg": math.degrees(
            optical_interface.MAX_REGISTRATION_YAW_RAD
        ),
        "rail_alignment_radius_allowance_mm": RAIL_ALIGNMENT_RESERVE_MM,
        "half_angle_deg": math.degrees(angular_bound),
        "height_mm": height,
        "pitch_axis_module_mm": PIVOT_MODULE,
        "instrument_pitch_range_deg": (-20, 20),
    }


def motion_bounds(optical):
    """Saved rigid bracket and both sensor alternatives over common pitch."""
    _, _, frame, saved_tray = instrument_context(optical)
    profile = optical_sensor.profile_for_document(optical.Document)
    for name, expected in (
        ("ModuleMTF02PEnvelope", optical_sensor.envelope_shape(profile)),
        ("MTF02PConnectorReserve", optical_sensor.connector_reserve_shape(profile)),
        (
            "MTF02POpticalClearanceReserve",
            optical_sensor.optical_reserve_shape(profile),
        ),
    ):
        obj = optical.Document.getObject(name)
        if (
            obj is None
            or obj.getParentGeoFeatureGroup() != frame
            or not obj.Placement.isSame(App.Placement(), 1e-7)
            or list(obj.ExpressionEngine)
            or obj.Shape.isNull()
            or not obj.Shape.isValid()
            or not obj.Shape.Solids
            or abs(local_shape(obj).cut(expected).Volume) > TOL
        ):
            raise ValueError(
                "Saved optical sensor geometry exceeds its declared envelope: " + name
            )
    regions, missing = tray_stock_enclosures(local_shape(saved_tray))
    if missing > TOL:
        raise ValueError(
            "Optical bracket stock exceeds its literal continuous envelopes"
        )
    tray_bound = union(
        [registered_instrument_bound(optical, region) for region in regions]
    )
    result = {
        "OpticalMountToolAccessBound": union(
            [
                registered_instrument_bound(optical, shape)
                for shape in mount_tool_shapes().values()
            ]
        )
    }
    for key, profile in SENSOR_PROFILES.items():
        result[f"{key}ContinuousOpticalFieldBound"] = external_field_bound(
            optical, profile
        )[0]
        result[f"{key}ContinuousTrayBound"] = tray_bound.copy()
        for name, shape in (
            ("Body", optical_sensor.envelope_shape(profile)),
            ("Connector", optical_sensor.connector_reserve_shape(profile)),
        ):
            result[f"{key}Continuous{name}Bound"] = registered_instrument_bound(
                optical, shape
            )
    return result
