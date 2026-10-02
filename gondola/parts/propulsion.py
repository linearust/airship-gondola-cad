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
    DRIVE_INWARD_OFFSET_MM,
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
from gondola.contracts.rail_attachments import PROPULSION_ATTACHMENT

from . import (
    bearing_retention,
    purchased_hardware,
    rail,
    servo_bridge,
    servo_coupling,
    servo_envelope,
)

V = App.Vector
FOOT_THICKNESS = 5.0
FOOT_BOTTOM_Z = 24.5
FOOT_WIDTH = 18.0
BEARING_POST_WIDTH = 18.0
BEARING_ROOT_RADIUS = 1.5
RAIL_BOLT_OFFSET_X = PROPULSION_ATTACHMENT.half_spacing_mm
RAIL_CONTACT_LENGTH = PROPULSION_ATTACHMENT.contact_length_mm
PIVOT_Z = PIVOT_Z_MM
PIVOT_HALF_SPAN = PIVOT_SPAN_MM / 2
GUARD_OUTER_RADIUS = 26.0
GUARD_INNER_RADIUS = 23.0
# Space for a later replacement rotor, not a fitted 50 mm propeller option.
# The current nominal guard remains specific to the 40 mm prop.
FUTURE_ROTOR_PROPELLER_DIAMETER = 50.0
FUTURE_ROTOR_HALF_WIDTH = 29.0
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
GUARD_DEPTH = 3.0
# Keep the rear face at X8 and the front flush with the root at X11. The 3x3
# ring and 12mm-high front fan add stock without closing the jack-nut exit.
# Physical blade coverage still needs verified seating and blade geometry.
GUARD_PLANE_X = 9.5
GUARD_ROOT_FAN_HEIGHT = 12.0
GUARD_RETURN_HEIGHT = 8.0
GUARD_RETURN_ROOT_RADIUS = 1.0
CARRIER_SIDE_THICKNESS = 8.0
CARRIER_SIDE_FRONT_X = 11.0
CARRIER_SIDE_LENGTH = CARRIER_SIDE_FRONT_X - MOTOR_PLATE_BACK_X
MOTOR_SOURCE = "https://www.happymodel.cn/index.php/2025/01/08/happymodel-rs1102-kv10000-kv13500-brushless-motor-for-micro-fpv-drone/"
PROP_SOURCE = "https://www.gemfanhobby.com/40mm-1610-pc-2-blade.html"
CREALLO_SOURCE = "https://creallo.com/ko/guide/design-spec-guide"
GEAR_MODULE = MODULE_MM
GEAR_HUB_START_Y = (
    servo_coupling.HORN_BOTTOM_Y + servo_coupling.GEAR_START_Y - DRIVE_INWARD_OFFSET_MM
)
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


BEARING_CENTRES_ABS_Y = (28.0, 41.0)
BEARING_START_Y = BEARING_CENTRES_ABS_Y[0] - bearing_retention.BEARING_WIDTH / 2
BEARING_WINDOW_DIAMETER = bearing_retention.SHIELD_OPENING_DIAMETER
BEARING_GUIDE_START_Y = BEARING_CENTRES_ABS_Y[0] + bearing_retention.BODY_FRONT_Y
BEARING_SHOULDER_Y = BEARING_CENTRES_ABS_Y[-1] + bearing_retention.SEAT_WIDTH / 2
BEARING_SHOULDER_THICKNESS = bearing_retention.SHOULDER_THICKNESS
BEARING_POST_DEPTH = bearing_retention.BODY_REAR_Y - bearing_retention.BODY_FRONT_Y
CARRIER_END_Y = 30.5
CARRIER_CLAMP_START_Y = 20.5
CARRIER_CLAMP_LENGTH = CARRIER_END_Y - CARRIER_CLAMP_START_Y
CARRIER_CLAMP_BOLT_Y = (CARRIER_CLAMP_START_Y + CARRIER_END_Y) / 2
CARRIER_NUT_POCKET_AF = 4.25
OUTPUT_SHAFT_INNER_Y = 20.0
OUTPUT_DRIVEN_SHAFT_LENGTH = 42.0
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


CARRIER_JACK_HEAD_X = 13.0
CARRIER_JACK_NUT_SEAT_X = 8.0
CARRIER_JACK_LENGTH = 12.0
CARRIER_SHAFT_FLAT_X = 1.0
CARRIER_SOCKET_FLAT_CLEARANCE = 0.05
OUTPUT_CARRIER_FLAT_LENGTH = 11.0


