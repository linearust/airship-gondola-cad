"""Purchased KST horn and two printed clamp halves for its 3 mm input axle.

Local rotation axis is +Y; horn bottom is Y=0 and its blade points +X. The
published horn profile is conservatively reconstructed from its two end circles
and straight tangents. It is not a precision manufacturer CAD model. Assembly
seating, closure and torque retention remain fit-prototype qualification gates.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import box, union
from gondola.contracts.equipment_interfaces import HORN_DRAWING_SOURCE, HORN_SOURCE

V = App.Vector
HORN_SKU = "KST_0415_13"
HORN_MATERIAL = "Aluminium alloy (grade unspecified)"
HORN_HEIGHT = 3.5
HORN_BLADE_THICKNESS = 1.6
HORN_HUB_RADIUS = 3.0
HORN_TIP_RADIUS = 2.0
HORN_TIP_CENTRE = 13.2
HORN_SPLINE_RECESS_DEPTH = 2.5
HORN_BLADE_BOTTOM = HORN_HEIGHT - HORN_BLADE_THICKNESS
FIT_CLEARANCE = 0.2
SPLIT_GAP = 0.6
SHAFT_RADIUS = 1.5
SHAFT_START_Y = 7.3
CLAMP_END_Y = 14.8
BOLT_POSITIONS = ((10.4, 7.4), (4.5, 11.1))
SCREW_SEAT_Z = 3.1
NUT_SEAT_Z = -3.1
OUTER_HALF_WIDTH = 4.5


def _cylinder(radius, length, origin, direction=(0, 1, 0)):
    return Part.makeCylinder(radius, length, V(*origin), V(*direction))


def _blade_hull(y, depth, clearance=0.0):
    """Convex envelope of dimensioned root/tip circles; clearance is our choice."""
    root = HORN_HUB_RADIUS + clearance
    tip = HORN_TIP_RADIUS + clearance
    cosine = (root - tip) / HORN_TIP_CENTRE
    sine = math.sqrt(1 - cosine**2)
    a = V(root * cosine, y, root * sine)
    b = V(HORN_TIP_CENTRE + tip * cosine, y, tip * sine)
    c = V(b.x, y, -b.z)
    d = V(a.x, y, -a.z)
    edges = [
        Part.makeLine(a, b),
        Part.Arc(b, V(HORN_TIP_CENTRE + tip, y, 0), c).toShape(),
        Part.makeLine(c, d),
        Part.Arc(d, V(-root, y, 0), a).toShape(),
    ]
    return Part.Face(Part.Wire(edges)).extrude(V(0, depth, 0))


def horn_shape():
    """Bought horn envelope with published holes; spline is a smooth bore."""
    shape = union(
        [
            _cylinder(HORN_HUB_RADIUS, HORN_HEIGHT, (0, 0, 0)),
            _blade_hull(HORN_BLADE_BOTTOM, HORN_BLADE_THICKNESS),
        ]
    )
    for radius, start, depth in (
        (1.95, -0.1, HORN_SPLINE_RECESS_DEPTH + 0.1),
        (1.1, HORN_SPLINE_RECESS_DEPTH, 0.5),
        (2.2, 3.0, 0.6),
    ):
        shape = shape.cut(_cylinder(radius, depth, (0, start, 0)))
    for radius, positions in (
        (0.4, (4.5, 8.0, 11.5)),
        (0.5, (6.8, 10.0, 13.2)),
    ):
        for x in positions:
            shape = shape.cut(_cylinder(radius, 2.0, (x, 1.7, 0)))
    return shape.removeSplitter()


def adapter_half_shapes():
    """Return lower nut half and upper screw half, in the unclosed assembly pose.

    Both halves can be fitted around an already screwed-down horn. Two common
    M2 clamps close the side clearance around its blade and the independent
    steel shaft. Axial assembly clearance avoids preloading the servo spline.
    """
    shape = union(
        [
            box(13.3, 9.45, 9.0, (3.7, 1.65, -OUTER_HALF_WIDTH)),
            box(20.2, 3.5, 6.4, (-3.2, 5.5, -3.2)),
            _cylinder(3.2, CLAMP_END_Y - SHAFT_START_Y, (0, SHAFT_START_Y, 0)),
            box(7.4, 7.4, 9.0, (0.8, 7.4, -OUTER_HALF_WIDTH)),
        ]
    )
    shape = shape.cut(
        _blade_hull(
            -0.1,
            HORN_HEIGHT + FIT_CLEARANCE + 0.1,
            FIT_CLEARANCE,
        )
    )
    # Open centre lets the two halves surround a previously retained horn.
    # The original horn screw is serviced after removing this separable clamp;
    # no invented screw, centre thread or tool path through the solid shaft.
    shape = shape.cut(_cylinder(2.5, SHAFT_START_Y + 0.1, (0, -0.1, 0)))
    shape = shape.cut(
        _cylinder(SHAFT_RADIUS + FIT_CLEARANCE, 9.0, (0, SHAFT_START_Y - 0.1, 0))
    )
    for x, y in BOLT_POSITIONS:
        shape = shape.cut(_cylinder(1.15, 12, (x, y, -6), (0, 0, 1)))
        shape = shape.cut(_cylinder(2.05, 3.0, (x, y, SCREW_SEAT_Z), (0, 0, 1)))
        shape = shape.cut(box(4.3, 4.3, 3, (x - 2.15, y - 2.15, NUT_SEAT_Z - 3)))
    lower = shape.common(box(50, 30, 10, (-10, -1, -10 - SPLIT_GAP / 2)))
    upper = shape.common(box(50, 30, 10, (-10, -1, SPLIT_GAP / 2)))
    halves = tuple(part.removeSplitter() for part in (lower, upper))
    for half in halves:
        if not half.isValid() or len(half.Solids) != 1:
            raise RuntimeError("Horn/shaft clamp half must be one valid solid")
    return halves


def fastener_positions():
    """Under-head and inner nut bearing positions; both fasteners point -Z."""
    return tuple(
        {"screw": (x, y, SCREW_SEAT_Z), "nut": (x, y, NUT_SEAT_Z)}
        for x, y in BOLT_POSITIONS
    )


def metrics():
    return {
        "horn_sku": HORN_SKU,
        "sources": [HORN_SOURCE, HORN_DRAWING_SOURCE],
        "retained_evidence": "references/kst_0415_13_horn_dimensions.png",
        "horn_shape_scope": "KST-authored drawing via distributor. Conservative tangent hull, smooth spline bore and nominal holes; exact fillets, spline teeth, material grade and measured mass are not claimed.",
        "shaft_grip_length_mm": CLAMP_END_Y - SHAFT_START_Y,
        "fit_clearance_each_side_mm": FIT_CLEARANCE,
        "unclosed_split_gap_mm": SPLIT_GAP,
        "common_clamp_fasteners_per_side": 2,
        "assembly": "Install and retain the stock horn using its original servo screw first. Assemble the two printed halves around the horn blade and the separately supported 3mm axle. Slide the axle to avoid axial preload, tighten the two M2 clamps minimally and verify engagement before locking the remaining shaft retention. Remove the separable coupling to service the OEM horn screw.",
        "qualification": "Measured horn seating, screw head, purchased shaft fit, clamp closure, torsional play, creep and loaded bidirectional torque remain required. The printed shape supplies a complete nominal torque path, not qualified transmission performance.",
    }
