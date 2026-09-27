"""Three bought 15T/4 mm horn choices, independent on each input drive.

The shared printed adapter is invariant. Profiles describe installed envelopes,
not received-part metrology. KST's small plain holes need the explicitly stated
preparation; they must never be treated as supplied M1.6 threads.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HornProfile:
    key: str
    sku: str
    label: str
    root_diameter_mm: float
    overall_length_mm: float
    arm_thickness_mm: float
    holes: tuple[tuple[float, float], ...]  # radius, supplied hole diameter
    attachment_radii_mm: tuple[float, float]
    threaded: bool
    source: str
    evidence: str
    centre_hole_mm: float = 2.2
    height_mm: float = 3.5

    @property
    def screw_length_mm(self):
        return 5.0 if self.threaded else 6.0

    @property
    def blade_bottom_mm(self):
        return self.height_mm - self.arm_thickness_mm

    @property
    def screw_sku(self):
        return f"M1_{6 if self.threaded else 4}X{self.screw_length_mm:g}_PAN_HEAD_KIT"


PROFILES = {
    "PTK_6_6": HornProfile(
        "PTK_6_6",
        "ALI_PTK_15T_4MM_HORN",
        "15T/4 mm metal horn, 6.6 mm first hole",
        6.1,
        18.2,
        1.6,
        ((6.6, 1.6), (9.4, 1.6), (12.2, 1.6)),
        (6.6, 12.2),
        True,
        "https://www.aliexpress.com/item/1005012006498403.html",
        "references/selected_15t_4mm_horn_drawing.png",
    ),
    "METAL_6_98": HornProfile(
        "METAL_6_98",
        "METAL_15T_4MM_HORN_6_98",
        "15T/4 mm metal horn, 6.98 mm first hole",
        6.25,
        18.2,
        1.6,
        ((6.98, 1.6), (9.98, 1.6), (12.98, 1.6)),
        (6.98, 12.98),
        True,
        "User-supplied dimension drawing, 2026-09-27",
        "references/metal_15t_4mm_horn_6_98_drawing.png",
        2.3,
    ),
    "KST_0415_13": HornProfile(
        "KST_0415_13",
        "KST_0415_13_HORN",
        "KST 0415.13, prepared end holes",
        6.0,
        18.2,
        1.0,
        ((4.5, 0.8), (6.8, 1.0), (8.0, 0.8), (10.0, 1.0), (11.5, 0.8), (13.2, 1.0)),
        (4.5, 13.2),
        False,
        "https://kstservos.com/products/0415-13-aluminium-servo-arm-for-4mm-15t-servo",
        "references/kst_0415_13_horn_drawing.png",
    ),
}
# One original horn is available. Show a mixed pair without changing the print.
SELECTED_BY_SIDE = {"Port": "PTK_6_6", "Starboard": "METAL_6_98"}
PREPARED_HOLE_DIAMETER_MM = 1.5
NUT_AF_MM = 3.0
NUT_MIN_AF_MM = 2.9
NUT_HEIGHT_MM = 1.2
KST_SCREW_HEAD_DIAMETER_MM = 2.6
KST_SCREW_HEAD_HEIGHT_MM = 1.0
KST_TOOL_STEM_DIAMETER_MM = 1.5
NUT_DIMENSION_SOURCE = (
    "https://www.fastenal.com/content/product_specifications/M.FHN.934.A4-80.01.pdf"
)


def profile(key=None, *, side=None):
    if side is not None:
        key = SELECTED_BY_SIDE[side]
    return PROFILES[key or "PTK_6_6"]


def preparation_note(item):
    if item.threaded:
        return (
            "Use the first and third existing M1.6 threads; no horn drilling or nuts."
        )
    return (
        "On the detached horn enlarge only the existing end pilot holes at 4.5 and "
        "13.2 mm to 1.5 mm, deburr, then insert two M1.4x6 screws from the rear and fit M1.4 hex nuts on the adapter front. "
        "Rear screw heads must be at most 2.6 mm diameter and 1.0 mm high; front nuts at most 3.0 mm AF and 1.2 mm high. No washers. Do not transfer an axis or drill new centres. The narrowest nominal ligament "
        "to an unused hole is 0.55 mm; reject tearing/distortion and verify retention "
        "under reversing load. The factory holes are plain, not M1.6 threads."
    )
