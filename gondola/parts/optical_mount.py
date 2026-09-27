"""Integral-carrier, manually clamped roll/pitch optical sensor support.

The fixed portal is integrated into its selected rail carrier. Two movable PA12
parts print separately. Two ordinary M2 fastener stacks clamp
plain contact faces; the native angle limits are planning controls, not physical
stops, self-levelling, or a qualified friction/holding-torque specification.
"""

import json

import FreeCAD as App
import Part

from gondola.cad import box, create_group, create_printed_part, set_property, union
from gondola.contracts import fasteners
from gondola.contracts.design import STACK_ANCHOR_LOCATIONS
from gondola.contracts.hardware import HEX_NUT_SOURCE, STACK_SCREW_SOURCE

from . import purchased_hardware, stack_interface

V = App.Vector
ROLL_PIVOT_Z = 8.0
PITCH_PIVOT_OFFSET_Z = 10.0
ANGLE_LIMIT_DEG = 20.0
EAR_RADIUS = 3.5
EAR_THICKNESS = 2.0
ROLL_POST_WIDTH = 3.0
ROLL_POST_BOTTOM_Z = 2.8
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


def roll_support_shape():
    """Fixed roll ear and post, in portal-top coordinates."""
    ear = _cylinder(
        EAR_RADIUS, EAR_THICKNESS, (-EAR_THICKNESS, 0, ROLL_PIVOT_Z), (1, 0, 0)
    )
    post = box(
        EAR_THICKNESS,
        2 * EAR_RADIUS,
        ROLL_PIVOT_Z - stack_interface.TOP_BEAM_THICKNESS,
        (-EAR_THICKNESS, -EAR_RADIUS, stack_interface.TOP_BEAM_THICKNESS),
    )
    bore = _cylinder(
        PIVOT_HOLE_DIAMETER / 2,
        2 * EAR_THICKNESS + 2,
        (-EAR_THICKNESS - 1, 0, ROLL_PIVOT_Z),
        (1, 0, 0),
    )
    return _finished(union([ear, post]).cut(bore), "fixed roll support")


def base_shape():
    """Portal and fixed roll support; a construction shape, never a separate print."""
    return _finished(
        union([stack_interface.tower_shape(), roll_support_shape()]), "integral support"
    )


def fixed_base_shape(doc):
    """World-space support subset of the actual integrated carrier."""
    shape = base_shape()
    shape.Placement = doc.OpticalFlowModule.getGlobalPlacement().multiply(
        shape.Placement
    )
    return shape


def roll_bracket_shape():
    """Orthogonal ears joined by one 3 by 2 mm beam, in the roll frame."""
    first = _cylinder(EAR_RADIUS, EAR_THICKNESS, (0, 0, 0), (1, 0, 0))
    # Widen only +X, within the second ear's radial outline. Start above the
    # first-axis nut's full circumradius; the first ear contains the old narrow
    # post below this height. Keep Y in the second ear's plane to clear its head.
    post = box(
        ROLL_POST_WIDTH,
        EAR_THICKNESS,
        PITCH_PIVOT_OFFSET_Z - ROLL_POST_BOTTOM_Z,
        (0, -EAR_THICKNESS, ROLL_POST_BOTTOM_Z),
    )
    second = _cylinder(
        EAR_RADIUS,
        EAR_THICKNESS,
        (0, -EAR_THICKNESS, PITCH_PIVOT_OFFSET_Z),
        (0, 1, 0),
    )
    shape = union([first, post, second])
    shape = shape.cut(_cylinder(PIVOT_HOLE_DIAMETER / 2, 5, (-1, 0, 0), (1, 0, 0))).cut(
        _cylinder(
            PIVOT_HOLE_DIAMETER / 2,
            6,
            (0, -EAR_THICKNESS - 1, PITCH_PIVOT_OFFSET_Z),
            (0, 1, 0),
        )
    )
    return _finished(shape, "roll bracket")


