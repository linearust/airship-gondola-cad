"""Seated M2 head acceptance on carrier slots; no freely floating clamp claim."""

import FreeCAD as App
import Part

MINIMUM_FLAT_HEAD_DIAMETER = 3.5
MAXIMUM_CENTRING_ERROR = 0.1
MINIMUM_TRANSVERSE_LAND = 0.2
TOL = 1e-5


def contract(maximum_slot_width, minimum_screw_diameter):
    concentric = (MINIMUM_FLAT_HEAD_DIAMETER - maximum_slot_width) / 2
    free_offset = (maximum_slot_width - minimum_screw_diameter) / 2
    return {
        "minimum_received_flat_head_bearing_diameter_mm": MINIMUM_FLAT_HEAD_DIAMETER,
        "maximum_accepted_slot_width_mm": maximum_slot_width,
        "maximum_head_axis_offset_from_slot_centreline_mm": MAXIMUM_CENTRING_ERROR,
        "concentric_head_land_across_maximum_slot_width_mm": concentric,
        "minimum_transverse_land_at_accepted_centring_mm": concentric
        - MAXIMUM_CENTRING_ERROR,
        "required_minimum_transverse_land_mm": MINIMUM_TRANSVERSE_LAND,
        "full_free_screw_offset_mm": free_offset,
        "minimum_transverse_land_at_full_free_offset_mm": concentric - free_offset,
        "full_free_screw_offset_support_qualified": False,
        "bearing_scope": "Accept a measured flat head face at least 3.5 mm across and a finished slot no wider than 2.9 mm. Centre the screw axis within 0.1 mm of the slot centreline, fully tighten the seated clamp, then verify both transverse bearing lands remain at least 0.2 mm at the head diameter. Recheck after tightening; head outside diameter alone does not establish its flat face. This is assembly positioning, not a floating operating joint. The full shank clearance is not an accepted bearing position. Reject shifted or tilted seating; clamp pressure, retention and PA12 creep remain unqualified.",
    }


def check(shape, centre, bottom, *, maximum_slot_width, minimum_screw_diameter):
    """Check complete worst-case circular side caps on the saved underside.

    The infinite-width slot strip removes round-end support conservatively.
    Both limiting head offsets enclose the side cap that must remain supported
    throughout the accepted centring interval. A thin material prism checks the
    bearing surface, without assigning a physical head or a tightening torque.
    """
    fit = contract(maximum_slot_width, minimum_screw_diameter)
    radius = MINIMUM_FLAT_HEAD_DIAMETER / 2
    half_slot = maximum_slot_width / 2
    depth = 0.2
    x, y = centre
    rows = []
    for offset in (-MAXIMUM_CENTRING_ERROR, MAXIMUM_CENTRING_ERROR):
        head = Part.makeCylinder(radius, depth, App.Vector(x + offset, y, bottom))
        for side in (-1, 1):
            start = x + half_slot if side == 1 else x - half_slot - 2 * radius
            region = Part.makeBox(
                2 * radius,
                2 * radius,
                depth,
                App.Vector(start, y - radius, bottom),
            )
            footprint = head.common(region)
            missing = abs(footprint.cut(shape).Volume)
            rows.append(
                {
                    "head_offset_mm": offset,
                    "side": side,
                    "bearing_cap_area_mm2": footprint.Volume / depth,
                    "missing_support_mm3": missing,
                    "passed": footprint.Volume > TOL and missing < TOL,
                }
            )
    return {
        "acceptance": fit,
        "bearing_caps": rows,
        "passed": fit["minimum_transverse_land_at_accepted_centring_mm"]
        >= MINIMUM_TRANSVERSE_LAND - TOL
        and all(row["passed"] for row in rows),
        "scope": "Saved carrier material supports both complete circular side caps at the accepted centring limits. Actual flat head dimensions, final screw centring and loaded retention still require inspection.",
    }
