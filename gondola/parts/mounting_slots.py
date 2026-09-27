"""Shared mounting slots; separate from the rigid structural tower joint.

Square pitch coverage and rotation are geometric allowances, not qualification
of an arbitrary board, fastener, standoff or occupied installation.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import box, union

V = App.Vector
MINIMUM_LAND = 1.5
SMALL_PITCH_RANGE = (20.0, 24.0)
SMALL_PATTERN_ROTATION = 30.0
LARGE_PITCH = 30.5
LARGE_ROTATION_RANGE = (-15.0, 15.0)
SIDE_X = 23.0
SIDE_Y_RANGE = (-9.0, 9.0)


def _radial_point(radius, angle):
    radians = math.radians(angle)
    return (radius * math.cos(radians), radius * math.sin(radians))


def rows():
    """Return fresh scalar records so consumers cannot mutate shared datums."""
    result = []
    for index in range(4):
        angle = SMALL_PATTERN_ROTATION - 45 + 90 * index
        result.append(
            {
                "name": f"square20_24_{index}",
                "kind": "straight",
                "family": "square20_24",
                "width_mm": 2.6,
                "fastener": "M2",
                "start_xy_mm": _radial_point(
                    SMALL_PITCH_RANGE[0] / math.sqrt(2), angle
                ),
                "end_xy_mm": _radial_point(SMALL_PITCH_RANGE[1] / math.sqrt(2), angle),
            }
        )
        result.append(
            {
                "name": f"square30_5_{index}",
                "kind": "arc",
                "family": "square30_5",
                "width_mm": 3.6,
                "fastener": "M3",
                "radius_mm": LARGE_PITCH / math.sqrt(2),
                "start_angle_deg": 45 + LARGE_ROTATION_RANGE[0] + 90 * index,
                "end_angle_deg": 45 + LARGE_ROTATION_RANGE[1] + 90 * index,
            }
        )
    for index, x in enumerate((-SIDE_X, SIDE_X)):
        result.append(
            {
                "name": f"side_{index}",
                "kind": "straight",
                "family": "side",
                "width_mm": 2.6,
                "fastener": "M2",
                "start_xy_mm": (x, SIDE_Y_RANGE[0]),
                "end_xy_mm": (x, SIDE_Y_RANGE[1]),
            }
        )
    return result


def shape(row, bottom, depth, *, border=0.0):
    """Exact capsule or rounded annular sector, including a continuous offset."""
    radius = row["width_mm"] / 2 + border
    if radius <= 0 or depth <= 0 or border < 0:
        raise ValueError(
            "Mounting slot requires positive width/depth and nonnegative border"
        )
    if row["kind"] == "straight":
        start = V(*row["start_xy_mm"], bottom)
        end = V(*row["end_xy_mm"], bottom)
        delta = end - start
        if delta.Length <= 0:
            raise ValueError("Straight slot endpoints must differ")
        middle = box(delta.Length, 2 * radius, depth, (0, -radius, 0))
        middle.rotate(V(), V(0, 0, 1), math.degrees(math.atan2(delta.y, delta.x)))
        middle.translate(start)
        ends = (start, end)
    elif row["kind"] == "arc":
        centre_radius = row["radius_mm"]
        start, end = row["start_angle_deg"], row["end_angle_deg"]
        if centre_radius <= radius or not 0 < end - start < 180:
            raise ValueError(
                "Arc slot requires positive inner radius and a short open arc"
            )
        middle = Part.makeCylinder(
            centre_radius + radius, depth, V(0, 0, bottom), V(0, 0, 1), end - start
        ).cut(
            Part.makeCylinder(
                centre_radius - radius, depth, V(0, 0, bottom), V(0, 0, 1), end - start
            )
        )
        middle.rotate(V(), V(0, 0, 1), start)
        ends = tuple(
            V(*_radial_point(centre_radius, angle), bottom) for angle in (start, end)
        )
    else:
        raise ValueError("Unknown mounting slot kind: " + str(row["kind"]))
    return union(
        [middle, *(Part.makeCylinder(radius, depth, point) for point in ends)]
    ).removeSplitter()


def shapes(bottom, depth, *, border=0.0):
    return [shape(row, bottom, depth, border=border) for row in rows()]


def contract():
    return {
        "datum_xy_mm": (0.0, 0.0),
        "slots": rows(),
        "slot_count": len(rows()),
        "minimum_full_thickness_land_mm": MINIMUM_LAND,
        "square_pitch_range_mm": SMALL_PITCH_RANGE,
        "square_pitch_range_rotation_deg": SMALL_PATTERN_ROTATION,
        "square30_5_pitch_mm": LARGE_PITCH,
        "square30_5_rotation_range_deg": LARGE_ROTATION_RANGE,
        "side_row_spacing_mm": 2 * SIDE_X,
        "side_centre_travel_y_mm": SIDE_Y_RANGE,
        "reference_patterns": [
            {
                "pitch_mm": 20.0,
                "fastener": "M2",
                "source": "https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/",
                "evidence": "Manufacturer lists a 20 x 20 mm pattern and M2/M3 screw or grommet compatibility. This slot family supports the M2 option; 20 through 24 mm pitches are geometric adjustment coverage, not another selected manufacturer's interface.",
            },
            {
                "pitch_mm": 30.5,
                "fastener": "M3",
                "source": "https://www.mateksys.com/?portfolio=f405-std",
                "evidence": "Manufacturer lists a 30.5 mm mounting pattern and supplied M3 vibration standoffs. Slot width and angular travel are this project's printed clearance choices.",
            },
        ],
        "x500_drop_in_compatible": False,
        "reference": "references/holybro_x500_plate_review.md",
        "scope": "Project-specific rounded slots inspired by the X500 payload plate, not its outline, datums or complete pattern. Four M2 radial slots geometrically admit square pitches 20 through 24 mm at 30 degrees; four M3 arcs admit a 30.5 mm square rotated -15 through +15 degrees. Opposed M2 side slots have 46 mm row spacing and independent +/-9 mm longitudinal centre travel. These are alternative positions for future devices, not simultaneously populated hardware. Fixed FC/P-AS bores retain their full support lands. Slots do not replace the two circular structural tower clamps. Select actual heads, nuts, standoffs and underside access after checking the installation; do not use existing small M2 heads on the M3-width arcs without a suitable independently reviewed bearing interface. No extra baseline fasteners or washers are selected.",
    }
