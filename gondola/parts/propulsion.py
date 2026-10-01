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
    translated_shape,
    union,
)
from gondola.contracts.design import DESIGN_REVISION, HARDWARE_MATERIALS
from gondola.contracts.drive import (
    DRIVE_CONFIGURATIONS,
    GEARS,
    MODULE_MM,
    PIVOT_SPAN_MM,
    PIVOT_Z_MM,
    PRESSURE_ANGLE_DEG,
    SELECTED_DRIVE,
)
from gondola.contracts.equipment_interfaces import (
    BEARING_SOURCE,
    PROPULSION_EVIDENCE,
    SHAFT_SOURCE,
    X06_DATASHEET_SOURCE,
)
from gondola.contracts.fasteners import KIT_MATERIAL, SERVO_SCREW_MATERIAL
from gondola.contracts.hardware import (
    CLAMP_SCREW_SOURCE,
    HEX_NUT_SOURCE,
    SERVO_NUT_SOURCE,
    SERVO_SCREW_SOURCE,
)

from . import (
    bearing_retention,
    purchased_hardware,
    rail,
    servo_bridge,
    servo_coupling,
    servo_envelope,
)

V = App.Vector
BASE_Z = 1.5
FOOT_THICKNESS = 5.0
FOOT_BOTTOM_Z = servo_bridge.SEAT_Z - FOOT_THICKNESS
FOOT_WIDTH = 18.0
BEARING_POST_WIDTH = 13.0
RAIL_BOLT_OFFSET_X = servo_bridge.CLAMP_AXIS_X
RAIL_CONTACT_LENGTH = servo_bridge.CENTRAL_SEAT_LENGTH
PIVOT_Z = PIVOT_Z_MM
PIVOT_HALF_SPAN = PIVOT_SPAN_MM / 2
GUARD_OUTER_RADIUS = 25.0
GUARD_INNER_RADIUS = 23.0
# Space for a later replacement rotor, not a fitted 50 mm propeller option.
# The current nominal guard remains specific to the 40 mm prop.
FUTURE_ROTOR_PROPELLER_DIAMETER = 50.0
FUTURE_ROTOR_HALF_WIDTH = 30.0
FUTURE_ROTOR_ORBIT_RADIUS = 34.0
MOTOR_NOMINAL_DIAMETER = 13.5
MOTOR_DIAMETER = 13.6
MOTOR_LENGTH = 8.8
MOTOR_LENGTH_UPPER_TOLERANCE = 0.1
MOTOR_TOTAL_LENGTH = 14.0
MOTOR_SHAFT_PROJECTION = 4.0
# The printed mounting face is the controlled datum. Overall motor length also
# includes the rear clip and front shaft; it is not the motor body length.
MOTOR_MOUNT_FACE_X = -5.0
MOTOR_FRONT_X = MOTOR_MOUNT_FACE_X + MOTOR_LENGTH
MOTOR_REAR_PROJECTION = MOTOR_TOTAL_LENGTH - MOTOR_LENGTH - MOTOR_SHAFT_PROJECTION
# Explicit illustrative seating case, not an installed measurement. The 5 mm
# hub thickness does not establish the blades' axial swept volume.
PROPELLER_PREVIEW_SEATING_OFFSET = 0.0
PROPELLER_ENVELOPE_THICKNESS = 5.0
PROPELLER_PLANE_X = (
    MOTOR_FRONT_X + PROPELLER_PREVIEW_SEATING_OFFSET + PROPELLER_ENVELOPE_THICKNESS / 2
)
MOTOR_PLATE_THICKNESS = 3.0
MOTOR_PLATE_BACK_X = MOTOR_MOUNT_FACE_X - MOTOR_PLATE_THICKNESS
GUARD_DEPTH = 2.0
# Independent printed guard datum: X8..10 clears the existing clamp head/nut
# service envelopes without new connector blocks or long tool pockets. Physical
# blade coverage still depends on unverified seating and blade axial geometry.
GUARD_PLANE_X = 9.0
CARRIER_SIDE_THICKNESS = 8.0
CARRIER_SIDE_FRONT_X = 11.0
CARRIER_SIDE_LENGTH = CARRIER_SIDE_FRONT_X - MOTOR_PLATE_BACK_X
MOTOR_SOURCE = "https://www.happymodel.cn/index.php/2025/01/08/happymodel-rs1102-kv10000-kv13500-brushless-motor-for-micro-fpv-drone/"
PROP_SOURCE = "https://www.gemfanhobby.com/40mm-1610-pc-2-blade.html"
CREALLO_SOURCE = "https://creallo.com/ko/guide/design-spec-guide"
GEAR_MODULE = MODULE_MM
GEAR_HUB_START_Y = servo_coupling.HORN_BOTTOM_Y + servo_coupling.GEAR_START_Y
GEAR_FACE_START_Y = GEAR_HUB_START_Y + SELECTED_DRIVE.driver.hub_extension_mm
GEAR_END_Y = GEAR_FACE_START_Y + SELECTED_DRIVE.driver.face_width_mm


def gear_axial_span(teeth):
    """Centre the purchased 3 mm driver face within the 5 mm output face."""
    spec = GEARS[teeth]
    centre = (GEAR_FACE_START_Y + GEAR_END_Y) / 2
    face_start = centre - spec.face_width_mm / 2
    return (
        face_start - spec.hub_extension_mm,
        face_start,
        face_start + spec.face_width_mm,
    )


BEARING_START_Y = 33.75
BEARING_WINDOW_DIAMETER = bearing_retention.SHIELD_OPENING_DIAMETER
BEARING_GUIDE_START_Y = BEARING_START_Y + bearing_retention.GUIDE_START_Y
BEARING_SHOULDER_Y = BEARING_START_Y + bearing_retention.SHOULDER_START_Y
BEARING_SHOULDER_THICKNESS = bearing_retention.SHOULDER_THICKNESS
BEARING_POST_DEPTH = (
    BEARING_SHOULDER_Y + BEARING_SHOULDER_THICKNESS - BEARING_GUIDE_START_Y
)
CARRIER_END_Y = 31.25
CARRIER_CLAMP_START_Y = 21.25
CARRIER_CLAMP_LENGTH = CARRIER_END_Y - CARRIER_CLAMP_START_Y
CARRIER_CLAMP_BOLT_Y = (CARRIER_CLAMP_START_Y + CARRIER_END_Y) / 2
CARRIER_NUT_RECESS_DEPTH = CARRIER_SIDE_THICKNESS / 2 - 2.5
CARRIER_NUT_POCKET_AF = 4.25
SHAFT_ASSEMBLY_RETRACTION = 12.0
SHAFT_FINAL_WITHDRAWAL = 20.0
OUTPUT_SHAFT_INNER_Y = 20.0
OUTPUT_DRIVEN_SHAFT_LENGTH = 34.0
OUTPUT_IDLE_SHAFT_LENGTH = 20.0
OUTPUT_SHAFT_FLAT_LENGTH = 5.0
OUTPUT_SHAFT_SWEEP_HALF_LENGTH = OUTPUT_SHAFT_INNER_Y + OUTPUT_DRIVEN_SHAFT_LENGTH
NUT_SKU = "M2_HEX_NUT"
BEARING_SKU = "BEARING_3X6X2_5"


def cylinder(radius, length, origin, direction=(0, 1, 0)):
    return Part.makeCylinder(radius, length, V(*origin), V(*direction))


def _checked(shape, label):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError(
            f"{label}: expected one valid solid, got {len(shape.Solids)}"
        )
    return shape


def bearing_shape():
    return cylinder(3, 2.5, (0, 0, 0)).cut(cylinder(1.5, 2.5, (0, 0, 0)))


