"""Seating and ordered removal of the paired, replaceable servo drive.

The bearings and all four output shafts stay installed. These checks establish
nominal rigid-part access, not print tolerances, preload or loaded stiffness.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, translated_shape, union
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
    """Require both fitted U walls and the complete flat frame roof."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"missing_parts": missing, "passed": False}
    frame, bridge = shapes["PropulsionFixedFrame"], shapes["ServoDriveBridge"]
    planes = (
        ("full_roof_support", 2, 12.5, 552, (-23, -6, 46, 12)),
        ("negative_y_beam_roof", 2, 12.5, 90, (-9, -11, 18, 5)),
        ("positive_y_beam_roof", 2, 12.5, 90, (-9, 6, 18, 5)),
        ("negative_y_wall", 1, -6, 27.6 * 10.3 - 2 * math.pi * 1.7**2, None),
        ("positive_y_wall", 1, 6, 27.6 * 10.3 - 2 * math.pi * 1.7**2, None),
    )
    contacts = []
    for name, axis, station, minimum, bounds in planes:
        seat_frame, seat_bridge = frame, bridge
        if bounds is not None:
            x, y, width, length = bounds
            region = Part.makeBox(width, length, 100, App.Vector(x, y, 0))
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
    wrap = bridge_wrap_check(frame, bridge)
    spec = drive_for_document(doc)
    return {
        "wrap_fit": wrap,
        "contacts": contacts,
        "frame_bridge_intersection_mm3": overlap,
        "expected_bridge_sku": spec.bridge_sku,
        "actual_bridge_sku": doc.ServoDriveBridge.PrintSKU,
        "scope": "The continuous roof seats in Z and both U walls seat in Y. Two shared M3x20 pairs at X +/-15 load both cap walls, both frame legs and the rail. These are nominal fitted contact planes, not spring jaws or guaranteed as-printed fits. Coupon-finish and hand-seat the complete stack before tightening; reject warp rather than pulling it closed. Nominal geometry establishes no strength, automatic centering, preload or creep resistance.",
        "passed": overlap < TOL
        and wrap["passed"]
        and all(row["passed"] for row in contacts)
        and doc.ServoDriveBridge.PrintSKU == spec.bridge_sku,
    }


def bridge_wrap_check(frame, bridge):
    """Literal complete U walls and head/nut floors, independent of builders."""
    bores = union(
        [
            Part.makeCylinder(1.7, 24, App.Vector(x, -12, 6), App.Vector(0, 1, 0))
            for x in (-15, 15)
        ]
    )
    nut_radius = 5.9 / math.sqrt(3)
    nut_points = [
        App.Vector(
            -15 + nut_radius * math.cos(math.radians(a)),
            -11.1,
            6 + nut_radius * math.sin(math.radians(a)),
        )
        for a in range(30, 390, 60)
    ]
    nut_cut = Part.Face(Part.makePolygon(nut_points + [nut_points[0]])).extrude(
        App.Vector(0, 3.1, 0)
    )
    nut_cut = nut_cut.fuse(Part.makeBox(5.9, 3.1, 7, App.Vector(-17.95, -11.1, -1)))
    relief = Part.makeBox(18.4, 24, 10.4, App.Vector(-9.2, -12, 2.1))
    wall = Part.makeBox(46, 5, 12.8, App.Vector(-23, -11, 2.2)).cut(relief).cut(bores)
    wall = (
        wall.cut(Part.makeCylinder(3.2, 2, App.Vector(15, -11, 6), App.Vector(0, 1, 0)))
        .cut(Part.makeBox(6.4, 2, 7, App.Vector(11.8, -11, -1)))
        .cut(nut_cut)
    )
    rows = []
    for sign in (1, -1):

        def turn(shape):
            if sign < 0:
                shape.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
            return shape

        values = {
            "missing_continuous_wall_mm3": abs(turn(wall.copy()).cut(bridge).Volume)
        }
        for label, target, y, thickness in (
            ("head_floor", bridge, -9, 3),
            ("nut_floor", bridge, 6, 2),
            ("frame_head_leg", frame, -6, 4.75),
            ("frame_nut_leg", frame, 1.25, 4.75),
        ):
            land = Part.makeCylinder(
                3, thickness, App.Vector(15, y, 6), App.Vector(0, 1, 0)
            ).cut(bores)
            values["missing_" + label + "_mm3"] = abs(turn(land).cut(target).Volume)
        rows.append(
            {
                "side": sign,
                **values,
                "passed": all(value < TOL for value in values.values()),
            }
        )
    roof_missing = abs(
        Part.makeBox(46, 22, 2.5, App.Vector(-23, -11, 12.5)).cut(bridge).Volume
    )
    relief_obstruction = abs(bridge.common(relief).Volume)
    return {
        "sides": rows,
        "missing_roof_mm3": roof_missing,
        "crossbeam_relief_obstruction_mm3": relief_obstruction,
        "nominal_fitted_side_gap_mm": 0.0,
        "nominal_sidewall_mm": 5.0,
        "head_bearing_floor_mm": 3.0,
        "nut_bearing_floor_mm": 2.0,
        "clamp_axis_spacing_mm": 30.0,
        "passed": len(rows) == 2
        and all(row["passed"] for row in rows)
        and roof_missing < TOL
        and relief_obstruction < TOL,
    }


