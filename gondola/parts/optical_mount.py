"""Compact two-print optical pedestal with one manually clamped pitch axis.

The carrier is placed along the balloon bottom centreline; the one transverse
axis corrects longitudinal curvature. This is not self-levelling or actuated.
"""

import json

import FreeCAD as App
import Part

from gondola.cad import box, create_group, create_printed_part, set_property, union
from gondola.contracts import fasteners
from gondola.contracts.hardware import HEX_NUT_SOURCE, STACK_SCREW_SOURCE

from . import optical_interface, purchased_hardware

V = App.Vector
PIVOT_CENTRE = (23.0, -18.0, 22.0)
ANGLE_LIMIT_DEG = 20.0
EAR_RADIUS = 4.0
EAR_THICKNESS = 2.0
UPRIGHT_WIDTH = 6.0
GUSSET_DEPTH = 2.0
GUSSET_TOP_Z = 10.0
LOW_ARM_THICKNESS = 3.0
LOW_ARM_WIDTH = 5.0
PIVOT_HOLE_DIAMETER = 2.6
TRAY_SIZE_MM = (18.0, 12.0)
TRAY_BOTTOM_Z = 4.5
TRAY_TOP_Z = 6.5
ADHESIVE_ALLOWANCE = 1.0
SCREW_LENGTH = fasteners.OPTICAL_PIVOT_SCREW_LENGTH
SCREW_BEARING_START = -EAR_THICKNESS
NUT_START = EAR_THICKNESS
BOLT_TIP = SCREW_BEARING_START + SCREW_LENGTH


def _cylinder(radius, length, origin, axis):
    return Part.makeCylinder(radius, length, V(*origin), V(*axis))


def _finished(shape, name):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Optical mount is not one valid solid: " + name)
    return shape


def upright_shape():
    """Broad post and one low integral buttress, clear of both foot nuts."""
    x, y, z = PIVOT_CENTRE
    bottom = LOW_ARM_THICKNESS
    left = x - UPRIGHT_WIDTH / 2
    post = box(
        UPRIGHT_WIDTH,
        EAR_THICKNESS,
        z - bottom,
        (left, y - EAR_THICKNESS, bottom),
    )
    points = [
        V(left, y, bottom),
        V(left, y + GUSSET_DEPTH, bottom),
        V(left, y, GUSSET_TOP_Z),
    ]
    buttress = Part.Face(Part.makePolygon(points + [points[0]])).extrude(
        V(UPRIGHT_WIDTH, 0, 0)
    )
    return union([post, buttress]).removeSplitter()


def low_arm_components():
    """Two broad rectangular beams link the corner foot to the centred post."""
    x, y, _ = PIVOT_CENTRE
    left = x - UPRIGHT_WIDTH / 2
    return [
        (
            "outboard_arm",
            box(
                x + UPRIGHT_WIDTH / 2 - 2,
                LOW_ARM_WIDTH,
                LOW_ARM_THICKNESS,
                (2, -LOW_ARM_WIDTH / 2, 0),
            ),
        ),
        (
            "return_arm",
            box(
                UPRIGHT_WIDTH,
                -y + LOW_ARM_WIDTH / 2 + EAR_THICKNESS,
                LOW_ARM_THICKNESS,
                (left, y - EAR_THICKNESS, 0),
            ),
        ),
    ]


def base_shape():
    """One corner foot, low L arm and braced upright ending in a pitch ear."""
    x, y, z = PIVOT_CENTRE
    ear = _cylinder(EAR_RADIUS, EAR_THICKNESS, (x, y - EAR_THICKNESS, z), (0, 1, 0))
    post = upright_shape()
    bore = _cylinder(
        PIVOT_HOLE_DIAMETER / 2,
        2 * EAR_THICKNESS + 2,
        (x, y - EAR_THICKNESS - 1, z),
        (0, 1, 0),
    )
    return _finished(
        union(
            [
                optical_interface.foot_shape(),
                *[shape for _, shape in low_arm_components()],
                ear,
                post,
            ]
        ).cut(bore),
        "base",
    )


