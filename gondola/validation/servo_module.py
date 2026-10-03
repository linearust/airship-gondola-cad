"""Integrated fixed support and ordered preparation for individual servo service.

No printed servo bridge is removable. Service leaves the fixed frame and both
output-bearing pairs installed; only the small gears are first unmeshed.
"""

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group
from gondola.contracts.drive import drive_for_document

from .geometry import TOL
from .propulsion_service import module_service_shapes
from .service_geometry import (
    continuous_path,
    retained_obstacles,
)


def servo_unit_service_waypoints(prefix):
    """Withdraw servo/horn/adapter after separately removing shaft and driver."""
    if prefix not in ("Port", "Starboard"):
        raise ValueError("Unknown servo side")
    sign = 1 if prefix == "Port" else -1
    return [
        (0, 0, 0),
        (0, sign * 13, 0),
        (sign * 60, sign * 13, 0),
    ]


def input_shaft_service_waypoints(prefix):
    """Clear the retained input bearing/housing after parking the loose rotor."""
    if prefix not in ("Port", "Starboard"):
        raise ValueError("Unknown servo side")
    sign = 1 if prefix == "Port" else -1
    return [(0, 0, 0), (0, sign * 32, 0), (sign * 60, sign * 32, 0)]


def input_service_rotor_parking_angle_deg(prefix):
    """Unmeshed output-only service pose; input servo and gear stay neutral."""
    if prefix not in ("Port", "Starboard"):
        raise ValueError("Unknown servo side")
    return 90.0


def park_output_rotor_for_input_service(doc, module, prefix, shapes, removed):
    """Certify the rotor's complete rotation envelope, then retain its parked pose.

    The output gear must already be absent. Copies are transformed directly so
    native gear-ratio expressions cannot rotate the still-installed input unit.
    """
    from .rotation_envelope import full_orbit_envelope

    sign = 1 if prefix == "Port" else -1
    angle = input_service_rotor_parking_angle_deg(prefix)
    group = doc.getObject(prefix + "Pod")
    drive = doc.getObject(prefix + "InputDrive")
    neutral = (
        group is not None
        and drive is not None
        and group.Placement.Rotation.isSame(App.Rotation(), TOL)
        and drive.Placement.Rotation.isSame(App.Rotation(), TOL)
    )
    moving = {
        name
        for name in shapes
        if belongs_to_group(doc.getObject(name), group) and name not in removed
    }
    fixed = retained_obstacles(shapes, removed | moving)
    axis = (0, sign * 75, 50)
    rows = []
    for name in sorted(moving):
        if "OutputShaft" in name:
            envelope = Part.makeCylinder(
                1.5, 42, App.Vector(0, sign * 13, 50), App.Vector(0, sign, 0)
            )
            evidence = {
                "method": "literal coaxial round output-shaft envelope",
                "radius_mm": 1.5,
                "scope": "Complete42mm stock and both filed regions fit inside the unchanged round journal cylinder; contact with nominal bearing bores is retained, not excluded.",
            }
        else:
            envelope, evidence = full_orbit_envelope(shapes[name], axis)
        outside = abs(shapes[name].cut(envelope).Volume)
        hits = {n: abs(envelope.common(s).Volume) for n, s in fixed.items()}
        rows.append(
            {
                "part": name,
                "envelope": evidence,
                "outside_envelope_mm3": outside,
                "intersection_mm3": hits,
                "passed": outside < TOL and all(v < TOL for v in hits.values()),
            }
        )
    parked = dict(shapes)
    for name in moving:
        parked[name] = shapes[name].copy()
        parked[name].rotate(App.Vector(*axis), App.Vector(0, 1, 0), angle)
    return parked, {
        "pod": prefix,
        "removed_output_gear": prefix + "OutputGear",
        "moving_parts": sorted(moving),
        "retained_parts": sorted(fixed),
        "axis_origin_mm": list(axis),
        "axis_direction": [0, 1, 0],
        "angle_deg": angle,
        "input_remains_neutral": True,
        "initial_input_and_output_neutral": neutral,
        "continuous_rotation": rows,
        "scope": "After unmeshing, support and park only this output rotor; leave the input servo neutral. Complete all-angle envelopes certify this parking arc against every retained physical part, including input shaft/support. Bearings and caps stay fixed. Reverse the rotation only after the input shaft is reinstalled and before refitting the output gear. Flexible wires and loaded operation are unqualified.",
        "passed": prefix + "OutputGear" in removed
        and neutral
        and bool(moving)
        and all(row["passed"] for row in rows),
    }


