"""Shared optical tray: manual-pitch pedestal or fixed direct rail attachment.

The mount is placed along the balloon bottom centreline; the one transverse
axis corrects longitudinal curvature. This is not self-levelling or actuated.
"""

import json

import FreeCAD as App
import Part

from gondola.cad import box, create_group, create_printed_part, set_property, union
from gondola.contracts import fasteners
from gondola.contracts.hardware import HEX_NUT_SOURCE, STACK_SCREW_SOURCE
from gondola.contracts.optical_attachment import (
    TRAY_RAIL_SHOE_OFFSET,
    pivot_z,
    resolve_mount_mode,
)

from . import optical_interface, purchased_hardware, rail

V = App.Vector
ANGLE_LIMIT_DEG = 20.0
EAR_RADIUS = 4.0
EAR_THICKNESS = 2.0
FIXED_EAR_THICKNESS = 2.0
UPRIGHT_WIDTH = 8.0
GUSSET_DEPTH = 2.0
GUSSET_HEIGHT = 5.0
PIVOT_HOLE_DIAMETER = 2.2
TRAY_SIZE_MM = (18.0, 12.0)
TRAY_CORNER_RADIUS = 1.0
TRAY_BOTTOM_Z = 8.5
TRAY_TOP_Z = 10.5
ADHESIVE_ALLOWANCE = 1.0
SCREW_LENGTH = fasteners.OPTICAL_PIVOT_SCREW_LENGTH
SCREW_BEARING_START = -FIXED_EAR_THICKNESS
NUT_START = EAR_THICKNESS - optical_interface.NUT_RECESS_DEPTH
BOLT_TIP = SCREW_BEARING_START + SCREW_LENGTH


def _cylinder(radius, length, origin, axis):
    return Part.makeCylinder(radius, length, V(*origin), V(*axis))


def _finished(shape, name):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Optical mount is not one valid solid: " + name)
    return shape


def pivot_centre(mode="carrier"):
    """Tray origin in its module; the rail mode has no adjustable joint."""
    if resolve_mount_mode(mode) == "rail":
        return tuple(-v for v in TRAY_RAIL_SHOE_OFFSET)
    return (0.0, 0.0, pivot_z(mode))


def angle_limit_deg(mode="carrier"):
    return 0.0 if resolve_mount_mode(mode) == "rail" else ANGLE_LIMIT_DEG


def base_top_z(mode="carrier"):
    if resolve_mount_mode(mode) != "carrier":
        raise ValueError("Direct rail mode installs the upper tray only")
    return optical_interface.FOOT_THICKNESS


def gusset_depth(mode="carrier"):
    base_top_z(mode)
    return GUSSET_DEPTH


def upright_shape(mode="carrier"):
    """Straight transverse ear support, with a short integral root buttress."""
    x, y, z = pivot_centre(mode)
    bottom = base_top_z(mode)
    left = x - UPRIGHT_WIDTH / 2
    post = box(
        UPRIGHT_WIDTH,
        FIXED_EAR_THICKNESS,
        z - bottom,
        (left, y - FIXED_EAR_THICKNESS, bottom),
    )
    points = [
        V(left, y, bottom),
        V(left, y + gusset_depth(mode), bottom),
        V(left, y, bottom + GUSSET_HEIGHT),
    ]
    buttress = Part.Face(Part.makePolygon(points + [points[0]])).extrude(
        V(UPRIGHT_WIDTH, 0, 0)
    )
    return union([post, buttress]).removeSplitter()


def base_shape(mode="carrier"):
    """Original carrier foot/post geometry; omitted in direct rail mode."""
    mode = resolve_mount_mode(mode)
    x, y, z = pivot_centre(mode)
    bottom = base_top_z(mode)
    ear = _cylinder(
        EAR_RADIUS, FIXED_EAR_THICKNESS, (x, y - FIXED_EAR_THICKNESS, z), (0, 1, 0)
    )
    post = upright_shape(mode)
    bore = _cylinder(
        PIVOT_HOLE_DIAMETER / 2,
        FIXED_EAR_THICKNESS + EAR_THICKNESS + 2,
        (x, y - FIXED_EAR_THICKNESS - 1, z),
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
                    near(b.ZMin, bottom)
                    and (
                        near(b.YMin, -FIXED_EAR_THICKNESS)
                        or near(b.YMin, gusset_depth(mode))
                    )
                )
                or (near(b.YMin, 0) and near(b.ZMin, bottom + GUSSET_HEIGHT))
            )
        ),
        3,
        "Optical pedestal and buttress roots",
    )
    return _finished(body, "base")