def sensor_tray_shape():
    """Continuous adhesive pad and one pitch ear, without invented sensor holes."""
    ear = _cylinder(EAR_RADIUS, EAR_THICKNESS, (0, 0, 0), (0, 1, 0))
    neck = box(4, EAR_THICKNESS, TRAY_BOTTOM_Z, (-2, 0, 0))
    pad = box(
        *TRAY_SIZE_MM,
        TRAY_TOP_Z - TRAY_BOTTOM_Z,
        (-TRAY_SIZE_MM[0] / 2, -TRAY_SIZE_MM[1] / 2, TRAY_BOTTOM_Z),
    )
    bore = _cylinder(PIVOT_HOLE_DIAMETER / 2, 4, (0, -1, 0), (0, 1, 0))
    return _finished(union([ear, neck, pad]).cut(bore), "sensor tray")


def mount_contract():
    return {
        "mechanism": "One manual pitch-Y friction clamp on an outboard L pedestal with carrier-centred sensor",
        "adjustment_degrees_of_freedom": 1,
        "pivot_centre_in_pedestal_mm": PIVOT_CENTRE,
        "pivot_centre_in_carrier_mm": tuple(
            a + b
            for a, b in zip(
                PIVOT_CENTRE,
                (*optical_interface.HOST_ORIGIN_XY, optical_interface.HOST_SUPPORT_Z),
            )
        ),
        "planning_angle_limit_deg": ANGLE_LIMIT_DEG,
        "axis": "Carrier-local Y, transverse to the longitudinal rail. The FC carrier's 180 degree yaw reverses the angle sign, not the physical axis.",
        "physical_angle_stops_modeled": False,
        "self_levelling": False,
        "holding_torque_verified": False,
        "integral_common_rail_shoe": False,
        "carrier_interface": optical_interface.interface_contract(),
        "ear_diameter_mm": 2 * EAR_RADIUS,
        "ear_thickness_mm": EAR_THICKNESS,
        "pivot_clearance_hole_diameter_mm": PIVOT_HOLE_DIAMETER,
        "nominal_ear_radial_wall_mm": EAR_RADIUS - PIVOT_HOLE_DIAMETER / 2,
        "upright_section_mm": (UPRIGHT_WIDTH, EAR_THICKNESS),
        "low_arm_sections_mm": {
            "outboard": (LOW_ARM_WIDTH, LOW_ARM_THICKNESS),
            "return": (UPRIGHT_WIDTH, LOW_ARM_THICKNESS),
        },
        "relocation_scope": "The original corner slot and its two clamps remain. A low integral L arm places the nominal sensor pivot at carrier Y=0, outside both host wiring envelopes. The larger cantilever and footprint are not strength, stiffness or pointing qualifications.",
        "integral_base_buttress": {
            "depth_mm": GUSSET_DEPTH,
            "top_z_mm": GUSSET_TOP_Z,
            "scope": "Low triangular reinforcement on the positive-Y side; no additional part or fastener. Geometric section improvement, not measured strength or pointing stiffness.",
        },
        "tray_size_mm": TRAY_SIZE_MM,
        "tray_bottom_z_in_pitch_frame_mm": TRAY_BOTTOM_Z,
        "tray_top_z_in_pitch_frame_mm": TRAY_TOP_Z,
        "nominal_tray_to_fixed_pitch_disc_gap_mm": TRAY_BOTTOM_Z - EAR_RADIUS,
        "adhesive_allowance_mm": ADHESIVE_ALLOWANCE,
        "hardware": "Three kit steel M2x8 button-head screw / M2 hex nut pairs total: two pedestal clamps and one pitch clamp. No washers.",
        "full_nut_engagement_mm": purchased_hardware.HEX_NUT_HEIGHT,
        "bolt_tip_beyond_nut_mm": BOLT_TIP
        - NUT_START
        - purchased_hardware.HEX_NUT_HEIGHT,
        "assembly": "Print the pedestal and sensor tray separately. Seat and clamp the pedestal on the original corner carrier slot, placing the sensor on carrier Y=0 through the low L arm; clamp the two plain 2 mm pitch ears with the third M2 pair. No intermediate roll bracket or broad tower remains.",
        "adjustment": "Place the rail along the balloon bottom centreline. Support the sensor, loosen its pitch screw while holding the nut, align downward at flight trim, and hand-snug. There is no roll correction or operating play. Native angle limits are planning controls only; no claimed tightening torque, friction capacity, vibration retention or PA12 creep life.",
        "sensor_interface": "Continuous insulating adhesive pad; OEM backside contact, adhesive retention and connector/wire fit remain unverified. Do not invent sensor fixing holes or cover its optical apertures.",
    }


