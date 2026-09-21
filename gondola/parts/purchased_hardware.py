"""Purchased M2 mechanism hardware, modeled as simple dimensional envelopes.

No modeled helical threads, no custom printed fasteners. The exact procurement
item remains unselected; the cited manufacturers substantiate the purchasing
geometry, not a tested marketplace SKU. All objects are excluded from STL lists.
"""

import functools
import math
import re
from functools import partial
from urllib.parse import quote_plus

import FreeCAD as App
import Part

from gondola.cad import set_property as _set_property
from gondola.contracts.equipment_interfaces import (
    BEARING_SOURCE,
    GEAR_SOURCE,
    HORN_SOURCE,
    SHAFT_CATALOG_SOURCE,
    SHAFT_SOURCE,
)
from gondola.contracts.fasteners import CLAMP_SCREW_LENGTH as CLAMP_SCREW_LENGTH
from gondola.contracts.fasteners import SCREW_HEAD_DIAMETER as SCREW_HEAD_DIAMETER
from gondola.contracts.fasteners import SCREW_HEAD_HEIGHT as SCREW_HEAD_HEIGHT
from gondola.contracts.fasteners import SOCKET_DEPTH as SOCKET_DEPTH
from gondola.contracts.fasteners import SOCKET_KEY as SOCKET_KEY
from gondola.contracts.fasteners import SQUARE_NUT_AF as SQUARE_NUT_AF
from gondola.contracts.fasteners import SQUARE_NUT_HEIGHT as SQUARE_NUT_HEIGHT
from gondola.contracts.fasteners import THREAD_DIAMETER as THREAD_DIAMETER
from gondola.contracts.fasteners import THREAD_PITCH as THREAD_PITCH

set_property = partial(_set_property, group="Purchased hardware")

V = App.Vector
PURCHASED_COLOR = (0.86, 0.67, 0.27)
CLAMP_SCREW_SOURCE = (
    "https://www.accu.co.uk/metric-cap-head-screws/152178-SSCF-M2-8-A2-BL"
)
SERVO_SCREW_SOURCE = (
    "https://www.accu.co.uk/metric-cheese-head-screws/6455-SFE-M1-6-8-A2"
)
SERVO_NUT_SOURCE = "https://www.ettinger.de/en/product-datasheet/4ca7065842fccd4de02bac906e3675ad/create"
STACK_SCREW_SOURCE = (
    "https://www.ricoplastics.co.uk/shop-components/product/"
    "167-nylon-pan-head-screws-m2-x-5mm/"
)
STACK_SCREW_DRAWING_SOURCE = (
    "https://cdn.rwd.group/ricoplastics.co.uk/docs/shop/"
    "167-nylon-pan-head-screws-m2-x-5mm-179.pdf"
)
STACK_SCREW_LENGTH = 5.0
STACK_SCREW_HEAD_DIAMETER = 4.0
STACK_SCREW_HEAD_HEIGHT = 1.3
STACK_SPACER_SOURCE = (
    "https://www.kangyang-usa.com/wp-content/uploads/2026/09/HPS2-H-18-2.pdf"
)
STACK_SPACER_AF = 4.0
STACK_SPACER_LENGTH = 25.0
STACK_SPACER_THREAD_DEPTH_REFERENCE = 4.0
SQUARE_NUT_SOURCE = "https://www.accu.co.uk/flat-square-nuts/21324-HFSN-M2-A2"
SQUARE_NUT_PTS_SOURCE = (
    "https://www.pts-uk.com/products/nuts/square-nuts/metric-a2/a56202"
)
PURCHASING_STATUS = (
    "Specification only; no AliExpress SKU, supplier lot or actual purchased sample "
    "has been verified. Search results and cited dimensional examples are not "
    "approved purchase selections."
)