def driver_gear_service_waypoints(prefix):
    """Remove the supported loose driver laterally after its shaft is absent."""
    if prefix not in ("Port", "Starboard"):
        raise ValueError("Unknown servo side")
    sign = 1 if prefix == "Port" else -1
    return [(0, 0, 0), (sign * 60, 0, 0)]


def input_jack_backoff_vector(prefix):
    """Module-frame0.2mm release along the selected outward/downward jack axis."""
    from gondola.parts import servo_coupling

    if prefix not in ("Port", "Starboard"):
        raise ValueError("Unknown servo side")
    delta = servo_coupling.shaft_frame_point(-0.2, 0, 0)
    if prefix == "Starboard":
        delta = App.Rotation(App.Vector(0, 0, 1), 180).multVec(delta)
    return tuple(delta)


def integrated_frame_check(doc, module):
    """One mirrored, connected fixed print contains both servo support datums."""
    shapes, missing = module_service_shapes(doc, module)
    obj = doc.getObject("PropulsionFixedFrame")
    if missing or obj is None or "PropulsionFixedFrame" not in shapes:
        return {"passed": False, "missing_parts": missing or ["PropulsionFixedFrame"]}
    frame = shapes["PropulsionFixedFrame"]
    opposite = frame.copy()
    opposite.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
    symmetry_error = abs(frame.cut(opposite).Volume) + abs(opposite.cut(frame).Volume)
    copies = sum(part is obj for part in module["printed"])
    obsolete = [
        name for name in ("ServoDriveBridge",) if doc.getObject(name) is not None
    ]
    spec = drive_for_document(doc)
    return {
        "fixed_frame": obj.Name,
        "registered_print_count": copies,
        "single_valid_solid": frame.isValid() and len(frame.Solids) == 1,
        "half_turn_symmetry_difference_mm3": symmetry_error,
        "obsolete_separate_supports": obsolete,
        "expected_frame_sku": spec.frame_sku,
        "actual_frame_sku": getattr(obj, "PrintSKU", None),
        "scope": "One connected and horizontally mirrored fixed print; servo-seat, bearing, rail-joint and service checks qualify geometry separately. Integration is not a strength, coaxiality or physical fit qualification.",
        "passed": copies == 1
        and not obsolete
        and frame.isValid()
        and len(frame.Solids) == 1
        and symmetry_error < TOL
        and getattr(obj, "PrintSKU", None) == spec.frame_sku,
    }


def servo_service_preparation_check(doc, module):
    """Unmesh both output gears with the whole remaining mechanism retained."""
    shapes, missing = module_service_shapes(doc, module)
    expected = {prefix + "OutputGear" for prefix in ("Port", "Starboard")}
    if missing or not expected <= shapes.keys():
        return {
            "passed": False,
            "missing_parts": missing or sorted(expected - shapes.keys()),
        }
    removed, paths = set(), []
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        name = prefix + "OutputGear"
        points = [
            (0, 0, 0),
            (0, -sign * 11, 0),
            (0, -sign * 11, 20),
            (30, -sign * 11, 20),
        ]
        path = continuous_path(
            shapes[name], points, retained_obstacles(shapes, removed | {name})
        )
        paths.append({"part": name, "waypoints_mm": points, **path})
        removed.add(name)
    return {
        "removed_parts": sorted(removed),
        "retained_parts": sorted(shapes.keys() - removed),
        "output_gear_removal": paths,
        "coordinate_frame": "propulsion module",
        "scope": "Unpowered neutral preparation: release both output gear set screws and withdraw each small gear11mm inboard, lift20mm and move30mm in X. The one-piece fixed frame, bearings, caps, output shafts and rotors stay installed. Next remove the selected input stub and loose driver before releasing its ear pairs and withdrawing the servo/horn/adapter. Disconnect leads. Actual gear set-screw/tool access remains unverified.",
        "passed": all(row["passed"] for row in paths),
    }