def _bearing_cup(start_y, *, positive_side=True):
    """Fixed round seat and shoulder; canonical bearing occupies Y0..2.5."""
    body = bearing_retention.cup_shape()
    if not positive_side:
        body = mirrored_y(body, -1)
    return translated_shape(body, y=start_y)


def _carrier_clamp_cuts():
    """Positive-Y clamp tools, applied after all carrier/guard unions."""
    passage_start = CARRIER_CLAMP_START_Y - 0.25
    passage_length = CARRIER_CLAMP_LENGTH + 0.5
    pocket = translated_shape(
        purchased_hardware.hex_prism(CARRIER_NUT_POCKET_AF, 2, z=2.5),
        x=4.2,
        y=CARRIER_CLAMP_BOLT_Y,
    )
    return (
        cylinder(1.6, passage_length, (0, passage_start, 0)),
        box(CARRIER_SIDE_FRONT_X + 1, passage_length, 0.8, (0, passage_start, -0.4)),
        cylinder(1.1, 8, (4.2, CARRIER_CLAMP_BOLT_Y, -4), (0, 0, 1)),
        cylinder(2.9, 2, (4.2, CARRIER_CLAMP_BOLT_Y, -4.5), (0, 0, 1)),
        pocket,
    )


def _carrier_side_blank():
    return box(
        CARRIER_SIDE_LENGTH,
        CARRIER_CLAMP_LENGTH,
        CARRIER_SIDE_THICKNESS,
        (MOTOR_PLATE_BACK_X, CARRIER_CLAMP_START_Y, -CARRIER_SIDE_THICKNESS / 2),
    )


def _carrier_side_shape():
    """Isolated clamp for hardware insertion/service checks."""
    body = _carrier_side_blank()
    for tool in _carrier_clamp_cuts():
        body = body.cut(tool)
    return _checked(body, "Integral carrier side and split shaft clamp")


def moving_carrier_shape():
    rear = union(
        [
            cylinder(8.2, MOTOR_PLATE_THICKNESS, (MOTOR_PLATE_BACK_X, 0, 0), (1, 0, 0)),
            box(
                MOTOR_PLATE_THICKNESS,
                2 * CARRIER_END_Y,
                CARRIER_SIDE_THICKNESS,
                (MOTOR_PLATE_BACK_X, -CARRIER_END_Y, -CARRIER_SIDE_THICKNESS / 2),
            ),
        ]
    )
    passage_x = MOTOR_PLATE_BACK_X - 0.5
    passage_length = MOTOR_PLATE_THICKNESS + 1
    rear = rear.cut(cylinder(2.2, passage_length, (passage_x, 0, 0), (1, 0, 0)))
    # Known three-hole pitch is implemented as open radial slots, removing the
    # former0.2mm central ligament. OEM screw depth/head seat remain unverified.
    for angle in (0, 120, 240):
        slot = union(
            [
                box(passage_length, 3.3, 1.8, (passage_x, 0, -0.9)),
                cylinder(0.9, passage_length, (passage_x, 3.3, 0), (1, 0, 0)),
            ]
        )
        slot.rotate(V(), V(1, 0, 0), angle)
        rear = rear.cut(slot)
    parts = [rear]
    side_shape = _carrier_side_blank()
    for side in (-1, 1):
        parts.append(mirrored_y(side_shape, side))
    guard_start = GUARD_PLANE_X - GUARD_DEPTH / 2
    guard = cylinder(
        GUARD_OUTER_RADIUS, GUARD_DEPTH, (guard_start, 0, 0), (1, 0, 0)
    ).cut(
        cylinder(
            GUARD_INNER_RADIUS, GUARD_DEPTH + 2, (guard_start - 1, 0, 0), (1, 0, 0)
        )
    )
    # The nominal guard joins the existing side blocks directly. No forward
    # connector boxes are needed. Its two side interruptions preserve the clamp
    # splits; an added guard must never refill these functional openings.
    parts.append(guard)
    body = union(parts)
    for side in (-1, 1):
        for tool in _carrier_clamp_cuts():
            body = body.cut(mirrored_y(tool, side))
    return _checked(body, "Motor carrier with split shaft clamps")


def rotor_geometry_contract():
    """Separate manufactured datums, supplier dimensions and display assumptions."""
    return {
        "motor_mount_face_from_tilt_axis_mm": MOTOR_MOUNT_FACE_X,
        "motor_body_length_nominal_mm": MOTOR_LENGTH,
        "motor_body_length_tolerance_mm": [0.0, MOTOR_LENGTH_UPPER_TOLERANCE],
        "motor_shaft_projection_nominal_mm": MOTOR_SHAFT_PROJECTION,
        "motor_rear_projection_derived_nominal_mm": round(MOTOR_REAR_PROJECTION, 6),
        "rear_clip_diameter_mm": None,
        "hub_thickness_nominal_mm": PROPELLER_ENVELOPE_THICKNESS,
        "actual_hub_seating_offset_mm": None,
        "actual_hub_midplane_from_tilt_axis_mm": None,
        "hub_midplane_relation_mm": "6.3 + s; s is signed hub rear-face offset from the nominal motor front face",
        "preview_seating_offset_mm": PROPELLER_PREVIEW_SEATING_OFFSET,
        "preview_hub_midplane_from_tilt_axis_mm": PROPELLER_PLANE_X,
        "preview_clearance_disk_thickness_mm": PROPELLER_ENVELOPE_THICKNESS,
        "actual_blade_axial_envelope_mm": None,
        "guard_design_midplane_from_tilt_axis_mm": GUARD_PLANE_X,
        "physical_propeller_clearance_verified": False,
        "scope": "Motor mounting face and guard plane are printed design datums. Body/shaft lengths are supplier nominal dimensions, not measurements. Preview uses s=0 and a 40 by 5 mm disk; hub thickness does not prove blade swept volume. Guard X8..10 clears the known clamp service envelopes, but coverage of the real blades is unverified. Confirm actual hub seating, rear clip, screws and complete blade sweep before releasing this motor carrier for fabrication. Nominal motion checks do not close these interfaces. Other printed parts are not made unverified by this propeller-specific uncertainty.",
    }


def _output_support(sign):
    parts = []
    for side in (-1, 1):
        y_start = (
            BEARING_GUIDE_START_Y
            if side > 0
            else -BEARING_SHOULDER_Y - BEARING_SHOULDER_THICKNESS
        )
        bottom = FOOT_BOTTOM_Z + FOOT_THICKNESS
        y = y_start + PIVOT_HALF_SPAN
        # Straight posts match the cup width without tapered roots or steps.
        post = box(
            BEARING_POST_WIDTH,
            BEARING_POST_DEPTH,
            PIVOT_Z - bottom,
            (-BEARING_POST_WIDTH / 2, y, bottom),
        )
        # Keep the bearing post and its root solid; no service tunnel is needed.
        cup = _bearing_cup(side * BEARING_START_Y, positive_side=side > 0)
        cup = translated_shape(cup, y=PIVOT_HALF_SPAN, z=PIVOT_Z)
        relief = mirrored_y(bearing_retention.post_clearance_tool(), side)
        post = post.cut(
            translated_shape(
                relief, y=PIVOT_HALF_SPAN + side * BEARING_START_Y, z=PIVOT_Z
            )
        )
        parts.extend([post, cup])
    result = union(parts)
    if sign < 0:
        result = result.mirror(V(), V(1, 0, 0))
        result = mirrored_y(result, -1)
    return result