def sensor_tray_shape():
    """Continuous adhesive pad and one pitch ear, without invented sensor holes."""
    from .edge_blends import fillet_selected, near

    ear = _cylinder(EAR_RADIUS, EAR_THICKNESS, (0, 0, 0), (0, 1, 0))
    neck = box(4, EAR_THICKNESS, TRAY_BOTTOM_Z, (-2, 0, 0))
    pad = box(
        *TRAY_SIZE_MM,
        TRAY_TOP_Z - TRAY_BOTTOM_Z,
        (-TRAY_SIZE_MM[0] / 2, -TRAY_SIZE_MM[1] / 2, TRAY_BOTTOM_Z),
    )
    pad = fillet_selected(
        pad,
        TRAY_CORNER_RADIUS,
        lambda e, b: near(b.ZLength, TRAY_TOP_Z - TRAY_BOTTOM_Z),
        4,
        "Optical tray plan corners",
    )
    bore = _cylinder(PIVOT_HOLE_DIAMETER / 2, 4, (0, -1, 0), (0, 1, 0))
    recess = purchased_hardware.hex_prism(
        optical_interface.NUT_RECESS_AF, optical_interface.NUT_RECESS_DEPTH + 0.1
    )
    recess.rotate(V(), V(1, 0, 0), -90)
    recess.translate(V(0, NUT_START, 0))
    body = union([ear, neck, pad]).cut(bore).cut(recess).removeSplitter()
    body = fillet_selected(
        body,
        0.5,
        lambda e, b: (
            near(b.ZMin, TRAY_BOTTOM_Z)
            and near(b.ZLength, 0)
            and (
                near(abs(b.XMin), TRAY_SIZE_MM[0] / 2)
                or near(abs(b.XMax), TRAY_SIZE_MM[0] / 2)
                or near(abs(b.YMin), TRAY_SIZE_MM[1] / 2)
                or near(abs(b.YMax), TRAY_SIZE_MM[1] / 2)
            )
        ),
        8,
        "Optical tray lower outside rim",
    )
    shoe = rail.mount_base_shape()
    shoe.translate(V(*TRAY_RAIL_SHOE_OFFSET))
    bridge = box(10, 2, 4, (-2, 0, 4.5))
    return _finished(union([body, shoe, bridge]), "sensor tray")


def rail_mounted_tray_shape():
    """The same tray in canonical shoe coordinates, including unused pitch ear."""
    shape = sensor_tray_shape()
    shape.translate(V(*pivot_centre("rail")))
    return shape


