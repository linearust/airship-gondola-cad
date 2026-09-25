"""Purchased 15T/4 mm horn with an open locating saddle and clamp allowance.

Factory threads remove manual horn drilling. The shallow C-shaped root seat
provides an assembly reference; clearance holes/one short slot allow adjustment
before tightening, never intentional operating looseness. Seller front-outline
geometry is distinguished from the still-unmeasured axial seating envelope.
Local rotation is +Y and the arm points +X.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import box, union
from gondola.contracts.equipment_interfaces import HORN_SOURCE

V = App.Vector
HORN_SKU = "ALI_PTK_15T_4MM_HORN"
HORN_MATERIAL = "Aluminium alloy (grade unspecified)"
HORN_BOTTOM_Y = 7.4
# Axial proxy retained for fit-prototype clearance only, not a seller dimension.
HORN_HEIGHT = 3.5
HORN_BLADE_THICKNESS = 1.6
HORN_BLADE_BOTTOM = HORN_HEIGHT - HORN_BLADE_THICKNESS
HORN_HUB_RADIUS = 6.1 / 2
HORN_LENGTH = 18.2
HORN_TIP_RADIUS = 2.0  # Unsourced rounded-tip envelope, not a locating datum.
HORN_TIP_CENTRE = HORN_LENGTH - HORN_HUB_RADIUS - HORN_TIP_RADIUS
HORN_RECESS_DEPTH = 2.5  # Smooth spline-space proxy; no spline is fabricated.
HORN_FACTORY_HOLE_CENTRES = ((6.6, 0.0), (9.4, 0.0), (12.2, 0.0))
# Third position is inferred equal pitch; the outer slot tolerates +/-0.4 mm.
HORN_BOLT_CENTRES = (HORN_FACTORY_HOLE_CENTRES[0], HORN_FACTORY_HOLE_CENTRES[2])
HORN_ADAPTER_HOLE_DIAMETERS = (2.2, 2.2)
HORN_ADAPTER_SLOT_ALLOWANCE = 0.4
HORN_ADAPTER_SLOT_LENGTH = 3.0
HORN_CLAMP_THREAD_DIAMETER = 1.6
HORN_CLAMP_LENGTH = 4.0
BOLT_DIRECTION = (0, -1, 0)
FASTENER_SEAT_Y = 6.1
HEAD_CLEARANCE_DIAMETER = 4.0
HORN_MIN_HEAD_BEARING_DIAMETER = 3.0

# Preserve the selected gears' established axial plane and output shaft fit.
PLATE_FRONT_Y = 7.1
PLATE_X_MIN, PLATE_X_MAX = -6.5, 15.3
PLATE_HALF_WIDTH = 5.5
REGISTER_RADIUS = HORN_HUB_RADIUS
REGISTER_CLEARANCE = 0.15
REGISTER_INNER_RADIUS = REGISTER_RADIUS + REGISTER_CLEARANCE
REGISTER_OUTER_RADIUS = 5.2
REGISTER_ENGAGEMENT = 1.5
REGISTER_OPEN_X = 0.7
BODY_BACK_Y = HORN_HEIGHT - REGISTER_ENGAGEMENT
OEM_HEAD_CAVITY_RADIUS = 2.5
OEM_HEAD_CAVITY_TOP_Y = 5.6
ADAPTER_RELEASE_TRAVEL = 1.7

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
SHAFT_CLAMP_CLOCK_DEG = -90.0
SHAFT_SCREW_LENGTH = 6.0
SHAFT_SCREW_HEAD_X = -7.0
SHAFT_NUT_SEAT_X = -5.0
SHAFT_BOLT_DIRECTION = (1, 0, 0)
NUT_POCKET_AF = 4.2
SHAFT_NUT_POCKET_LENGTH = 1.8
SHAFT_BOSS_END_X = -6.5


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
    """Seller root/length envelope with a provisional rounded-tip radius."""
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
    """Seller front outline plus explicitly provisional axial/spline envelope."""
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
    shape = shape.cut(_cylinder(1.95, HORN_RECESS_DEPTH + 0.1, (0, -0.1, 0)))
    shape = shape.cut(_cylinder(1.1, HORN_HEIGHT + 0.2, (0, -0.1, 0)))
    for x, z in HORN_FACTORY_HOLE_CENTRES:
        # Nominal thread-major void: thread flanks intentionally not modeled.
        shape = shape.cut(_cylinder(0.8, HORN_HEIGHT + 0.2, (x, -0.1, z)))
    return _one_solid(shape, "Selected 15T/4 mm purchased horn envelope")


def capsule(radius, allowance, start_y, length, x, z=0):
    """Round-ended opening elongated in the arm direction only."""
    if allowance == 0:
        return _cylinder(radius, length, (x, start_y, z))
    return union(
        [
            _cylinder(radius, length, (x - allowance, start_y, z)),
            _cylinder(radius, length, (x + allowance, start_y, z)),
            box(
                2 * allowance, length, 2 * radius, (x - allowance, start_y, z - radius)
            ),
        ]
    )


def adapter_shape():
    """Finished one-piece adapter; no undrilled blank or separate retaining cap."""
    root = (
        _cylinder(REGISTER_OUTER_RADIUS, REGISTER_ENGAGEMENT, (0, BODY_BACK_Y, 0))
        .cut(
            _cylinder(
                REGISTER_INNER_RADIUS,
                REGISTER_ENGAGEMENT + 0.2,
                (0, BODY_BACK_Y - 0.1, 0),
            )
        )
        .cut(
            box(
                10,
                REGISTER_ENGAGEMENT + 0.2,
                14,
                (REGISTER_OPEN_X, BODY_BACK_Y - 0.1, -7),
            )
        )
    )
    shape = union(
        [
            box(
                PLATE_X_MAX - PLATE_X_MIN,
                PLATE_FRONT_Y - HORN_HEIGHT,
                2 * PLATE_HALF_WIDTH,
                (PLATE_X_MIN, HORN_HEIGHT, -PLATE_HALF_WIDTH),
            ),
            root,
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
            OEM_HEAD_CAVITY_RADIUS,
            OEM_HEAD_CAVITY_TOP_Y - BODY_BACK_Y + 0.1,
            (0, BODY_BACK_Y - 0.1, 0),
        )
    )
    # The old jig passage is deleted: this is a full 1.5 mm shaft-stop floor.
    shape = shape.cut(
        shaft_frame_shape(
            _d_section(SHAFT_START_Y, SHAFT_SOCKET_LENGTH + 0.1, SHAFT_SOCKET_CLEARANCE)
        )
    )
    for index, ((x, z), diameter) in enumerate(
        zip(HORN_BOLT_CENTRES, HORN_ADAPTER_HOLE_DIAMETERS)
    ):
        allowance = HORN_ADAPTER_SLOT_ALLOWANCE if index else 0.0
        shape = shape.cut(
            capsule(
                diameter / 2,
                allowance,
                HORN_HEIGHT - 0.1,
                PLATE_FRONT_Y - HORN_HEIGHT + 0.2,
                x,
                z,
            )
        )
        if index:
            # Open the outer head recess to the end instead of leaving a
            # fragile 0.4 mm top rim. The through-slot keeps a 1.6 mm end web.
            shape = shape.cut(
                box(
                    PLATE_X_MAX - x + 0.1,
                    PLATE_FRONT_Y - FASTENER_SEAT_Y + 0.1,
                    HEAD_CLEARANCE_DIAMETER,
                    (x, FASTENER_SEAT_Y, z - HEAD_CLEARANCE_DIAMETER / 2),
                )
            )
        shape = shape.cut(
            capsule(
                HEAD_CLEARANCE_DIAMETER / 2,
                allowance,
                FASTENER_SEAT_Y,
                PLATE_FRONT_Y - FASTENER_SEAT_Y + 0.1,
                x,
                z,
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
    return _one_solid(shape, "Factory-hole horn adapter with locating saddle")


def fastener_positions():
    """Two screws seat from the gear side into the existing horn threads."""
    return tuple({"screw": (x, FASTENER_SEAT_Y, z)} for x, z in HORN_BOLT_CENTRES)


def shaft_fastener_positions():
    return {
        "screw": tuple(shaft_frame_point(SHAFT_SCREW_HEAD_X, SHAFT_CLAMP_Y, 0)),
        "nut": tuple(shaft_frame_point(SHAFT_NUT_SEAT_X, SHAFT_CLAMP_Y, 0)),
        "direction": tuple(shaft_frame_point(*SHAFT_BOLT_DIRECTION)),
        "length": SHAFT_SCREW_LENGTH,
    }


def assembly_contract():
    return {
        "horn_sku": HORN_SKU,
        "x06_compatibility_basis": "User-accepted design premise; do not re-request absent concrete contrary evidence.",
        "factory_threads": "All three M1.6, confirmed by user; nominal thread-major voids only.",
        "factory_hole_centres_xz_mm": HORN_FACTORY_HOLE_CENTRES,
        "outer_hole_position_basis": "12.2 mm inferred from equal pitch in seller drawing; outer slot allows +/-0.4 mm radial position variation.",
        "horn_requires_drilling": False,
        "physical_concentricity_verified": False,
        "axial_envelope_measured": False,
        "axial_envelope_scope": "3.5 mm overall hub height, spline recess, OEM head and installed seating are provisional fit-prototype envelopes, not seller dimensions. Recheck seated hardware before fabrication.",
        "nominal_arm_thickness_mm": HORN_BLADE_THICKNESS,
        "adapter_hole_diameters_mm": HORN_ADAPTER_HOLE_DIAMETERS,
        "outer_slot_allowance_mm": HORN_ADAPTER_SLOT_ALLOWANCE,
        "register_radial_clearance_mm": REGISTER_CLEARANCE,
        "register_engagement_mm": REGISTER_ENGAGEMENT,
        "register_scope": "Open C-saddle based on 6.1 mm front root outline, not a specified precision cylindrical hub. It bounds assembly displacement; centre the adapter before tightening, rather than force the root against one side of its clearance. No automatic centring or operating flexibility is claimed.",
        "assembly_adjustment": "Factory threads stay unmodified. Use the preprinted round clearance and outer capsule to accommodate relative hole-position error before tightening. Finish interfering printed surfaces; never force a misaligned assembly home with the screws. Tighten both screws, then verify runout and free mesh over the permitted travel. No deliberate operating looseness.",
        "fastener_grip_mm": FASTENER_SEAT_Y - HORN_HEIGHT,
        "minimum_screw_head_flat_bearing_diameter_mm": HORN_MIN_HEAD_BEARING_DIAMETER,
        "nominal_thread_engagement_mm": HORN_CLAMP_LENGTH
        - (FASTENER_SEAT_Y - HORN_HEIGHT),
        "nominal_rear_tip_clearance_mm": FASTENER_SEAT_Y
        - HORN_CLAMP_LENGTH
        - HORN_BLADE_BOTTOM,
        "thread_engagement_scope": "Geometric engagement only; kit length, chamfers, effective threads and aluminium stripping strength remain physical checks. Keep tips clear of the case during rotation.",
        "centre_screw_service": "First remove both output gears and the complete paired servo/input-drive module. On the bench remove the input gear for front access, then the two horn screws and adapter. Retain the original X06 spline screw; no spline or replacement central thread is fabricated.",
    }


def metrics():
    contract = assembly_contract()
    return {
        "horn_sku": HORN_SKU,
        "sources": [HORN_SOURCE],
        "horn_shape_scope": "Selected seller front dimensions and user-confirmed threads; axial seating and root concentricity remain prototype envelopes.",
        "assembly_contract": contract,
        "horn_factory_hole_centres_xz_mm": HORN_FACTORY_HOLE_CENTRES,
        "horn_adapter_hole_diameters_mm": HORN_ADAPTER_HOLE_DIAMETERS,
        "horn_clamp_thread_diameter_mm": HORN_CLAMP_THREAD_DIAMETER,
        "horn_clamp_screw_length_mm": HORN_CLAMP_LENGTH,
        "horn_clamp_grip_mm": contract["fastener_grip_mm"],
        "horn_clamp_nuts_per_side": 0,
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
        "shaft_retention": "Nominal Ø3x18 mm 304 stock, full-length 0.5 mm flat, 8 mm D socket and radial M2 clamp. Full 1.5 mm stop floor; selected gear M3 screw and 2 mm end reserve retained. No input bearing. Actual shaft fit and retention require inspection.",
        "assembly": contract["assembly_adjustment"]
        + " "
        + contract["centre_screw_service"],
        "qualification": "Fit prototype, not manufactured-part qualification. Factory-hole selection avoids hand transfer drilling; C-seat/clearances do not certify axis concentricity, clamping strength or zero backlash. Check actual axial seating, thread engagement, runout, full motion and load.",
    }
