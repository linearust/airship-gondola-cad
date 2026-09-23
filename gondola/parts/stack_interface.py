"""Project-standard structural stack, separate from FC holes and soft dampers.

Both rail equipment carriers share the project's diagonal M2 mounting pair.
The optical base integrates two open legs and bolt feet; no separate columns or printed threads.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, box, set_property, union
from gondola.contracts import fasteners
from gondola.contracts.design import (
    STACK_AXIS_LOCATIONS,
    STACK_HOLE_CENTRES,
    STACK_PITCH_MM,
)
from gondola.contracts.hardware import HEX_NUT_SOURCE, STACK_SCREW_SOURCE

from . import purchased_hardware

V = App.Vector
PITCH_MM = STACK_PITCH_MM
HOLE_CENTRES = STACK_HOLE_CENTRES
HOLE_DIAMETER = 2.6
PAD_DIAMETER = 6.5
ARM_WIDTH = 5.0
DECK_THICKNESS = 2.0
HOST_DECK_BOTTOM_Z = 10.2
HOST_SUPPORT_Z = HOST_DECK_BOTTOM_Z + DECK_THICKNESS
TOWER_HEIGHT = 25.0
STACK_TOP_Z = HOST_SUPPORT_Z + TOWER_HEIGHT
FOOT_THICKNESS = 2.0
FOOT_RADIUS = 3.75
FOOT_SLOT_TRAVEL = 0.5
LEG_INNER_OFFSET = 4.0
LEG_OUTER_OFFSET = 8.0
LEG_WIDTH = 6.0
FOOT_SCREW_LENGTH = 8.0
MINIMUM_HEAD_BEARING_DIAMETER = 3.2
SUPPORTED_HOSTS = {
    "BatteryEquipmentModule": "BatteryMount",
    "ElectronicsEquipmentModule": "ElectronicsMount",
}


def interface_contract():
    return {
        "standard": f"Project structural stack: two M2 clearance axes at {STACK_AXIS_LOCATIONS}",
        "industry_standard_claimed": False,
        "axis_spacing_mm": math.sqrt(2) * PITCH_MM,
        "hole_centres_xy_mm": HOLE_CENTRES,
        "hole_diameter_mm": HOLE_DIAMETER,
        "pad_diameter_mm": PAD_DIAMETER,
        "printed_deck_thickness_mm": DECK_THICKNESS,
        "host_support_z_mm": HOST_SUPPORT_Z,
        "integral_tower_height_mm": TOWER_HEIGHT,
        "tower_foot_thickness_mm": FOOT_THICKNESS,
        "foot_slot_radial_travel_each_way_mm": FOOT_SLOT_TRAVEL,
        "tower_leg_section_mm": [LEG_OUTER_OFFSET - LEG_INNER_OFFSET, LEG_WIDTH],
        "tower_attachment": "Two M2x8 button-head screws from below the host and ordinary M2 hex nuts above the slotted feet;4mm host/foot grip, no washers, captive nut fit, blind threads or separate columns. Remove upper nuts to lift the tower; lower-headed bolts remain in the host",
        "minimum_screw_bearing_face_diameter_mm": MINIMUM_HEAD_BEARING_DIAMETER,
        "service": "Remove the two upper nuts and lift the complete optical tower off the lower-headed bolts retained in the host. To replace or transfer those bolts between hosts, remove the carrier from the rail for bench access. Host selection in CAD represents reassembly, not an in-place quick swap.",
        "stack_platform_bottom_z_mm": STACK_TOP_Z,
        "supported_hosts": list(SUPPORTED_HOSTS),
        "load_path": "Carrier pads -> two integral PA12 bolt feet and outward-offset legs -> optical platform. No stack load is routed through FC silicone dampers, PCB or battery.",
        "qualification": "The two short radial foot slots absorb up to +/-0.5mm local hole-spacing mismatch without a close captive-nut fit. Measure printed feet and purchased heads/nuts; screw underside bearing diameter must be at least3.2mm while the complete head stays inside the4.5x2mm clearance envelope. Verify full nut engagement and support, and hand snug while holding the exposed nut. Tower stiffness, clamp/creep strength and cable retention require physical checks; no load/torque qualification is claimed.",
    }


def platform_shape():
    """One diagonal bar connects two pads to the head without a solid board."""
    pieces = []
    for x, y in HOLE_CENTRES:
        arm = box(math.hypot(x, y), ARM_WIDTH, DECK_THICKNESS, (0, -ARM_WIDTH / 2, 0))
        arm.rotate(V(), V(0, 0, 1), math.degrees(math.atan2(y, x)))
        pieces.extend(
            [arm, Part.makeCylinder(PAD_DIAMETER / 2, DECK_THICKNESS, V(x, y, 0))]
        )
    shape = union(pieces)
    for x, y in HOLE_CENTRES:
        shape = shape.cut(
            Part.makeCylinder(HOLE_DIAMETER / 2, DECK_THICKNESS + 2, V(x, y, -1))
        )
    return shape.removeSplitter()


def add_host_interface(shape):
    platform = platform_shape()
    platform.translate(V(0, 0, HOST_DECK_BOTTOM_Z))
    combined = shape.fuse(platform)
    for x, y in HOLE_CENTRES:
        combined = combined.cut(
            Part.makeCylinder(
                HOLE_DIAMETER / 2, DECK_THICKNESS + 2, V(x, y, HOST_DECK_BOTTOM_Z - 1)
            )
        )
    return combined.removeSplitter()


def annotate_interface(obj):
    set_property(
        obj, "StackInterfaceContract", json.dumps(interface_contract(), sort_keys=True)
    )
    set_property(obj, "StackFitVerified", False, "App::PropertyBool")


def attach_to_host(group, host):
    """Represent bench reassembly on another host; never move single pieces."""
    if host.Name not in SUPPORTED_HOSTS or host.Document != group.Document:
        raise ValueError(
            "Optical stack requires a supported carrier in the same document"
        )
    old = group.getParentGeoFeatureGroup()
    if old is not None and old != host:
        old.removeObject(group)
    host.addObject(group)
    group.Placement = App.Placement(V(0, 0, STACK_TOP_Z), App.Rotation())
    set_property(group, "StackHostName", host.Name)
    annotate_interface(group)
    group.Document.recompute()


def tower_shape():
    """One open diagonal platform with outward legs and accessible slotted feet."""
    pieces = []
    for x, y in HOLE_CENTRES:
        radius = math.hypot(x, y)
        angle = math.degrees(math.atan2(y, x))
        arm = box(
            radius + LEG_OUTER_OFFSET, LEG_WIDTH, DECK_THICKNESS, (0, -LEG_WIDTH / 2, 0)
        )
        leg = box(
            LEG_OUTER_OFFSET - LEG_INNER_OFFSET,
            LEG_WIDTH,
            TOWER_HEIGHT,
            (radius + LEG_INNER_OFFSET, -LEG_WIDTH / 2, -TOWER_HEIGHT),
        )
        foot = union(
            [
                Part.makeCylinder(
                    FOOT_RADIUS, FOOT_THICKNESS, V(radius, 0, -TOWER_HEIGHT)
                ),
                box(
                    LEG_OUTER_OFFSET,
                    LEG_WIDTH,
                    FOOT_THICKNESS,
                    (radius, -LEG_WIDTH / 2, -TOWER_HEIGHT),
                ),
            ]
        )
        slot = union(
            [
                Part.makeCylinder(
                    HOLE_DIAMETER / 2,
                    FOOT_THICKNESS + 2,
                    V(radius + offset, 0, -TOWER_HEIGHT - 1),
                )
                for offset in (-FOOT_SLOT_TRAVEL, FOOT_SLOT_TRAVEL)
            ]
            + [
                box(
                    2 * FOOT_SLOT_TRAVEL,
                    HOLE_DIAMETER,
                    FOOT_THICKNESS + 2,
                    (radius - FOOT_SLOT_TRAVEL, -HOLE_DIAMETER / 2, -TOWER_HEIGHT - 1),
                )
            ]
        )
        piece = union([arm, leg, foot.cut(slot)])
        piece.rotate(V(), V(0, 0, 1), angle)
        pieces.append(piece)
    return union(pieces).removeSplitter()


def is_removable_head_part(obj, stack):
    """Remove the tower and upper nuts; lower-headed bolts stay in the host."""
    return belongs_to_group(obj, stack) and not obj.Name.startswith(
        "OpticalStackFootBolt"
    )


def build_stack_hardware(doc, group):
    """Open foot through-joints, relative to the optical platform bottom face."""
    hardware = []
    common = (
        "Structural optical tower only; never print. Screw enters from below the host; nut seats on the slotted foot. Require at least3.2mm actual screw underside bearing diameter. Two2mm PA12 plates give4mm "
        "nominal grip, followed by the full1.6mm M2 nut and2.4mm screw projection. "
        "Both plates0.3mm thicker still leave1.8mm projection before screw/nut "
        "tolerances. Hold the exposed nut and hand snug after verifying actual "
        "parts, support and retention; no qualified tightening torque. "
    )
    for index, (x, y) in enumerate(HOLE_CENTRES):
        bolt = purchased_hardware.add_hardware(
            doc,
            group,
            f"OpticalStackFootBolt{index}",
            "BUY | M2x8 kit button-head screw | optical tower foot",
            purchased_hardware.screw_shape(FOOT_SCREW_LENGTH),
            "M2X8_BUTTON_HEAD",
            common + fasteners.HEAD_ENVELOPE_NOTE,
            STACK_SCREW_SOURCE,
            fasteners.KIT_MATERIAL,
        )
        bolt.Placement.Base = V(x, y, -TOWER_HEIGHT - DECK_THICKNESS)
        set_property(bolt, "StackEnd", "Foot")
        nut = purchased_hardware.add_hardware(
            doc,
            group,
            f"OpticalStackFootNut{index}",
            "BUY | M2 kit hex nut | optical tower foot",
            purchased_hardware.hex_nut_shape(),
            "M2_HEX_NUT",
            common,
            HEX_NUT_SOURCE,
            fasteners.KIT_MATERIAL,
        )
        nut.Placement.Base = V(x, y, -TOWER_HEIGHT + FOOT_THICKNESS)
        set_property(nut, "StackEnd", "Foot")
        hardware.extend((bolt, nut))
    return hardware