# A CAD SKU denotes the required interface, not an identified seller's listing.
# Keep these requirements with the native bought-part objects so a generated BOM
# contains the purchase conditions without relying on a separate guide.
PROCUREMENT_SPECS = {
    "M1_6X8_CHEESE_HEAD": {
        "search_query": "M1.6x8 DIN84 A2 slotted cheese head screw 3mm head",
        "candidate_url": SERVO_SCREW_SOURCE,
        "requirements": "A2 stainless M1.6 x 0.35, 8 mm under-head length, DIN 84 slotted cheese head: maximum diameter 3 mm, height 1 mm, slot width 0.4 mm and depth 0.45 mm. Four X06 ear screws. Smaller than the general M2 hardware to provide nominal 0.2 mm radial clearance in the published 2 mm servo ear holes and 0.5 mm head-to-case gap. No washers. Check actual ear seating and safe tightening; not the OEM spline-retaining screw.",
    },
    "M1_6_HEX_NUT_DIN934": {
        "search_query": "M1.6 DIN934 A2 hex nut 3.2mm 1.3mm",
        "candidate_url": SERVO_NUT_SOURCE,
        "requirements": "A2 stainless DIN 934 / ISO 4032 M1.6 x 0.35 hex nut, 3.2 mm across flats and 1.3 mm nominal height. Four X06 ear nuts, accessible with a small wrench. Does not replace the captive M2 DIN 562 square nuts elsewhere. No washers; check actual engagement and printed support faces.",
    },
    "MR63ZZ": {
        "search_query": "NSK Micro Precision ISC MR63ZZ 3x6x2.5 bearing",
        "candidate_url": BEARING_SOURCE,
        "requirements": "NSK Micro Precision (ISC) MR63ZZ, 3 x 6 x 2.5 mm, double shielded. Eight installed: four output-axis bearings and four separate input-axis bearings. Do not substitute an open MR63 or a different brand under the same generic size without rechecking fits. Published reference mass 0.27 g each. Do not load the shields; inner-ring abutment OD at most 3.7 mm, housing shoulder opening at least 5.4 mm. Fits and endplay require trials.",
    },
    "KST_0415_13": {
        "search_query": "KST 0415.13 aluminium servo arm 15T 4mm",
        "candidate_url": HORN_SOURCE,
        "requirements": "KST 0415.13 aluminium horn, 15T / 4 mm spline class. Selected separately from the unmeasured plastic horn supplied with X06. Verify actual spline fit and use the correct OEM retaining screw; its thread/length are not inferred from the horn clearance hole. Stock arm requires no added hole pattern; the printed coupling captures its blade. Installed axial seating, outline tolerances and clamping fit remain sample checks.",
    },
    "M2X8_SOCKET_CAP": {
        "search_query": "M2x8 DIN912 A2 socket cap screw",
        "requirements": (
            "A2 stainless steel, M2 x 0.4 right-hand, 8 mm under-head length. "
            "DIN 912 / ISO 4762 socket cap shape; nominal head diameter 3.8 mm, "
            "head height 2 mm and 1.5 mm hex key. Shared propulsion mounting, "
            "bearing caps and shaft clamps; match each documented grip and "
            "thread projection. No washers. Use minimal preload and verify "
            "PA12 retention/creep. This is not an OEM horn or motor screw."
        ),
        "evidence_notes": (
            "Accu's discontinued black-finish A2 example supports nominal "
            "dimensions only; no finish or current stock requirement is inferred. "
            "Select a currently available A2 DIN 912 / ISO 4762 screw matching "
            "the interface. Seller lot, strength and actual mass remain unverified."
        ),
    },
    "M2X5_PA66_PAN_HEAD": {
        "search_query": "M2x5 PA66 nylon 66 slotted pan head screw 4mm head",
        "requirements": (
            "Bought Nylon PA66 slotted pan screw, M2 x 0.4 right-hand, "
            "5 mm under-head length; nominal head diameter 4 mm and height "
            "1.3 mm. Match RI-CO's M2 x 5 mm nylon pan-head product; no "
            "DIN 912 / ISO 4762 or socket-drive claim. No washers. Four screws "
            "attach two stack spacers through 2 mm printed plates; nominal "
            "thread penetration is 3.0 mm. Two screws clamp the manual optical "
            "pivots through two 1.5 mm ears and a DIN 562 square nut: nominal "
            "grip 4.2 mm and tip projection 0.8 mm. Check actual printed thickness, "
            "screw length and usable female depth; do not bottom the screw. "
            "Use minimal hand preload and check angle retention with actual "
            "cables. Do not substitute PA6, unspecified nylon or printed screws."
        ),
        "candidate_url": STACK_SCREW_SOURCE,
        "evidence_notes": (
            "RI-CO's product page lists Nylon 66, M2, length 5 mm and head "
            "4 x 1.3 mm. Its linked preliminary drawing dated 30/6/24 "
            "identifies a slotted pan head and under-head thread length, "
            "but does not dimension the slot or tolerances. M2 x 0.4 is "
            "the required mating thread; the product page does not separately "
            "state pitch. CAD retains the cylindrical head envelope without "
            "inventing the slot or crown profile. Drawing: "
            + STACK_SCREW_DRAWING_SOURCE
            + ". Retained evidence: references/rico_m2x5_nylon_screw.pdf. "
            "Nominal screw length with a printed plate 2 +/-0.3 mm gives "
            "2.7-3.3 mm stack penetration. Two pivot ears each 1.5 +/-0.3 mm "
            "leave at least 0.2 mm nominal tip projection through a 1.2 mm nut. "
            "Both ranges exclude screw-length tolerance. These geometric "
            "allowances do not qualify thread engagement, tightening torque, "
            "PA66 creep life or strength. No seller lot or actual mass is verified."
        ),
    },
    "M2_FF_PA66_AF4_L25": {
        "search_query": "M2 female female nylon PA66 hex standoff 25mm 4mm AF",
        "requirements": (
            "Bought Nylon PA66 female-female standoff, M2 x 0.4 right-hand "
            "threads at both ends. Match Kang Yang HPS2-25: nominal body "
            "length 25 mm, across flats 4 mm; drawing tolerances +/-0.4 mm "
            "length and +/-0.2 mm across flats. Do not substitute metal, "
            "PA6, an unspecified nylon grade, a male-female part or a printed "
            "spacer. Verify at least 3.6 mm actual usable female depth at "
            "each end, then confirm measured screw penetration does not bottom. "
            "This depth acceptance is our purchasing condition, not a "
            "manufacturer-guaranteed thread depth or retention rating."
        ),
        "candidate_url": STACK_SPACER_SOURCE,
        "evidence_notes": (
            "Kang Yang HPS2-H Rev B drawing specifies Nylon 66 UL94V-2, "
            "M2x0.4 and the HPS2-25 dimensions. Its long-spacer drawing shows "
            "4 mm REF tapped depth at each end, not guaranteed full-length "
            "threading. CAD uses a solid hex body and two diameter 2 mm by "
            "4 mm nominal bores; internal unthreaded geometry, chamfers and "
            "helical threads are not measured. Manufacturer mass, minimum "
            "usable engagement, thread strength, preload and creep life "
            "remain unverified. Retained evidence: "
            "references/kangyang_hps2_dimensions.pdf."
        ),
    },
    "M2x6_ISO4026_DIN913": {
        "search_query": "M2x6 DIN913 flat point stainless set screw",
        "requirements": (
            "A2 stainless steel, M2 x 0.4 right-hand, 6 mm overall length. "
            "DIN 913 / ISO 4026 flat-point set screw with 0.9 mm hex key. "
            "Do not substitute a cup point or cone point. One screw/DIN 562 "
            "square-nut pair per rail shoe; the unused opposite clamp port stays empty."
        ),
    },
    "M2_SQUARE_NUT_DIN562": {
        "search_query": "M2 DIN562 A2 flat square nut 4 1.2",
        "requirements": (
            "A2 stainless steel, DIN 562 M2 x 0.4 right-hand flat square nut. "
            "Nominal width 4 mm and height 1.2 mm; accepted width 3.6-4.0 mm "
            "and height 0.8-1.2 mm. Shared by the rail clamps, propulsion clamps, "
            "bearing caps, input mounts and optical pivots. No washers. Preserve square "
            "corners for rail anti-rotation; verify actual corner form and captive "
            "fit with the printed coupon. Exposed propulsion and pivot nuts require "
            "a holding tool. Do not substitute a hex nut."
        ),
        "candidate_url": SQUARE_NUT_SOURCE,
        "evidence_notes": (
            "Accu HFSN-M2-A2 lists width 4 +0/-0.4 mm (minimum 3.6 mm) "
            "and height 1.2 +0/-0.4 mm. PTS A56202 lists width 4.0-3.7 mm "
            "and height 1.2-0.8 mm: " + SQUARE_NUT_PTS_SOURCE + ". "
            "The tolerance check uses the broader Accu minimum width 3.6 mm. "
            "The dimensional examples do not verify the selected seller lot, "
            "corner form, thread strength or printed pocket retention."
        ),
    },
}

