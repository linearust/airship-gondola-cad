"""Independent local rail geometry and angular-clearance screens.

Dimensions here are literal acceptance witnesses, independent of rail builders.
The angular screen moves one rigid wall and its local base about a bolt axis;
it is neither a continuous-beam model nor evidence of tape or PA12 strength.
"""

import math

import FreeCAD as App
import Part

V = App.Vector
TOL = 1e-5


def _box(length, width, height, x, y, z):
    return Part.makeBox(length, width, height, V(x, y, z))


def root_stock_check(shape, centres=tuple(range(-140, 141, 28))):
    """Check the round end and side roots away from their corner intersections."""
    rows = []
    for centre in centres:
        probes = []
        for sign in (-1, 1):
            # End-root cross sections are one millimetre square minus R1.
            low_x = centre + (9 if sign > 0 else -10)
            region = _box(1, 1, 1, low_x, -0.5, 1.5)
            cutter = Part.makeCylinder(
                1, 1.2, V(centre + sign * 10, -0.6, 2.5), V(0, 1, 0)
            )
            expected = region.cut(cutter)
            probes.append(("x_end", sign, region, expected))
            # The middle of each long side independently witnesses the R0.5.
            low_y = 1.25 if sign > 0 else -1.75
            region = _box(14, 0.5, 0.5, centre - 7, low_y, 1.5)
            cutter = Part.makeCylinder(
                0.5, 14.2, V(centre - 7.1, sign * 1.75, 2), V(1, 0, 0)
            )
            probes.append(("long_side", sign, region, region.cut(cutter)))
        for kind, sign, region, expected in probes:
            actual = shape.common(region)
            missing = abs(expected.cut(actual).Volume)
            excess = abs(actual.cut(expected).Volume)
            rows.append(
                {
                    "wall_centre_x_mm": centre,
                    "root": kind,
                    "side": sign,
                    "missing_stock_mm3": missing,
                    "excess_stock_mm3": excess,
                    "passed": max(missing, excess) < TOL,
                }
            )
    return {
        "x_end_radius_mm": 1.0,
        "long_side_radius_mm": 0.5,
        "minimum_base_thickness_mm": 1.5,
        "root_footprint_length_mm": 20.0,
        "clear_between_root_footprints_mm": 8.0,
        "root_witnesses": rows,
        "scope": "Literal circular root profiles away from their joined corners; base stock is checked separately. No stress, peel or fatigue capacity is inferred.",
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }


def _wall_top_seat_check(section, mount, zone_length=10):
    """Ordinary carrier: flat wall-top datum and lower legs clear of the base."""
    if abs(zone_length - 10) > TOL:
        raise ValueError("Ordinary carrier cheeks must retain their 10 mm zone")
    line = Part.makeLine(V(-40, 0, 9.49), V(40, 0, 9.49))
    intervals = [
        (edge.BoundBox.XMin, edge.BoundBox.XMax)
        for edge in section.common(line).Edges
        if abs(edge.BoundBox.XLength - 18) < TOL
    ]
    choices = [
        (max(-8, first), min(8, last))
        for first, last in intervals
        if min(8, last) > max(-8, first)
    ]
    first, last = max(choices, key=lambda row: row[1] - row[0]) if choices else (0, 0)
    overlap = last - first
    top = {"overlap_length_mm": overlap, "nominal_area_mm2": 2.5 * overlap}
    if overlap > 0:
        roof = _box(overlap, 2.5, 0.01, first, -1.25, 9.5)
        wall = _box(overlap, 2.5, 0.01, first, -1.25, 9.49)
        top["missing_roof_stock_mm3"] = abs(roof.cut(mount).Volume)
        top["missing_wall_stock_mm3"] = abs(wall.cut(section).Volume)
        top["passed"] = (
            overlap >= 14 - TOL
            and max(top["missing_roof_stock_mm3"], top["missing_wall_stock_mm3"]) < TOL
        )
    else:
        top["passed"] = False
    side_rows = []
    for sign in (-1, 1):
        y = -1.26 if sign < 0 else 1.25
        face = _box(10, 0.01, 7, -5, y, 2.5).cut(_box(12, 3, 3.4, -6, -1.5, 4.3))
        inside = face.copy()
        inside.translate(V(0, -sign * 0.01, 0))
        missing = abs(face.cut(mount).Volume) + abs(inside.cut(section).Volume)
        side_rows.append(
            {"side": sign, "missing_contact_mm3": missing, "passed": missing < TOL}
        )
    lower = _box(16, 12, 2.5, -8, -6, 0)
    blocked = abs(lower.common(mount).Volume)
    return {
        "seat_type": "wall_top_bearing",
        "top_bearing": top,
        "bottom_datum_contacts": [],
        "lower_leg_bottom_z_mm": 2.5,
        "nominal_base_clearance_mm": 1.0,
        "blocked_lower_clearance_mm3": blocked,
        "local_side_contacts": side_rows,
        "missing_flat_side_contact_mm3": side_rows[0]["missing_contact_mm3"],
        "missing_opposite_side_contact_mm3": side_rows[1]["missing_contact_mm3"],
        "scope": "Each16mm roof seats on14..16mm of one wall top atZ9.5, with10mm fitted cheeks and lower edges atZ2.5. Carrier attitude follows the local wall; the2.5mm-wide top seat and1.8mm upper slot ligament are not strength or roll-stiffness qualifications.",
        "passed": top["passed"]
        and blocked < TOL
        and all(row["passed"] for row in side_rows),
    }


