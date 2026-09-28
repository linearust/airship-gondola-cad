"""One compact two-slot adapter for the manufacturer-supplied X06 half arm 1.

An open root register locates the arm; short slots absorb assembly variation
before tightening. They never permit deliberate movement during operation.
Local rotation is +Y and the arm points +X; shaft and gear planes stay fixed.
"""

import FreeCAD as App
import Part

from gondola.cad import box, union
from gondola.contracts import servo_horns

V = App.Vector
HORN_SKU = servo_horns.profile().sku
HORN_MATERIAL = "Supplied horn material unverified"
HORN_BOTTOM_Y = 7.4
# Nominal manufacturer dimensions, distinct from received/installed measurements.
HORN_HEIGHT = 3.5
HORN_BLADE_THICKNESS = 2.0
HORN_BLADE_BOTTOM = HORN_HEIGHT - HORN_BLADE_THICKNESS
HORN_RECESS_DEPTH = 2.5
HORN_FACTORY_HOLE_CENTRES = tuple((x, 0.0) for x, _ in servo_horns.profile().holes)
HORN_BOLT_CENTRES = tuple((x, 0.0) for x in servo_horns.profile().attachment_radii_mm)
HORN_ADAPTER_HOLE_DIAMETERS = (1.8, 1.8)
HORN_ADAPTER_SLOT_ALLOWANCE = 0.3
SLOT_WIDTH = 1.8
HORN_CLAMP_THREAD_DIAMETER = 1.4
HORN_CLAMP_LENGTH = 8.0
BOLT_DIRECTION = (0, 1, 0)
FASTENER_SEAT_Y = 7.1
HEAD_CLEARANCE_DIAMETER = 4.0
HORN_MIN_HEAD_BEARING_DIAMETER = 3.0

# Preserve the selected gears' established axial plane and output shaft fit.
PLATE_FRONT_Y = 7.1
PLATE_X_MIN, PLATE_X_MAX = -6.5, 16.0
PLATE_HALF_WIDTH = 5.15
REGISTER_RADIUS = max(p.root_diameter_mm / 2 for p in servo_horns.PROFILES.values())
REGISTER_CLEARANCE = 0.15
REGISTER_INNER_RADIUS = REGISTER_RADIUS + REGISTER_CLEARANCE
REGISTER_OUTER_RADIUS = 5.15
REGISTER_ENGAGEMENT = 1.5
REGISTER_OPEN_X = 0.7
BODY_BACK_Y = HORN_HEIGHT - REGISTER_ENGAGEMENT
OEM_HEAD_CAVITY_RADIUS = 2.5
OEM_HEAD_CAVITY_TOP_Y = 5.6
ADAPTER_RELEASE_TRAVEL = 1.7
RETAINED_BOLT_RELEASE_TRAVEL = HORN_BLADE_BOTTOM + HORN_CLAMP_LENGTH - BODY_BACK_Y + 0.2

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