for _teeth in (60, 20):
    _sku = f"GEABP0.5-{_teeth}-3-B-3"
    PROCUREMENT_SPECS[_sku] = {
        "search_query": f"MISUMI {_sku}",
        "candidate_url": GEAR_SOURCE,
        "requirements": (
            f"MISUMI {_sku}: white POM, module 0.5, pressure angle 20 degrees, "
            f"{_teeth} teeth, 3 mm H7 bore, 3 mm face, 8 mm total length. "
            "B-type hub with one included M3 SCM435 black-oxide set screw; "
            "do not order a second screw for the same gear. No metal hub insert. "
            "Set-screw length/tip/torque and actual mass remain unverified. "
            "Prefer MISUMI Korea; Korean order acceptance, price and lead time "
            "are not confirmed by the Japanese dimensional catalog."
        ),
    }


def _shaft_dimensions(sku):
    """Decode the verified diameter-3 straight-shaft and one-flat order syntax."""
    match = re.fullmatch(r"PSFU3-(\d+)(?:-FC(\d+)-A(\d+))?", sku)
    if match is None:
        return None
    length = int(match.group(1))
    if not 10 <= length <= 400:
        raise ValueError("PSFU3 standard shaft length must be 10 to 400 mm")
    flat_length = int(match.group(2)) if match.group(2) is not None else None
    offset = int(match.group(3)) if match.group(3) is not None else None
    if flat_length is not None:
        if length < 20:
            raise ValueError("PSFU3 FC alteration requires shaft length at least20mm")
        if not 1 <= flat_length <= 15:
            raise ValueError("PSFU3 FC flat length must be 1 to 15 mm")
        if offset == 1 or offset + flat_length > length:
            raise ValueError("PSFU3 flat offset must be0or≥2mm and fit within shaft")
    return length, flat_length, offset


