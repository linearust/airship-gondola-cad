"""Integrated fixed support and ordered preparation for individual servo service.

No printed servo bridge is removable. Service leaves the fixed frame and both
output-bearing pairs installed; only the small gears are first unmeshed.
"""

import FreeCAD as App

from gondola.contracts.drive import drive_for_document

from .geometry import TOL
from .propulsion_service import (
    continuous_path,
    module_service_shapes,
    retained_obstacles,
)


def servo_unit_service_waypoints(prefix):
    """Withdraw servo/horn/adapter after separately removing shaft and driver."""
    if prefix not in ("Port", "Starboard"):
        raise ValueError("Unknown servo side")
    sign = 1 if prefix == "Port" else -1
    return [
        (0, 0, 0),
        (0, sign * 14, 0),
        (sign * 60, sign * 14, 0),
    ]


def input_shaft_service_waypoints(prefix):
    """Clear the gear bore, then move outward before reaching the rotor jack."""
    if prefix not in ("Port", "Starboard"):
        raise ValueError("Unknown servo side")
    sign = 1 if prefix == "Port" else -1
    return [(0, 0, 0), (0, sign * 18, 0), (sign * 60, sign * 18, 0)]


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
