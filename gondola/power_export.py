"""Separate optional power-platform artifacts and read-only geometric screening.

The optional platform does not enter the default print or equipment inventory.
Validation refreshes only its report; it never regenerates exported artifacts.
"""

import functools
import json
import math
from itertools import combinations
from pathlib import Path

import FreeCAD as App
import Mesh
import Part

from .cad import create_group, create_reference, set_property, world_shape
from .config import ARTIFACT_STEM, OUTPUT_DIR
from .contracts.power_options import (
    POWER_ARTIFACT_NAMES as ARTIFACT_NAMES,
)
from .contracts.power_options import (
    POWER_VALIDATION_NAME as REPORT_NAME,
)
from .contracts.power_options import get_power_plan, power_option_contract
from .mass_budget import DENSITIES_G_CM3, PA12_DENSITY_SOURCE
from .parts import power_mount, stack_interface
from .print_export import (
    geometry_comparison,
    mesh_checks,
    mesh_from_shape,
    print_shape,
    print_size_check,
    print_solid_comparison,
)
from .provenance import file_sha256, source_fingerprint
from .validation.geometry import intersection_volume

OPTIONAL_PLANS = ("TETHER_DUAL_BEC", "TETHER_BEC_SVPDB", "BATTERY_SVPDB")
TOL = 1e-5


def _main_shapes(doc):
    registry = doc.DesignRegistry
    return {
        obj.Name: world_shape(obj)
        for category in (
            "PrintedParts",
            "HardwareParts",
            "ReferenceParts",
            "TapeReferences",
            "ClearanceVolumes",
        )
        for obj in getattr(registry, category)
        if hasattr(obj, "Shape") and not obj.Shape.isNull() and obj.Shape.Solids
    }


def _placed(shapes, pose):
    result = {}
    for name, shape in shapes.items():
        item = shape.copy()
        item.Placement = pose.multiply(item.Placement)
        result[name] = item
    return result


def _collisions(first, second):
    return [
        {"first": name, "second": other, "intersection_mm3": volume}
        for name, shape in first.items()
        for other, obstacle in second.items()
        if (volume := intersection_volume(shape, obstacle)) > TOL
    ]


def _internal_collisions(physical, reserves):
    conflicts = _collisions(reserves, physical)
    for (name, shape), (other, obstacle) in combinations(physical.items(), 2):
        # Nominal threaded fasteners deliberately engage their corresponding nuts.
        if name.startswith("PowerFootBolt") and other == name.replace("Bolt", "Nut"):
            continue
        volume = intersection_volume(shape, obstacle)
        if volume > TOL:
            conflicts.append(
                {"first": name, "second": other, "intersection_mm3": volume}
            )
    conflicts.extend(
        _collisions(
            {"TetherDepartureReserve": reserves["TetherDepartureReserve"]},
            {
                name: shape
                for name, shape in reserves.items()
                if name != "TetherDepartureReserve"
            },
        )
    )
    return conflicts


def _xy_registration_bound(shape):
    """Continuous XY bound, without rotating an already-enclosing box twice.

    Every point is within the shape's XY box and hence within radius r. Seated
    translation is <=g and yaw <=2 asin(g/(2 R)); rotation displaces any point
    by <=2 r sin(yaw/2). Adding those bounds is conservative for all poses,
    including the actual correlated translation/yaw constraint.
    """
    bounds = shape.BoundBox
    g = stack_interface.MAX_RADIAL_FLOAT
    axis_radius = math.hypot(*stack_interface.CLAMP_CENTRES[0])
    radius = max(
        math.hypot(x, y)
        for x in (bounds.XMin, bounds.XMax)
        for y in (bounds.YMin, bounds.YMax)
    )
    padding = g + radius * g / axis_radius
    return Part.makeBox(
        bounds.XLength + 2 * padding,
        bounds.YLength + 2 * padding,
        bounds.ZLength,
        App.Vector(bounds.XMin - padding, bounds.YMin - padding, bounds.ZMin),
    )