def mount_contract(mode="carrier"):
    mode = resolve_mount_mode(mode)
    rail_mounted = mode == "rail"
    return {
        "mechanism": "Fixed direct rail tray"
        if rail_mounted
        else "Original carrier pedestal with one manual pitch-Y clamp",
        "attachment_mode": mode,
        "base_selection": "Use the same upper tray in both modes. Default carrier mode retains the original lower pedestal. Direct rail mode omits that pedestal and both M2 pairs; attach the upper tray with its integral standard M3 rail shoe. Rebuild assembly/BOM when switching modes.",
        "adjustment_degrees_of_freedom": 0 if rail_mounted else 1,
        "tray_origin_in_module_mm": pivot_centre(mode),
        "pivot_centre_in_module_mm": None if rail_mounted else pivot_centre(mode),
        "planning_angle_limit_deg": angle_limit_deg(mode),
        "axis": None
        if rail_mounted
        else "Rail-local Y, transverse to the longitudinal rail",
        "physical_angle_stops_modeled": False,
        "self_levelling": False,
        "holding_torque_verified": False,
        "integral_common_rail_shoe": True,
        "rail_shoe_offset_in_tray_mm": TRAY_RAIL_SHOE_OFFSET,
        "attachment_interface": optical_interface.interface_contract(mode),
        "ear_diameter_mm": 2 * EAR_RADIUS,
        "ear_thickness_mm": EAR_THICKNESS,
        "fixed_ear_thickness_mm": FIXED_EAR_THICKNESS,
        "pivot_clearance_hole_diameter_mm": PIVOT_HOLE_DIAMETER,
        "nominal_ear_radial_wall_mm": EAR_RADIUS - PIVOT_HOLE_DIAMETER / 2,
        "upright_section_mm": (UPRIGHT_WIDTH, FIXED_EAR_THICKNESS),
        "integral_base_buttress": {
            "depth_mm": GUSSET_DEPTH,
            "top_z_mm": base_top_z() + GUSSET_HEIGHT,
            "installed": not rail_mounted,
        },
        "tray_size_mm": TRAY_SIZE_MM,
        "tray_plan_corner_radius_mm": TRAY_CORNER_RADIUS,
        "tray_bottom_z_in_pitch_frame_mm": TRAY_BOTTOM_Z,
        "tray_top_z_in_pitch_frame_mm": TRAY_TOP_Z,
        "nominal_tray_to_fixed_pitch_disc_gap_mm": TRAY_BOTTOM_Z - EAR_RADIUS,
        "adhesive_allowance_mm": ADHESIVE_ALLOWANCE,
        "hardware": "One standard M3x10 rail pair only; no pedestal or M2 hardware. No washers."
        if rail_mounted
        else "Two M2x8 button-head screw / ordinary M2 nut pairs: carrier-foot clamp and pitch clamp. No washers.",
        "nut_recess": optical_interface.nut_recess_contract(),
        "full_nut_engagement_mm": None
        if rail_mounted
        else purchased_hardware.HEX_NUT_HEIGHT,
        "bolt_tip_beyond_nut_mm": None
        if rail_mounted
        else BOLT_TIP - NUT_START - purchased_hardware.HEX_NUT_HEIGHT,
        "assembly": "Carrier mode: retain the original lower pedestal and install the extended upper tray separately. Finish both 2.2 mm pitch bores for a free M2 screw through the two 2 mm ears. The nut sits in a 0.5 mm tray-ear recess with a 1.5 mm floor and follows the tray. Fit nuts freely; keep pitch faces seated and do not force undersized bores with screw torque.",
        "adjustment": "Direct rail mode is fixed at zero pitch; use the stacked configuration when local curvature needs correction. In carrier mode centre the rail on the balloon. Support the sensor, loosen the pitch screw while the tray pocket restrains its nut, align downward at flight trim, and hand-snug. No roll correction, self-levelling or operating play. Native limits are planning controls; actual stiffness, holding torque, vibration retention and PA12 creep remain unqualified.",
        "sensor_interface": "Continuous insulating adhesive pad for either MTF-01P or MTF-02P. OEM backside contact, retention and connector/wire fit remain unverified; no invented sensor fixing holes.",
    }


def _pivot_hardware(doc, parent, pitch, mode="carrier"):
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
                V(
                    pivot_centre(mode)[0],
                    pivot_centre(mode)[1] + axial,
                    pivot_centre(mode)[2],
                )
            )
        objects.append(
            purchased_hardware.add_hardware(
                doc,
                hardware_parent,
                "OpticalPitch" + kind,
                "BUY | manual optical pitch " + kind.lower(),
                shape,
                sku,
                "M2x8 and ordinary M2 nut clamp two 2 mm ears with a 0.5 mm tray nut recess and 1.5 mm remaining floor. Nominal full 1.6 mm engagement and 2.9 mm tip projection; verify actual hardware, printed fit and angle retention. No washer, bearing or qualified holding-torque claim.",
                source,
                fasteners.KIT_MATERIAL,
            )
        )
    return objects


