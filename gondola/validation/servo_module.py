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
    """Check the central seat, shared clamp face and bounded locating-key fit."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"missing_parts": missing, "passed": False}
    frame, bridge = shapes["PropulsionFixedFrame"], shapes["ServoDriveBridge"]
    contacts = []
    for name, axis, station, minimum, bounds in servo_bridge.contact_planes():
        seat_frame, seat_bridge = frame, bridge
        if bounds is not None:
            x, y, width, length = bounds
            region = Part.makeBox(
                width,
                length,
                100,
                App.Vector(x, y, 0),
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
                "support_region_xy_mm": list(bounds) if bounds is not None else None,
                "passed": area >= minimum - TOL,
            }
        )
    overlap = intersection_volume(frame, bridge)
    key = bridge_key_check(frame, bridge)
    spec = drive_for_document(doc)
    return {
        "key_fit": key,
        "contacts": contacts,
        "frame_bridge_intersection_mm3": overlap,
        "expected_bridge_sku": spec.bridge_sku,
        "actual_bridge_sku": doc.ServoDriveBridge.PrintSKU,
        "scope": "The central roof seats the bridge in Z; the shared bolt clamps its cheek to the frame in Y. A deep rectangular key bounds X/Z displacement and rotation with nominal 0.2mm side clearance. Seat and align the gear mesh before tightening; this is not automatic centering. Print fit, distortion, loaded stiffness, friction and creep require a prototype.",
        "passed": overlap < TOL
        and key["passed"]
        and all(row["passed"] for row in contacts)
        and doc.ServoDriveBridge.PrintSKU == spec.bridge_sku,
    }


def bridge_key_check(frame, bridge):
    """Reject absent keys or enlarged/missing pocket walls independently of builders."""
    key = Part.makeBox(5, 2.5, 5.5, App.Vector(20, -7.75, 4))
    bore = Part.makeCylinder(1.7, 14, App.Vector(15, -11, 7), App.Vector(0, 1, 0))
    recess = Part.makeBox(5.4, 2.7, 5.9, App.Vector(19.8, -7.95, 3.8))
    head_recess = Part.makeCylinder(
        3.2, 2, App.Vector(15, -9.75, 7), App.Vector(0, 1, 0)
    )
    region = Part.makeBox(18, 4.5, 10.3, App.Vector(9, -9.75, 2.2))
    pocket_walls = region.cut(recess).cut(bore).cut(head_recess)
    backing = Part.makeCylinder(
        3, 2.5, App.Vector(15, -7.75, 7), App.Vector(0, 1, 0)
    ).cut(bore)
    frame_backing = Part.makeCylinder(
        3, 4, App.Vector(15, -5.25, 7), App.Vector(0, 1, 0)
    ).cut(bore)
    rows = {
        "missing_solid_head_backing_mm3": abs(backing.cut(bridge).Volume),
        "missing_solid_frame_backing_mm3": abs(frame_backing.cut(frame).Volume),
        "missing_key_mm3": abs(key.cut(frame).Volume),
        "key_in_pocket_interference_mm3": abs(key.common(bridge).Volume),
        "recess_obstruction_mm3": abs(recess.common(bridge).Volume),
        "missing_pocket_walls_mm3": abs(pocket_walls.cut(bridge).Volume),
    }
    return {
        **rows,
        "nominal_side_clearance_mm": 0.2,
        "nominal_depth_clearance_mm": 0.2,
        "remaining_cheek_skin_mm": 1.8,
        "minimum_recess_edge_rim_mm": 1.6,
        "passed": all(value < TOL for value in rows.values()),
    }


def _bridge_path(shape, waypoints, obstacles, spec):
    """Sweep the joined flat plate and cradle stock with hardware holes filled.

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
    """Bench removal after the common rail screw/nut and rail have been removed."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"missing_parts": missing, "passed": False}
    # The saved full assembly includes the rail pair; source bench modules do
    # not. Inventory has already been checked, then explicitly remove only the
    # documented common clamp for this off-rail bench sequence.
    rail_pair = {
        module["group"].Name + suffix for suffix in ("RailMountScrew", "RailMountNut")
    }
    present_rail_pair = rail_pair & shapes.keys()
    if present_rail_pair and present_rail_pair != rail_pair:
        return {
            "passed": False,
            "error": "Incomplete common rail clamp",
            "missing_parts": sorted(rail_pair - shapes.keys()),
        }
    shapes = {name: shape for name, shape in shapes.items() if name not in rail_pair}
    removed, gear_paths = set(), []
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        name = prefix + "OutputGear"
        path = continuous_path(
            shapes[name],
            [(0, 0, 0), (0, -sign * 35, 0)],
            retained_obstacles(shapes, removed | {name}),
        )
        gear_paths.append({"part": name, **path})
        removed.add(name)
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
    from gondola.contracts import servo_horns

    for prefix in ("Port", "Starboard"):
        if not servo_horns.profile(
            str(doc.getObject(prefix + "ServoHorn").HornProfile)
        ).threaded:
            expected_moving.update(
                prefix + "HornGearClamp" + side + "Nut" for side in ("Near", "Far")
            )
    fixed = retained_obstacles(shapes, removed | moving)
    points = list(servo_bridge.SERVICE_WAYPOINTS)
    rows = []
    spec = drive_for_document(doc)
    for name in sorted(moving):
        if name == "ServoDriveBridge":
            path = _bridge_path(shapes[name], points, fixed, spec)
        elif name.endswith("DriverGear"):
            axial = continuous_path(shapes[name], points[:-1], fixed)
            lateral = driver_lateral_service_check(
                shapes[name],
                points[-2],
                points[-1],
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
        "shared_rail_fasteners_removed_before_bench": sorted(present_rail_pair),
        "prerequisites": "Remove the shared M3x12 rail screw and nut, lift the whole propulsion assembly off the rail and disconnect leads before this local bench check. Rail attachment service is checked separately.",
        "part_paths": rows,
        "retained_parts": sorted(fixed),
        "coordinate_frame": "propulsion module",
        "scope": "Neutral, unpowered bench service after rail release. Release gear set screws and withdraw both small output gears inboard. Shift the paired servo module 2.7mm in -Y to disengage its locating key, lift 0.5mm and slide 80mm in +X. Servos, horns, adapters, driver gears, input stubs and radial clamps stay assembled. Output shafts, bearings and carriers remain installed. Reverse for installation; seat the central roof, align mesh within key clearance and tighten the shared rail clamp. Adjacent equipment, wires, tools and fit forces are outside this local bench path.",
        "passed": moving == expected_moving
        and all(row["passed"] for row in gear_paths + rows),
    }
