"""Optical pitch access and disconnected bench disassembly reservations."""

import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, union, world_shape
from gondola.contracts import fasteners
from gondola.parts import optical_interface, optical_mount

from .geometry import intersection_volume, translation_sweep
from .wiring import collision_hits

V = App.Vector
TOL = 1e-5
TOOL_APPROACH_LENGTH_MM = 15.0
RELEASE_MARGIN_MM = 0.2


def _tray_service_envelope(shape):
    """Literal full pad/neck/ear stock, enclosing the saved rounded tray.

    The pad's lower edge rounds include cylinders transverse to the Y move.
    Filling only those outer rounds and the already released fastener holes
    preserves the space below the pad instead of filling the whole tray box.
    """
    envelope = union(
        [
            Part.makeCylinder(4, 2, V(), V(0, 1, 0)),
            Part.makeBox(4, 2, 4.5, V(-2, 0, 0)),
            Part.makeBox(18, 12, 2, V(-9, -6, 4.5)),
        ]
    )
    envelope.Placement = shape.Placement
    missing = abs(shape.cut(envelope).Volume)
    return envelope, missing


def pitch_tool_shape():
    """Module-local straight hex-key leg envelope, not a handle or socket model."""
    x, y, z = optical_mount.PIVOT_CENTRE
    return Part.makeCylinder(
        fasteners.SOCKET_KEY / math.sqrt(3),
        TOOL_APPROACH_LENGTH_MM,
        V(x, y + optical_mount.SCREW_BEARING_START - fasteners.SCREW_HEAD_HEIGHT, z),
        V(0, -1, 0),
    )


def pitch_tool_check(group, obstacles):
    """Check the fixed approach against supplied physical and reserved solids."""
    tool = pitch_tool_shape()
    tool.Placement = group.getGlobalPlacement()
    # The screw head is the tool's target; its exact socket is unmodeled.
    hits = collision_hits(
        tool,
        {
            name: shape
            for name, shape in obstacles.items()
            if name != "OpticalPitchBolt"
        },
        tolerance=TOL,
    )
    return {
        "key_across_flats_mm": fasteners.SOCKET_KEY,
        "straight_approach_length_mm": TOOL_APPROACH_LENGTH_MM,
        "collisions": hits,
        "passed": not hits,
        "scope": "A straight 1.5 mm hex-key leg approaching 15 mm along optical-local -Y. The envelope is fixed to the post, independent of pitch; moving tray/sensor clearance is checked at the stated sampled attitudes. Actual socket engagement, bent key/handle and hands remain unmodeled. Disconnect leads and remove the carrier for bench access as needed; passing this reservation does not establish complete on-balloon service.",
    }


def pitch_disassembly_check(doc, kit):
    """Release nut, withdraw screw, then remove the neutral tray and sensor."""
    group, stage = doc.OpticalFlowModule, doc.OpticalPitchStage
    inverse = group.getGlobalPlacement().inverse()
    foot_fasteners = {
        f"OpticalFoot{kind}{index}"
        for kind in ("Nut", "Bolt")
        for index in optical_interface.CLAMP_CENTRES
    }
    remaining = {}
    for obj in kit:
        if obj.Name in foot_fasteners:
            continue  # Removed first by the separate, ordered foot-service check.
        shape = world_shape(obj)
        shape.Placement = inverse.multiply(shape.Placement)
        remaining[obj.Name] = shape
    neutral = stage.Placement.Rotation.isSame(App.Rotation(), TOL)
    paths = []

    def check_path(name, shape, delta, obstacles):
        sweep_input = shape
        enclosure = None
        if name == "TrayAssembly/OpticalSensorTray":
            sweep_input, missing = _tray_service_envelope(shape)
            enclosure = {
                "kind": "literal full pad, neck and coaxial ear",
                "uncovered_saved_stock_mm3": missing,
                "passed": missing < TOL,
            }
        swept, method = translation_sweep(sweep_input, delta)
        hits = [
            {"object": other, "intersection_mm3": volume}
            for other, target in obstacles.items()
            if (volume := intersection_volume(swept, target)) > TOL
        ]
        paths.append(
            {
                "part": name,
                "translation_mm": delta,
                "method": method,
                "conservative_enclosure": enclosure,
                "collisions": hits,
                "passed": not hits and (enclosure is None or enclosure["passed"]),
            }
        )

    nut_release = optical_mount.BOLT_TIP - optical_mount.NUT_START + RELEASE_MARGIN_MM
    for name, distance in (
        ("OpticalPitchNut", nut_release),
        ("OpticalPitchBolt", -optical_mount.SCREW_LENGTH - RELEASE_MARGIN_MM),
    ):
        moving = remaining.pop(name)
        check_path(name, moving, (0.0, distance, 0.0), remaining)
    moving_names = {
        obj.Name
        for obj in kit
        if belongs_to_group(obj, stage) and obj.Name in remaining
    }
    fixed = {
        name: shape for name, shape in remaining.items() if name not in moving_names
    }
    distance = (
        max(shape.BoundBox.YMax for shape in fixed.values())
        - min(remaining[name].BoundBox.YMin for name in moving_names)
        + RELEASE_MARGIN_MM
    )
    for name in sorted(moving_names):
        check_path("TrayAssembly/" + name, remaining[name], (0.0, distance, 0.0), fixed)
    return {
        "neutral_pitch": neutral,
        "previously_removed_foot_fasteners": sorted(foot_fasteners),
        "paths": paths,
        "passed": neutral
        and bool(moving_names)
        and all(row["passed"] for row in paths),
        "scope": "Disconnect the sensor lead, use the checked foot-removal sequence and support the complete optical head on a bench. Set pitch to zero and support the tray; keep the screw head seated while unthreading the nut along +Y beyond the tip, withdraw the screw along -Y, then move the tray and sensor together along +Y. Screw paths follow the actual nominal stack; tray travel separates the saved bounding boxes by 0.2 mm. The tray sweep uses a literal full-pad/neck/ear enclosure only after proving that it contains all saved tray stock; its released holes and external rounds are conservatively filled while the space below the pad stays open. Continuous rigid translation checks do not model thread rotation, hand access, cables or force.",
    }
