"""Optional one-piece power platform on the common structural stack interface."""

import functools
import json

import FreeCAD as App
import Part

from gondola.cad import (
    box,
    create_group,
    create_printed_part,
    create_reference,
    set_property,
)
from gondola.contracts.power_options import (
    DEFAULT_OPTIONAL_POWER_PLAN_KEY,
    get_power_module_profile,
    get_power_plan,
)

from . import equipment_mounts as mounts
from . import mounting_plate, mounting_slots, purchased_hardware, stack_interface

V = App.Vector
DECK_SIZE_MM = mounting_plate.SIZE_MM
DECK_THICKNESS_MM = mounting_plate.THICKNESS_MM
SUPPORT_Z = stack_interface.TOP_BEAM_THICKNESS
DECK_BOTTOM_Z = SUPPORT_Z - DECK_THICKNESS_MM
INSULATION_ALLOWANCE_MM = 1.0
BODY_BOTTOM_Z = SUPPORT_Z + INSULATION_ALLOWANCE_MM
BAY_CENTRES = ((0.0, -13.0), (0.0, 13.0))
TERMINAL_TRAVEL_MM = 15.0
CONNECTION_HEIGHT_ALLOWANCE_MM = 15.0
DEFAULT_HOST = "AccessoryEquipmentModule"
DEFAULT_PLAN = DEFAULT_OPTIONAL_POWER_PLAN_KEY


def standard_slot_rows():
    return mounts.standard_slot_rows("electronics")


def platform_contract():
    return {
        "optional_only": True,
        "common_plate": mounts.common_plate_contract(),
        "carrier_attachment": stack_interface.interface_contract(),
        "expansion_mounting": mounts.expansion_contract(),
        "deck_size_mm": (*DECK_SIZE_MM, DECK_THICKNESS_MM),
        "deck_bottom_z_mm": DECK_BOTTOM_Z,
        "support_z_mm": SUPPORT_Z,
        "body_bottom_z_mm": BODY_BOTTOM_Z,
        "insulation_allowance_mm": INSULATION_ALLOWANCE_MM,
        "bay_centres_xy_mm": BAY_CENTRES,
        "standard_mounting": mounting_slots.contract(),
        "tether_scope": "No dedicated tether hole, guide or constrained cable route. Wrap existing structure with suitable straps and secure the incoming lead before the PCB terminals. Actual tether routing, strain relief, loads and clearance from moving propulsors are unverified and must be established for the installed cable; no arbitrary straight cable envelope is certified.",
        "connection_height_allowance_mm": CONNECTION_HEIGHT_ALLOWANCE_MM,
        "terminal_end_allowance_mm": TERMINAL_TRAVEL_MM,
        "support_scope": "Flat open deck with two board regions, no dedicated tie slots, board pockets or invented board holes. Use suitable adhesive or wrap the existing structure with a removable strap. One mm nominal insulating support allowance is not measured underside-component clearance or thermal qualification. Position ties clear of hot components, solder and headers after inspecting received boards.",
        "stack_scope": "One optional platform per unoccupied structural host. Do not occupy the installed optical head host or stack platforms on one another. Remove the host from the rail for foot-fastener service; the balloon is not modeled.",
    }


@functools.lru_cache(None)
def platform_shape():
    shape = stack_interface.tower_shape().fuse(mounting_plate.shape(DECK_BOTTOM_Z))
    for hole in mounting_plate.cutters(-1, 5):
        shape = shape.cut(hole)
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Optional power platform is not one valid solid")
    return shape


@functools.lru_cache(None)
def _attachment_templates():
    bottom = -stack_interface.TOWER_HEIGHT - stack_interface.DECK_THICKNESS
    depth = stack_interface.DECK_THICKNESS
    common_deck = mounting_plate.shape(bottom)
    return tuple(
        (
            stack_interface.foot_shape(index, bottom=bottom, thickness=depth).common(
                common_deck
            ),
            Part.makeCylinder(
                stack_interface.CLAMP_HOLE_DIAMETER / 2, depth, V(x, y, bottom)
            ),
        )
        for index, (x, y) in enumerate(stack_interface.CLAMP_CENTRES)
    )


def attachment_check(carrier_in_platform_coordinates):
    """Check actual carrier material beneath the two complete slotted foot seats."""
    depth = stack_interface.DECK_THICKNESS
    rows = []
    for index, (expected_seat, bore) in enumerate(_attachment_templates()):
        missing = expected_seat.cut(carrier_in_platform_coordinates).Volume
        obstruction = bore.common(carrier_in_platform_coordinates).Volume
        rows.append(
            {
                "foot": index,
                "expected_supported_contact_area_mm2": expected_seat.Volume / depth,
                "missing_contact_material_mm3": missing,
                "screw_path_obstruction_mm3": obstruction,
                "passed": expected_seat.Volume / depth > 50
                and missing < 1e-5
                and obstruction < 1e-5,
            }
        )
    return {
        "feet": rows,
        "passed": all(row["passed"] for row in rows),
        "scope": "Nominal geometric support around the common carrier slots, not clamp pressure, strength or PA12 creep qualification.",
    }


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
    plan = get_power_plan(plan_key)
    pose = host_placement(main_doc, host_name)
    physical, reserves = local_shapes(plan_key)
    doc = App.newDocument("GondolaPowerOptions")
    doc.Label = "Optional power platform | separate from battery baseline"
    group = create_group(doc, "PowerOptionModule", "Optional power module")
    group.Placement = pose
    for key, value in (
        ("PowerPlan", plan_key),
        ("PowerPlanContract", json.dumps(plan.contract(), sort_keys=True)),
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
            label = name
            if name.startswith("PowerModule"):
                index = int(name.removeprefix("PowerModule"))
                branch = plan.branches[index]
                profile = get_power_module_profile(branch.module_key)
                label = (
                    f"{profile.model} | {plan.branch_input_voltage_v(index):g} V"
                    f" -> {branch.output_voltage_v:g} V"
                )
            obj = create_reference(
                doc,
                group,
                name,
                label,
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
