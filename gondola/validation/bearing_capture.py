"""Saved-geometry proof of spacerless, outer-ring-only bearing capture."""

import math

import FreeCAD as App
import Part

from gondola.cad import translated_shape
from gondola.parts import bearing_retention
from gondola.print_export import geometry_comparison

from .geometry import intersection_volume

TOL = 1e-5


def release_motion_check(position_shape, obstacles):
    """Check both moving arms against every retained physical obstacle.

    The caller removes only these arms' resting material from the fixed-frame
    obstacle. The retained bearing remains an obstacle during release. Nine
    prescribed shear poses supplement the axial path check; they do not prove
    continuous elastic motion or physical deflection capability.
    """
    poses = []
    for index in range(9):
        release = bearing_retention.RELEASE_MM * index / 8
        hooks = Part.makeCompound(
            [
                bearing_retention.hook_shape(-1, release),
                bearing_retention.hook_shape(1, release),
            ]
        )
        hooks = position_shape(hooks)
        collisions = {
            name: volume
            for name, shape in obstacles.items()
            if (volume := intersection_volume(hooks, shape)) > TOL
        }
        poses.append(
            {
                "outward_displacement_at_axis_mm": release,
                "collisions_mm3": collisions,
                "passed": not collisions,
            }
        )
    return {
        "checked_objects": sorted(obstacles),
        "poses": poses,
        "scope": "Nine sampled, prescribed shear poses of both release arms, including rest and fully open. Every retained physical object is checked, including the bearing being released and the fixed frame with only these arms' resting material removed. Not a continuous-motion, elasticity, tool-force or strength qualification.",
        "passed": bool(obstacles) and all(row["passed"] for row in poses),
    }


def _annulus(inner, outer, start_y, length, x=0, z=0):
    axis = App.Vector(0, 1, 0)
    origin = App.Vector(x, start_y, z)
    return Part.makeCylinder(outer, length, origin, axis).cut(
        Part.makeCylinder(inner, length, origin, axis)
    )


def _normalise_seat(seat, origin, contacts):
    """Recover the fixed cup's roll from actual opposed hook contact patches.

    A pod's frame rotates in inverse pod coordinates during tilt. Bearing and
    shaft cylinders cannot identify that roll; the two contact patches can,
    up to 180 degrees. Complete actual arm material resolves that ambiguity.
    """
    centre = contacts[0].CenterOfMass
    angle = math.degrees(math.atan2(centre.z - origin.z, centre.x - origin.x))
    expected_arms = Part.makeCompound(
        [bearing_retention.hook_shape(-1), bearing_retention.hook_shape(1)]
    )
    candidates = []
    for rotation in (angle, angle + 180):
        candidate = translated_shape(seat, -origin.x, -origin.y, -origin.z)
        candidate.rotate(App.Vector(), App.Vector(0, 1, 0), rotation)
        candidates.append((expected_arms.cut(candidate).Volume, candidate))
    return min(candidates, key=lambda item: item[0])[1]