def _carrier_clamp_cuts():
    """Positive-Y keyed socket and top-entry ordinary-nut jack screw."""
    start = OUTPUT_SHAFT_INNER_Y - 0.1
    length = CARRIER_END_Y + 0.25 - start
    bore = cylinder(1.5, length, (0, start, 0)).cut(
        box(
            3,
            length + 0.2,
            4,
            (CARRIER_SHAFT_FLAT_X + CARRIER_SOCKET_FLAT_CLEARANCE, start - 0.1, -2),
        )
    )
    pocket = purchased_hardware.hex_prism(CARRIER_NUT_POCKET_AF, 1.8)
    pocket.Placement = App.Placement(
        V(6.2, CARRIER_CLAMP_BOLT_Y, 0), App.Rotation(V(0, 0, 1), V(1, 0, 0))
    )
    return (
        bore,
        pocket,
        box(
            1.8,
            CARRIER_NUT_POCKET_AF,
            4.1,
            (6.2, CARRIER_CLAMP_BOLT_Y - CARRIER_NUT_POCKET_AF / 2, 0),
        ),
        cylinder(1.1, 12.2, (0.9, CARRIER_CLAMP_BOLT_Y, 0), (1, 0, 0)),
    )


def _carrier_side_blank():
    return box(
        CARRIER_SIDE_LENGTH,
        CARRIER_CLAMP_LENGTH,
        CARRIER_SIDE_THICKNESS,
        (MOTOR_PLATE_BACK_X, CARRIER_CLAMP_START_Y, -CARRIER_SIDE_THICKNESS / 2),
    )


def _carrier_side_shape():
    body = _carrier_side_blank()
    for tool in _carrier_clamp_cuts():
        body = body.cut(tool)
    return _checked(body, "Keyed carrier root and radial jack")


def moving_carrier_shape(sign=1):
    """Inboard keyed rotor with a rear bridge and far-side guard return arm."""
    rear = union(
        [
            cylinder(8.2, MOTOR_PLATE_THICKNESS, (MOTOR_PLATE_BACK_X, 0, 0), (1, 0, 0)),
            box(
                MOTOR_PLATE_THICKNESS,
                CARRIER_END_Y + GUARD_OUTER_RADIUS,
                CARRIER_SIDE_THICKNESS,
                (MOTOR_PLATE_BACK_X, -CARRIER_END_Y, -CARRIER_SIDE_THICKNESS / 2),
            ),
        ]
    )
    passage_x = MOTOR_PLATE_BACK_X - 0.5
    rear = rear.cut(
        cylinder(2.2, MOTOR_PLATE_THICKNESS + 1, (passage_x, 0, 0), (1, 0, 0))
    )
    for angle in (0, 120, 240):
        slot = union(
            [
                box(MOTOR_PLATE_THICKNESS + 1, 3.3, 1.8, (passage_x, 0, -0.9)),
                cylinder(
                    0.9, MOTOR_PLATE_THICKNESS + 1, (passage_x, 3.3, 0), (1, 0, 0)
                ),
            ]
        )
        slot.rotate(V(), V(1, 0, 0), angle)
        rear = rear.cut(slot)
    web = Part.Face(
        Part.makePolygon(
            [
                V(-5, -CARRIER_CLAMP_START_Y, -4),
                V(3, -CARRIER_CLAMP_START_Y, -4),
                V(-5, -8.2, -4),
                V(-5, -CARRIER_CLAMP_START_Y, -4),
            ]
        )
    ).extrude(V(0, 0, 8))
    guard_start = GUARD_PLANE_X - GUARD_DEPTH / 2
    guard = cylinder(
        GUARD_OUTER_RADIUS, GUARD_DEPTH, (guard_start, 0, 0), (1, 0, 0)
    ).cut(
        cylinder(
            GUARD_INNER_RADIUS, GUARD_DEPTH + 2, (guard_start - 1, 0, 0), (1, 0, 0)
        )
    )
    fan = box(
        GUARD_DEPTH,
        CARRIER_CLAMP_LENGTH,
        GUARD_ROOT_FAN_HEIGHT,
        (guard_start, -CARRIER_END_Y, -GUARD_ROOT_FAN_HEIGHT / 2),
    ).cut(
        cylinder(
            GUARD_INNER_RADIUS, GUARD_DEPTH + 2, (guard_start - 1, 0, 0), (1, 0, 0)
        )
    )
    outer_return = box(
        CARRIER_SIDE_LENGTH,
        GUARD_OUTER_RADIUS - GUARD_INNER_RADIUS,
        GUARD_RETURN_HEIGHT,
        (MOTOR_PLATE_BACK_X, GUARD_INNER_RADIUS, -GUARD_RETURN_HEIGHT / 2),
    )
    body = union(
        [rear, mirrored_y(_carrier_side_blank(), -1), web, guard, fan, outer_return]
    )
    for tool in _carrier_clamp_cuts():
        body = body.cut(mirrored_y(tool, -1))
    from .edge_blends import fillet_selected, near

    body = body.removeSplitter()
    body = fillet_selected(
        body,
        1.0,
        lambda e, b: (
            near(b.XMin, 3)
            and near(b.XLength, 0)
            and near(b.YMin, -CARRIER_CLAMP_START_Y)
            and near(b.YLength, 0)
            and near(b.ZLength, 8)
        ),
        1,
        "Carrier triangular root",
    )
    body = fillet_selected(
        body,
        GUARD_RETURN_ROOT_RADIUS,
        lambda e, b: (
            near(b.XMin, MOTOR_MOUNT_FACE_X)
            and near(b.XLength, 0)
            and near(b.YMin, GUARD_INNER_RADIUS)
            and near(b.YLength, 0)
            and near(b.ZLength, GUARD_RETURN_HEIGHT)
        ),
        1,
        "Guard outer return rear root",
    )
    for x, label in ((MOTOR_PLATE_BACK_X, "rear web"),):
        body = fillet_selected(
            body,
            0.5,
            lambda e, b: (
                near(b.XMin, x)
                and near(b.XLength, 0)
                and near(b.ZLength, 0)
                and near(abs(b.ZMin), 4)
                and b.YLength > 9.9
                and b.YMax < 0
            ),
            2,
            "Carrier " + label,
        )
    return _checked(mirrored_y(body, sign), "Braced-guard keyed motor carrier")


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
        "guard_axial_range_mm": [8.0, 11.0],
        "guard_inner_outer_radius_mm": [23.0, 26.0],
        "guard_root_fan_height_mm": GUARD_ROOT_FAN_HEIGHT,
        "guard_outer_return": {
            "rear_bridge_x_mm": [-8.0, -5.0],
            "return_x_mm": [-8.0, 11.0],
            "return_outboard_distance_mm": [23.0, 26.0],
            "height_mm": GUARD_RETURN_HEIGHT,
            "rear_root_radius_mm": GUARD_RETURN_ROOT_RADIUS,
            "scope": "An integral rear bridge and outer return support the opposite ring sector. The bridge is behind the motor face; the forward return is outside the nominalR23 opening. No outboard shaft or fixed bearing is added.",
        },
        "physical_propeller_clearance_verified": False,
        "scope": "Motor mounting face and guard plane are printed design datums. Body/shaft lengths are supplier nominal dimensions, not measurements. Preview uses s=0 and a 40 by 5 mm disk; hub thickness does not prove blade swept volume. The3x3 ring atX8..11 and12mm-high front root fan retain the known clamp service openings; extra stock is not strength qualification. Coverage of the real blades is unverified. Confirm actual hub seating, rear clip, screws and complete blade sweep before releasing this motor carrier for fabrication. Nominal motion checks do not close these interfaces. Other printed parts are not made unverified by this propeller-specific uncertainty.",
    }


