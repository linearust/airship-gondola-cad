"""Seating and ordered removal of the paired, replaceable servo drive.

The bearings and all four output shafts stay installed. These checks establish
nominal rigid-part access, not print tolerances, preload or loaded stiffness.
"""

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group
from gondola.contracts.drive import drive_for_document
from gondola.parts import servo_bridge

from .geometry import TOL, intersection_volume
from .propulsion_service import (
    continuous_path,
    driver_lateral_service_check,
    fastener_service_check,
    module_service_shapes,
    retained_obstacles,
)


def _plane_contact_area(first, second, axis, station):
    def faces(shape):
        return [
            face
            for face in shape.Faces
            if type(face.Surface).__name__ == "Plane"
            and all(abs(vertex.Point[axis] - station) < TOL for vertex in face.Vertexes)
        ]

    return sum(
        a.common(b).Area
        for a in faces(first)
        for b in faces(second)
        if a.normalAt(0, 0).dot(b.normalAt(0, 0)) < -0.99
    )


def bridge_joint_check(doc, module):
    """Check the actual two seating pads and unilateral locating faces."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"missing_parts": missing, "passed": False}
    frame, bridge = shapes["PropulsionFixedFrame"], shapes["ServoDriveBridge"]
    contacts = []
    for name, axis, station, minimum in servo_bridge.contact_planes():
        seat_frame, seat_bridge = frame, bridge
        if name.endswith("cradle_seat"):
            region = Part.makeBox(
                100,
                50,
                100,
                App.Vector(-50, 0 if name.startswith("positive") else -50, 0),
            )
            seat_frame, seat_bridge = frame.common(region), bridge.common(region)
        area = _plane_contact_area(seat_frame, seat_bridge, axis, station)
        contacts.append(
            {
                "interface": name,
                "plane_axis": axis,
                "plane_position_mm": station,
                "actual_contact_area_mm2": area,
                "required_contact_area_mm2": minimum,
                "passed": area >= minimum - TOL,
            }
        )
    overlap = intersection_volume(frame, bridge)
    spec = drive_for_document(doc)
    return {
        "contacts": contacts,
        "frame_bridge_intersection_mm3": overlap,
        "expected_bridge_sku": spec.bridge_sku,
        "actual_bridge_sku": doc.ServoDriveBridge.PrintSKU,
        "scope": "Two broad outer feet and a central shoe saddle support the shared wall and plate; unilateral Y and X datums locate the removable bridge. Bolt clearance does not locate the gear axes. The two outer feet share one seating height; the central support is higher and must meet its corresponding underside simultaneously. Actual seating without rocking, print distortion, centre distance, clamping friction and creep require the supplied parts and a physical prototype.",
        "passed": overlap < TOL
        and all(row["passed"] for row in contacts)
        and doc.ServoDriveBridge.PrintSKU == spec.bridge_sku,
    }


def _bridge_path(shape, waypoints, obstacles, spec):
    """Sweep the joined plate, pad and cradle stock with hardware holes filled.

    Containment of the actual bridge is mandatory. Filling its holes is
    conservative because every servo, ear bolt and clamp leaves with it.
    Spaces between the stock sections stay open in the exact face-prism sweep.
    """
    envelope = servo_bridge.bridge_blank(spec)
    missing = abs(shape.cut(envelope).Volume)
    path = continuous_path(envelope, waypoints, obstacles)
    return {
        **path,
        "envelope": "Planar bridge stock with case/fastener holes conservatively filled; actual bridge containment checked.",
        "uncovered_bridge_volume_mm3": missing,
        "passed": missing < TOL and path["passed"],
    }


def servo_module_service_check(doc, module):
    """Remove both small gears, two mount pairs, then the assembled input module."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"missing_parts": missing, "passed": False}
    removed, gear_paths, fasteners = set(), [], []
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        name = prefix + "OutputGear"
        path = continuous_path(
            shapes[name],
            [(0, 0, 0), (0, -sign * 35, 0)],
            retained_obstacles(shapes, removed | {name}),
        )
        gear_paths.append({"part": name, **path})
        removed.add(name)
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        stem = "ServoBridge" + prefix
        pair = {stem + "Bolt", stem + "Nut"}
        path = fastener_service_check(
            shapes[stem + "Bolt"],
            shapes[stem + "Nut"],
            retained_obstacles(shapes, removed | pair),
            nut_lateral_direction=(sign, 0, 0),
        )
        fasteners.append({"bolt": stem + "Bolt", "nut": stem + "Nut", **path})
        removed.update(pair)
    moving = {
        name
        for name in shapes
        if belongs_to_group(doc.getObject(name), doc.ServoDriveModule)
    }
    expected_moving = {"ServoDriveBridge"} | {
        prefix + suffix
        for prefix in ("Port", "Starboard")
        for suffix in (
            "Servo",
            "ServoHorn",
            "DriverGear",
            "InputShaft",
            "InputShaftClampBolt",
            "InputShaftClampNut",
            "HornGearAdapter",
            "HornGearClampNearBolt",
            "HornGearClampFarBolt",
            "ServoEarLowerBolt",
            "ServoEarLowerNut",
            "ServoEarUpperBolt",
            "ServoEarUpperNut",
        )
    }
    fixed = retained_obstacles(shapes, removed | moving)
    points = [(0, 0, 0), (0, 0, 0.5), (80, 0, 0.5)]
    rows = []
    spec = drive_for_document(doc)
    for name in sorted(moving):
        if name == "ServoDriveBridge":
            path = _bridge_path(shapes[name], points, fixed, spec)
        elif name.endswith("DriverGear"):
            axial = continuous_path(shapes[name], points[:2], fixed)
            lateral = driver_lateral_service_check(
                shapes[name],
                points[1],
                points[2],
                fixed,
                spec,
                1 if name.startswith("Port") else -1,
            )
            path = {
                **lateral,
                "segments": axial["segments"] + lateral["segments"],
                "passed": axial["passed"] and lateral["passed"],
            }
        else:
            path = continuous_path(shapes[name], points, fixed)
        rows.append({"part": name, "waypoints_mm": points, **path})
    return {
        "moving_parts": sorted(moving),
        "expected_moving_parts": sorted(expected_moving),
        "removed_output_gears": [row["part"] for row in gear_paths],
        "released_fasteners": sorted(removed - {row["part"] for row in gear_paths}),
        "output_gear_removal": gear_paths,
        "mount_fastener_release": fasteners,
        "part_paths": rows,
        "retained_parts": sorted(fixed),
        "coordinate_frame": "propulsion module",
        "scope": "Neutral, unpowered bench service with leads disconnected. Release the selected gear set screws and withdraw both small output gears inboard. Withdraw the two M2 mounting bolts, then slide each unthreaded hex nut outward. Lift the paired servo module 0.5 mm and slide it 80 mm in +X. Keep both servos, horns, adapters, driver gears, metal input stubs and both radial jack clamps assembled. Individual jack-clamp screw/nut access is a separate bench task and is not certified by this path. All output shafts, bearings and motor carriers remain installed. Reverse for installation, fully seat the three datums and recheck neutral, tooth phase and shaft-flat alignment. Adjacent rail equipment, flexible leads, set-screw tools and actual fit forces are not certified by this local bench path.",
        "passed": moving == expected_moving
        and all(row["passed"] for row in gear_paths + fasteners + rows),
    }
