"""Project-standard structural stack, separate from FC holes and soft dampers.

Both rail equipment carriers use the same two diagonal M2 axes of a 40 mm square. Purchased
25 mm nylon spacers support one interchangeable optical head; no printed posts.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import box, set_property, union

from . import metric_hardware as metric

V = App.Vector
PITCH_MM = 40.0
HOLE_CENTRES = tuple((sign * PITCH_MM / 2, sign * PITCH_MM / 2) for sign in (-1, 1))
HOLE_DIAMETER = 2.6
PAD_DIAMETER = 6.5
ARM_WIDTH = 5.0
DECK_THICKNESS = 2.0
HOST_DECK_BOTTOM_Z = 10.2
HOST_SUPPORT_Z = HOST_DECK_BOTTOM_Z + DECK_THICKNESS
SPACER_LENGTH = metric.STACK_SPACER_LENGTH
STACK_TOP_Z = HOST_SUPPORT_Z + SPACER_LENGTH
SUPPORTED_HOSTS = {
    "BatteryEquipmentModule": "BatteryMount",
    "ElectronicsEquipmentModule": "ElectronicsMount",
}


def interface_contract():
    return {
        "standard": "Project structural stack: two M2 clearance axes at (-20,-20) and (20,20) mm",
        "industry_standard_claimed": False,
        "axis_spacing_mm": math.sqrt(2) * PITCH_MM,
        "hole_centres_xy_mm": HOLE_CENTRES,
        "hole_diameter_mm": HOLE_DIAMETER,
        "pad_diameter_mm": PAD_DIAMETER,
        "printed_deck_thickness_mm": DECK_THICKNESS,
        "host_support_z_mm": HOST_SUPPORT_Z,
        "purchased_spacer_length_mm": SPACER_LENGTH,
        "stack_platform_bottom_z_mm": STACK_TOP_Z,
        "supported_hosts": list(SUPPORTED_HOSTS),
        "load_path": "Carrier pads -> two bought M2 female/female PA66 spacers -> optical platform. No stack load is routed through FC silicone dampers, PCB or battery.",
        "qualification": "Verify purchased spacer dimensions, usable thread depth>=3.6mm, thread engagement, PA66 clamp/creep strength and retention with actual cables. 4mm REF drawing depth is not a guaranteed minimum. No load/torque qualification is claimed.",
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
    """Reparent the complete kit at the shared datum; never move single pieces."""
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


def build_stack_hardware(doc, group):
    """All coordinates are relative to the bottom face of the optical platform."""
    hardware = []
    common = "Structural stack only; never print. Hand snug after verifying actual parts, thread depth/engagement and retention; no qualified tightening torque."
    for index, (x, y) in enumerate(HOLE_CENTRES):
        spacer = metric.add_hardware(
            doc,
            group,
            f"OpticalStackSpacer{index}",
            "BUY | M2 F/F PA66 AF4 x25mm spacer",
            metric.spacer_shape(),
            "M2_FF_PA66_AF4_L25",
            common,
            metric.STACK_SPACER_SOURCE,
            "Nylon PA66",
        )
        set_property(spacer, "StackEnd", "Spacer")
        spacer.Placement.Base = V(x, y, -SPACER_LENGTH)
        hardware.append(spacer)
        for end, bearing_z, direction in (
            ("Lower", -SPACER_LENGTH - DECK_THICKNESS, 1),
            ("Upper", DECK_THICKNESS, -1),
        ):
            rotation = App.Rotation(V(0, 0, 1), V(0, 0, direction))
            bolt = metric.add_hardware(
                doc,
                group,
                f"OpticalStack{end}Bolt{index}",
                "BUY | M2x5 PA66 slotted pan screw",
                metric.stack_screw_shape(),
                "M2X5_PA66_PAN_HEAD",
                common
                + " Nominal thread entry3.0mm through printed2mm plate without washers; actual printed thickness, screw tolerance and blind depth must be checked.",
                metric.STACK_SCREW_SOURCE,
                "Nylon PA66",
            )
            bolt.Placement = App.Placement(V(x, y, bearing_z), rotation)
            set_property(bolt, "StackEnd", end)
            hardware.append(bolt)
    return hardware