@functools.lru_cache(None)
def _registration_bounds(plan_key):
    physical, reserves = power_mount.local_shapes(plan_key)
    result = dict(stack_interface.rigid_float_component_bounds())
    result.update(
        {
            "PowerFoot" + name: shape
            for name, shape in stack_interface.clamp_hardware_float_bounds()
        }
    )
    result["PowerDeck"] = _xy_registration_bound(
        Part.makeBox(
            *power_mount.DECK_SIZE_MM,
            power_mount.DECK_THICKNESS_MM,
            App.Vector(-32, -32, power_mount.DECK_BOTTOM_Z),
        )
    )
    result.update(
        {
            name: _xy_registration_bound(shape)
            for name, shape in {**physical, **reserves}.items()
            if name.startswith("PowerModule") or name == "TetherDepartureReserve"
        }
    )
    return result


def _configuration_conflicts(plan_key, pose, context, host_name):
    physical, reserves = power_mount.local_shapes(plan_key)
    physical, reserves = _placed(physical, pose), _placed(reserves, pose)
    nominal = (
        _collisions(physical, context)
        + _collisions(reserves, context)
        + _internal_collisions(physical, reserves)
    )
    # Feet intentionally seat on their host. Its mating-hole/clamp fit is a
    # separate interface check; arbitrary host overlap is never excused nominally.
    obstacles = {
        name: shape
        for name, shape in context.items()
        if name != stack_interface.MECHANICAL_HOSTS[host_name]
    }
    float_conflicts = _collisions(
        _placed(_registration_bounds(plan_key), pose), obstacles
    )
    return [{**row, "phase": "nominal"} for row in nominal] + [
        {**row, "phase": "conservative seated registration"} for row in float_conflicts
    ]


def screen_configurations(main_doc):
    """Screen the saved arrangement; occupied hosts are intentionally rejected."""
    from .contracts.equipment_options import NAVIGATION_PROFILES, get_navigation_profile
    from .contracts.optical_sensors import SENSOR_PROFILES
    from .parts import equipment_envelopes, wiring_reserves
    from .validation.optical import _external_field_bound

    context = _main_shapes(main_doc)
    optical = main_doc.getObject("OpticalFlowModule")
    if optical is not None:
        # These cones enclose both sensor profiles and the declared manual aim range.
        for key, profile in SENSOR_PROFILES.items():
            context[f"{key}ContinuousOpticalFieldBound"] = _external_field_bound(
                optical, profile
            )[0]
    rows = []
    for host_name in stack_interface.MECHANICAL_HOSTS:
        for plan_key in OPTIONAL_PLANS:
            row = {"host": host_name, "plan": plan_key}
            try:
                pose = power_mount.host_placement(main_doc, host_name)
            except ValueError as error:
                row.update(
                    status="rejected", reason=str(error), collisions=[], permitted=False
                )
                rows.append(row)
                continue
            conflicts = _configuration_conflicts(plan_key, pose, context, host_name)
            row.update(
                status="clear" if not conflicts else "rejected",
                collisions=conflicts,
                permitted=not conflicts,
            )
            rows.append(row)
    default = next(
        row
        for row in rows
        if row["host"] == power_mount.DEFAULT_HOST
        and row["plan"] == power_mount.DEFAULT_PLAN
    )
    # Alternative navigation remains a compatibility probe, never added to BOM.
    # MG-F10's direct helix is large enough to reject otherwise valid stack sites.
    navigation_rows = []
    accessory_pose = main_doc.AccessoryEquipmentModule.getGlobalPlacement()
    for profile in NAVIGATION_PROFILES.values():
        installations = (
            ("direct_sma", "remote_sma")
            if profile.external_antenna
            else ("integrated",)
        )
        for installation in installations:
            probe_context = {
                name: shape
                for name, shape in context.items()
                if name
                not in (
                    "ModulePASEnvelope",
                    "PASConnectorReserve",
                    "NavigationDirectAntennaReserve",
                )
            }
            replacements = {
                "ModulePASEnvelope": equipment_envelopes.navigation_envelope_shape(
                    profile
                ),
                "PASConnectorReserve": wiring_reserves.reserve_shapes(
                    navigation_profile=profile
                )["PASConnectorReserve"],
            }
            if installation == "direct_sma":
                replacements["NavigationDirectAntennaReserve"] = (
                    wiring_reserves.direct_antenna_reserve_shape(profile)
                )
            probe_context.update(_placed(replacements, accessory_pose))
            for host_name in stack_interface.MECHANICAL_HOSTS:
                try:
                    pose = power_mount.host_placement(main_doc, host_name)
                except ValueError:
                    continue
                for plan_key in OPTIONAL_PLANS:
                    conflicts = _configuration_conflicts(
                        plan_key, pose, probe_context, host_name
                    )
                    navigation_rows.append(
                        {
                            "host": host_name,
                            "plan": plan_key,
                            "navigation": profile.key,
                            "antenna_installation": installation,
                            "permitted": not conflicts,
                            "collisions": conflicts,
                        }
                    )
    return {
        "saved_optical_host": getattr(optical, "StackHostName", None),
        "configurations": rows,
        "default_configuration_clear": default["permitted"],
        "source_selected_navigation": get_navigation_profile().key,
        "navigation_compatibility_probes": navigation_rows,
        "seated_registration_scope": "Continuous conservative XY/yaw bounds from the shared two-hole clearance contract, with no axial lift. Cylindrical fasteners use expanded radial bounds; legs use existing analytical component bounds; flat deck, devices and reservations use XY boxes enlarged by the sum of maximum translation and maximum rotational point displacement. Any bound intersection rejects the configuration rather than proving actual collision. The host's intended foot seating is excluded only from this float pass, not from the nominal check.",
        "scope": "Exact nominal optional bodies, local terminal/top allowances and nominal 50 mm tether departure allowance versus all saved solid bodies and reservations, including full propulsion sweep bounds. Additional conservative cones enclose both optical profiles throughout their declared manual angle range on the currently saved optical host. Other host/antenna/rail arrangements require another audit. Intentional mating contact has zero volume; positive interference rejects a configuration. Free tether trajectory, tie retention, cooling and electrical operation are not qualified.",
        "passed": default["permitted"] and len(rows) == 9,
    }


