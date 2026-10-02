"""Selected X06 supplied plastic horn, from manufacturer nominal STEP geometry.

The supplied horn remains unmodified. Three plain Ø1 holes are M1 candidates;
the inner Ø0.8 hole is not an M1 passage.
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
        return 6.0

    @property
    def blade_bottom_mm(self):
        return self.height_mm - self.arm_thickness_mm

    @property
    def screw_sku(self):
        return SCREW_SKU


SELECTED_PROFILE = "KST_X06_HALF_ARM_1"
PROFILES = {
    SELECTED_PROFILE: HornProfile(
        SELECTED_PROFILE,
        "KST_X06_STOCK_HALF_ARM_1",
        "X06 supplied plastic half arm 1 | unmodified factory holes",
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
SCREW_SKU = "M1X6_HEX_HEAD"
NUT_SKU = "M1_HEX_NUT"
HARDWARE_MATERIAL = "Unverified metal"
M1_USABLE_FACTORY_RADII_MM = (6.8, 10.0, 13.2)
OPTIONAL_ATTACHMENT_RADIUS_MM = 10.0
NUT_AF_MM = 2.5
NUT_MIN_AF_MM = 2.4
NUT_HEIGHT_MM = 0.8
# An explicit compatibility envelope, not an ISO 4017 M1 head specification:
# ISO 4017 starts at M1.6; received M1 external-hex heads remain unmeasured.
KST_SCREW_HEAD_AF_MM = 2.5
KST_SCREW_HEAD_HEIGHT_MM = 1.0
KST_SCREW_HEAD_DIAMETER_MM = 2 * KST_SCREW_HEAD_AF_MM / (3**0.5)
# Wera 2069 2.5 mm external-hex driver: published 5.7 mm blade diameter.
KST_TOOL_DIAMETER_MM = 5.7
KST_TOOL_LENGTH_MM = 60.0
NUT_DIMENSION_SOURCE = (
    "https://www.nbk1560.com/images/en/product/miniaturescrew/SHNS/SHNS_1.pdf"
)
HEX_HEAD_STANDARD_SCOPE_SOURCE = "https://www.iso.org/standard/72585.html"
HEX_TOOL_DIMENSION_SOURCE = (
    "https://www.wera.de/en-au/tools/2069-nutdriver-for-electronic-applications"
)


def profile(key=None, *, side=None):
    if side is not None:
        key = SELECTED_BY_SIDE[side]
    return PROFILES[key or SELECTED_PROFILE]


def preparation_note(item=None):
    item = item or profile()
    near, far = item.attachment_radii_mm
    return (
        f"Keep the supplied half arm 1 unmodified, including all four factory holes, "
        f"spline and OEM centre screw. Use the existing plain Ø1 holes at {near:g} "
        f"and {far:g} mm for two rear M1x6 external-hex bolts and front M1 nuts. "
        "The third Ø1 hole at10mm has an optional adapter opening; no third bolt "
        "is installed or included in the qualified default service sequence. "
        "The inner Ø0.8 hole at4.5mm is not M1-compatible. Do not drill, tap or "
        "force threads through the horn; the actual M1 bolts must slip through "
        "its existing Ø1 holes. Nominal equal diameters do not guarantee clearance. "
        "Design acceptance: external-hex heads at most AF2.5 x1.0mm; ordinary "
        "front nuts AF2.4..2.5 x0.8mm maximum. These are explicit envelopes, not "
        "a claim that all M1 heads or owned fasteners match. M1x6 is a design "
        "length, not the measured owned length. Check full nut engagement, tip "
        "projection, actual tool access, root seating and reversing-load runout. "
        "Hardware material and load capacity remain unverified; no washers."
    )