def fixed_frame_shape():
    """One raised transverse beam joins the posts and fitted U rail spine."""
    web_opening = rail.WEB_THICKNESS
    half_span = PIVOT_HALF_SPAN + BEARING_SHOULDER_Y + BEARING_SHOULDER_THICKNESS + 0.5
    beam = box(
        FOOT_WIDTH,
        2 * half_span,
        FOOT_THICKNESS,
        (-FOOT_WIDTH / 2, -half_span, FOOT_BOTTOM_Z),
    )
    length, width = servo_bridge.CENTRAL_SEAT_LENGTH, servo_bridge.CENTRAL_SEAT_WIDTH
    spine = box(
        length, width, servo_bridge.SEAT_Z - BASE_Z, (-length / 2, -width / 2, BASE_Z)
    )
    frame = union(
        [
            spine,
            beam,
            _output_support(1),
            _output_support(-1),
        ]
    )
    frame = frame.cut(
        box(
            length + 2,
            web_opening,
            rail.MOUNT_INNER_ROOF_Z,
            (-length / 2 - 1, -web_opening / 2, 0),
        )
    )
    return _checked(
        servo_bridge.cut_shared_bolt_passage(frame),
        "Common output-bearing frame with a continuous U rail spine",
    )


def gear_shape(teeth, phase_degrees=0):
    """Nominal involute display outline; no unverified hub or tooth manufacturing."""
    if teeth not in GEARS:
        raise ValueError(f"Unsupported purchased gear: {teeth} teeth")
    pitch = GEAR_MODULE * teeth / 2
    root = GEAR_MODULE * (teeth - 2.5) / 2
    tip = GEAR_MODULE * (teeth + 2) / 2
    pressure_angle = math.radians(PRESSURE_ANGLE_DEG)
    base = pitch * math.cos(pressure_angle)
    inv_pitch = math.tan(pressure_angle) - pressure_angle

    def half_angle(radius):
        alpha = math.acos(min(1, base / max(radius, base)))
        return math.pi / (2 * teeth) + inv_pitch - (math.tan(alpha) - alpha)

    hub_start, face_start, gear_end = gear_axial_span(teeth)
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
                        face_start,
                        radius * math.sin(angle),
                    )
                )
    face = Part.Face(Part.makePolygon(points + [points[0]]))
    tooth_body = face.extrude(V(0, GEARS[teeth].face_width_mm, 0))
    hub_radius = GEARS[teeth].hub_diameter_mm / 2
    gear = union(
        [
            tooth_body,
            cylinder(hub_radius, GEARS[teeth].hub_extension_mm, (0, hub_start, 0)),
        ]
    )
    gear = gear.cut(
        cylinder(
            GEARS[teeth].bore_mm / 2,
            gear_end - hub_start + 0.2,
            (0, hub_start - 0.1, 0),
        )
    )
    # The seller specifies an M3 radial threaded hole. Set-screw length, tip and
    # inclusion are not verified; no invented screw solid is added.
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
    if sku.startswith("ALI_KAILASH"):
        thread_diameter, thread_pitch = (3.0, 0.5)
    elif sku.startswith("M1_6"):
        thread_diameter, thread_pitch = (1.6, 0.35)
    elif sku.startswith("M1_4"):
        thread_diameter, thread_pitch = (1.4, 0.3)
    else:
        thread_diameter, thread_pitch = (2.0, 0.4) if threaded else (None, None)
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
        thread_diameter=thread_diameter,
        thread_pitch=thread_pitch,
    )


def _buy_bearing(doc, parent, name, shape, notes):
    return _buy(
        doc,
        parent,
        name,
        shape,
        BEARING_SKU,
        notes,
        BEARING_SOURCE,
        "Bearing steel",
    )