def _output_support(sign):
    """One short rectangular web supports both seats in each bearing housing."""
    bed = translated_shape(
        bearing_retention.lower_housing_shape(), y=BEARING_CENTRES_ABS_Y[0], z=PIVOT_Z
    )
    beam_top = FOOT_BOTTOM_Z + FOOT_THICKNESS
    post = box(
        BEARING_POST_WIDTH,
        BEARING_POST_DEPTH,
        PIVOT_Z + bearing_retention.BODY_BOTTOM_Z - beam_top,
        (-BEARING_POST_WIDTH / 2, BEARING_GUIDE_START_Y, beam_top),
    )
    return mirrored_y(union([bed, post]), sign)


def fixed_frame_shape():
    """Standard rail shoes, raised crossbeam and two short bearing webs."""
    half_span = BEARING_CENTRES_ABS_Y[0] + bearing_retention.BODY_REAR_Y
    beam = box(
        FOOT_WIDTH,
        2 * half_span,
        FOOT_THICKNESS,
        (-FOOT_WIDTH / 2, -half_span, FOOT_BOTTOM_Z),
    )
    length = PROPULSION_ATTACHMENT.contact_length_mm
    shoe_top = PROPULSION_ATTACHMENT.seat_z_mm
    width = rail.FAR_LEG_OUTER_Y - rail.MOUNT_OUTER_Y
    pedestal = box(
        length,
        width,
        FOOT_BOTTOM_Z - shoe_top,
        (-length / 2, -width / 2, shoe_top),
    )
    body = union(
        [
            beam,
            pedestal,
            *rail.attachment_shoe_shapes(shared_drive=True),
            _output_support(1),
            _output_support(-1),
            servo_bridge.integrated_cradle_shape(),
        ]
    ).removeSplitter()
    from .edge_blends import fillet_selected, near

    # Each broad web is flush with the housing and beam side/end faces.
    # Only its inward load-transfer corner needs a root blend.
    body = fillet_selected(
        body,
        BEARING_ROOT_RADIUS,
        lambda e, b: (
            near(b.ZMin, FOOT_BOTTOM_Z + FOOT_THICKNESS)
            and near(b.ZLength, 0)
            and near(b.YLength, 0)
            and near(abs(b.YMin), BEARING_GUIDE_START_Y)
            and near(b.XLength, BEARING_POST_WIDTH)
        ),
        2,
        "Short bearing web inward roots",
    )
    return _checked(body, "Integrated servo and inboard-bearing frame")


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
    elif sku in {"M1X6_HEX_HEAD", "M1_HEX_NUT"}:
        thread_diameter, thread_pitch = (1.0, 0.25)
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
        "Print first | paired split bearing seats and keyed cap",
    )
    cup = _print(
        doc,
        group,
        "BearingSeatFitSample",
        bearing_retention.coupon_shape(),
        "Production paired lower bearing housing on a handling foot, used with the keyed cap. "
        "Use the same PA12 process, finish and orientation as the frame. Fit two actual "
        "3x6x2.5 bearings and qualify both outer-ring seats, shield clearance, free rotation "
        "and removal. The nominal diameter-6 split seats and side keys are finish-to-fit: "
        "reject radial rocking or an oversized seat, and never use screw preload to force "
        "the cap into alignment. Nominal bearing axial allowance is 0.5 mm total. "
        "Hard cap/body lands must meet without loading bearings or shields.",
        rotation=App.Rotation(V(0, 0, 1), 45),
    )
    keeper = _print(
        doc,
        group,
        "BearingKeeperFitSample",
        bearing_retention.keeper_shape(),
        "Production shared cap coupon. Assemble with the paired housing, two actual "
        "bearings and two owned M2x10 screws with ordinary M2 nuts. Both locating keys "
        "and hard seating lands must engage before tightening. The screw heads seat "
        "on the cap; the two side-entry nuts bear against the lower body's 2.5 mm floors. "
        "Match process and finish to the production cap, then verify concentricity, "
        "shield clearance at both axial limits, free rotation and screw retention.",
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
    set_property(horn, "FactoryThreadedHoles", profile.threaded, "App::PropertyBool")
    set_property(horn, "HornProfile", profile.key)
    set_property(horn, "HornInterfaceContract", json.dumps(contract, sort_keys=True))
    set_property(horn, "HornPreparationRequired", False, "App::PropertyBool")
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
        servo_horns.preparation_note(profile)
        + " Open root register, one near round opening and two radial slots in the adapter. Keep the OEM horn unchanged. Only the two end bolts are installed in this assembly; the middle slot is an optional interface, not a qualified three-bolt assembly. Align before tightening and check runout.",
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
                "references/m1_horn_hardware_2026-10-02.json"
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
    """Named independent measurements for the integrated support and keyed root."""
    return [
        (
            "frame_crossbeam",
            "PropulsionFixedFrame",
            (0, 20, 24.49),
            (0, 20, 29.51),
            5.0,
        ),
        (
            "integrated_saddle_roof",
            "PropulsionFixedFrame",
            (14, 0, 9.49),
            (14, 0, 12.5),
            3.0,
        ),
        ("bearing_cap_roof", "PortBearingCap", (0, 28, 52.99), (0, 28, 54.51), 1.5),
        (
            "bearing_cap_nut_floor",
            "PropulsionFixedFrame",
            (5.5, 35.8, 47.49),
            (5.5, 35.8, 50.01),
            2.5,
        ),
    ]


def _build_frame(doc, module, spec):
    frame = _print(
        doc,
        module,
        "PropulsionFixedFrame",
        fixed_frame_shape(),
        "One integral PA12 support with two standard carrier U shoes atX±14 and M3x10 rail pairs. Both shoes seat atZ9.5; their rail walls must be coplanar. A raised5mm crossbeam atZ24.5..29.5 ends flush with two18x19mm bearing webs. Only broad R1.5 bearing-web roots are blended. Each servo has its own compact closed planar frame with3mm side walls and a16.7x5x5 local foot overlapping the main beam by3mm; no broad lower plate or upper inter-servo tie. Input axesX±16/Z50 keep16mm mesh distance; output axes remain150mm apart atZ50. The7.4x20.4 window has0.2mm nominal clearance per case face; fastened ears locate and clamp the servo. Remove both small gears, loosen the input jack/driver screw, withdraw its20mm stubY18 thenX60, and remove the loose driverX60 before releasing the ear pairs and withdrawing servo/horn/adapterY14 thenX60. Mirror X/Y on Starboard. Keep OEM horn and M1 joints assembled until off-frame. Finish tight windows without forcing case compression. Each bearing pair uses a common keyed cap on hard lands. Finish nominalØ6 seats to fit;0.5mm bearing float and±0.5mm rotor stops are independent. No cap preload on bearings/shields. Physical fit, retention, stiffness and strength remain unqualified.",
        App.Rotation(V(0, 0, 1), 45),
        sku=spec.frame_sku,
    )
    for key, value in (
        ("FootThickness", FOOT_THICKNESS),
        ("FootBottomZ", FOOT_BOTTOM_Z),
        ("BearingPostWidth", BEARING_POST_WIDTH),
        ("FrameCrossbeamThickness", FOOT_THICKNESS),
        ("RailBoltOffsetX", RAIL_BOLT_OFFSET_X),
        ("RailContactLength", RAIL_CONTACT_LENGTH),
        ("RailBoltAxisZ", rail.BOLT_AXIS_Z),
        ("CentralBridgeSeatZ", PROPULSION_ATTACHMENT.seat_z_mm),
    ):
        set_property(frame, key, value, "App::PropertyLength")
    set_property(frame, "IntegratedRailSaddle", True, "App::PropertyBool")
    set_property(frame, "IntegratedServoSupport", True, "App::PropertyBool")
    set_property(
        frame, "CarriageContactZ", rail.CARRIER_INNER_ROOF_Z, "App::PropertyLength"
    )
    set_property(frame, "RailCenterY", 0, "App::PropertyLength")
    return frame


def _build_output_pod(doc, assembly, prefix, sign, spec):
    printed, hardware = [], []
    pod = create_group(doc, prefix + "Pod", prefix + " braced rotor and output gear")
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
        "Bounded±180deg output, no endpoint wrap. Check actual loaded travel and moving wires.",
    )
    carrier = _print(
        doc,
        pod,
        prefix + "MotorCarrier",
        moving_carrier_shape(sign),
        "The rotor remains supported by its inboard shaft and bearings only. One10mm nominalØ3 D socket,0.5mm shaft flat and radialM2x12 jack provide keyed torque transfer and axial grip. The nut enters from the top and reacts against a3mm outer wall; the screw head floats2mm outside the root, its tip seats on the flat. Do not apply clamp torque as though the head seated. An8mm-thick triangular web joins the3mm motor plate to the solid root. The3x3mm guard has a23mm inner radius and12mm-high inboard fan. A3x8mm rear bridge and outer return arm support the opposite ring sector, behind the motor face and outside the nominal propeller disk; the return has oneR1 rear root. No outboard shaft, fixed bearing or extra hardware is added. Jack access remains open. The inner root face and output-gear web bracket stationary thrust lands with±0.5mm rotor travel independently of bearing shields. Nominal40mm guard geometry does not establish real blade seating, protection or strength; fabrication remains on hold pending installation evidence.",
        App.Rotation(V(0, 1, 0), -90),
        sku=prefix + "MotorCarrier",
    )
    for key, value in (
        ("MotorPlateThickness", MOTOR_PLATE_THICKNESS),
        ("MotorMountFaceX", MOTOR_MOUNT_FACE_X),
        ("TiltAxisToPropellerPlane", PROPELLER_PLANE_X),
        ("GuardRadialWall", GUARD_OUTER_RADIUS - GUARD_INNER_RADIUS),
        ("GuardAxialThickness", GUARD_DEPTH),
        ("GuardRootFanHeight", GUARD_ROOT_FAN_HEIGHT),
        ("GuardReturnHeight", GUARD_RETURN_HEIGHT),
        ("GuardReturnRootRadius", GUARD_RETURN_ROOT_RADIUS),
    ):
        set_property(
            carrier,
            key,
            value,
            "App::PropertyDistance"
            if key == "MotorMountFaceX"
            else "App::PropertyLength",
        )
    set_property(
        carrier, "RotorGeometryContract", json.dumps(rotor_geometry_contract())
    )
    set_property(
        carrier, "PhysicalPropellerClearanceVerified", False, "App::PropertyBool"
    )
    printed.append(carrier)
    side = -sign
    suffix = "Negative" if side < 0 else "Positive"
    low, high = OUTPUT_SHAFT_INNER_Y, OUTPUT_SHAFT_INNER_Y + OUTPUT_DRIVEN_SHAFT_LENGTH
    shaft = cylinder(1.5, OUTPUT_DRIVEN_SHAFT_LENGTH, (0, low, 0))
    for start, length in (
        (high - OUTPUT_SHAFT_FLAT_LENGTH, OUTPUT_SHAFT_FLAT_LENGTH),
        (low, OUTPUT_CARRIER_FLAT_LENGTH),
    ):
        shaft = shaft.cut(box(2, length, 4, (1, start, -2)))
    shaft = mirrored_y(shaft, side)
    hardware.append(
        _buy(
            doc,
            pod,
            prefix + "OutputShaft" + suffix,
            shaft,
            "SS304_CUT3_L42_FLAT5_GRIP11_A0",
            "OneØ3x42 driven rod per rotor; no idler or through-motor shaft. File separate0.5mm-deep flats:5mm at the gear end and11mm at the carrier end, with full round journals through both bearings. Key the10mm carrier socket with its jack screw and the bought gear with its set screw. Actual fits, flats and grip require checks.",
            SHAFT_SOURCE,
            "304 stainless steel (seller claim)",
        )
    )
    jack_pair = _bolt_pair(
        doc,
        pod,
        prefix + "OutputClamp" + suffix,
        (CARRIER_JACK_HEAD_X, side * CARRIER_CLAMP_BOLT_Y, 0),
        (-1, 0, 0),
        grip=5,
        length=12,
    )
    for item in jack_pair:
        set_property(
            item,
            "Notes",
            "M2x12 radial jack screw with an ordinary M2 nut in the top-entry pocket. "
            "The 5 mm head-to-nut bearing-plane spacing includes a 2 mm air gap "
            "outside the carrier and a 3 mm printed nut-reaction wall; it is not "
            "a 5 mm clamped stack. The screw tip bears on the shaft flat while "
            "the head remains floating. Never tighten to seat the head against "
            "the carrier. Qualify actual nut fit, tip contact and axial retention "
            "without crushing the printed wall or damaging the shaft flat.",
        )
    hardware.extend(jack_pair)
    for label, y in zip(("Inboard", "Outboard"), BEARING_CENTRES_ABS_Y):
        bearing = translated_shape(bearing_shape(), y=y - 1.25, z=PIVOT_Z)
        hardware.append(
            _buy_bearing(
                doc,
                assembly,
                prefix + "OutputBearing" + label,
                mirrored_y(bearing, sign),
                "Owned generic3x6x2.5 bearing in a3mm-wide split seat;0.25mm nominal float each way. Hard cap lands and locating keys must seat without radial compression or shield preload. Check actual ring lands, shields and fitted concentricity.",
            )
        )
    cap = translated_shape(
        bearing_retention.cap_shape(), y=BEARING_CENTRES_ABS_Y[0], z=PIVOT_Z
    )
    printed.append(
        _print(
            doc,
            assembly,
            prefix + "BearingCap",
            mirrored_y(cap, sign),
            "One rigid cap retains both inboard bearings. Two1.5mm side keys positively register the cap; finish both halves together to the actual bearings and never use bolt preload to remove radial play. TwoM2x10 screws seat on hard cap/body lands, with7mm grip,1.6mm nuts and1.4mm nominal tip projection. Remove screws/nuts and lift cap+Z; support rotor and remove shaft before lifting bearings. No bearing shields carry cap or rotor-stop load.",
            rotation=App.Rotation(V(0, 0, 1), 0 if sign > 0 else 180),
            sku="PairedBearingCap",
        )
    )
    for label, x in zip(("Negative", "Positive"), bearing_retention.CAP_BOLT_X):
        hardware.extend(
            _bolt_pair(
                doc,
                assembly,
                prefix + "BearingCap" + label,
                (
                    x,
                    sign * (BEARING_CENTRES_ABS_Y[0] + bearing_retention.CAP_BOLT_Y),
                    PIVOT_Z + bearing_retention.CAP_SCREW_SEAT_Z,
                ),
                (0, 0, -1),
                grip=7,
                length=10,
            )
        )
    driver_angle = math.degrees(
        math.atan2(PIVOT_Z - spec.input_z_mm, -sign * spec.input_x_mm)
    )
    output_angle = driver_angle + 180 + 180 / spec.output.teeth
    output_gear = translated_shape(
        mirrored_y(gear_shape(spec.output.teeth, output_angle), sign),
        y=-sign * PIVOT_HALF_SPAN,
    )
    hardware.append(
        _buy(
            doc,
            pod,
            prefix + "OutputGear",
            output_gear,
            spec.output.sku,
            "Bought16T m0.5 gear withØ3 bore and5mm face; set screw bears on prepared flat. Its outer face bears only on the separate frame thrust land after0.5mm axial travel, never a bearing shield. Confirm actual solid web, set-screw retention and rubbing behavior; no qualified thrust capacity is claimed.",
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
        mirrored_y(
            translated_shape(
                gear_shape(spec.driver.teeth, driver_angle), y=DRIVE_INWARD_OFFSET_MM
            ),
            sign,
        ),
        spec.driver.sku,
        f"Selected seller {spec.driver.teeth}T m0.5/20° gear, nominal Ø3 H8 bore, face 3, overall 8, hub Ø12. Stock X06 horn, open clamping adapter and a short Ø3 metal stub transmit torque; no additional input bearing. M3 screw position/length, actual material (aluminium description conflicts with steel attribute), mass and loaded grip remain unverified. Output turns oppositely at {spec.ratio:g} times input. Nominal tooth reference only.",
        spec.driver.item_url,
        "Aluminium alloy (seller claim; steel attribute conflicts)",
    )
    return drive, [gear]


def _build_servo(doc, mount, prefix, sign, spec):
    """Mount the sourced vertical X06 case in its closed integral frame."""
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
        f"Each servo has an integral {servo_bridge.MOUNT_DEPTH:g} mm-deep closed frame with3mm inboard/outboard walls. "
        f"All four case faces have nominal {servo_bridge.CASE_CLEARANCE:g} mm clearance in the{servo_bridge.CASE_WINDOW_WIDTH:g}x{servo_bridge.CASE_WINDOW_HEIGHT:g}mm window. Ear joints locate and clamp the servo. Finish a tight print rather than force case compression. Remove input stub and driver before axial servo withdrawal. "
        "M1.6×8 Phillips kit screws clamp4.5mm printed grip plus1mm ears;0.5mm rear hex recesses restrain ordinary M1.6 nuts. Ear transverse outline remains a conservative 7 mm envelope. Smooth Ø3.90×2.7 spline envelope does not claim tooth detail. Actual case fit, horn seating, OEM retaining screw, wiring exit and loaded travel require physical confirmation. Direct gearing transfers mesh load to the servo output bearings; allowable radial load is unpublished.",
        X06_DATASHEET_SOURCE,
    )
    return [servo_ref], hardware


