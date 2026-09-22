"""Standard-stack, manually clamped roll/pitch optical sensor support.

The three PA12 parts print separately. Two ordinary M2 fastener stacks clamp
plain contact faces; the native angle limits are planning controls, not physical
stops, self-levelling, or a qualified friction/holding-torque specification.
"""

import json

import FreeCAD as App
import Part

from gondola.cad import box, create_group, create_printed_part, set_property, union
from gondola.contracts import fasteners
from gondola.contracts.design import STACK_AXIS_LOCATIONS
from gondola.contracts.hardware import HEX_NUT_SOURCE, STACK_SCREW_SOURCE

from . import purchased_hardware, stack_interface

V = App.Vector
ROLL_PIVOT_Z = 8.0
PITCH_PIVOT_OFFSET_Z = 10.0
ANGLE_LIMIT_DEG = 20.0
EAR_RADIUS = 3.5
EAR_THICKNESS = 1.5
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


def base_shape():
    """Common diagonal stack bar and a 1.5 mm negative-X roll ear."""
    ear = _cylinder(
        EAR_RADIUS, EAR_THICKNESS, (-EAR_THICKNESS, 0, ROLL_PIVOT_Z), (1, 0, 0)
    )
    post = box(
        EAR_THICKNESS,
        2 * EAR_RADIUS,
        ROLL_PIVOT_Z - stack_interface.DECK_THICKNESS,
        (-EAR_THICKNESS, -EAR_RADIUS, stack_interface.DECK_THICKNESS),
    )
    bore = _cylinder(
        PIVOT_HOLE_DIAMETER / 2,
        2 * EAR_THICKNESS + 2,
        (-EAR_THICKNESS - 1, 0, ROLL_PIVOT_Z),
        (1, 0, 0),
    )
    return _finished(
        union([stack_interface.platform_shape(), ear, post]).cut(bore), "base"
    )


def roll_bracket_shape():
    """Orthogonal ears joined by a 1.5 mm square post, in the roll frame."""
    first = _cylinder(EAR_RADIUS, EAR_THICKNESS, (0, 0, 0), (1, 0, 0))
    # Keep the post in the second ear's plane. Extending it behind that plane
    # would obstruct the purchased second-axis screw head.
    post = box(
        EAR_THICKNESS,
        EAR_THICKNESS,
        PITCH_PIVOT_OFFSET_Z + EAR_THICKNESS,
        (0, -EAR_THICKNESS, -EAR_THICKNESS),
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
    """Continuous adhesive pad and one 1.5 mm pitch ear, in the pitch frame."""
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
        "integral_common_rail_shoe": False,
        "standard_stack_interface": f"Two diagonal M2 clearance axes at {STACK_AXIS_LOCATIONS}, shared open bar; supported by two purchased columns independently of the FC dampers",
        "ear_diameter_mm": 2 * EAR_RADIUS,
        "ear_thickness_mm": EAR_THICKNESS,
        "pivot_clearance_hole_diameter_mm": PIVOT_HOLE_DIAMETER,
        "nominal_ear_radial_wall_mm": EAR_RADIUS - PIVOT_HOLE_DIAMETER / 2,
        "post_section_mm": [EAR_THICKNESS, EAR_THICKNESS],
        "tray_size_mm": list(TRAY_SIZE_MM),
        "tray_bottom_z_in_pitch_frame_mm": TRAY_BOTTOM_Z,
        "tray_top_z_in_pitch_frame_mm": TRAY_TOP_Z,
        "nominal_tray_to_fixed_pitch_disc_gap_mm": TRAY_BOTTOM_Z - EAR_RADIUS,
        "adhesive_allowance_mm": ADHESIVE_ALLOWANCE,
        "hardware_per_axis": "Kit steel M2x6 button-head screw and M2 hex nut; no washers. Unmeasured head uses a design clearance envelope.",
        "full_nut_engagement_mm": purchased_hardware.HEX_NUT_HEIGHT,
        "bolt_tip_beyond_nut_mm": BOLT_TIP
        - NUT_START
        - purchased_hardware.HEX_NUT_HEIGHT,
        "minimum_nominal_wall_mm": EAR_THICKNESS,
        "fastener_fit_scope": "Nominal screw projection is 1.4mm beyond a 1.6mm nut. Two ears each 0.3mm thicker leave 0.8mm, before screw-length tolerance. Measure printed thickness, kit head and screw/nut before use; full physical engagement is unverified.",
        "assembly": "Print all three parts separately; plain nominal contact faces touch when the bought fasteners clamp them. No printed thread, bearing or screw.",
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
            "M2X6_BUTTON_HEAD",
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
            "One kit steel M2x6 button-head screw and M2 hex nut directly clamp two separately printed1.5mm ears, without washers. Nominal full1.6mm nut engagement and1.4mm tip projection; actual screw length, head envelope and both printed thicknesses must be checked. Manual friction adjustment, not a qualified torque, creep life or holding-load claim.",
            source,
            material,
        )
        objects.append(obj)
    return objects


def build_optical_mount(doc, parent):
    group = create_group(
        doc,
        "OpticalFlowModule",
        "Optical flow | standard-stack manual roll/pitch mount",
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
    for parent, name, shape in (
        (group, "OpticalMountBase", base_shape()),
        (roll, "OpticalRollBracket", roll_bracket_shape()),
        (pitch, "OpticalSensorTray", sensor_tray_shape()),
    ):
        obj = create_printed_part(
            doc,
            parent,
            name,
            "PRINT | " + name,
            shape,
            App.Rotation(),
            "PA12 SLS/MJF, printed separately. Plain1.5mm friction ears and post with kit steel M2x6 screws and hex nuts, no washers, printed threads or physical stops. Verify printed thickness, screw/head dimensions, engagement, actual fit, stiffness, adhesive contact and angle retention before use.",
        )
        set_property(obj, "PrintSKU", name)
        set_property(obj, "OpticalMountContract", contract)
        set_property(obj, "PrintProcess", "PA12 SLS or MJF")
        set_property(obj, "HoldingTorqueVerified", False, "App::PropertyBool")
        if name == "OpticalMountBase":
            stack_interface.annotate_interface(obj)
        printed.append(obj)
    hardware = _pivot_hardware(doc, group, "OpticalRoll", "X", ROLL_PIVOT_Z)
    hardware += _pivot_hardware(doc, roll, "OpticalPitch", "Y", PITCH_PIVOT_OFFSET_Z)
    doc.recompute()
    return {
        "group": group,
        "roll_stage": roll,
        "pitch_stage": pitch,
        "printed": printed,
        "hardware": hardware,
        "base": printed[0],
    }


def set_angles(doc, roll, pitch):
    """Set the two saved native controls; their own expressions bound motion."""
    doc.getObject("OpticalRollStage").Roll = roll
    doc.getObject("OpticalPitchStage").Pitch = pitch
    doc.recompute()
