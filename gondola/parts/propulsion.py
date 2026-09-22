"""Independent KST X06 direct gear drives with supported output stubs.

All dimensions are millimetres. Bought gear tooth outlines are visualization
models; manufacture only the marked PA12 parts. Unverified OEM interfaces and
physical fits remain explicit release blockers.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import (
    box,
    create_group,
    create_printed_part,
    mirrored_y,
    set_property,
    union,
)
from gondola.contracts.design import DESIGN_REVISION
from gondola.contracts.drive import (
    DRIVE_CONFIGURATIONS,
    FACE_WIDTH_MM,
    GEARS,
    MODULE_MM,
    PIVOT_Z_MM,
    SELECTED_DRIVE,
)
from gondola.contracts.equipment_interfaces import (
    BEARING_SOURCE,
    GEAR_SOURCE,
    PROPULSION_EVIDENCE,
    SHAFT_SOURCE,
    X06_DATASHEET_SOURCE,
)
from gondola.contracts.hardware import (
    CLAMP_SCREW_SOURCE,
    SERVO_NUT_SOURCE,
    SERVO_SCREW_SOURCE,
    SQUARE_NUT_SOURCE,
)

from . import purchased_hardware, rail, servo_bridge

V = App.Vector
BASE_Z = rail.SHOE_BOTTOM
FOOT_THICKNESS = 2.0
PIVOT_Z = PIVOT_Z_MM
PIVOT_HALF_SPAN = 80.0
GUARD_OUTER_RADIUS = 24.3
GUARD_INNER_RADIUS = 22.8
MOTOR_NOMINAL_DIAMETER = 13.5
MOTOR_DIAMETER = 13.6
MOTOR_LENGTH = 14.0
MOTOR_SOURCE = "https://www.happymodel.cn/index.php/2025/01/08/happymodel-rs1102-kv10000-kv13500-brushless-motor-for-micro-fpv-drone/"
PROP_SOURCE = "https://www.gemfanhobby.com/40mm-1610-pc-2-blade.html"
CREALLO_SOURCE = "https://creallo.com/ko/guide/design-spec-guide"
GEAR_MODULE = MODULE_MM
GEAR_FACE_WIDTH = FACE_WIDTH_MM
GEAR_HUB_START_Y = 38.0
GEAR_FACE_START_Y = 43.0
GEAR_END_Y = 46.0
BEARING_WINDOW_DIAMETER = 5.6
BEARING_CAP_THICKNESS = 1.5
BEARING_CAP_BOLT_Z = 18.5
BEARING_CAP_PEG_LENGTH = 1.0
CLAMP_SCREW_SKU = "M2X8_SOCKET_CAP"
NUT_SKU = "M2_SQUARE_NUT_DIN562"
BEARING_SKU = "MR63ZZ"


def cylinder(radius, length, origin, direction=(0, 1, 0)):
    return Part.makeCylinder(radius, length, V(*origin), V(*direction))


def _shifted(shape, x=0, y=0, z=0):
    result = shape.copy()
    result.translate(V(x, y, z))
    return result


def _checked(shape, label):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError(
            f"{label}: expected one valid solid, got {len(shape.Solids)}"
        )
    return shape


def bearing_shape():
    return cylinder(3, 2.5, (0, 0, 0)).cut(cylinder(1.5, 2.5, (0, 0, 0)))


def _bearing_retainer_blank(depth, start_y):
    # Align the cap and cup extension with the vertical post, eliminating the
    # sideways elbow. Keep the radial bolt offset for full-rotation clearance.
    arm_start_z = 3.5
    arm_half_width = 2.7
    return union(
        [
            cylinder(4.8, depth, (0, start_y, 0)),
            box(
                2 * arm_half_width,
                depth,
                BEARING_CAP_BOLT_Z + arm_half_width - arm_start_z,
                (-arm_half_width, start_y, arm_start_z),
            ),
        ]
    )


def bearing_cap_shape():
    cap = _bearing_retainer_blank(1.5, 0)
    cap = cap.cut(cylinder(2.8, 2, (0, -0.25, 0)))
    cap = cap.cut(cylinder(1.1, 2, (0, -0.25, BEARING_CAP_BOLT_Z)))
    cap = cap.fuse(
        cylinder(1, BEARING_CAP_PEG_LENGTH, (0, -BEARING_CAP_PEG_LENGTH, 6.2))
    )
    return _checked(cap, "Bearing outer-race cap")


def _bearing_cup(start_y, *, opens_positive=True):
    # Canonical bearing is Y0..2.5, with a 1.5mm inner shoulder before Y0.
    body = _bearing_retainer_blank(4, -1.5)
    body = body.cut(cylinder(3, 2.6, (0, 0, 0)))
    body = body.cut(cylinder(2.8, 4.2, (0, -1.6, 0)))
    body = body.cut(cylinder(1.1, 4.2, (0, -1.6, BEARING_CAP_BOLT_Z)))
    body = body.cut(cylinder(1.15, 1.7, (0, 0.9, 6.2)))
    if not opens_positive:
        body = mirrored_y(body, -1)
    return _shifted(body, y=start_y)


def shaft_clamp_shape():
    body = union([cylinder(3.1, 5.5, (0, 20.5, 0)), box(6, 5.5, 6, (1, 20.5, -3))])
    body = body.cut(cylinder(1.6, 6, (0, 20.25, 0)))
    body = body.cut(box(8, 6, 0.8, (0, 20.25, -0.4)))
    body = body.cut(cylinder(1.1, 8, (4.2, 23.25, -4), (0, 0, 1)))
    return _checked(body, "Split output shaft clamp")


def moving_carrier_shape():
    rear = union(
        [
            cylinder(8.2, 1.5, (-8.5, 0, 0), (1, 0, 0)),
            box(1.5, 52, 6.4, (-8.5, -26, -3.2)),
        ]
    )
    rear = rear.cut(cylinder(2.2, 3, (-9, 0, 0), (1, 0, 0)))
    # Known three-hole pitch is implemented as open radial slots, removing the
    # former0.2mm central ligament. OEM screw depth/head seat remain unverified.
    for angle in (0, 120, 240):
        slot = union(
            [box(3, 3.3, 1.8, (-9, 0, -0.9)), cylinder(0.9, 3, (-9, 3.3, 0), (1, 0, 0))]
        )
        slot.rotate(V(), V(1, 0, 0), angle)
        rear = rear.cut(slot)
    parts = [rear]
    for side in (-1, 1):
        strut = box(18, 5.5, 6.4, (-7, 20.5, -3.2))
        # The clamp slot remains open all the way through the adjacent strut.
        strut = strut.cut(cylinder(1.6, 6, (0, 20.25, 0)))
        strut = strut.cut(box(12, 6, 0.8, (0, 20.25, -0.4)))
        strut = strut.cut(cylinder(1.1, 8, (4.2, 23.25, -4), (0, 0, 1)))
        strut = strut.cut(box(5.8, 6, 0.4, (1.3, 20.25, 3)))
        strut = strut.cut(box(5.8, 6, 0.4, (1.3, 20.25, -3.4)))
        parts.append(mirrored_y(union([strut, shaft_clamp_shape()]), side))
    guard = cylinder(GUARD_OUTER_RADIUS, 2, (11, 0, 0), (1, 0, 0)).cut(
        cylinder(GUARD_INNER_RADIUS, 4, (10, 0, 0), (1, 0, 0))
    )
    parts.extend(
        [guard, box(2, 4, 6.4, (11, -26, -3.2)), box(2, 4, 6.4, (11, 22, -3.2))]
    )
    return _checked(union(parts), "Motor carrier with split shaft clamps")


def _output_support(sign):
    parts = []
    # An open perimeter foot is shared structure, independent of servo model.
    foot = box(18, 93, FOOT_THICKNESS, (-9, 20, BASE_Z)).cut(
        box(14, 89, 3, (-7, 22, BASE_Z - 0.5))
    )
    parts.append(foot)
    for side in (-1, 1):
        y_start = 26.5 if side > 0 else -30.5
        post = box(
            9.6,
            4,
            PIVOT_Z - BASE_Z - FOOT_THICKNESS,
            (-4.8, y_start + PIVOT_HALF_SPAN, BASE_Z + FOOT_THICKNESS),
        )
        post = post.cut(box(6.4, 5, 29.2, (-3.2, y_start + PIVOT_HALF_SPAN - 0.5, 9.8)))
        cup = _bearing_cup(28 if side > 0 else -28, opens_positive=side > 0)
        cup = _shifted(cup, y=PIVOT_HALF_SPAN, z=PIVOT_Z)
        post = post.cut(
            cylinder(
                3, 2.5, (0, PIVOT_HALF_SPAN + min(side * 28, side * 30.5), PIVOT_Z)
            )
        )
        post = post.cut(cylinder(2.8, 5, (0, PIVOT_HALF_SPAN + y_start - 0.5, PIVOT_Z)))
        parts.extend(
            [
                post,
                cup,
                box(18, 4, FOOT_THICKNESS, (-9, y_start + PIVOT_HALF_SPAN, BASE_Z)),
            ]
        )
    result = union(parts)
    if sign < 0:
        result = result.mirror(V(), V(1, 0, 0))
        result = mirrored_y(result, -1)
    return result


def fixed_frame_shape():
    """Common rail shoe, output supports and fixed servo-bridge seats."""
    wings = box(18, 70, FOOT_THICKNESS, (-9, -35, BASE_Z)).cut(
        box(20, rail.SHOE_WIDTH, 20, (-10, -rail.SHOE_WIDTH / 2, 0))
    )
    frame = union(
        [
            rail.shoe_shape(),
            wings,
            _output_support(1),
            _output_support(-1),
            servo_bridge.frame_seats(),
        ]
    )
    return _checked(servo_bridge.finish_frame(frame), "Common output-bearing frame")


def gear_shape(teeth, phase_degrees=0):
    """Nominal involute display outline; no unverified hub or tooth manufacturing."""
    if teeth not in GEARS:
        raise ValueError(f"Unsupported purchased gear: {teeth} teeth")
    pitch = GEAR_MODULE * teeth / 2
    root = GEAR_MODULE * (teeth - 2.5) / 2
    tip = GEAR_MODULE * (teeth + 2) / 2
    base = pitch * math.cos(math.radians(20))
    inv_pitch = math.tan(math.radians(20)) - math.radians(20)

    def half_angle(radius):
        alpha = math.acos(min(1, base / max(radius, base)))
        return math.pi / (2 * teeth) + inv_pitch - (math.tan(alpha) - alpha)

    points = []
    for index in range(teeth):
        center = math.radians(phase_degrees) + index * 2 * math.pi / teeth
        for flank in (-1, 1):
            radii = [root] + [
                max(root, base) + (tip - max(root, base)) * step / 8
                for step in range(9)
            ]
            if flank > 0:
                radii.reverse()
            for radius in radii:
                angle = center + flank * half_angle(radius)
                points.append(
                    V(
                        radius * math.cos(angle),
                        GEAR_FACE_START_Y,
                        radius * math.sin(angle),
                    )
                )
    face = Part.Face(Part.makePolygon(points + [points[0]]))
    tooth_body = face.extrude(V(0, GEAR_FACE_WIDTH, 0))
    hub_radius = GEARS[teeth].hub_diameter_mm / 2
    gear = union([tooth_body, cylinder(hub_radius, 5, (0, GEAR_HUB_START_Y, 0))])
    gear = gear.cut(
        cylinder(GEARS[teeth].bore_mm / 2, 8.2, (0, GEAR_HUB_START_Y - 0.1, 0))
    )
    # Supplied M3 radial set screw is included in this bought assembly. Its exact
    # length/tip are undocumented; do not invent a solid or an independent SKU.
    return _checked(gear, f"Bought {teeth}T gear")


def _reference(doc, parent, name, label, shape, notes, source="", clearance=False):
    obj = doc.addObject("Part::Feature", name)
    parent.addObject(obj)
    obj.Label, obj.Shape = label, shape
    set_property(obj, "Role", "Clearance" if clearance else "Hardware reference")
    set_property(obj, "Notes", notes)
    set_property(obj, "SourceURL", source)
    set_property(
        obj, "ManufacturingStatus", "Reference geometry only; exclude from fabrication"
    )
    if App.GuiUp:
        obj.ViewObject.ShapeColor = (
            (0.95, 0.65, 0.2) if clearance else (0.35, 0.4, 0.45)
        )
        obj.ViewObject.Visibility = not clearance
        if clearance:
            obj.ViewObject.Transparency = 88
    return obj


def _buy(doc, parent, name, shape, sku, notes, source, material, *, threaded=False):
    return purchased_hardware.add_hardware(
        doc,
        parent,
        name,
        "BUY | " + name,
        shape,
        sku,
        notes,
        source,
        material,
        thread_diameter=3.0
        if sku.startswith("GEABP")
        else (1.6 if sku.startswith("M1_6") else (2.0 if threaded else None)),
        thread_pitch=0.5
        if sku.startswith("GEABP")
        else (0.35 if sku.startswith("M1_6") else (0.4 if threaded else None)),
    )


def _buy_bearing(doc, parent, name, shape, notes):
    bearing = _buy(
        doc,
        parent,
        name,
        shape,
        BEARING_SKU,
        notes,
        BEARING_SOURCE,
        "Bearing steel",
    )
    set_property(bearing, "ReferenceMassGrams", 0.27, "App::PropertyFloat")
    set_property(bearing, "ReferenceMassSource", BEARING_SOURCE)
    return bearing


def _bolt_pair(doc, parent, name, origin, direction, grip=6, servo_ear=False):
    """Seat a bought bolt and nut on the specified grip planes."""
    rotation = App.Rotation(V(0, 0, 1), V(*direction))
    bolt = (
        purchased_hardware.servo_screw_shape()
        if servo_ear
        else purchased_hardware.screw_shape(8)
    ).copy()
    bolt.Placement = App.Placement(V(*origin), rotation)
    nut = (
        purchased_hardware.servo_nut_shape()
        if servo_ear
        else purchased_hardware.square_nut_shape()
    ).copy()
    # Servo case length is vertical; the hex nut's flats face the case ends.
    nut.Placement = App.Placement(V(*origin) + V(*direction) * grip, rotation)
    notes = (
        f"M1.6x0.35 x8 DIN84 cheese-head bolt and DIN934 hex nut;{grip:g}mm grip+1.3mm nut gives{8 - grip - 1.3:g}mm tip. NominalØ2 OEM hole gives0.2mm radial clearance,Ø3 head gives0.5mm case gap. Verify actual ear/seat fit."
        if servo_ear
        else f"Common M2x0.4 x8 A2 bolt and DIN562 square nut; nominal{grip:g}mm grip,1.2mm nut,{8 - grip - 1.2:g}mm tip projection. Hand snug; actual preload and printed bearing faces unqualified."
    )
    return [
        _buy(
            doc,
            parent,
            name + "Bolt",
            bolt,
            "M1_6X8_CHEESE_HEAD" if servo_ear else CLAMP_SCREW_SKU,
            notes,
            SERVO_SCREW_SOURCE if servo_ear else CLAMP_SCREW_SOURCE,
            "A2 stainless steel",
            threaded=True,
        ),
        _buy(
            doc,
            parent,
            name + "Nut",
            nut,
            "M1_6_HEX_NUT_DIN934" if servo_ear else NUT_SKU,
            notes,
            SERVO_NUT_SOURCE if servo_ear else SQUARE_NUT_SOURCE,
            "A2 stainless steel",
            threaded=True,
        ),
    ]


def _print(doc, parent, name, shape, notes, rotation=None, sku=None):
    obj = create_printed_part(
        doc, parent, name, "PRINT | " + name, shape, rotation or App.Rotation(), notes
    )
    set_property(
        obj,
        "ManufacturingStatus",
        "PA12 SLS/MJF fit prototype; physical fits and motion under load remain unqualified",
    )
    if sku:
        set_property(obj, "PrintSKU", sku)
    return obj


def build_fit_coupons(doc):
    """Reuse the actual bearing seat and cap before committing to full prints."""
    group = create_group(
        doc, "BearingFitCoupons", "Print first | MR63ZZ seat and cap registration"
    )
    cup = _print(
        doc,
        group,
        "BearingSeatFitSample",
        _bearing_cup(0),
        "Actual nominal 6 mm bearing cup, 5.6 mm shoulder opening and cap register. "
        "Print with the same process/material/finish as the supports. Finish and "
        "measure fit, concentricity and shield clearance using an actual MR63ZZ. "
        "Reuse one installed M2x8 screw and DIN562 nut for the trial; no extra "
        "onboard hardware is counted. This coupon does not qualify frame strength.",
    )
    cap = _print(
        doc,
        group,
        "BearingCapFitSample",
        bearing_cap_shape(),
        "Same cap as all four installed bearing retainers. Assemble against the "
        "bearing-seat coupon; confirm the locating peg seats, only the outer "
        "race is captured, and the shaft turns without shield contact or preload.",
        sku="MR63ZZ_OuterRaceCap",
    )
    return {"group": group, "printed": [cup, cap]}


def _build_coupling(doc, parent, prefix, sign):
    from . import servo_coupling as coupling

    def positioned(shape):
        shape = _shifted(shape, y=coupling.HORN_BOTTOM_Y)
        if sign < 0:
            shape.rotate(V(), V(0, 0, 1), 180)
        return shape

    horn = _buy(
        doc,
        parent,
        prefix + "ServoHorn",
        positioned(coupling.horn_shape()),
        coupling.HORN_SKU,
        "Bought KST0415.13 15T horn. The horn remains retained by its original servo screw; no printed spline is used. Nominal 0.2 mm case gap comes from the published spline protrusion and horn recess. Measure actual seating and retaining-screw clearance before assembly.",
        coupling.HORN_SOURCE,
        coupling.HORN_MATERIAL,
    )
    printed = []
    for suffix, shape, sku in (
        ("Adapter", coupling.adapter_shape(), "KST0415_GearAdapter"),
        ("Retainer", coupling.retainer_shape(), "KST0415_GearRetainer"),
    ):
        printed.append(
            _print(
                doc,
                parent,
                prefix + "HornGear" + suffix,
                positioned(shape),
                "Direct horn-to-gear fit prototype: the bought horn drives a printed adapter with a hollow journal in the stock 7 mm driver bore. One removable retainer and M2 bolt capture the horn blade. No separate input axle or input bearings. Install the OEM horn retaining screw first. Verify actual journal fit, set-screw grip, horn capture, clearance, creep and loaded servo deflection; geometry is not a torque qualification.",
                rotation=App.Rotation(V(0, 0, 1), 180) if sign < 0 else App.Rotation(),
                sku=sku,
            )
        )
    hardware = [horn]
    rotation = App.Rotation(V(0, 0, 1), V(*coupling.BOLT_DIRECTION))
    for positions in coupling.fastener_positions():
        for kind, anchor in positions.items():
            shape = (
                purchased_hardware.screw_shape(8).copy()
                if kind == "screw"
                else purchased_hardware.square_nut_shape().copy()
            )
            shape.Placement = App.Placement(V(*anchor), rotation)
            hardware.append(
                _buy(
                    doc,
                    parent,
                    prefix + "HornGearClamp" + ("Bolt" if kind == "screw" else "Nut"),
                    positioned(shape),
                    CLAMP_SCREW_SKU if kind == "screw" else NUT_SKU,
                    "M2x8 axial clamp through the horn adapter and rear retainer; nominal 5.7 mm grip plus 1.2 mm nut leaves 1.1 mm tip. Install around the retained stock horn and check full bidirectional capture before loading.",
                    CLAMP_SCREW_SOURCE if kind == "screw" else SQUARE_NUT_SOURCE,
                    "A2 stainless steel",
                    threaded=True,
                )
            )
    return {
        "printed": printed,
        "hardware": hardware,
        "references": [],
        "clearances": [],
    }


def manufacturing_wall_probes(drive=SELECTED_DRIVE):
    x, z = drive.input_x_mm, drive.input_z_mm
    y = servo_bridge.case_front_y() - 4.7 - servo_bridge.MOUNT_DEPTH / 2
    return [
        (
            "output_bearing_outer_wall",
            "PropulsionFixedFrame",
            (-4.81, PIVOT_HALF_SPAN + 29, PIVOT_Z),
            (-2.99, PIVOT_HALF_SPAN + 29, PIVOT_Z),
            1.8,
        ),
        (
            "bearing_cap_plate",
            "PortOutputBearingCapPositive",
            (-3.5, PIVOT_HALF_SPAN + 30.49, PIVOT_Z),
            (-3.5, PIVOT_HALF_SPAN + 32.01, PIVOT_Z),
            1.5,
        ),
        (
            "servo_cradle_left_wall",
            "ServoDriveBridge",
            (x - servo_bridge.CRADLE_WIDTH / 2 - 0.01, y, z - 5),
            (x - servo_bridge.CASE_WINDOW_WIDTH / 2 + 0.01, y, z - 5),
            servo_bridge.SIDE_WALL,
        ),
        (
            "servo_cradle_right_wall",
            "ServoDriveBridge",
            (x + servo_bridge.CASE_WINDOW_WIDTH / 2 - 0.01, y, z - 5),
            (x + servo_bridge.CRADLE_WIDTH / 2 + 0.01, y, z - 5),
            servo_bridge.SIDE_WALL,
        ),
        (
            "servo_cradle_upper_wall",
            "ServoDriveBridge",
            (x, y, z + 8.09),
            (x, y, z + 10.11),
            2.0,
        ),
        (
            "servo_bridge_pad",
            "ServoDriveBridge",
            (15.5, 15, 8.69),
            (15.5, 15, 10.71),
            2.0,
        ),
        (
            "servo_bridge_ring",
            "ServoDriveBridge",
            (18.5, 0, 10.39),
            (18.5, 0, 12.41),
            2.0,
        ),
        (
            "servo_bridge_frame_seat",
            "PropulsionFixedFrame",
            (12, 18, 5.69),
            (12, 18, 8.71),
            3.0,
        ),
        (
            "servo_bridge_y_datum",
            "PropulsionFixedFrame",
            (-15, -13.51, 9.5),
            (-15, -11.99, 9.5),
            1.5,
        ),
    ]


def _build_frame(doc, module, spec):
    """Keep the supported output mechanism independent of the servo selection."""
    frame = _print(
        doc,
        module,
        "PropulsionFixedFrame",
        fixed_frame_shape(),
        "Common integral rail shoe and output-bearing frame, with two broad local seats for the removable paired servo bridge. One inside Y datum and one outside X stop locate the bridge; two M2 bolts clamp it. Both supported gear ratios use this same frame. Actual printed seating, gear centre distance and creep remain unqualified. Finish nominal Ø6 bearing seats using a matching coupon; removable caps capture outer races without designed shield or inner-race preload.",
        App.Rotation(V(0, 0, 1), 45),
        sku=spec.frame_sku,
    )
    set_property(frame, "IntegratedRailShoe", True, "App::PropertyBool")
    set_property(frame, "CarriageContactZ", BASE_Z, "App::PropertyLength")
    set_property(frame, "RailCenterY", 0, "App::PropertyLength")
    set_property(frame, "FootThickness", FOOT_THICKNESS, "App::PropertyLength")
    return frame


def _build_output_pod(doc, assembly, prefix, sign, spec):
    """Build one rotating carrier and its fixed bearings in native object order."""
    printed, hardware = [], []
    pod = create_group(doc, prefix + "Pod", prefix + " motor/guard and output gear")
    assembly.addObject(pod)
    pod.Placement.Base = V(0, sign * PIVOT_HALF_SPAN, PIVOT_Z)
    pod.Placement.Rotation = App.Rotation(V(0, 1, 0), 1)
    for key, value in (("Tilt", 0), ("MinimumTilt", -180), ("MaximumTilt", 180)):
        set_property(pod, key, value, "App::PropertyAngle", "Motion")
    pod.setExpression(
        "Placement.Rotation.Angle", "min(MaximumTilt; max(MinimumTilt; Tilt))"
    )
    set_property(
        pod,
        "Notes",
        f"Bounded output -180..180 degrees, no endpoint wrap. Input servo moves oppositely by 1/{spec.ratio:g}. Verify actual servo travel, wire loops, backlash and endpoints before operation.",
    )
    carrier = _print(
        doc,
        pod,
        prefix + "MotorCarrier",
        moving_carrier_shape(),
        "Integral guard, motor plate and two splitØ3.2 shaft clamps. Two separateØ3 shafts stop before the motor. M2x8 clamps provide frictional torque and axial grip; strength, creep and slip require tests. Nominal0.5mm carrier/frame end clearance provides low-load axial travel stops; these are rubbing stops, not bearing inner-ring retention. Three1.8mm open radial mounting slots followM1.4/PCD6.6 and merge into the rear relief, avoiding a0.2mm ligament. Actual OEM screw length, usable depth, head bearing footprint and rearclipclearance remain unverified.",
        App.Rotation(V(0, 1, 0), -90),
        sku="GearedMotorCarrier",
    )
    printed.append(carrier)
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        driven = side == -sign
        low, high = (20, 44) if driven else (20, 34)
        shaft = cylinder(1.5, high - low, (0, low, 0))
        if driven:
            shaft = shaft.cut(box(2, 5, 4, (1, 36, -2)))
        shaft = mirrored_y(shaft, side)
        sku = "PSFU3-24-FC5-A3" if driven else "PSFU3-14"
        hardware.append(
            _buy(
                doc,
                pod,
                prefix + "OutputShaft" + suffix,
                shaft,
                sku,
                "Ø3 h5 separate output stub, never a through-shaft. Driven shaft usesfactoryFC5-A3 flat,depth0.5, outsidebearing; idle shaft remainsround. Clockactualflat towardincludedgearsetscrewaftertoothphasing. Final length/edge treatment and clamp grip require purchased-part fit confirmation.",
                SHAFT_SOURCE,
                "SUJ2-equivalent hard-chrome steel",
            )
        )
        hardware.extend(
            _bolt_pair(
                doc,
                pod,
                prefix + "OutputClamp" + suffix,
                (4.2, side * 23.25, -3),
                (0, 0, 1),
            )
        )
        # All bearing geometry is fixed; each shaft rotates with the pod.
        bearing_start = sign * PIVOT_HALF_SPAN + min(side * 28, side * 30.5)
        bearing = _buy_bearing(
            doc,
            assembly,
            prefix + "OutputBearing" + suffix,
            _shifted(bearing_shape(), y=bearing_start, z=PIVOT_Z),
            "MR63ZZ3×6×2.5, annular clearance envelope. Fixed outer ring captured by frame shoulder/cap; finish the printed seat. No shield/inner-ring axial preload.",
        )
        hardware.append(bearing)
        cap = bearing_cap_shape()
        if side < 0:
            cap = mirrored_y(cap, -1)
        cap = _shifted(cap, y=sign * PIVOT_HALF_SPAN + side * 30.5, z=PIVOT_Z)
        printed.append(
            _print(
                doc,
                assembly,
                prefix + "OutputBearingCap" + suffix,
                cap,
                "Outer-race-only positive cap;Ø5.6 opening exceeds bearing maker5.4 minimum. Finish mating faces; do not preload shields. Ø2 locating peg and bolt constrain cap rotation; finish and measure concentricity. NominalØ2.3 pocket fit does not guarantee shield clearance with raw printing tolerances.",
                rotation=App.Rotation(V(0, 0, 1), 180) if side < 0 else App.Rotation(),
                sku="MR63ZZ_OuterRaceCap",
            )
        )
        # The cap bolt seats through1.5mm cap and4mm cup; bearing fit is separate.
        origin = (
            0,
            sign * PIVOT_HALF_SPAN + side * 32,
            PIVOT_Z + BEARING_CAP_BOLT_Z,
        )
        hardware.extend(
            _bolt_pair(
                doc,
                assembly,
                prefix + "OutputBearingCap" + suffix,
                origin,
                (0, -side, 0),
                grip=5.5,
            )
        )
    driver_angle = math.degrees(
        math.atan2(PIVOT_Z - spec.input_z_mm, -sign * spec.input_x_mm)
    )
    output_angle = driver_angle + 180 + 180 / spec.output.teeth
    output_gear = gear_shape(spec.output.teeth, output_angle)
    output_gear = mirrored_y(output_gear, sign)
    output_gear = _shifted(output_gear, y=-sign * PIVOT_HALF_SPAN)
    hardware.append(
        _buy(
            doc,
            pod,
            prefix + "OutputGear",
            output_gear,
            spec.output.sku,
            "Bought POM20T module0.5 bore3H7,face3,overall8,hubØ8.5; included radialM3 set screw provides shaft grip. Set-screw length/tip and allowable torque unverified. CAD tooth profile is nominal visualization only.",
            GEAR_SOURCE,
            "POM",
        )
    )
    return pod, printed, hardware, driver_angle


def _build_input_drive(doc, mount, prefix, sign, driver_angle, spec):
    """Rotate the bought driver gear directly with the stock servo horn."""
    drive = create_group(
        doc,
        prefix + "InputDrive",
        prefix + f" servo gear rotates at -output/{spec.ratio:g}",
    )
    mount.addObject(drive)
    drive.Placement.Rotation = App.Rotation(V(0, 1, 0), 1)
    drive.setExpression(
        "Placement.Rotation.Angle",
        f"-{prefix}Pod.Placement.Rotation.Angle / {spec.ratio:g}",
    )
    gear = _buy(
        doc,
        drive,
        prefix + "DriverGear",
        mirrored_y(gear_shape(spec.driver.teeth, driver_angle), sign),
        spec.driver.sku,
        f"Bought POM {spec.driver.teeth}T module 0.5, bore {spec.driver.bore_mm:g}H7, face 3, overall 8, hub Ø10; supplied radial M3 set screw. The stock servo horn and removable printed adapter drive this gear without an auxiliary axle or input bearings. Output rotates oppositely at {spec.ratio:g} times the servo angle; torque is reduced. Check adapter grip and servo radial-load deflection in a physical prototype. Tooth outline is nominal display geometry.",
        GEAR_SOURCE,
        "POM",
    )
    return drive, [gear]


def _build_servo(doc, mount, prefix, sign):
    """Mount the sourced vertical X06 case on its replaceable bridge cradle."""
    hardware = []
    front = servo_bridge.case_front_y()
    servo = box(7, 16.6, 20, (-3.5, front - 16.6, -15))
    for hole_z in (-17, 7):
        ear = box(7, 1, 4, (-3.5, front - 4.7, hole_z - 2)).cut(
            cylinder(1, 1.2, (0, front - 4.8, hole_z))
        )
        servo = servo.fuse(ear)
    servo = servo.fuse(cylinder(1.95, 2.7, (0, front, 0)))
    servo = mirrored_y(servo, sign)
    for hole_z, suffix in ((-17, "Lower"), (7, "Upper")):
        hardware.extend(
            _bolt_pair(
                doc,
                mount,
                prefix + "ServoEar" + suffix,
                (0, sign * (front - 3.7), hole_z),
                (0, -sign, 0),
                grip=6,
                servo_ear=True,
            )
        )
    servo_ref = _reference(
        doc,
        mount,
        prefix + "Servo",
        "KST X06 V6.0 vertical case 20×7×16.6; 6 g",
        servo,
        "Official case envelope, rotated 90 degrees about the output axis so the body extends downward. Output axis is 5 mm from the case end; sourced ear axes are Ø2 on 24 mm pitch. The closed cradle has two 2 mm side walls and an 8×21 mm axial case opening. M1.6×8 DIN84 through-bolts clamp 5 mm printed grip plus 1 mm ears. Ear transverse outline remains a conservative 7 mm envelope. Smooth Ø3.90×2.7 spline envelope does not claim tooth detail. Actual case fit, horn seating, OEM retaining screw, wiring exit and loaded travel require physical confirmation. Direct gearing transfers mesh load to the servo output bearings; allowable radial load is unpublished.",
        X06_DATASHEET_SOURCE,
    )
    return [servo_ref], hardware


def _build_servo_drive(doc, assembly, prefix, sign, driver_angle, spec):
    """Keep each independent servo/input drive on its fixed native axis."""
    mount = create_group(
        doc,
        prefix + "ServoMount",
        prefix + " servo and direct drive on removable bridge",
    )
    assembly.addObject(mount)
    mount.Placement.Base = V(sign * spec.input_x_mm, 0, spec.input_z_mm)
    set_property(
        mount,
        "ServiceSequence",
        "At neutral, disconnect power and free the leads. Service the removable "
        "gear/horn coupling before withdrawing one servo from its cradle, or "
        "remove both small output gears and two bridge mount pairs to exchange "
        "the complete paired module. Follow the checked ordered paths. Printed fit and handling "
        "require a prototype check.",
    )
    drive, hardware = _build_input_drive(doc, mount, prefix, sign, driver_angle, spec)
    references, servo_hardware = _build_servo(doc, mount, prefix, sign)
    coupling = _build_coupling(doc, drive, prefix, sign)
    return {
        "printed": coupling["printed"],
        "hardware": hardware + servo_hardware + coupling["hardware"],
        "references": references + coupling["references"],
        "clearances": coupling["clearances"],
    }


def _build_motor_references(doc, pod, prefix, sign):
    """Place the motor, shaft and propeller envelopes on the rotating carrier."""
    references = []
    motor = _reference(
        doc,
        pod,
        prefix + "Motor",
        "RS1102 conservative maximum body envelope",
        cylinder(MOTOR_DIAMETER / 2, MOTOR_LENGTH, (-7, 0, 0), (1, 0, 0)),
        "Published threeM1.4 axes onPCD6.6 are represented by open1.8mm radial slots; mounting depth, rear clip and head seating remain unfinished. Never run a tilt through-shaft through this motor envelope.",
        MOTOR_SOURCE,
    )
    set_property(motor, "Diameter", MOTOR_DIAMETER, "App::PropertyLength")
    set_property(
        motor, "NominalDiameter", MOTOR_NOMINAL_DIAMETER, "App::PropertyLength"
    )
    set_property(motor, "EnvelopeLength", MOTOR_LENGTH, "App::PropertyLength")
    set_property(motor, "CatalogMassGrams", 2.8, "App::PropertyFloat")
    references.append(motor)
    references.append(
        _reference(
            doc,
            pod,
            prefix + "Shaft",
            "RS1102 shaft envelope",
            cylinder(0.75, 5, (7, 0, 0), (1, 0, 0)),
            "PublishedØ1.5;5mm projection provisional.",
            MOTOR_SOURCE,
        )
    )
    propeller = _reference(
        doc,
        pod,
        prefix + "PropellerDisk",
        "Gemfan1610 spinning envelope",
        cylinder(20, 5, (9.5, 0, 0), (1, 0, 0)),
        "Published40mm diameter,5mm hub thickness applied to full disk; not blade geometry.",
        PROP_SOURCE,
    )
    set_property(propeller, "PropDiameter", 40, "App::PropertyLength")
    set_property(propeller, "HubThickness", 5, "App::PropertyLength")
    set_property(propeller, "Variant", "CW" if sign > 0 else "CCW")
    references.append(propeller)
    return references


def _build_sweep_reserve(doc, assembly, prefix, sign):
    """Create the separate clearance reference for external vehicle equipment."""
    bound = union([cylinder(30, 52, (0, -26, 0)), cylinder(10, 88, (0, -44, 0))])
    bound = _shifted(bound, y=sign * PIVOT_HALF_SPAN, z=PIVOT_Z)
    return _reference(
        doc,
        assembly,
        prefix + "SweepBound",
        "Conservative complete output rotation reserve",
        bound,
        "Main motor/guard radius30 overY±26, output clamps/bolts/shafts/gears radius10 overY±44. Excludes the separately validated gear mesh and input mechanism; full bound is used only against external vehicle equipment.",
        clearance=True,
    )


def _build_propulsion_side(doc, module, drive_module, prefix, sign, spec):
    """Assemble one independent gear drive without changing native object order."""
    assembly = create_group(
        doc, prefix + "Assembly", prefix + " independent geared propulsion"
    )
    module.addObject(assembly)
    pod, printed, hardware, driver_angle = _build_output_pod(
        doc, assembly, prefix, sign, spec
    )
    input_parts = _build_servo_drive(
        doc, drive_module, prefix, sign, driver_angle, spec
    )
    motor_references = _build_motor_references(doc, pod, prefix, sign)
    sweep_reserve = _build_sweep_reserve(doc, assembly, prefix, sign)
    return {
        "printed": printed + input_parts["printed"],
        "hardware": hardware + input_parts["hardware"],
        "references": input_parts["references"] + motor_references,
        "clearances": input_parts["clearances"] + [sweep_reserve],
        "pods": [pod],
    }


def _module_metrics(printed, hardware, references, spec):
    from .servo_coupling import metrics as coupling_metrics

    return {
        "revision": DESIGN_REVISION,
        "module_count": 1,
        "main_pod_count": 2,
        "tilt_range_deg": [-180, 180],
        "independent_native_tilt": True,
        "single_rail_center_y_mm": 0,
        "integrated_rail_shoe": True,
        "printed_part_count": len(printed),
        "purchased_mechanism_hardware_count": len(hardware),
        "device_reference_count": len(references),
        "main_pivot_centers_mm": [
            [0, PIVOT_HALF_SPAN, PIVOT_Z],
            [0, -PIVOT_HALF_SPAN, PIVOT_Z],
        ],
        "gear_drive": {
            "configuration": spec.key,
            "driver_teeth": spec.driver.teeth,
            "output_teeth": spec.output.teeth,
            "module_mm": GEAR_MODULE,
            "nominal_center_mm": spec.center_distance_mm,
            "face_width_mm": 3,
            "gear_axial_span_mm": [GEAR_HUB_START_Y, GEAR_END_Y],
            "input_axis_abs_x_mm": spec.input_x_mm,
            "input_axis_z_mm": spec.input_z_mm,
            "output_to_input_angle_ratio": -spec.ratio,
            "fixed_frame_print_sku": spec.frame_sku,
            "servo_bridge_print_sku": spec.bridge_sku,
            "input_mount": "Direct stock-horn drives on one removable paired bridge. Two broad seats under the cradles and unilateral locating datums establish the fixed position; two M2 mount pairs clamp it. A supported ratio change replaces the bridge and both driver gears while retaining the common output frame.",
            "supported_configurations": list(DRIVE_CONFIGURATIONS),
            "limits": "Bounded motion only. Servo travel, tooth clearance, backlash, clamp slip and wire loops require physical calibration.",
        },
        "shaft_topology": {
            "output_stub_count": 4,
            "output_driven_length_mm": 24,
            "output_idle_length_mm": 14,
            "input_count": 0,
            "through_shaft_allowed": False,
            "reason": "A through-shaft crosses the motor. Separate stubs leave the motor bay clear.",
        },
        "bearing_seats": {
            "count": 4,
            "dimensions_mm": [3, 6, 2.5],
            "nominal_bore_mm": 6,
            "cap_opening_mm": BEARING_WINDOW_DIAMETER,
            "seat_shoulder_mm": 1.5,
            "cap_thickness_mm": BEARING_CAP_THICKNESS,
            "finishing": "Nominal fit prototype. Print matching coupon, finish and measure bearing seats; Creallo tolerances do not prove bearing fit. Do not force bearings into undersized seats or preload shields.",
            "running_axial_clearance_mm": 0.5,
        },
        "process_design_reference": {
            "source": CREALLO_SOURCE,
            "process": "PA12 SLS/MJF",
            "minimum_feature_wall_mm": 1.5,
            "guard_radial_wall_mm": 1.5,
            "frame_foot_thickness_mm": 2,
        },
        "OEM_interfaces": PROPULSION_EVIDENCE,
        "horn_coupling": coupling_metrics(),
        "unfinished_interfaces": [
            "Measured OEM horn seating and retaining screw",
            "Actual direct horn-to-gear adapter clearance and grip",
            "Servo output-bearing deflection under direct gear mesh load",
            "Printed bridge seating, cradle fit and retained gear center distance",
            "Motor rear clip, seat and M1.4 usable depth",
            "Printed bearing fits and outer-race capture",
            "Shaft/gear/clamp torque and axial grip",
            "KST loaded travel, backlash and wire loops",
        ],
        "printed_parts": [
            {
                "name": o.Name,
                "volume_mm3": o.Shape.Volume,
                "solid_count": len(o.Shape.Solids),
                "valid_brep": o.Shape.isValid(),
            }
            for o in printed
        ],
        "printed_volume_mm3": sum(o.Shape.Volume for o in printed),
    }


def build_propulsion_module(doc, drive=SELECTED_DRIVE):
    if DRIVE_CONFIGURATIONS.get(drive.key) != drive:
        raise ValueError(
            "Only the sourced, supported drive configurations can be built"
        )
    module = create_group(
        doc,
        "MainPropulsionModule",
        f"Independent KST X06 {drive.driver.teeth}:{drive.output.teeth} gear drives | four output stubs",
    )
    set_property(module, "GearConfiguration", drive.key, group="Drive")
    set_property(
        module,
        "DriveContract",
        json.dumps(drive.contract(), sort_keys=True),
        group="Drive",
    )
    module.setEditorMode("GearConfiguration", 1)
    module.setEditorMode("DriveContract", 1)
    frame = _build_frame(doc, module, drive)
    drive_module = create_group(
        doc, "ServoDriveModule", "Replaceable paired servo and input-gear module"
    )
    module.addObject(drive_module)
    bridge = _print(
        doc,
        drive_module,
        "ServoDriveBridge",
        servo_bridge.bridge_shape(drive),
        "One paired bridge with straight 2 mm servo walls and an open connecting ring. Each cradle sits on its own broad frame seat; the ring joins them for handling. Two M2 mount pairs retain it against fixed X/Y datums. For bench replacement remove both small output gears, then the mount pairs; lift 0.5 mm and slide 80 mm in +X with servos, horns and large gears assembled. All output shafts, bearings, caps and motor carriers remain installed. Verify actual seating, centre distance and handling; do not force a warped bridge flat with its screws.",
        sku=drive.bridge_sku,
    )
    mount_hardware = []
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        mount_hardware.extend(
            _bolt_pair(
                doc,
                module,
                "ServoBridge" + prefix,
                (
                    sign * servo_bridge.BOLT_X,
                    sign * servo_bridge.BOLT_Y,
                    servo_bridge.PAD_TOP_Z,
                ),
                (0, 0, -1),
                grip=servo_bridge.MOUNT_GRIP,
            )
        )
    parts = {
        "printed": [frame, bridge],
        "hardware": mount_hardware,
        "references": [],
        "clearances": [],
        "pods": [],
    }
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        side = _build_propulsion_side(doc, module, drive_module, prefix, sign, drive)
        for kind, objects in parts.items():
            objects.extend(side[kind])
    doc.recompute()
    return {
        "group": module,
        "printed": parts["printed"],
        "references": parts["references"],
        "clearances": parts["clearances"],
        "pods": parts["pods"],
        "hardware": parts["hardware"],
        "frame": frame,
        "metrics": _module_metrics(
            parts["printed"], parts["hardware"], parts["references"], drive
        ),
    }
