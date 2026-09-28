"""Nominal purchased carbon stack adapter; no inferred precision cutout geometry.

The seller drawing supplies mounting pitches and nominal holes. A filled square
is a conservative external clearance envelope, not a certified material/contact
footprint. This module is independent of FreeCAD and printed-carrier dimensions.
"""

import math

PART_SKU = "CARBON_STACK_ADAPTER_30MM"
PRODUCT_URL = "https://ko.aliexpress.com/item/1005009117550746.html"
MODEL = "30 mm carbon FPV stack adapter, 25.5 / 20 / 16 mm"
MATERIAL = "carbon_fiber_laminate"
OUTER_SIZE_MM = (30.0, 30.0)
THICKNESS_MM = 1.0
LISTED_MASS_G = 0.72
HOLE_DIAMETER_MM = 2.0
SQUARE_PITCHES_MM = (25.5, 20.0, 16.0)
SELECTED_OPTION = "5PCS"
SELECTED_OPTION_BOARD_COUNT = 5
COMMON_PITCH_MM = 25.5
COMMON_ROTATION_DEG = 45.0
EVIDENCE_FILE = "references/stock_stack_adapter/product_evidence.json"
DRAWING_FILE = "references/stock_stack_adapter/dimension_drawing.png"


def hole_centres(pitch_mm, rotation_deg=0.0):
    """Return four sorted XY axes for one supported nominal square pattern.

    Coordinates use the plate centre; rotation is about +Z. Zeroing roundoff on
    cardinal axes makes the common 45-degree interface stable for serialization.
    These are nominal part datums, not printed hole sizes or fit allowances.
    """
    if pitch_mm not in SQUARE_PITCHES_MM:
        raise ValueError(f"Unsupported stock adapter pitch: {pitch_mm!r}")
    if not math.isfinite(rotation_deg):
        raise ValueError("Stack adapter rotation must be finite")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    half = pitch_mm / 2

    def clean(value):
        return 0.0 if abs(value) < 1e-12 else value

    return tuple(
        sorted(
            (
                clean(x * cosine - y * sine),
                clean(x * sine + y * cosine),
            )
            for x in (-half, half)
            for y in (-half, half)
        )
    )


COMMON_HOLE_CENTRES = hole_centres(COMMON_PITCH_MM, COMMON_ROTATION_DEG)
RAIL_FIX_PITCH_MM = 16.0
RAIL_FIX_CENTRES = tuple(
    (x, y)
    for x, y in hole_centres(RAIL_FIX_PITCH_MM, COMMON_ROTATION_DEG)
    if abs(y) > 1
)
RAIL_TRACK_SPACING_MM = 2 * abs(RAIL_FIX_CENTRES[0][1])


def stack_adapter_contract():
    """Return fresh metadata for one bought plate, separate from kit quantities."""
    return {
        "sku": PART_SKU,
        "model": MODEL,
        "purchased_part": True,
        "printed_part": False,
        "source": PRODUCT_URL,
        "retained_evidence": [EVIDENCE_FILE, DRAWING_FILE],
        "material_claim": MATERIAL,
        "outer_size_mm": OUTER_SIZE_MM,
        "thickness_mm": THICKNESS_MM,
        "listed_mass_g": LISTED_MASS_G,
        "mass_basis": "Seller reference for one board, not measured and not derived from the modeled envelope.",
        "hole_diameter_mm": HOLE_DIAMETER_MM,
        "hole_type": "nominal unthreaded through-hole",
        "patterns": [
            {"square_pitch_mm": pitch, "centres_xy_mm": hole_centres(pitch)}
            for pitch in SQUARE_PITCHES_MM
        ],
        "pattern_basis": "Horizontal pitches and diameter 2 mm are dimensioned. Concentric square patterns follow the illustrated symmetry; separate vertical pitch tolerances are not specified.",
        "selected_option": SELECTED_OPTION,
        "selected_option_board_count": SELECTED_OPTION_BOARD_COUNT,
        "included_hardware_quantities_confirmed": False,
        "package_scope": "Saved option and gallery say 5PCS. General delivery text instead lists 1 board, 8 M2 nylon nuts, 4 M2x6 and 4 M2x8 screws. Do not assume those hardware counts apply per board or multiply them by 5.",
        "fc_axis_reference": {
            "square_pitch_mm": COMMON_PITCH_MM,
            "rotation_deg": COMMON_ROTATION_DEG,
            "centres_xy_mm": COMMON_HOLE_CENTRES,
            "fastener_nominal": "M2",
            "clamp_scope": "This25.5mm pattern identifies FC and selected optional portal axes, not the16mm rail fixation. Carbon-to-rail clamping is independent of FC soft support. Do not use PCB or damper compression as a rigid clamp stop; retain the FC separately.",
        },
        "project_rail_interface": {
            "square_pitch_mm": RAIL_FIX_PITCH_MM,
            "rotation_deg": COMMON_ROTATION_DEG,
            "selected_centres_xy_mm": RAIL_FIX_CENTRES,
            "track_spacing_mm": RAIL_TRACK_SPACING_MM,
            "fastener": "Two owned ordinary M2x6 screws, downwards into rail hex-nut guides",
            "scope": "Project installation uses the opposed Y pair of the purchased16mm pattern. It does not add a seller feature, qualify contact material or make neighboring patterns simultaneously usable.",
        },
        "electrical": "Carbon fiber is conductive. Isolate exposed conductors and FC underside from the plate; required wiring height and insulating hardware are separate assembly constraints.",
        "simultaneous_hole_use": "Pattern existence does not prove simultaneous hardware clearance. Same-corner centre spacing is 2.828 mm for 16/20, 3.889 mm for 20/25.5 and 6.718 mm for 16/25.5. Heads, nuts and standoffs on adjacent patterns can overlap; check actual hardware and occupied faces/heights.",
        "contour_scope": "Central hole, interior cutouts, outer waist and corner blends are not dimensioned. Do not use traced edges as precision locators or infer continuous support/adhesive material from a filled 30x30 mm envelope.",
        "unknown": "Hole/position/thickness/flatness tolerances, laminate lay-up, stiffness/strength, exact contour and cutouts, central-hole diameter, verified bearing footprints, delivered kit hardware and received dimensions.",
        "physical_fit_verified": False,
    }
