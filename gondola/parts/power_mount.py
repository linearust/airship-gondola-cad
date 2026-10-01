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
    set_print_sku,
    set_property,
)
from gondola.contracts.power_options import (
    DEFAULT_OPTIONAL_POWER_PLAN_KEY,
    DIRECT_CARRIER,
    PORTAL,
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
DEFAULT_HOST = "BatteryEquipmentModule"
DEFAULT_PLAN = DEFAULT_OPTIONAL_POWER_PLAN_KEY
DEFAULT_PACKAGING = DIRECT_CARRIER
DEFAULT_OPTICAL_HOST = "AccessoryEquipmentModule"
DEFAULT_OPTICAL_SIDE = "NegativeX"
DIRECT_BAY_CENTRES = ((0.0, -14.0), (0.0, 14.0))
DIRECT_ADHESIVE_REGIONS = (
    (((0.0, -23.0), (12.0, 4.0)), ((0.0, -6.0), (12.0, 4.0))),
    (((0.0, 6.0), (12.0, 4.0)), ((0.0, 22.0), (12.0, 4.0))),
)


def installation_contract(plan_key, packaging):
    """Explicitly separate a vacant-carrier installation from the raised option."""
    get_power_plan(plan_key)
    if packaging not in (DIRECT_CARRIER, PORTAL):
        raise ValueError("Unknown optional power packaging")
    if packaging == DIRECT_CARRIER and plan_key != "TETHER_BEC_SVPDB":
        raise ValueError(
            "Direct carrier packaging requires tether power and no battery"
        )
    return {
        "packaging": packaging,
        "plan": plan_key,
        "battery_installed": plan_key != "TETHER_BEC_SVPDB",
        "additional_printed_quantity": int(packaging == PORTAL),
        "additional_screw_nut_pairs": 2 if packaging == PORTAL else 0,
        "bay_centres_xy_mm": DIRECT_BAY_CENTRES
        if packaging == DIRECT_CARRIER
        else BAY_CENTRES,
        "insulation_allowance_mm": INSULATION_ALLOWANCE_MM,
        "continuous_adhesive_regions": DIRECT_ADHESIVE_REGIONS
        if packaging == DIRECT_CARRIER
        else (),
        "support_scope": "Direct tether boards each use two separated 12 x 4 mm continuous carrier lands and 1 mm nominal insulating adhesive. The published envelopes do not locate underside components or solder. Inspect received undersides, insulate exposed conductors and verify contact/retention without pressing components. No board holes, rigid spacers or thermal rating are inferred."
        if packaging == DIRECT_CARRIER
        else platform_contract()["support_scope"],
        "service": "Disconnect leads, release adhesive and lift each direct-mounted board 32 mm away from the carrier. The bare-board sweep is checked; connected wiring, actual adhesive release and tether handling are not qualified. Raised-platform foot service remains as defined by its separate contract.",
        "tether_scope": platform_contract()["tether_scope"],
    }


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
        "stack_scope": "One optional platform per supported carrier; use only composed configurations whose equipment, wiring and independent optical field screens pass. Do not stack platforms on one another. Remove the carrier from the rail for foot-fastener service; the balloon is not modeled.",
    }


@functools.lru_cache(None)
def _platform_shape():
    shape = stack_interface.tower_shape().fuse(mounting_plate.shape(DECK_BOTTOM_Z))
    for hole in mounting_plate.cutters(-1, 5):
        shape = shape.cut(hole)
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Optional power platform is not one valid solid")
    return shape


def platform_shape():
    """Return an independent optional-platform solid for each caller."""
    return _platform_shape().copy()


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


