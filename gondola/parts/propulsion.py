"""Two detachable ±150° main propulsors; all geometry is in millimetres.

The fixed PA12 frame carries two servos and two rotating motor/guard carriers.
Four identical keyed sleeves provide the journals; standard M2 hardware retains
them. Official servo-ear axes locate open mounting saddles. The motor screw
pattern is known, but its seating/engagement and the servo-horn coupling remain
unqualified interfaces rather than invented fasteners.
"""

import FreeCAD as App
import Part

from gondola.cad import (
    box,
    create_group,
    create_printed_part,
    mirrored_y,
    set_property,
    union,
    update_print_orientation,
)
from gondola.contracts.design import DESIGN_REVISION

from . import purchased_hardware, rail

V = App.Vector
BASE_Z = rail.SHOE_BOTTOM
FOOT_THICKNESS = 2.0
SERVICE_CEILING_Z = 8.0
GUARD_OUTER_RADIUS = 24.3
GUARD_INNER_RADIUS = 22.8
PIVOT_Z = 48.2
SLEEVE_RADIUS = 4.0
SLEEVE_BORE_RADIUS = 1.2
SLEEVE_D_FLAT = 3.0
JOURNAL_RADIUS = 4.45
CARRIER_D_FLAT = 3.45
CARRIER_OUTER_Y = 26.55
SLEEVE_INNER_Y = 22.0
CARRIER_CAP_THICKNESS = 1.5
CARRIER_CAP_INNER_Y = SLEEVE_INNER_Y - CARRIER_CAP_THICKNESS
SLEEVE_ROUND_START = 26.8
SLEEVE_FLANGE_Y = 29.45
SLEEVE_END_Y = 30.95
JOURNAL_SCREW_LENGTH = purchased_hardware.JOURNAL_SCREW_LENGTH
SCREW_UNDERHEAD_Y = SLEEVE_END_Y
JOURNAL_NUT_Y = CARRIER_CAP_INNER_Y - purchased_hardware.SQUARE_NUT_HEIGHT
JOURNAL_SCREW_SKU = (
    f"M{purchased_hardware.THREAD_DIAMETER:g}X{JOURNAL_SCREW_LENGTH:g}_SOCKET_CAP"
)
JOURNAL_NUT_SKU = "M2_SQUARE_NUT_DIN562"
SERVO_SOURCE = "https://www.dspowerservo.com/ds-m005-mini-servo-product/"
SERVO_DRAWING = "https://cdn.globalso.com/dspowerservo/m0055.jpg"
MOTOR_SOURCE = "https://www.happymodel.cn/index.php/2025/01/08/happymodel-rs1102-kv10000-kv13500-brushless-motor-for-micro-fpv-drone/"
MOTOR_DRAWING = (
    "https://www.happymodel.cn/wp-content/uploads/2025/02/RS1102-KV10000.jpg"
)
JOURNAL_SCREW_SOURCE = purchased_hardware.JOURNAL_SCREW_SOURCE
JOURNAL_NUT_SOURCE = purchased_hardware.SQUARE_NUT_SOURCE
CREALLO_SOURCE = "https://creallo.com/ko/guide/design-spec-guide"
PROP_SOURCE = "https://www.gemfanhobby.com/40mm-1610-pc-2-blade.html"


# The local tilt axis is Y; motor thrust is +X at zero tilt. Fixed frame geometry
# is expressed in module coordinates, moving geometry about each local pivot.
PIVOT_HALF_SPAN = 80.0
MINIMUM_TILT_DEG = -150.0
MAXIMUM_TILT_DEG = 150.0
MOTOR_NOMINAL_DIAMETER = 13.5
MOTOR_DIAMETER = 13.6  # Manufacturer drawing: 13.5 +0.10/-0 mm.
MOTOR_LENGTH = 14.0
PROPELLER_DIAMETER = 40.0
PROPELLER_HUB_THICKNESS = 5.0
SERVO_BODY_LENGTH = 16.2
SERVO_BODY_HEIGHT = 17.4
SERVO_BODY_WIDTH = 8.3
SERVO_BODY_BASE_Y = -55.0
SERVO_CASE_MIN_X = -4.1  # Packaging assumption: case-to-output-axis datum unpublished.
SERVO_EAR_UNDERSIDE = 10.2
SERVO_MOUNT_X = (-5.82, 13.68)
SERVO_MOUNT_CLEARANCE_DIAMETER = 2.0
SERVO_MOUNT_TAB_THICKNESS = 2.0
SERVO_MOUNT_TAB_HALF_HEIGHT = 3.5
SERVO_MOUNT_PLANE_Y = SERVO_BODY_BASE_Y + SERVO_EAR_UNDERSIDE
SERVO_SUPPORT_OUTER_X = (-9.32, 17.18)
SERVO_CASE_CLEARANCE = 0.3
SLEEVE_SERVICE_LIFT = 10.0
MOTOR_MOUNT_THREAD = "M1.4"
MOTOR_MOUNT_PCD = 6.6
MOTOR_MOUNT_COUNT = 3


def cylinder(radius, length, origin, direction=(0, 1, 0)):
    """Cylinder whose default axis follows the trunnion axis."""
    return Part.makeCylinder(radius, length, V(*origin), V(*direction))