def procurement_spec(sku):
    """Return a fresh, serializable purchase contract for a modeled CAD SKU."""
    shaft = _shaft_dimensions(sku)
    if shaft is not None:
        length, flat_length, offset = shaft
        flat_requirement = (
            "No flat is included. "
            if flat_length is None
            else (
                f"Factory FC{flat_length}-A{offset} alteration: one0.5mm-deep "
                f"flat, {flat_length}mm long, starting{offset}mm from the reference "
                "end. Clock this flat under the actual gear's radial set screw; "
                "its angle relative to tooth phase is not published. No manual "
                "grinding or substitute plain round shaft. "
            )
        )
        spec = {
            "search_query": f"MISUMI {sku}",
            "candidate_url": SHAFT_SOURCE,
            "requirements": (
                f"MISUMI {sku}: 3 mm h5 x {length} mm straight shaft, "
                "SUJ2-equivalent hardened hard-chrome steel. Diameter 2.996 to "
                "3.000 mm. No shoulder or thread is included. "
                + flat_requirement
                + "This order "
                "does not qualify bearing slip fit, shaft-clamp torque transfer "
                "or gear set-screw retention; verify actual interfaces. Do not "
                "silently substitute unhardened rod or add unmodeled end machining."
            ),
            "evidence_notes": (
                "MISUMI straight-shaft catalog and current product alteration "
                "table: FC and A use1mm increments; D3 flat depth0.5mm, "
                "FC≤15mm, A=0or≥2mm, and altered D3–12 shafts require L≥20mm. "
                "The selected complete order code must be accepted by the supplier. "
                "Catalog: " + SHAFT_CATALOG_SOURCE + ". Retained evidence: "
                "references/misumi_psfu_shaft_catalog.pdf."
            ),
        }
    else:
        spec = dict(PROCUREMENT_SPECS[sku])
    spec["search_url"] = (
        "https://www.aliexpress.com/wholesale?SearchText="
        + quote_plus(spec["search_query"])
    )
    spec.setdefault("candidate_url", "")
    spec.setdefault(
        "evidence_notes",
        "SourceURL supports the nominal dimensions. Verify selected seller "
        "options, material and actual dimensions before purchasing; the "
        "AliExpress URL is a search link, not a verified listing.",
    )
    spec["status"] = PURCHASING_STATUS
    return spec


