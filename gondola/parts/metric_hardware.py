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
from .fastener_spec import NUT_AF as NUT_AF
from .fastener_spec import NUT_HEIGHT as NUT_HEIGHT
from .fastener_spec import SCREW_HEAD_DIAMETER as SCREW_HEAD_DIAMETER
from .fastener_spec import SCREW_HEAD_HEIGHT as SCREW_HEAD_HEIGHT
from .fastener_spec import SET_SCREW_KEY as SET_SCREW_KEY
from .fastener_spec import SET_SCREW_LENGTH as SET_SCREW_LENGTH
from .fastener_spec import SOCKET_DEPTH as SOCKET_DEPTH
from .fastener_spec import SOCKET_KEY as SOCKET_KEY
from .fastener_spec import SQUARE_NUT_AF as SQUARE_NUT_AF
from .fastener_spec import SQUARE_NUT_HEIGHT as SQUARE_NUT_HEIGHT
from .fastener_spec import SQUARE_NUT_MIN_AF as SQUARE_NUT_MIN_AF
from .fastener_spec import SQUARE_NUT_MIN_HEIGHT as SQUARE_NUT_MIN_HEIGHT
from .fastener_spec import THREAD_DIAMETER as THREAD_DIAMETER
from .fastener_spec import THREAD_PITCH as THREAD_PITCH
from .fastener_spec import WASHER_ID as WASHER_ID
from .fastener_spec import WASHER_OD as WASHER_OD
from .fastener_spec import WASHER_THICKNESS as WASHER_THICKNESS

set_property = partial(_set_property, group="Purchased hardware")

V = App.Vector
PURCHASED_COLOR = (0.86, 0.67, 0.27)
WASHER_SOURCE = (
    "https://www.orbitalfasteners.co.uk/products/"
    "m2-form-a-flat-washer-stainless-steel-a2-304-din-125-2-2x5-0x0-3mm-"
)
JOURNAL_SCREW_SOURCE = (
    "https://www.accu.co.uk/metric-cap-head-screws/3796-SSCF-M2-14-A2"
)
NUT_SOURCE = "https://www.accu.co.uk/hexagon-nuts/7884-HPN-M2-A2"
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
            "head height 2 mm and 1.5 mm hex key. Retains the printed sleeve; "
            "it is not a substitute for an unspecified OEM motor or horn screw."
        ),
    },
    "M2x6_ISO4026_DIN913": {
        "search_query": "M2x6 DIN913 flat point stainless set screw",
        "requirements": (
            "A2 stainless steel, M2 x 0.4 right-hand, 6 mm overall length. "
            "DIN 913 / ISO 4026 flat-point set screw with 0.9 mm hex key. "
            "Do not substitute a cup point or cone point. One screw/nut pair "
            "per bottom module; the unused opposite clamp port stays empty."
        ),
    },
    "M2_HEX_NUT": {
        "search_query": "M2 DIN934 A2 hex nut 4 1.6",
        "requirements": (
            "A2 stainless steel, DIN 934 M2 x 0.4 right-hand hex nut; nominal "
            "across flats 4 mm and height 1.6 mm. Four nuts for journal retention; rail clamps require separate DIN 562 square nuts. Confirm these dimensions "
            "rather than substituting on an ISO 4032 label alone."
        ),
    },
    "M2_SQUARE_NUT_DIN562": {
        "search_query": "M2 DIN562 A2 flat square nut 4 1.2",
        "requirements": (
            "A2 stainless steel, DIN 562 M2 x 0.4 right-hand flat square nut. "
            "Nominal width 4 mm and height 1.2 mm; accepted width 3.6-4.0 mm "
            "and height 0.8-1.2 mm. Three rail clamps only. Preserve square "
            "corners for anti-rotation; verify actual corner form and captive "
            "fit with the printed coupon. Do not substitute a hex nut."
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
    "M2_WASHER_2.2_5_0.3": {
        "search_query": "M2 stainless washer 2.2 5 0.3",
        "requirements": (
            "A2 stainless steel flat washer, unthreaded; nominal bore 2.2 mm, "
            "outside diameter 5 mm and thickness 0.3 mm. Used for journal retention."
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
def nut_shape():
    return (
        hex_prism(NUT_AF, NUT_HEIGHT)
        .cut(Part.makeCylinder(THREAD_DIAMETER / 2, NUT_HEIGHT + 0.2, V(0, 0, -0.1)))
        .removeSplitter()
    )


@functools.lru_cache(None)
def washer_shape():
    return (
        Part.makeCylinder(WASHER_OD / 2, WASHER_THICKNESS)
        .cut(Part.makeCylinder(WASHER_ID / 2, WASHER_THICKNESS + 0.2, V(0, 0, -0.1)))
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
        "ISO metric coarse M2 x 0.4; right-hand. Washer is unthreaded.",
    )
    set_property(obj, "NominalThreadDiameter", THREAD_DIAMETER, "App::PropertyLength")
    set_property(obj, "ThreadPitch", THREAD_PITCH, "App::PropertyLength")
    set_property(
        obj,
        "ThreadGeometry",
        "Simplified nominal cylinders/bore only; no helical thread or thread-retention simulation",
    )
    set_property(obj, "MaterialSelection", material)
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