def sensor_tray_shape():
    """Continuous adhesive pad and one 2 mm pitch ear, in the pitch frame."""
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
        "mechanism": "Separate manual roll-X and pitch-Y friction clamps",
        "roll_pivot_z_mm": ROLL_PIVOT_Z,
        "pitch_pivot_offset_z_mm": PITCH_PIVOT_OFFSET_Z,
        "planning_angle_limit_each_axis_deg": ANGLE_LIMIT_DEG,
        "physical_angle_stops_modeled": False,
        "self_levelling": False,
        "holding_torque_verified": False,
        "integral_common_rail_shoe": True,
        "separate_fixed_base_print": False,
        "movable_print_count": 2,
        "standard_stack_interface": f"Two diagonal rigid legs at {STACK_ANCHOR_LOCATIONS}, joined by straight upper and lower beams; portal and selected carrier form one printed solid independently of FC dampers",
        "ear_diameter_mm": 2 * EAR_RADIUS,
        "ear_thickness_mm": EAR_THICKNESS,
        "pivot_clearance_hole_diameter_mm": PIVOT_HOLE_DIAMETER,
        "nominal_ear_radial_wall_mm": EAR_RADIUS - PIVOT_HOLE_DIAMETER / 2,
        "post_section_mm": [ROLL_POST_WIDTH, EAR_THICKNESS],
        "roll_post_bottom_z_mm": ROLL_POST_BOTTOM_Z,
        "tray_size_mm": list(TRAY_SIZE_MM),
        "tray_bottom_z_in_pitch_frame_mm": TRAY_BOTTOM_Z,
        "tray_top_z_in_pitch_frame_mm": TRAY_TOP_Z,
        "nominal_tray_to_fixed_pitch_disc_gap_mm": TRAY_BOTTOM_Z - EAR_RADIUS,
        "adhesive_allowance_mm": ADHESIVE_ALLOWANCE,
        "hardware_per_axis": "Kit steel M2x8 button-head screw and M2 hex nut; no washers. Unmeasured head uses a design clearance envelope.",
        "full_nut_engagement_mm": purchased_hardware.HEX_NUT_HEIGHT,
        "bolt_tip_beyond_nut_mm": BOLT_TIP
        - NUT_START
        - purchased_hardware.HEX_NUT_HEIGHT,
        "minimum_nominal_pivot_wall_mm": EAR_THICKNESS,
        "fastener_fit_scope": "Nominal screw projection is 2.4 mm beyond a 1.6 mm nut. Two ears each 0.3 mm thicker leave 1.8 mm, before screw-length tolerance. Measure printed thickness, kit head and screw/nut before use; full physical engagement is unverified.",
        "assembly": "Print the selected integral portal/carrier and two movable head parts. No separate base or foot hardware. Plain nominal contact faces touch when the bought fasteners clamp them. No printed thread, bearing or screw.",
        "adjustment": "Support the sensor, hold the hex nut with a small wrench or pliers, loosen the M2 screw, set its angle, then hand snug. Native limits are design controls only; no claimed tightening torque, friction capacity, vibration retention or PA12 creep life.",
        "sensor_interface": "Continuous insulating adhesive pad; OEM backside contact, adhesive retention and connector/wire fit remain unverified. The sensor is not screwed through invented holes.",
    }


def _pivot_hardware(doc, parent, prefix, axis, centre_z):
    rotation_axis = V(0, 1, 0) if axis == "X" else V(1, 0, 0)
    rotation_degrees = 90 if axis == "X" else -90
    specs = [
        (
            "Bolt",
            purchased_hardware.screw_shape(SCREW_LENGTH),
            SCREW_BEARING_START,
            "M2X8_BUTTON_HEAD",
            STACK_SCREW_SOURCE,
            fasteners.KIT_MATERIAL,
        ),
        (
            "Nut",
            purchased_hardware.hex_nut_shape(),
            NUT_START,
            "M2_HEX_NUT",
            HEX_NUT_SOURCE,
            fasteners.KIT_MATERIAL,
        ),
    ]
    objects = []
    for kind, original, axial, sku, source, material in specs:
        shape = original.copy()
        shape.rotate(V(), rotation_axis, rotation_degrees)
        shape.translate(V(axial, 0, centre_z) if axis == "X" else V(0, axial, centre_z))
        obj = purchased_hardware.add_hardware(
            doc,
            parent,
            prefix + kind,
            "BUY | manual optical "
            + prefix.removeprefix("Optical").lower()
            + " "
            + kind,
            shape,
            sku,
            "One kit steel M2x8 button-head screw and M2 hex nut directly clamp two separately printed 2 mm ears, without washers. Nominal full 1.6 mm nut engagement and 2.4 mm tip projection; actual screw length, head envelope and both printed thicknesses must be checked. Manual friction adjustment, not a qualified torque, creep life or holding-load claim.",
            source,
            material,
        )
        objects.append(obj)
    return objects


