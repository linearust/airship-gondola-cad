"""Captured stock horn driving a bought Ø3-bore gear through a short metal stub.

The gear runs on the servo output through its bought KST horn. Two simple PA12
parts sandwich that horn without drilling it; a single M2 screw sits beyond the
horn tip. A locally cut and flattened Ø3 aluminium stub seats in a finished
D-shaped socket. One radial M2 screw and captive hex nut retain the stub; the
gear uses an M3 set screw whose supply and exact geometry remain unverified. No printed journal enters the gear bore and
no external input bearing is added. Local rotation is +Y; the horn points +X.
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
HORN_BLADE_CLEARANCE = 0.25
HORN_TIP_CLEARANCE = HORN_REGISTER_CLEARANCE
ADAPTER_RELEASE_TRAVEL = 1.5
GEAR_BORE_DIAMETER = 3.0
SHAFT_DIAMETER = 3.0
SHAFT_START_Y = 7.1
SHAFT_LENGTH = 16.0
SHAFT_FLAT_DEPTH = 0.5
SHAFT_SOCKET_LENGTH = 8.0
SHAFT_SOCKET_CLEARANCE = 0.05
GEAR_START_Y = SHAFT_START_Y + SHAFT_SOCKET_LENGTH
GEAR_LENGTH = 8.0
SHAFT_CLAMP_Y = SHAFT_START_Y + SHAFT_SOCKET_LENGTH / 2
SHAFT_SCREW_LENGTH = 6.0
SHAFT_SCREW_HEAD_X = 7.0
SHAFT_NUT_SEAT_X = 5.0
SHAFT_BOLT_DIRECTION = (-1, 0, 0)
NUT_POCKET_AF = 4.2
SHAFT_NUT_POCKET_LENGTH = 1.8
SHAFT_BOSS_END_X = 6.5
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


def _horn_pocket():
    """Straight flank relief between the root register and flat tip datum.

    The channel clears the horn's two broad torque flanks. Its flat end locates
    the horn tip, without requiring a matching curved tip outline. The root
    circle is open toward the blade: this opposing tip stop remains essential
    for concentricity and cannot simply be given more longitudinal clearance.
    Clamp preload carries nominal torque; the relieved flanks limit gross slip
    but do not promise zero backlash or a qualified holding torque.
    """
    root = HORN_HUB_RADIUS + HORN_REGISTER_CLEARANCE
    relieved_tip = HORN_TIP_RADIUS + HORN_BLADE_CLEARANCE
    cosine = (root - relieved_tip) / HORN_TIP_CENTRE
    sine = math.sqrt(1 - cosine**2)
    end_x = HORN_TIP_CENTRE + HORN_TIP_RADIUS + HORN_TIP_CLEARANCE
    a = V(root * cosine, 0.3, root * sine)
    b = V(end_x, 0.3, (root - end_x * cosine) / sine)
    c, d = V(b.x, b.y, -b.z), V(a.x, a.y, -a.z)
    edges = [
        Part.makeLine(a, b),
        Part.makeLine(b, c),
        Part.makeLine(c, d),
        Part.Arc(d, V(-root, 0.3, 0), a).toShape(),
    ]
    return Part.Face(Part.Wire(edges)).extrude(V(0, HORN_HEIGHT - 0.3, 0))


def _hex_along_axis(across_flats, length, origin, direction):
    """Plain six-sided pocket, using the stock nut's vertex orientation."""
    from .purchased_hardware import hex_prism

    shape = hex_prism(across_flats, length)
    shape.Placement = App.Placement(V(*origin), App.Rotation(V(0, 0, 1), V(*direction)))
    return shape


def _d_section(y, length, clearance=0.0):
    radius = SHAFT_DIAMETER / 2 + clearance
    shape = _cylinder(radius, length, (0, y, 0))
    flat_x = SHAFT_DIAMETER / 2 - SHAFT_FLAT_DEPTH + clearance
    return shape.cut(box(4, length + 0.2, 4, (flat_x, y - 0.1, -2)))


def driver_shaft_shape():
    """Nominal locally cut Ø3×16 aluminium stub with a full-length 0.5 mm flat."""
    return _one_solid(_d_section(SHAFT_START_Y, SHAFT_LENGTH), "Driver metal shaft")


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
    """Open horn socket and keyed metal-shaft housing as one printable solid.

    The open root register and opposing flat tip datum locate the horn while
    the relieved straight flanks avoid matching its exact blade contour. It
    approaches an already retained horn axially; neither the spline nor new
    holes in the bought horn are fabricated. Both blind pockets open to the
    exterior; a 1.9 mm roof separates the shaft stop from the provisional OEM
    screw-head cavity.
    """
    shape = union(
        [
            _tangent_hull(BODY_BACK_Y, SHAFT_START_Y - BODY_BACK_Y, 4.7, 4.0, BOLT_X),
            _cylinder(3.8, SHAFT_SOCKET_LENGTH, (0, SHAFT_START_Y, 0)),
            box(
                SHAFT_BOSS_END_X,
                SHAFT_SOCKET_LENGTH,
                8,
                (0, SHAFT_START_Y, -4),
            ),
        ]
    )
    shape = shape.cut(_horn_pocket())
    # Clearance around an installed original screw head is deliberately a
    # prototype envelope. Remove the adapter for service; the metal shaft and
    # the closed socket floor do not offer access to that unmeasured head.
    shape = shape.cut(_cylinder(2.5, 5.3, (0, -0.1, 0)))
    shape = shape.cut(
        _d_section(SHAFT_START_Y, SHAFT_SOCKET_LENGTH + 0.1, SHAFT_SOCKET_CLEARANCE)
    )
    shape = shape.cut(_cylinder(1.1, 10.0, (BOLT_X, -0.1, 0)))
    shape = shape.cut(
        _hex_along_axis(NUT_POCKET_AF, 3, (BOLT_X, NUT_SEAT_Y, 0), (0, 1, 0))
    )
    # The transverse nut drops in from +Z. Its bottom hex seat prevents rotation;
    # the 1.5 mm outer wall takes the clamp reaction. No printed thread is used.
    nut_pocket = _hex_along_axis(
        NUT_POCKET_AF,
        SHAFT_NUT_POCKET_LENGTH,
        (SHAFT_NUT_SEAT_X, SHAFT_CLAMP_Y, 0),
        SHAFT_BOLT_DIRECTION,
    )
    nut_loading = box(
        SHAFT_NUT_POCKET_LENGTH,
        NUT_POCKET_AF,
        5,
        (
            SHAFT_NUT_SEAT_X - SHAFT_NUT_POCKET_LENGTH,
            SHAFT_CLAMP_Y - NUT_POCKET_AF / 2,
            0,
        ),
    )
    shape = shape.cut(union([nut_pocket, nut_loading]))
    shape = shape.cut(_cylinder(1.1, 7, (7, SHAFT_CLAMP_Y, 0), SHAFT_BOLT_DIRECTION))
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