def add_procurement_properties(obj):
    """Annotate a bought part without altering its geometry or placement.

    Also applies to the rail's independently created clamp parts.
    Unknown future SKUs retain their existing metadata instead of silently
    acquiring an unrelated specification.
    """
    sku = str(obj.HardwareSKU)
    if sku not in PROCUREMENT_SPECS and _shaft_dimensions(sku) is None:
        return obj
    spec = procurement_spec(sku)
    for name, key in (
        ("PurchaseSearchQuery", "search_query"),
        ("PurchaseSearchURL", "search_url"),
        ("PurchaseRequirements", "requirements"),
        ("PurchaseCandidateURL", "candidate_url"),
        ("PurchaseEvidenceNotes", "evidence_notes"),
        ("PurchasingStatus", "status"),
    ):
        set_property(obj, name, spec[key])
    return obj


def hex_prism(across_flats, height, z=0):
    radius = across_flats / math.sqrt(3)
    vertices = [
        V(radius * math.cos(math.pi * i / 3), radius * math.sin(math.pi * i / 3), z)
        for i in range(6)
    ]
    return Part.Face(Part.makePolygon(vertices + [vertices[0]])).extrude(
        V(0, 0, height)
    )


@functools.lru_cache(None)
def screw_shape(length=CLAMP_SCREW_LENGTH):
    # The bearing face is Z0; the head is below it and the shank points +Z.
    head = Part.makeCylinder(
        SCREW_HEAD_DIAMETER / 2, SCREW_HEAD_HEIGHT, V(0, 0, -SCREW_HEAD_HEIGHT)
    )
    shank = Part.makeCylinder(THREAD_DIAMETER / 2, length)
    drive = hex_prism(SOCKET_KEY, SOCKET_DEPTH + 0.1, -SCREW_HEAD_HEIGHT - 0.1)
    return head.fuse(shank).cut(drive).removeSplitter()


@functools.lru_cache(None)
def servo_screw_shape():
    """DIN 84 M1.6x8 stock envelope, under-head plane Z0 and shank along +Z."""
    head = Part.makeCylinder(1.5, 1.0, V(0, 0, -1.0))
    shank = Part.makeCylinder(0.8, 8.0)
    slot = Part.makeBox(4.0, 0.4, 0.45, V(-2.0, -0.2, -1.0))
    return head.fuse(shank).cut(slot).removeSplitter()


@functools.lru_cache(None)
def servo_nut_shape():
    """DIN 934 M1.6 hex nut; nominal geometry omits chamfers and threads."""
    return (
        hex_prism(3.2, 1.3)
        .cut(Part.makeCylinder(0.8, 1.5, V(0, 0, -0.1)))
        .removeSplitter()
    )


@functools.lru_cache(None)
def stack_screw_shape():
    """Bought PA66 screw; cylinder bounds avoid guessing its slot and crown."""
    head = Part.makeCylinder(
        STACK_SCREW_HEAD_DIAMETER / 2,
        STACK_SCREW_HEAD_HEIGHT,
        V(0, 0, -STACK_SCREW_HEAD_HEIGHT),
    )
    shank = Part.makeCylinder(THREAD_DIAMETER / 2, STACK_SCREW_LENGTH)
    return head.fuse(shank).removeSplitter()