def direct_attachment_check(carrier_in_power_coordinates, physical):
    """Measure the actual host lands beneath the nominal insulating allocations."""
    rows = []
    for index, regions in enumerate(DIRECT_ADHESIVE_REGIONS):
        for patch_index, (centre, size) in enumerate(regions):
            patch = box(
                *size,
                DECK_THICKNESS_MM,
                (centre[0] - size[0] / 2, centre[1] - size[1] / 2, -DECK_THICKNESS_MM),
            )
            bounds = physical[f"PowerModule{index}"].BoundBox
            footprint = box(
                bounds.XLength,
                bounds.YLength,
                DECK_THICKNESS_MM,
                (bounds.XMin, bounds.YMin, -DECK_THICKNESS_MM),
            )
            missing = patch.cut(carrier_in_power_coordinates).Volume
            overlap = patch.common(footprint).Volume / DECK_THICKNESS_MM
            rows.append(
                {
                    "board": f"PowerModule{index}",
                    "patch": patch_index,
                    "continuous_supported_area_mm2": size[0] * size[1],
                    "body_overlap_mm2": overlap,
                    "missing_host_material_mm3": missing,
                    "insulation_allowance_mm": bounds.ZMin,
                    "passed": missing < 1e-5
                    and abs(overlap - size[0] * size[1]) < 1e-5
                    and abs(bounds.ZMin - INSULATION_ALLOWANCE_MM) < 1e-5,
                }
            )
    return {
        "boards": rows,
        "passed": all(row["passed"] for row in rows),
        "scope": "Nominal flat contact and insulation allocation only. Received underside components, adhesive shear/peel, temperature and long-term retention require physical verification.",
    }


def local_shapes(plan_key=DEFAULT_PLAN, *, packaging=DEFAULT_PACKAGING):
    """Return platform, bought envelopes and explicit service allowances."""
    installation_contract(plan_key, packaging)
    plan = get_power_plan(plan_key)
    if not plan.branches or len(plan.branches) > len(BAY_CENTRES):
        raise ValueError("Power platform requires one or two optional regulators")
    physical = {"PowerPlatform": platform_shape().copy()} if packaging == PORTAL else {}
    reserves = {}
    centres = DIRECT_BAY_CENTRES if packaging == DIRECT_CARRIER else BAY_CENTRES
    body_bottom = (
        INSULATION_ALLOWANCE_MM if packaging == DIRECT_CARRIER else BODY_BOTTOM_Z
    )
    for index, branch in enumerate(plan.branches):
        profile = get_power_module_profile(branch.module_key)
        x, y = centres[index]
        length, width, height = profile.size_mm
        name = f"PowerModule{index}"
        physical[name] = box(
            length, width, height, (x - length / 2, y - width / 2, body_bottom)
        )
        reserves[f"{name}TopReserve"] = box(
            length,
            width,
            CONNECTION_HEIGHT_ALLOWANCE_MM,
            (x - length / 2, y - width / 2, body_bottom + height),
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
                    (left, y - width / 2, body_bottom),
                )
            )
    for index, (x, y) in enumerate(
        stack_interface.CLAMP_CENTRES if packaging == PORTAL else ()
    ):
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


def host_placement(
    main_doc, host_name, plan_key=DEFAULT_PLAN, *, packaging=DEFAULT_PACKAGING
):
    installation_contract(plan_key, packaging)
    if host_name not in stack_interface.MECHANICAL_HOSTS:
        raise ValueError("Unsupported power-platform host")
    if packaging == DIRECT_CARRIER and host_name != "BatteryEquipmentModule":
        raise ValueError("Direct tether boards require the vacated battery carrier")
    host = main_doc.getObject(host_name)
    if host is None:
        raise ValueError("Missing power-platform host")
    return host.getGlobalPlacement().multiply(
        stack_interface.host_placement(
            host_name,
            z=stack_interface.HOST_SUPPORT_Z
            if packaging == DIRECT_CARRIER
            else stack_interface.STACK_TOP_Z,
        )
    )


def create_option_document(
    main_doc,
    plan_key=DEFAULT_PLAN,
    host_name=DEFAULT_HOST,
    *,
    packaging=DEFAULT_PACKAGING,
):
    plan = get_power_plan(plan_key)
    pose = host_placement(main_doc, host_name, plan_key, packaging=packaging)
    physical, reserves = local_shapes(plan_key, packaging=packaging)
    doc = App.newDocument("GondolaPowerOptions")
    doc.Label = "Optional power platform | separate from battery baseline"
    group = create_group(doc, "PowerOptionModule", "Optional power module")
    group.Placement = pose
    for key, value in (
        ("PowerPlan", plan_key),
        ("PowerPackaging", packaging),
        (
            "OpticalCarrierHost",
            main_doc.OpticalFlowModule.CarrierHostName,
        ),
        ("OpticalCarrierSide", str(main_doc.OpticalFlowModule.MountSide)),
        (
            "PowerInstallationContract",
            json.dumps(installation_contract(plan_key, packaging), sort_keys=True),
        ),
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
            set_print_sku(obj, "PowerPlatform")
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