def horn_shape(profile=None, *, prepared=True):
    """Exact nominal OEM STEP, optionally preparing only two existing hole axes."""
    from .oem_servo_horn import normalized_shape

    profile = profile or servo_horns.profile()
    shape = normalized_shape()
    if prepared:
        for x in profile.attachment_radii_mm:
            shape = shape.cut(
                _cylinder(
                    servo_horns.PREPARED_HOLE_DIAMETER_MM / 2,
                    profile.arm_thickness_mm + 0.2,
                    (x, profile.blade_bottom_mm - 0.1, 0),
                )
            )
    return _one_solid(shape, profile.label)


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
    """One piece, two short through-slots and flat seats; no cap or head recess."""
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
    # Keep the full 1.5 mm shaft-stop floor.
    shape = shape.cut(
        shaft_frame_shape(
            _d_section(SHAFT_START_Y, SHAFT_SOCKET_LENGTH + 0.1, SHAFT_SOCKET_CLEARANCE)
        )
    )
    # Short radial slots preserve factory spacing while allowing print/assembly
    # variation. The nearer joint at 6.8 mm clears the shaft boss without a
    # head-relief channel or a recessed nut seat.
    for x, z in HORN_BOLT_CENTRES:
        shape = shape.cut(
            capsule(
                SLOT_WIDTH / 2,
                HORN_ADAPTER_SLOT_ALLOWANCE,
                HORN_HEIGHT - 0.1,
                PLATE_FRONT_Y - HORN_HEIGHT + 0.2,
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
    return _one_solid(
        shape, "OEM half-arm adapter with two tolerance slots and an open register"
    )


def service_envelope(*, retain_screws=False):
    """Fill forward details while preserving the root pocket and, when needed, bolts."""
    actual = adapter_shape()
    b = actual.BoundBox
    rear = actual.common(
        box(
            b.XLength + 2,
            HORN_HEIGHT - BODY_BACK_Y,
            b.ZLength + 2,
            (b.XMin - 1, BODY_BACK_Y, b.ZMin - 1),
        )
    )
    plate = box(
        PLATE_X_MAX - PLATE_X_MIN,
        PLATE_FRONT_Y - HORN_HEIGHT,
        2 * PLATE_HALF_WIDTH,
        (PLATE_X_MIN, HORN_HEIGHT, -PLATE_HALF_WIDTH),
    )
    plate = plate.cut(
        _cylinder(
            OEM_HEAD_CAVITY_RADIUS,
            OEM_HEAD_CAVITY_TOP_Y - HORN_HEIGHT,
            (0, HORN_HEIGHT, 0),
        )
    )
    if retain_screws:
        for x, z in HORN_BOLT_CENTRES:
            plate = plate.cut(
                capsule(
                    SLOT_WIDTH / 2,
                    HORN_ADAPTER_SLOT_ALLOWANCE,
                    HORN_HEIGHT - 0.1,
                    PLATE_FRONT_Y - HORN_HEIGHT + 0.2,
                    x,
                    z,
                )
            )
    front = box(8, SHAFT_SOCKET_LENGTH, 10.5, (-4, SHAFT_START_Y, -6.5))
    envelope = union([rear, plate, front]).removeSplitter()
    if actual.cut(envelope).Volume > 1e-5:
        raise RuntimeError("Adapter service envelope must contain the installed solid")
    return envelope


def fastener_positions(profile=None):
    """Two factory hole axes locate the rear screws and front nuts."""
    profile = profile or servo_horns.profile()
    result = []
    for x in profile.attachment_radii_mm:
        row = {"screw": (x, FASTENER_SEAT_Y, 0)}
        if not profile.threaded:
            row["screw"] = (x, profile.blade_bottom_mm, 0)
            row["nut"] = (x, FASTENER_SEAT_Y, 0)
        result.append(row)
    return tuple(result)


def horn_hardware_shapes(profile=None):
    """Profile hardware in horn coordinates, shared by CAD and profile checks."""
    from . import purchased_hardware

    profile = profile or servo_horns.profile()
    result = []
    for label, anchors in zip(("Near", "Far"), fastener_positions(profile)):
        if profile.threaded:
            screw = purchased_hardware.servo_screw_shape(profile.screw_length_mm).copy()
            direction = V(*BOLT_DIRECTION)
        else:
            screw = (
                Part.makeCylinder(
                    servo_horns.KST_SCREW_HEAD_DIAMETER_MM / 2,
                    servo_horns.KST_SCREW_HEAD_HEIGHT_MM,
                    V(0, 0, -servo_horns.KST_SCREW_HEAD_HEIGHT_MM),
                )
                .fuse(Part.makeCylinder(0.7, profile.screw_length_mm))
                .removeSplitter()
            )
            direction = V(0, 1, 0)
        screw.Placement = App.Placement(
            V(*anchors["screw"]), App.Rotation(V(0, 0, 1), direction)
        )
        result.append((label + "Bolt", screw, profile.screw_sku))
        if not profile.threaded:
            nut = (
                purchased_hardware.hex_prism(
                    servo_horns.NUT_AF_MM, servo_horns.NUT_HEIGHT_MM
                )
                .cut(
                    Part.makeCylinder(
                        0.7, servo_horns.NUT_HEIGHT_MM + 0.2, V(0, 0, -0.1)
                    )
                )
                .removeSplitter()
            )
            nut.Placement = App.Placement(
                V(*anchors["nut"]), App.Rotation(V(0, 0, 1), V(0, 1, 0))
            )
            result.append((label + "Nut", nut, "M1_4_HEX_NUT_DIN934"))
    return tuple(result)


def shaft_fastener_positions():
    return {
        "screw": tuple(shaft_frame_point(SHAFT_SCREW_HEAD_X, SHAFT_CLAMP_Y, 0)),
        "nut": tuple(shaft_frame_point(SHAFT_NUT_SEAT_X, SHAFT_CLAMP_Y, 0)),
        "direction": tuple(shaft_frame_point(*SHAFT_BOLT_DIRECTION)),
        "length": SHAFT_SCREW_LENGTH,
    }


def assembly_contract(profile=None):
    from .oem_servo_horn import STEP_SHA256

    profile = profile or servo_horns.profile()
    return {
        "horn_sku": profile.sku,
        "profile": profile.key,
        "x06_compatibility_basis": "Manufacturer-supplied nominal STEP of the included X06 half arm 1; delivered spline fit remains unmeasured.",
        "manufacturer_geometry_sha256": STEP_SHA256,
        "factory_threads": "Plain holes: Ø0.8 at X4.5; Ø1 at X6.8,10,13.2. Not tapped.",
        "factory_hole_centres_xz_mm": tuple((x, 0.0) for x, _ in profile.holes),
        "attachment_radii_mm": profile.attachment_radii_mm,
        "horn_requires_drilling": True,
        "preparation": servo_horns.preparation_note(profile),
        "physical_concentricity_verified": False,
        "axial_envelope_measured": False,
        "nominal_axial_geometry_sourced": True,
        "axial_envelope_scope": "Manufacturer STEP establishes nominal 3.5 mm total height, 2 mm blade and 2.5 mm spline cavity. Physical installed seating, centre screw and delivered tolerances are unmeasured. The 0.2 mm case gap remains a design allowance.",
        "nominal_arm_thickness_mm": profile.arm_thickness_mm,
        "adapter_slot_width_mm": SLOT_WIDTH,
        "adapter_slot_centres_x_mm": profile.attachment_radii_mm,
        "adapter_slot_centre_allowance_mm": HORN_ADAPTER_SLOT_ALLOWANCE,
        "adapter_slot_overall_length_mm": SLOT_WIDTH + 2 * HORN_ADAPTER_SLOT_ALLOWANCE,
        "register_radial_clearance_mm": REGISTER_INNER_RADIUS
        - profile.root_diameter_mm / 2,
        "register_engagement_mm": REGISTER_ENGAGEMENT,
        "register_scope": "Open C seat follows the nominal Ø7 root with 0.15 mm radial trial clearance. It limits rearward/side motion without enclosing the arm. Fit the root seat evenly, check metal-stub alignment and free mesh before clamping; nominal surfaces are not precision pilots or proof of zero runout.",
        "assembly_adjustment": "Two short 1.8 x 2.4 mm radial slots centred at 6.8/13.2 mm absorb print and hole-preparation error. Align the root and axes before tightening both joints. Do not use loose screws or slots as operating compliance. Finish interfering print surfaces rather than pulling misaligned parts together with screws.",
        "fastener_grip_mm": FASTENER_SEAT_Y - profile.height_mm,
        "total_horn_and_adapter_grip_mm": FASTENER_SEAT_Y - profile.blade_bottom_mm,
        "screw_length_mm": profile.screw_length_mm,
        "nuts_per_side": 2,
        "minimum_front_nut_af_mm": servo_horns.NUT_MIN_AF_MM,
        "screw_thread_diameter_mm": HORN_CLAMP_THREAD_DIAMETER,
        "nominal_thread_engagement_mm": servo_horns.NUT_HEIGHT_MM,
        "nominal_front_nut_projection_mm": profile.blade_bottom_mm
        + profile.screw_length_mm
        - FASTENER_SEAT_Y
        - servo_horns.NUT_HEIGHT_MM,
        "thread_engagement_scope": "Nominal 2 mm horn + 3.6 mm adapter + 1.2 mm nut = 6.8 mm stack; M1.4x8 gives 1.2 mm tip projection beyond the nut. Rear head seats on the horn, front nut on the flat adapter; no recesses or washers. Actual thread runout, head size, plastic bearing stress and retention need inspection.",
        "centre_screw_service": "Remove both output gears and the paired servo/input module; remove selected driver gear and metal stub, release servo ears, then withdraw servo+horn+adapter together. Off the bridge, remove front nuts and adapter before accessing the OEM centre screw. For assembly insert rear M1.4 screws into the detached prepared horn, install horn and OEM centre screw on the free servo, fit adapter/front nuts, and clamp with a <=1.5 mm rear holding-tool stem. Refit the complete servo unit, stub and gear. Rear tool access past the assembled bridge is not assumed; the shaft-stop floor stays intact.",
    }


def metrics():
    contract = assembly_contract()
    return {
        "reference_profile": servo_horns.SELECTED_PROFILE,
        "reference_scope": "Both sides use the same selected manufacturer half arm 1 and adapter.",
        "selected_horns": {
            side: servo_horns.profile(side=side).sku
            for side in servo_horns.SELECTED_BY_SIDE
        },
        "sources": [item.source for item in servo_horns.PROFILES.values()],
        "horn_shape_scope": "Exact manufacturer half-arm-1 STEP with only two specified factory-hole enlargements. Older metal-horn alternatives are superseded. Nominal geometry does not establish received tolerance or installed seating.",
        "supported_profiles": {
            key: assembly_contract(item) for key, item in servo_horns.PROFILES.items()
        },
        "selected_by_side": dict(servo_horns.SELECTED_BY_SIDE),
        "assembly_contract": contract,
        "horn_factory_hole_centres_xz_mm": HORN_FACTORY_HOLE_CENTRES,
        "horn_adapter_slot_width_mm": SLOT_WIDTH,
        "horn_adapter_slot_centres_x_mm": servo_horns.profile().attachment_radii_mm,
        "horn_adapter_slot_centre_allowance_mm": HORN_ADAPTER_SLOT_ALLOWANCE,
        "horn_clamp_thread_diameter_mm": HORN_CLAMP_THREAD_DIAMETER,
        "horn_clamp_screw_length_mm": HORN_CLAMP_LENGTH,
        "horn_clamp_grip_mm": contract["fastener_grip_mm"],
        "horn_clamp_nuts_by_side": {
            side: 0 if servo_horns.profile(side=side).threaded else 2
            for side in servo_horns.SELECTED_BY_SIDE
        },
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
        "common_clamp_screws_per_side": 3,
        "shaft_retention": "Nominal Ø3x18 mm 304 stock, full-length 0.5 mm flat, 8 mm D socket and radial M2 clamp. Full 1.5 mm stop floor; selected gear M3 screw and 2 mm end reserve retained. No input bearing. Actual shaft fit and retention require inspection.",
        "assembly": contract["assembly_adjustment"]
        + " "
        + contract["centre_screw_service"],
        "qualification": "Manufacturer nominal geometry, not manufactured-part qualification. Enlarge the selected existing factory holes without transferring new centres; the C-seat and short slots do not certify delivered concentricity, retention or zero backlash. Check actual axial seating, hardware, runout, full motion and load.",
    }
