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
# Keep this height local to the carrier so deck changes carry the sensor with it.
PIVOT_CENTRE = (0.0, 0.0, 19.0)
ANGLE_LIMIT_DEG = 20.0
EAR_RADIUS = 4.0
EAR_THICKNESS = 2.0
UPRIGHT_WIDTH = 8.0
GUSSET_DEPTH = 2.0
GUSSET_TOP_Z = 7.0
PIVOT_HOLE_DIAMETER = 2.2
TRAY_SIZE_MM = (18.0, 12.0)
TRAY_BOTTOM_Z = 4.5
TRAY_TOP_Z = 6.5
ADHESIVE_ALLOWANCE = 1.0
SCREW_LENGTH = fasteners.OPTICAL_PIVOT_SCREW_LENGTH
SCREW_BEARING_START = -EAR_THICKNESS
NUT_START = EAR_THICKNESS - optical_interface.NUT_RECESS_DEPTH
BOLT_TIP = SCREW_BEARING_START + SCREW_LENGTH


def _cylinder(radius, length, origin, axis):
    return Part.makeCylinder(radius, length, V(*origin), V(*axis))


def _finished(shape, name):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Optical mount is not one valid solid: " + name)
    return shape


def upright_shape():
    """Straight transverse ear support, with a short integral root buttress."""
    x, y, z = PIVOT_CENTRE
    bottom = optical_interface.FOOT_THICKNESS
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


def base_shape():
    """Small rectangular carrier foot fused to a straight post and pitch ear."""
    x, y, z = PIVOT_CENTRE
    ear = _cylinder(EAR_RADIUS, EAR_THICKNESS, (x, y - EAR_THICKNESS, z), (0, 1, 0))
    post = upright_shape()
    bore = _cylinder(
        PIVOT_HOLE_DIAMETER / 2,
        2 * EAR_THICKNESS + 2,
        (x, y - EAR_THICKNESS - 1, z),
        (0, 1, 0),
    )
    body = (
        union(
            [
                optical_interface.foot_shape(),
                ear,
                post,
            ]
        )
        .cut(bore)
        .removeSplitter()
    )
    from .edge_blends import fillet_selected, near

    body = fillet_selected(
        body,
        0.5,
        lambda e, b: (
            near(b.XLength, UPRIGHT_WIDTH)
            and near(b.YLength, 0)
            and near(b.ZLength, 0)
            and (
                (
                    near(b.ZMin, optical_interface.FOOT_THICKNESS)
                    and (near(b.YMin, -EAR_THICKNESS) or near(b.YMin, GUSSET_DEPTH))
                )
                or (near(b.YMin, 0) and near(b.ZMin, GUSSET_TOP_Z))
            )
        ),
        3,
        "Optical pedestal and buttress roots",
    )
    return _finished(body, "base")


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
    recess = purchased_hardware.hex_prism(
        optical_interface.NUT_RECESS_AF, optical_interface.NUT_RECESS_DEPTH + 0.1
    )
    recess.rotate(V(), V(1, 0, 0), -90)
    recess.translate(V(0, NUT_START, 0))
    body = union([ear, neck, pad]).cut(bore).cut(recess).removeSplitter()
    from .edge_blends import fillet_selected, near

    body = fillet_selected(
        body,
        0.5,
        lambda e, b: (
            near(b.ZMin, TRAY_BOTTOM_Z)
            and near(b.ZLength, 0)
            and (
                (near(b.XLength, 0) and near(abs(b.XMin), TRAY_SIZE_MM[0] / 2))
                or (near(b.YLength, 0) and near(abs(b.YMin), TRAY_SIZE_MM[1] / 2))
            )
        ),
        4,
        "Optical tray lower outside rim",
    )
    return _finished(body, "sensor tray")


