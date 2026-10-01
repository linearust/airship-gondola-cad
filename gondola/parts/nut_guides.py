"""Shallow, freely seating M2 keeper pockets within the fixed frame face.

The recess limits ordinary hex-nut rotation after clearance is taken up.
It neither captures a loose nut axially nor qualifies tightening torque.
"""

from .purchased_hardware import hex_prism

CLEAR_GAP = 4.25
POCKET_DEPTH = 0.5


def pocket_tool():
    """Hex cutter; local Z0 is the nut bearing plane below the host face."""
    return hex_prism(CLEAR_GAP, POCKET_DEPTH + 0.01)


def fit_contract():
    return {
        "sites": "Four fixed bearing-keeper nut seats; rotor clamps use deeper recessed hex pockets",
        "clear_gap_mm": CLEAR_GAP,
        "recess_depth_mm": POCKET_DEPTH,
        "minimum_frame_floor_mm": 2.0,
        "finished_gap_acceptance_mm": [4.2, 4.3],
        "nut_type": "Ordinary M2 hex nut; no flange, prevailing-torque or thin-nut compatibility claimed",
        "nominal_screw_axis_float_radius_mm": 0.1,
        "nut_axially_captive": False,
        "physical_fit_verified": False,
        "scope": "Nominal geometry only. Coupon-match the actual nut and production PA12 process/finish. The 4.2–4.3 mm finished gap is an acceptance target, not a general print-tolerance guarantee. Nuts must enter and leave freely while retaining flat-flank engagement; actual chamfers can consume the shallow 0.5 mm recess. Check full seating, antirotation and axial service. Finish or reprint an unsuitable pocket; do not force the nut. The keeper screw remains M2x6; its seat moves 0.5 mm inward without moving bearing or keeper datums. No strength or torque rating.",
    }
