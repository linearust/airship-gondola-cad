"""Shared square plate geometry, holes and carrier support heights.

Equipment carriers and the optional power deck use this same plate template;
their distinct supports and installation contracts belong to their own modules.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import box
from gondola.contracts.equipment_interfaces import FC_HOLE_PITCH

from . import mounting_slots

V = App.Vector
SIZE_MM = (64.0, 64.0)
THICKNESS_MM = 2.0
CORNER_RADIUS_MM = 3.0
CARRIER_BOTTOM_Z = 15.0
CARRIER_SUPPORT_Z = CARRIER_BOTTOM_Z + THICKNESS_MM
FIXED_HOLE_DIAMETER_MM = 2.6
FC_PAD_DIAMETER_MM = 6.5
_FC_AXIS_OFFSET = FC_HOLE_PITCH / math.sqrt(2)
FC_HOLE_CENTRES = (
    (-_FC_AXIS_OFFSET, 0.0),
    (0.0, -_FC_AXIS_OFFSET),
    (0.0, _FC_AXIS_OFFSET),
    (_FC_AXIS_OFFSET, 0.0),
)
CENTRE_HOLE_DIAMETER_MM = 2.6
FIXED_HOLE_CENTRES = (*FC_HOLE_CENTRES, (0.0, 0.0))


def cutters(bottom, depth):
    """Five M2 bores and the shared slot array."""
    return (
        [
            Part.makeCylinder(FIXED_HOLE_DIAMETER_MM / 2, depth, V(x, y, bottom))
            for x, y in FC_HOLE_CENTRES
        ]
        + [Part.makeCylinder(CENTRE_HOLE_DIAMETER_MM / 2, depth, V(0, 0, bottom))]
        + mounting_slots.shapes(bottom, depth)
    )


def shape(bottom=CARRIER_BOTTOM_Z):
    """A fresh plate before attached supports can mask a broken web."""
    length, width = SIZE_MM
    plate = box(length, width, THICKNESS_MM, (-length / 2, -width / 2, bottom))
    vertical_edges = [
        edge for edge in plate.Edges if edge.BoundBox.ZLength > THICKNESS_MM - 0.01
    ]
    plate = plate.makeFillet(CORNER_RADIUS_MM, vertical_edges)
    for hole in cutters(bottom - 1, THICKNESS_MM + 2):
        plate = plate.cut(hole)
    plate = plate.removeSplitter()
    if not plate.isValid() or len(plate.Solids) != 1:
        raise RuntimeError("Common mounting plate must be one valid solid")
    return plate