def bearing_stack_check(bearing, shaft, seat, carrier, *, opposite_travel):
    """Check actual solids with this bearing's outboard direction along +Y.

    Neither the carrier nor a spacer retains the bearing. The independently
    verified carrier/frame stops bound carrier motion; the bearing itself is
    captured by two inboard outer-ring hooks and one outboard shoulder.
    """
    if any(
        shape.isNull() or not shape.isValid()
        for shape in (bearing, shaft, seat, carrier)
    ):
        return {"passed": False, "error": "Missing or invalid bearing-stack solid"}
    if (
        opposite_travel is None
        or not math.isfinite(opposite_travel)
        or opposite_travel < 0
    ):
        return {"passed": False, "error": "Unproven carrier axial stop"}
    bounds = bearing.optimalBoundingBox(False, False)
    x, z = bounds.Center.x, bounds.Center.z
    origin = App.Vector(x, bounds.YMin, z)
    expected = _annulus(1.5, 3.0, bounds.YMin, 2.5, x, z)
    comparison = geometry_comparison(bearing, expected)
    shaft_bounds = shaft.optimalBoundingBox(False, False)
    axis_error = math.hypot(shaft_bounds.Center.x - x, shaft_bounds.Center.z - z)
    inward = -bearing_retention.HOOK_STOP_Y
    bearing_interval = [bounds.YMin - inward, bounds.YMax]
    shaft_coverage = min(bounds.YMax, shaft_bounds.YMax - opposite_travel) - max(
        bounds.YMin - inward, shaft_bounds.YMin + opposite_travel
    )
    shaft_journal = any(
        type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - 1.5) < TOL
        and abs(abs(face.Surface.Axis.y) - 1) < TOL
        and math.hypot(face.Surface.Center.x - x, face.Surface.Center.z - z) < TOL
        and face.BoundBox.YMin <= bounds.YMin - inward - opposite_travel + TOL
        and face.BoundBox.YMax >= bounds.YMax + opposite_travel - TOL
        for face in shaft.Faces
    )

    # Only the outer-ring design land is used: do not count shield contact as
    # a valid axial stop. Each independent hook must contribute a broad patch.
    stop_slice = _annulus(2.81, 2.99, bounds.YMin - inward - 0.01, 0.01, x, z)
    contacts = list(seat.common(stop_slice).Solids)
    contact_areas = [solid.Volume / 0.01 for solid in contacts]
    if len(contacts) != 2:
        return {
            "passed": False,
            "error": "Expected two separate inboard outer-ring hook contacts",
            "hook_contact_patch_areas_mm2": contact_areas,
        }
    centres = [solid.CenterOfMass for solid in contacts]
    opposed_error = math.hypot(
        centres[0].x + centres[1].x - 2 * x,
        centres[0].z + centres[1].z - 2 * z,
    )
    normalised = _normalise_seat(seat, origin, contacts)
    capture = bearing_retention.geometry_check(normalised)

    # The front pockets intentionally remove two side sectors. The top and
    # bottom fixed arcs, measured in the saved cup, support the full width.
    # A generous 0.3 mm radial witness checks actual surrounding PA12 material.
    full_width_wall = _annulus(3.01, 3.3, -inward, 2.5 + inward)
    upper = Part.makeBox(8, 2.5 + inward, 2, App.Vector(-4, -inward, 2.11))
    lower = Part.makeBox(8, 2.5 + inward, 2, App.Vector(-4, -inward, -4.11))
    arc_witness = full_width_wall.common(upper.fuse(lower))
    missing_arcs = abs(arc_witness.cut(normalised).Volume)
    outer_shoulder = _annulus(2.81, 2.99, 2.51, 1.48)
    missing_shoulder = abs(outer_shoulder.cut(normalised).Volume)

    travel = _annulus(1.5, 3.0, bounds.YMin - inward, 2.5 + inward, x, z)
    overlaps = {
        "bearing_seat_overlap_mm3": intersection_volume(bearing, seat),
        "bearing_shaft_overlap_mm3": intersection_volume(bearing, shaft),
        "bearing_travel_seat_overlap_mm3": intersection_volume(travel, seat),
    }
    # Existing symmetric carrier stops are independently verified by the caller.
    # Use their full travel as a conservative approach bound, not as retention.
    carrier_end = carrier.optimalBoundingBox(False, False).YMax
    carrier_gap = bounds.YMin - inward - carrier_end - opposite_travel
    return {
        "stock_shape_comparison": comparison,
        "shaft_axis_error_mm": axis_error,
        "nominal_3mm_journal_covers_bearing_and_carrier_motion": shaft_journal,
        "minimum_shaft_coverage_over_bearing_motion_mm": shaft_coverage,
        "bearing_motion_interval_y_mm": bearing_interval,
        "maximum_bearing_inward_travel_mm": inward,
        "maximum_bearing_outward_travel_mm": 0.0,
        "opposite_carrier_travel_mm": opposite_travel,
        "minimum_carrier_to_bearing_face_gap_mm": carrier_gap,
        "hook_contact_patch_areas_mm2": contact_areas,
        "opposed_hook_contact_centre_error_mm": opposed_error,
        "missing_full_width_fixed_guide_arcs_mm3": missing_arcs,
        "missing_complete_outer_shoulder_mm3": missing_shoulder,
        "capture_geometry": capture,
        **overlaps,
        "scope": "Saved nominal solids. Two integral hooks and the outer shoulder contact only the outer-ring design land; the carrier is separately bounded and does not retain the bearing. Complete 360-degree guide length is2.1mm, overlapping1.9mm at the inward limit, with top/bottom fixed arcs supporting the complete bearing width. Ø5.4 is a shield-clearance design envelope, not a measured generic-bearing shield. Process-matched coupon fit, ring-land compatibility, release/recovery, forces, creep and fatigue remain physically unqualified.",
        "passed": comparison["difference_mm3"] < TOL
        and axis_error < TOL
        and shaft_journal
        and shaft_coverage >= 2.5 + inward - TOL
        and min(contact_areas) > 0.4
        and opposed_error < TOL
        and capture["passed"]
        and missing_arcs < TOL
        and missing_shoulder < TOL
        and carrier_gap >= 1.8 - TOL
        and all(value < TOL for value in overlaps.values()),
    }