def _manifest(doc):
    part = doc.PowerPlatform
    printed = print_shape(part)
    bounds = printed.optimalBoundingBox(False, False)
    sizes = [bounds.XLength, bounds.YLength, bounds.ZLength]
    local = part.Shape.optimalBoundingBox(False, False)
    return {
        "source_fingerprint": source_fingerprint(),
        "optional_only": True,
        "included_in_default_installed_inventory": False,
        "default_host": power_mount.DEFAULT_HOST,
        "illustrated_power_plan": get_power_plan(power_mount.DEFAULT_PLAN).contract(),
        "printed_quantity": 1,
        "printed_volume_mm3": round(float(part.Shape.Volume), 6),
        "estimated_printed_mass_g": round(
            float(part.Shape.Volume) * DENSITIES_G_CM3["PA12"] / 1000, 6
        ),
        "mass_scope": "Optional printed platform only, estimated from modeled solid volume and provisional PA12 density. Excludes optional hardware, regulators, ties, insulation, wires, manufacturing variation and tether; not measured or all-up mass.",
        "density_reference": {
            "material": "PA12",
            "g_cm3": DENSITIES_G_CM3["PA12"],
            "source": PA12_DENSITY_SOURCE,
        },
        "additional_hardware": {"M2X8_BUTTON_HEAD": 2, "M2_HEX_NUT": 2},
        "size_mm": sizes,
        "size_check": print_size_check(
            [local.XLength, local.YLength, local.ZLength], sizes
        ),
        "platform_contract": power_mount.platform_contract(),
        "power_options": power_option_contract(),
        "context_scope": "Hidden saved assembly reference solids preserve shape and world placement independently of main CAD display properties. Context shapes are not optional manufacturing parts or additional bought parts.",
    }