def mount_contract():
    return {
        "mechanism": "Carrier-mounted straight pedestal with one manual pitch-Y friction clamp",
        "adjustment_degrees_of_freedom": 1,
        "pivot_centre_in_module_mm": PIVOT_CENTRE,
        "planning_angle_limit_deg": ANGLE_LIMIT_DEG,
        "axis": "Rail-local Y, transverse to the longitudinal rail",
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
        "integral_base_buttress": {"depth_mm": GUSSET_DEPTH, "top_z_mm": GUSSET_TOP_Z},
        "tray_size_mm": TRAY_SIZE_MM,
        "tray_bottom_z_in_pitch_frame_mm": TRAY_BOTTOM_Z,
        "tray_top_z_in_pitch_frame_mm": TRAY_TOP_Z,
        "nominal_tray_to_fixed_pitch_disc_gap_mm": TRAY_BOTTOM_Z - EAR_RADIUS,
        "adhesive_allowance_mm": ADHESIVE_ALLOWANCE,
        "hardware": "Two kit steel M2x8 button-head screw / M2 hex nut pairs total: one located carrier-foot clamp and one pitch clamp. No washers.",
        "nut_recess": optical_interface.nut_recess_contract(),
        "full_nut_engagement_mm": purchased_hardware.HEX_NUT_HEIGHT,
        "bolt_tip_beyond_nut_mm": BOLT_TIP
        - NUT_START
        - purchased_hardware.HEX_NUT_HEIGHT,
        "assembly": "Print the integral carrier foot/post and sensor tray separately. Insert the integral tongue freely into an existing carrier middle-side slot and fully seat the foot before tightening its M2 pair; finish both 2.2 mm pitch bores for a free M2 screw before clamping the two 2 mm ears with the second pair. Its nut sits in a 0.5 mm tray-ear recess, leaving a 1.5 mm floor, and rotates with the tray. Fit the nut freely and keep both ear faces seated. Do not use screw torque to force an undersized bore.",
        "adjustment": "Centre the rail on the balloon. Support the sensor, loosen the pitch screw while the tray pocket restrains its nut, align downward at flight trim, and hand-snug. No roll correction, self-levelling or operating play. Native limits are planning controls; actual stiffness, holding torque, vibration retention and PA12 creep remain unqualified.",
        "sensor_interface": "Continuous insulating adhesive pad for either MTF-01P or MTF-02P. OEM backside contact, retention and connector/wire fit remain unverified; no invented sensor fixing holes.",
    }


def _pivot_hardware(doc, parent, pitch):
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
        # The keyed nut must follow its tray pocket during manual pitch adjustment.
        if kind == "Nut":
            hardware_parent = pitch
            shape.translate(V(0, axial, 0))
        else:
            hardware_parent = parent
            shape.translate(
                V(PIVOT_CENTRE[0], PIVOT_CENTRE[1] + axial, PIVOT_CENTRE[2])
            )
        objects.append(
            purchased_hardware.add_hardware(
                doc,
                hardware_parent,
                "OpticalPitch" + kind,
                "BUY | manual optical pitch " + kind.lower(),
                shape,
                sku,
                "M2x8 and ordinary M2 nut clamp two 2 mm PA12 ears with a 0.5 mm tray nut recess and 1.5 mm remaining floor. Nominal full 1.6 mm engagement and 2.9 mm tip projection; verify actual hardware, printed fit and angle retention. No washer, bearing or qualified holding-torque claim.",
                source,
                fasteners.KIT_MATERIAL,
            )
        )
    return objects


def build_optical_mount(doc, host, side=optical_interface.DEFAULT_SIDE):
    group = create_group(
        doc,
        "OpticalFlowModule",
        "Optical flow | carrier foot and manual pitch",
    )
    optical_interface.attach_to_host(group, host, side)
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
            "PA12 SLS/MJF compact carrier foot with straight braced post and separate adhesive tray. A rigid shallow tongue locates the foot; two M2x8/M2 nut pairs lock the foot and single pitch joint. Check received print fit, clamp retention, adhesive and optical alignment before use.",
        )
        set_property(obj, "PrintSKU", name)
        set_property(obj, "OpticalMountContract", contract)
        set_property(obj, "HoldingTorqueVerified", False, "App::PropertyBool")
        if name == "OpticalMountBase":
            optical_interface.annotate_interface(obj)
        printed.append(obj)
    hardware = _pivot_hardware(doc, group, pitch) + optical_interface.build_hardware(
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
