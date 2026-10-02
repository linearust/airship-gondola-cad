"""Saved-solid checks for seated metric bolt/nut pairs and thread engagement.

Rigid contact does not establish tightening preload or printed-joint strength.
"""

import Part

from .geometry import TOL, intersection_volume, planar_contact_area


def clamp_fastener_check(clamp, bolt, nut, *, thread_diameter=2.0, nut_height=1.6):
    """Require seated bolt/nut bearing faces and a complete nominal metric nut core.

    This checks assembly geometry only. A tightened split clamp's shaft torque
    capacity, creep and axial grip are not established by a rigid CAD model.
    """
    contacts = []
    for name, fastener in (("Bolt", bolt), ("Nut", nut)):
        area = planar_contact_area(fastener, clamp)
        contacts.append(
            {"part": name, "bearing_contact_area_mm2": area, "passed": area > TOL}
        )
    bore_surfaces = [
        face.Surface
        for face in nut.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - thread_diameter / 2) < TOL
    ]
    if not bore_surfaces:
        return {
            "contacts": contacts,
            "passed": False,
            "error": "Missing metric nut bore",
        }
    bore = bore_surfaces[0]
    axis = bore.Axis
    projections = [vertex.Point.dot(axis) for vertex in nut.Vertexes]
    low, high = min(projections), max(projections)
    origin = bore.Center + axis * (low - bore.Center.dot(axis))
    core = Part.makeCylinder(thread_diameter * 0.4, high - low, origin, axis)
    missing_core = abs(core.cut(bolt).Volume)
    clamp_overlap = intersection_volume(clamp, bolt) + intersection_volume(clamp, nut)
    return {
        "contacts": contacts,
        "nut_engagement_length_mm": high - low,
        "missing_bolt_thread_core_mm3": missing_core,
        "fastener_clamp_overlap_mm3": clamp_overlap,
        "scope": "Nominal seated metric fasteners with full nut core; no helical-thread, preload, shaft-friction or printed-clamp strength qualification.",
        "passed": all(row["passed"] for row in contacts)
        and missing_core < TOL
        and high - low >= nut_height - TOL
        and clamp_overlap < TOL,
    }