def _bridge_path(shape, waypoints, obstacles, spec):
    """Exact box-prism sweeps retain the U opening and avoid tangent face artifacts.

    Six deliberately plain stock boxes cover the actual bridge, including its
    cradle. The visible windows and transverse fastener bores are conservatively
    filled. Coverage and exact prescribed directions are independently required.
    """
    width = servo_bridge.bulkhead_width(spec)
    sections = (
        ((width, 5, spec.input_z_mm + 10.2 - 12.5), (-width / 2, -2.5, 12.5)),
        ((46, 22, 2.5), (-23, -11, 12.5)),
        ((13.8, 5, 10.3), (-23, -11, 2.2)),
        ((13.8, 5, 10.3), (9.2, -11, 2.2)),
        ((13.8, 5, 10.3), (-23, 6, 2.2)),
        ((13.8, 5, 10.3), (9.2, 6, 2.2)),
    )
    envelope = union(
        [Part.makeBox(*size, App.Vector(*origin)) for size, origin in sections]
    )
    missing = abs(shape.cut(envelope).Volume)
    expected = [(0, 0, 0), (0, 0, 11), (80, 0, 11)]
    if list(waypoints) != expected:
        return {
            "passed": False,
            "error": "Unreviewed U-bridge service path",
            "segments": [],
        }
    rows = []
    for start, end in zip(waypoints, waypoints[1:]):
        travel = [b - a for a, b in zip(start, end)]
        swept = union(
            [
                Part.makeBox(
                    *(size[i] + abs(travel[i]) for i in range(3)),
                    App.Vector(*(origin[i] + min(start[i], end[i]) for i in range(3))),
                )
                for size, origin in sections
            ]
        )
        hits = {
            name: intersection_volume(swept, other) for name, other in obstacles.items()
        }
        rows.append(
            {
                "start_mm": list(start),
                "end_mm": list(end),
                "method": "continuous exact union of six axis-aligned stock-box prisms",
                "intersection_mm3": hits,
                "passed": all(v < TOL for v in hits.values()),
            }
        )
    return {
        "obstacles": sorted(obstacles),
        "segments": rows,
        "envelope": "Six stock boxes with holes conservatively filled; actual bridge containment required.",
        "uncovered_bridge_volume_mm3": missing,
        "passed": missing < TOL and all(row["passed"] for row in rows),
    }


def servo_module_service_check(doc, module):
    """Bench removal after both shared rail pairs and the rail are removed."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"missing_parts": missing, "passed": False}
    # The saved assembly includes both rail pairs; source bench modules do not.
    # Require the complete installed inventory before removing those pairs
    # explicitly for this off-rail bench sequence.
    rail_pairs = {
        module["group"].Name + middle + suffix
        for middle in ("", "Opposite")
        for suffix in ("RailMountScrew", "RailMountNut")
    }
    present_rail_pairs = rail_pairs & shapes.keys()
    if present_rail_pairs and present_rail_pairs != rail_pairs:
        return {
            "passed": False,
            "error": "Incomplete shared rail clamps",
            "missing_parts": sorted(rail_pairs - shapes.keys()),
        }
    shapes = {name: shape for name, shape in shapes.items() if name not in rail_pairs}
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
    shaft_paths = []
    staged = retained_obstacles(shapes, removed)
    for name, offset, clamp in (
        ("PortOutputShaftNegative", (0, 12, 0), "PortOutputClampNegative"),
        ("StarboardOutputShaftPositive", (0, -12, 0), "StarboardOutputClampPositive"),
    ):
        path = continuous_path(
            staged[name], [(0, 0, 0), offset], retained_obstacles(staged, {name})
        )
        shaft_paths.append(
            {
                "part": name,
                "loosened_clamp": clamp,
                "staged_offset_mm": list(offset),
                **path,
            }
        )
        staged[name] = translated_shape(staged[name], *offset)
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
    fixed = retained_obstacles(staged, moving)
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
        "shaft_staging": shaft_paths,
        "loosened_carrier_clamps": [row["loosened_clamp"] for row in shaft_paths],
        "shared_rail_fasteners_removed_before_bench": sorted(present_rail_pairs),
        "prerequisites": "Remove both shared M3x20 rail screws and nuts, disconnect leads and support both modules. Slide the complete propulsion assembly +X10 mm, then lift it +Z30 mm from the rail before this local bench check. Rail attachment service is checked separately. Loosen only the two driven-stub carrier clamps for shaft staging; hold the rotors while their driven stubs are released.",
        "part_paths": rows,
        "retained_parts": sorted(fixed),
        "coordinate_frame": "propulsion module",
        "scope": "Neutral, unpowered bench service after removing both rail clamps. Release gear set screws and withdraw both small output gears inboard. Loosen the two driven-stub carrier clamps and retract Port negative stub 12 mm in +Y and Starboard positive stub 12 mm in -Y. These staged shafts remain visible and retained obstacles, with bearings and keepers unchanged. Support the rotors. Lift the paired servo module 11 mm and slide 80 mm in +X. Servos, horns, adapters, driver gears, input stubs and radial clamps stay assembled. Reverse for installation and restore shaft insertion and clamps before operation. Tools, flexible leads and real fit/clamp forces are not established by the rigid path.",
        "passed": moving == expected_moving
        and all(row["passed"] for row in gear_paths + shaft_paths + rows),
    }
