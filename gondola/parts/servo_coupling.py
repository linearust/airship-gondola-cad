"""One radial-slot adapter for three 15T/4 mm bought horn profiles.

The open root seat and slot provide assembly allowance before clamping, never
intentional operating looseness. KST's end pilot holes need stated preparation.
Local rotation is +Y and the arm points +X; the shaft and gear planes are fixed.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import box, union
from gondola.contracts import servo_horns

V = App.Vector
HORN_SKU = "ALI_PTK_15T_4MM_HORN"
HORN_MATERIAL = "Aluminium alloy (grade unspecified)"
HORN_BOTTOM_Y = 7.4
# Axial proxy retained for fit-prototype clearance only, not a seller dimension.
HORN_HEIGHT = 3.5
HORN_BLADE_THICKNESS = 1.6
HORN_BLADE_BOTTOM = HORN_HEIGHT - HORN_BLADE_THICKNESS
HORN_TIP_RADIUS = 2.0  # Unsourced rounded-tip envelope, not a locating datum.
HORN_RECESS_DEPTH = 2.5  # Smooth spline-space proxy; no spline is fabricated.
HORN_FACTORY_HOLE_CENTRES = ((6.6, 0.0), (9.4, 0.0), (12.2, 0.0))
# Third position is inferred equal pitch; the outer slot tolerates +/-0.4 mm.
HORN_BOLT_CENTRES = (HORN_FACTORY_HOLE_CENTRES[0], HORN_FACTORY_HOLE_CENTRES[2])
HORN_ADAPTER_HOLE_DIAMETERS = (2.2, 2.2)
HORN_ADAPTER_SLOT_ALLOWANCE = 0.4
SLOT_CENTRE_MIN = 4.3
SLOT_CENTRE_MAX = 13.4
SLOT_WIDTH = 2.2
SLOT_HEAD_WIDTH = 3.7
SLOT_HEAD_TOP_Y = 10.1
HORN_CLAMP_THREAD_DIAMETER = 1.6
HORN_CLAMP_LENGTH = 5.0
BOLT_DIRECTION = (0, -1, 0)
FASTENER_SEAT_Y = 7.1
HEAD_CLEARANCE_DIAMETER = 4.0
HORN_MIN_HEAD_BEARING_DIAMETER = 3.0

# Preserve the selected gears' established axial plane and output shaft fit.
PLATE_FRONT_Y = 7.1
PLATE_X_MIN, PLATE_X_MAX = -6.5, 16.0
PLATE_HALF_WIDTH = 5.0
REGISTER_RADIUS = max(p.root_diameter_mm / 2 for p in servo_horns.PROFILES.values())
REGISTER_CLEARANCE = 0.15
REGISTER_INNER_RADIUS = REGISTER_RADIUS + REGISTER_CLEARANCE
REGISTER_OUTER_RADIUS = 5.0
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


def horn_shape(profile=None, *, prepared=True):
    """Bought outline with explicit unmeasured axial proxy for the two metal options."""
    profile = profile or servo_horns.profile()
    radius = profile.root_diameter_mm / 2
    shape = union(
        [
            _cylinder(radius, profile.height_mm, (0, 0, 0)),
            _tangent_hull(
                profile.blade_bottom_mm,
                profile.arm_thickness_mm,
                radius,
                HORN_TIP_RADIUS,
                profile.overall_length_mm - radius - HORN_TIP_RADIUS,
            ),
        ]
    )
    shape = shape.cut(_cylinder(1.95, HORN_RECESS_DEPTH + 0.1, (0, -0.1, 0)))
    shape = shape.cut(
        _cylinder(profile.centre_hole_mm / 2, profile.height_mm + 0.2, (0, -0.1, 0))
    )
    for x, diameter in profile.holes:
        if prepared and not profile.threaded and x in profile.attachment_radii_mm:
            diameter = servo_horns.PREPARED_HOLE_DIAMETER_MM
        shape = shape.cut(
            _cylinder(diameter / 2, profile.height_mm + 0.2, (x, -0.1, 0))
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
    """One piece, one through-slot and flat seats; no separate cap or blank."""
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
    # One radial passage accepts all three hole patterns. Both screws must be
    # tightened: the slot is assembly allowance, not a running sliding joint.
    slot_mid = (SLOT_CENTRE_MIN + SLOT_CENTRE_MAX) / 2
    slot_half = (SLOT_CENTRE_MAX - SLOT_CENTRE_MIN) / 2
    shape = shape.cut(
        capsule(
            SLOT_WIDTH / 2,
            slot_half,
            HORN_HEIGHT - 0.1,
            PLATE_FRONT_Y - HORN_HEIGHT + 0.2,
            slot_mid,
        )
    )
    # Flat front face: no recessed fastener seats. Only the shaft boss needs
    # an open side relief for the KST inner front nut and its axial release.
    # Radius1.85 at x4.5 retains a1.10mm nominal wall beside the D bore.
    head_mid = (4.5 + SLOT_CENTRE_MAX) / 2
    head_half = (SLOT_CENTRE_MAX - 4.5) / 2
    shape = shape.cut(
        capsule(
            SLOT_HEAD_WIDTH / 2,
            head_half,
            FASTENER_SEAT_Y,
            SLOT_HEAD_TOP_Y - FASTENER_SEAT_Y,
            head_mid,
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
        shape, "Universal radial-slot horn adapter with open locating saddle"
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
        # Rectangle sits wholly within the real rounded slot and clears both
        # KST M1.4 shanks, making this a conservative rather than reduced part.
        plate = plate.cut(
            box(
                10.5,
                PLATE_FRONT_Y - HORN_HEIGHT + 0.2,
                1.5,
                (3.6, HORN_HEIGHT - 0.1, -0.75),
            )
        )
    front = box(8, SHAFT_SOCKET_LENGTH, 10.5, (-4, SHAFT_START_Y, -6.5))
    envelope = union([rear, plate, front]).removeSplitter()
    if retain_screws:
        envelope = envelope.cut(
            box(
                10.5,
                SLOT_HEAD_TOP_Y - HORN_HEIGHT + 0.1,
                1.5,
                (3.6, HORN_HEIGHT - 0.1, -0.75),
            )
        ).removeSplitter()
    if actual.cut(envelope).Volume > 1e-5:
        raise RuntimeError("Adapter service envelope must contain the installed solid")
    return envelope


def fastener_positions(profile=None):
    """The same slot takes the actual profile's two outer attachment positions."""
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
    profile = profile or servo_horns.profile()
    grip = FASTENER_SEAT_Y - profile.height_mm
    return {
        "horn_sku": profile.sku,
        "profile": profile.key,
        "x06_compatibility_basis": "User-accepted 15T/4 mm design premise; received fit remains unmeasured.",
        "factory_threads": "M1.6"
        if profile.threaded
        else "Plain 0.8/1.0 mm holes, not threaded.",
        "factory_hole_centres_xz_mm": tuple((x, 0.0) for x, _ in profile.holes),
        "attachment_radii_mm": profile.attachment_radii_mm,
        "horn_requires_drilling": not profile.threaded,
        "preparation": servo_horns.preparation_note(profile),
        "physical_concentricity_verified": False,
        "axial_envelope_measured": False,
        "axial_envelope_scope": "KST drawing gives 3.5 mm height/1.0 mm blade. Both other horns use provisional 3.5 mm height; second horn's 1.6 mm blade is also provisional. Actual installed seating, OEM screw and root concentricity remain checks.",
        "nominal_arm_thickness_mm": profile.arm_thickness_mm,
        "adapter_slot_width_mm": SLOT_WIDTH,
        "adapter_slot_centre_range_mm": (SLOT_CENTRE_MIN, SLOT_CENTRE_MAX),
        "register_radial_clearance_mm": REGISTER_INNER_RADIUS
        - profile.root_diameter_mm / 2,
        "register_engagement_mm": REGISTER_ENGAGEMENT,
        "register_scope": "One open C seat clears all three nominal roots. It limits rearward/side movement, not automatic centring. Centre the metal stub on the servo axis, check runout and free gear mesh, then tighten both screws. Root outlines are not specified precision pilots.",
        "assembly_adjustment": "Use the continuous radial slot to align the two actual attachment holes before tightening. Keep at least 4 mm between screw centres. Finish interfering printed surfaces rather than force alignment with screws. No intentional operating looseness; the clamped arm face transmits torque.",
        "fastener_grip_mm": grip,
        "screw_length_mm": profile.screw_length_mm,
        "nuts_per_side": 0 if profile.threaded else 2,
        "minimum_screw_head_flat_bearing_diameter_mm": HORN_MIN_HEAD_BEARING_DIAMETER
        if profile.threaded
        else None,
        "minimum_front_nut_af_mm": None
        if profile.threaded
        else servo_horns.NUT_MIN_AF_MM,
        "screw_thread_diameter_mm": 1.6 if profile.threaded else 1.4,
        "nominal_thread_engagement_mm": min(
            profile.arm_thickness_mm, profile.screw_length_mm - grip
        )
        if profile.threaded
        else servo_horns.NUT_HEIGHT_MM,
        "nominal_rear_tip_clearance_mm": FASTENER_SEAT_Y
        - profile.screw_length_mm
        - profile.blade_bottom_mm
        if profile.threaded
        else None,
        "nominal_front_nut_projection_mm": None
        if profile.threaded
        else profile.blade_bottom_mm
        + profile.screw_length_mm
        - FASTENER_SEAT_Y
        - servo_horns.NUT_HEIGHT_MM,
        "thread_engagement_scope": "Geometric only; actual useful threads, head, kit length, PA12 bearing stress and retention need inspection. For KST, a 0.2 mm nominal projection extends beyond the front nut; the rear head clears the case.",
        "centre_screw_service": "Remove both output gears and the paired servo/input-drive module. Remove the selected driver gear and metal stub, release the servo ear fasteners, and withdraw servo+horn+adapter as a unit gearward then sideways. Off the bridge, remove the adapter before accessing the OEM spline screw. For KST insert the rear M1.4 screws into the detached horn, fit horn/OEM centre screw to the free servo, add adapter/front nuts, and clamp while a <=1.5 mm rear driver stem clears the bare case. Insert the assembled servo unit into the bridge and secure its ears before replacing stub/gear. Do not claim rear tool access past the assembled bridge. The shaft stop remains a full floor.",
    }


