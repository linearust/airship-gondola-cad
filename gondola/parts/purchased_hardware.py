"""Purchased mechanism hardware, modeled as simple dimensional envelopes.

No modeled helical threads or custom printed fasteners. Purchase contracts
distinguish selected cart options from dimensional references; received-part
fit remains unverified. All objects are excluded from STL lists.
"""

import functools
import math
from functools import partial

import FreeCAD as App
import Part

from gondola.cad import set_property as _set_property
from gondola.contracts import fasteners
from gondola.contracts import hardware as hardware_contract
from gondola.contracts.fasteners import CLAMP_SCREW_LENGTH as CLAMP_SCREW_LENGTH
from gondola.contracts.fasteners import HEX_NUT_AF as HEX_NUT_AF
from gondola.contracts.fasteners import HEX_NUT_HEIGHT as HEX_NUT_HEIGHT
from gondola.contracts.fasteners import SCREW_HEAD_DIAMETER as SCREW_HEAD_DIAMETER
from gondola.contracts.fasteners import SCREW_HEAD_HEIGHT as SCREW_HEAD_HEIGHT
from gondola.contracts.fasteners import THREAD_DIAMETER as THREAD_DIAMETER
from gondola.contracts.fasteners import THREAD_PITCH as THREAD_PITCH

set_property = partial(_set_property, group="Purchased hardware")

V = App.Vector
PURCHASED_COLOR = (0.86, 0.67, 0.27)


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
    for key, name, _ in hardware_contract.PROCUREMENT_FIELDS:
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
    # The bearing face is Z0; the head is a design envelope below that plane.
    # No socket recess is invented: the selected kit supplies a 1.5 mm key but
    # does not document socket depth or the button-head profile.
    head = Part.makeCylinder(
        SCREW_HEAD_DIAMETER / 2, SCREW_HEAD_HEIGHT, V(0, 0, -SCREW_HEAD_HEIGHT)
    )
    shank = Part.makeCylinder(THREAD_DIAMETER / 2, length)
    return head.fuse(shank).removeSplitter()


@functools.lru_cache(None)
def servo_screw_shape():
    """M1.6 kit head acceptance envelope; actual Phillips recess is unmodeled."""
    head = Part.makeCylinder(
        fasteners.SERVO_SCREW_HEAD_DIAMETER / 2,
        fasteners.SERVO_SCREW_HEAD_HEIGHT,
        V(0, 0, -fasteners.SERVO_SCREW_HEAD_HEIGHT),
    )
    shank = Part.makeCylinder(0.8, fasteners.SERVO_SCREW_LENGTH)
    return head.fuse(shank).removeSplitter()


@functools.lru_cache(None)
def servo_nut_shape():
    """DIN 934 M1.6 hex nut; nominal geometry omits chamfers and threads."""
    return (
        hex_prism(3.2, 1.3)
        .cut(Part.makeCylinder(0.8, 1.5, V(0, 0, -0.1)))
        .removeSplitter()
    )


@functools.lru_cache(None)
def hex_nut_shape():
    """Accepted M2 kit hex-nut envelope; chamfers and threads are unmeasured."""
    return (
        hex_prism(HEX_NUT_AF, HEX_NUT_HEIGHT)
        .cut(
            Part.makeCylinder(THREAD_DIAMETER / 2, HEX_NUT_HEIGHT + 0.2, V(0, 0, -0.1))
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
        "Simplified nominal cylinders/bore only; no helical thread or thread-retention simulation",
    )
    set_property(obj, "MaterialSelection", material)
    set_property(
        obj,
        "ShapeModelNotes",
        "Nominal dimensional envelope only; material selection does not qualify "
        "strength, preload or retention. Helical threads and actual mass are unverified."
        + (" " + fasteners.HEAD_ENVELOPE_NOTE if sku.endswith("_BUTTON_HEAD") else ""),
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
