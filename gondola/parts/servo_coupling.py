"""Three-opening M1 adapter for the unmodified manufacturer X06 half arm 1.

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
# Installed end joints stay at6.8/13.2. The centre10mm opening is optional only.
HORN_ADAPTER_OPENING_CENTRES = ((6.8, 0.0), (10.0, 0.0), (13.2, 0.0))
HORN_ADAPTER_OPENING_ALLOWANCES = (0.0, 0.2, HORN_ADAPTER_SLOT_ALLOWANCE)
HORN_INSTALLED_OPENING_ALLOWANCES = (0.0, HORN_ADAPTER_SLOT_ALLOWANCE)
SLOT_WIDTH = 1.2
HORN_CLAMP_THREAD_DIAMETER = 1.0
HORN_CLAMP_LENGTH = HORN_PROFILE.screw_length_mm
BOLT_DIRECTION = (0, 1, 0)

# Preserve the selected gears' established axial plane and output shaft fit.
PLATE_FRONT_Y = 7.1
HORN_NUT_RECESS_DEPTH = 1.1
HORN_NUT_POCKET_AF = 2.6
# Shared flat-sided trough avoids fragile webs between three close nut positions.
# It opens at the tip, retaining the full lower2.5mm bearing floor.
HORN_NUT_TROUGH_START_X = 5.05
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
SHAFT_LENGTH = 35.0
SHAFT_FLAT_DEPTH = 0.5
SHAFT_FLAT_LENGTH = 16.0
SHAFT_SOCKET_LENGTH = 8.0
# The jack screw must react against a centred circular journal, rather than
# pushing the shaft across a radial gap and making the gear run eccentrically.
# Finish this nominal contact fit to the actual shaft. Only the filed flat is
# relieved; it is not the radial locating datum.
SHAFT_SOCKET_CLEARANCE = 0.0
SHAFT_SOCKET_FLAT_CLEARANCE = 0.05
GEAR_START_Y = SHAFT_START_Y + SHAFT_SOCKET_LENGTH
GEAR_LENGTH = 8.0
SHAFT_CLAMP_Y = SHAFT_START_Y + SHAFT_SOCKET_LENGTH / 2 + 0.4
SHAFT_CLAMP_CLOCK_DEG = 240.0
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


def _d_section(y, length, clearance=0.0, *, flat_clearance=None):
    radius = SHAFT_DIAMETER / 2 + clearance
    shape = _cylinder(radius, length, (0, y, 0))
    flat_clearance = clearance if flat_clearance is None else flat_clearance
    flat_x = -(SHAFT_DIAMETER / 2 - SHAFT_FLAT_DEPTH) - flat_clearance
    return shape.cut(box(4 + flat_x, length + 0.2, 4, (-4, y - 0.1, -2)))


def _one_solid(shape, name):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError(name + " must be one valid solid")
    return shape


def driver_shaft_shape():
    """Selected Ø3×35 stock: proximal16mm flat, uninterrupted round journal."""
    shaft = _cylinder(SHAFT_DIAMETER / 2, SHAFT_LENGTH, (0, SHAFT_START_Y, 0))
    flat_x = -(SHAFT_DIAMETER / 2 - SHAFT_FLAT_DEPTH)
    shaft = shaft.cut(
        box(
            4 + flat_x,
            SHAFT_FLAT_LENGTH + 0.1,
            4,
            (-4, SHAFT_START_Y - 0.1, -2),
        )
    )
    return _one_solid(shaft_frame_shape(shaft), "Driver metal shaft")


def horn_shape(profile=None):
    """Exact unmodified nominal OEM STEP; no preparation operation is supported."""
    from .oem_servo_horn import normalized_shape

    profile = profile or servo_horns.profile()
    return normalized_shape()


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


def horn_nut_trough():
    """One open-ended recess with parallel antirotation flats and no thin dividers."""
    return box(
        PLATE_X_MAX - HORN_NUT_TROUGH_START_X + 0.2,
        HORN_NUT_RECESS_DEPTH + 0.1,
        HORN_NUT_POCKET_AF,
        (HORN_NUT_TROUGH_START_X, FASTENER_SEAT_Y, -HORN_NUT_POCKET_AF / 2),
    )


def adapter_shape():
    """One piece with three M1 openings and a shared open-ended nut trough."""
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
            _d_section(
                SHAFT_START_Y,
                SHAFT_SOCKET_LENGTH + 0.1,
                SHAFT_SOCKET_CLEARANCE,
                flat_clearance=SHAFT_SOCKET_FLAT_CLEARANCE,
            )
        )
    )
    # The near round opening bounds translation along the open register. Only
    # the far joint is slotted, so pitch variation does not force the two holes.
    # Shallow elongated nut pockets retain radial fitting freedom without raised walls.
    for (x, z), allowance in zip(
        HORN_ADAPTER_OPENING_CENTRES, HORN_ADAPTER_OPENING_ALLOWANCES
    ):
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
    shape = shape.cut(horn_nut_trough())
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
            HORN_ADAPTER_OPENING_CENTRES, HORN_ADAPTER_OPENING_ALLOWANCES
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
    front = shaft_frame_shape(
        box(10.5, SHAFT_SOCKET_LENGTH, 8, (-6.5, SHAFT_START_Y, -4))
    )
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
    """Rear M1 external-hex bolts and front nuts; the OEM horn stays unmodified."""
    from . import purchased_hardware

    profile = profile or servo_horns.profile()
    result = []
    rotation = App.Rotation(V(0, 0, 1), V(*BOLT_DIRECTION))
    radius = HORN_CLAMP_THREAD_DIAMETER / 2
    for label, anchors in zip(("Near", "Far"), fastener_positions(profile)):
        head = purchased_hardware.hex_prism(
            servo_horns.KST_SCREW_HEAD_AF_MM,
            servo_horns.KST_SCREW_HEAD_HEIGHT_MM,
        )
        head.translate(V(0, 0, -servo_horns.KST_SCREW_HEAD_HEIGHT_MM))
        screw = head.fuse(
            Part.makeCylinder(radius, profile.screw_length_mm)
        ).removeSplitter()
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
        result.append((label + "Nut", nut, servo_horns.NUT_SKU))
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
        "x06_compatibility_basis": "Manufacturer-supplied nominal STEP of the included X06 half arm1, unchanged; delivered spline and M1 slip fits remain unmeasured.",
        "manufacturer_geometry_sha256": STEP_SHA256,
        "factory_threads": "Unmodified plain holes: Ø0.8 atX4.5; Ø1 atX6.8,10,13.2. Not tapped. The Ø0.8 hole is not M1-compatible.",
        "factory_hole_centres_xz_mm": tuple((x, 0.0) for x, _ in profile.holes),
        "attachment_radii_mm": profile.attachment_radii_mm,
        "optional_attachment_radius_mm": 10.0,
        "optional_middle_fastener_installed": False,
        "horn_requires_drilling": False,
        "preparation": servo_horns.preparation_note(profile),
        "physical_concentricity_verified": False,
        "axial_envelope_measured": False,
        "nominal_axial_geometry_sourced": True,
        "axial_envelope_scope": "Manufacturer STEP establishes nominal3.5mm total height,2mm blade and2.5mm spline cavity. Physical installed seating, centre screw and delivered tolerances are unmeasured. The0.2mm case gap remains a design allowance.",
        "nominal_arm_thickness_mm": profile.arm_thickness_mm,
        "adapter_backing_outline": "Tangent rounded taper: root radius5.15mm, tip radius2.8mm centred at13.2mm. Retains nominal OEM blade support and continuous2.5mm nut floor; no enclosing arm walls.",
        "adapter_round_hole_x_mm": 6.8,
        "adapter_round_hole_diameter_mm": SLOT_WIDTH,
        "adapter_slot_width_mm": SLOT_WIDTH,
        "adapter_slot_centres_x_mm": (10.0, 13.2),
        "adapter_slot_centre_allowances_mm": (0.2, 0.3),
        "adapter_slot_overall_lengths_mm": (1.6, 1.8),
        "adapter_slot_centre_allowance_mm": HORN_ADAPTER_SLOT_ALLOWANCE,
        "adapter_slot_overall_length_mm": round(
            SLOT_WIDTH + 2 * HORN_ADAPTER_SLOT_ALLOWANCE, 6
        ),
        "register_radial_clearance_mm": REGISTER_INNER_RADIUS
        - profile.root_diameter_mm / 2,
        "register_engagement_mm": REGISTER_ENGAGEMENT,
        "register_scope": "Open C seat follows the nominal Ø7 root with0.15mm radial trial clearance. It limits rearward/side motion without enclosing the arm. Fit the root seat evenly, check metal-stub alignment and free mesh before clamping; nominal surfaces are not precision pilots or proof of zero runout.",
        "assembly_adjustment": "NearØ1.2 round hole at6.8mm bounds translation; the1.2x1.8 far slot at13.2mm accommodates pitch variation. M1 nominal shank-centre travel is±0.1mm near and±0.4mm far along the arm,±0.1mm transversely. The optional10mm opening is1.2x1.6mm (±0.3mm along-arm shank travel). Root/horn fit and adjacent hardware further restrict simultaneous positions; these are loose-part geometric limits, not operating play. Align the input shaft, seat the horn face, then tighten both end joints and check runout. Never pull misaligned parts together with bolts.",
        "nut_recess": {
            "kind": "shared_open_tip_parallel_flat_trough",
            "depth_mm": HORN_NUT_RECESS_DEPTH,
            "across_parallel_flats_mm": HORN_NUT_POCKET_AF,
            "start_x_mm": HORN_NUT_TROUGH_START_X,
            "open_at_tip": True,
            "remaining_adapter_floor_mm": FASTENER_SEAT_Y - profile.height_mm,
            "finished_flat_gap_acceptance_mm": [2.55, 2.65],
            "scope": "Shared trough restrains ordinary AF2.4..2.5 M1 nuts without thin partitions. Its2.5mm floor remains continuous except for declared bolt openings. Nuts are below the plate face at seating; reverse the rear bolt while holding its head axially seated to advance the nut, then grip the exposed nut with fine pliers. Check actual chamfer/flank engagement and free insertion; no axial captivity, tightening-torque or PA12 dimensional guarantee.",
        },
        "fastener_grip_mm": FASTENER_SEAT_Y - profile.height_mm,
        "total_horn_and_adapter_grip_mm": FASTENER_SEAT_Y - profile.blade_bottom_mm,
        "screw_length_mm": profile.screw_length_mm,
        "screw_length_basis": "Selected6mm nominal design length; the user's owned length is not measured or implied.",
        "nuts_per_side": 2,
        "minimum_front_nut_af_mm": servo_horns.NUT_MIN_AF_MM,
        "screw_thread_diameter_mm": HORN_CLAMP_THREAD_DIAMETER,
        "screw_head": {
            "drive": "external_hex",
            "maximum_across_flats_mm": servo_horns.KST_SCREW_HEAD_AF_MM,
            "maximum_height_mm": servo_horns.KST_SCREW_HEAD_HEIGHT_MM,
            "swept_diameter_mm": servo_horns.KST_SCREW_HEAD_DIAMETER_MM,
            "scope": "Declared geometric acceptance envelope, not a universal M1 hex-head standard or measurement of owned hardware. ISO4017 begins atM1.6.",
        },
        "hardware_material": servo_horns.HARDWARE_MATERIAL,
        "nominal_thread_engagement_mm": servo_horns.NUT_HEIGHT_MM,
        "nominal_front_nut_projection_mm": profile.blade_bottom_mm
        + profile.screw_length_mm
        - FASTENER_SEAT_Y
        - servo_horns.NUT_HEIGHT_MM,
        "thread_engagement_scope": "Nominal2mm horn+2.5mm adapter floor+0.8mm nut=5.3mm stack; design M1x6 gives0.7mm tip projection. No washers. Actual length, thread runout, chamfers, full nut engagement, head bearing and retention require inspection.",
        "rear_tool_envelope": {
            "type": "external_hex_nutdriver",
            "diameter_mm": servo_horns.KST_TOOL_DIAMETER_MM,
            "length_mm": servo_horns.KST_TOOL_LENGTH_MM,
            "source": servo_horns.HEX_TOOL_DIMENSION_SOURCE,
            "scope": "Wera2069 2.5mm example envelope; not proof of user's tool size. Check the two default end bolts with the complete servo unit off the frame and horn in neutral arm orientation.",
        },
        "optional_middle_scope": "The10mm opening is a candidate, not an installed third fastener or qualified alternate configuration. At3.2mm adjacent pitch, AF2.5 hexes have only0.313mm nominal corner-to-corner gap. A5.7mm driver collides with adjacent heads; simultaneous three-bolt service needs a verified thinner tool (theoretical OD<=3.513mm for ideal AF2.5 heads), full hardware checks and renewed service verification. Do not force three bolts into unmatched holes.",
        "centre_screw_service": "Remove both output gears to unmesh. Keep the selected input neutral while supporting and parking only its output rotor90deg about module+Y. Support the48T driver, release its set screw and back off the input M2 jack0.2mm. Grip3.8mm of the round tip of the35mm shaft with side-entry fine pliers, beyond the fixed input support. Pull the shaft32mm forwardY, then60mm outwardX. Remove the loose driver60mm outwardX. Withdraw the selected servo's two M1.6 ear screws and nuts, then move its servo/horn/adapter13mm forwardY and60mm outwardX; mirror translation X/Y for Starboard. Input bearing and cap remain installed. Keep both M1 joints and OEM horn attached until off-frame. With the horn neutral on the bench, remove far front nut then near nut by turning each rear external-hex bolt with a<=5.7mm OD axial tool while keeping its head seated. The trough initially restrains the nut; after1.3mm lift use fine pliers. Remove nuts beyond the retained screw tips, then remove adapter to reach the OEM centre screw. For assembly insert rear bolts into the unmodified detached horn, fit horn/OEM centre screw on the free servo, fit adapter/front nuts, then align and tighten end joints. Reverse the compact-frame route; seat the ears, install driver/shaft, confirm free journal alignment without forcing the horn axis, then tighten clamps. Return the output rotor to neutral before refitting output gears and checking mesh. Actual tools and unmodeled gear set-screw access remain checks. Full shaft-stop floor stays intact.",
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
        "horn_shape_scope": "Exact unmodified manufacturer half-arm-1 STEP; all four factory holes retained. Older metal-horn alternatives are superseded. Nominal geometry does not establish received tolerance or installed seating.",
        "supported_profiles": {
            key: assembly_contract(item) for key, item in servo_horns.PROFILES.items()
        },
        "selected_by_side": dict(servo_horns.SELECTED_BY_SIDE),
        "assembly_contract": contract,
        "horn_factory_hole_centres_xz_mm": HORN_FACTORY_HOLE_CENTRES,
        "horn_adapter_round_hole_x_mm": HORN_PROFILE.attachment_radii_mm[0],
        "horn_adapter_round_hole_diameter_mm": SLOT_WIDTH,
        "horn_adapter_slot_width_mm": SLOT_WIDTH,
        "horn_adapter_slot_centres_x_mm": (10.0, 13.2),
        "horn_adapter_slot_centre_allowances_mm": (0.2, 0.3),
        "horn_adapter_slot_centre_allowance_mm": HORN_ADAPTER_SLOT_ALLOWANCE,
        "horn_clamp_thread_diameter_mm": HORN_CLAMP_THREAD_DIAMETER,
        "horn_clamp_screw_length_mm": HORN_CLAMP_LENGTH,
        "horn_clamp_grip_mm": contract["fastener_grip_mm"],
        "horn_clamp_nuts_by_side": {side: 2 for side in servo_horns.SELECTED_BY_SIDE},
        "gear_bore_diameter_mm": GEAR_BORE_DIAMETER,
        "driver_shaft_diameter_mm": SHAFT_DIAMETER,
        "driver_shaft_length_mm": SHAFT_LENGTH,
        "driver_shaft_flat_depth_mm": SHAFT_FLAT_DEPTH,
        "driver_shaft_flat_length_mm": SHAFT_FLAT_LENGTH,
        "driver_shaft_round_journal_start_from_horn_bottom_mm": SHAFT_START_Y
        + SHAFT_FLAT_LENGTH,
        "driver_shaft_flat_facing": "positive X / negative Z diagonal in horn-local coordinates; outward and downward on each mirrored servo",
        "driver_shaft_flat_normal_horn_local": list(shaft_frame_point(-1, 0, 0)),
        "driver_shaft_socket_length_mm": SHAFT_SOCKET_LENGTH,
        "driver_shaft_socket_clearance_mm": SHAFT_SOCKET_CLEARANCE,
        "driver_shaft_socket_flat_clearance_mm": SHAFT_SOCKET_FLAT_CLEARANCE,
        "driver_shaft_projection_beyond_gear_mm": SHAFT_START_Y
        + SHAFT_LENGTH
        - GEAR_START_Y
        - GEAR_LENGTH,
        "gear_start_from_horn_bottom_mm": GEAR_START_Y,
        "horn_long_side_walls_retained": False,
        "adapter_axial_release_travel_mm": RETAINED_BOLT_RELEASE_TRAVEL,
        "common_clamp_screws_per_side": 3,
        "shaft_retention": "Nominal Ø3x35 mm 304 stock with a0.5mm-deep proximal16mm flat through the8mm D socket and8mm gear; preserve the remaining19mm as a full round journal. One external3x6x2.5 bearing supports that journal beyond the driver. The nominalØ3 circular socket locates the shaft at the horn axis under the radialM2 jack; only the filed-flat side has0.05mm relief. Coupon-match and finish for hand insertion without radial rocking; reprint an oversized socket. Retain the full1.5mm stop floor, selected gearM3 screw and4.5mm tip beyond the input housing for side-entry plier service. Never file through the bearing journal or force a misaligned shaft, horn or bearing into axis alignment with fasteners. Actual horn runout, coaxiality, free rotation, fit, tool grip and loaded retention require inspection; the external bearing does not qualify the servo spline or horn concentricity.",
        "assembly": contract["assembly_adjustment"]
        + " "
        + contract["centre_screw_service"],
        "qualification": "Manufacturer nominal geometry, not manufactured-part qualification. Do not drill or force M1 bolts through factory holes; the C-seat, near hole and far slot do not certify delivered concentricity, retention or zero backlash. Check actual axial seating, hardware, runout, full motion and load.",
    }