def build_optical_mount(doc, parent):
    group = create_group(
        doc,
        "OpticalFlowModule",
        "Optical flow | integral-carrier manual roll/pitch mount",
    )
    parent.addObject(group)
    group.Placement.Base.z = stack_interface.STACK_TOP_Z
    contract = json.dumps(mount_contract(), sort_keys=True)
    set_property(group, "OpticalMountContract", contract)
    set_property(
        group,
        "AdjustmentControls",
        "OpticalRollStage.Roll and OpticalPitchStage.Pitch; native controls are on their own stages to avoid parent/child expression cycles.",
    )
    set_property(group, "HoldingTorqueVerified", False, "App::PropertyBool")
    set_property(group, "SelfLevelling", False, "App::PropertyBool")
    roll = create_group(doc, "OpticalRollStage", "Manual roll | X axis")
    group.addObject(roll)
    roll.Placement = App.Placement(V(0, 0, ROLL_PIVOT_Z), App.Rotation(V(1, 0, 0), 1))
    pitch = create_group(doc, "OpticalPitchStage", "Manual pitch | Y axis after roll")
    roll.addObject(pitch)
    pitch.Placement = App.Placement(
        V(0, 0, PITCH_PIVOT_OFFSET_Z), App.Rotation(V(0, 1, 0), 1)
    )
    for stage, key in ((roll, "Roll"), (pitch, "Pitch")):
        set_property(stage, key, 0, "App::PropertyAngle", "Manual adjustment")
        set_property(
            stage,
            "MinimumAngle",
            -ANGLE_LIMIT_DEG,
            "App::PropertyAngle",
            "Manual adjustment",
        )
        set_property(
            stage,
            "MaximumAngle",
            ANGLE_LIMIT_DEG,
            "App::PropertyAngle",
            "Manual adjustment",
        )
        stage.setEditorMode("MinimumAngle", 1)
        stage.setEditorMode("MaximumAngle", 1)
        stage.setExpression(
            "Placement.Rotation.Angle",
            f"min(MaximumAngle; max(MinimumAngle; {key}))",
        )
    printed = []
    for part_parent, name, shape in (
        (roll, "OpticalRollBracket", roll_bracket_shape()),
        (pitch, "OpticalSensorTray", sensor_tray_shape()),
    ):
        obj = create_printed_part(
            doc,
            part_parent,
            name,
            "PRINT | " + name,
            shape,
            App.Rotation(),
            f"PA12 SLS/MJF, printed separately from the integral carrier/portal. Plain 2 mm friction ears use M2x8 screws and hex nuts; their {ROLL_POST_WIDTH:g} by {EAR_THICKNESS:g} mm connecting post starts {ROLL_POST_BOTTOM_Z:g} mm above the roll axis to clear its nut. No washers, printed threads or physical stops. Verify printed thickness, screw/head dimensions, engagement, stiffness, adhesive contact and angle retention before use.",
        )
        set_property(obj, "PrintSKU", name)
        set_property(obj, "OpticalMountContract", contract)
        set_property(obj, "PrintProcess", "PA12 SLS or MJF")
        set_property(obj, "HoldingTorqueVerified", False, "App::PropertyBool")
        printed.append(obj)
    hardware = _pivot_hardware(doc, group, "OpticalRoll", "X", ROLL_PIVOT_Z)
    hardware += _pivot_hardware(doc, roll, "OpticalPitch", "Y", PITCH_PIVOT_OFFSET_Z)
    stack_interface.attach_to_host(group, parent)
    doc.recompute()
    return {
        "group": group,
        "roll_stage": roll,
        "pitch_stage": pitch,
        "printed": printed,
        "hardware": hardware,
        "base": stack_interface.host_print(group),
    }


def set_angles(doc, roll, pitch):
    """Set the two saved native controls; their own expressions bound motion."""
    doc.getObject("OpticalRollStage").Roll = roll
    doc.getObject("OpticalPitchStage").Pitch = pitch
    doc.recompute()
