"""Direct stock-horn adapter for a purchased 7 mm-bore driver gear.

The gear runs on the servo output through its bought KST horn. Two simple PA12
parts sandwich that horn without drilling it; a single M2 screw sits beyond the
horn tip. The main part carries an integral hollow spigot, with no extra axle or
input bearing. Local rotation axis is +Y and the horn blade points +X.
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
HORN_BOTTOM_Y = 30.9
HORN_REGISTER_CLEARANCE = 0.05
GEAR_BORE_DIAMETER = 7.0
SPIGOT_DIAMETER = 6.9
SPIGOT_BORE_DIAMETER = 3.0
SPIGOT_START_Y = 7.1
SPIGOT_LENGTH = 8.0
RETAINER_BACK_Y = 0.4
RETAINER_THICKNESS = 1.5
BODY_BACK_Y = 2.2
BOLT_X = 18.0
NUT_SEAT_Y = 6.1
BOLT_DIRECTION = (0, 1, 0)


def _cylinder(radius, length, origin, direction=(0, 1, 0)):
    return Part.makeCylinder(radius, length, V(*origin), V(*direction))


def _tangent_hull(y, depth, root, tip, tip_centre):
    """Extrude two circular ends and their common external tangents."""
    cosine = (root - tip) / tip_centre
    sine = math.sqrt(1 - cosine**2)
    a = V(root * cosine, y, root * sine)
    b = V(tip_centre + tip * cosine, y, tip * sine)
    c = V(b.x, y, -b.z)
    d = V(a.x, y, -a.z)
    edges = [
        Part.makeLine(a, b),
        Part.Arc(b, V(tip_centre + tip, y, 0), c).toShape(),
        Part.makeLine(c, d),
        Part.Arc(d, V(-root, y, 0), a).toShape(),
    ]
    return Part.Face(Part.Wire(edges)).extrude(V(0, depth, 0))


def _blade_hull(y, depth, clearance=0.0):
    return _tangent_hull(
        y,
        depth,
        HORN_HUB_RADIUS + clearance,
        HORN_TIP_RADIUS + clearance,
        HORN_TIP_CENTRE,
    )


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


def adapter_shape():
    """Open horn socket, front plate and integral gear spigot as one solid.

    The shallow socket can approach an already retained horn axially. Its hub
    and blade pocket share the same small nominal finishing allowance;
    neither the spline nor new holes in the bought horn are fabricated. The
    bore supplies powder escape, not a claimed OEM screw/tool interface.
    """
    shape = union(
        [
            _tangent_hull(BODY_BACK_Y, SPIGOT_START_Y - BODY_BACK_Y, 4.7, 4.0, BOLT_X),
            _cylinder(SPIGOT_DIAMETER / 2, SPIGOT_LENGTH, (0, SPIGOT_START_Y, 0)),
        ]
    )
    shape = shape.cut(_blade_hull(0.3, HORN_HEIGHT - 0.3, HORN_REGISTER_CLEARANCE))
    # Clearance around an installed original screw head is deliberately a
    # prototype envelope. Remove the adapter for service; its small through-bore
    # is not assumed to pass that unmeasured head or a particular driver bit.
    shape = shape.cut(_cylinder(2.5, 5.3, (0, -0.1, 0)))
    shape = shape.cut(_cylinder(SPIGOT_BORE_DIAMETER / 2, 16.0, (0, -0.1, 0)))
    shape = shape.cut(_cylinder(1.1, 10.0, (BOLT_X, -0.1, 0)))
    shape = shape.cut(box(4.3, 3.0, 4.3, (BOLT_X - 2.15, NUT_SEAT_Y, -2.15)))
    return _one_solid(shape, "Direct horn gear adapter")


def retainer_shape():
    """Flat rear strap retained by one screw beyond the existing horn tip."""
    shape = union(
        [
            box(BOLT_X - 5.0, RETAINER_THICKNESS, 8.0, (5.0, RETAINER_BACK_Y, -4.0)),
            _cylinder(4.0, RETAINER_THICKNESS, (BOLT_X, RETAINER_BACK_Y, 0)),
        ]
    )
    shape = shape.cut(_cylinder(1.1, 2.0, (BOLT_X, 0.3, 0)))
    return _one_solid(shape, "Direct horn rear retainer")


def _one_solid(shape, name):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError(name + " must be one valid solid")
    return shape


def fastener_positions():
    """Under-head and inner nut bearing positions; the stock M2 screw faces +Y."""
    return ({"screw": (BOLT_X, RETAINER_BACK_Y, 0), "nut": (BOLT_X, NUT_SEAT_Y, 0)},)


def metrics():
    return {
        "horn_sku": HORN_SKU,
        "sources": [HORN_SOURCE, HORN_DRAWING_SOURCE],
        "retained_evidence": "references/kst_0415_13_horn_dimensions.png",
        "horn_shape_scope": "KST-authored drawing via distributor. Conservative tangent hull, smooth spline bore and nominal holes; exact fillets, spline teeth, material grade and measured mass are not claimed.",
        "gear_bore_diameter_mm": GEAR_BORE_DIAMETER,
        "integral_spigot_diameter_mm": SPIGOT_DIAMETER,
        "integral_spigot_bore_diameter_mm": SPIGOT_BORE_DIAMETER,
        "integral_spigot_length_mm": SPIGOT_LENGTH,
        "horn_register_clearance_each_side_mm": HORN_REGISTER_CLEARANCE,
        "horn_socket_engagement_mm": HORN_HEIGHT - BODY_BACK_Y,
        "retainer_thickness_mm": RETAINER_THICKNESS,
        "retainer_closure_gap_mm": BODY_BACK_Y - HORN_BLADE_BOTTOM,
        "common_clamp_fasteners_per_side": 1,
        "assembly": "At neutral with power disconnected and leads freed, release the output gear's supplied set screw and withdraw the small gear inboard. Remove the adapter clamp screw/nut and slide the rear retainer outward. Move the adapter and large gear together 1.5 mm toward the gear side, then 40 mm sideways outward. Both output shafts, bearings and caps remain installed. Remove the servo ear fasteners, then move the servo with its retained stock horn 12.5 mm toward the gear side and 40 mm outward. Service the large gear and adapter on the bench. Reverse this order for assembly; the OEM horn retaining screw must be installed before the adapter. Re-establish neutral and tooth phasing, and clock the output shaft flat toward the gear set screw before tightening. Final set-screw access, wire handling and fits require actual parts.",
        "qualification": "The 0.05 mm radial pocket and gear fit are nominal finish-fit targets, not as-printed tolerance claims. The 1.3 mm shallow hub/blade engagement preserves the blade torque interface but shortens the former hub register: verify concentricity, rocking, clamp closure and loaded alignment. The annular material ahead of the provisional OEM screw-head cavity is 1.9 mm; measure the actual head and check stiffness, PA12 spigot retention/creep and bidirectional motion. The direct gear adds unqualified radial load to the servo output; no external radial-load rating is published.",
    }
