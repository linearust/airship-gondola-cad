"""Bound intentional horn contact to the actual sourced servo spline volume.

The servo's smooth spline envelope contains the OEM female spline teeth. That
nominal overlap is intentional; no part of the case or ears is exempted here.
These helpers do not establish tooth fit, engagement or continuous clearance.
"""

import math

import FreeCAD as App
import Part

from gondola.contracts.equipment_interfaces import PROPULSION_EVIDENCE

DATUM_TOLERANCE_MM = 1e-7
OVERLAP_TOLERANCE_MM3 = 1e-5


def _valid_solid(shape):
    return (
        not shape.isNull()
        and shape.isValid()
        and shape.isClosed()
        and len(shape.Solids) == 1
        and math.isfinite(shape.Volume)
        and shape.Volume > 0
    )


def _vector(value):
    vector = App.Vector(value)
    if not all(math.isfinite(component) for component in vector):
        raise ValueError("Nonfinite servo axis")
    return vector


def sourced_spline_volume(servo_shape, axis_origin, axis_direction):
    """Return the unique nominal spline cylinder and JSON-compatible evidence.

    Inputs share any rigid coordinate frame. Actual cylindrical face vertices
    define the axial interval; world-aligned bounding boxes do not. The source
    radius and length, complete circumference, declared axis and full solid
    occupancy must all agree. Invalid geometry returns ``(None, failed_report)``.
    Neither the supplied shape nor either axis argument is modified.
    """
    evidence = PROPULSION_EVIDENCE["X06"]
    radius = evidence["spline_major_diameter_mm"] / 2
    length = evidence["overall_height_with_spline_mm"] - evidence["case_size_mm"][2]
    report = {
        "passed": False,
        "radius_mm": radius,
        "length_mm": length,
        "candidate_face_count": 0,
    }
    try:
        if not _valid_solid(servo_shape):
            raise ValueError("Invalid servo solid")
        origin, axis = _vector(axis_origin), _vector(axis_direction)
        if axis.Length <= DATUM_TOLERANCE_MM:
            raise ValueError("Missing servo axis direction")
        axis.normalize()
        report.update(axis_origin_mm=list(origin), axis_direction=list(axis))
        candidates = []
        for face in servo_shape.Faces:
            surface = face.Surface
            if not isinstance(surface, Part.Cylinder):
                continue
            if (
                abs(surface.Radius - radius) > DATUM_TOLERANCE_MM
                or surface.Axis.cross(axis).Length > DATUM_TOLERANCE_MM
                or (surface.Center - origin).cross(axis).Length > DATUM_TOLERANCE_MM
                or not face.Vertexes
            ):
                continue
            projections = [
                (vertex.Point - origin).dot(axis) for vertex in face.Vertexes
            ]
            start, end = min(projections), max(projections)
            full_area = 2 * math.pi * radius * length
            if (
                abs(end - start - length) <= DATUM_TOLERANCE_MM
                and abs(face.Area - full_area) <= DATUM_TOLERANCE_MM * full_area
            ):
                candidates.append((start, end))
        report["candidate_face_count"] = len(candidates)
        if len(candidates) != 1:
            raise ValueError("Missing unique sourced servo spline face")
        start, end = candidates[0]
        start_point, end_point = origin + axis * start, origin + axis * end
        spline = Part.makeCylinder(radius, length, start_point, axis)
        missing = abs(spline.cut(servo_shape).Volume)
        report.update(
            axial_interval_mm=[start, end],
            start_mm=list(start_point),
            end_mm=list(end_point),
            volume_mm3=spline.Volume,
            missing_servo_material_mm3=missing,
        )
        if not math.isfinite(missing) or missing >= OVERLAP_TOLERANCE_MM3:
            raise ValueError("Sourced spline cylinder is not fully occupied by servo")
        report["passed"] = True
        return spline, report
    except (
        AttributeError,
        TypeError,
        ValueError,
        RuntimeError,
        Part.OCCError,
    ) as error:
        report["error"] = str(error)
        return None, report


def horn_spline_contact(horn_shape, servo_shape, axis_origin, axis_direction):
    """Accept nominal overlap only inside the sourced smooth spline envelope.

    A disjoint pair can pass this containment check. Callers must independently
    retain horn seating/coaxiality and complete case/ear clearance checks.
    Unknown overlap values on invalid input are ``None``, never an invented zero.
    """
    spline, evidence = sourced_spline_volume(servo_shape, axis_origin, axis_direction)
    report = {
        "passed": False,
        "neutral_intersection_mm3": None,
        "forbidden_overlap_mm3": None,
        "spline": evidence,
    }
    if spline is None:
        report["error"] = evidence["error"]
        return report
    try:
        if not _valid_solid(horn_shape):
            raise ValueError("Invalid horn solid")
        overlap = horn_shape.common(servo_shape)
        volume = abs(overlap.Volume)
        forbidden = abs(overlap.cut(spline).Volume) if not overlap.isNull() else 0.0
        report.update(
            neutral_intersection_mm3=volume,
            forbidden_overlap_mm3=forbidden,
            passed=math.isfinite(volume)
            and math.isfinite(forbidden)
            and forbidden < OVERLAP_TOLERANCE_MM3,
        )
        return report
    except (
        AttributeError,
        TypeError,
        ValueError,
        RuntimeError,
        Part.OCCError,
    ) as error:
        report["error"] = str(error)
        return report