def local_seat_check(section, mount, zone_length=10, *, shared=False):
    """Every station uses the same wall-top shoe; pairing is checked separately."""
    return _wall_top_seat_check(section, mount, zone_length)


def local_wall_coupon(section):
    """Take a saved wall and the full 6 mm base width, centred on that wall."""
    if abs(section.BoundBox.ZMin) > TOL or abs(section.BoundBox.ZMax - 9.5) > TOL:
        raise ValueError(
            "The local rail must retain its Z0 underside and Z9.5 wall top"
        )
    line = Part.makeLine(V(-20, 0, 8.5), V(20, 0, 8.5))
    intervals = [
        (edge.BoundBox.XMin, edge.BoundBox.XMax)
        for edge in section.common(line).Edges
        if abs(edge.BoundBox.XLength - 18) < TOL
    ]
    if not intervals:
        raise ValueError("No complete 18 mm local wall is present")
    first, last = min(intervals, key=lambda row: abs(sum(row)))
    centre = (first + last) / 2
    coupon = section.common(_box(28, 6, 9.5, centre - 14, -3, 0))
    coupon.translate(V(-centre, 0, 0))
    return coupon


def angular_clearance_check(
    section, mount, *, slot_positions=(-3, 0, 3), follow_wall=False
):
    """Sample an explicit local angular range; report its finite sampling scope."""
    try:
        coupon = local_wall_coupon(section)
    except ValueError as error:
        return {"passed": False, "error": str(error)}
    # The 28 mm coupon, ±3 mm trim and ±2° rotation stay inside this fixed
    # prism. Discarding more distant mount geometry changes no intersections.
    obstacle = mount.common(_box(36, 6, 12, -18, -3, -1))
    rows = []
    angles = tuple(index / 4 for index in range(-8, 9))
    for offset in slot_positions:
        if not math.isfinite(offset) or abs(offset) > 3:
            raise ValueError("Angular screen offsets must lie within design trim ±3 mm")
        for angle in angles:
            placed = coupon.copy()
            placed.translate(V(-offset, 0, 0))
            placed.rotate(V(0, 0, 6), V(0, 1, 0), angle)
            tested_mount = obstacle.copy()
            if follow_wall:
                tested_mount.rotate(V(0, 0, 6), V(0, 1, 0), angle)
            overlap = abs(placed.common(tested_mount).Volume)
            rows.append(
                {
                    "slot_position_mm": offset,
                    "angle_deg": angle,
                    "interference_mm3": overlap,
                    "passed": overlap < TOL,
                }
            )
    return {
        "rotation_axis": "Y through the local bolt at Z6 mm",
        "half_angle_deg": 2.0,
        "sample_step_deg": 0.25,
        "slot_positions_mm": list(slot_positions),
        "carrier_follows_wall": follow_wall,
        "poses": rows,
        "scope": (
            "Ordinary carrier and saved single-wall/base coupon rotate together through±2° about the local bolt. The flat top datum follows the wall attitude; this is not a fixed-deck clearance claim. "
            if follow_wall
            else "Saved single-wall/base coupon rotates through±2° against a fixed shoe, a diagnostic interference screen only. "
        )
        + "Samples are a local geometric interference screen, not a certified continuous sweep, rail bend-radius allowance, paired-frame compliance, tape peel, stiffness, fatigue or strength result.",
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }
