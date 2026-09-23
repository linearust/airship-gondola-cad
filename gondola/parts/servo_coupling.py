"""Machining blank for the supplied X06 horn and a bought Ø3-bore gear.

No drawing of the supplied horn is available. The installed horn/holes below
are an explicitly illustrative prepared specimen, not purchased dimensions.
Print the un-drilled blank; transfer two holes from the measured horn while
centred with the separate bench jig, then qualify the finished assembly.
The real spline and original retaining screw are retained, never printed.
Local rotation is +Y; the illustrative horn arm points +X.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import box, union
from gondola.contracts.equipment_interfaces import HORN_SOURCE

V = App.Vector
HORN_SKU = "KST_X06_SUPPLIED_HORN"
HORN_MATERIAL = "Supplied horn material unverified"
HORN_BOTTOM_Y = 7.4
# Illustrative machining setup only: none of these supplied-horn dimensions
# are manufacturer specifications or measurements of the user's part.
HORN_HEIGHT = 3.5
HORN_BLADE_THICKNESS = 1.6
HORN_BLADE_BOTTOM = HORN_HEIGHT - HORN_BLADE_THICKNESS
HORN_HUB_RADIUS = 3.5
HORN_TIP_RADIUS = 2.0
HORN_TIP_CENTRE = 12.0
HORN_EXAMPLE_RECESS_DEPTH = 2.5
HORN_BOLT_CENTRES = ((8.0, 0.0), (12.0, 0.0))
HORN_PREPARED_HOLE_DIAMETERS = (1.7, 1.8)
HORN_ADAPTER_HOLE_DIAMETERS = HORN_PREPARED_HOLE_DIAMETERS
HORN_CLAMP_THREAD_DIAMETER = 1.6
HORN_CLAMP_LENGTH = 8.0
HORN_CLAMP_NUT_HEIGHT = 1.3
BOLT_DIRECTION = (0, 1, 0)

# Fixed gear/servo datums are retained. Change the machining blank, not the
# gear's axial seating datum, if the received horn cannot fit this envelope.
BODY_BACK_Y = 2.5
PLATE_FRONT_Y = 7.1
PLATE_X_MIN, PLATE_X_MAX = -6.5, 15.0
PLATE_HALF_WIDTH = 5.5
HUB_RELIEF_RADIUS = 3.8
HUB_RELIEF_TOP_Y = 4.1
OEM_HEAD_CAVITY_RADIUS = 2.5
OEM_HEAD_CAVITY_TOP_Y = 5.6
CENTER_GUIDE_DIAMETER = 2.4
ADAPTER_RELEASE_TRAVEL = 1.5

GEAR_BORE_DIAMETER = 3.0
SHAFT_DIAMETER = 3.0
SHAFT_START_Y = PLATE_FRONT_Y
SHAFT_LENGTH = 18.0
SHAFT_FLAT_DEPTH = 0.5
SHAFT_SOCKET_LENGTH = 8.0
SHAFT_SOCKET_CLEARANCE = 0.05
GEAR_START_Y = SHAFT_START_Y + SHAFT_SOCKET_LENGTH
GEAR_LENGTH = 8.0
SHAFT_CLAMP_Y = SHAFT_START_Y + SHAFT_SOCKET_LENGTH / 2 + 0.4
# The clamp dimensions below use a canonical negative-X section, clocked
# -90 degrees around Y as a unit. Its real head and shaft flat face negative Z.
# This preserves wall thickness and keeps the opposite servo lead space clear.
SHAFT_CLAMP_CLOCK_DEG = -90.0
SHAFT_SCREW_LENGTH = 6.0
SHAFT_SCREW_HEAD_X = -7.0
SHAFT_NUT_SEAT_X = -5.0
SHAFT_BOLT_DIRECTION = (1, 0, 0)
NUT_POCKET_AF = 4.2
SHAFT_NUT_POCKET_LENGTH = 1.8
SHAFT_BOSS_END_X = -6.5
NUT_SEAT_Y = PLATE_FRONT_Y

JIG_GUIDE_START_Y = 7.7
JIG_GUIDE_LENGTH = 12.0
JIG_NOSE_START_Y = 1.5
JIG_NOSE_LENGTH = 1.5
JIG_NOSE_TIP_DIAMETER = 0.6
JIG_NOSE_BASE_DIAMETER = 1.8
JIG_STEM_DIAMETER = 1.8
JIG_ACCEPTED_ENTRY_DIAMETERS = (0.8, 1.6)
JIG_REFERENCE_ENTRY_Y = 2.5


def shaft_frame_point(x, y, z):
    """Map a canonical clamp-section point or direction into the horn frame."""
    return App.Rotation(V(0, 1, 0), SHAFT_CLAMP_CLOCK_DEG).multVec(V(x, y, z))


def shaft_frame_shape(shape):
    """Clock the complete shaft/clamp feature, preserving all radial sections."""
    shape = shape.copy()
    shape.rotate(V(), V(0, 1, 0), SHAFT_CLAMP_CLOCK_DEG)
    return shape


def _cylinder(radius, length, origin, direction=(0, 1, 0)):
    return Part.makeCylinder(radius, length, V(*origin), V(*direction))


def _tangent_hull(y, depth, root, tip, tip_centre):
    """Simple illustrative arm envelope, not a sourced supplied-horn outline."""
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


def _hex_along_axis(across_flats, length, origin, direction):
    from .purchased_hardware import hex_prism

    shape = hex_prism(across_flats, length)
    shape.Placement = App.Placement(V(*origin), App.Rotation(V(0, 0, 1), V(*direction)))
    return shape


def _d_section(y, length, clearance=0.0):
    radius = SHAFT_DIAMETER / 2 + clearance
    shape = _cylinder(radius, length, (0, y, 0))
    flat_x = -(SHAFT_DIAMETER / 2 - SHAFT_FLAT_DEPTH) - clearance
    return shape.cut(box(4 + flat_x, length + 0.2, 4, (-4, y - 0.1, -2)))


def _one_solid(shape, name):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError(name + " must be one valid solid")
    return shape


def driver_shaft_shape():
    """Selected 304 stock cut to Ø3×18, with a full-length negative-Z flat."""
    return _one_solid(
        shaft_frame_shape(_d_section(SHAFT_START_Y, SHAFT_LENGTH)), "Driver metal shaft"
    )


def horn_shape():
    """Unmeasured supplied-horn *example*, showing two prepared through-holes.

    Smooth recess and centre hole only prevent a misleading solid proxy through
    the servo output. They do not specify a spline, recess depth, OEM screw,
    material or factory horn outline. The real supplied horn must be surveyed.
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
    shape = shape.cut(_cylinder(1.95, HORN_EXAMPLE_RECESS_DEPTH + 0.1, (0, -0.1, 0)))
    shape = shape.cut(_cylinder(1.1, HORN_HEIGHT + 0.2, (0, -0.1, 0)))
    for (x, z), diameter in zip(HORN_BOLT_CENTRES, HORN_PREPARED_HOLE_DIAMETERS):
        shape = shape.cut(_cylinder(diameter / 2, HORN_HEIGHT + 0.2, (x, -0.1, z)))
    return _one_solid(shape, "Unmeasured supplied horn prepared example")


