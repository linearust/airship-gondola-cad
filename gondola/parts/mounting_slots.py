"""Symmetric shared square/rectangular slots and support-foot attachments.

Pattern coverage and quarter-turn alternatives are geometric provisions, not qualification
of an arbitrary board, fastener, standoff or occupied installation.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import box, union

V = App.Vector
MINIMUM_LAND = 1.5
SMALL_PITCH_RANGE = (16.0, 20.0)
SMALL_PATTERN_ROTATION = 0.0
OUTER_DIAGONAL_PITCH_RANGE = (40.0, 45.0)
LARGE_PITCH = 30.5
LARGE_PITCH_RANGE = (30.0, 31.0)
LARGE_ROTATION_RANGE = (0.0, 0.0)
FC_PITCH_RANGE = (25.0, 26.0)
SIDE_X = 27.0
SIDE_Y_RANGE = (13.0, 19.0)
SIDE_MIDDLE_Y_RANGE = (-5.0, 5.0)
# Stop before the complete 6.5 mm FC bearing-face sweep at the 25 mm endpoint.
CENTRAL_AXIS_RADIUS_RANGE = (11.5, 13.0)


def _radial_point(radius, angle):
    radians = math.radians(angle)
    return (radius * math.cos(radians), radius * math.sin(radians))


def rows():
    """Return fresh scalar records so consumers cannot mutate shared datums."""
    result = []
    large_near, large_far = (pitch / 2 for pitch in LARGE_PITCH_RANGE)
    for index in range(4):
        result.append(
            {
                "name": f"square25_26_{index}",
                "kind": "straight",
                "family": "square25_26",
                "width_mm": 2.6,
                "fastener": "M2",
                "start_xy_mm": _radial_point(
                    FC_PITCH_RANGE[0] / math.sqrt(2), 90 * index
                ),
                "end_xy_mm": _radial_point(
                    FC_PITCH_RANGE[1] / math.sqrt(2), 90 * index
                ),
            }
        )
        angle = SMALL_PATTERN_ROTATION - 45 + 90 * index
        result.append(
            {
                "name": f"square16_20_{index}",
                "kind": "straight",
                "family": "square16_20",
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
                "name": f"square40_45_{index}",
                "kind": "straight",
                "family": "square40_45",
                "width_mm": 2.6,
                "fastener": "M2",
                "start_xy_mm": _radial_point(
                    OUTER_DIAGONAL_PITCH_RANGE[0] / math.sqrt(2), angle
                ),
                "end_xy_mm": _radial_point(
                    OUTER_DIAGONAL_PITCH_RANGE[1] / math.sqrt(2), angle
                ),
            }
        )
        quarter_turn = math.radians(90 * index)

        def rotate(point):
            x, y = point
            return (
                x * math.cos(quarter_turn) - y * math.sin(quarter_turn),
                x * math.sin(quarter_turn) + y * math.cos(quarter_turn),
            )

        result.append(
            {
                "name": f"rectangle25_30_square30_31_{index}",
                "kind": "polyline",
                "family": "rectangle25_30_square30_31",
                "width_mm": 3.6,
                "fastener": "M2.5 or M3 with reviewed broad bearing hardware",
                "points_xy_mm": tuple(
                    # Retracing the short radial branch preserves mirror symmetry
                    # and the full 30..31 square travel between the A8 endpoints.
                    rotate(point)
                    for point in (
                        (12.5, 15),
                        (large_near, large_near),
                        (large_far, large_far),
                        (large_near, large_near),
                        (15, 12.5),
                    )
                ),
            }
        )
        for sign in (-1, 1):
            result.append(
                {
                    "name": f"rectangle58_49_{index}_{sign}",
                    "kind": "straight",
                    "family": "rectangle58_49",
                    "width_mm": 3.2,
                    "fastener": "M2.5 with reviewed broad bearing hardware",
                    "start_xy_mm": rotate((29, sign * 23.5)),
                    "end_xy_mm": rotate((29, sign * 25.5)),
                }
            )
    for index in range(4):
        result.append(
            {
                "name": f"central_axis_{index}",
                "kind": "straight",
                "family": "central_axis",
                "width_mm": 2.6,
                "fastener": "M2",
                "start_xy_mm": _radial_point(CENTRAL_AXIS_RADIUS_RANGE[0], 90 * index),
                "end_xy_mm": _radial_point(CENTRAL_AXIS_RADIUS_RANGE[1], 90 * index),
            }
        )
        angle = math.radians(90 * index)
        for suffix, interval in (
            ("negative", tuple(-y for y in SIDE_Y_RANGE)),
            ("middle", SIDE_MIDDLE_Y_RANGE),
            ("positive", SIDE_Y_RANGE),
        ):
            points = tuple(
                (
                    SIDE_X * math.cos(angle) - y * math.sin(angle),
                    SIDE_X * math.sin(angle) + y * math.cos(angle),
                )
                for y in interval
            )
            result.append(
                {
                    "name": f"side_{index}_{suffix}",
                    "kind": "straight",
                    "family": "side",
                    "width_mm": 2.6,
                    "fastener": "M2",
                    "start_xy_mm": points[0],
                    "end_xy_mm": points[1],
                }
            )
    return result


def shape(row, bottom, depth, *, border=0.0):
    """Exact capsule or joined capsule path, including continuous offset."""
    radius = row["width_mm"] / 2 + border
    if radius <= 0 or depth <= 0 or border < 0:
        raise ValueError(
            "Mounting slot requires positive width/depth and nonnegative border"
        )
    if row["kind"] == "polyline":
        points = row["points_xy_mm"]
        if len(points) < 3:
            raise ValueError("Polyline slot requires at least three points")
        return union(
            [
                shape(
                    {**row, "kind": "straight", "start_xy_mm": start, "end_xy_mm": end},
                    bottom,
                    depth,
                    border=border,
                )
                for start, end in zip(points, points[1:])
            ]
        ).removeSplitter()
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
        "quarter_turn_and_xy_mirror_symmetric": True,
        "minimum_full_thickness_land_mm": MINIMUM_LAND,
        "square_pitch_range_mm": SMALL_PITCH_RANGE,
        "square_pitch_range_rotation_deg": SMALL_PATTERN_ROTATION,
        "outer_diagonal_square_pitch_range_mm": OUTER_DIAGONAL_PITCH_RANGE,
        "square30_5_pitch_mm": LARGE_PITCH,
        "large_square_pitch_range_mm": LARGE_PITCH_RANGE,
        "square30_5_rotation_range_deg": LARGE_ROTATION_RANGE,
        "fc_square_pitch_range_mm": FC_PITCH_RANGE,
        "fc_square_pitch_range_rotation_deg": 45.0,
        "side_row_spacing_mm": 2 * SIDE_X,
        "side_centre_travel_y_mm": SIDE_Y_RANGE,
        "side_middle_centre_travel_y_mm": SIDE_MIDDLE_Y_RANGE,
        "central_axis_radius_range_mm": CENTRAL_AXIS_RADIUS_RANGE,
        "central_axis_opposed_pitch_range_mm": tuple(
            2 * radius for radius in CENTRAL_AXIS_RADIUS_RANGE
        ),
        "reference_patterns": [
            {
                "pitch_mm": 20.0,
                "fastener": "M2",
                "source": "https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/",
                "evidence": "Manufacturer lists a 20 x 20 mm pattern and M2/M3 screw or grommet compatibility. This slot family supports the M2 option; 16 through 20 mm pitches are geometric adjustment coverage, not another selected manufacturer's interface.",
            },
            {
                "pitch_mm": 30.5,
                "fastener": "M3",
                "source": "https://www.mateksys.com/?portfolio=f405-std",
                "evidence": "Manufacturer lists a 30.5 mm mounting pattern and supplied M3 vibration standoffs. This project's short radial branch covers square pitches30..31mm; slot width and the shared rectangular/square corner path are printed clearance choices, not full angular travel.",
            },
        ],
        "x500_drop_in_compatible": False,
        "reference": "references/dense_mount_review.md",
        "optional_payloads": optional_payload_profiles(),
        "scope": "Project array, not a universal industry breadboard or drop-in X500 interface. Four inner M2 diagonal slots accept square pitches16..20mm; four outer diagonals accept40..45mm. Four short corner paths accept M3 square pitches30..31mm and a25x30mm M2.5 rectangle in either quarter-turn orientation; no angular travel is claimed. Eight outer M2.5 slots accept58x49mm rectangles in either quarter-turn orientation. Four axial M2 slots provide opposed spacing23..26mm, including the repositioned P-AS pair. Twelve side M2 slots on a54mm square preserve the optical foot at each side midpoint and accept reviewed power feet at(+27,+19)/(-27,-19). Four short M2 radial slots accept square pitches25..26mm at45deg, including the unchanged nominal25.5mm FC axes; complete6.5mm bearing-face sweeps remain except for the intended slots. Tighten the installed stack before operation; these openings do not self-centre a board. Patterns are alternative uses, not simultaneous-device clearance or load qualification. Wider slots require separately reviewed bearing hardware; default small M2 heads must not bridge them. Bench-service and occupied-device checks remain mandatory.",
    }


def optional_payload_profiles():
    """Published patterns plus explicit geometric fastener acceptance envelopes.

    Profiles are provisions only; they do not add hardware, equipment mass or an
    installed device to the baseline. Bearing dimensions below are design choices.
    """
    return {
        "RaspberryPi5": {
            "pattern_mm": (58.0, 49.0),
            "published_hole_diameter_mm": 2.7,
            "fastener": "M2.5",
            "slot_family": "rectangle58_49",
            "bearing_diameter_mm": 5.5,
            "bearing_type": "Flat circular standoff/washer face; verify supplied hardware",
            "source": "https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf",
            "retained_source": "references/manufacturer/raspberry_pi5_mechanical_drawing.pdf",
            "scope": "Manufacturer reference drawing, not production tolerance data. PCB85x56mm extends beyond this carrier when its hole pattern is centred. Standoff height, underside components, cooling and connector access are not qualified.",
        },
        "SIYIA8Mini": {
            "pattern_mm": (25.0, 30.0),
            "published_hole_diameter_mm": 2.7,
            "fastener": "M2.5",
            "slot_family": "rectangle25_30_square30_31",
            "bearing_diameter_mm": 7.0,
            "bearing_type": "Flat circular load-spreading face; verify selected washer/standoff",
            "source": "https://res.siyi.biz/oss/other/2026/06/15/A8_mini_User_Manual_v1_10_563cde30.pdf",
            "retained_source": "references/manufacturer/siyi_a8_mini_mounting.png",
            "scope": "Mount the original vibration-isolated assembly. Pattern support does not qualify the95g published payload, full gimbal sweep, optical field or rail strength. Published11..25.2V input is incompatible with direct2S/8V. No baseline installation or screw length is selected.",
        },
    }
