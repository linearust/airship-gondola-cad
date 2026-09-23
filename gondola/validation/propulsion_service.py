"""Shared propulsion service geometry, independent of report coordination.

Inventory every physical module obstacle and certify ordered rigid-part paths
without changing the scope of the calling assembly or removal check.
"""

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, translated_shape, world_shape
from gondola.contracts.drive import FACE_WIDTH_MM, MODULE_MM
from gondola.parts import propulsion

from .geometry import TOL, intersection_volume, translation_sweep


def module_service_shapes(doc, module):
    """Require every retained physical obstacle, in the local propulsion frame."""
    group = module["group"]
    expected = {
        obj.Name
        for obj in doc.Objects
        if belongs_to_group(obj, group)
        and obj.isDerivedFrom("Part::Feature")
        and obj.Shape.Solids
        and getattr(obj, "Role", "") != "Clearance"
    }
    objects = module["printed"] + module["hardware"] + module["references"]
    shapes = {obj.Name: world_shape(obj) for obj in objects if obj.Name in expected}
    inverse = group.getGlobalPlacement().inverse()
    for shape in shapes.values():
        shape.Placement = inverse.multiply(shape.Placement)
    return shapes, sorted(expected - shapes.keys())


def retained_obstacles(physical, excluded, *, members=None):
    """Retain installed obstacles within the declared whole-module or bench scope."""
    return {
        name: shape
        for name, shape in physical.items()
        if name not in excluded and (members is None or name in members)
    }


def continuous_path(shape, waypoints, obstacles):
    """Check every point of a piecewise translation, not just its waypoints."""
    rows = []
    for start, end in zip(waypoints, waypoints[1:]):
        placed = translated_shape(shape, *start)
        swept, method = translation_sweep(
            placed, tuple(b - a for a, b in zip(start, end))
        )
        collisions = {
            name: intersection_volume(swept, obstacle)
            for name, obstacle in obstacles.items()
        }
        rows.append(
            {
                "start_mm": list(start),
                "end_mm": list(end),
                "method": method,
                "intersection_mm3": collisions,
                "passed": all(v < TOL for v in collisions.values()),
            }
        )
    return {
        "obstacles": sorted(obstacles),
        "segments": rows,
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }


def driver_lateral_service_check(shape, start, end, obstacles, spec, sign):
    """Bound the toothed disk and smaller hub separately during lateral release.

    A single bounding box fills the empty corners around the large gear and
    falsely hits the retained small gear. These exact swept cylinders enclose
    the complete bought gear; containment of the actual CAD is checked first.
    """
    axis = App.Vector(0, sign, 0)
    x, z = sign * spec.input_x_mm, spec.input_z_mm
    reference, swept = [], []
    for y, height, radius in (
        (propulsion.GEAR_HUB_START_Y, 5, spec.driver.hub_diameter_mm / 2),
        (
            propulsion.GEAR_FACE_START_Y,
            FACE_WIDTH_MM,
            MODULE_MM * (spec.driver.teeth + 2) / 2,
        ),
    ):
        origin = App.Vector(x, sign * y, z)
        cylinder = Part.makeCylinder(radius, height, origin, axis)
        reference.append(cylinder)
        first = translated_shape(cylinder, *start)
        last = translated_shape(cylinder, *end)
        bridge = Part.makeBox(
            abs(end[0] - start[0]),
            height,
            2 * radius,
            App.Vector(
                x + min(start[0], end[0]),
                min(sign * y, sign * (y + height)) + start[1],
                z - radius + start[2],
            ),
        )
        swept.append(first.fuse(last).fuse(bridge))
    envelope = reference[0].fuse(reference[1])
    outside = abs(shape.cut(envelope).Volume)
    sweep = swept[0].fuse(swept[1])
    hits = {
        name: intersection_volume(sweep, other) for name, other in obstacles.items()
    }
    axial_invariance = start[1:] == end[1:] and abs(end[0] - start[0]) > TOL
    return {
        "obstacles": sorted(obstacles),
        "segments": [
            {
                "start_mm": list(start),
                "end_mm": list(end),
                "method": "continuous tooth-disk and hub swept-cylinder union",
                "intersection_mm3": hits,
                "passed": all(value < TOL for value in hits.values()),
            }
        ],
        "gear_outside_reference_envelope_mm3": outside,
        "passed": axial_invariance
        and outside < TOL
        and all(value < TOL for value in hits.values()),
    }


def fastener_service_check(
    bolt, nut, obstacles, *, thread_diameter=2.0, nut_lateral_direction=None
):
    """Check an ordered threaded-fastener release and its head-tool approach."""
    bore = next(
        face.Surface
        for face in nut.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - thread_diameter / 2) < TOL
    )
    axis = bore.Axis
    if (
        nut.optimalBoundingBox(False, False).Center
        - bolt.optimalBoundingBox(False, False).Center
    ).dot(axis) < 0:
        axis = -axis
    thread_points = [
        vertex.Point.dot(axis)
        for face in bolt.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - thread_diameter / 2) < TOL
        for vertex in face.Vertexes
    ]
    thread_start, thread_end = min(thread_points), max(thread_points)
    nut_start = min(vertex.Point.dot(axis) for vertex in nut.Vertexes)
    nut_travel = thread_end - nut_start + 0.2
    bolt_travel = thread_end - thread_start + 0.2
    if nut_lateral_direction is None:
        nut_waypoints = [(0, 0, 0), tuple(axis * nut_travel)]
        sequence = "Disengage the nut beyond the thread tip, then withdraw the bolt."
    else:
        offset = axis * 0.2
        lateral = App.Vector(*nut_lateral_direction) * 25
        nut_waypoints = [(0, 0, 0), tuple(offset), tuple(offset + lateral)]
        sequence = "Hold the nut and withdraw the bolt first, then move the unthreaded nut 0.2 mm away from its seat and 25 mm sideways."
    nut_path = continuous_path(nut, nut_waypoints, obstacles)
    bolt_path = continuous_path(
        bolt, [(0, 0, 0), tuple(axis * -bolt_travel)], obstacles
    )
    head_projection = min(vertex.Point.dot(axis) for vertex in bolt.Vertexes)
    tool_origin = bore.Center + axis * (head_projection - 0.1 - bore.Center.dot(axis))
    tool_radius = 1.0 if thread_diameter == 2 else 1.6
    tool = Part.makeCylinder(tool_radius, 15, tool_origin, -axis)
    tool_hits = {
        name: volume
        for name, shape in obstacles.items()
        if (volume := intersection_volume(tool, shape)) > TOL
    }
    return {
        "nut_axial_removal": nut_path,
        "bolt_axial_withdrawal": bolt_path,
        "driver_approach_collisions": tool_hits,
        "tool_reserve_radius_mm": tool_radius,
        "nut_thread_disengagement_travel_mm": nut_travel,
        "bolt_withdrawal_travel_mm": bolt_travel,
        "service_order": sequence,
        "scope": "Modeled full thread/shank withdrawal includes 0.2 mm clearance. Named obstacles stay installed at neutral tilt. Cylindrical driver reservation: 1 mm radius for M2 hex socket, 1.6 mm for the M1.6 Phillips kit head. This is a tool-space envelope, not a measured bit or proof of recess engagement. Handling the released nut, bit match and wrench handling remain unverified.",
        "passed": nut_path["passed"] and bolt_path["passed"] and not tool_hits,
    }