def adapter_blank_shape():
    """One printable blank: flat machining stock, keyed socket and radial clamp.

    No horn fastening holes or shape-specific end/root registers are printed.
    The wide hub relief is clearance, not a locating fit. A centred access hole
    connects the separate alignment jig through the shaft-stop floor. The floor
    retains an annular/crescent metal stop; the jig is removed before the stub.
    """
    shape = union(
        [
            box(
                PLATE_X_MAX - PLATE_X_MIN,
                PLATE_FRONT_Y - BODY_BACK_Y,
                2 * PLATE_HALF_WIDTH,
                (PLATE_X_MIN, BODY_BACK_Y, -PLATE_HALF_WIDTH),
            ),
            _cylinder(3.8, SHAFT_SOCKET_LENGTH, (0, SHAFT_START_Y, 0)),
            shaft_frame_shape(
                box(
                    -SHAFT_BOSS_END_X,
                    SHAFT_SOCKET_LENGTH,
                    8,
                    (SHAFT_BOSS_END_X, SHAFT_START_Y, -4),
                )
            ),
        ]
    )
    shape = shape.cut(
        _cylinder(
            HUB_RELIEF_RADIUS,
            HUB_RELIEF_TOP_Y - BODY_BACK_Y + 0.1,
            (0, BODY_BACK_Y - 0.1, 0),
        )
    )
    shape = shape.cut(
        _cylinder(
            OEM_HEAD_CAVITY_RADIUS,
            OEM_HEAD_CAVITY_TOP_Y - BODY_BACK_Y + 0.1,
            (0, BODY_BACK_Y - 0.1, 0),
        )
    )
    shape = shape.cut(
        _cylinder(
            CENTER_GUIDE_DIAMETER / 2,
            GEAR_START_Y - BODY_BACK_Y + 0.2,
            (0, BODY_BACK_Y - 0.1, 0),
        )
    )
    shape = shape.cut(
        shaft_frame_shape(
            _d_section(SHAFT_START_Y, SHAFT_SOCKET_LENGTH + 0.1, SHAFT_SOCKET_CLEARANCE)
        )
    )
    pocket = _hex_along_axis(
        NUT_POCKET_AF,
        SHAFT_NUT_POCKET_LENGTH,
        (SHAFT_NUT_SEAT_X, SHAFT_CLAMP_Y, 0),
        SHAFT_BOLT_DIRECTION,
    )
    loading = box(
        SHAFT_NUT_POCKET_LENGTH,
        NUT_POCKET_AF,
        5,
        (SHAFT_NUT_SEAT_X, SHAFT_CLAMP_Y - NUT_POCKET_AF / 2, 0),
    )
    shape = shape.cut(shaft_frame_shape(union([pocket, loading])))
    shape = shape.cut(
        shaft_frame_shape(
            _cylinder(
                1.1, 7, (SHAFT_SCREW_HEAD_X, SHAFT_CLAMP_Y, 0), SHAFT_BOLT_DIRECTION
            )
        )
    )
    return _one_solid(shape, "Supplied-horn machining blank")