def export_power_options(main_doc, output_dir=None):
    out = Path(output_dir or OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    doc = power_mount.create_option_document(main_doc)
    try:
        context = create_group(
            doc, "AssemblyContext", "REFERENCE | saved baseline assembly"
        )
        for name, shape in _main_shapes(main_doc).items():
            obj = create_reference(
                doc,
                context,
                "Context_" + name,
                name,
                shape,
                "Saved baseline context; not printed by optional export",
            )
            set_property(obj, "SourceObjectName", name)
            obj.Label = "CONTEXT | " + name
            if App.GuiUp:
                obj.ViewObject.Visibility = False
        set_property(doc.PowerOptionModule, "SourceFingerprint", source_fingerprint())
        doc.recompute()
        shape = print_shape(doc.PowerPlatform)
        mesh_from_shape(shape).write(str(out / ARTIFACT_NAMES[1]))
        shape.exportStep(str(out / ARTIFACT_NAMES[2]))
        (out / ARTIFACT_NAMES[3]).write_text(
            json.dumps(_manifest(doc), indent=2) + "\n"
        )
        doc.saveAs(str(out / ARTIFACT_NAMES[0]))
        # Only validation against the final saved main CAD claims report success.
        return {"artifacts": list(ARTIFACT_NAMES), "optional_only": True}
    finally:
        App.closeDocument(doc.Name)


def _same_shape(first, second):
    result = geometry_comparison(first, second)
    return all(
        result[key] < TOL
        for key in ("difference_mm3", "bounds_difference_mm", "volume_difference_mm3")
    )


def _mesh_signature(mesh):
    points, triangles = mesh.Topology
    return sorted(
        tuple(
            sorted(
                tuple(round(float(value), 6) for value in points[index])
                for index in triangle
            )
        )
        for triangle in triangles
    )


def audit_power_options(source=None, output_dir=None):
    source = Path(source or Path(output_dir or OUTPUT_DIR) / f"{ARTIFACT_STEM}.FCStd")
    out = Path(output_dir or source.parent)
    report = {
        "source_fingerprint": source_fingerprint(),
        "source_sha256": file_sha256(source),
        "artifact_hashes_before": {
            name: file_sha256(out / name) for name in ARTIFACT_NAMES
        },
        "passed": False,
    }
    main = App.openDocument(str(source))
    option = None
    try:
        option = App.openDocument(str(out / ARTIFACT_NAMES[0]))
        registry = main.DesignRegistry
        report["main_optional_contract_matches"] = getattr(
            registry, "OptionalPowerDocument", None
        ) == ARTIFACT_NAMES[0] and json.loads(
            getattr(registry, "OptionalPowerContract", "null")
        ) == json.loads(json.dumps(power_option_contract()))
        physical, reserves = power_mount.local_shapes()
        expected = {**physical, **reserves}
        group = option.getObject("PowerOptionModule")
        pose = power_mount.host_placement(main, power_mount.DEFAULT_HOST)
        report["option_pose_matches"] = group.Placement.isSame(pose, TOL)
        report["option_source_matches"] = (
            str(group.SourceFingerprint) == source_fingerprint()
        )
        report["option_selection_matches"] = (
            str(group.PowerPlan) == power_mount.DEFAULT_PLAN
            and str(group.StackHostName) == power_mount.DEFAULT_HOST
        )
        report["option_contract_matches"] = json.loads(
            group.PowerPlatformContract
        ) == json.loads(json.dumps(power_mount.platform_contract()))
        report["native_shape_checks"] = {
            name: option.getObject(name) is not None
            and option.getObject(name).getParentGeoFeatureGroup() == group
            and _same_shape(option.getObject(name).Shape, shape)
            for name, shape in expected.items()
        }
        report["native_inventory_matches"] = {
            obj.Name for obj in group.Group if hasattr(obj, "Shape")
        } == set(expected)
        main_shapes = _main_shapes(main)
        context = {
            obj.SourceObjectName: obj
            for obj in option.AssemblyContext.Group
            if hasattr(obj, "SourceObjectName")
        }
        context_children = [
            obj for obj in option.AssemblyContext.Group if hasattr(obj, "Shape")
        ]
        report["context_names_unique"] = len(context) == len(context_children)
        allowed_shapes = set(expected) | {obj.Name for obj in context_children}
        report["complete_shape_inventory_matches"] = {
            obj.Name
            for obj in option.Objects
            if obj.isDerivedFrom("Part::Feature") and not obj.Shape.isNull()
        } == allowed_shapes
        report["optional_print_inventory_matches"] = [
            obj.Name for obj in option.Objects if getattr(obj, "PrintPart", False)
        ] == ["PowerPlatform"]
        report["context_inventory_matches"] = set(context) == set(main_shapes)
        report["context_shapes_match"] = report["context_inventory_matches"] and all(
            _same_shape(world_shape(context[name]), shape)
            for name, shape in main_shapes.items()
        )
        actual_manifest = json.loads((out / ARTIFACT_NAMES[3]).read_text())
        report["manifest_matches"] = actual_manifest == json.loads(
            json.dumps(_manifest(option))
        )
        report["print_size_passed"] = bool(
            actual_manifest.get("size_check", {}).get("passed")
        )
        expected_print = print_shape(option.PowerPlatform)
        step = Part.Shape()
        step.read(str(out / ARTIFACT_NAMES[2]))
        report["step_comparison"] = print_solid_comparison(expected_print, step, TOL)
        mesh = Mesh.Mesh(str(out / ARTIFACT_NAMES[1]))
        report["mesh_checks"] = mesh_checks(expected_print, mesh)
        report["mesh_matches_native_tessellation"] = _mesh_signature(
            mesh
        ) == _mesh_signature(mesh_from_shape(expected_print))
        report["configuration_screen"] = screen_configurations(main)
        report["alternate_optical_host_screens"] = []
        optical = main.getObject("OpticalFlowModule")
        if optical is not None:
            original_host = optical.getParentGeoFeatureGroup()
            original_pose = App.Placement(optical.Placement)
            try:
                for host_name in stack_interface.SUPPORTED_HOSTS:
                    if host_name != original_host.Name:
                        stack_interface.attach_to_host(
                            optical, main.getObject(host_name)
                        )
                        report["alternate_optical_host_screens"].append(
                            screen_configurations(main)
                        )
            finally:
                stack_interface.attach_to_host(optical, original_host)
                optical.Placement = original_pose
                main.recompute()
        report["source_sha256_after"] = file_sha256(source)
        report["artifact_hashes"] = {
            name: file_sha256(out / name) for name in ARTIFACT_NAMES
        }
        report["read_only_artifacts"] = (
            report["source_sha256"] == report["source_sha256_after"]
            and report["artifact_hashes_before"] == report["artifact_hashes"]
        )
        report["alternate_optical_hosts_passed"] = all(
            row["passed"] for row in report["alternate_optical_host_screens"]
        )
        report["source_fingerprint_after"] = source_fingerprint()
        report["source_code_unchanged"] = (
            report["source_fingerprint"] == report["source_fingerprint_after"]
        )
        report["passed"] = (
            all(
                report[key]
                for key in (
                    "option_pose_matches",
                    "main_optional_contract_matches",
                    "option_source_matches",
                    "option_selection_matches",
                    "option_contract_matches",
                    "native_inventory_matches",
                    "context_names_unique",
                    "complete_shape_inventory_matches",
                    "optional_print_inventory_matches",
                    "context_inventory_matches",
                    "context_shapes_match",
                    "manifest_matches",
                    "print_size_passed",
                    "mesh_matches_native_tessellation",
                    "read_only_artifacts",
                    "alternate_optical_hosts_passed",
                    "source_code_unchanged",
                )
            )
            and all(report["native_shape_checks"].values())
            and report["step_comparison"]["passed"]
            and report["configuration_screen"]["passed"]
            and report["mesh_checks"]["watertight_mesh"]
            and report["mesh_checks"]["valid_brep"]
            and report["mesh_checks"]["single_closed_solid"]
            and report["mesh_checks"]["solid_count"] == 1
            and report["mesh_checks"]["mesh_components"] == 1
        )
    finally:
        if option is not None:
            App.closeDocument(option.Name)
        App.closeDocument(main.Name)
    (out / REPORT_NAME).write_text(json.dumps(report, indent=2) + "\n")
    return report