def metrics():
    contract = assembly_contract()
    return {
        "reference_profile": "PTK_6_6",
        "reference_scope": "Legacy top-level horn dimensions and assembly_contract describe PTK_6_6 only; selected_horns and supported_profiles define the installed per-side choices.",
        "selected_horns": {
            side: servo_horns.profile(side=side).sku
            for side in servo_horns.SELECTED_BY_SIDE
        },
        "sources": [item.source for item in servo_horns.PROFILES.values()],
        "horn_shape_scope": "Three retained drawings; two metal threaded variants plus conditionally prepared KST0415.13. Axial seating and root concentricity remain prototype envelopes.",
        "supported_profiles": {
            key: assembly_contract(item) for key, item in servo_horns.PROFILES.items()
        },
        "selected_by_side": dict(servo_horns.SELECTED_BY_SIDE),
        "assembly_contract": contract,
        "horn_factory_hole_centres_xz_mm": HORN_FACTORY_HOLE_CENTRES,
        "horn_adapter_slot_width_mm": SLOT_WIDTH,
        "horn_adapter_slot_centre_range_mm": (SLOT_CENTRE_MIN, SLOT_CENTRE_MAX),
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
        "qualification": "Fit prototype, not manufactured-part qualification. Factory-hole selection avoids hand transfer drilling; C-seat/clearances do not certify axis concentricity, clamping strength or zero backlash. Check actual axial seating, thread engagement, runout, full motion and load.",
    }
