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
    PRESSURE_ANGLE_DEG,
    SELECTED_DRIVE,
)
from gondola.contracts.equipment_interfaces import (
    BEARING_SOURCE,
    PROPULSION_EVIDENCE,
    SHAFT_SOURCE,
    X06_DATASHEET_SOURCE,
)
from gondola.contracts.fasteners import KIT_MATERIAL
from gondola.contracts.hardware import (
    BEARING_SPACER,
    CLAMP_SCREW_SOURCE,
    HEX_NUT_SOURCE,
    SERVO_NUT_SOURCE,
    SERVO_SCREW_SOURCE,
)

from . import purchased_hardware, rail, servo_bridge, servo_coupling

V = App.Vector
BASE_Z = rail.SHOE_BOTTOM
FOOT_THICKNESS = 3.0
RAIL_SERVICE_FLOOR_THICKNESS = 2.0
PIVOT_Z = PIVOT_Z_MM
PIVOT_HALF_SPAN = 65.5
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


BEARING_WINDOW_DIAMETER = 5.6
BEARING_GUIDE_START_Y = 26.5
BEARING_SHOULDER_Y = 30.5
BEARING_SHOULDER_THICKNESS = 1.5
CARRIER_END_Y = 26.0
CARRIER_STOP_RADIUS = 3.8
BEARING_SPACER_START_Y = CARRIER_END_Y
SPACER_ASSEMBLY_SHIFT = 0.3
SHAFT_ASSEMBLY_RETRACTION = 6.5
CLAMP_SCREW_SKU = "M2X8_BUTTON_HEAD"
NUT_SKU = "M2_HEX_NUT"
BEARING_SKU = "BEARING_3X6X2_5"


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


def _bearing_cup(start_y, *, positive_side=True):
    """Inward-open rigid cup; the canonical bearing occupies Y0..2.5.

    A four-millimetre guide preserves full radial support during inward bearing
    float. The integral outer shoulder replaces the cap and its fastening arm.
    """
    body = cylinder(4.8, 5.5, (0, -1.5, 0))
    body = body.cut(cylinder(3, 4.01, (0, -1.51, 0)))
    body = body.cut(cylinder(BEARING_WINDOW_DIAMETER / 2, 5.7, (0, -1.6, 0)))
    if not positive_side:
        body = mirrored_y(body, -1)
    return _shifted(body, y=start_y)


def bearing_spacer_shape():
    """Bought flanged bush, neck toward the positive-side bearing inner ring."""
    flange_t = BEARING_SPACER["flange_thickness_mm"]
    body = union(
        [
            cylinder(
                BEARING_SPACER["flange_diameter_mm"] / 2,
                flange_t,
                (0, BEARING_SPACER_START_Y, 0),
            ),
            cylinder(
                BEARING_SPACER["neck_diameter_mm"] / 2,
                BEARING_SPACER["neck_length_mm"],
                (0, BEARING_SPACER_START_Y + flange_t, 0),
            ),
        ]
    )
    return _checked(
        body.cut(
            cylinder(
                BEARING_SPACER["bore_mm"] / 2,
                BEARING_SPACER["overall_length_mm"] + 0.2,
                (0, BEARING_SPACER_START_Y - 0.1, 0),
            )
        ),
        "Bought inner-ring flanged spacer",
    )


def shaft_clamp_shape():
    body = union(
        [
            cylinder(3.1, 5.5, (0, 20.5, 0)),
            cylinder(CARRIER_STOP_RADIUS, 1.5, (0, CARRIER_END_Y - 1.5, 0)),
            box(6, 5.5, 6, (1, 20.5, -3)),
        ]
    )
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
        clamp = union([strut, shaft_clamp_shape()])
        # Open the complete seat above/below the enlarged clamp, without the
        # thin crescent that a 1 mm-deep cut leaves at its outer cylindrical edge.
        for z in (2.5, -4.5):
            clamp = clamp.cut(box(5.8, 6, 2, (1.3, 20.25, z)))
        parts.append(mirrored_y(clamp, side))
    guard = cylinder(GUARD_OUTER_RADIUS, 2, (11, 0, 0), (1, 0, 0)).cut(
        cylinder(GUARD_INNER_RADIUS, 4, (10, 0, 0), (1, 0, 0))
    )
    parts.extend(
        [guard, box(2, 4, 6.4, (11, -26, -3.2)), box(2, 4, 6.4, (11, 22, -3.2))]
    )
    return _checked(union(parts), "Motor carrier with split shaft clamps")