def _build_servo_drive(doc, assembly, prefix, sign, driver_angle, spec):
    """Keep each independent servo/input drive on its fixed native axis."""
    mount = create_group(
        doc,
        prefix + "ServoMount",
        prefix + " servo and direct drive in closed integral frame",
    )
    assembly.addObject(mount)
    mount.Placement.Base = V(
        sign * spec.input_x_mm, -sign * DRIVE_INWARD_OFFSET_MM, spec.input_z_mm
    )
    set_property(
        mount,
        "ServiceSequence",
        "Set the input to neutral and disconnect leads. Remove both output gears, support the large driver, release its set screw and back off the input M2 jack0.2mm. Using side-entry pliers on the4mm exposed tip, withdraw the20mm stubY18 thenX60. Remove the loose driverX60. Release the selected ear screws/nuts, then withdraw servo/horn/adapterY14 andX60; mirror X/Y for Starboard. OEM horn and M1 joints remain assembled until off-frame. Actual gear set-screw access and plier grip remain checks. Reverse, seat the ears before fitting driver/stub, tighten clamps and recheck mesh. The fixed frame and output bearings remain installed.",
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
        f"Current motor/guard/carrier radius30 overY±{CARRIER_END_Y:g}, output clamps/bolts/shafts/gears radius10 overY±{OUTPUT_SHAFT_SWEEP_HALF_LENGTH:g}. Also reserves a replacement-rotor full-turn cylinder radius34 overY±29.5, including nominal ±0.5 axial travel. This allows space to design a future 50 mm propeller rotor, not compatibility of the present 40 mm guard or struts. Excludes the separately validated gear mesh and input mechanism; full bound is used against external vehicle equipment.",
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
        "integrated_rail_saddle": True,
        "integrated_servo_support": True,
        "printed_part_count": len(printed),
        "purchased_mechanism_hardware_count": len(hardware),
        "device_reference_count": len(references),
        "main_pivot_centers_mm": [
            [0, sign * PIVOT_HALF_SPAN, PIVOT_Z] for sign in (1, -1)
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
            "inward_offset_mm": DRIVE_INWARD_OFFSET_MM,
            "output_to_input_angle_ratio": -spec.ratio,
            "fixed_frame_print_sku": spec.frame_sku,
            "input_mount": "Two compact closed planar frames with3mm side walls,7.4x20.4 case windows and two16.7x5x5 feet into the main beam. No broad lower plate or central upper tie. Nominal case clearance0.2mm per face; ear joints locate and clamp without case compression. Remove both output gears, release input jack/driver screw, withdraw20mm stubY18 thenX60, remove loose driverX60, release ear pairs, then withdraw servo/horn/adapterY14 thenX60. Mirror X/Y for Starboard. OEM horn/M1 joints stay assembled until off-frame. No separate bridge or closure hardware. TwoM3 rail pairs retain the whole frame.",
            "supported_configurations": list(DRIVE_CONFIGURATIONS),
            "limits": "Bounded motion; physical travel, fit, stiffness and grip remain unqualified.",
        },
        "shaft_topology": {
            "output_stub_count": 2,
            "output_driven_length_mm": OUTPUT_DRIVEN_SHAFT_LENGTH,
            "output_idle_count": 0,
            "carrier_grip_length_mm": CARRIER_CLAMP_LENGTH,
            "carrier_flat_length_mm": OUTPUT_CARRIER_FLAT_LENGTH,
            "gear_flat_length_mm": OUTPUT_SHAFT_FLAT_LENGTH,
            "input_count": 2,
            "input_length_mm": servo_coupling.SHAFT_LENGTH,
            "through_shaft_allowed": False,
            "reason": "One inboard driven shaft per rotor spans both bearings; no idler or through-motor shaft.",
            "service": "Remove output gear, disconnect leads and withdraw supported rotor with its shaft locked outwardY60. Service jack/shaft off frame. Never withdraw one shaft through the opposing installed rotor.",
        },
        "bearing_seats": {
            "support_centre_span_mm": BEARING_CENTRES_ABS_Y[1]
            - BEARING_CENTRES_ABS_Y[0],
            "centres_abs_y_mm": list(BEARING_CENTRES_ABS_Y),
            "count": 4,
            "dimensions_mm": [3, 6, 2.5],
            "nominal_bore_mm": 6.0,
            "outer_shoulder_opening_mm": BEARING_WINDOW_DIAMETER,
            "outer_shoulder_thickness_mm": 1.5,
            "rigid_guide_length_mm": bearing_retention.SEAT_WIDTH,
            "complete_circumferential_guide_width_mm": bearing_retention.SEAT_WIDTH,
            "minimum_complete_guide_overlap_mm": 2.5,
            "nominal_bearing_axial_float_mm": 0.5,
            "retention": "Two split seats per rotor; one positively keyed rigid cap with twoM2x10 pairs seats on hard frame lands, not bearings. Independent shoulders retain outer rings; separate carrier/gear thrust lands bound rotor translation.",
            "cap_screw_length_mm": 10,
            "cap_count": 2,
            "finishing": "Coupon-match both split seats and locating side keys to actual bearings. Reject radial shake or cap mismatch rather than tightening it away. Verify shield lands and no preload at both bearing-float limits.",
            "rotor_stop_clearance_each_direction_mm": 0.5,
            "rotor_total_axial_travel_mm": 1.0,
            "assembly": "With rotor/shaft removed, lower both bearings into the open seats, place the keyed cap and seat its two screws/nuts on hard lands. Insert rotor/shaft inward from its own open outer side, install output gear and qualify both axial stops. Bearing service reverses this order.",
        },
        "replacement_rotor_space": {
            "future_propeller_reference_diameter_mm": FUTURE_ROTOR_PROPELLER_DIAMETER,
            "bulk_half_width_mm": FUTURE_ROTOR_HALF_WIDTH,
            "full_rotation_radius_mm": FUTURE_ROTOR_ORBIT_RADIUS,
            "included_axial_travel_each_way_mm": 0.5,
            "scope": "Reservation for a future redesigned rotor, not qualification of the present40mm guard. New blade seating, guard, root, wiring and loaded clearances require design and checks.",
        },
        "process_design_reference": {
            "source": CREALLO_SOURCE,
            "process": "PA12 SLS/MJF",
            "minimum_feature_wall_mm": 1.5,
            "guard_radial_wall_mm": 3,
            "guard_axial_thickness_mm": 3,
            "guard_root_fan_height_mm": 12,
            "guard_return_section_mm": [3, 8],
            "guard_return_root_radius_mm": 1,
            "frame_foot_thickness_mm": FOOT_THICKNESS,
            "frame_foot_z_range_mm": [FOOT_BOTTOM_Z, FOOT_BOTTOM_Z + FOOT_THICKNESS],
            "frame_crossbeam_thickness_mm": FOOT_THICKNESS,
            "bearing_post_root_radius_mm": BEARING_ROOT_RADIUS,
            "frame_lower_exterior_radius_mm": 0.0,
            "servo_cradle_root_radius_mm": 0.0,
        },
        "OEM_interfaces": PROPULSION_EVIDENCE,
        "horn_coupling": coupling_metrics(),
        "carrier_nut_pockets": {
            "across_flats_mm": CARRIER_NUT_POCKET_AF,
            "axial_depth_mm": 1.8,
            "outer_wall_mm": 3.0,
            "top_open": True,
            "nut_axially_captive": False,
            "physical_fit_verified": False,
            "scope": "Top-entry radial jack nut; bolt head does not seat on PA12. Qualify tip/flat contact and loaded retention.",
        },
        "rotor_geometry": rotor_geometry_contract(),
        "motor_plate_thickness_mm": MOTOR_PLATE_THICKNESS,
        "motor_mount_face_x_mm": MOTOR_MOUNT_FACE_X,
        "motor_envelope_centre_x_mm": MOTOR_MOUNT_FACE_X + MOTOR_LENGTH / 2,
        "unfinished_interfaces": [
            "Actual propeller seating/blade sweep",
            "PA12 split-seat/key fits",
            "Gear thrust-web land and set-screw retention",
            "Shaft flats and jack grip",
            "Moving-wire routing",
            "Loaded horn/gear/carrier/frame performance",
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
        f"Integrated KST X06 {drive.driver.teeth}:{drive.output.teeth} drives | two inboard shafts",
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
        doc,
        "ServoDriveModule",
        "Fixed grouping of individually removable servo/input units",
    )
    module.addObject(drive_module)
    parts = {
        "printed": [frame],
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
