"""Low, open M2 nut guides added above an existing bearing plane.

These guides stop an ordinary hex nut turning after nominal clearance is taken
up. They neither retain a loose nut axially nor qualify tightening torque.
"""

from gondola.cad import box, union

CLEAR_GAP = 4.25
WALL_WIDTH = 1.5
HEIGHT = 1.0


def rails_shape(length):
    """Two rails parallel to X; the unchanged nut seat is local Z0."""
    return union(
        [
            box(
                length,
                WALL_WIDTH,
                HEIGHT,
                (
                    -length / 2,
                    sign * CLEAR_GAP / 2 - (WALL_WIDTH if sign < 0 else 0),
                    0,
                ),
            )
            for sign in (-1, 1)
        ]
    )


def fit_contract():
    return {
        "sites": "Four rotor shaft clamps and four fixed bearing-keeper nut seats",
        "clear_gap_mm": CLEAR_GAP,
        "wall_width_mm": WALL_WIDTH,
        "height_above_unchanged_seat_mm": HEIGHT,
        "finished_gap_acceptance_mm": [4.2, 4.3],
        "nut_type": "Ordinary M2 hex nut; no flange, prevailing-torque or thin-nut compatibility claimed",
        "nominal_screw_axis_float_radius_mm": 0.1,
        "nut_axially_captive": False,
        "physical_fit_verified": False,
        "scope": "Nominal geometry only. Coupon-match the actual nut and production PA12 process/finish. The 4.2–4.3 mm finished gap is an acceptance target, not a general print-tolerance guarantee. Check full flat seating, actual nut chamfers, flank engagement, axial insertion/removal and torque restraint. Finish or reprint an unsuitable guide; do not force the nut between rails. The seat planes, screw lengths and clamp splits are unchanged. Open ends and tops allow powder removal and nut release.",
    }