def _capsule_window(width, z_low, z_high, y, depth):
    radius = width / 2
    return union(
        [
            box(width, depth, z_high - z_low - width, (-radius, y, z_low + radius)),
            cylinder(radius, depth, (0, y, z_low + radius)),
            cylinder(radius, depth, (0, y, z_high - radius)),
        ]
    )


def _fixed_side(sign):
    bottom = BASE_Z - PIVOT_Z
    top = bottom + FOOT_THICKNESS
    foot = box(12.8, 73, FOOT_THICKNESS, (-6.4, -42, bottom))
    foot = foot.cut(box(8, 46, FOOT_THICKNESS + 2, (-4, -23, bottom - 1)))
    servo_foot = box(26.5, 25, FOOT_THICKNESS, (-9.32, -58, bottom)).cut(
        box(21.7, 20.2, FOOT_THICKNESS + 2, (-6.92, -55.6, bottom - 1))
    )
    foot = foot.fuse(servo_foot)
    parts = [foot]
    # Open two-millimetre feet deliberately omit raised perimeter ribs. The
    # lower stiffness is accepted for the indoor LTA fit prototype, not qualified.
    for y in (-28, 28):
        # Constant-width posts and ordinary circular bores: no FDM roof relief.
        cheek = union(
            [box(12.8, 2, -top, (-6.4, y - 1, top)), cylinder(6.4, 2, (0, y - 1, 0))]
        )
        cheek = cheek.cut(_capsule_window(8, top + 5, -7.5, y - 2, 4))
        cheek = cheek.cut(cylinder(JOURNAL_RADIUS, 4, (0, y - 2, 0)))
        parts.append(cheek)
    # Official ear centres and underside datum locate the supports. Closed
    # holes would leave sub-millimetre walls against the nominal case envelope:
    # open each Ø2 saddle toward the case instead of printing that fragile web.
    for index, hole_x in enumerate(SERVO_MOUNT_X):
        outer = SERVO_SUPPORT_OUTER_X[index]
        inner = (
            SERVO_CASE_MIN_X - SERVO_CASE_CLEARANCE
            if index == 0
            else SERVO_CASE_MIN_X + SERVO_BODY_LENGTH + SERVO_CASE_CLEARANCE
        )
        left, right = sorted((outer, inner))
        tab_y = SERVO_MOUNT_PLANE_Y - SERVO_MOUNT_TAB_THICKNESS
        tab = box(
            right - left,
            SERVO_MOUNT_TAB_THICKNESS,
            2 * SERVO_MOUNT_TAB_HALF_HEIGHT,
            (left, tab_y, -SERVO_MOUNT_TAB_HALF_HEIGHT),
        )
        saddle_radius = SERVO_MOUNT_CLEARANCE_DIAMETER / 2
        tab = tab.cut(cylinder(saddle_radius, 4, (hole_x, tab_y - 1, 0)))
        slot_left, slot_right = sorted((hole_x, inner))
        tab = tab.cut(
            box(
                slot_right - slot_left + 0.02,
                4,
                SERVO_MOUNT_CLEARANCE_DIAMETER,
                (slot_left - 0.01, tab_y - 1, -saddle_radius),
            )
        )
        parts.append(tab)
        support_x = outer if index == 0 else outer - 2.4
        # An open A-frame carries each saddle to the perimeter foot. The two
        # inclined webs are 2 mm wide in Y and 2.4 mm in X, not a solid cradle.
        for anchor_y in (-55.6, -37.4):
            points = [
                V(support_x, anchor_y, top),
                V(support_x, anchor_y + 2, top),
                V(support_x, SERVO_MOUNT_PLANE_Y, -SERVO_MOUNT_TAB_HALF_HEIGHT),
                V(support_x, tab_y, -SERVO_MOUNT_TAB_HALF_HEIGHT),
            ]
            parts.append(
                Part.Face(Part.makePolygon(points + [points[0]])).extrude(V(2.4, 0, 0))
            )
    shape = mirrored_y(union(parts), sign)
    shape.translate(V(0, sign * PIVOT_HALF_SPAN, PIVOT_Z))
    return shape


def integral_frame_shape():
    # Wings meet the exact shared shoe sides. Never refill its nut slot,
    # bore or T-channel with the former crossmember geometry.
    wings = box(18, 70, FOOT_THICKNESS, (-9, -35, BASE_Z)).cut(
        box(20, rail.SHOE_WIDTH, 20, (-10, -rail.SHOE_WIDTH / 2, 0))
    )
    frame = union([_fixed_side(1), _fixed_side(-1), wings, rail.shoe_shape()])
    # The metric hex driver reaches the selected clamp screw from either Y side.
    # This corridor stays outside the shared shoe and opens through the
    # low portions of the outrigger legs and keeps the open support windows free.
    for side in (-1, 1):
        # Cut the local foot cap above Z4; its remaining base is 1.8 mm thick.
        driver_clearance = box(
            6.4,
            103,
            SERVICE_CEILING_Z - 4.0,
            (-3.2, rail.SHOE_WIDTH / 2, 4.0),
        )
        if side < 0:
            driver_clearance = mirrored_y(driver_clearance, -1)
        frame = frame.cut(driver_clearance)
    frame = frame.removeSplitter()
    if not frame.isValid() or len(frame.Solids) != 1:
        raise RuntimeError("Propulsion frame is not one solid")
    return frame


