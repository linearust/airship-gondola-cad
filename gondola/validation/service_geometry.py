"""Shared rigid-part service paths and tool envelopes used only by validation."""

import FreeCAD as App
import Part

from gondola.cad import translated_shape, union

from .geometry import TOL, intersection_volume, translation_sweep


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


def contained_region_paths(shape, regions, waypoints, obstacles):
    """Sweep named stock regions only after accounting for the complete part.

    Callers define their own conservative stock. Keeping regions separate avoids
    filling empty corners with one bounding box; their union must contain every
    part feature so an omitted region cannot silently pass the path check.
    """
    regions = tuple(regions)
    uncovered = (
        abs(shape.cut(union([part for _, part in regions])).Volume)
        if regions
        else abs(shape.Volume)
    )
    rows = [
        {"region": label, **continuous_path(part, waypoints, obstacles)}
        for label, part in regions
    ]
    return {
        "regions": rows,
        "uncovered_volume_mm3": uncovered,
        "passed": bool(rows) and uncovered < TOL and all(row["passed"] for row in rows),
    }


def side_driver_shape(screw):
    """Straight negative-Y driver ending 0.1 mm before the saved screw head."""
    bounds = screw.BoundBox
    origin = App.Vector(bounds.Center.x, bounds.YMin - 0.1, bounds.Center.z)
    direction = App.Vector(0, -1, 0)
    return union(
        [
            Part.makeCylinder(2, 140, origin, direction),
            Part.makeCylinder(6, 40, origin + App.Vector(0, -140, 0), direction),
        ]
    )
