"""Optional removable PA12 portal with two bought carbon regulator supports."""

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
    union,
)
from gondola.contracts.power_options import (
    DEFAULT_OPTIONAL_POWER_PLAN_KEY,
    get_power_module_profile,
    get_power_plan,
)

from . import purchased_hardware, stack_interface, stock_adapter

V = App.Vector
DECK_SIZE_MM = (6.0, 74.0)
DECK_THICKNESS_MM = 3.0
SUPPORT_Z = stack_interface.TOP_BEAM_THICKNESS + 1.0
DECK_BOTTOM_Z = 0.0
INSULATION_ALLOWANCE_MM = 3.0
BODY_BOTTOM_Z = SUPPORT_Z + INSULATION_ALLOWANCE_MM
BAY_CENTRES = ((0.0, -22.0), (0.0, 22.0))
STANDARD_PATTERNS = ()
TERMINAL_TRAVEL_MM = 15.0
CONNECTION_HEIGHT_ALLOWANCE_MM = 15.0
DEFAULT_HOST = "AccessoryEquipmentModule"
DEFAULT_PLAN = DEFAULT_OPTIONAL_POWER_PLAN_KEY
# A common carbon-to-portal interface is used at every host.
PORTAL_ROTATION_DEG = {name: 0.0 for name in stack_interface.MECHANICAL_HOSTS}
TOP_FIX_Y = tuple(
    cy + dy for _, cy in BAY_CENTRES for dy in (-16 / 2**0.5, 16 / 2**0.5)
)


def standard_hole_rows():
    return [{"centre_xy_mm": (0, y), "diameter_mm": 2.6} for y in TOP_FIX_Y]


def platform_contract(host_name=DEFAULT_HOST):
    return {
        "host_name": host_name,
        "optional_only": True,
        "replacement_carrier": False,
        "portal_rotation_deg": 0.0,
        "portal_anchor_centres_xy_mm": stack_interface.ANCHOR_CENTRES,
        "deck_size_mm": (*DECK_SIZE_MM, DECK_THICKNESS_MM),
        "deck_bottom_z_mm": DECK_BOTTOM_Z,
        "support_z_mm": SUPPORT_Z,
        "body_bottom_z_mm": BODY_BOTTOM_Z,
        "insulation_allowance_mm": INSULATION_ALLOWANCE_MM,
        "bay_centres_xy_mm": BAY_CENTRES,
        "standard_mounting": {
            "patterns": [{"square_pitch_mm": 16.0, "rotation_deg": 45.0}],
            "scope": "Two opposite16mm Y axes secure each upper bought carbon with M2x8 screws and ordinary M2 nuts. Other pattern populations need their own hardware clearance check.",
        },
        "bought_upper_carbon_count": 2,
        "upper_clamp_hardware": "Four M2x8 screws down from carbon top, four M2 ordinary nuts below the3mm beam. Fit on bench before attaching the portal.",
        "foot_hardware": "Two M2x6 upward screws and M2 nuts on battery/navigation carbon. At FC reuse two25.5mm X studs and move their intermediate nuts above the2mm feet. Carbon-to-rail16mm clamps remain independent.",
        "connection_height_allowance_mm": CONNECTION_HEIGHT_ALLOWANCE_MM,
        "terminal_end_allowance_mm": TERMINAL_TRAVEL_MM,
        "support_scope": "One open PA12 portal and narrow upper cross-beam; two purchased carbon boards carry regulators. No printed mounting deck, invented PCB holes or tie-only slots. Three-mm nominal insulating/adhesive pad allowance clears the clamp heads; inspect compression, received cutouts, PCB underside, straps and cooling. Filled carbon envelopes do not establish contact area or load capacity.",
        "stack_scope": "Fit only at a host without the optical portal. Lower carbon stays installed; this is an added upper structure, not a replacement low carrier. Remove lower equipment for attachment/tool access, then reconnect after the verified service sequence. When tethering omit the battery; reuse released carbon as appropriate, but count every installed upper and lower board.",
        "tether_scope": "Strain-relieve the external cable to the main PA12 frame/rail with existing structure and suitable straps, not a regulator PCB or its carbon plate. Real cable, loads, propeller clearance, cooling and electrical power remain unqualified.",
        "physical_fit_verified": False,
    }


