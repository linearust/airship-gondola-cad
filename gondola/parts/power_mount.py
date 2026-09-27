"""Optional integral power carriers with host-specific portal orientations."""

import functools
import json

import FreeCAD as App

from gondola.cad import (
    box,
    create_group,
    create_printed_part,
    create_reference,
    set_property,
    union,
)
from gondola.contracts.power_options import (
    DEFAULT_OPTIONAL_POWER_PLAN_KEY,
    get_power_module_profile,
    get_power_plan,
)

from . import equipment_mounts as mounts
from . import stack_interface

V = App.Vector
DECK_SIZE_MM = (40.0, 56.0)
DECK_THICKNESS_MM = 2.0
SUPPORT_Z = stack_interface.TOP_BEAM_THICKNESS
DECK_BOTTOM_Z = SUPPORT_Z - DECK_THICKNESS_MM
INSULATION_ALLOWANCE_MM = 1.0
BODY_BOTTOM_Z = SUPPORT_Z + INSULATION_ALLOWANCE_MM
BAY_CENTRES = ((0.0, -13.0), (0.0, 13.0))
STANDARD_PATTERNS = ()
TERMINAL_TRAVEL_MM = 15.0
CONNECTION_HEIGHT_ALLOWANCE_MM = 15.0
DEFAULT_HOST = "AccessoryEquipmentModule"
DEFAULT_PLAN = DEFAULT_OPTIONAL_POWER_PLAN_KEY
# The accessory radio has end connector lanes at Y=-22. Its optional portal
# uses X-aligned legs; the optical and FC portals keep their diagonal support.
PORTAL_ROTATION_DEG = {
    "BatteryEquipmentModule": 0.0,
    "ElectronicsEquipmentModule": 0.0,
    "AccessoryEquipmentModule": -45.0,
}


def standard_hole_rows():
    return []


def platform_contract(host_name=DEFAULT_HOST):
    rotation = PORTAL_ROTATION_DEG[host_name]
    transform = App.Rotation(V(0, 0, 1), rotation)
    centres = [transform.multVec(V(x, y, 0)) for x, y in stack_interface.ANCHOR_CENTRES]
    return {
        "host_name": host_name,
        "portal_rotation_deg": rotation,
        "portal_anchor_centres_xy_mm": [(point.x, point.y) for point in centres],
        "portal_orientation_by_host_deg": PORTAL_ROTATION_DEG,
        "portal_orientation_scope": "Accessory power uses straight X-aligned legs, keeping both Mini radio end-connector lanes open. Battery and FC power variants retain diagonal legs. The optical portal is unchanged. Lower carriers, board bays and deck orientations are unchanged.",
        "optional_only": True,
        "replacement_carrier": True,
        "attachment_hardware_added": 0,
        "deck_size_mm": (*DECK_SIZE_MM, DECK_THICKNESS_MM),
        "deck_bottom_z_mm": DECK_BOTTOM_Z,
        "support_z_mm": SUPPORT_Z,
        "body_bottom_z_mm": BODY_BOTTOM_Z,
        "insulation_allowance_mm": INSULATION_ALLOWANCE_MM,
        "bay_centres_xy_mm": BAY_CENTRES,
        "standard_mounting": {
            "patterns": [],
            "scope": "Unperforated insulating support for boards without verified holes. Shared rail coupling provides interchangeability.",
        },
        "tether_scope": "No dedicated tether hole, guide or constrained cable route. Wrap existing structure with suitable straps and secure the incoming lead before the PCB terminals. Actual tether routing, strain relief, loads and clearance from moving propulsors are unverified and must be established for the installed cable; no arbitrary straight cable envelope is certified.",
        "connection_height_allowance_mm": CONNECTION_HEIGHT_ALLOWANCE_MM,
        "terminal_end_allowance_mm": TERMINAL_TRAVEL_MM,
        "support_scope": "Flat open deck with two board regions, no dedicated tie slots, board pockets or invented board holes. Use suitable adhesive or wrap the existing structure with a removable strap. One mm nominal insulating support allowance is not measured underside-component clearance or thermal qualification. Position ties clear of hot components, solder and headers after inspecting received boards.",
        "stack_scope": "One optional integral carrier variant replaces the low carrier at an unoccupied host. Reuse its existing rail clamp and any FC carbon hardware; do not add this shape on top of the original printed carrier. Optical and power variants are mutually exclusive at a host. Disconnect and bench-service before exchanging the complete carrier. Devices below the fixed portal require lateral service, not lift through the upper deck. No extra platform feet or fasteners.",
    }


def deck_shape():
    """Unperforated insulating contact for the two boards with no confirmed holes."""
    return box(
        *DECK_SIZE_MM,
        DECK_THICKNESS_MM,
        (-DECK_SIZE_MM[0] / 2, -DECK_SIZE_MM[1] / 2, DECK_BOTTOM_Z),
    )


@functools.lru_cache(None)
def platform_shape(host_name=DEFAULT_HOST):
    part_name = stack_interface.MECHANICAL_HOSTS[host_name]
    kind = next(k for k, name in mounts.MOUNT_NAMES.items() if name == part_name)
    # Rotate the structural portal only. Rotating the low carrier would move
    # the rail shoe; rotating the deck would move its declared board regions.
    components = []
    roots = []
    for name, component in stack_interface.structural_component_shapes():
        component.rotate(V(), V(0, 0, 1), PORTAL_ROTATION_DEG[host_name])
        component.translate(V(0, 0, stack_interface.STACK_TOP_Z))
        components.append(component)
        if name.startswith("root_arm_"):
            roots.append(component)
    lower = mounts.mount_shape(kind)
    if abs(lower.common(union(roots)).Volume) <= 1e-5:
        raise RuntimeError("Power portal requires positive-volume carrier/root overlap")
    deck = deck_shape()
    deck.translate(V(0, 0, stack_interface.STACK_TOP_Z))
    shape = union([lower, deck, *components]).removeSplitter()
    shape.translate(V(0, 0, -stack_interface.STACK_TOP_Z))
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Optional power carrier is not one valid solid")
    return shape


def local_shapes(plan_key=DEFAULT_PLAN, host_name=DEFAULT_HOST):
    """Return platform, bought envelopes and explicit service allowances."""
    plan = get_power_plan(plan_key)
    if not plan.branches or len(plan.branches) > len(BAY_CENTRES):
        raise ValueError("Power platform requires one or two optional regulators")
    physical = {"PowerPlatform": platform_shape(host_name).copy()}
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
    physical, reserves = local_shapes(plan_key, host_name)
    doc = App.newDocument("GondolaPowerOptions")
    doc.Label = "Optional power platform | separate from battery baseline"
    group = create_group(doc, "PowerOptionModule", "Optional power module")
    group.Placement = pose
    for key, value in (
        ("PowerPlan", plan_key),
        ("PowerPlanContract", json.dumps(plan.contract(), sort_keys=True)),
        ("StackHostName", host_name),
        (
            "PowerPlatformContract",
            json.dumps(platform_contract(host_name), sort_keys=True),
        ),
    ):
        set_property(group, key, value)
    for name, shape in physical.items():
        if name == "PowerPlatform":
            obj = create_printed_part(
                doc,
                group,
                name,
                "OPTIONAL PRINT | integral power carrier (replaces low carrier)",
                shape,
                App.Rotation(V(1, 0, 0), 180),
                platform_contract(host_name)["support_scope"],
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