def _output_support(sign):
    parts = []
    # A plain full-width foot distributes the bearing-post loads without long
    # lightening windows, separate ribs or narrow perimeter strips.
    foot_length = PIVOT_HALF_SPAN + 33 - 20
    foot = box(18, foot_length, FOOT_THICKNESS, (-9, 20, BASE_Z))
    parts.append(foot)
    for side in (-1, 1):
        y_start = 26.5 if side > 0 else -30.5
        post = box(
            9.6,
            4,
            PIVOT_Z - BASE_Z - FOOT_THICKNESS,
            (-4.8, y_start + PIVOT_HALF_SPAN, BASE_Z + FOOT_THICKNESS),
        )
        # Keep the full post and its root solid. Rail-key access stays in the
        # central service bay rather than passing through these bearing feet.
        cup = _bearing_cup(28 if side > 0 else -28, positive_side=side > 0)
        cup = _shifted(cup, y=PIVOT_HALF_SPAN, z=PIVOT_Z)
        post = post.cut(
            cylinder(3, 4.02, (0, PIVOT_HALF_SPAN + y_start - 0.01, PIVOT_Z))
        )
        parts.extend([post, cup])
    result = union(parts)
    if sign < 0:
        result = result.mirror(V(), V(1, 0, 0))
        result = mirrored_y(result, -1)
    return result