def adapter_shape():
    """Prepared assembly example only; STL/STEP must use adapter_blank_shape()."""
    shape = adapter_blank_shape()
    shape = shape.cut(box(30, HORN_HEIGHT - BODY_BACK_Y, 20, (-10, BODY_BACK_Y, -10)))
    for (x, z), diameter in zip(HORN_BOLT_CENTRES, HORN_ADAPTER_HOLE_DIAMETERS):
        shape = shape.cut(
            _cylinder(
                diameter / 2,
                PLATE_FRONT_Y - HORN_HEIGHT + 0.2,
                (x, HORN_HEIGHT - 0.1, z),
            )
        )
    return _one_solid(shape, "Supplied-horn prepared assembly example")


def centering_jig_shape():
    """Removable bench tool, no spline copy and no installed flight function.

    Fit the D guide to the same finished socket. Its soft conical nose may seat
    only against a measured concentric centre-screw entry, with the original
    screw removed. Never force it into threads. The small tip is a prototype
    feature requiring supplier agreement, dressing and concentricity inspection.
    """
    nose = Part.makeCone(
        JIG_NOSE_TIP_DIAMETER / 2,
        JIG_NOSE_BASE_DIAMETER / 2,
        JIG_NOSE_LENGTH,
        V(0, JIG_NOSE_START_Y, 0),
        V(0, 1, 0),
    )
    stem_start = JIG_NOSE_START_Y + JIG_NOSE_LENGTH
    stem = _cylinder(
        JIG_STEM_DIAMETER / 2, JIG_GUIDE_START_Y - stem_start, (0, stem_start, 0)
    )
    guide = shaft_frame_shape(_d_section(JIG_GUIDE_START_Y, JIG_GUIDE_LENGTH))
    handle = _cylinder(4, 2, (0, JIG_GUIDE_START_Y + JIG_GUIDE_LENGTH, 0))
    return _one_solid(union([nose, stem, guide, handle]), "Horn centring bench jig")


