"""Optional one-piece power platform on the common structural stack interface."""

import functools
import json
import math

import FreeCAD as App
import Part

from gondola.cad import (
    box,
    create_group,
    create_printed_part,
    create_reference,
    set_property,
)
from gondola.contracts.power_options import get_power_module_profile, get_power_plan

from . import purchased_hardware, stack_interface

V = App.Vector
DECK_SIZE_MM = (64.0, 64.0)
DECK_THICKNESS_MM = 2.0
SUPPORT_Z = stack_interface.TOP_BEAM_THICKNESS
DECK_BOTTOM_Z = SUPPORT_Z - DECK_THICKNESS_MM
INSULATION_ALLOWANCE_MM = 1.0
BODY_BOTTOM_Z = SUPPORT_Z + INSULATION_ALLOWANCE_MM
BAY_CENTRES = ((0.0, -14.5), (0.0, 14.5))
TIE_SLOT_CENTRES = tuple((x, y) for x in (-20.0, 20.0) for y in (-14.5, 14.5))
TIE_SLOT_SIZE_MM = (3.0, 8.0)
GENERIC_STACK_PITCHES_MM = (20.0, 30.5)
GENERIC_HOLE_DIAMETER_MM = 2.6
TERMINAL_TRAVEL_MM = 15.0
CONNECTION_HEIGHT_ALLOWANCE_MM = 15.0
TETHER_DIAMETER_MM = 4.0
TETHER_CENTRE_XY = (27.0, 0.0)
TETHER_DEPARTURE_LENGTH_MM = 50.0
TETHER_TIE_CENTRES = ((27.0, -5.0), (27.0, 5.0))
DEFAULT_HOST = "AccessoryEquipmentModule"
DEFAULT_PLAN = "TETHER_DUAL_BEC"


def generic_hole_centres(pitch):
    if pitch not in GENERIC_STACK_PITCHES_MM:
        raise ValueError("Unsupported generic stack pitch")
    radius = pitch / math.sqrt(2)
    return ((-radius, 0), (0, -radius), (radius, 0), (0, radius))


def platform_contract():
    return {
        "optional_only": True,
        "deck_size_mm": (*DECK_SIZE_MM, DECK_THICKNESS_MM),
        "deck_bottom_z_mm": DECK_BOTTOM_Z,
        "support_z_mm": SUPPORT_Z,
        "body_bottom_z_mm": BODY_BOTTOM_Z,
        "insulation_allowance_mm": INSULATION_ALLOWANCE_MM,
        "bay_centres_xy_mm": BAY_CENTRES,
        "tie_slot_centres_xy_mm": TIE_SLOT_CENTRES,
        "tie_slot_size_mm": TIE_SLOT_SIZE_MM,
        "generic_square_patterns_mm": GENERIC_STACK_PITCHES_MM,
        "generic_pattern_rotation_deg": 45.0,
        "generic_hole_diameter_mm": GENERIC_HOLE_DIAMETER_MM,
        "generic_hole_scope": "Project-selected M2 clearance in common 20 and 30.5 mm square spacings, rotated 45 degrees to miss the tower beam. These are not confirmed bolt patterns for either Matek board and do not establish another board's fastener compatibility.",
        "tether_centre_xy_mm": TETHER_CENTRE_XY,
        "tether_diameter_mm": TETHER_DIAMETER_MM,
        "tether_tie_centres_xy_mm": TETHER_TIE_CENTRES,
        "tether_departure_length_mm": TETHER_DEPARTURE_LENGTH_MM,
        "tether_scope": "Only a nominal straight 4 mm departure envelope for 50 mm along local +Z is screened. The single tie pair does not enforce that direction or length. Secure the actual incoming lead to the structural platform before the PCB terminals. Free tether movement, tensile rating, board pigtail bends and an aircraft tether anchor are not qualified.",
        "connection_height_allowance_mm": CONNECTION_HEIGHT_ALLOWANCE_MM,
        "terminal_end_allowance_mm": TERMINAL_TRAVEL_MM,
        "support_scope": "Flat open deck with two tie-equipped bays, no board pockets or invented board holes. One mm nominal insulating support allowance is not measured underside-component clearance or thermal qualification. Position ties clear of hot components, solder and headers after inspecting received boards.",
        "stack_scope": "One optional platform per unoccupied structural host. Do not install over an optical tower or stack platforms on one another. Remove the host from the rail for foot-fastener service; the balloon is not modeled.",
    }


@functools.lru_cache(None)
def platform_shape():
    shape = stack_interface.tower_shape().fuse(
        box(*DECK_SIZE_MM, DECK_THICKNESS_MM, (-32, -32, DECK_BOTTOM_Z))
    )
    for x, y in TIE_SLOT_CENTRES:
        shape = shape.cut(box(3, 8, 5, (x - 1.5, y - 4, -1)))
    for x, y in TETHER_TIE_CENTRES:
        shape = shape.cut(box(3, 4, 5, (x - 1.5, y - 2, -1)))
    for pitch in GENERIC_STACK_PITCHES_MM:
        for x, y in generic_hole_centres(pitch):
            shape = shape.cut(
                Part.makeCylinder(GENERIC_HOLE_DIAMETER_MM / 2, 5, V(x, y, -1))
            )
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Optional power platform is not one valid solid")
    return shape


