"""Open bolted horn plate driving a bought Ø3-bore gear through a metal stub.

The gear runs on the servo output through its bought KST horn. Its outer hole
is locally enlarged to Ø1.8; an existing M1.6 screw/nut clamps the metal blade
directly to one PA12 adapter, without a separate rear strap. A locally cut and flattened Ø3 aluminium stub seats in a finished
D-shaped socket. One radial M2 screw and captive hex nut retain the stub; the
gear uses an M3 set screw whose supply and exact geometry remain unverified.
No printed journal enters the gear bore and no external input bearing is added. Local rotation is +Y; the horn points +X.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import box, union
from gondola.contracts.equipment_interfaces import HORN_DRAWING_SOURCE, HORN_SOURCE

V = App.Vector
HORN_SKU = "KST_0415_13_TIP_D1_8"
HORN_MATERIAL = "Aluminium alloy (grade unspecified)"
HORN_HEIGHT = 3.5
HORN_BLADE_THICKNESS = 1.6
HORN_HUB_RADIUS = 3.0
HORN_TIP_RADIUS = 2.0
HORN_TIP_CENTRE = 13.2
HORN_SPLINE_RECESS_DEPTH = 2.5
HORN_BLADE_BOTTOM = HORN_HEIGHT - HORN_BLADE_THICKNESS
# The two servo ear seats straddle the shared wall at Y +/-2.5 mm.
HORN_BOTTOM_Y = 7.4
HORN_REGISTER_CLEARANCE = 0.05
HORN_TIP_CLEARANCE = HORN_REGISTER_CLEARANCE
TIP_STOP_WIDTH = 3.0
TIP_STOP_THICKNESS = 1.8
ADAPTER_RELEASE_TRAVEL = 1.5
GEAR_BORE_DIAMETER = 3.0
SHAFT_DIAMETER = 3.0
SHAFT_START_Y = 7.1
SHAFT_LENGTH = 18.0
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
BODY_BACK_Y = 2.2
BOLT_X = HORN_TIP_CENTRE
ADAPTER_ROOT_RADIUS = 4.7
ADAPTER_TIP_RADIUS = 4.5
HORN_PREPARED_HOLE_DIAMETER = 1.8
HORN_ADAPTER_HOLE_DIAMETER = 2.0
HORN_CLAMP_THREAD_DIAMETER = 1.6
HORN_CLAMP_LENGTH = 8.0
HORN_CLAMP_NUT_HEIGHT = 1.3
NUT_SEAT_Y = SHAFT_START_Y
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


def _root_register_clearance():
    """Leave a constant-section negative-X semicircle around the horn hub.

    Removing the complete positive half avoids the feathered ends produced
    when a narrower rectangular throat intersects the outer circular wall.
    """
    radius = HORN_HUB_RADIUS + HORN_REGISTER_CLEARANCE
    depth = HORN_HEIGHT - 0.3
    opening_radius = ADAPTER_ROOT_RADIUS + 0.1
    return union(
        [
            _cylinder(radius, depth, (0, 0.3, 0)),
            box(opening_radius, depth, 2 * opening_radius, (0, 0.3, -opening_radius)),
        ]
    )


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
    """Nominal Ø3×18 stub; a full-length flat includes the 2 mm gear-end reserve."""
    return _one_solid(_d_section(SHAFT_START_Y, SHAFT_LENGTH), "Driver metal shaft")


def horn_shape():
    """Stock horn with only its outer Ø1 hole locally enlarged to Ø1.8.

    The other holes retain the manufacturer drawing dimensions. The prepared
    hole is a workshop operation, not a factory specification; spline teeth
    remain a smooth envelope and are never fabricated from this model.
    """
    shape = union(
        [
            _cylinder(HORN_HUB_RADIUS, HORN_HEIGHT, (0, 0, 0)),
            _tangent_hull(
                HORN_BLADE_BOTTOM,
                HORN_BLADE_THICKNESS,
                HORN_HUB_RADIUS,
                HORN_TIP_RADIUS,
                HORN_TIP_CENTRE,
            ),
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
    shape = shape.cut(_cylinder(HORN_PREPARED_HOLE_DIAMETER / 2, 2.0, (BOLT_X, 1.7, 0)))
    return _one_solid(shape, "Locally prepared KST horn")


def adapter_shape():
    """Open clamping plate and keyed metal-shaft housing as one solid.

    Only the short root register and a small opposing tip stop locate the horn;
    both long arm edges stay uncovered. The broad front face clamps the blade. It
    approaches an already retained horn axially after its outer hole has been
    enlarged and the M1.6 screw inserted from the rear. Both blind pockets open
    to the exterior; a 1.9 mm roof separates the shaft stop from the provisional OEM
    screw-head cavity.
    """
    shape = union(
        [
            _tangent_hull(
                HORN_HEIGHT,
                SHAFT_START_Y - HORN_HEIGHT,
                ADAPTER_ROOT_RADIUS,
                ADAPTER_TIP_RADIUS,
                BOLT_X,
            ),
            _cylinder(
                ADAPTER_ROOT_RADIUS,
                HORN_HEIGHT - BODY_BACK_Y,
                (0, BODY_BACK_Y, 0),
            ),
            box(
                TIP_STOP_THICKNESS,
                HORN_HEIGHT - BODY_BACK_Y,
                TIP_STOP_WIDTH,
                (
                    HORN_TIP_CENTRE + HORN_TIP_RADIUS + HORN_TIP_CLEARANCE,
                    BODY_BACK_Y,
                    -TIP_STOP_WIDTH / 2,
                ),
            ),
            _cylinder(3.8, SHAFT_SOCKET_LENGTH, (0, SHAFT_START_Y, 0)),
            box(
                SHAFT_BOSS_END_X,
                SHAFT_SOCKET_LENGTH,
                8,
                (0, SHAFT_START_Y, -4),
            ),
        ]
    )
    shape = shape.cut(_root_register_clearance())
    # Clearance around an installed original screw head is deliberately a
    # prototype envelope. Remove the adapter for service; the metal shaft and
    # the closed socket floor do not offer access to that unmeasured head.
    shape = shape.cut(_cylinder(2.5, 5.3, (0, -0.1, 0)))
    shape = shape.cut(
        _d_section(SHAFT_START_Y, SHAFT_SOCKET_LENGTH + 0.1, SHAFT_SOCKET_CLEARANCE)
    )
    # The front nut bears on the broad solid face, not on a captive pocket.
    # Ø2 clearance accepts the prepared metal hole without a second close fit.
    shape = shape.cut(
        _cylinder(HORN_ADAPTER_HOLE_DIAMETER / 2, 10.0, (BOLT_X, -0.1, 0))
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


def _one_solid(shape, name):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError(name + " must be one valid solid")
    return shape


def fastener_positions():
    """M1.6 head bears on the metal horn; its plain front nut bears on PA12."""
    return ({"screw": (BOLT_X, HORN_BLADE_BOTTOM, 0), "nut": (BOLT_X, NUT_SEAT_Y, 0)},)


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
        "horn_shape_scope": "KST-authored drawing via distributor. Conservative tangent hull and smooth spline bore; the outer factory Ø1.0 hole at 13.2 mm radius is locally enlarged to Ø1.8. Other drawing holes are unchanged. Exact fillets, spline teeth, material grade and measured mass are not claimed.",
        "horn_prepared_hole_diameter_mm": HORN_PREPARED_HOLE_DIAMETER,
        "horn_prepared_hole_radius_mm": BOLT_X,
        "horn_adapter_hole_diameter_mm": HORN_ADAPTER_HOLE_DIAMETER,
        "horn_clamp_thread_diameter_mm": HORN_CLAMP_THREAD_DIAMETER,
        "horn_clamp_screw_length_mm": HORN_CLAMP_LENGTH,
        "horn_clamp_grip_mm": NUT_SEAT_Y - HORN_BLADE_BOTTOM,
        "horn_clamp_nut_height_mm": HORN_CLAMP_NUT_HEIGHT,
        "horn_clamp_tip_projection_mm": HORN_CLAMP_LENGTH
        - (NUT_SEAT_Y - HORN_BLADE_BOTTOM)
        - HORN_CLAMP_NUT_HEIGHT,
        "gear_bore_diameter_mm": GEAR_BORE_DIAMETER,
        "driver_shaft_diameter_mm": SHAFT_DIAMETER,
        "driver_shaft_length_mm": SHAFT_LENGTH,
        "driver_shaft_flat_depth_mm": SHAFT_FLAT_DEPTH,
        "driver_shaft_socket_length_mm": SHAFT_SOCKET_LENGTH,
        "driver_shaft_socket_clearance_mm": SHAFT_SOCKET_CLEARANCE,
        "driver_shaft_projection_beyond_gear_mm": SHAFT_START_Y
        + SHAFT_LENGTH
        - GEAR_START_Y
        - GEAR_LENGTH,
        "gear_start_from_horn_bottom_mm": GEAR_START_Y,
        "horn_register_clearance_each_side_mm": HORN_REGISTER_CLEARANCE,
        "horn_long_side_walls_retained": False,
        "horn_tip_stop_width_mm": TIP_STOP_WIDTH,
        "horn_tip_stop_thickness_mm": TIP_STOP_THICKNESS,
        "horn_tip_clearance_mm": HORN_TIP_CLEARANCE,
        "horn_socket_engagement_mm": HORN_HEIGHT - BODY_BACK_Y,
        "adapter_axial_release_travel_mm": ADAPTER_RELEASE_TRAVEL,
        "common_clamp_fasteners_per_side": 2,
        "shaft_retention": "Nominal Ø3 x18 mm 6061 rod, cut square and deburred, with one continuous 0.5 mm-deep flat. The shaft bottoms in the adapter and projects 2 mm beyond the selected 8 mm gear, leaving a small metal-length reserve without changing its nominal mesh location. This does not qualify arbitrary replacement gears or an axial adjustment range. An M2x6 button screw through a captive M2 hex nut presses the flat. The gear requires a radial M3 set screw on the same flat; inclusion, length, point and protrusion remain unverified. The printed D socket provides geometric anti-rotation after its clearance is taken up; axial retention and initial torque transmission still require actual clamp tests. Both the raw rod diameter and filed flat are shop acceptance dimensions, not guaranteed purchased tolerances.",
        "assembly": "Remove the horn before drilling: support its blade, enlarge only the existing outer Ø1.0 hole at 13.2 mm radius to Ø1.8 and deburr both faces without altering the spline or seating surfaces. Reject cracks, elongated holes or a distorted blade. Refit the horn and its original OEM retaining screw before the adapter. Finish and clean the open D socket and nut-loading slot; seat the metal stub against its stop, drop the radial hex nut through the +Z opening and tighten the M2x6 screw against the flat without bottoming its head. Fit the purchased driver and tighten its verified M3 screw on the same flat. At neutral, insert the M1.6x8 slotted screw from behind the prepared horn tip, approach the adapter axially over the screw and install the M1.6 front hex nut. The screw head bears directly on the metal blade; tighten only enough to prevent slip or rocking without crushing PA12. For removal, unthread the nut 3 mm forward, move it outboard, then withdraw the screw rearward before releasing the adapter. For service, use the checked module or horn-coupling path with the metal stub and radial clamp kept with the adapter. Set neutral, mesh direction and tooth phasing before calibration. Actual screw access, cable handling and both-direction grip remain sample checks.",
        "qualification": "The open hub register, short central tip stop and D-socket retain 0.05 mm nominal finish-fit clearances, not as-printed tolerance claims. The long blade sides are uncovered; exact blade taper does not locate the assembly. Horn hub diameter and overall length remain critical for concentricity independently of screw-hole clearance. Clamp preload transfers normal torque; the through-screw limits gross rotation if it slips, without a zero-backlash or strength claim. The prepared Ø1.8 tip hole leaves only 0.4 mm to its neighboring factory Ø0.8 hole in the drawing envelope: inspect that web after preparation and verify the actual horn and clamp under both-direction load. The drawing does not specify alloy grade or allowable loads. Verify clamp grip in both directions, the 1.3 mm register, 1.9 mm roof ahead of the provisional OEM screw-head cavity, nut capture, shaft concentricity, rocking, axial retention and loaded alignment. Check the finished rod against both gear bore and socket; reject bent, oversize or loose stock. Do not force an oversize rod into a gear. The direct gear still applies unqualified radial load to the servo output; no external radial-load rating is published.",
    }