@functools.lru_cache(None)
def spacer_shape():
    """Bought HPS2-25 envelope; 4 mm end bores represent reference tap depths."""
    body = hex_prism(STACK_SPACER_AF, STACK_SPACER_LENGTH)
    for start in (0.0, STACK_SPACER_LENGTH - STACK_SPACER_THREAD_DEPTH_REFERENCE):
        body = body.cut(
            Part.makeCylinder(
                THREAD_DIAMETER / 2,
                STACK_SPACER_THREAD_DEPTH_REFERENCE,
                V(0, 0, start),
            )
        )
    return body.removeSplitter()


@functools.lru_cache(None)
def square_nut_shape():
    """The same purchased DIN 562 nut serves every structural nut interface."""
    return (
        Part.makeBox(
            SQUARE_NUT_AF,
            SQUARE_NUT_AF,
            SQUARE_NUT_HEIGHT,
            V(-SQUARE_NUT_AF / 2, -SQUARE_NUT_AF / 2, 0),
        )
        .cut(
            Part.makeCylinder(
                THREAD_DIAMETER / 2, SQUARE_NUT_HEIGHT + 0.2, V(0, 0, -0.1)
            )
        )
        .removeSplitter()
    )


def add_hardware(
    doc,
    parent,
    name,
    label,
    shape,
    sku,
    notes,
    source="",
    material="A2 stainless steel",
    thread_diameter=THREAD_DIAMETER,
    thread_pitch=THREAD_PITCH,
):
    if sku in ("M2_FF_PA66_AF4_L25", "M2X5_PA66_PAN_HEAD") and material != "Nylon PA66":
        raise ValueError("PA66 stack hardware requires explicit Nylon PA66 material.")
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Invalid purchased envelope: " + name)
    obj = doc.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape.copy()
    if parent is not None:
        parent.addObject(obj)
    set_property(obj, "Role", "Purchased mechanism hardware")
    set_property(obj, "PrintPart", False, "App::PropertyBool")
    set_property(
        obj, "ManufacturingRoute", "Purchase separately; never export as a print part"
    )
    set_property(obj, "HardwareSKU", sku)
    set_property(
        obj,
        "ThreadStandard",
        (
            f"ISO metric M{thread_diameter:g} x {thread_pitch:g}; right-hand."
            if thread_diameter is not None
            else "Unthreaded purchased interface; no modeled thread."
        ),
    )
    set_property(
        obj,
        "NominalThreadDiameter",
        thread_diameter or 0.0,
        "App::PropertyLength",
    )
    set_property(
        obj,
        "ThreadPitch",
        thread_pitch if thread_diameter else 0.0,
        "App::PropertyLength",
    )
    set_property(
        obj,
        "ThreadGeometry",
        (
            "Two nominal diameter 2 mm end bores, 4 mm REF deep; usable thread "
            "depth is unmeasured. No helical thread or thread-retention simulation."
            if sku == "M2_FF_PA66_AF4_L25"
            else "Simplified nominal cylinders/bore only; no helical thread or thread-retention simulation"
        ),
    )
    set_property(obj, "MaterialSelection", material)
    set_property(
        obj,
        "ShapeModelNotes",
        "Nominal dimensional envelope only; material selection does not qualify "
        "strength, preload or retention. Helical threads and actual mass are unverified."
        + (
            " PA66 pan-head screw uses a full cylinder for the head; the "
            "undimensioned slot and crown are not generated."
            if sku == "M2X5_PA66_PAN_HEAD"
            else ""
        ),
    )
    set_property(
        obj,
        "PurchasingStatus",
        PURCHASING_STATUS,
    )
    set_property(obj, "SourceURL", source)
    set_property(obj, "Notes", notes)
    set_property(
        obj,
        "CADColorMeaning",
        "Gold denotes purchased hardware; it does not claim the selected part is brass or gold-coloured",
    )
    add_procurement_properties(obj)
    if App.GuiUp:
        obj.ViewObject.ShapeColor = PURCHASED_COLOR
        obj.ViewObject.LineColor = (0.31, 0.22, 0.07)
        obj.ViewObject.DisplayMode = "Flat Lines"
        obj.ViewObject.Visibility = True
    return obj