def fastener_positions():
    """Two separately prepared joints; near/far holes are an example, not OEM."""
    return tuple(
        {"screw": (x, HORN_BLADE_BOTTOM, z), "nut": (x, NUT_SEAT_Y, z)}
        for x, z in HORN_BOLT_CENTRES
    )


def shaft_fastener_positions():
    return {
        "screw": tuple(shaft_frame_point(SHAFT_SCREW_HEAD_X, SHAFT_CLAMP_Y, 0)),
        "nut": tuple(shaft_frame_point(SHAFT_NUT_SEAT_X, SHAFT_CLAMP_Y, 0)),
        "direction": tuple(shaft_frame_point(*SHAFT_BOLT_DIRECTION)),
        "length": SHAFT_SCREW_LENGTH,
    }


def machining_contract():
    return {
        "supplied_horn_measured": False,
        "prepared_preview_is_example": True,
        "printed_blank_has_horn_holes": False,
        "horn_central_hub_radius_max_mm": 3.5,
        "horn_central_hub_front_max_y_mm": 4.0,
        "arm_contact_front_y_range_mm": [BODY_BACK_Y, HUB_RELIEF_TOP_Y],
        "arm_back_min_y_mm": 1.9,
        "allowed_arm_thickness_rule": "Arm front minus measured thickness must be at least Y1.9; do not infer an independent thickness tolerance.",
        "horn_outline_limit_x_mm": [-3.5, 14.0],
        "horn_outline_limit_z_mm": [-3.5, 3.5],
        "bolt_centre_working_x_range_mm": [6.5, 12.5],
        "bolt_centre_working_z_range_mm": [-1.0, 1.0],
        "minimum_two_hole_separation_mm": 4.0,
        "minimum_measured_horn_hole_edge_ligament_mm": 0.8,
        "example_horn_hole_diameters_mm": HORN_PREPARED_HOLE_DIAMETERS,
        "example_adapter_hole_diameters_mm": HORN_ADAPTER_HOLE_DIAMETERS,
        "example_hole_centres_xz_mm": HORN_BOLT_CENTRES,
        "example_arm_front_y_mm": HORN_HEIGHT,
        "example_arm_thickness_mm": HORN_BLADE_THICKNESS,
        "minimum_plate_thickness_after_facing_mm": PLATE_FRONT_Y - HUB_RELIEF_TOP_Y,
        "oem_head_envelope_diameter_mm": 4.4,
        "oem_head_top_limit_y_mm": 5.4,
        "head_cavity_ceiling_y_mm": OEM_HEAD_CAVITY_TOP_Y,
        "shaft_stop_floor_thickness_mm": SHAFT_START_Y - OEM_HEAD_CAVITY_TOP_Y,
        "guide_hole_diameter_mm": CENTER_GUIDE_DIAMETER,
        "jig_entry_diameter_range_mm": JIG_ACCEPTED_ENTRY_DIAMETERS,
        "jig_reference_entry_y_mm": JIG_REFERENCE_ENTRY_Y,
        "jig_tip_min_diameter_mm": JIG_NOSE_TIP_DIAMETER,
        "jig_scope": "Prototype centring aid, not a precision-certified pin. The range is a jig design range, not the OEM screw/thread specification. Confirm a circular entry concentric with the real output and its depth, finish the guide/tip, verify actual seating without loading/damaging threads, and inspect the tip for damage. Reject a mismatched entry rather than forcing it.",
        "machining_scope": "These are design working limits, not supplied-horn dimensions. Survey the genuine horn, including existing holes, hub, root fillets and installed axial seating. Do not weaken the spline/root or bridge into an existing hole. If two sound fastening sites do not fit, replace/redesign the blank rather than damage the horn. No arbitrary horn or round-disc compatibility is claimed.",
        "centering_sequence": "On an unpowered bench, retain the real spline and remove only the OEM centre screw. Fit/face the blank to the measured arm without changing the gear datum or thinning the socket floor. Centre it with the finished D-guide jig lightly seated on the measured output-screw entry. Hold the horn/blank registration with temporary bench clamps; transfer the two locations. Remove the parts from the servo before drilling, retaining their registration in the fixture. Drill the supported pair, deburr and clean; never drill into the servo. Fit the near hole closely to the measured M1.6 shank (Ø1.7 is only the modeled example); use the second Ø1.8 hole for assembly allowance. The two separated through-bolts provide clamp force and improve repeatability, but do not establish zero play or certified concentricity.",
        "final_alignment": "Remove the adapter and jig, reinstall the genuine horn with the OEM retaining screw, then attach the prepared adapter with both rear M1.6 screws and front nuts. Remove the jig permanently before fitting the metal stub. The clearance holes do not establish precision concentricity: indicate the actual input stub/gear while moving the unpowered servo through its allowed travel, align before final tightening, then recheck runout, mesh, both-direction retention and drift. No numerical runout or torque acceptance has yet been qualified.",
        "centre_screw_service": "Remove gear, metal stub and adapter as required before using the proper tool on the OEM screw. The guide hole is for the jig stem, not a promise that the unknown screw head can be inserted through the assembled socket. No fictitious side-insertion path is claimed.",
    }