def deck_shape():
    shape = box(
        *DECK_SIZE_MM,
        DECK_THICKNESS_MM,
        (-DECK_SIZE_MM[0] / 2, -DECK_SIZE_MM[1] / 2, 0),
    )
    for y in TOP_FIX_Y:
        shape = shape.cut(Part.makeCylinder(1.3, 5, V(0, y, -1)))
    return shape.removeSplitter()


@functools.lru_cache(None)
def platform_shape(host_name=DEFAULT_HOST):
    if host_name not in stack_interface.MECHANICAL_HOSTS:
        raise ValueError("Unknown carbon power host")
    shape = union([stack_interface.tower_shape(), deck_shape()]).removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Carbon power portal must be one valid printed solid")
    return shape


def _bought_support_shapes(host_name):
    from gondola.contracts import fasteners

    shapes = {}
    for i, centre in enumerate(BAY_CENTRES):
        shapes[f"PowerCarbon{i}"] = stock_adapter.plate_shape(
            bottom=3.0, centre_xy_mm=centre
        )
    for i, y in enumerate(TOP_FIX_Y):
        screw = purchased_hardware.screw_shape(8).copy()
        screw.rotate(V(), V(1, 0, 0), 180)
        screw.translate(V(0, y, 4))
        nut = purchased_hardware.hex_nut_shape().copy()
        nut.translate(V(0, y, -fasteners.HEX_NUT_HEIGHT))
        shapes[f"PowerCarbonBolt{i}"] = screw
        shapes[f"PowerCarbonNut{i}"] = nut
    if host_name != "ElectronicsEquipmentModule":
        for i, (x, y) in enumerate(stack_interface.FOOT_CENTRES):
            screw = purchased_hardware.screw_shape(6).copy()
            screw.translate(V(x, y, 7 - stack_interface.STACK_TOP_Z))
            nut = purchased_hardware.hex_nut_shape().copy()
            nut.translate(V(x, y, 10 - stack_interface.STACK_TOP_Z))
            shapes[f"PowerFootBolt{i}"] = screw
            shapes[f"PowerFootNut{i}"] = nut
    return shapes


def hardware_inventory(host_name=DEFAULT_HOST):
    """Additional installed parts only; FC shared studs/nuts are already present."""
    if host_name not in stack_interface.MECHANICAL_HOSTS:
        raise ValueError("Unknown carbon power host")
    rows = {f"PowerCarbon{i}": stock_adapter.specification.PART_SKU for i in range(2)}
    rows.update({f"PowerCarbonBolt{i}": "M2X8_BUTTON_HEAD" for i in range(4)})
    rows.update({f"PowerCarbonNut{i}": "M2_HEX_NUT" for i in range(4)})
    if host_name != "ElectronicsEquipmentModule":
        rows.update({f"PowerFootBolt{i}": "M2X6_BUTTON_HEAD" for i in range(2)})
        rows.update({f"PowerFootNut{i}": "M2_HEX_NUT" for i in range(2)})
    return rows


def local_shapes(plan_key=DEFAULT_PLAN, host_name=DEFAULT_HOST):
    """Return platform, bought envelopes and explicit service allowances."""
    plan = get_power_plan(plan_key)
    if not plan.branches or len(plan.branches) > len(BAY_CENTRES):
        raise ValueError("Power platform requires one or two optional regulators")
    physical = {
        "PowerPlatform": platform_shape(host_name).copy(),
        **_bought_support_shapes(host_name),
    }
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
                "OPTIONAL PRINT | carbon-mounted power portal",
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
            inventory = hardware_inventory(host_name)
            if name in inventory:
                set_property(obj, "HardwareSKU", inventory[name])
                set_property(
                    obj, "OptionalAdditionalHardware", True, "App::PropertyBool"
                )
                set_property(obj, "IncludedInDefaultBOM", False, "App::PropertyBool")
                if inventory[name] == stock_adapter.specification.PART_SKU:
                    set_property(
                        obj,
                        "ReferenceMassGrams",
                        stock_adapter.specification.LISTED_MASS_G,
                        "App::PropertyFloat",
                    )
                    set_property(
                        obj,
                        "ReferenceMassSource",
                        stock_adapter.specification.PRODUCT_URL,
                    )
                    set_property(
                        obj,
                        "ReferenceMassBasis",
                        "Seller mass per bought board, unmeasured; not inferred from filled collision volume",
                    )
                    set_property(obj, "ExactContourModeled", False, "App::PropertyBool")
                    set_property(
                        obj,
                        "MaterialSelection",
                        "Carbon fibre composite (seller claim)",
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
