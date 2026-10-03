"""Shared conservative optical field and pitch envelopes.

These helpers create new shapes without changing native assembly controls.
Collision policy and service sequencing belong to their respective validators.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import placed_shape, union
from gondola.contracts.optical_attachment import resolve_mount_mode
from gondola.contracts.optical_sensors import SENSOR_PROFILES
from gondola.parts import optical_interface, optical_mount, optical_sensor

from .optical_service import pitch_tool_shape, tray_stock_enclosures

V = App.Vector
PITCH_SAMPLE_ANGLES = (-20, -10, 0, 10, 20)
RAIL_ALIGNMENT_RESERVE_MM = 0.3


def external_field_bound(group, profile=None):
    """Contain the field with a conservative assembly-alignment reserve."""
    profile = profile or optical_sensor.profile_for_document(group.Document)
    half_x, half_y = (v / 2 for v in profile.size_mm[:2])
    front = optical_sensor.SENSOR_BOTTOM_Z + profile.optical_origin_min_z_mm
    mode = resolve_mount_mode(str(group.OpticalAttachmentMode))
    pivot = optical_mount.pivot_centre(mode)
    angle = math.radians(optical_mount.angle_limit_deg(mode))
    z = pivot[2] + front * math.cos(angle) - half_x * math.sin(angle)
    registration = RAIL_ALIGNMENT_RESERVE_MM + math.hypot(
        optical_interface.MAX_REGISTRATION_X, optical_interface.MAX_REGISTRATION_Y
    )
    radius = math.sqrt(half_x**2 + half_y**2 + front**2) + registration
    angular_bound = angle + math.atan(
        math.sqrt(2) * math.tan(math.radians(profile.flow_fov_deg / 2))
    )
    axial_depth = optical_sensor.OPTICAL_RESERVE_LENGTH_MM
    # Cover the far corners of the rectangular field too: after pitch, a
    # corner can extend farther in module Z than the nominal axial distance.
    height = (
        math.hypot(
            front + axial_depth,
            half_x + axial_depth * math.tan(math.radians(profile.flow_fov_deg / 2)),
        )
        + pivot[2]
        - z
    )
    bound = Part.makeCone(
        radius,
        radius + height * math.tan(angular_bound),
        height,
        V(pivot[0], pivot[1], z),
    )
    bound.Placement = group.getGlobalPlacement()
    return bound, {
        "minimum_front_z_in_module_frame_mm": z,
        "initial_radius_mm": radius,
        "assembly_registration_radius_allowance_mm": registration,
        "half_angle_deg": math.degrees(angular_bound),
        "height_mm": height,
    }


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
        App.Vector(min(xs), bounds.YMin, min(zs)),
    )


def motion_bounds(optical):
    """Both mutually exclusive sensors and connectors, continuous pitch."""

    mode = str(optical.OpticalAttachmentMode)
    result = {}
    if mode == "carrier":
        result["OpticalPitchToolAccessBound"] = placed_shape(
            optical_interface.registration_bound(pitch_tool_shape(mode), mode),
            optical.getGlobalPlacement(),
        )
    # Keep empty space between the raised pad and offset shoe available. Each
    # literal region independently bounds the entire pitch and registration
    # domain; their union therefore contains the whole rigid tray at every
    # allowed pose without filling the enclosing box between distant regions.
    saved_tray = optical.Document.getObject("OpticalSensorTray")
    stage = optical.Document.getObject("OpticalPitchStage")
    if (
        saved_tray is None
        or stage is None
        or saved_tray.getParentGeoFeatureGroup() != stage
        or stage.getParentGeoFeatureGroup() != optical
        or saved_tray.Shape.isNull()
        or not saved_tray.Shape.isValid()
        or len(saved_tray.Shape.Solids) != 1
    ):
        raise ValueError("Missing or inconsistent saved optical tray hierarchy")
    limit = optical_mount.angle_limit_deg(mode)
    controls = ("Pitch", "MinimumAngle", "MaximumAngle")
    if any(name not in stage.PropertiesList for name in controls):
        raise ValueError("Missing optical pitch controls")
    pitch = float(stage.Pitch.Value)
    if (
        not math.isfinite(pitch)
        or stage.MinimumAngle.Value != -limit
        or stage.MaximumAngle.Value != limit
        or (mode == "rail" and pitch != 0)
        or (stage.Placement.Base - App.Vector(*optical_mount.pivot_centre(mode))).Length
        > 1e-5
        or not stage.Placement.Rotation.isSame(
            App.Rotation(App.Vector(0, 1, 0), max(-limit, min(limit, pitch))), 1e-7
        )
    ):
        raise ValueError(
            "Saved optical tray stage differs from its bounded pitch domain"
        )
    tray = saved_tray.Shape.copy()
    regions, missing = tray_stock_enclosures(tray)
    if missing > 1e-5:
        raise ValueError("Optical tray stock exceeds its literal continuous envelopes")
    tray_bounds = []
    for region in regions:
        bound = pitch_bound(region, optical_mount.angle_limit_deg(mode))
        bound.translate(App.Vector(*optical_mount.pivot_centre(mode)))
        tray_bounds.append(optical_interface.registration_bound(bound, mode))
    tray_bound = placed_shape(union(tray_bounds), optical.getGlobalPlacement())
    for key, profile in SENSOR_PROFILES.items():
        result[f"{key}ContinuousOpticalFieldBound"] = external_field_bound(
            optical, profile
        )[0]
        result[f"{key}ContinuousTrayBound"] = tray_bound.copy()
        for name, shape in (
            ("Body", optical_sensor.envelope_shape(profile)),
            ("Connector", optical_sensor.connector_reserve_shape(profile)),
        ):
            bound = pitch_bound(shape, optical_mount.angle_limit_deg(mode))
            bound.translate(App.Vector(*optical_mount.pivot_centre(mode)))
            bound = optical_interface.registration_bound(bound, mode)
            result[f"{key}Continuous{name}Bound"] = placed_shape(
                bound, optical.getGlobalPlacement()
            )
    return result