def metrics():
    contract = machining_contract()
    return {
        "horn_sku": HORN_SKU,
        "sources": [HORN_SOURCE],
        "horn_shape_scope": "Illustrative supplied-horn working envelope, not a manufacturer drawing or measured purchased part; no spline is fabricated.",
        "machining": contract,
        "horn_prepared_hole_diameters_mm": HORN_PREPARED_HOLE_DIAMETERS,
        "horn_prepared_hole_centres_xz_mm": HORN_BOLT_CENTRES,
        "horn_adapter_hole_diameters_mm": HORN_ADAPTER_HOLE_DIAMETERS,
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
        "driver_shaft_flat_facing": "negative Z in horn-local coordinates",
        "driver_shaft_socket_length_mm": SHAFT_SOCKET_LENGTH,
        "driver_shaft_socket_clearance_mm": SHAFT_SOCKET_CLEARANCE,
        "driver_shaft_projection_beyond_gear_mm": SHAFT_START_Y
        + SHAFT_LENGTH
        - GEAR_START_Y
        - GEAR_LENGTH,
        "gear_start_from_horn_bottom_mm": GEAR_START_Y,
        "horn_long_side_walls_retained": False,
        "adapter_axial_release_travel_mm": ADAPTER_RELEASE_TRAVEL,
        "common_clamp_fasteners_per_side": 3,
        "shaft_retention": "Selected nominal Ø3×18 mm 304 rod with a full-length 0.5 mm flat toward negative Z; finish diameter and straightness against the bought gear and finished D socket. The radial M2x6 jack clamp and purchased gear M3 screw act on that flat. An 8 mm socket, perforated 1.5 mm stop floor and 2 mm beyond-gear reserve are geometric features, not qualified friction/strength. No input bearing is added.",
        "assembly": contract["centering_sequence"]
        + " "
        + contract["final_alignment"]
        + " "
        + contract["centre_screw_service"],
        "qualification": "Unmeasured supplied horn, manually matched drilling/facing and prototype alignment jig. No 0415.13 outline, 13.2 mm factory hole, radial register, precise bolt-hole centering, physical fit or strength claim is inherited. Complete physical centring, clamp, motion and load qualification before use.",
    }