def local_shapes(plan_key=DEFAULT_PLAN):
    """Return platform, bought envelopes and explicit service allowances."""
    plan = get_power_plan(plan_key)
    if not plan.branches or len(plan.branches) > len(BAY_CENTRES):
        raise ValueError("Power platform requires one or two optional regulators")
    physical = {"PowerPlatform": platform_shape().copy()}
    reserves = {}
    for index, branch in enumerate(plan.branches):
        profile = get_power_module_profile(branch.module_key)
        x, y = BAY_CENTRES[index]
        length, width, height = profile.size_mm
        name = f"PowerModule{index}"
        physical[name] = box(
            length, width, height, (x - length / 2, y - width / 2, BODY_BOTTOM_Z)
        )
        reserves[f"{name}TopReserve"] = box(
            length,
            width,
            CONNECTION_HEIGHT_ALLOWANCE_MM,
            (x - length / 2, y - width / 2, BODY_BOTTOM_Z + height),
        )
        for axis in profile.terminal_axes:
            left = (
                x - length / 2 - TERMINAL_TRAVEL_MM if axis == "-X" else x + length / 2
            )
            reserves[f"{name}{'Negative' if axis == '-X' else 'Positive'}XReserve"] = (
                box(
                    TERMINAL_TRAVEL_MM,
                    width,
                    height + CONNECTION_HEIGHT_ALLOWANCE_MM,
                    (left, y - width / 2, BODY_BOTTOM_Z),
                )
            )
    for index, (x, y) in enumerate(stack_interface.CLAMP_CENTRES):
        for kind, shape, z in (
            (
                "Bolt",
                purchased_hardware.screw_shape(8),
                -stack_interface.TOWER_HEIGHT - stack_interface.DECK_THICKNESS,
            ),
            (
                "Nut",
                purchased_hardware.hex_nut_shape(),
                -stack_interface.TOWER_HEIGHT + stack_interface.FOOT_THICKNESS,
            ),
        ):
            placed = shape.copy()
            placed.translate(V(x, y, z))
            physical[f"PowerFoot{kind}{index}"] = placed
    # This nominal departure allowance is not a physically enforced cable trajectory.
    reserves["TetherDepartureReserve"] = Part.makeCylinder(
        TETHER_DIAMETER_MM / 2,
        TETHER_DEPARTURE_LENGTH_MM,
        V(*TETHER_CENTRE_XY, SUPPORT_Z),
    )
    return physical, reserves


def host_placement(main_doc, host_name):
    if host_name not in stack_interface.MECHANICAL_HOSTS:
        raise ValueError("Unsupported power-platform host")
    host = main_doc.getObject(host_name)
    if host is None:
        raise ValueError("Missing power-platform host")
    optical = main_doc.getObject("OpticalFlowModule")
    if optical is not None and optical.getParentGeoFeatureGroup() == host:
        raise ValueError("Power platform cannot occupy the installed optical host")
    return host.getGlobalPlacement().multiply(
        stack_interface.host_placement(host_name, z=stack_interface.STACK_TOP_Z)
    )


def create_option_document(main_doc, plan_key=DEFAULT_PLAN, host_name=DEFAULT_HOST):
    pose = host_placement(main_doc, host_name)
    physical, reserves = local_shapes(plan_key)
    doc = App.newDocument("GondolaPowerOptions")
    doc.Label = "Optional power platform | separate from battery baseline"
    group = create_group(doc, "PowerOptionModule", "Optional power module")
    group.Placement = pose
    for key, value in (
        ("PowerPlan", plan_key),
        ("StackHostName", host_name),
        ("PowerPlatformContract", json.dumps(platform_contract(), sort_keys=True)),
    ):
        set_property(group, key, value)
    for name, shape in physical.items():
        if name == "PowerPlatform":
            obj = create_printed_part(
                doc,
                group,
                name,
                "OPTIONAL PRINT | one-piece power platform",
                shape,
                App.Rotation(V(1, 0, 0), 180),
                platform_contract()["support_scope"],
            )
        else:
            obj = create_reference(
                doc,
                group,
                name,
                name,
                shape,
                "Optional purchased hardware envelope; not in the default installed BOM",
            )
            if App.GuiUp:
                obj.ViewObject.ShapeColor = (
                    (0.3, 0.45, 0.75)
                    if name.startswith("PowerModule")
                    else (0.86, 0.67, 0.27)
                )
    for name, shape in reserves.items():
        obj = create_reference(
            doc,
            group,
            name,
            name,
            shape,
            "Design allowance only; see platform contract",
        )
        obj.Role = "Clearance"
        obj.Label = "CLEARANCE | " + name
        if App.GuiUp:
            obj.ViewObject.Visibility = False
    doc.recompute()
    return doc
