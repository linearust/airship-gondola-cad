"""Purchased M2 mechanism hardware, modeled as simple dimensional envelopes.

No modeled helical threads, no custom printed fasteners. The exact procurement
item remains unselected; the cited manufacturers substantiate the purchasing
geometry, not a tested marketplace SKU. All objects are excluded from STL lists.
"""

import functools
import math
from functools import partial
from urllib.parse import quote_plus

import FreeCAD as App
import Part

from gondola.cad import set_property as _set_property

from .fastener_spec import JOURNAL_SCREW_LENGTH as JOURNAL_SCREW_LENGTH
from .fastener_spec import SCREW_HEAD_DIAMETER as SCREW_HEAD_DIAMETER
from .fastener_spec import SCREW_HEAD_HEIGHT as SCREW_HEAD_HEIGHT
from .fastener_spec import SOCKET_DEPTH as SOCKET_DEPTH
from .fastener_spec import SOCKET_KEY as SOCKET_KEY
from .fastener_spec import SQUARE_NUT_AF as SQUARE_NUT_AF
from .fastener_spec import SQUARE_NUT_HEIGHT as SQUARE_NUT_HEIGHT
from .fastener_spec import THREAD_DIAMETER as THREAD_DIAMETER
from .fastener_spec import THREAD_PITCH as THREAD_PITCH

set_property = partial(_set_property, group="Purchased hardware")

V = App.Vector
PURCHASED_COLOR = (0.86, 0.67, 0.27)
JOURNAL_SCREW_SOURCE = (
    "https://www.accu.co.uk/metric-cap-head-screws/3796-SSCF-M2-14-A2"
)
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
    "M2X14_SOCKET_CAP": {
        "search_query": "M2x14 DIN912 A2 socket cap screw",
        "requirements": (
            "A2 stainless steel, M2 x 0.4 right-hand, 14 mm under-head length. "
            "DIN 912 / ISO 4762 socket cap shape; nominal head diameter 3.8 mm, "
            "head height 2 mm and 1.5 mm hex key. Bears directly on the printed sleeve flange; "
            "one DIN 562 square nut bears directly on the integral 1.5 mm carrier cap. "
            "No washers. Nominal nut-side projection is 2.35 mm. Use minimal "
            "preload and check actual retention; this is not an OEM motor or horn screw."
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
            "and height 0.8-1.2 mm. Shared by three rail clamps, four propulsion "
            "journals and two optical pivots. No washers. Preserve square "
            "corners for rail anti-rotation; verify actual corner form and captive "
            "fit with the printed coupon. Exposed journal and pivot nuts require "
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


def procurement_spec(sku):
    """Return a fresh, serializable purchase contract for a modeled CAD SKU."""
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
    if sku not in PROCUREMENT_SPECS:
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
def screw_shape(length=JOURNAL_SCREW_LENGTH):
    # The bearing face is Z0; the head is below it and the shank points +Z.
    head = Part.makeCylinder(
        SCREW_HEAD_DIAMETER / 2, SCREW_HEAD_HEIGHT, V(0, 0, -SCREW_HEAD_HEIGHT)
    )
    shank = Part.makeCylinder(THREAD_DIAMETER / 2, length)
    drive = hex_prism(SOCKET_KEY, SOCKET_DEPTH + 0.1, -SCREW_HEAD_HEIGHT - 0.1)
    return head.fuse(shank).cut(drive).removeSplitter()


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
    set_property(obj, "Role", "Purchased metric hardware")
    set_property(obj, "PrintPart", False, "App::PropertyBool")
    set_property(
        obj, "ManufacturingRoute", "Purchase separately; never export as a print part"
    )
    set_property(obj, "HardwareSKU", sku)
    set_property(
        obj,
        "ThreadStandard",
        "ISO metric coarse M2 x 0.4; right-hand.",
    )
    set_property(
        obj,
        "NominalThreadDiameter",
        THREAD_DIAMETER,
        "App::PropertyLength",
    )
    set_property(obj, "ThreadPitch", THREAD_PITCH, "App::PropertyLength")
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
