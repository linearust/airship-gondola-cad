"""Round-hole/slot adapter for the manufacturer-supplied X06 half arm 1.

An open root register and near round hole bound assembly displacement. The far
short slot accommodates hole-pitch variation before both joints are tightened.
Local rotation is +Y and the arm points +X; shaft and gear planes stay fixed.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import box, union
from gondola.contracts import servo_horns

V = App.Vector
HORN_PROFILE = servo_horns.profile()
HORN_SKU = HORN_PROFILE.sku
HORN_MATERIAL = "Supplied horn material unverified"
HORN_BOTTOM_Y = 7.4
# Nominal manufacturer dimensions, distinct from received/installed measurements.
HORN_HEIGHT = HORN_PROFILE.height_mm
HORN_BLADE_BOTTOM = HORN_PROFILE.blade_bottom_mm
HORN_FACTORY_HOLE_CENTRES = tuple((x, 0.0) for x, _ in HORN_PROFILE.holes)
HORN_BOLT_CENTRES = tuple((x, 0.0) for x in HORN_PROFILE.attachment_radii_mm)
HORN_ADAPTER_SLOT_ALLOWANCE = 0.3
HORN_ADAPTER_OPENING_ALLOWANCES = (0.0, HORN_ADAPTER_SLOT_ALLOWANCE)
SLOT_WIDTH = 1.8
HORN_CLAMP_THREAD_DIAMETER = 1.4
HORN_CLAMP_LENGTH = HORN_PROFILE.screw_length_mm
BOLT_DIRECTION = (0, 1, 0)

# Preserve the selected gears' established axial plane and output shaft fit.
PLATE_FRONT_Y = 7.1
HORN_NUT_RECESS_DEPTH = 0.6
HORN_NUT_POCKET_AF = 3.2
HORN_NUT_RADIAL_EXTENSION = 0.1
FASTENER_SEAT_Y = PLATE_FRONT_Y - HORN_NUT_RECESS_DEPTH
PLATE_HALF_WIDTH = 5.15
PLATE_TIP_RADIUS = 2.8
PLATE_TIP_X = HORN_BOLT_CENTRES[-1][0]
PLATE_X_MIN, PLATE_X_MAX = -PLATE_HALF_WIDTH, PLATE_TIP_X + PLATE_TIP_RADIUS
REGISTER_RADIUS = HORN_PROFILE.root_diameter_mm / 2
REGISTER_CLEARANCE = 0.15
REGISTER_INNER_RADIUS = REGISTER_RADIUS + REGISTER_CLEARANCE
REGISTER_OUTER_RADIUS = 5.15
REGISTER_ENGAGEMENT = 1.5
REGISTER_OPEN_X = 0.7
BODY_BACK_Y = HORN_HEIGHT - REGISTER_ENGAGEMENT
OEM_HEAD_CAVITY_RADIUS = 2.5
OEM_HEAD_CAVITY_TOP_Y = 5.6
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


def plate_blank():
    """Tangent rounded taper follows the selected horn and its two nut seats."""
    radius, tip_radius = PLATE_HALF_WIDTH, PLATE_TIP_RADIUS
    slope = (radius - tip_radius) / PLATE_TIP_X
    normal_z = math.sqrt(1 - slope**2)
    x0, z0 = radius * slope, radius * normal_z
    x1, z1 = PLATE_TIP_X + tip_radius * slope, tip_radius * normal_z
    corners = [
        V(x0, HORN_HEIGHT, -z0),
        V(x1, HORN_HEIGHT, -z1),
        V(x1, HORN_HEIGHT, z1),
        V(x0, HORN_HEIGHT, z0),
    ]
    thickness = PLATE_FRONT_Y - HORN_HEIGHT
    web = Part.Face(Part.makePolygon(corners + [corners[0]])).extrude(
        V(0, thickness, 0)
    )
    return union(
        [
            _cylinder(radius, thickness, (0, HORN_HEIGHT, 0)),
            _cylinder(tip_radius, thickness, (PLATE_TIP_X, HORN_HEIGHT, 0)),
            web,
        ]
    ).removeSplitter()


def horn_nut_recess(x, z, allowance):
    """Shallow hexagon elongated radially; its parallel flats still stop rotation."""
    radius = HORN_NUT_POCKET_AF / math.sqrt(3)
    extension = HORN_NUT_RADIAL_EXTENSION + allowance
    corners = [
        V(
            x
            + radius * math.cos(math.pi * i / 3)
            + (extension if i in (0, 1, 5) else -extension),
            FASTENER_SEAT_Y,
            z + radius * math.sin(math.pi * i / 3),
        )
        for i in range(6)
    ]
    return Part.Face(Part.makePolygon(corners + [corners[0]])).extrude(
        V(0, HORN_NUT_RECESS_DEPTH + 0.1, 0)
    )


def adapter_shape():
    """One piece with round/far-slot holes and shallow radially floating nut seats."""
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
            plate_blank(),
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
    # The near round opening bounds translation along the open register. Only
    # the far joint is slotted, so pitch variation does not force the two holes.
    # Shallow elongated nut pockets retain radial fitting freedom without raised walls.
    for (x, z), allowance in zip(HORN_BOLT_CENTRES, HORN_ADAPTER_OPENING_ALLOWANCES):
        shape = shape.cut(
            capsule(
                SLOT_WIDTH / 2,
                allowance,
                HORN_HEIGHT - 0.1,
                PLATE_FRONT_Y - HORN_HEIGHT + 0.2,
                x,
                z,
            )
        )
        shape = shape.cut(horn_nut_recess(x, z, allowance))
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
        shape, "OEM half-arm adapter with a round hole, far slot and open register"
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
    plate = plate_blank()
    plate = plate.cut(
        _cylinder(
            OEM_HEAD_CAVITY_RADIUS,
            OEM_HEAD_CAVITY_TOP_Y - HORN_HEIGHT,
            (0, HORN_HEIGHT, 0),
        )
    )
    if retain_screws:
        for (x, z), allowance in zip(
            HORN_BOLT_CENTRES, HORN_ADAPTER_OPENING_ALLOWANCES
        ):
            plate = plate.cut(
                capsule(
                    SLOT_WIDTH / 2,
                    allowance,
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
    return tuple(
        {"screw": (x, profile.blade_bottom_mm, 0), "nut": (x, FASTENER_SEAT_Y, 0)}
        for x in profile.attachment_radii_mm
    )


def horn_hardware_shapes(profile=None):
    """Rear M1.4 screws and front nuts; the OEM horn has plain holes."""
    from . import purchased_hardware

    profile = profile or servo_horns.profile()
    result = []
    rotation = App.Rotation(V(0, 0, 1), V(*BOLT_DIRECTION))
    radius = HORN_CLAMP_THREAD_DIAMETER / 2
    for label, anchors in zip(("Near", "Far"), fastener_positions(profile)):
        screw = (
            Part.makeCylinder(
                servo_horns.KST_SCREW_HEAD_DIAMETER_MM / 2,
                servo_horns.KST_SCREW_HEAD_HEIGHT_MM,
                V(0, 0, -servo_horns.KST_SCREW_HEAD_HEIGHT_MM),
            )
            .fuse(Part.makeCylinder(radius, profile.screw_length_mm))
            .removeSplitter()
        )
        screw.Placement = App.Placement(V(*anchors["screw"]), rotation)
        result.append((label + "Bolt", screw, profile.screw_sku))
        nut = (
            purchased_hardware.hex_prism(
                servo_horns.NUT_AF_MM, servo_horns.NUT_HEIGHT_MM
            )
            .cut(
                Part.makeCylinder(
                    radius, servo_horns.NUT_HEIGHT_MM + 0.2, V(0, 0, -0.1)
                )
            )
            .removeSplitter()
        )
        nut.Placement = App.Placement(V(*anchors["nut"]), rotation)
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
        "adapter_backing_outline": "Tangent rounded taper: root radius5.15mm, tip radius2.8mm centred at13.2mm. Retains nominal OEM blade support and both nut seats; no enclosing arm walls.",
        "adapter_round_hole_x_mm": profile.attachment_radii_mm[0],
        "adapter_round_hole_diameter_mm": SLOT_WIDTH,
        "adapter_slot_width_mm": SLOT_WIDTH,
        "adapter_slot_centres_x_mm": profile.attachment_radii_mm[1:],
        "adapter_slot_centre_allowance_mm": HORN_ADAPTER_SLOT_ALLOWANCE,
        "adapter_slot_overall_length_mm": SLOT_WIDTH + 2 * HORN_ADAPTER_SLOT_ALLOWANCE,
        "register_radial_clearance_mm": REGISTER_INNER_RADIUS
        - profile.root_diameter_mm / 2,
        "register_engagement_mm": REGISTER_ENGAGEMENT,
        "register_scope": "Open C seat follows the nominal Ø7 root with 0.15 mm radial trial clearance. It limits rearward/side motion without enclosing the arm. Fit the root seat evenly, check metal-stub alignment and free mesh before clamping; nominal surfaces are not precision pilots or proof of zero runout.",
        "assembly_adjustment": "A diameter 1.8 mm round hole at 6.8 mm bounds motion along the open root seat; a 1.8 x 2.4 mm radial slot at 13.2 mm accommodates pitch variation. For nominal diameter 1.4 mm shanks, near centre travel is 0.2 mm radially and far travel is 0.5 mm along/0.2 mm across the arm before other features intervene; the shallow nut pockets restrict nominal AF3.0 nut centres to +/-0.1 mm across the arm. The root seat and horn holes can restrict the final fit further. These are loose-part geometric limits, not a rectangular tolerance box or operating play. Align the input axis and check runout before tightening both joints. Finish interfering print surfaces rather than pulling misaligned parts together with screws.",
        "nut_recess": {
            "depth_mm": HORN_NUT_RECESS_DEPTH,
            "across_parallel_flats_mm": HORN_NUT_POCKET_AF,
            "radial_extensions_mm": tuple(
                HORN_NUT_RADIAL_EXTENSION + value
                for value in HORN_ADAPTER_OPENING_ALLOWANCES
            ),
            "remaining_adapter_floor_mm": FASTENER_SEAT_Y - profile.height_mm,
            "finished_flat_gap_acceptance_mm": [3.1, 3.25],
            "scope": "Shallow open hex pockets restrain ordinary AF2.9..3.0 M1.4 nuts; no axial captivity or tightening-torque qualification. Their radial extension retains nominal screw-centre travel +/-0.2 and +/-0.5 mm; the AF3.0 nut limits transverse centre travel to +/-0.1 mm. Confirm actual chamfer/flank engagement, finish for free insertion and full floor seating, and reject rotation or floor damage. These are fit acceptance targets, not guaranteed PA12 process tolerances.",
        },
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
        "thread_engagement_scope": "Nominal 2 mm horn + 3.0 mm adapter floor + 1.2 mm nut = 6.2 mm stack; M1.4x8 gives 1.8 mm tip projection beyond the nut. Rear head seats on the horn; the front nut seats 0.6 mm below the plate face. No washers. Actual thread runout, head size, plastic bearing stress and retention need inspection.",
        "centre_screw_service": "Remove both output gears and the paired servo/input module; remove selected driver gear and metal stub, withdraw both M1.6 ear screws and release their pocket-held nuts, then withdraw servo+horn+adapter. Off the bridge, remove front nuts and adapter before accessing the OEM centre screw. For assembly insert rear M1.4 screws into the detached prepared horn, install horn and OEM centre screw on the free servo, fit adapter/front nuts, and turn the rear screws using a <=1.5 mm tool stem while the pockets restrain the nuts. For removal turn the rear screw to release the pocket-held nut; its exposed portion remains accessible to fine pliers once it leaves the pocket. Refit the complete servo unit and both ear fastener pairs, then the stub and gear. Rear tool access past the assembled bridge is not assumed; the shaft-stop floor stays intact.",
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
        "horn_adapter_round_hole_x_mm": HORN_PROFILE.attachment_radii_mm[0],
        "horn_adapter_round_hole_diameter_mm": SLOT_WIDTH,
        "horn_adapter_slot_width_mm": SLOT_WIDTH,
        "horn_adapter_slot_centres_x_mm": HORN_PROFILE.attachment_radii_mm[1:],
        "horn_adapter_slot_centre_allowance_mm": HORN_ADAPTER_SLOT_ALLOWANCE,
        "horn_clamp_thread_diameter_mm": HORN_CLAMP_THREAD_DIAMETER,
        "horn_clamp_screw_length_mm": HORN_CLAMP_LENGTH,
        "horn_clamp_grip_mm": contract["fastener_grip_mm"],
        "horn_clamp_nuts_by_side": {side: 2 for side in servo_horns.SELECTED_BY_SIDE},
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
        "adapter_axial_release_travel_mm": RETAINED_BOLT_RELEASE_TRAVEL,
        "common_clamp_screws_per_side": 3,
        "shaft_retention": "Nominal Ø3x18 mm 304 stock, full-length 0.5 mm flat, 8 mm D socket and radial M2 clamp. Full 1.5 mm stop floor; selected gear M3 screw and 2 mm end reserve retained. No input bearing. Actual shaft fit and retention require inspection.",
        "assembly": contract["assembly_adjustment"]
        + " "
        + contract["centre_screw_service"],
        "qualification": "Manufacturer nominal geometry, not manufactured-part qualification. Enlarge the selected existing factory holes without transferring new centres; the C-seat, near hole and far slot do not certify delivered concentricity, retention or zero backlash. Check actual axial seating, hardware, runout, full motion and load.",
    }