def build_optical_mount(
    doc, host=None, side=optical_interface.DEFAULT_SIDE, *, mode=None
):
    mode = resolve_mount_mode("carrier" if mode is None and host is not None else mode)
    if mode == "rail" and host is not None:
        raise ValueError("A direct optical rail mount cannot also have a carrier host")
    if mode == "carrier" and host is None:
        raise ValueError("A carrier optical mount requires its host")
    group = create_group(
        doc,
        "OpticalFlowModule",
        "Optical flow | "
        + ("stacked manual pitch" if mode == "carrier" else "fixed direct rail tray"),
    )
    set_property(group, "OpticalAttachmentMode", mode)
    group.setEditorMode("OpticalAttachmentMode", 1)
    if mode == "carrier":
        optical_interface.attach_to_host(group, host, side)
    contract = json.dumps(mount_contract(mode), sort_keys=True)
    set_property(group, "OpticalMountContract", contract)
    set_property(
        group,
        "AdjustmentControls",
        "OpticalPitchStage.Pitch; one manually clamped transverse axis, no roll stage."
        if mode == "carrier"
        else "Fixed direct rail tray; zero pitch DOF.",
    )
    set_property(group, "HoldingTorqueVerified", False, "App::PropertyBool")
    set_property(group, "SelfLevelling", False, "App::PropertyBool")
    optical_interface.annotate_interface(group, mode)
    pitch = create_group(
        doc,
        "OpticalPitchStage",
        "Manual pitch | Y axis"
        if mode == "carrier"
        else "Fixed tray frame | no pitch DOF",
    )
    group.addObject(pitch)
    pitch.Placement = App.Placement(V(*pivot_centre(mode)), App.Rotation(V(0, 1, 0), 1))
    for key, value in (
        ("Pitch", 0),
        ("MinimumAngle", -angle_limit_deg(mode)),
        ("MaximumAngle", angle_limit_deg(mode)),
    ):
        set_property(pitch, key, value, "App::PropertyAngle", "Manual adjustment")
    pitch.setEditorMode("MinimumAngle", 1)
    pitch.setEditorMode("MaximumAngle", 1)
    if mode == "rail":
        pitch.setEditorMode("Pitch", 1)
    pitch.setExpression(
        "Placement.Rotation.Angle", "min(MaximumAngle; max(MinimumAngle; Pitch))"
    )
    printed = []
    parts = [(pitch, "OpticalSensorTray", sensor_tray_shape())]
    if mode == "carrier":
        parts.insert(0, (group, "OpticalMountBase", base_shape()))
    for part_parent, name, shape in parts:
        obj = create_printed_part(
            doc,
            part_parent,
            name,
            "PRINT | " + name,
            shape,
            App.Rotation(),
            "PA12 SLS/MJF optical head: original carrier pedestal and extended dual-interface upper tray. Direct rail mode uses the same tray alone at a fixed angle. Qualify printed fit, retention, adhesive and pointing. "
            + mount_contract(mode)["hardware"],
        )
        set_property(
            obj,
            "PrintSKU",
            "OpticalCarrierBase" if name == "OpticalMountBase" else name,
        )
        set_property(obj, "OpticalMountContract", contract)
        set_property(obj, "HoldingTorqueVerified", False, "App::PropertyBool")
        if name == "OpticalMountBase":
            optical_interface.annotate_interface(obj, mode)
        printed.append(obj)
    hardware = []
    if mode == "carrier":
        hardware = _pivot_hardware(doc, group, pitch, mode)
        hardware += optical_interface.build_hardware(doc, group)
    doc.recompute()
    return {
        "group": group,
        "pitch_stage": pitch,
        "printed": printed,
        "hardware": hardware,
        "base": printed[0] if mode == "carrier" else None,
    }


def set_pitch(doc, pitch):
    """Set the one saved native control; its own expression bounds motion."""
    mode = doc.getObject("OpticalFlowModule").OpticalAttachmentMode
    if mode == "rail" and abs(pitch) > 1e-9:
        raise ValueError("Direct rail tray has no pitch adjustment")
    doc.getObject("OpticalPitchStage").Pitch = pitch
    doc.recompute()
