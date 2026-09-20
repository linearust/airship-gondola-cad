"""Small geometric helpers shared only by validation."""

import math
import struct
from collections import Counter

TOL = 1e-5


def belongs_to_group(obj, group):
    parent = obj.getParentGeoFeatureGroup()
    while parent is not None:
        if parent == group:
            return True
        parent = parent.getParentGeoFeatureGroup()
    return False


def local_shape(obj):
    import FreeCAD as App

    shape = obj.Shape.copy()
    shape.Placement = App.Placement()
    return shape


def intersection_volume(first, second):
    """Reject disjoint bounding boxes before the exact solid intersection."""
    if not first.BoundBox.intersect(second.BoundBox):
        return 0.0
    return abs(first.common(second).Volume)


def _stl_triangle(points):
    """Normalize coordinates to the precision actually serialized in STL."""
    return tuple(
        sorted(
            tuple(struct.unpack("<f", struct.pack("<f", float(c)))[0] for c in point)
            for point in points
        )
    )


def mesh_triangle_signature(mesh):
    """Compare triangles at STL precision, independent of vertex/facet order."""
    return sorted(_stl_triangle(facet.Points) for facet in mesh.Facets)


def _subtract(first, second):
    return tuple(a - b for a, b in zip(first, second))


def _dot(first, second):
    return sum(a * b for a, b in zip(first, second))


def _cross(first, second):
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _signed_area(polygon):
    return (
        sum(
            a[0] * b[1] - a[1] * b[0]
            for a, b in zip(polygon, polygon[1:] + polygon[:1])
        )
        / 2
    )


def _clip_polygon(polygon, signed_distance):
    """Keep a convex polygon's portion in the nonnegative half-space."""
    result = []
    if not polygon:
        return result
    previous = polygon[-1]
    previous_distance = signed_distance(previous)
    for point in polygon:
        distance = signed_distance(point)
        if (distance >= 0) != (previous_distance >= 0):
            fraction = previous_distance / (previous_distance - distance)
            result.append(
                tuple(a + fraction * (b - a) for a, b in zip(previous, point))
            )
        if distance >= 0:
            result.append(point)
        previous, previous_distance = point, distance
    return result


def _subtract_polygon(subject, cutter):
    """Return disjoint convex pieces outside cutter, without summing overlaps."""
    if _signed_area(cutter) < 0:
        cutter = list(reversed(cutter))
    outside, inside = [], subject
    for start, end in zip(cutter, cutter[1:] + cutter[:1]):
        dx, dy = _subtract(end, start)

        def distance(point):
            return dx * (point[1] - start[1]) - dy * (point[0] - start[0])

        fragment = _clip_polygon(inside, lambda point: -distance(point))
        if len(fragment) >= 3 and abs(_signed_area(fragment)) > 1e-14:
            outside.append(fragment)
        inside = _clip_polygon(inside, distance)
        if len(inside) < 3:
            break
    return outside


def compare_mesh_surfaces(actual, expected, plane_tolerance_mm=1e-5):
    """Prove bidirectional surface coverage despite planar retriangulation.

    STL coordinates use float32. Different diagonals on a saved planar face can
    give skinny facets different normals after serialization. Clip each target
    triangle to a narrow slab around the source triangle, then project it
    orthogonally: every covered point is within plane_tolerance_mm of the target
    surface. Polygon subtraction checks the covered union, so overlapping facets
    cannot compensate for holes. The reverse pass rejects extra surface as well.
    Solid topology is checked separately by the export validator.
    """
    if not math.isfinite(plane_tolerance_mm) or plane_tolerance_mm <= 0:
        raise ValueError("Mesh plane tolerance must be finite and positive.")
    first = Counter(_stl_triangle(facet.Points) for facet in actual.Facets)
    second = Counter(_stl_triangle(facet.Points) for facet in expected.Facets)
    first_only = list((first - second).elements())
    second_only = list((second - first).elements())

    def coverage_failures(source_triangles, target_triangles):
        failures = []
        targets = [
            (
                triangle,
                tuple(min(p[i] for p in triangle) for i in range(3)),
                tuple(max(p[i] for p in triangle) for i in range(3)),
            )
            for triangle in target_triangles
        ]
        for number, triangle in enumerate(source_triangles):
            origin = triangle[0]
            normal = _cross(
                _subtract(triangle[1], origin), _subtract(triangle[2], origin)
            )
            length = math.sqrt(_dot(normal, normal))
            if length < 1e-14:
                failures.append({"triangle": number, "error": "degenerate triangle"})
                continue
            normal = tuple(component / length for component in normal)
            axis_index = min(range(3), key=lambda i: abs(normal[i]))
            axis = tuple(float(i == axis_index) for i in range(3))
            horizontal = _cross(normal, axis)
            horizontal_length = math.sqrt(_dot(horizontal, horizontal))
            horizontal = tuple(value / horizontal_length for value in horizontal)
            vertical = _cross(normal, horizontal)

            def project(point):
                delta = _subtract(point, origin)
                return (_dot(delta, horizontal), _dot(delta, vertical))

            projected = [project(point) for point in triangle]
            area = abs(_signed_area(projected))
            remaining = [projected]
            low = tuple(min(p[i] for p in triangle) for i in range(3))
            high = tuple(max(p[i] for p in triangle) for i in range(3))
            for target, target_low, target_high in targets:
                if any(
                    target_high[i] < low[i] - plane_tolerance_mm
                    or target_low[i] > high[i] + plane_tolerance_mm
                    for i in range(3)
                ):
                    continue
                clipped = _clip_polygon(
                    list(target),
                    lambda point: (
                        plane_tolerance_mm - _dot(normal, _subtract(point, origin))
                    ),
                )
                clipped = _clip_polygon(
                    clipped,
                    lambda point: (
                        plane_tolerance_mm + _dot(normal, _subtract(point, origin))
                    ),
                )
                if len(clipped) < 3:
                    continue
                cutter = [project(point) for point in clipped]
                if abs(_signed_area(cutter)) < 1e-14:
                    continue
                remaining = [
                    fragment
                    for piece in remaining
                    for fragment in _subtract_polygon(piece, cutter)
                ]
                if not remaining:
                    break
            uncovered_area = sum(abs(_signed_area(piece)) for piece in remaining)
            # Floating-point clipping noise only, not a manufacturing allowance.
            if uncovered_area > max(1e-12, area * 1e-12):
                failures.append(
                    {
                        "triangle": number,
                        "surface_area_mm2": area,
                        "uncovered_area_mm2": uncovered_area,
                    }
                )
        return failures

    actual_failures = coverage_failures(first_only, second_only)
    expected_failures = coverage_failures(second_only, first_only)
    return {
        "method": "Bidirectional surface coverage by orthogonal slab projection and polygon union subtraction",
        "plane_tolerance_mm": plane_tolerance_mm,
        "coordinate_precision": "STL float32",
        "actual_retriangulated_facets": len(first_only),
        "expected_retriangulated_facets": len(second_only),
        "uncovered_actual_triangles": actual_failures,
        "uncovered_expected_triangles": expected_failures,
        "passed": bool(first)
        and bool(second)
        and not actual_failures
        and not expected_failures,
    }