def _bolt_pair(doc, parent, name, origin, direction, grip=6, servo_ear=False, length=8):
    """Seat a bought bolt and nut on the specified grip planes."""
    rotation = App.Rotation(V(0, 0, 1), V(*direction))
    bolt = (
        purchased_hardware.servo_screw_shape()
        if servo_ear
        else purchased_hardware.screw_shape(length)
    ).copy()
    bolt.Placement = App.Placement(V(*origin), rotation)
    nut = (
        purchased_hardware.servo_nut_shape()
        if servo_ear
        else purchased_hardware.hex_nut_shape()
    ).copy()
    # Servo case length is vertical; the hex nut's flats face the case ends.
    nut.Placement = App.Placement(V(*origin) + V(*direction) * grip, rotation)
    notes = (
        f"Selected M1.6x0.35 x8 Phillips kit head envelope and DIN934 hex nut;{grip:g}mm grip+1.3mm nut gives{8 - grip - 1.3:g}mm tip. A0.5mm rear hex recess restrains the nut over4.5mm of printed wall. NominalØ2 OEM hole gives0.2mm radial clearance,Ø3.5 head envelope gives0.25mm nominal case gap. Verify actual ear/seat fit."
        if servo_ear
        else f"Selected-kit M2x0.4 x{length:g} button-head bolt and hex nut; nominal{grip:g}mm grip,1.6mm nut,{length - grip - 1.6:g}mm tip projection. Head is a conservative clearance envelope pending measurement. Hand snug; actual preload and printed bearing faces unqualified."
    )
    return [
        _buy(
            doc,
            parent,
            name + "Bolt",
            bolt,
            "M1_6X8_PAN_HEAD_KIT" if servo_ear else f"M2X{length:g}_BUTTON_HEAD",
            notes,
            SERVO_SCREW_SOURCE if servo_ear else CLAMP_SCREW_SOURCE,
            SERVO_SCREW_MATERIAL if servo_ear else KIT_MATERIAL,
            threaded=True,
        ),
        _buy(
            doc,
            parent,
            name + "Nut",
            nut,
            "M1_6_HEX_NUT_DIN934" if servo_ear else NUT_SKU,
            notes,
            SERVO_NUT_SOURCE if servo_ear else HEX_NUT_SOURCE,
            SERVO_SCREW_MATERIAL if servo_ear else KIT_MATERIAL,
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
    """Production bearing-capture coupon; no horn-drilling jig is needed."""
    group = create_group(
        doc,
        "BearingFitCoupons",
        "Print first | rigid bearing seat and removable keeper",
    )
    cup = _print(
        doc,
        group,
        "BearingSeatFitSample",
        bearing_retention.coupon_shape(),
        "Production fixed bearing cup on a handling foot, used with the separate keeper. "
        "Use the same PA12 process, finish and orientation as the frame. "
        "Qualify actual outer-ring contact, no shield rubbing, endplay, free "
        "rotation and ordinary screw/keeper removal before full printing. "
        "Centre the keeper aperture on the received bearing before tightening. "
        "No spacer or press-fit retention is assumed. Raw printing does not "
        "guarantee the nominal 0.1 mm diametral or 0.5 mm axial allowance.",
        rotation=App.Rotation(V(0, 0, 1), 45),
    )
    keeper = _print(
        doc,
        group,
        "BearingKeeperFitSample",
        bearing_retention.keeper_shape(),
        "Production keeper coupon. Assemble with the cup, actual bearing and "
        "one owned M2x6/ordinary M2 nut. The recessed head clamps the lower "
        "frame seat; it must not preload the bearing. Match process/finish and "
        "orientation to the production keeper. Verify centering, shield clearance "
        "at both axial limits, free rotation and screw retention.",
        sku="BearingKeeperFitSample",
    )
    return {"group": group, "printed": [cup, keeper]}


def _build_coupling(doc, parent, prefix, sign):
    from gondola.contracts import servo_horns

    from . import oem_servo_horn
    from . import servo_coupling as coupling

    profile = servo_horns.profile(side=prefix)
    contract = coupling.assembly_contract(profile)

    def positioned(shape):
        shape = translated_shape(shape, y=coupling.HORN_BOTTOM_Y)
        if sign < 0:
            shape.rotate(V(), V(0, 0, 1), 180)
        return shape

    horn = _buy(
        doc,
        parent,
        prefix + "ServoHorn",
        positioned(coupling.horn_shape(profile)),
        profile.sku,
        profile.label
        + ". "
        + servo_horns.preparation_note(profile)
        + " Retain the appropriate X06 spline screw. Installed axial seating and root concentricity remain prototype checks.",
        profile.source,
        coupling.HORN_MATERIAL,
    )
    set_property(horn, "AxialSeatingMeasured", False, "App::PropertyBool")
    set_property(horn, "PurchasedHornMeasured", False, "App::PropertyBool")
    set_property(horn, "ManufacturerGeometryProvided", True, "App::PropertyBool")
    set_property(horn, "ManufacturerGeometrySHA256", oem_servo_horn.STEP_SHA256)
    set_property(horn, "X06CompatibilityAccepted", True, "App::PropertyBool")
    set_property(
        horn, "FactoryM1_6ThreadsConfirmed", profile.threaded, "App::PropertyBool"
    )
    set_property(horn, "HornProfile", profile.key)
    set_property(horn, "HornInterfaceContract", json.dumps(contract, sort_keys=True))
    set_property(
        horn, "HornPreparationRequired", not profile.threaded, "App::PropertyBool"
    )
    set_property(
        horn,
        "ManufacturingRoute",
        "Purchased horn; never print. " + servo_horns.preparation_note(profile),
    )
    adapter = _print(
        doc,
        parent,
        prefix + "HornGearAdapter",
        positioned(coupling.adapter_shape()),
        "One common adapter for the manufacturer X06 half arm 1 on both sides: open Ø7-root seat, near Ø1.8 round hole at X6.8, far 1.8 x 2.4 mm radial slot at X13.2 and flat front nut seats. The near hole bounds displacement along the open seat; the far slot accommodates pitch variation. No long head channel, separate cap or centring jig. Centre the shaft and check runout before tightening both rear M1.4x8/front-nut pairs; the openings do not permit operating movement. Actual axial seating, root fit, retention and runout require inspection. Export this installed solid.",
        rotation=App.Rotation(V(0, 0, 1), 180) if sign < 0 else App.Rotation(),
        sku="FactoryHoleHornGearAdapter",
    )
    set_property(
        adapter,
        "AfterPrintPreparation",
        "Deburr and finish the shaft socket/root seat as needed. "
        + servo_horns.preparation_note(profile)
        + " Align the axes before tightening both screws; inspect runout, mesh, grip and case clearance.",
    )
    printed = [adapter]
    hardware = [horn]
    for suffix, shape, sku in coupling.horn_hardware_shapes(profile):
        hardware.append(
            _buy(
                doc,
                parent,
                prefix + "HornGearClamp" + suffix,
                positioned(shape),
                sku,
                f"Nominal {contract['fastener_grip_mm']:g} mm printed grip. "
                + servo_horns.preparation_note(profile)
                + " Align before clamping; inspect useful threads, head support, length and case clearance.",
                SERVO_SCREW_SOURCE
                if suffix.endswith("Bolt")
                else servo_horns.NUT_DIMENSION_SOURCE,
                HARDWARE_MATERIALS[sku],
                threaded=True,
            )
        )
    hardware.append(
        _buy(
            doc,
            parent,
            prefix + "InputShaft",
            positioned(coupling.driver_shaft_shape()),
            f"SS304_CUT3_L{coupling.SHAFT_LENGTH:g}_FLAT{coupling.SHAFT_LENGTH:g}_A0",
            f"Cut selected Ø3 304 stock to {coupling.SHAFT_LENGTH:g} mm, deburr, and file a {coupling.SHAFT_FLAT_DEPTH:g} mm-deep full-length flat. "
            "The finished D socket keys torque; an M2 radial jack screw bears on the flat for axial retention. The M3 gear screw also bears on the flat. Nominal geometry is not a guarantee of stock diameter, straightness, concentricity or holding torque.",
            SHAFT_SOURCE,
            "304 stainless steel (seller claim)",
        )
    )
    positions = coupling.shaft_fastener_positions()
    rotation = App.Rotation(V(0, 0, 1), V(*positions["direction"]))
    for kind in ("screw", "nut"):
        shape = (
            purchased_hardware.screw_shape(positions["length"])
            if kind == "screw"
            else purchased_hardware.hex_nut_shape()
        ).copy()
        shape.Placement = App.Placement(V(*positions[kind]), rotation)
        hardware.append(
            _buy(
                doc,
                parent,
                prefix + "InputShaftClamp" + ("Bolt" if kind == "screw" else "Nut"),
                positioned(shape),
                "M2X6_BUTTON_HEAD" if kind == "screw" else NUT_SKU,
                "M2×6 radial jack screw through a captive kit hex nut, tip against the shaft flat. Head has nominal 0.5 mm clearance from the boss and does not seat on PA12. Nut bears against the 1.5 mm outer pocket wall. Tighten gently and verify retention without crushing or damaging the shaft flat; the full-length flat also keys the socket.",
                CLAMP_SCREW_SOURCE if kind == "screw" else HEX_NUT_SOURCE,
                KIT_MATERIAL,
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
    y = servo_envelope.ear_seat_y() - servo_bridge.MOUNT_DEPTH / 2
    return (
        [
            (
                f"{prefix}_bearing_post_{suffix}",
                "PropulsionFixedFrame",
                (0, sign * (PIVOT_HALF_SPAN + local_y - 0.01), 24),
                (0, sign * (PIVOT_HALF_SPAN + local_y + BEARING_POST_DEPTH + 0.01), 24),
                BEARING_POST_DEPTH,
            )
            for sign, prefix in ((1, "port"), (-1, "starboard"))
            for local_y, suffix in (
                (-BEARING_SHOULDER_Y - BEARING_SHOULDER_THICKNESS, "inner"),
                (BEARING_GUIDE_START_Y, "outer"),
            )
        ]
        + [
            (
                f"{prefix}_servo_bridge_sidewall",
                "ServoDriveBridge",
                (sign * (x + servo_bridge.CASE_WINDOW_WIDTH / 2 - 0.01), y, z),
                (sign * (x + servo_bridge.CRADLE_WIDTH / 2 + 0.01), y, z),
                servo_bridge.SIDE_WALL,
            )
            for prefix, sign in (("port", 1), ("starboard", -1))
        ]
        + [
            (
                "frame_rail_clamp_leg",
                "PropulsionFixedFrame",
                (RAIL_BOLT_OFFSET_X, servo_bridge.CHEEK_CONTACT_Y - 0.01, 3.5),
                (RAIL_BOLT_OFFSET_X, -rail.WEB_THICKNESS / 2 + 0.01, 3.5),
                -servo_bridge.CHEEK_CONTACT_Y - rail.WEB_THICKNESS / 2,
            ),
            (
                "frame_rail_relieved_roof",
                "PropulsionFixedFrame",
                (RAIL_BOLT_OFFSET_X, 0, rail.MOUNT_INNER_ROOF_Z - 0.01),
                (RAIL_BOLT_OFFSET_X, 0, servo_bridge.SEAT_Z + 0.01),
                servo_bridge.SEAT_Z - rail.MOUNT_INNER_ROOF_Z,
            ),
            (
                "frame_rail_to_central_seat_connection",
                "PropulsionFixedFrame",
                (0, -2.5, BASE_Z - 0.01),
                (0, -2.5, servo_bridge.SEAT_Z + 0.01),
                servo_bridge.SEAT_Z - BASE_Z,
            ),
            (
                "output_bearing_outer_wall",
                "PropulsionFixedFrame",
                (-6.51, PIVOT_HALF_SPAN + BEARING_START_Y + 1.5, PIVOT_Z),
                (-3.04, PIVOT_HALF_SPAN + BEARING_START_Y + 1.5, PIVOT_Z),
                3.45,
            ),
            (
                "bearing_integral_outer_shoulder",
                "PropulsionFixedFrame",
                (-2.9, PIVOT_HALF_SPAN + BEARING_SHOULDER_Y - 0.01, PIVOT_Z),
                (
                    -2.9,
                    PIVOT_HALF_SPAN
                    + BEARING_SHOULDER_Y
                    + BEARING_SHOULDER_THICKNESS
                    + 0.01,
                    PIVOT_Z,
                ),
                1.5,
            ),
            (
                "servo_common_cradle_negative_outer_wall",
                "ServoDriveBridge",
                (-x - servo_bridge.CRADLE_WIDTH / 2 - 0.01, y, z - 5),
                (-x - servo_bridge.CASE_WINDOW_WIDTH / 2 + 0.01, y, z - 5),
                servo_bridge.SIDE_WALL,
            ),
            (
                "servo_common_cradle_positive_outer_wall",
                "ServoDriveBridge",
                (x + servo_bridge.CASE_WINDOW_WIDTH / 2 - 0.01, y, z - 5),
                (x + servo_bridge.CRADLE_WIDTH / 2 + 0.01, y, z - 5),
                servo_bridge.SIDE_WALL,
            ),
            (
                "servo_common_cradle_central_web",
                "ServoDriveBridge",
                (-x + servo_bridge.CASE_WINDOW_WIDTH / 2 - 0.01, y, z - 5),
                (x - servo_bridge.CASE_WINDOW_WIDTH / 2 + 0.01, y, z - 5),
                2 * x - servo_bridge.CASE_WINDOW_WIDTH,
            ),
            (
                "servo_cradle_upper_wall",
                "ServoDriveBridge",
                (x, y, z + 8.09),
                (x, y, z + 10.21),
                2.1,
            ),
            (
                "servo_bridge_shared_cheek",
                "ServoDriveBridge",
                (22, servo_bridge.CHEEK_OUTER_Y - 0.01, 10.5),
                (22, servo_bridge.CHEEK_CONTACT_Y + 0.01, 10.5),
                servo_bridge.CHEEK_THICKNESS,
            ),
            (
                "servo_bridge_opposite_cheek",
                "ServoDriveBridge",
                (-22, 5.99, 10.5),
                (-22, 11.01, 10.5),
                5.0,
            ),
            (
                "servo_bridge_positive_nut_floor",
                "ServoDriveBridge",
                (15, 5.99, 8.2),
                (15, 8.01, 8.2),
                2.0,
            ),
            (
                "servo_bridge_negative_nut_floor",
                "ServoDriveBridge",
                (-15, -8.01, 8.2),
                (-15, -5.99, 8.2),
                2.0,
            ),
            (
                "servo_bridge_connector_plate",
                "ServoDriveBridge",
                (22, 0, servo_bridge.SEAT_Z - 0.01),
                (
                    22,
                    0,
                    servo_bridge.SEAT_Z + servo_bridge.CONNECTOR_PLATE_THICKNESS + 0.01,
                ),
                servo_bridge.CONNECTOR_PLATE_THICKNESS,
            ),
        ]
    )


def _build_frame(doc, module, spec):
    """Keep the supported output mechanism independent of the servo selection."""
    frame = _print(
        doc,
        module,
        "PropulsionFixedFrame",
        fixed_frame_shape(),
        "Integral output frame with one 46 by 12 mm U rail spine, a complete flat seat at Z12.5, and two round M3 passages at X +/-15 mm. Both 4.75 mm frame legs carry shared M3x20 clamp preload through the 2.5 mm rail web; no nut pockets or clearance guards interrupt the rail-spine legs. The removable full-U servo cap carries the recessed heads and nuts. One 18 x 5 mm transverse beam spans the frame at Z7.5..12.5, with its top aligned to the saddle seat. Four straight 13 by 6 mm posts rise from that beam and match the bearing cup width; their unsupported length to the 50 mm axes is 37.5 mm. Four bearing-keeper nut seats use0.5mm-deep hex recesses with2mm supporting floors. No separate ribs or fasteners. This is a nominal fitted stack, not a spring clamp: coupon-fit all contact planes to hand-seat before tightening; finish or reprint an unsuitable fit instead of pulling gaps or warp closed. The 46 mm footprint locally restrains rail curvature. Support both modules during release. Bearing/shaft interfaces, 150 mm span and 50 mm height are retained; strength, fit, creep and retention remain unqualified.",
        App.Rotation(V(0, 0, 1), 45),
        sku=spec.frame_sku,
    )
    set_property(frame, "IntegratedRailSaddle", True, "App::PropertyBool")
    set_property(frame, "CarriageContactZ", rail.MOUNT_BOTTOM_Z, "App::PropertyLength")
    set_property(frame, "RailCenterY", 0, "App::PropertyLength")
    set_property(frame, "FootThickness", FOOT_THICKNESS, "App::PropertyLength")
    set_property(frame, "FootBottomZ", FOOT_BOTTOM_Z, "App::PropertyLength")
    set_property(frame, "BearingPostWidth", BEARING_POST_WIDTH, "App::PropertyLength")
    set_property(
        frame,
        "FrameCrossbeamThickness",
        FOOT_THICKNESS,
        "App::PropertyLength",
    )
    set_property(
        frame,
        "RailBoltOffsetX",
        RAIL_BOLT_OFFSET_X,
        "App::PropertyLength",
    )
    set_property(frame, "RailContactLength", RAIL_CONTACT_LENGTH, "App::PropertyLength")
    set_property(frame, "RailBoltAxisZ", rail.BOLT_AXIS_Z, "App::PropertyLength")
    set_property(
        frame,
        "CentralBridgeSeatZ",
        servo_bridge.CONNECTOR_PLATE_BOTTOM_Z,
        "App::PropertyLength",
    )
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
        "Integral nominal guard,3mm motor plate/crossbar and two rectangular19x10x8mm shaft-clamp sides. Motor mounting face is X=-5mm. The guard joins these blocks directly, with two small side interruptions preserving the clamp splits; all clamp openings are cut after union. No forward connector blocks. Flat end faces replace the separate circular stop flanges; the 3.2mm bores, radial splits and bearing planes are unchanged. Each M2 nut sits in a1.5mm-deep hex recess in the flat top, with2.1mm stock between its seat and the split. Existing M2x8 screws retain their5mm grip. Guard plane is X=9mm, clearing the existing clamp head/nut service envelopes; the illustrative propeller disk is centred at X=6.3mm for the explicitly assumed s=0 hub seating. Actual seating and blade swept volume are unknown; nominal clearance does not qualify this carrier for fabrication. The two bearing centres are 70 mm apart, and the gear face centre is 11 mm from the inner bearing centre. Two separate Ø3 shafts stop before the motor. M2x8 clamps provide frictional torque and axial grip; strength, creep and slip require tests. Nominal 0.5 mm carrier/frame end clearance provides low-load rubbing stops. Rigid keepers capture each bearing independently of the shaft and carrier. Install bearings and centre/secure their keepers, retract output shafts 12 mm, insert the carrier transversely, then advance and clamp shafts. The broad carrier/frame stops limit rotor travel to nominal ±0.5 mm without pressing a bearing shield. Three 1.8 mm open radial motor slots follow M1.4/PCD6.6. Actual OEM screw length, usable depth, head footprint, rear-clip clearance and finished axial fits remain unverified.",
        App.Rotation(V(0, 1, 0), -90),
        sku="GearedMotorCarrier",
    )
    set_property(
        carrier, "MotorPlateThickness", MOTOR_PLATE_THICKNESS, "App::PropertyLength"
    )
    set_property(
        carrier, "MotorMountFaceX", MOTOR_MOUNT_FACE_X, "App::PropertyDistance"
    )
    set_property(
        carrier, "TiltAxisToPropellerPlane", PROPELLER_PLANE_X, "App::PropertyLength"
    )
    set_property(
        carrier, "RotorGeometryContract", json.dumps(rotor_geometry_contract())
    )
    set_property(
        carrier, "PhysicalPropellerClearanceVerified", False, "App::PropertyBool"
    )
    printed.append(carrier)
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        driven = side == -sign
        length = OUTPUT_DRIVEN_SHAFT_LENGTH if driven else OUTPUT_IDLE_SHAFT_LENGTH
        low, high = OUTPUT_SHAFT_INNER_Y, OUTPUT_SHAFT_INNER_Y + length
        shaft = cylinder(1.5, high - low, (0, low, 0))
        if driven:
            shaft = shaft.cut(
                box(
                    2,
                    OUTPUT_SHAFT_FLAT_LENGTH,
                    4,
                    (1, high - OUTPUT_SHAFT_FLAT_LENGTH, -2),
                )
            )
        shaft = mirrored_y(shaft, side)
        sku = (
            f"SS304_CUT3_L{length:g}_FLAT{OUTPUT_SHAFT_FLAT_LENGTH:g}_A0"
            if driven
            else f"SS304_CUT3_L{length:g}"
        )
        hardware.append(
            _buy(
                doc,
                pod,
                prefix + "OutputShaft" + suffix,
                shaft,
                sku,
                "Cut the selected nominal Ø3 mm 304 rod to length and deburr. Use two 34 mm driven stubs and two 20 mm idlers; separate stubs leave the motor bay clear. Driven stub has a locally prepared 0.5 mm deep flat on the final 5 mm at the gear end, entirely outside the bearing journal. Its tip projects 0.5 mm beyond the inner gear-hub face. Clock the flat toward the M3 screw after tooth phasing. The symmetric supports retain the 150 mm motor-axis spacing with 11 mm gear overhang and space on both sides of the rotor; check loaded mesh alignment, bearing/post and carrier/clamp compliance before running. Diameter tolerance, straightness, clamp slip and actual fit remain sample checks; replace with a matching nominal Ø3 precision shaft if needed.",
                SHAFT_SOURCE,
                "304 stainless steel (seller claim)",
            )
        )
        hardware.extend(
            _bolt_pair(
                doc,
                pod,
                prefix + "OutputClamp" + suffix,
                (4.2, side * CARRIER_CLAMP_BOLT_Y, -2.5),
                (0, 0, 1),
                grip=5,
            )
        )
        # All bearing geometry is fixed; each shaft rotates with the pod.
        bearing_start = sign * PIVOT_HALF_SPAN + min(
            side * BEARING_START_Y, side * BEARING_SHOULDER_Y
        )
        bearing = _buy_bearing(
            doc,
            assembly,
            prefix + "OutputBearing" + suffix,
            translated_shape(bearing_shape(), y=bearing_start, z=PIVOT_Z),
            "Selected generic 3×6×2.5 bearing, annular clearance envelope; brand, internal axial play, race lands, shields and fits need inspection. The integral outer shoulder and rigid removable keeper act only on the outer-ring region. Nominal inward float is 0.5 mm; the continuous fixed guide supports the complete 2.5 mm bearing width at either limit. Finish the seat and qualify actual outer-ring land, shield opening, keeper alignment/retention and internal play; no shield contact or preload is intended. Purchase is user-confirmed; these nominal boundary dimensions do not establish delivered tolerances.",
        )
        hardware.append(bearing)
        keeper_name = prefix + "OutputBearingKeeper" + suffix
        keeper = _print(
            doc,
            assembly,
            keeper_name,
            translated_shape(
                mirrored_y(bearing_retention.keeper_shape(), side),
                y=sign * PIVOT_HALF_SPAN + side * BEARING_START_Y,
                z=PIVOT_Z,
            ),
            "Rigid replaceable outer-ring keeper with a symmetric3.5mm backing extending to5mm below the axis; one recessed M2x6 and ordinary "
            "M2 nut clamp the broad frame seat, not the bearing. A0.5mm-deep hex nut recess in the fixed seat leaves2mm supporting stock without shifting the bearing plane. The existing "
            "rotor stop plane is retained. No flexure, radial squeeze or bearing "
            "preload. Centre its opening on the received bearing before tightening; "
            "the broad side guides prevent gross rotation, not precision alignment. "
            "Check actual ring lands, shield clearance and free rotation at both "
            "axial limits. Remove carrier/shafts before screw, keeper and bearing service.",
            rotation=App.Rotation(V(0, 0, 1), 180) if side < 0 else App.Rotation(),
            sku="OutputBearingKeeper",
        )
        printed.append(keeper)
        hardware.extend(
            _bolt_pair(
                doc,
                assembly,
                keeper_name,
                (
                    0,
                    sign * PIVOT_HALF_SPAN
                    + side * (BEARING_START_Y + bearing_retention.KEEPER_SCREW_SEAT_Y),
                    PIVOT_Z + bearing_retention.KEEPER_SCREW_Z,
                ),
                (0, side, 0),
                grip=bearing_retention.KEEPER_NUT_SEAT_Y
                - bearing_retention.KEEPER_SCREW_SEAT_Y,
                length=bearing_retention.KEEPER_SCREW_LENGTH,
            )
        )

    driver_angle = math.degrees(
        math.atan2(PIVOT_Z - spec.input_z_mm, -sign * spec.input_x_mm)
    )
    output_angle = driver_angle + 180 + 180 / spec.output.teeth
    output_gear = gear_shape(spec.output.teeth, output_angle)
    output_gear = mirrored_y(output_gear, sign)
    output_gear = translated_shape(output_gear, y=-sign * PIVOT_HALF_SPAN)
    hardware.append(
        _buy(
            doc,
            pod,
            prefix + "OutputGear",
            output_gear,
            spec.output.sku,
            "Selected seller 16T m0.5/20° gear, nominal Ø3 bore, 5 mm face, 10 mm overall and Ø6.5 hub. M3 screw axis is 2.5 mm from the hub end. Copper-alloy identity, bore tolerance, screw length and actual torque remain unverified. Tooth shape is a nominal reference, not manufacturing data.",
            spec.output.item_url,
            "Copper alloy (seller claim)",
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
        f"Selected seller {spec.driver.teeth}T m0.5/20° gear, nominal Ø3 H8 bore, face 3, overall 8, hub Ø12. Stock X06 horn, open clamping adapter and a short Ø3 metal stub transmit torque; no additional input bearing. M3 screw position/length, actual material (aluminium description conflicts with steel attribute), mass and loaded grip remain unverified. Output turns oppositely at {spec.ratio:g} times input. Nominal tooth reference only.",
        spec.driver.item_url,
        "Aluminium alloy (seller claim; steel attribute conflicts)",
    )
    return drive, [gear]


def _build_servo(doc, mount, prefix, sign, spec):
    """Mount the sourced vertical X06 case on its replaceable bridge cradle."""
    hardware = []
    servo = mirrored_y(servo_envelope.shape(), sign)
    for hole_z, suffix in zip(servo_envelope.EAR_CENTRES_Z, ("Lower", "Upper")):
        hardware.extend(
            _bolt_pair(
                doc,
                mount,
                prefix + "ServoEar" + suffix,
                (0, sign * servo_envelope.ear_head_y(), hole_z),
                (0, -sign, 0),
                grip=servo_bridge.EAR_NUT_GRIP,
                servo_ear=True,
            )
        )
    servo_ref = _reference(
        doc,
        mount,
        prefix + "Servo",
        "KST X06 V6.0 vertical case 20×7×16.6; 6 g",
        servo,
        "Official case envelope, rotated 90 degrees about the output axis so the body extends downward. Output axis is 5 mm from the case end; sourced ear axes are Ø2 on 24 mm pitch. "
        f"Both servos share one {servo_bridge.MOUNT_DEPTH:g} mm-deep wall with {servo_bridge.SIDE_WALL:g} mm outer sides "
        f"and a {2 * spec.input_x_mm - servo_bridge.CASE_WINDOW_WIDTH:g} mm central web. "
        f"Each nonlocating {servo_bridge.CASE_WINDOW_WIDTH:g} by {servo_bridge.CASE_WINDOW_HEIGHT:g} mm case opening "
        f"has nominal {servo_bridge.CASE_CLEARANCE:g} mm side and end clearance around the body. "
        "M1.6×8 Phillips kit screws clamp4.5mm printed grip plus1mm ears;0.5mm rear hex recesses restrain ordinary M1.6 nuts. Ear transverse outline remains a conservative 7 mm envelope. Smooth Ø3.90×2.7 spline envelope does not claim tooth detail. Actual case fit, horn seating, OEM retaining screw, wiring exit and loaded travel require physical confirmation. Direct gearing transfers mesh load to the servo output bearings; allowable radial load is unpublished.",
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
        "First remove both output gears and the paired servo/input module. On the "
        "bench remove the selected driver gear and input stub, turn and withdraw "
        "the ear screws while their rear nuts remain in the shallow pockets, "
        "then remove the nuts and withdraw the servo/horn/adapter unit. "
        "Reverse for assembly; verify head-tool access and full nut seating.",
    )
    drive, hardware = _build_input_drive(doc, mount, prefix, sign, driver_angle, spec)
    references, servo_hardware = _build_servo(doc, mount, prefix, sign, spec)
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
        "RS1102 nominal body | mounting face -5 mm",
        cylinder(
            MOTOR_DIAMETER / 2, MOTOR_LENGTH, (MOTOR_MOUNT_FACE_X, 0, 0), (1, 0, 0)
        ),
        "Supplier body length8.8(+0.1/-0)mm from mounting face;14mm is overall length including shaft and rear protrusion. Display uses nominal axial length and maximum published13.6mm diameter. ThreeM1.4 axes onPCD6.6 use open1.8mm radial slots through the3mm plate. Rear protrusion1.2mm is derived nominally; its clip diameter, screw length/depth and seating remain unverified. No tilt through-shaft is allowed.",
        MOTOR_SOURCE,
    )
    set_property(motor, "Diameter", MOTOR_DIAMETER, "App::PropertyLength")
    set_property(
        motor, "NominalDiameter", MOTOR_NOMINAL_DIAMETER, "App::PropertyLength"
    )
    set_property(motor, "EnvelopeLength", MOTOR_LENGTH, "App::PropertyLength")
    set_property(
        motor,
        "BodyLengthUpperTolerance",
        MOTOR_LENGTH_UPPER_TOLERANCE,
        "App::PropertyLength",
    )
    set_property(motor, "RotorGeometryContract", json.dumps(rotor_geometry_contract()))
    set_property(motor, "CatalogMassGrams", 2.8, "App::PropertyFloat")
    references.append(motor)
    references.append(
        _reference(
            doc,
            pod,
            prefix + "Shaft",
            "RS1102 shaft envelope",
            cylinder(0.75, MOTOR_SHAFT_PROJECTION, (MOTOR_FRONT_X, 0, 0), (1, 0, 0)),
            "PublishedØ1.5mm shaft,4mm nominal projection from the motor front face. Motor body's+0.1mm length tolerance also shifts the front and shaft axially. Displayed shaft is nominal; rear clip shape is unresolved.",
            MOTOR_SOURCE,
        )
    )
    propeller = _reference(
        doc,
        pod,
        prefix + "PropellerDisk",
        "Gemfan1610 illustrative clearance disk | seating unverified",
        cylinder(
            20,
            PROPELLER_ENVELOPE_THICKNESS,
            (PROPELLER_PLANE_X - PROPELLER_ENVELOPE_THICKNESS / 2, 0, 0),
            (1, 0, 0),
        ),
        "Illustrative s=0 seating: hub midpoint6.3mm from tilt axis. Published40mm diameter and5mm hub thickness applied to a full clearance disk; this is not verified blade geometry or actual seating. Do not treat its centroid as physical mass/aerodynamic centre. See RotorGeometryContract; nominal clearance does not release this motor carrier for fabrication.",
        PROP_SOURCE,
    )
    set_property(propeller, "PropDiameter", 40, "App::PropertyLength")
    set_property(
        propeller, "HubThickness", PROPELLER_ENVELOPE_THICKNESS, "App::PropertyLength"
    )
    set_property(
        propeller, "TiltAxisToCentrePlane", PROPELLER_PLANE_X, "App::PropertyLength"
    )
    set_property(
        propeller, "RotorGeometryContract", json.dumps(rotor_geometry_contract())
    )
    set_property(propeller, "PhysicalSeatingVerified", False, "App::PropertyBool")
    set_property(propeller, "Variant", "CW" if sign > 0 else "CCW")
    references.append(propeller)
    return references


def _build_sweep_reserve(doc, assembly, prefix, sign):
    """Create the separate clearance reference for external vehicle equipment."""
    bound = union(
        [
            cylinder(30, 2 * CARRIER_END_Y, (0, -CARRIER_END_Y, 0)),
            cylinder(
                FUTURE_ROTOR_ORBIT_RADIUS,
                2 * FUTURE_ROTOR_HALF_WIDTH + 1,
                (0, -FUTURE_ROTOR_HALF_WIDTH - 0.5, 0),
            ),
            cylinder(
                10,
                2 * OUTPUT_SHAFT_SWEEP_HALF_LENGTH,
                (0, -OUTPUT_SHAFT_SWEEP_HALF_LENGTH, 0),
            ),
        ]
    )
    bound = translated_shape(bound, y=sign * PIVOT_HALF_SPAN, z=PIVOT_Z)
    return _reference(
        doc,
        assembly,
        prefix + "SweepBound",
        "Conservative complete output rotation reserve",
        bound,
        f"Current motor/guard/carrier radius30 overY±{CARRIER_END_Y:g}, output clamps/bolts/shafts/gears radius10 overY±{OUTPUT_SHAFT_SWEEP_HALF_LENGTH:g}. Also reserves a replacement-rotor full-turn cylinder radius34 overY±30.5, including nominal ±0.5 axial travel. This allows space to design a future 50 mm propeller rotor, not compatibility of the present 40 mm guard or struts. Excludes the separately validated gear mesh and input mechanism; full bound is used against external vehicle equipment.",
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
    from .nut_guides import fit_contract as nut_guide_contract
    from .servo_coupling import metrics as coupling_metrics

    return {
        "revision": DESIGN_REVISION,
        "module_count": 1,
        "main_pod_count": 2,
        "tilt_range_deg": [-180, 180],
        "independent_native_tilt": True,
        "single_rail_center_y_mm": 0,
        "integrated_rail_saddle": True,
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
            "driver_face_width_mm": spec.driver.face_width_mm,
            "output_face_width_mm": spec.output.face_width_mm,
            "nominal_full_face_overlap_mm": min(
                spec.driver.face_width_mm, spec.output.face_width_mm
            ),
            "driver_axial_span_mm": list(gear_axial_span(spec.driver.teeth)),
            "output_axial_span_mm": list(gear_axial_span(spec.output.teeth)),
            "input_axis_abs_x_mm": spec.input_x_mm,
            "input_axis_z_mm": spec.input_z_mm,
            "output_to_input_angle_ratio": -spec.ratio,
            "fixed_frame_print_sku": spec.frame_sku,
            "servo_bridge_print_sku": spec.bridge_sku,
            "input_mount": "Prepared stock-horn drives on a removable continuous U cap with a 46 by 12 mm frame seat and two shared M3x20 clamps at 30 mm pitch. Both cap walls and both frame legs carry preload; coupon-fit the nominal mating planes before tightening. Support both modules and release both rail pairs before bench service; remove small gears and stage the two driven shafts by 12 mm before lifting the saddle. Only selected 48T/16T is supported; another drive requires replacement geometry and validation.",
            "supported_configurations": list(DRIVE_CONFIGURATIONS),
            "limits": "Bounded motion only. Servo travel, tooth clearance, backlash, clamp slip and wire loops require physical calibration.",
        },
        "shaft_topology": {
            "output_stub_count": 4,
            "output_driven_length_mm": OUTPUT_DRIVEN_SHAFT_LENGTH,
            "output_idle_length_mm": OUTPUT_IDLE_SHAFT_LENGTH,
            "carrier_grip_length_mm": CARRIER_CLAMP_LENGTH,
            "assembly_retraction_mm": SHAFT_ASSEMBLY_RETRACTION,
            "staged_final_withdrawal_mm": SHAFT_FINAL_WITHDRAWAL,
            "input_count": 2,
            "input_length_mm": servo_coupling.SHAFT_LENGTH,
            "through_shaft_allowed": False,
            "reason": "A through-shaft crosses the motor. Separate stubs leave the motor bay clear.",
        },
        "bearing_seats": {
            "support_centre_span_mm": 2
            * (BEARING_START_Y + bearing_retention.BEARING_WIDTH / 2),
            "post_section_mm": [BEARING_POST_WIDTH, BEARING_POST_DEPTH],
            "gear_face_centre_overhang_mm": (
                PIVOT_HALF_SPAN
                - BEARING_START_Y
                - bearing_retention.BEARING_WIDTH / 2
                - sum(gear_axial_span(spec.output.teeth)[1:]) / 2
            ),
            "count": 4,
            "dimensions_mm": [3, 6, 2.5],
            "nominal_bore_mm": 2 * bearing_retention.SEAT_RADIUS,
            "outer_shoulder_opening_mm": BEARING_WINDOW_DIAMETER,
            "outer_shoulder_thickness_mm": BEARING_SHOULDER_THICKNESS,
            "rigid_guide_length_mm": bearing_retention.BEARING_WIDTH
            - bearing_retention.KEEPER_STOP_Y,
            "retention": "Integral outer shoulder and one rigid removable keeper per bearing, fixed by a recessed M2x6/ordinary M2 nut against the frame. No bought spacers, radial clamp or spring arms.",
            "nominal_maximum_bearing_inward_float_mm": -bearing_retention.KEEPER_STOP_Y,
            "complete_circumferential_guide_width_mm": bearing_retention.BEARING_WIDTH
            - bearing_retention.KEEPER_STOP_Y,
            "minimum_complete_guide_overlap_mm": bearing_retention.BEARING_WIDTH,
            "keeper_screw_length_mm": bearing_retention.KEEPER_SCREW_LENGTH,
            "finishing": "Print the production cup and keeper coupons first. Finish and measure the seat, centre the keeper aperture on the actual bearing, then check both axial limits for shield clearance/free rotation and retention. Broad guide clearance is not automatic precision centring. The 0.1 mm diametral allowance does not absorb general PA12 variation. Never force the bearing or use keeper torque to remove radial play.",
            "running_axial_clearance_mm": 0.5,
            "assembly": "Insert bearings from the empty carrier bay, centre the keepers and secure each M2x6/nut against the frame seat. Remove the output gear, loosen carrier clamps and retract output shafts 12 mm. Insert the carrier transversely, then advance shafts and clamp. Bearing service requires removal of the carrier/shafts, then the keeper screw/nut and keeper. The paired servo module stays installed.",
        },
        "replacement_rotor_space": {
            "future_propeller_reference_diameter_mm": FUTURE_ROTOR_PROPELLER_DIAMETER,
            "bulk_half_width_mm": FUTURE_ROTOR_HALF_WIDTH,
            "full_rotation_radius_mm": FUTURE_ROTOR_ORBIT_RADIUS,
            "included_axial_travel_each_way_mm": 0.5,
            "scope": "Space allowance for a redesigned replacement rotor only. Its bulk must fit |Y|<=30 mm and radius34 about the tilt axis through every angle; retain the separate shaft/clamp stop interfaces. The current nominal 40 mm guard does not accept a 50 mm propeller. Future guard, motor, hub, fastening, wiring, thrust, balance and load capacity require selection and revalidation. Existing two-bearing support and 150 by 50 mm main-axis datums remain unchanged.",
        },
        "process_design_reference": {
            "source": CREALLO_SOURCE,
            "process": "PA12 SLS/MJF",
            "minimum_feature_wall_mm": 1.5,
            "guard_radial_wall_mm": GUARD_OUTER_RADIUS - GUARD_INNER_RADIUS,
            "frame_foot_thickness_mm": FOOT_THICKNESS,
            "frame_foot_z_range_mm": [FOOT_BOTTOM_Z, FOOT_BOTTOM_Z + FOOT_THICKNESS],
            "frame_crossbeam_thickness_mm": FOOT_THICKNESS,
        },
        "OEM_interfaces": PROPULSION_EVIDENCE,
        "horn_coupling": coupling_metrics(),
        "nut_assembly_guides": nut_guide_contract(),
        "carrier_nut_pockets": {
            "depth_mm": CARRIER_NUT_RECESS_DEPTH,
            "across_flats_mm": CARRIER_NUT_POCKET_AF,
            "seat_to_split_wall_mm": 2.1,
            "axis_float_radius_mm": 0.1,
            "nut_axially_captive": False,
            "physical_fit_verified": False,
            "scope": "Ordinary M2 nuts; flat19x10x8mm clamp block. Qualify nut chamfers, free seating, torque restraint and split-clamp grip with the production print and actual hardware.",
        },
        "rotor_geometry": rotor_geometry_contract(),
        "motor_plate_thickness_mm": MOTOR_PLATE_THICKNESS,
        "motor_mount_face_x_mm": MOTOR_MOUNT_FACE_X,
        "motor_envelope_centre_x_mm": MOTOR_MOUNT_FACE_X + MOTOR_LENGTH / 2,
        "unfinished_interfaces": [
            "Measured OEM horn seating and retaining screw",
            "Actual direct horn-to-gear adapter clearance and grip",
            "Servo output-bearing deflection under direct gear mesh load",
            "Printed bridge seating, cradle fit and retained gear center distance",
            "Motor rear clip, seat and M1.4 usable depth",
            "Actual propeller seating and full blade swept volume; current guard is a provisional s=0 design",
            "Printed bearing fits, actual outer-ring lands, shield clearance and releasable outer-ring capture",
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
        "Removable paired servos on a continuous U cap with a flat 46 by 22 by 2.5 mm roof at Z12.5 and two 5 mm walls wrapping the frame. Two straight openings at X +/-9.2 extend to the roof underside at Z12.5 for the raised 18 mm beam. The beam adds 180 mm2 of roof bearing outside the central spine; both full clamp legs remain at X +/-15. Two shared M3x20 pairs at X +/-15 load both cap walls, both frame legs and the rail web. Head recesses retain 3 mm stock; opposite nut pockets retain nominal 2 mm floors. Both outer recesses open downward; inner round shank bores retain their bearing faces. Nut flats are vertical. Nominal fitted planes must hand-seat after coupon qualification; never tighten an unseated or warped joint into place. Servos, horn interfaces and their datums are unchanged. For bench service disconnect leads, support both modules and remove both rail pairs; slide the unit +X10 then lift Z30. Remove the small output gears, release the two driven-shaft clamps, shift PortOutputShaftNegative +Y12 and StarboardOutputShaftPositive -Y12 while supporting the rotors, then lift the servo assembly Z11 and withdraw X80. Restore shafts, clamps, gear retention and mesh alignment before operation.",
        sku=drive.bridge_sku,
    )
    parts = {
        "printed": [frame, bridge],
        "hardware": [],
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