def _pivot_hardware(doc, parent):
    objects = []
    for kind, shape, axial, sku, source in (
        (
            "Bolt",
            purchased_hardware.screw_shape(SCREW_LENGTH),
            SCREW_BEARING_START,
            "M2X8_BUTTON_HEAD",
            STACK_SCREW_SOURCE,
        ),
        (
            "Nut",
            purchased_hardware.hex_nut_shape(),
            NUT_START,
            "M2_HEX_NUT",
            HEX_NUT_SOURCE,
        ),
    ):
        shape = shape.copy()
        shape.rotate(V(), V(1, 0, 0), -90)
        shape.translate(V(PIVOT_CENTRE[0], PIVOT_CENTRE[1] + axial, PIVOT_CENTRE[2]))
        objects.append(
            purchased_hardware.add_hardware(
                doc,
                parent,
                "OpticalPitch" + kind,
                "BUY | manual optical pitch " + kind.lower(),
                shape,
                sku,
                "M2x8 and ordinary M2 nut clamp two plain 2 mm PA12 ears. Nominal full 1.6 mm engagement and 2.4 mm tip projection; verify actual hardware, printed fit and angle retention. No washer, bearing or qualified holding-torque claim.",
                source,
                fasteners.KIT_MATERIAL,
            )
        )
    return objects


def build_optical_mount(doc, parent):
    group = create_group(
        doc, "OpticalFlowModule", "Optical flow | compact single-axis pedestal"
    )
    parent.addObject(group)
    group.Placement = optical_interface.host_placement()
    contract = json.dumps(mount_contract(), sort_keys=True)
    set_property(group, "OpticalMountContract", contract)
    set_property(
        group,
        "AdjustmentControls",
        "OpticalPitchStage.Pitch; one manually clamped transverse axis, no roll stage.",
    )
    set_property(group, "HoldingTorqueVerified", False, "App::PropertyBool")
    set_property(group, "SelfLevelling", False, "App::PropertyBool")
    optical_interface.annotate_interface(group)
    pitch = create_group(doc, "OpticalPitchStage", "Manual pitch | Y axis")
    group.addObject(pitch)
    pitch.Placement = App.Placement(V(*PIVOT_CENTRE), App.Rotation(V(0, 1, 0), 1))
    for key, value in (
        ("Pitch", 0),
        ("MinimumAngle", -ANGLE_LIMIT_DEG),
        ("MaximumAngle", ANGLE_LIMIT_DEG),
    ):
        set_property(pitch, key, value, "App::PropertyAngle", "Manual adjustment")
    pitch.setEditorMode("MinimumAngle", 1)
    pitch.setEditorMode("MaximumAngle", 1)
    pitch.setExpression(
        "Placement.Rotation.Angle", "min(MaximumAngle; max(MinimumAngle; Pitch))"
    )
    printed = []
    for part_parent, name, shape in (
        (group, "OpticalMountBase", base_shape()),
        (pitch, "OpticalSensorTray", sensor_tray_shape()),
    ):
        obj = create_printed_part(
            doc,
            part_parent,
            name,
            "PRINT | " + name,
            shape,
            App.Rotation(),
            "PA12 SLS/MJF compact optical support, two separately printed pieces. One corner foot, low L arm, broad upright and integral low buttress support a sensor on carrier Y=0. Existing M2x8 / M2 nut pairs seat the foot and lock the single pitch joint. Check actual print, contact, clamping, adhesive and optical alignment before use.",
        )
        set_property(obj, "PrintSKU", name)
        set_property(obj, "OpticalMountContract", contract)
        set_property(obj, "PrintProcess", "PA12 SLS or MJF")
        set_property(obj, "HoldingTorqueVerified", False, "App::PropertyBool")
        if name == "OpticalMountBase":
            optical_interface.annotate_interface(obj)
        printed.append(obj)
    hardware = _pivot_hardware(doc, group) + optical_interface.build_hardware(
        doc, group
    )
    doc.recompute()
    return {
        "group": group,
        "pitch_stage": pitch,
        "printed": printed,
        "hardware": hardware,
        "base": printed[0],
    }


def set_pitch(doc, pitch):
    """Set the one saved native control; its own expression bounds motion."""
    doc.getObject("OpticalPitchStage").Pitch = pitch
    doc.recompute()