def fixed_frame_shape():
    """Common rail shoe, output supports and fixed servo-bridge seats."""
    # The short central floor stays below the rail screw head. The outboard
    # bearing feet are thicker and overlap it without separate connectors.
    wings = box(18, 70, RAIL_SERVICE_FLOOR_THICKNESS, (-9, -35, BASE_Z)).cut(
        box(20, rail.SHOE_WIDTH, 20, (-10, -rail.SHOE_WIDTH / 2, 0))
    )
    # Raise the already solid shoe roof to carry the common servo wall through
    # its plate directly, instead of spanning between the two outboard feet.
    central_seat = box(
        rail.SHOE_LENGTH,
        rail.SHOE_WIDTH,
        servo_bridge.CONNECTOR_PLATE_BOTTOM_Z - rail.TOP_Z,
        (-rail.SHOE_LENGTH / 2, -rail.SHOE_WIDTH / 2, rail.TOP_Z),
    )
    frame = union(
        [
            rail.shoe_shape(),
            central_seat,
            wings,
            _output_support(1),
            _output_support(-1),
            servo_bridge.frame_seats(),
        ]
    )
    return _checked(
        servo_bridge.cut_mounting_holes(frame), "Common output-bearing frame"
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
        if sku.startswith("ALI_KAILASH")
        else (1.6 if sku.startswith("M1_6") else (2.0 if threaded else None)),
        thread_pitch=0.5
        if sku.startswith("ALI_KAILASH")
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
        else purchased_hardware.hex_nut_shape()
    ).copy()
    # Servo case length is vertical; the hex nut's flats face the case ends.
    nut.Placement = App.Placement(V(*origin) + V(*direction) * grip, rotation)
    notes = (
        f"M1.6x0.35 x8 DIN84 cheese-head bolt and DIN934 hex nut;{grip:g}mm grip+1.3mm nut gives{8 - grip - 1.3:g}mm tip. NominalØ2 OEM hole gives0.2mm radial clearance,Ø3 head gives0.5mm case gap. Verify actual ear/seat fit."
        if servo_ear
        else f"Selected-kit M2x0.4 x8 button-head bolt and hex nut; nominal{grip:g}mm grip,1.6mm nut,{8 - grip - 1.6:g}mm tip projection. Head is a conservative clearance envelope pending measurement. Hand snug; actual preload and printed bearing faces unqualified."
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
            "A2 stainless steel" if servo_ear else KIT_MATERIAL,
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
            "A2 stainless steel" if servo_ear else KIT_MATERIAL,
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
    """Reuse the actual inward-open seat before committing to full prints."""
    group = create_group(
        doc,
        "BearingFitCoupons",
        "Print first | 3×6×2.5 bearing seat and stock spacer fit",
    )
    cup = _print(
        doc,
        group,
        "BearingSeatFitSample",
        _bearing_cup(0),
        "Actual inward-open nominal 6 mm bearing cup and integral 5.6 mm outer shoulder opening. "
        "Print with the same process/material/finish as the supports. Finish and "
        "measure fit, concentricity and shield clearance using an actual purchased bearing. "
        "Trial the purchased F3035-5105T spacer on the actual shaft: narrow neck "
        "must contact only the inner ring, flange and neck must clear both shields "
        "and outer ring through available eccentricity. No extra onboard hardware "
        "is counted. This coupon does not qualify full-frame axial capture or strength.",
    )
    return {"group": group, "printed": [cup]}


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
        "Bought KST0415.13 15T horn with only its existing tip hole locally enlarged from nominal Ø1 to Ø1.8 at radius13.2mm. The hole modification is not a factory variant or a strength qualification. Support and deburr the blade; reject damaged parts. The original spline and OEM retaining screw remain unchanged. Nominal0.2mm case gap follows the published spline protrusion and horn recess; verify actual seating and screw clearance.",
        coupling.HORN_SOURCE,
        coupling.HORN_MATERIAL,
    )
    printed = [
        _print(
            doc,
            parent,
            prefix + "HornGearAdapter",
            positioned(coupling.adapter_shape()),
            "One-piece adapter attaches directly through the prepared horn tip with an M1.6x8 screw and nut; no printed rear strap or washer. "
            f"The stock horn drives an {coupling.SHAFT_SOCKET_LENGTH:g} mm D socket and locally cut Ø3×{coupling.SHAFT_LENGTH:g} metal stub. "
            "A radial M2 screw/nut retains the stub. The hub register and flat tip datum retain0.05mm nominal finish-fit clearance; the long blade sides are open and a 3 by 1.8 mm central tip stop replaces the enclosing end wall. Bolt preload and the through-bolt retain the joint; the locating faces alone do not qualify torque retention. Install the OEM horn screw before the adapter. Verify prepared hole, face contact, concentricity, screw grip, backlash, creep and loaded deflection; nominal geometry is not a torque qualification.",
            rotation=App.Rotation(V(0, 0, 1), 180) if sign < 0 else App.Rotation(),
            sku="KST0415_GearAdapter",
        )
    ]
    hardware = [horn]
    rotation = App.Rotation(V(0, 0, 1), V(*coupling.BOLT_DIRECTION))
    for positions in coupling.fastener_positions():
        for kind, anchor in positions.items():
            shape = (
                purchased_hardware.servo_screw_shape().copy()
                if kind == "screw"
                else purchased_hardware.servo_nut_shape().copy()
            )
            shape.Placement = App.Placement(V(*anchor), rotation)
            hardware.append(
                _buy(
                    doc,
                    parent,
                    prefix + "HornGearClamp" + ("Bolt" if kind == "screw" else "Nut"),
                    positioned(shape),
                    "M1_6X8_CHEESE_HEAD" if kind == "screw" else "M1_6_HEX_NUT_DIN934",
                    "M1.6x8 DIN84 screw and DIN934 nut through the locally enlarged horn tip and adapter. Head bears on metal; nut bears on the adapter front. Nominal5.2mm grip+1.3mm nut leaves1.5mm tip. Insert and service at neutral with the OEM horn screw already installed. Verify adequate seated bearing contact, prepared hole integrity, clamping and loaded bidirectional retention; the adjacent stock hole slightly interrupts the nominal head-bearing annulus.",
                    SERVO_SCREW_SOURCE if kind == "screw" else SERVO_NUT_SOURCE,
                    "A2 stainless steel",
                    threaded=True,
                )
            )
    hardware.append(
        _buy(
            doc,
            parent,
            prefix + "InputShaft",
            positioned(coupling.driver_shaft_shape()),
            f"AL6061_CUT3_L{coupling.SHAFT_LENGTH:g}_FLAT{coupling.SHAFT_LENGTH:g}_A0",
            f"Cut selected Ø3 6061 stock to {coupling.SHAFT_LENGTH:g} mm, deburr, and file a {coupling.SHAFT_FLAT_DEPTH:g} mm-deep full-length flat. "
            "The finished D socket keys torque; an M2 radial jack screw bears on the flat for axial retention. The M3 gear screw also bears on the flat. Nominal geometry is not a guarantee of stock diameter, straightness, concentricity or holding torque.",
            SHAFT_SOURCE,
            "Aluminium 6061 (seller claim)",
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
                "M2×6 radial jack screw through a captive kit hex nut, tip against the shaft flat. Head has nominal 0.5 mm clearance from the boss and does not seat on PA12. Nut bears against the 1.5 mm outer pocket wall. Tighten gently and verify retention without crushing or stripping the aluminium flat; the full-length flat also keys the socket.",
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
    y = servo_bridge.case_front_y() - 4.7 - servo_bridge.MOUNT_DEPTH / 2
    return [
        (
            f"{prefix}_bearing_post_{suffix}",
            "PropulsionFixedFrame",
            (0, sign * (PIVOT_HALF_SPAN + local_y - 0.01), 24),
            (0, sign * (PIVOT_HALF_SPAN + local_y + 4.01), 24),
            4.0,
        )
        for sign, prefix in ((1, "port"), (-1, "starboard"))
        for local_y, suffix in ((-30.5, "inner"), (26.5, "outer"))
    ] + [
        (
            "output_bearing_outer_wall",
            "PropulsionFixedFrame",
            (-4.81, PIVOT_HALF_SPAN + 29, PIVOT_Z),
            (-2.99, PIVOT_HALF_SPAN + 29, PIVOT_Z),
            1.8,
        ),
        (
            "bearing_integral_outer_shoulder",
            "PropulsionFixedFrame",
            (-2.9, PIVOT_HALF_SPAN + 30.49, PIVOT_Z),
            (-2.9, PIVOT_HALF_SPAN + 32.01, PIVOT_Z),
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
            (x, y, z + 10.11),
            2.0,
        ),
        (
            "servo_bridge_pad",
            "ServoDriveBridge",
            (18.5, 15, 8.69),
            (18.5, 15, 13.41),
            4.7,
        ),
        (
            "servo_bridge_connector_plate",
            "ServoDriveBridge",
            (0, 8, 11.39),
            (0, 8, 13.41),
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
        "Common integral rail shoe, full-width 18 by 3 mm solid output-support feet and four plain 9.6 by 4 mm bearing posts with continuous roots. The output axes are 131 mm apart. An 18 by 22 mm central shoe roof reaches the bridge plate at Z11.4 and supports its common servo wall directly; the two broad rectangular outboard seats remain. These contact faces must all seat without rocking or drawing a warped bridge flat with the bolts. Only the short central rail-service floor stays 2 mm thick below the raised clamp head; no long lightening windows, post tunnels, extra ribs or separate base parts remain. One inside Y datum and one outside X stop locate the removable bridge; two M2 bolts clamp it. Actual printed seating, gear centre distance, stiffness and creep remain unqualified. Inward-open Ø6 seats retain a 4 mm-long rigid guide and integral 1.5 mm outer shoulders. Stock flanged spacers and the assembled carrier limit inward bearing escape. Finish seats using the matching coupon and verify actual axial freedom, shield clearance and full bearing guidance; no bearing preload is designed.",
        App.Rotation(V(0, 0, 1), 45),
        sku=spec.frame_sku,
    )
    set_property(frame, "IntegratedRailShoe", True, "App::PropertyBool")
    set_property(frame, "CarriageContactZ", BASE_Z, "App::PropertyLength")
    set_property(frame, "RailCenterY", 0, "App::PropertyLength")
    set_property(frame, "FootThickness", FOOT_THICKNESS, "App::PropertyLength")
    set_property(
        frame,
        "RailServiceFloorThickness",
        RAIL_SERVICE_FLOOR_THICKNESS,
        "App::PropertyLength",
    )
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
        "Integral guard, motor plate and two split Ø3.2 shaft clamps with broad Ø7.6 end flanges, 1.5mm thick. The remaining clamp body retains its original section to avoid unnecessary stiffening around the clamp bolt. Two separate Ø3 shafts stop before the motor. M2x8 clamps provide frictional torque and axial grip; strength, creep and slip require tests. Nominal 0.5 mm carrier/frame end clearance provides low-load rubbing stops. Purchased inner-ring spacers limit inward bearing movement while the 4 mm cup guide preserves full radial support. Assemble bearings and spacers first, stage spacers 0.3 mm outward and shafts 6.5 mm outward, insert the carrier transversely, then advance and clamp shafts. Three 1.8 mm open radial motor slots follow M1.4/PCD6.6. Actual OEM screw length, usable depth, head footprint, rear-clip clearance and finished axial fits remain unverified.",
        App.Rotation(V(0, 1, 0), -90),
        sku="GearedMotorCarrier",
    )
    printed.append(carrier)
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        driven = side == -sign
        low, high = (20, 44) if driven else (20, 34)
        shaft = cylinder(1.5, high - low, (0, low, 0))
        if driven:
            shaft = shaft.cut(box(2, 5, 4, (1, 39, -2)))
        shaft = mirrored_y(shaft, side)
        sku = "AL6061_CUT3_L24_FLAT5_A0" if driven else "AL6061_CUT3_L14"
        hardware.append(
            _buy(
                doc,
                pod,
                prefix + "OutputShaft" + suffix,
                shaft,
                sku,
                "Cut the selected nominal Ø3 mm 6061 rod to length and deburr. Separate output stubs leave the motor bay clear. Driven stub has a locally prepared 0.5 mm deep flat on the final 5 mm at the gear end, entirely outside the bearing journal. Clock the flat toward the M3 screw after tooth phasing. Diameter tolerance, straightness, clamp slip and actual fit remain sample checks; replace with a matching nominal Ø3 precision shaft if needed.",
                SHAFT_SOURCE,
                "Aluminium 6061 (seller claim)",
            )
        )
        hardware.extend(
            _bolt_pair(
                doc,
                pod,
                prefix + "OutputClamp" + suffix,
                (4.2, side * 23.25, -2.5),
                (0, 0, 1),
                grip=5,
            )
        )
        # All bearing geometry is fixed; each shaft rotates with the pod.
        bearing_start = sign * PIVOT_HALF_SPAN + min(side * 28, side * 30.5)
        bearing = _buy_bearing(
            doc,
            assembly,
            prefix + "OutputBearing" + suffix,
            _shifted(bearing_shape(), y=bearing_start, z=PIVOT_Z),
            "Selected generic 3×6×2.5 bearing, annular clearance envelope; brand, internal axial play, race lands, shields and fits need inspection. The integral outer shoulder stops outward movement; the inner-ring spacer and retained carrier bound inward movement. The nominal 4 mm guide supports the complete bearing width through the nominal 1 mm maximum inward float. Finish the seat and qualify actual internal play and stack dimensions; no shield contact or bearing preload is intended.",
        )
        hardware.append(bearing)
        hardware.append(
            _buy(
                doc,
                pod,
                prefix + "OutputBearingSpacer" + suffix,
                mirrored_y(bearing_spacer_shape(), side),
                BEARING_SPACER["sku"],
                "Bought F3035-5105T flanged steel bush used as a loose inner-ring spacer: Ø3 bore, Ø3.5 neck, Ø5 flange, 1 mm flange plus 0.5 mm neck. Neck faces bearing. Installed pose is the carrier-side end of its axial float; it is not keyed to the shaft or clamped as a bearing preload stack. Nominal 0.5 mm axial gap remains to the bearing. Verify the actual neck and chamfer contact only the received bearing inner ring throughout shaft/bore eccentricity; reference MR63ZZ abutment limits do not qualify this generic bearing. Confirm free rotation, full guide engagement and actual assembled endplay. Stage 0.3 mm toward the bearing for carrier insertion with the shaft retracted 6.5 mm.",
                BEARING_SPACER["source"],
                BEARING_SPACER["material"],
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
        "Official case envelope, rotated 90 degrees about the output axis so the body extends downward. Output axis is 5 mm from the case end; sourced ear axes are Ø2 on 24 mm pitch. Both servos share one 5 mm-deep wall with 3 mm outer sides and a 4.8 mm central web. Each nonlocating 8 by 21 mm case opening has nominal 0.5 mm side and end clearance around the body. M1.6×8 DIN84 through-bolts clamp 5 mm printed grip plus 1 mm ears. Ear transverse outline remains a conservative 7 mm envelope. Smooth Ø3.90×2.7 spline envelope does not claim tooth detail. Actual case fit, horn seating, OEM retaining screw, wiring exit and loaded travel require physical confirmation. Direct gearing transfers mesh load to the servo output bearings; allowable radial load is unpublished.",
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
            "input_mount": "Prepared stock-horn drives on one removable paired bridge with a common central servo wall. The integral central shoe roof directly supports its central plate, joined to the mounting feet by two broad straight arms with open sides; two broad outboard seats and unilateral locating datums establish the fixed position, with two M2 mount pairs providing clamping. All support faces must seat without rocking. Only the selected 48T/16T configuration is supported. A future ratio change requires sourced replacement parts, redesign and validation of the complete transmission.",
            "supported_configurations": list(DRIVE_CONFIGURATIONS),
            "limits": "Bounded motion only. Servo travel, tooth clearance, backlash, clamp slip and wire loops require physical calibration.",
        },
        "shaft_topology": {
            "output_stub_count": 4,
            "output_driven_length_mm": 24,
            "output_idle_length_mm": 14,
            "input_count": 2,
            "input_length_mm": servo_coupling.SHAFT_LENGTH,
            "through_shaft_allowed": False,
            "reason": "A through-shaft crosses the motor. Separate stubs leave the motor bay clear.",
        },
        "bearing_seats": {
            "count": 4,
            "dimensions_mm": [3, 6, 2.5],
            "nominal_bore_mm": 6,
            "outer_shoulder_opening_mm": BEARING_WINDOW_DIAMETER,
            "outer_shoulder_thickness_mm": BEARING_SHOULDER_THICKNESS,
            "rigid_guide_length_mm": BEARING_SHOULDER_Y - BEARING_GUIDE_START_Y,
            "retention": "Integral outer shoulders, loose stock inner-ring spacers and carrier/frame travel stops; no separate bearing caps or cap fasteners.",
            "spacer_sku": BEARING_SPACER["sku"],
            "spacer_overall_length_mm": BEARING_SPACER["overall_length_mm"],
            "nominal_spacer_to_bearing_gap_mm": 0.5,
            "nominal_maximum_bearing_inward_float_mm": 1.0,
            "nominal_full_guide_reserve_mm": 0.5,
            "finishing": "Nominal fit prototype. Print matching coupon, finish and measure bearing seats. Measure received bearing inner-ring lands/internal axial play, spacer neck/chamfer and lengths, shaft fits and frame axial stack. Creallo tolerances do not prove free running, race contact or remaining full guide support. Do not force bearings into undersized seats or clamp a preload stack.",
            "running_axial_clearance_mm": 0.5,
            "assembly": "With output gear removed and output clamps loose, install bearings/spacers from the empty carrier bay. Stage spacers 0.3 mm outward and output shafts 6.5 mm outward; insert carrier transversely, then advance shafts and clamp. The paired servo bridge remains removable and need not be dismantled for this path.",
        },
        "process_design_reference": {
            "source": CREALLO_SOURCE,
            "process": "PA12 SLS/MJF",
            "minimum_feature_wall_mm": 1.5,
            "guard_radial_wall_mm": 1.5,
            "frame_foot_thickness_mm": FOOT_THICKNESS,
            "rail_service_floor_thickness_mm": RAIL_SERVICE_FLOOR_THICKNESS,
        },
        "OEM_interfaces": PROPULSION_EVIDENCE,
        "horn_coupling": coupling_metrics(),
        "unfinished_interfaces": [
            "Measured OEM horn seating and retaining screw",
            "Actual direct horn-to-gear adapter clearance and grip",
            "Servo output-bearing deflection under direct gear mesh load",
            "Printed bridge seating, cradle fit and retained gear center distance",
            "Motor rear clip, seat and M1.4 usable depth",
            "Printed bearing fits, actual race lands, spacer eccentricity/shield clearance and bounded axial capture",
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
        "One removable paired bridge with a single 26.8 mm-wide by 5 mm-deep central servo wall: two 8 by 21 mm case windows, 3 mm outer sides and a shared 4.8 mm middle web. The common wall joins a 26.8 by 22 by 2 mm central plate on the frame's central shoe roof. Two broad 15.6 by 18 by 2 mm straight arms connect the outboard feet with 3 mm overlap onto the central plate; unused side regions are open within the unchanged 39 by 52 mm footprint. The plate clears the rail-key elbow and the feet stand outside the rail head screw; no thin perimeter ring or local service tunnels remain. Two open 6 mm head-access counterbores retain the existing M2x8 mounting screws and 5 mm grip against fixed X/Y datums. Nominal clearance below the servo body exceeds 5 mm; actual lead exit and bend requirements need the supplied hardware. For bench replacement remove both small output gears, then the mount pairs; lift 0.5 mm and slide 80 mm in +X with servos, horns and large gears assembled. All output shafts, bearings, loose spacers and motor carriers remain installed. Verify all support faces seat without rocking, actual centre distance and handling; do not force a warped bridge flat with its screws.",
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
                    servo_bridge.MOUNT_BOLT_SEAT_Z,
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