def shaft_fastener_positions():
    """Radial button screw touches the filed flat; head remains clear of PA12.

    The screw acts as a jack through the captive nut. Its head is not a bearing
    face: the nominal 0.5 mm head-to-boss gap allows tightening against the stub.
    """
    return {
        "screw": (SHAFT_SCREW_HEAD_X, SHAFT_CLAMP_Y, 0),
        "nut": (SHAFT_NUT_SEAT_X, SHAFT_CLAMP_Y, 0),
        "direction": SHAFT_BOLT_DIRECTION,
        "length": SHAFT_SCREW_LENGTH,
    }


def metrics():
    return {
        "horn_sku": HORN_SKU,
        "sources": [HORN_SOURCE, HORN_DRAWING_SOURCE],
        "retained_evidence": "references/kst_0415_13_horn_dimensions.png",
        "horn_shape_scope": "KST-authored drawing via distributor. Conservative tangent hull, smooth spline bore and nominal holes; exact fillets, spline teeth, material grade and measured mass are not claimed.",
        "gear_bore_diameter_mm": GEAR_BORE_DIAMETER,
        "driver_shaft_diameter_mm": SHAFT_DIAMETER,
        "driver_shaft_length_mm": SHAFT_LENGTH,
        "driver_shaft_flat_depth_mm": SHAFT_FLAT_DEPTH,
        "driver_shaft_socket_length_mm": SHAFT_SOCKET_LENGTH,
        "driver_shaft_socket_clearance_mm": SHAFT_SOCKET_CLEARANCE,
        "gear_start_from_horn_bottom_mm": GEAR_START_Y,
        "horn_register_clearance_each_side_mm": HORN_REGISTER_CLEARANCE,
        "horn_flank_relief_at_tip_centre_mm": HORN_BLADE_CLEARANCE,
        "horn_tip_clearance_mm": HORN_TIP_CLEARANCE,
        "horn_socket_engagement_mm": HORN_HEIGHT - BODY_BACK_Y,
        "adapter_axial_release_travel_mm": ADAPTER_RELEASE_TRAVEL,
        "retainer_thickness_mm": RETAINER_THICKNESS,
        "retainer_closure_gap_mm": BODY_BACK_Y - HORN_BLADE_BOTTOM,
        "common_clamp_fasteners_per_side": 2,
        "shaft_retention": "Nominal Ø3 x16 mm 6061 rod, cut square and deburred, with one continuous 0.5 mm-deep flat. The shaft bottoms in the adapter; an M2x6 button screw through a captive M2 hex nut presses the flat. The gear requires a radial M3 set screw on the same flat; inclusion, length, point and protrusion remain unverified. The printed D socket provides geometric anti-rotation after its clearance is taken up; axial retention and initial torque transmission still require actual clamp tests. Both the raw rod diameter and filed flat are shop acceptance dimensions, not guaranteed purchased tolerances.",
        "assembly": "Install the OEM horn-retaining screw before the adapter. Finish and clean the open D socket and nut-loading slot; seat the metal stub against its stop, drop the radial hex nut through the +Z opening and tighten the M2x6 screw against the flat without bottoming its head. Fit the purchased driver and tighten its verified M3 screw on the same flat. Capture the retained horn with the rear strap and M2x8 screw/nut. For service, use the checked module or horn-coupling path with the metal stub and radial clamp kept with the adapter. Set neutral, mesh direction and tooth phasing before calibration. Actual screw access, cable handling and both-direction grip remain sample checks.",
        "qualification": "The open hub register, opposing flat tip stop and D-socket retain 0.05 mm nominal finish-fit clearances, not as-printed tolerance claims. Straight flanks spread from the root datum to 0.25 mm nominal relief at the tip-centre station; exact blade taper and tip radius do not locate the assembly. Horn hub diameter and overall length remain critical for concentricity. Clamp preload transfers normal torque; the relieved flanks provide a backup stop, not a zero-backlash claim. Verify clamp grip in both directions, the 1.3 mm register, 1.9 mm roof ahead of the provisional OEM screw-head cavity, nut capture, shaft concentricity, rocking, axial retention and loaded alignment. Check the finished rod against both gear bore and socket; reject bent, oversize or loose stock. Do not force an oversize rod into a gear. The direct gear still applies unqualified radial load to the servo output; no external radial-load rating is published.",
    }
