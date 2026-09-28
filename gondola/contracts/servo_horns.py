"""Selected X06 supplied plastic horn, from manufacturer nominal STEP geometry.

Only the two existing outer Ø1 pilot holes are enlarged for through fasteners.
Manufacturer CAD does not establish delivered tolerances or installed seating.
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
    holes: tuple[tuple[float, float], ...]
    attachment_radii_mm: tuple[float, float]
    threaded: bool
    source: str
    evidence: str
    centre_hole_mm: float = 2.2
    height_mm: float = 3.5

    @property
    def screw_length_mm(self):
        return 8.0

    @property
    def blade_bottom_mm(self):
        return self.height_mm - self.arm_thickness_mm

    @property
    def screw_sku(self):
        return "M1_4X8_PAN_HEAD_KIT"


SELECTED_PROFILE = "KST_X06_HALF_ARM_1"
PROFILES = {
    SELECTED_PROFILE: HornProfile(
        SELECTED_PROFILE,
        "KST_X06_STOCK_HALF_ARM_1",
        "X06 supplied plastic half arm 1 | prepared outer factory holes",
        7.0,
        18.7,
        2.0,
        ((4.5, 0.8), (6.8, 1.0), (10.0, 1.0), (13.2, 1.0)),
        (6.8, 13.2),
        False,
        "KST manufacturer STEP supplied by user, 2026-09-28",
        "gondola/data/kst_x06_half_arm_1.step",
    ),
}
SELECTED_BY_SIDE = {"Port": SELECTED_PROFILE, "Starboard": SELECTED_PROFILE}
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
    return PROFILES[key or SELECTED_PROFILE]


def preparation_note(item):
    near, far = item.attachment_radii_mm
    return (
        f"On the detached supplied plastic half arm 1 enlarge only its existing "
        f"Ø1 holes at {near:g} and {far:g} mm to Ø1.5 mm and deburr. Preserve "
        "their factory axes, the other two holes, spline and OEM centre screw. "
        "Use two rear M1.4x8 pan-head screws and front M1.4 hex nuts per horn; "
        "no washers or threads cut into plastic. Rear heads must be at most "
        "Ø2.6 x 1.0 mm; front nuts at most 3.0 mm AF x 1.2 mm high. "
        "The nominal plain-hole ligament to the unused inner hole is 1.15 mm. "
        "Do not transfer new hole centres. Reject cracked or distorted arms and "
        "check clamping/runout under reversing load; nominal CAD is not a fit test."
    )
