"""Small geometric helpers shared only by validation."""

import math
import struct
from collections import Counter

TOL = 1e-5


def belongs_to_group(obj, group):
    from gondola.cad import belongs_to_group as native_membership

    return native_membership(obj, group)


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


def translation_sweep(shape, displacement):
    """Return a continuous translational envelope and its construction method.

    Sweeping only forward-facing boundary faces together with the starting solid
    gives the exact volume for planar faces and cylinders parallel to the move.
    A periodic curved face extruded across its axis may fold onto itself, so it
    is deliberately not accepted by that construction. Other surfaces use the
    union bounding box of both endpoints: conservative, never an endpoint-only
    collision test. A collision with this fallback may need a better envelope.
    """
    import FreeCAD as App
    import Part

    coordinates = tuple(float(value) for value in displacement)
    if len(coordinates) != 3 or not all(math.isfinite(x) for x in coordinates):
        raise ValueError("Translation must contain three finite coordinates.")
    if shape.isNull() or not shape.isValid() or not shape.Solids:
        raise ValueError("Translation sweep requires valid solid geometry.")
    vector = App.Vector(*coordinates)
    if vector.Length == 0:
        return shape.copy(), "stationary solid"
    exact = True
    leading_faces = []
    for face in shape.Faces:
        surface = face.Surface
        name = type(surface).__name__
        if name == "Plane":
            if face.normalAt(0, 0).dot(vector) > 0:
                leading_faces.append(face)
            continue
        if (
            name == "Cylinder"
            and surface.Axis.cross(vector).Length <= 1e-12 * vector.Length
        ):
            continue
        exact = False
        break
    if not exact:
        bounds = shape.BoundBox
        minimum = [bounds.XMin, bounds.YMin, bounds.ZMin]
        size = [bounds.XLength, bounds.YLength, bounds.ZLength]
        return (
            Part.makeBox(
                *(size[i] + abs(coordinates[i]) for i in range(3)),
                App.Vector(*(minimum[i] + min(0, coordinates[i]) for i in range(3))),
            ),
            "continuous conservative bounding prism",
        )
    pieces = [shape.copy()]
    # Every new swept point is reached by following the move from an exit face
    # of the original solid. Its outward normal points along the move. This
    # remains true for concavities and cavity walls; normals of inner faces are
    # oriented toward the void. Back faces add only already covered volume, and
    # coaxial-cylinder sides and tangent planes sweep no three-dimensional set.
    # Skipping these before extrusion avoids degenerate prisms and duplicate
    # many-edged profiles in gear sweeps, without replacing a continuous sweep
    # with sampled positions or a convex hull.
    for face in leading_faces:
        prism = face.extrude(vector)
        if abs(prism.Volume) <= 1e-12:
            continue
        if not prism.isValid() or not prism.Solids:
            raise ValueError("Invalid face prism in continuous translation sweep.")
        pieces.append(prism)
    swept = (
        pieces[0].multiFuse(pieces[1:]).removeSplitter()
        if len(pieces) > 1
        else pieces[0]
    )
    if swept.isNull() or not swept.isValid() or not swept.Solids:
        raise ValueError("Invalid continuous translation sweep.")
    end = shape.copy()
    end.translate(vector)
    if abs(shape.cut(swept).Volume) > TOL or abs(end.cut(swept).Volume) > TOL:
        raise ValueError("Continuous sweep does not contain both endpoint solids.")
    return swept, "continuous planar/coaxial-cylinder face-prism union"


def certify_translation_clearance(
    shape, displacement, obstacles, *, max_depth=18, max_evaluations=4096
):
    """Certify a clear translation when a conservative sweep is too broad.

    Distance to a fixed solid is 1-Lipschitz under translation. At each interval
    midpoint, a distance greater than half the interval travel certifies every
    position in that interval, including its endpoints. Otherwise subdivide;
    touching, numerical ambiguity or a work limit fails closed. This constructs
    no replacement envelope and does not change ``translation_sweep`` fallback.
    """
    coordinates = tuple(float(value) for value in displacement)
    if len(coordinates) != 3 or not all(math.isfinite(x) for x in coordinates):
        raise ValueError("Translation must contain three finite coordinates.")
    if shape.isNull() or not shape.isValid() or not shape.Solids:
        raise ValueError("Clearance certification requires valid solid geometry.")
    if not isinstance(max_depth, int) or not 0 <= max_depth <= 24:
        raise ValueError("Certificate depth must be an integer from 0 to 24.")
    if not isinstance(max_evaluations, int) or max_evaluations < 1:
        raise ValueError("Certificate evaluation limit must be a positive integer.")
    for name, obstacle in obstacles.items():
        if obstacle.isNull() or not obstacle.isValid() or not obstacle.Solids:
            raise ValueError(f"Invalid certificate obstacle: {name}")

    import FreeCAD as App

    travel = math.sqrt(sum(value * value for value in coordinates))
    bounds = {name: obstacle.BoundBox for name, obstacle in obstacles.items()}
    report = {
        "method": "continuous adaptive translation-distance certificate",
        "obstacles": sorted(obstacles),
        "displacement_mm": list(coordinates),
        "evaluated_positions": 0,
        "certified_intervals": 0,
        "maximum_depth_used": 0,
        "passed": False,
    }
    # An obstacle certified for a parent interval is certified for both children.
    pending = [(0.0, 1.0, 0, tuple(obstacles))]
    while pending:
        start, end, depth, names = pending.pop()
        if report["evaluated_positions"] >= max_evaluations:
            report["unresolved"] = "Certificate evaluation limit reached."
            return report
        middle = (start + end) / 2
        half_travel = travel * (end - start) / 2
        placed = shape.copy()
        placed.translate(App.Vector(*(middle * value for value in coordinates)))
        placed_bounds = placed.BoundBox
        report["evaluated_positions"] += 1
        report["maximum_depth_used"] = max(report["maximum_depth_used"], depth)
        unresolved = []
        for name in names:
            other_bounds = bounds[name]
            box_distance = math.sqrt(
                sum(
                    max(
                        0.0,
                        getattr(placed_bounds, axis + "Min")
                        - getattr(other_bounds, axis + "Max"),
                        getattr(other_bounds, axis + "Min")
                        - getattr(placed_bounds, axis + "Max"),
                    )
                    ** 2
                    for axis in ("X", "Y", "Z")
                )
            )
            if box_distance > half_travel + TOL:
                continue
            obstacle = obstacles[name]
            volume = intersection_volume(placed, obstacle)
            if volume > TOL:
                report["collision"] = {
                    "obstacle": name,
                    "path_fraction": middle,
                    "intersection_mm3": volume,
                }
                return report
            distance = float(placed.distToShape(obstacle)[0])
            if not math.isfinite(distance) or distance < 0:
                report["unresolved"] = f"Invalid kernel distance for {name}."
                return report
            if distance <= half_travel + TOL:
                unresolved.append(name)
        if not unresolved:
            report["certified_intervals"] += 1
            continue
        if depth >= max_depth:
            report["unresolved"] = {
                "reason": "Touching, insufficient clearance or subdivision limit.",
                "interval": [start, end],
                "obstacles": unresolved,
            }
            return report
        pending.extend(
            (
                (middle, end, depth + 1, tuple(unresolved)),
                (start, middle, depth + 1, tuple(unresolved)),
            )
        )
    report["passed"] = True
    return report


def _stl_triangle(points):
    """Normalize coordinates to the precision actually serialized in STL."""
    return tuple(
        sorted(
            tuple(struct.unpack("<f", struct.pack("<f", float(c)))[0] for c in point)
            for point in points
        )
    )


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
