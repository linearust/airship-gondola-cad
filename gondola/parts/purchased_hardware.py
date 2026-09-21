"""Purchased mechanism hardware, modeled as simple dimensional envelopes.

No modeled helical threads, no custom printed fasteners. The exact procurement
item remains unselected; the cited manufacturers substantiate the purchasing
geometry, not a tested marketplace SKU. All objects are excluded from STL lists.
"""

import functools
import math
from functools import partial

import FreeCAD as App
import Part

from gondola.cad import set_property as _set_property
from gondola.contracts import hardware as hardware_contract
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
STACK_SCREW_LENGTH = 5.0
STACK_SCREW_HEAD_DIAMETER = 4.0
STACK_SCREW_HEAD_HEIGHT = 1.3
STACK_SPACER_AF = 4.0
STACK_SPACER_LENGTH = 25.0
STACK_SPACER_THREAD_DEPTH_REFERENCE = 4.0


def add_procurement_properties(obj):
    """Annotate a bought part without altering its geometry or placement.

    Also applies to the rail's independently created clamp parts.
    Unknown future SKUs retain their existing metadata instead of silently
    acquiring an unrelated specification.
    """
    sku = str(obj.HardwareSKU)
    spec = hardware_contract.procurement_spec(sku, allow_unknown=True)
    if spec is None:
        return obj
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
        hardware_contract.PURCHASING_STATUS,
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
