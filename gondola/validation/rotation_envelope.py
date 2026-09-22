"""Conservative solid envelope for a complete rotation about a fixed Y axis."""

import math


def full_orbit_envelope(shape, axis_origin):
    """Return an enclosing cylinder and its geometric evidence, without policy.

    ``shape`` and ``axis_origin`` must share one coordinate frame. The rotation
    axis is parallel to that frame's Y axis. Rotation preserves Y and distance
    from the axis. The farthest XZ corner of the source bounding box therefore
    bounds every source point at every angle, including between sampled poses.

    A positive distance from this envelope to an obstacle is a lower bound on
    the body's clearance. Envelope overlap is inconclusive: it may fill empty
    space, including shaft bores. No contact, tolerance or axial play is waived.
    """
    import FreeCAD as App
    import Part

    try:
        origin = tuple(float(value) for value in axis_origin)
    except (TypeError, ValueError) as exc:
        raise ValueError("Rotation axis needs three finite coordinates.") from exc
    if len(origin) != 3 or not all(math.isfinite(value) for value in origin):
        raise ValueError("Rotation axis needs three finite coordinates.")
    if shape.isNull() or not shape.isValid() or not shape.Solids:
        raise ValueError("Rotation envelope requires valid solid geometry.")

    bounds = shape.BoundBox
    limits = (
        (bounds.XMin, bounds.XMax),
        (bounds.YMin, bounds.YMax),
        (bounds.ZMin, bounds.ZMax),
    )
    radius = math.hypot(
        max(abs(value - origin[0]) for value in limits[0]),
        max(abs(value - origin[2]) for value in limits[2]),
    )
    height = bounds.YLength
    if (
        not all(math.isfinite(value) for pair in limits for value in pair)
        or not math.isfinite(radius)
        or radius <= 0
        or height <= 0
    ):
        raise ValueError("Rotation envelope needs finite positive dimensions.")
    envelope = Part.makeCylinder(
        radius,
        height,
        App.Vector(origin[0], bounds.YMin, origin[2]),
        App.Vector(0, 1, 0),
    )
    if envelope.isNull() or not envelope.isValid() or not envelope.Solids:
        raise ValueError("Invalid full rotation envelope.")
    return envelope, {
        "method": "continuous conservative full rotation cylinder about Y",
        "axis_origin_mm": list(origin),
        "axis_direction": [0, 1, 0],
        "radius_mm": radius,
        "axial_bounds_mm": list(limits[1]),
        "source_bounds_mm": [list(pair) for pair in limits],
        "scope": "All rotation angles; source bounding box bounds the radius and invariant axial interval. Contains empty space, so envelope overlap does not establish a collision. Excludes manufacturing tolerance, deformation and additional translation.",
    }
