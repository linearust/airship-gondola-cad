"""Shared FreeCAD geometry, object metadata and coordinate conventions.

Shape builders use millimetres in a part's local frame. Assembly export uses
``world_shape``; print export deliberately ignores the assembly placement.
"""

import math

import FreeCAD as App
import Part


def set_property(obj, name, value, kind="App::PropertyString", group="Design"):
    """Create or update an inspectable native FreeCAD property."""
    if name not in obj.PropertiesList:
        obj.addProperty(kind, name, group)
    setattr(obj, name, value)


def create_group(doc, name, label):
    """Create an assembly container whose placement moves its children."""
    obj = doc.addObject("App::Part", name)
    obj.Label = label
    return obj


def world_shape(obj):
    """Copy a feature with its complete parent-to-world placement applied once."""
    shape = obj.Shape.copy()
    shape.Placement = obj.getGlobalPlacement()
    return shape


def box(dx, dy, dz, origin):
    return Part.makeBox(dx, dy, dz, App.Vector(*origin))


def union(shapes):
    """Fuse the supplied solids and remove internal split edges."""
    return (
        shapes[0].multiFuse(shapes[1:]).removeSplitter()
        if len(shapes) > 1
        else shapes[0]
    )


def polygon_extrusion(points, vector):
    vertices = [App.Vector(*point) for point in points]
    face = Part.Face(Part.makePolygon(vertices + [vertices[0]]))
    return face.extrude(App.Vector(*vector))


def mirrored_y(shape, sign):
    """Use the canonical +Y part, or reflect it through the XZ plane."""
    return shape.mirror(App.Vector(), App.Vector(0, 1, 0)) if sign < 0 else shape


def create_printed_part(doc, parent, name, label, shape, rotation, notes):
    """Create one printed solid with explicit local-to-print orientation.

    PrintPlacement is the native FreeCAD preview placement. The export path
    computes exact trimmed bounds separately; this preserves the saved design's
    existing orientation metadata and does not change assembly geometry.
    """
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Not one valid printed solid: " + name)
    obj = doc.addObject("Part::Feature", name)
    obj.Label, obj.Shape = label, shape
    parent.addObject(obj)
    set_property(obj, "Role", "Printed fit prototype")
    set_property(obj, "Notes", notes)
    set_property(obj, "PrintNotes", notes, group="Printing")
    set_property(obj, "PrintRotation", rotation, "App::PropertyRotation", "Printing")
    transformed = shape.copy()
    transformed.rotate(App.Vector(), rotation.Axis, math.degrees(rotation.Angle))
    bounds = transformed.BoundBox
    placement = App.Placement(
        App.Vector(-bounds.XMin, -bounds.YMin, -bounds.ZMin), rotation
    )
    set_property(obj, "PrintPlacement", placement, "App::PropertyPlacement", "Printing")
    if App.GuiUp:
        obj.ViewObject.ShapeColor = (0.39, 0.70, 0.77)
        obj.ViewObject.LineColor = (0.12, 0.20, 0.24)
        obj.ViewObject.DisplayMode = "Flat Lines"
    return obj


def update_print_orientation(obj, rotation=None):
    """Refresh propulsion orientation metadata after replacing its local shape.

    Replacing Shape.Placement rather than composing it is intentional: these
    parts are expressed in their journal frame before the assembly moves them.
    """
    rotation = rotation or obj.PrintRotation
    bed = obj.Shape.copy()
    bed.Placement = App.Placement(App.Vector(), rotation)
    bounds = bed.BoundBox
    obj.PrintRotation = rotation
    obj.PrintPlacement = App.Placement(
        App.Vector(-bounds.XMin, -bounds.YMin, -bounds.ZMin), rotation
    )
    set_property(obj, "PrintHeight", bounds.ZLength, "App::PropertyLength", "Printing")
    if not obj.Shape.isValid() or len(obj.Shape.Solids) != 1:
        raise RuntimeError("Invalid propulsion part: " + obj.Name)


def set_print_category(objects, label):
    for obj in objects:
        set_property(obj, "PrintCategory", label, group="Printing")


def create_reference(doc, parent, name, label, shape, notes, source=""):
    """Equipment envelopes remain separate from printable geometry."""
    obj = doc.addObject("Part::Feature", name)
    parent.addObject(obj)
    obj.Label = "REFERENCE | " + label
    obj.Shape = shape
    set_property(obj, "Role", "Purchased equipment envelope; not a printable part")
    set_property(obj, "Notes", notes)
    set_property(obj, "SourceURL", source)
    return obj


def set_print_sku(obj, sku):
    set_property(obj, "PrintSKU", sku, group="Printing")


def translated_shape(shape, x=0, y=0, z=0):
    """Return a translated copy without mutating cached source geometry."""
    result = shape.copy()
    result.translate(App.Vector(x, y, z))
    return result