def moving_carrier_shape():
    # Rebuilt without inherited FDM teardrops or obsolete guard-bonding tabs.
    rear = union(
        [
            cylinder(8.2, 1.5, (-8.5, 0, 0), (1, 0, 0)),
            box(1.5, 52, 6.4, (-8.5, -26, -3.2)),
        ]
    )
    rear = rear.cut(cylinder(2.2, 3, (-9, 0, 0), (1, 0, 0)))
    parts = [rear]
    for side in (-1, 1):
        y = 22 if side > 0 else -CARRIER_OUTER_Y
        strut = union(
            [
                box(18, CARRIER_OUTER_Y - 22, 6.4, (-7, y, -3.2)),
                cylinder(6, CARRIER_OUTER_Y - 22, (0, y, 0)),
            ]
        )
        bore = cylinder(JOURNAL_RADIUS, 8, (0, y - 1, 0)).cut(
            box(20, 10, 12, (-10, y - 2, CARRIER_D_FLAT))
        )
        parts.append(strut.cut(bore))
        cap = cylinder(6, CARRIER_CAP_THICKNESS, (0, CARRIER_CAP_INNER_Y, 0))
        cap = cap.cut(
            cylinder(
                SLEEVE_BORE_RADIUS,
                CARRIER_CAP_THICKNESS + 2,
                (0, CARRIER_CAP_INNER_Y - 1, 0),
            )
        )
        parts.append(mirrored_y(cap, side))
    guard = cylinder(GUARD_OUTER_RADIUS, 2, (11, 0, 0), (1, 0, 0)).cut(
        cylinder(GUARD_INNER_RADIUS, 4, (10, 0, 0), (1, 0, 0))
    )
    parts.extend(
        [guard, box(2, 4, 6.4, (11, -26, -3.2)), box(2, 4, 6.4, (11, 22, -3.2))]
    )
    shape = union(parts)
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Motor carrier/guard is not one solid")
    return shape


def journal_sleeve_shape(side):
    stem = cylinder(
        SLEEVE_RADIUS, SLEEVE_ROUND_START - SLEEVE_INNER_Y, (0, SLEEVE_INNER_Y, 0)
    )
    stem = stem.cut(
        box(
            20,
            SLEEVE_ROUND_START - SLEEVE_INNER_Y,
            12,
            (-10, SLEEVE_INNER_Y, SLEEVE_D_FLAT),
        )
    )
    journal = cylinder(
        SLEEVE_RADIUS, SLEEVE_FLANGE_Y - SLEEVE_ROUND_START, (0, SLEEVE_ROUND_START, 0)
    )
    flange = cylinder(5.5, SLEEVE_END_Y - SLEEVE_FLANGE_Y, (0, SLEEVE_FLANGE_Y, 0))
    sleeve = (
        union([stem, journal, flange])
        .cut(cylinder(SLEEVE_BORE_RADIUS, 12, (0, 20, 0)))
        .removeSplitter()
    )
    return mirrored_y(sleeve, side)


def _hardware_shape(shape, side, offset_y, axis_sign):
    oriented_shape = shape.copy()
    oriented_shape.rotate(V(), V(1, 0, 0), -90 * axis_sign)
    oriented_shape.translate(V(0, offset_y, 0))
    return mirrored_y(oriented_shape, side)


def _journal_hardware(doc, pod, prefix, side):
    suffix = "Positive" if side > 0 else "Negative"
    hardware_specs = [
        (
            "Bolt",
            purchased_hardware.screw_shape(JOURNAL_SCREW_LENGTH),
            SCREW_UNDERHEAD_Y,
            -1,
            JOURNAL_SCREW_SKU,
            f"M2x{JOURNAL_SCREW_LENGTH:g} socket cap bolt, M2x{purchased_hardware.THREAD_PITCH:g}. Head bears directly on the hollow sleeve; the square nut bears on the integral carrier cap. Stationary cheeks remain free. Nominal{JOURNAL_NUT_Y - (SCREW_UNDERHEAD_Y - JOURNAL_SCREW_LENGTH):g}mm projects beyond the{purchased_hardware.SQUARE_NUT_HEIGHT:g}mm nut. PA12 bearing pressure, creep and loosening remain unqualified.",
            JOURNAL_SCREW_SOURCE,
        ),
        (
            "Nut",
            purchased_hardware.square_nut_shape(),
            JOURNAL_NUT_Y,
            1,
            JOURNAL_NUT_SKU,
            f"Purchased M2x{purchased_hardware.THREAD_PITCH:g} DIN562 square nut, AF{purchased_hardware.SQUARE_NUT_AF:g} height{purchased_hardware.SQUARE_NUT_HEIGHT:g}, shared with the rail clamp. Bears directly on the integral1.5mm carrier cap and retains the sleeve with full nominal nut engagement. No printed thread or clip. Actual bearing face, PA12 indentation and vibration retention require physical checks.",
            JOURNAL_NUT_SOURCE,
        ),
    ]
    hardware = []
    for kind, shape, offset_y, axis_sign, sku, note, source in hardware_specs:
        obj = purchased_hardware.add_hardware(
            doc,
            pod,
            prefix + "Journal" + suffix + kind,
            "BUY | M2 journal " + kind,
            _hardware_shape(shape, side, offset_y, axis_sign),
            sku,
            note,
            source,
            "A2 stainless steel",
        )
        hardware.append(obj)
    return hardware


def _reference(doc, parent, name, label, shape, notes, source="", clearance=False):
    """A device envelope is never a print part or an invented OEM interface."""
    if shape.isNull() or not shape.isValid() or not shape.Solids:
        raise RuntimeError("Invalid propulsion reference: " + name)
    obj = doc.addObject("Part::Feature", name)
    parent.addObject(obj)
    obj.Label = label
    obj.Shape = shape
    set_property(obj, "Role", "Clearance" if clearance else "Hardware reference")
    set_property(obj, "Notes", notes)
    set_property(obj, "SourceURL", source)
    set_property(
        obj, "ManufacturingStatus", "Reference geometry only; exclude from fabrication"
    )
    if App.GuiUp:
        obj.ViewObject.ShapeColor = (
            (0.96, 0.62, 0.18) if clearance else (0.35, 0.38, 0.43)
        )
        obj.ViewObject.LineColor = (0.12, 0.16, 0.18)
        obj.ViewObject.DisplayMode = "Flat Lines"
        obj.ViewObject.Visibility = not clearance
        if clearance:
            obj.ViewObject.Transparency = 88
    return obj


def _create_pod(doc, module, prefix, sign):
    """Create only the current assembly, motion control and device envelopes."""
    assembly = create_group(
        doc, prefix + "Assembly", prefix + " · main propulsor assembly"
    )
    module.addObject(assembly)
    assembly.Placement.Base = V(0, sign * PIVOT_HALF_SPAN, PIVOT_Z)
    pod = create_group(
        doc, prefix + "Pod", prefix + " · independently tilting motor and guard"
    )
    assembly.addObject(pod)
    # Set a nonzero rotation first so FreeCAD retains Y as the rotation axis.
    pod.Placement.Rotation = App.Rotation(V(0, 1, 0), 1)
    set_property(pod, "Tilt", 0, "App::PropertyAngle", "Motion")
    set_property(pod, "MinimumTilt", MINIMUM_TILT_DEG, "App::PropertyAngle", "Motion")
    set_property(pod, "MaximumTilt", MAXIMUM_TILT_DEG, "App::PropertyAngle", "Motion")
    set_property(
        pod,
        "Notes",
        "Direct 1:1 servo-to-trunnion concept. Tilt is the requested angle; the native expression clamps travel to -150..+150 degrees. No continuous rotation. Actual horn coupling and measured OEM interfaces remain unfinished.",
    )
    pod.setEditorMode("MinimumTilt", 1)
    pod.setEditorMode("MaximumTilt", 1)
    pod.setExpression(
        "Placement.Rotation.Angle", "min(MaximumTilt; max(MinimumTilt; Tilt))"
    )

    motor = _reference(
        doc,
        pod,
        prefix + "Motor",
        "RS1102 · motor envelope Ø13.6 maximum × 14 mm",
        cylinder(MOTOR_DIAMETER / 2, MOTOR_LENGTH, (-7, 0, 0), (1, 0, 0)),
        "Conservative packaging cylinder, not exact bell/base geometry. Official drawing specifies overall length14, body datum8.8 and shaft projection4; this cylinder must not be used to derive a mounting depth. Three M1.4 mounting axes on PCD6.6 are published, but usable screw depth and rear clip clearance remain unverified.",
        MOTOR_SOURCE,
    )
    set_property(motor, "Diameter", MOTOR_DIAMETER, "App::PropertyLength")
    set_property(
        motor, "NominalDiameter", MOTOR_NOMINAL_DIAMETER, "App::PropertyLength"
    )
    set_property(motor, "EnvelopeLength", MOTOR_LENGTH, "App::PropertyLength")
    set_property(motor, "CatalogMassGrams", 2.8, "App::PropertyFloat")
    shaft = _reference(
        doc,
        pod,
        prefix + "Shaft",
        "RS1102 · Ø1.5 shaft; projection provisional",
        cylinder(0.75, 5, (7, 0, 0), (1, 0, 0)),
        "Shaft diameter is published; 5 mm projection is a packaging assumption, not a measured dimension.",
        MOTOR_SOURCE,
    )
    propeller = _reference(
        doc,
        pod,
        prefix + "PropellerDisk",
        "Gemfan 1610 · spinning envelope Ø40",
        cylinder(
            PROPELLER_DIAMETER / 2, PROPELLER_HUB_THICKNESS, (9.5, 0, 0), (1, 0, 0)
        ),
        "Conservative full disk uses the published 5 mm hub thickness throughout. This is not blade CAD. Select 1.5 mm bore; actual shaft engagement is unverified. The main pair requires opposite CW/CCW variants.",
        PROP_SOURCE,
    )
    set_property(propeller, "PropDiameter", PROPELLER_DIAMETER, "App::PropertyLength")
    set_property(
        propeller, "HubThickness", PROPELLER_HUB_THICKNESS, "App::PropertyLength"
    )
    set_property(propeller, "Variant", "CW" if sign > 0 else "CCW")
    if App.GuiUp:
        propeller.ViewObject.ShapeColor = (0.68, 0.81, 0.96)
        propeller.ViewObject.Transparency = 70

    servo_y = (
        SERVO_BODY_BASE_Y if sign > 0 else -(SERVO_BODY_BASE_Y + SERVO_BODY_HEIGHT)
    )
    servo = _reference(
        doc,
        assembly,
        prefix + "Servo",
        prefix + " · DS-M005 case reference",
        box(
            SERVO_BODY_LENGTH,
            SERVO_BODY_HEIGHT,
            SERVO_BODY_WIDTH,
            (SERVO_CASE_MIN_X, servo_y, -SERVO_BODY_WIDTH / 2),
        ),
        "Published current case envelope16.2x8.3x17.4, excluding ears, horn and spline. Output axis is Y at X=Z=0. Case X offset4.1 is a packaging assumption, not an official axis-to-edge dimension; the drawing instead fixes mounting-hole axes at X=-5.82/+13.68 and ear underside10.2 from the case bottom. Verify case clearance before manufacturing. No ear thickness or horn geometry is invented. Do not connect directly to2S LiPo.",
        SERVO_DRAWING,
    )
    coupling_y = -37.6 if sign > 0 else 30
    _reference(
        doc,
        assembly,
        prefix + "Coupling",
        "REFERENCE | unfinished OEM servo horn/coupling space",
        cylinder(3.5, 7.6, (0, coupling_y, 0)),
        "Space reservation only; this is not a printable coupler or a verified spline.",
        SERVO_SOURCE,
        clearance=True,
    )
    sweep_bound = _reference(
        doc,
        assembly,
        prefix + "SweepBound",
        prefix + " · conservative full-travel clearance bound",
        union(
            [
                cylinder(30, 2 * CARRIER_OUTER_Y, (0, -CARRIER_OUTER_Y, 0)),
                cylinder(6.4, 70, (0, -35, 0)),
            ]
        ),
        "Moving carrier, motor and propeller bound. Journal interfaces are assessed separately.",
        clearance=True,
    )
    set_property(sweep_bound, "RadialBound", 30, "App::PropertyLength")
    set_property(
        sweep_bound, "LateralHalfWidth", CARRIER_OUTER_Y, "App::PropertyLength"
    )
    set_property(sweep_bound, "JournalHeadHalfSpan", 35, "App::PropertyLength")
    return pod, [motor, shaft, propeller, servo]


def build_propulsion_module(doc):
    module = create_group(
        doc,
        "MainPropulsionModule",
        "Main propulsion | PA12 frame, continuous rail and M2 retention",
    )
    set_property(module, "Notes", "")
    set_property(module, "SupportPlaneZ", BASE_Z, "App::PropertyLength")
    set_property(module, "RailCenters", "")
    frame = create_printed_part(
        doc,
        module,
        "PropulsionFixedFrame",
        "PRINT | PA12 integral paired propulsion frame and M2-clamped rail shoe",
        integral_frame_shape(),
        App.Rotation(V(0, 0, 1), 45),
        "",
    )
    set_property(frame, "CarriageContactZ", BASE_Z, "App::PropertyLength")
    set_property(frame, "IntegratedRailShoe", True, "App::PropertyBool")
    set_property(frame, "RailCenterY", 0, "App::PropertyLength")
    device_references, hardware, pods = [], [], []
    frame.Notes = (
        "Continuous T-rail shoe, both open outrigger feet and open servo-ear supports are one PA12 SLS/MJF part. "
        f"Common foot bottomZ{BASE_Z:g} clears nominal{rail.PAD_THICKNESS:g}mm rail pads and{rail.TAPE_THICKNESS:g}mm tape; feet are{FOOT_THICKNESS:g}mm thick without raised edge ribs; stiffness remains unqualified. Pivots are at(0,+/-80,{PIVOT_Z:g}). "
        "The exact common shoe includes the M2 captive nut pocket and screw bore; choose one of the rotationally symmetric clamp ports; each has side-loaded nut access. "
        "Hollow printed D sleeves are retained by purchased M2 hardware; no printed pin or retaining clip. "
        "Official servo-ear centres locate two2mm open saddles for a prospective M1.6 through-fastener. Slots open toward the case to remove otherwise sub-millimetre walls; ear thickness, bolt length and retention are not yet approved. "
        f"Assemble journals before fitting the servo. For driven-side removal retract8mm, lift{SLEEVE_SERVICE_LIFT:g}mm above the ear saddles, then move outward. "
        "Rail friction, journal fit, supplier tolerances and the motor/servo-horn interfaces require physical validation."
    )
    frame.PrintNotes = "PA12 SLS/MJF. Depowder the through T-channel, side nut pocket, screw bore, hollow sleeves and open windows. No printed thread. STL contains this integrated frame only; purchased gold hardware must be excluded."
    set_property(frame, "PivotHeight", PIVOT_Z, "App::PropertyLength")
    set_property(
        frame,
        "RailRetention",
        "Choose either symmetric M2 captive-nut clamp port; fit one screw/nut pair only",
    )
    set_property(frame, "FootThickness", FOOT_THICKNESS, "App::PropertyLength")
    set_property(
        frame,
        "ClampServiceDirections",
        "+Y or -Y; opposite nut-loading directions +X or -X",
    )
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        pod, devices = _create_pod(doc, module, prefix, sign)
        pods.append(pod)
        device_references.extend(devices)
        carrier = create_printed_part(
            doc,
            pod,
            prefix + "MotorCarrier",
            "PRINT | integral motor carrier and propeller guard",
            moving_carrier_shape(),
            App.Rotation(V(0, 1, 0), -90),
            "",
        )
        carrier.Notes = (
            "One PA12 SLS/MJF part combines rear motor plate, journal struts, integral1.5mm retention caps and propeller guard. "
            "Front guard ID45.6mm admits the40mm propeller and13.6mm maximum motor envelope axially. "
            "D bores use nominal radius4.45 and flatZ3.45; hollow sleeve radius4/flatZ3.0 preserves a positive torque path. "
            "Boss endsY+/-26.55 give0.9mm total width clearance between stationary cheek inner facesY+/-27. "
            "Official RS1102 drawing gives3 M1.4 axes on PCD6.6. Holes remain uncut: a1.8mm clearance hole would leave only0.2mm between it and the existing4.4mm rear-shaft relief, and the rear clip diameter/head seating/depth are unverified. No false mounting approval."
        )
        carrier.PrintNotes = "PA12 SLS/MJF integral carrier/guard. Depowder open guard, rear relief and D journal bores. Install motor and propeller through the front opening; actual motor and horn fastening require measured vendor interfaces."
        for side, suffix in ((-1, "Negative"), (1, "Positive")):
            sleeve = create_printed_part(
                doc,
                pod,
                prefix + "JournalSleeve" + suffix,
                "hollow unthreaded D journal sleeve",
                journal_sleeve_shape(side),
                (
                    App.Rotation(V(1, 0, 0), -90)
                    if side > 0
                    else App.Rotation(V(0, 0, 1), 180).multiply(
                        App.Rotation(V(1, 0, 0), 90)
                    )
                ),
                "PA12 SLS/MJF hollow journal: OD8, through bore2.4, D flatZ3.0 leaves1.8mm minimum wall. Smooth round neck rotates inØ8.9 cheek; D stem turns the carrier. M2x14 bolt and DIN562 square nut clamp sleeve to the integral1.5mm carrier cap with no washers. Bolt head and nut bear directly on PA12. The carrier cap captures the inner end; the outer sleeve flange blocks opposite travel. Remove bolt and nut before extracting the sleeve. Bearing pressure, creep and loosening require physical checks. Flange faceY29.45 clears fixed outer cheekY29 by0.45mm. No thread or snap clip is printed. Actual servo horn attachment remains unfinished.",
            )
            sleeve.PrintNotes = (
                sleeve.Notes
                + " Depowder both open ends and verify sleeve/keyed-bore fit before assembly."
            )
            set_property(
                sleeve,
                "PrintSKU",
                f"JournalSleeve_M{purchased_hardware.THREAD_DIAMETER:g}_Retained",
            )
            hardware.extend(_journal_hardware(doc, pod, prefix, side))
        coupling = doc.getObject(prefix + "Coupling")
        coupling.Notes = "Space reservation only. Official DS-M005 page states28T horn; spline dimensions and horn retention screw diameter/pitch/length are not published. Use the vendor-supplied horn/fastener after confirming metric compatibility; do not substitute M2 into this interface. Required horn-to-D-sleeve torque connection remains unfinished."
        coupling.ManufacturingStatus = (
            "Clearance placeholder only, not actual hardware or printable coupling"
        )
        if App.GuiUp:
            coupling.ViewObject.ShapeColor = (0.95, 0.62, 0.18)
        servo = doc.getObject(prefix + "Servo")
        set_property(
            servo,
            "OEMFastenerStatus",
            "Unresolved vendor horn screw;28T horn specified, ear holesØ1.8 on19.5mm pitch. Do not forceM2 into OEM features.",
        )
        set_property(servo, "OEMDrawingURL", SERVO_DRAWING)
        motor = doc.getObject(prefix + "Motor")
        set_property(
            motor,
            "OEMFastenerStatus",
            "Official drawing:3-M1.4 equally spaced on PCD6.6. Separate pitch, thread depth and safe engagement are unpublished. No final fastener length or mounting geometry is approved.",
        )
        set_property(motor, "OEMDrawingURL", MOTOR_DRAWING)
        sweep_bound = doc.getObject(prefix + "SweepBound")
        sweep_bound.Notes = "Conservative moving bound for integral carrier and guard plus hollow sleeves/purchased M2 retention; journal interfaces intentionally enter the stationary frame. External module/rail clearance can be tested against this full bound."
    module.Notes = "One detachable two-propulsor module. Seven printed parts; common M2 purchased bolts and square nuts retain hollow torque sleeves against integral carrier caps; no washers. Continuous-rail captive-nut screw clamp replaces loose keys. Vendor motor/horn interfaces remain unfinished."
    module.RailCenters = (
        "One continuous T rail atY0; commonM2 captive-nut friction clamp"
    )
    # Stable part numbering and registry order are independent of build order.
    printed = [
        doc.getObject(name)
        for name in (
            "PortMotorCarrier",
            "StarboardMotorCarrier",
            "PropulsionFixedFrame",
            "PortJournalSleeveNegative",
            "PortJournalSleevePositive",
            "StarboardJournalSleeveNegative",
            "StarboardJournalSleevePositive",
        )
    ]
    clearance_references = [
        doc.getObject(prefix + suffix)
        for suffix in ("SweepBound", "Coupling")
        for prefix in ("Port", "Starboard")
    ]
    for obj in printed:
        set_property(
            obj,
            "ManufacturingStatus",
            "PA12 SLS/MJF fit prototype; depowder and verify physical fits",
        )
        if "ManufacturingProcess" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "ManufacturingProcess", "Printing")
        obj.ManufacturingProcess = "PA12 SLS/MJF"
        update_print_orientation(obj)
    doc.recompute()
    metrics = {
        "module_count": 1,
        "main_pod_count": 2,
        "tilt_range_deg": [MINIMUM_TILT_DEG, MAXIMUM_TILT_DEG],
        "independent_native_tilt": True,
        "single_rail_center_y_mm": 0,
        "integrated_rail_shoe": True,
        "consolidation": {
            "fixed_frame_and_single_rail_shoe_parts": 1,
            "fixed_frame_print_rotation_z_deg": 45,
        },
    }
    metrics.update(
        {
            "revision": DESIGN_REVISION,
            "status": "Paired detachable PA12 SLS/MJF fit prototype; device interfaces and retention not flight validated",
            "metal_structural_journal_parts_required": True,
            "printed_part_count": len(printed),
            "purchased_journal_hardware_count": len(hardware),
            "device_reference_count": len(device_references),
            "main_pivot_centers_mm": [[0, 80, PIVOT_Z], [0, -80, PIVOT_Z]],
            "frame_foot_thickness_mm": FOOT_THICKNESS,
            "frame_foot_edge_ribs": False,
            "symmetric_clamp_service": True,
            "integrated_guard_carriers": True,
            "printed_retaining_clips": 0,
            "printed_journal_pins": 0,
            "printed_hollow_unthreaded_sleeves": 4,
            "purchased_journal_quantities": {
                f"M2x{JOURNAL_SCREW_LENGTH:g}_socket_cap": 4,
                "M2_square_nut_DIN562": 4,
            },
        }
    )
    metrics["carrier_interface"] = {
        "shoe": "Exact gondola.parts.rail.shoe_shape; integrated",
        "feet_bottom_z_mm": BASE_Z,
        "retention": f"M2x{rail.SCREW_LENGTH:g} DIN913/ISO4026 screw in captured M2 nut, supplied by root builder",
        "hex_driver_access": "From either+Y or-Y, alongX0/Z6.2; symmetric6.4mm-wide service corridors outside shoe",
        "nut_loading_access": "Use the selected side of the symmetric common shoe; preserve nut-pocket loading corridor",
        "printed_rail_key": False,
        "installed_clamp_screw_nut_pairs": 1,
        "selectable_clamp_ports": 2,
    }
    metrics["journal"] = {
        "sleeve_od_mm": 2 * SLEEVE_RADIUS,
        "sleeve_bore_mm": 2 * SLEEVE_BORE_RADIUS,
        "sleeve_D_flat_z_mm": SLEEVE_D_FLAT,
        "minimum_sleeve_wall_mm": SLEEVE_D_FLAT - SLEEVE_BORE_RADIUS,
        "cheek_and_carrier_bore_mm": 2 * JOURNAL_RADIUS,
        "carrier_D_flat_z_mm": CARRIER_D_FLAT,
        "nominal_radial_and_flat_clearance_mm": 0.45,
        "nominal_total_carrier_width_clearance_mm": 0.9,
        "worst_case_width_clearance_two_0_3mm_size_errors_mm": 0.3,
        "retention": f"M2x{JOURNAL_SCREW_LENGTH:g} bolt and M2 DIN562 square nut per sleeve, without washers. Direct load path: bolt head -> sleeve -> integral carrier cap -> nut. Stationary cheeks remain free; the cap retains outward travel and the sleeve flange limits inward travel.",
        "integral_cap_thickness_mm": CARRIER_CAP_THICKNESS,
        "integral_cap_clearance_diameter_mm": 2 * SLEEVE_BORE_RADIUS,
        "thread_engagement_mm": purchased_hardware.SQUARE_NUT_HEIGHT,
        "bolt_tip_projection_beyond_nut_mm": JOURNAL_NUT_Y
        - (SCREW_UNDERHEAD_Y - JOURNAL_SCREW_LENGTH),
        "torque_path": "Unfinished OEM horn coupling -> keyed hollow sleeve -> D bore carrier. Metric retention bolt alone is not the drive coupling.",
        "fit_limit": "Nominal geometry only; local printed fit, accumulated position error and axial endplay require measured assembly/finishing.",
    }
    metrics["consolidation"]["remaining_split_reasons"] = {
        "carrier_and_fixed_frame": "Relative motor tilt needs a real journal.",
        "removable_hollow_sleeves": "Allows carrier insertion into closed stationary cheeks and future disassembly; standard bolts retain sleeves.",
    }
    metrics["consolidation"]["integral_motor_carrier_guard_parts"] = 2
    print_oriented_frame = frame.Shape.copy()
    print_oriented_frame.rotate(V(), V(0, 0, 1), 45)
    metrics["consolidation"]["fixed_frame_print_bounds_mm"] = [
        print_oriented_frame.BoundBox.XLength,
        print_oriented_frame.BoundBox.YLength,
        print_oriented_frame.BoundBox.ZLength,
    ]
    metrics["consolidation"]["separate_guard_ring_parts"] = 0
    metrics["consolidation"]["manufacturing_process"] = (
        "PA12 SLS/MJF; stored STL orientation is not a support-free FDM claim"
    )
    metrics["journal_assembly_order"] = [
        "Leave servos off the cradle while fitting the rotating carriers.",
        f"Insert hollow D sleeves from outside. Fit one M2x{JOURNAL_SCREW_LENGTH:g} bolt and DIN562 square nut, bearing directly on the sleeve flange and integral carrier cap. Tighten cautiously without pinching stationary cheeks; PA12 preload and creep are not qualified.",
        "Resolve motor mount seating/engagement and servo saddle fastening before fitting vendor motor fasteners, servos and measured horn coupling.",
        f"For journal service release both servos and unmodeled horn couplings. Remove the square nut, then the bolt. Withdraw the bare driven-side sleeve8mm, lift{SLEEVE_SERVICE_LIFT:g}mm, then move away; the idle sleeve can withdraw directly.",
    ]
    metrics["OEM_interfaces"] = {
        "DS_M005": {
            "source": SERVO_SOURCE,
            "drawing": SERVO_DRAWING,
            "horn_spline_teeth": 28,
            "mounting_ear_hole_diameter_mm": 1.8,
            "mounting_ear_pitch_mm": 19.5,
            "mounting_axes_relative_to_output_mm": list(SERVO_MOUNT_X),
            "ear_underside_from_case_bottom_mm": SERVO_EAR_UNDERSIDE,
            "printed_mount_interface": "Two Y-axis open saddles, nominal2mm width, for prospective M1.6 through-bolts; not a verified closed-hole or OEM screw specification.",
            "mount_saddle_width_mm": SERVO_MOUNT_CLEARANCE_DIAMETER,
            "mount_saddle_thickness_mm": SERVO_MOUNT_TAB_THICKNESS,
            "mount_saddle_bearing_plane_y_mm": SERVO_MOUNT_PLANE_Y,
            "case_axis_to_edge_offset_mm": None,
            "case_axis_to_edge_packaging_assumption_mm": -SERVO_CASE_MIN_X,
            "ear_thickness_mm": None,
            "mount_fastener_length_mm": None,
            "release_limit": "Verify supplied case/ear dimensions, washers and open-saddle retention before load-bearing use; no OEM ear solid is fabricated.",
            "horn_retention_screw": "Unspecified; verify vendor fastener and actual horn.",
        },
        "RS1102": {
            "source": MOTOR_SOURCE,
            "drawing": MOTOR_DRAWING,
            "retained_drawing": "references/rs1102_dimensions.jpg",
            "mount_thread_designation": MOTOR_MOUNT_THREAD,
            "nominal_diameter_mm": MOTOR_NOMINAL_DIAMETER,
            "maximum_diameter_mm": MOTOR_DIAMETER,
            "mount_hole_count": MOTOR_MOUNT_COUNT,
            "mount_pitch_circle_diameter_mm": MOTOR_MOUNT_PCD,
            "mount_angular_spacing_deg": 120,
            "thread_pitch_mm": None,
            "thread_usable_depth_mm": None,
            "mount_holes_implemented": False,
            "existing_rear_relief_diameter_mm": 4.4,
            "candidate_clearance_diameter_mm": 1.8,
            "candidate_closed_hole_ligament_mm": MOTOR_MOUNT_PCD / 2 - 2.2 - 0.9,
            "mount_hole_deferral_reason": "A closed1.8mm hole leaves0.2mm beside the4.4mm rear relief. Rear shaft/clip diameter, bolt-head seat and safe engagement are unpublished; do not shrink the relief or fabricate seating/depth assumptions.",
        },
    }
    metrics["printed_parts"] = [
        {
            "name": o.Name,
            "volume_mm3": o.Shape.Volume,
            "solid_count": len(o.Shape.Solids),
            "valid_brep": o.Shape.isValid(),
        }
        for o in printed
    ]
    metrics["printed_volume_mm3"] = sum(o.Shape.Volume for o in printed)
    metrics["process_design_reference"] = {
        "source": CREALLO_SOURCE,
        "process": "PA12 SLS/MJF",
        "minimum_feature_wall_mm": 1.5,
        "guard_radial_wall_mm": GUARD_OUTER_RADIUS - GUARD_INNER_RADIUS,
        "servo_support_web_width_mm": 2.0,
        "servo_support_web_depth_mm": 2.4,
        "raised_foot_ribs": False,
        "integral_carrier_cap_thickness_mm": CARRIER_CAP_THICKNESS,
        "long_frame_base_thickness_mm": FOOT_THICKNESS,
        "supplier_review_required": "Two-millimetre open feet omit raised perimeter ribs and retain the connected A-frame ear supports. General local wall target remains1.5mm, including integral carrier retention caps. The long integrated frame and direct PA12 fastener seats require supplier warp review and physical stiffness, creep and load checks.",
    }
    metrics["unfinished_interfaces"] = [
        "RS1102 rear clearance, screw head seating and safe engagement; known3-M1.4/PCD6.6 pattern not yet cut",
        "DS-M005 vendor horn screw and horn-to-sleeve coupling",
        "Servo case-to-axis offset, ear thickness and purchased open-saddle fastener/retention",
        "Printed journal tolerances and running clearance",
        "Nut retention and clamp holding force",
        "Motor wires and strain relief",
        "Actual tilt endpoint stops",
    ]
    return {
        "group": module,
        "printed": printed,
        "references": device_references,
        "clearances": clearance_references,
        "pods": pods,
        "hardware": hardware,
        "frame": frame,
        "metrics": metrics,
    }
