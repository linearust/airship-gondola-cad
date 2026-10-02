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


def _crown(x=0, low_y=-7, width=14):
    return Part.makeCylinder(4.5, width, V(x, low_y, 6), V(0, 1, 0))


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


def local_seat_check(section, mount, zone_length=10):
    """Actual bilateral crowned seats and local cheeks, without a flat-foot test."""
    if abs(zone_length - 10) > TOL:
        raise ValueError("The independently qualified local bearing zone is 10 mm")
    bottoms = []
    side_rows = []
    bore = Part.makeCylinder(1.7, 14, V(0, -7, 6), V(0, 1, 0))
    for sign in (-1, 1):
        low_y = -3 if sign < 0 else 1.75
        region = _box(10, 1.25, 4.5, -5, low_y, 1.5)
        expected = region.common(_crown()).cut(bore)
        actual = mount.common(region)
        missing = abs(expected.cut(actual).Volume)
        excess = abs(actual.cut(expected).Volume)
        # A thin base witness supports the tangent station. Its size is a
        # geometry probe, not an asserted contact patch or pressure estimate.
        base = _box(0.02, 1.25, 0.01, -0.01, low_y, 1.49)
        missing_base = abs(base.cut(section).Volume)
        bottoms.append(
            {
                "side": sign,
                "profile": "R4.5 circular crown about the M3 axis",
                "tangent_z_mm": 1.5,
                "flat_contact_area_claimed": False,
                "missing_contact_mm3": missing + missing_base,
                "missing_crown_stock_mm3": missing,
                "excess_below_crown_mm3": excess,
                "missing_tangent_base_support_mm3": missing_base,
                "passed": max(missing, excess, missing_base) < TOL,
            }
        )
        outside_y = -1.26 if sign < 0 else 1.25
        face = _box(10, 0.01, 6.9, -5, outside_y, 2.6)
        # Exclude the complete slot-height band, so the witnesses remain valid
        # at every slot position. Both upper and lower cheek stock is retained.
        face = face.cut(_box(12, 3, 3.4, -6, -1.5, 4.3))
        lower = face.common(_box(12, 3, 3.4, -6, -1.5, 2.6)).common(_crown())
        upper = face.common(_box(12, 3, 3.5, -6, -1.5, 6))
        face = lower.fuse(upper)
        inside = face.copy()
        inside.translate(V(0, -sign * 0.01, 0))
        missing_side = abs(face.cut(mount).Volume) + abs(inside.cut(section).Volume)
        side_rows.append(
            {
                "side": sign,
                "checked_local_length_mm": 10.0,
                "witness_area_mm2": face.Volume / 0.01,
                "missing_contact_mm3": missing_side,
                "passed": missing_side < TOL,
            }
        )
    roof = _box(10, 2.5, 0.7, -5, -1.25, 9.5)
    root_relief = _box(10, 3.5, 1.1, -5, -1.75, 1.5)
    blocked_roof = abs(roof.common(mount).Volume)
    blocked_root = abs(root_relief.common(mount).Volume)
    return {
        "bottom_datum_contacts": bottoms,
        "local_side_contacts": side_rows,
        "inner_roof_clearance_mm": 0.7,
        "blocked_inner_roof_relief_mm3": blocked_roof,
        "blocked_root_relief_mm3": blocked_root,
        "missing_flat_side_contact_mm3": side_rows[0]["missing_contact_mm3"],
        "missing_opposite_side_contact_mm3": side_rows[1]["missing_contact_mm3"],
        "scope": "Ten millimetre local cheeks and R4.5 crowned lower seats. The lower datum is a nominal tangent, with no finite flat contact area or contact pressure claimed.",
        "passed": all(row["passed"] for row in bottoms + side_rows)
        and max(blocked_roof, blocked_root) < TOL,
    }


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


def angular_clearance_check(section, mount, *, slot_positions=(-3, 0, 3)):
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
            overlap = abs(placed.common(obstacle).Volume)
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
        "poses": rows,
        "scope": "Saved single-wall/base coupon sampled through ±2° about one bolt at the stated slot positions. Samples are a local geometric interference screen, not a certified continuous sweep, rail bend-radius allowance, paired-frame compliance, tape peel, stiffness, fatigue or strength result.",
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }
