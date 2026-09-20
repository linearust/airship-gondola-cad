"""Two detachable ±150° main propulsors; all geometry is in millimetres.

The fixed PA12 frame carries two servos and two rotating motor/guard carriers.
Four identical keyed sleeves provide the journals; standard M3 hardware retains
them. The motor screw pattern and servo-horn coupling remain unmeasured OEM
interfaces. They are represented as reservations, not fabricated components.
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
from gondola.design_contract import DESIGN_REVISION

from . import metric_hardware as metric
from . import rail

V = App.Vector
BASE_Z = 2.0
FOOT_THICKNESS = 3.0
PIVOT_Z = 48.2
SLEEVE_RADIUS = 4.0
SLEEVE_BORE_RADIUS = 2.0
SLEEVE_D_FLAT = 3.0
JOURNAL_RADIUS = 4.45
CARRIER_D_FLAT = 3.45
CARRIER_OUTER_Y = 26.55
SLEEVE_INNER_Y = 21.55
SLEEVE_ROUND_START = 26.8
SLEEVE_FLANGE_Y = 29.45
SLEEVE_END_Y = 30.95
SCREW_UNDERHEAD_Y = 31.45
SERVO_SOURCE = "https://www.dspowerservo.com/ds-m005-mini-servo-product/"
SERVO_DRAWING = "https://cdn.globalso.com/dspowerservo/m0055.jpg"
MOTOR_SOURCE = "https://www.happymodel.cn/index.php/2025/01/08/happymodel-rs1102-kv10000-kv13500-brushless-motor-for-micro-fpv-drone/"
JOURNAL_SCREW_SOURCE = (
    "https://www.accu.co.uk/metric-cap-head-screws/3822-SSCF-M3-16-A2"
)
JOURNAL_NUT_SOURCE = "https://www.accu.co.uk/hexagon-nuts/7888-HPN-M3-A2"
JOURNAL_WASHER_SOURCE = (
    "https://www.pgb-europe.com/en-gb/9763/flat-washer-din-125a-m-3-a2-320-7-05"
)
CREALLO_SOURCE = "https://creallo.com/ko/guide/design-spec-guide"
PROP_SOURCE = "https://www.gemfanhobby.com/40mm-1610-pc-2-blade.html"
BEARING_SOURCE = "https://www.ezo-brg.co.jp/english/product/spec.php?eid=00213&unit=mm"


# The local tilt axis is Y; motor thrust is +X at zero tilt. Fixed frame geometry
# is expressed in module coordinates, moving geometry about each local pivot.
PIVOT_HALF_SPAN = 80.0
MINIMUM_TILT_DEG = -150.0
MAXIMUM_TILT_DEG = 150.0
MOTOR_DIAMETER = 13.5
MOTOR_LENGTH = 14.0
PROPELLER_DIAMETER = 40.0
PROPELLER_HUB_THICKNESS = 5.0


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
    foot = union(
        [
            box(12.8, 73, FOOT_THICKNESS, (-6.4, -42, bottom)),
            box(22, 25, FOOT_THICKNESS, (-7, -58, bottom)),
        ]
    )
    foot = foot.cut(box(14, 11, FOOT_THICKNESS + 2, (-3, -51, bottom - 1)))
    foot = foot.cut(box(8, 46, FOOT_THICKNESS + 2, (-4, -23, bottom - 1)))
    parts = [foot]
    for y in (-28, 28):
        # Constant-width posts and ordinary circular bores: no FDM roof relief.
        cheek = union(
            [box(12.8, 2, -top, (-6.4, y - 1, top)), cylinder(6.4, 2, (0, y - 1, 0))]
        )
        cheek = cheek.cut(_capsule_window(8, top + 5, -7.5, y - 2, 4))
        cheek = cheek.cut(cylinder(JOURNAL_RADIUS, 4, (0, y - 2, 0)))
        parts.append(cheek)
    # Four equal corner columns and a simple rim support the servo envelope.
    cradle = box(19.2, 18.4, -4.25 - top, (-5.6, -55.5, top))
    cradle = cradle.cut(box(14.4, 13.6, -top + 2, (-3.2, -53.1, top - 1)))
    window_bottom = top + 4
    for y in (-55.5, -39.5):
        cradle = cradle.cut(
            box(14.4, 2.6, -8.25 - window_bottom, (-3.2, y - 0.1, window_bottom))
        )
    for x in (-5.6, 11.2):
        cradle = cradle.cut(
            box(2.6, 13.6, -8.25 - window_bottom, (x - 0.1, -53.1, window_bottom))
        )
    # Journal service remains possible after the servo is removed.
    cradle = cradle.cut(cylinder(5.9, 6, (0, -41, 0)))
    parts.append(cradle)
    shape = mirrored_y(union(parts), sign)
    shape.translate(V(0, sign * PIVOT_HALF_SPAN, PIVOT_Z))
    return shape


def integral_frame_shape():
    # Wings meet the exact shared shoe at Y+/-12. Never refill its nut slot,
    # bore or T-channel with the former crossmember geometry.
    wings = box(18, 70, FOOT_THICKNESS, (-9, -35, BASE_Z)).cut(
        box(20, 24, 20, (-10, -12, 0))
    )
    frame = union([_fixed_side(1), _fixed_side(-1), wings, rail.shoe_shape()])
    # A 1.5mm hex driver reaches the selected captured M3 screw from either Y side.
    # This corridor stays outside the shared shoe and opens through the
    # low portions of the outrigger legs; SLS/MJF permits the local ceiling.
    for side in (-1, 1):
        # Top Z8 leaves a 1mm web below the cradle window floor at Z9.
        service = box(6.4, 103, 4.0, (-3.2, 12, 4.0))
        if side < 0:
            service = mirrored_y(service, -1)
        frame = frame.cut(service)
    frame = frame.removeSplitter()
    if not frame.isValid() or len(frame.Solids) != 1:
        raise RuntimeError("Propulsion frame is not one solid")
    return frame


def moving_carrier_shape():
    # Rebuilt without inherited FDM teardrops or obsolete guard-bonding tabs.
    rear = union(
        [
            cylinder(8.2, 1.5, (-8.5, 0, 0), (1, 0, 0)),
            box(1.5, 52, 9, (-8.5, -26, -4.5)),
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
    guard = cylinder(24, 2, (11, 0, 0), (1, 0, 0)).cut(
        cylinder(22.8, 4, (10, 0, 0), (1, 0, 0))
    )
    parts.extend([guard, box(2, 4, 9, (11, -26, -4.5)), box(2, 4, 9, (11, 22, -4.5))])
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


def _hardware_shape(shape, side, y0, axis_sign=1):
    s = shape.copy()
    s.rotate(V(), V(1, 0, 0), -90 * axis_sign)
    s.translate(V(0, y0, 0))
    return mirrored_y(s, side)


def _journal_hardware(doc, moving, prefix, side):
    suffix = "Positive" if side > 0 else "Negative"
    specs = [
        (
            "Bolt",
            metric.screw_shape(16),
            SCREW_UNDERHEAD_Y,
            -1,
            "M3X16_SOCKET_CAP",
            "M3x16 socket cap bolt, M3x0.5. Clamps only the hollow sleeve between washers; it must not pinch the stationary frame. Nominal3.2mm projects beyond the2.4mm nut. The thread does not rub the journal.",
            JOURNAL_SCREW_SOURCE,
        ),
        (
            "OuterWasher",
            metric.washer_shape(),
            SLEEVE_END_Y,
            1,
            "M3_WASHER_3.2_7_0.5",
            "Purchased3.2x7x0.5mm washer under the M3 bolt head; bears on sleeve flange.",
            JOURNAL_WASHER_SOURCE,
        ),
        (
            "InnerWasher",
            metric.washer_shape(),
            SLEEVE_INNER_Y - 0.5,
            1,
            "M3_WASHER_3.2_7_0.5",
            "Purchased3.2x7x0.5mm washer bears on the sleeve end, with0.45mm nominal clearance to the carrier inner face.",
            JOURNAL_WASHER_SOURCE,
        ),
        (
            "Nut",
            metric.nut_shape(),
            SLEEVE_INNER_Y - 0.5 - 2.4,
            1,
            "M3_HEX_NUT",
            "Purchased M3x0.5 regular nut, AF5.5 height2.4. Full nut engagement retains the removable sleeve. No printed thread or clip. Nut retention under vibration remains a physical assembly check.",
            JOURNAL_NUT_SOURCE,
        ),
    ]
    result = []
    for kind, shape, y0, axis, sku, note, source in specs:
        obj = metric.add_hardware(
            doc,
            moving,
            prefix + "Journal" + suffix + kind,
            "BUY | M3 journal " + kind,
            _hardware_shape(shape, side, y0, axis),
            sku,
            note,
            source,
            "A2 stainless steel",
        )
        result.append(obj)
    return result


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
    moving = create_group(
        doc, prefix + "Pod", prefix + " · independently tilting motor and guard"
    )
    assembly.addObject(moving)
    # Set a nonzero rotation first so FreeCAD retains Y as the rotation axis.
    moving.Placement.Rotation = App.Rotation(V(0, 1, 0), 1)
    set_property(moving, "Tilt", 0, "App::PropertyAngle", "Motion")
    set_property(
        moving, "MinimumTilt", MINIMUM_TILT_DEG, "App::PropertyAngle", "Motion"
    )
    set_property(
        moving, "MaximumTilt", MAXIMUM_TILT_DEG, "App::PropertyAngle", "Motion"
    )
    set_property(
        moving,
        "Notes",
        "Direct 1:1 servo-to-trunnion concept. Tilt is the requested angle; the native expression clamps travel to -150..+150 degrees. No continuous rotation. Actual horn coupling and measured OEM interfaces remain unfinished.",
    )
    moving.setEditorMode("MinimumTilt", 1)
    moving.setEditorMode("MaximumTilt", 1)
    moving.setExpression(
        "Placement.Rotation.Angle", "min(MaximumTilt; max(MinimumTilt; Tilt))"
    )

    motor = _reference(
        doc,
        moving,
        prefix + "Motor",
        "RS1102 · motor envelope Ø13.5 × 14 mm",
        cylinder(MOTOR_DIAMETER / 2, MOTOR_LENGTH, (-7, 0, 0), (1, 0, 0)),
        "Published outer envelope only. Bell/base datums, mounting-hole pitch, thread and usable screw depth are unverified.",
        MOTOR_SOURCE,
    )
    set_property(motor, "Diameter", MOTOR_DIAMETER, "App::PropertyLength")
    set_property(motor, "EnvelopeLength", MOTOR_LENGTH, "App::PropertyLength")
    set_property(motor, "CatalogMassGrams", 2.8, "App::PropertyFloat")
    shaft = _reference(
        doc,
        moving,
        prefix + "Shaft",
        "RS1102 · Ø1.5 shaft; projection provisional",
        cylinder(0.75, 5, (7, 0, 0), (1, 0, 0)),
        "Shaft diameter is published; 5 mm projection is a packaging assumption, not a measured dimension.",
        MOTOR_SOURCE,
    )
    propeller = _reference(
        doc,
        moving,
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

    servo_y = -55 if sign > 0 else 37.6
    servo = _reference(
        doc,
        assembly,
        prefix + "Servo",
        prefix + " · DS-M005 case reference",
        box(16.2, 17.4, 8.3, (-4.1, servo_y, -4.15)),
        "Case envelope only, excluding ears, horn and spline. Output axis along Y, with provisional coupling gap. Measure the supplied horn before designing a connection. Do not connect directly to 2S LiPo.",
        SERVO_DRAWING,
    )
    coupling_y = -37.6 if sign > 0 else 30
    coupling = _reference(
        doc,
        assembly,
        prefix + "Coupling",
        "REFERENCE | unfinished OEM servo horn/coupling space",
        cylinder(3.5, 7.6, (0, coupling_y, 0)),
        "Space reservation only; this is not a printable coupler or a verified spline.",
        SERVO_SOURCE,
        clearance=True,
    )
    bound = _reference(
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
    set_property(bound, "RadialBound", 30, "App::PropertyLength")
    set_property(bound, "LateralHalfWidth", CARRIER_OUTER_Y, "App::PropertyLength")
    set_property(bound, "JournalHeadHalfSpan", 35, "App::PropertyLength")
    return moving, [motor, shaft, propeller, servo], [bound, coupling]


def build_propulsion_module(doc, parent=None):
    module = create_group(
        doc,
        "MainPropulsionModule",
        "Main propulsion | PA12 frame, continuous rail and M3 retention",
    )
    if parent is not None:
        parent.addObject(module)
    set_property(module, "Notes", "")
    set_property(module, "SupportPlaneZ", BASE_Z, "App::PropertyLength")
    set_property(module, "RailCenters", "")
    frame = create_printed_part(
        doc,
        module,
        "PropulsionFixedFrame",
        "PRINT | PA12 integral paired propulsion frame and M3-clamped rail shoe",
        integral_frame_shape(),
        App.Rotation(V(0, 0, 1), 45),
        "",
    )
    set_property(frame, "CarriageContactZ", BASE_Z, "App::PropertyLength")
    set_property(frame, "IntegratedRailShoe", True, "App::PropertyBool")
    set_property(frame, "RailCenterY", 0, "App::PropertyLength")
    printed, refs, clear, hardware, pods = [frame], [], [], [], []
    frame.Label = (
        "PRINT | PA12 integral paired propulsion frame and M3-clamped rail shoe"
    )
    frame.Notes = (
        "Continuous T-rail shoe, both outrigger feet and servo cradles are one PA12 SLS/MJF part. "
        "Common foot bottomZ2 clears nominal1mm rail pads and0.15mm tape; feet/base are3mm thick. Pivots are at(0,+/-80,48.2). "
        "The exact common shoe includes the M3 captive nut pocket and screw bore; choose one of the rotationally symmetric clamp ports; each has side-loaded nut access. "
        "Hollow printed D sleeves are retained by purchased M3 hardware; no printed pin or retaining clip. "
        "Assemble journals and their screws before fitting the servo; the coaxial servo later blocks direct journal screw access. A small cradle output-rim relief permits8mm sleeve retraction, then lift before moving farther. "
        "Rail friction, journal fit, supplier tolerances and the motor/servo-horn interfaces require physical validation."
    )
    frame.PrintNotes = "PA12 SLS/MJF. Depowder the through T-channel, side nut pocket, screw bore, hollow sleeves and open windows. No printed thread. STL contains this integrated frame only; purchased gold hardware must be excluded."
    frame.CarriageContactZ = BASE_Z
    frame.IntegratedRailShoe = True
    set_property(frame, "PivotHeight", PIVOT_Z, "App::PropertyLength")
    set_property(
        frame,
        "RailRetention",
        "Choose either symmetric M3 captive-nut clamp port; fit one screw/nut pair only",
    )
    set_property(frame, "FootThickness", FOOT_THICKNESS, "App::PropertyLength")
    set_property(
        frame,
        "ClampServiceDirections",
        "+Y or -Y; opposite nut-loading directions +X or -X",
    )
    update_print_orientation(frame)
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        moving, devices, reservations = _create_pod(doc, module, prefix, sign)
        pods.append(moving)
        refs.extend(devices)
        clear.extend(reservations)
        carrier = create_printed_part(
            doc,
            moving,
            prefix + "MotorCarrier",
            "PRINT | integral motor carrier and propeller guard",
            moving_carrier_shape(),
            App.Rotation(V(0, 1, 0), -90),
            "",
        )
        printed.append(carrier)
        carrier.Label = "PRINT | integral motor carrier and propeller guard"
        carrier.Notes = (
            "One PA12 SLS/MJF part combines rear motor plate, journal struts and propeller guard. "
            "Front guard ID45.6mm admits the40mm propeller and13.5mm motor axially. "
            "D bores use nominal radius4.45 and flatZ3.45; hollow sleeve radius4/flatZ3.0 preserves a positive torque path. "
            "Boss endsY+/-26.55 give0.9mm total width clearance between stationary cheek inner facesY+/-27. "
            "Motor screw pattern, metric thread and allowed engagement remain unverified; no invented mounting holes."
        )
        carrier.PrintNotes = "PA12 SLS/MJF integral carrier/guard. Depowder open guard, rear relief and D journal bores. Install motor and propeller through the front opening; actual motor and horn fastening require measured vendor interfaces."
        update_print_orientation(carrier)
        for side, suffix in ((-1, "Negative"), (1, "Positive")):
            sleeve = create_printed_part(
                doc,
                moving,
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
                "PA12 SLS/MJF hollow journal: OD8, through bore4, D flatZ3.0 leaves1.0mm minimum wall. Smooth round neck rotates inØ8.9 cheek; D stem turns the carrier. M3 hardware clamps sleeve ends only. Flange faceY29.45 clears fixed outer cheekY29 by0.45mm. No thread or snap clip is printed. Actual servo horn attachment remains unfinished.",
            )
            sleeve.PrintNotes = (
                sleeve.Notes
                + " Depowder both open ends and verify sleeve/keyed-bore fit before assembly."
            )
            set_property(sleeve, "PrintSKU", "JournalSleeve_M3_Retained")
            printed.append(sleeve)
            hardware.extend(_journal_hardware(doc, moving, prefix, side))
        coupling = doc.getObject(prefix + "Coupling")
        coupling.Role = "Clearance"
        coupling.Label = "REFERENCE | unfinished OEM servo horn/coupling space"
        coupling.Notes = "Space reservation only. Official DS-M005 page states28T horn; spline dimensions and horn retention screw diameter/pitch/length are not published. Use the vendor-supplied horn/fastener after confirming metric compatibility; do not substitute M3 into this interface. Required horn-to-D-sleeve torque connection remains unfinished."
        coupling.ManufacturingStatus = (
            "Clearance placeholder only, not actual hardware or printable coupling"
        )
        coupling.SourceURL = SERVO_SOURCE
        if App.GuiUp:
            coupling.ViewObject.ShapeColor = (0.95, 0.62, 0.18)
            coupling.ViewObject.Transparency = 88
            coupling.ViewObject.Visibility = False
        servo = doc.getObject(prefix + "Servo")
        set_property(
            servo,
            "OEMFastenerStatus",
            "Unresolved vendor horn screw;28T horn specified, ear holesØ1.8 on19.5mm pitch. Do not forceM3 into OEM features.",
        )
        set_property(servo, "OEMDrawingURL", SERVO_DRAWING)
        motor = doc.getObject(prefix + "Motor")
        set_property(
            motor,
            "OEMFastenerStatus",
            "Official RS1102 data omit mounting screw size/pitch, PCD and thread depth. Vendor-supplied fastener requires metric identification before release.",
        )
        bound = doc.getObject(prefix + "SweepBound")
        bound.Notes = "Conservative moving bound for integral carrier and guard plus hollow sleeves/purchased M3 retention; journal interfaces intentionally enter the stationary frame. External module/rail clearance can be tested against this full bound."
        bound.LateralHalfWidth = CARRIER_OUTER_Y
        bound.JournalHeadHalfSpan = 35
    group = module
    group.Notes = "One detachable two-propulsor module. Seven printed parts; common M3 purchased bolts/nuts/washers retain hollow torque sleeves. Continuous-rail captive-nut screw clamp replaces loose keys. Vendor motor/horn interfaces remain unfinished."
    group.SupportPlaneZ = BASE_Z
    group.RailCenters = (
        "One continuous T rail atY0; commonM3 captive-nut friction clamp"
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
    clear = [
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
            "hardware_reference_count": len(hardware),
            "device_reference_count": len(refs),
            "main_pivot_centers_mm": [[0, 80, PIVOT_Z], [0, -80, PIVOT_Z]],
            "frame_foot_thickness_mm": FOOT_THICKNESS,
            "symmetric_clamp_service": True,
            "integrated_guard_carriers": True,
            "printed_retaining_clips": 0,
            "printed_journal_pins": 0,
            "printed_hollow_unthreaded_sleeves": 4,
            "purchased_journal_quantities": {
                "M3x16_socket_cap": 4,
                "M3_hex_nut": 4,
                "M3_flat_washer_3.2x7x0.5": 8,
            },
        }
    )
    metrics["carrier_interface"] = {
        "shoe": "Exact gondola.parts.rail.shoe_shape; integrated",
        "feet_bottom_z_mm": BASE_Z,
        "retention": "M3x8 DIN913/ISO4026 screw in captured M3 nut, supplied by root builder",
        "hex_driver_access": "From either+Y or-Y, alongX0/Z6.2; symmetric6.4mm-wide service corridors outside shoe",
        "nut_loading_access": "Use the selected side of the symmetric common shoe; preserve nut-pocket loading corridor",
        "printed_rail_key": False,
        "installed_clamp_screw_nut_pairs": 1,
        "selectable_clamp_ports": 2,
    }
    metrics["journal"] = {
        "sleeve_od_mm": 8,
        "sleeve_bore_mm": 4,
        "sleeve_D_flat_z_mm": 3.0,
        "minimum_sleeve_wall_mm": 1.0,
        "cheek_and_carrier_bore_mm": 8.9,
        "carrier_D_flat_z_mm": 3.45,
        "nominal_radial_and_flat_clearance_mm": 0.45,
        "nominal_total_carrier_width_clearance_mm": 0.9,
        "worst_case_width_clearance_two_0_3mm_size_errors_mm": 0.3,
        "retention": "M3x16 bolt, two3.2x7x0.5 washers and M3nut per sleeve; sleeve ends carry clamp load, cheeks remain free",
        "thread_engagement_mm": 2.4,
        "bolt_tip_projection_beyond_nut_mm": 3.2,
        "torque_path": "Unfinished OEM horn coupling -> keyed hollow sleeve -> D bore carrier. Metric retention bolt alone is not the drive coupling.",
        "fit_limit": "Nominal geometry only; local printed fit, accumulated position error and axial endplay require measured assembly/finishing.",
    }
    metrics["consolidation"]["remaining_split_reasons"] = {
        "carrier_and_fixed_frame": "Relative motor tilt needs a real journal.",
        "removable_hollow_sleeves": "Allows carrier insertion into closed stationary cheeks and future disassembly; standard bolts retain sleeves.",
    }
    metrics["consolidation"]["integral_motor_carrier_guard_parts"] = 2
    bed = frame.Shape.copy()
    bed.rotate(V(), V(0, 0, 1), 45)
    metrics["consolidation"]["fixed_frame_print_bounds_mm"] = [
        bed.BoundBox.XLength,
        bed.BoundBox.YLength,
        bed.BoundBox.ZLength,
    ]
    metrics["consolidation"]["separate_guard_ring_parts"] = 0
    metrics["consolidation"]["manufacturing_process"] = (
        "PA12 SLS/MJF; stored STL orientation is not a support-free FDM claim"
    )
    metrics["journal_assembly_order"] = [
        "Leave servos off the cradle while fitting the rotating carriers.",
        "Insert hollow D sleeves from outside, fit washers andM3x16 bolts/nuts without pinching stationary cheeks.",
        "Fit vendor motor fasteners, then servos and measured horn coupling.",
        "For driven-side journal service, remove servo first; withdraw sleeve8mm, lift2mm, then move away.",
    ]
    metrics["OEM_interfaces"] = {
        "DS_M005": {
            "source": SERVO_SOURCE,
            "drawing": SERVO_DRAWING,
            "horn_spline_teeth": 28,
            "mounting_ear_hole_diameter_mm": 1.8,
            "mounting_ear_pitch_mm": 19.5,
            "horn_retention_screw": "Unspecified; verify vendor fastener and actual horn.",
        },
        "RS1102": {
            "source": MOTOR_SOURCE,
            "motor_mount_screw_pitch_diameter_pattern_depth": "Not specified by examined manufacturer data; remains unresolved.",
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
    metrics["purchased_substitution_review"] = {
        "decision": "Retain four identical removable D sleeves; a standard bearing alone does not replace their drive and retention functions.",
        "candidate": "MR83ZZ, manufacturer-confirmed3x8x3mm",
        "source": BEARING_SOURCE,
        "inner_race_abutment_maximum_diameter_mm": 4.9,
        "why_not_installed": [
            "StandardM3 washerOD7 would bridge the small bearing races.",
            "Bearing housing fit, inner-race spacers and axial housing retention would add interfaces.",
            "DS-M005 actual28T horn spline dimensions and horn fastener remain unpublished; bearing substitution cannot solve that drive interface.",
            "Replacing only idle sleeves would add a second axle specification and handed carrier parts instead of one repeated sleeve SKU.",
        ],
        "marketplace_status": "Common bearing size is searchable on AliExpress, but no seller SKU or lot is verified.",
    }
    metrics["process_design_reference"] = {
        "source": CREALLO_SOURCE,
        "process": "PA12 SLS/MJF",
        "minimum_feature_wall_mm": 1.0,
        "long_frame_base_thickness_mm": FOOT_THICKNESS,
        "supplier_review_required": "The3mm foot/base follows the200mm-and-longer thin-part guidance; narrow journal/cage walls are local features, not a load qualification.",
    }
    metrics["unfinished_interfaces"] = [
        "RS1102 actual metric mounting screw and hole pattern/depth",
        "DS-M005 vendor horn screw and horn-to-sleeve coupling",
        "Servo mounting-ear retention",
        "Printed journal tolerances and running clearance",
        "Nut retention and clamp holding force",
        "Motor wires and strain relief",
        "Actual tilt endpoint stops",
    ]
    return {
        "group": group,
        "printed": printed,
        "references": refs,
        "clearances": clear,
        "pods": pods,
        "hardware": hardware,
        "purchased": hardware,
        "frame": frame,
        "crossmember": frame,
        "metrics": metrics,
    }
