"""Separate optional power-platform artifacts and read-only geometric screening.

The optional platform does not enter the default print or equipment inventory.
Validation refreshes only its report; it never regenerates exported artifacts.
"""

import functools
import json
from itertools import combinations
from pathlib import Path

import FreeCAD as App
import Mesh
import Part

from .cad import (
    create_group,
    create_printed_part,
    create_reference,
    placed_shape,
    set_print_sku,
    set_property,
    world_shape,
)
from .config import ARTIFACT_STEM, OUTPUT_DIR
from .contracts.power_options import (
    DIRECT_CARRIER,
    OPTIONAL_POWER_PLAN_KEYS,
    PORTAL,
    POWER_PACKAGINGS,
    POWER_PLATFORM_DOCUMENT_NAME,
    get_power_plan,
    power_option_contract,
)
from .contracts.power_options import (
    POWER_ARTIFACT_NAMES as ARTIFACT_NAMES,
)
from .contracts.power_options import (
    POWER_VALIDATION_NAME as REPORT_NAME,
)
from .mass_budget import DENSITIES_G_CM3, PA12_DENSITY_SOURCE
from .parts import (
    mounting_plate,
    power_mount,
    stack_interface,
)
from .print_export import (
    geometry_comparison,
    mesh_checks,
    mesh_from_shape,
    print_shape,
    print_size_check,
    print_solid_comparison,
)
from .print_materials import print_label, print_metadata_matches, print_specification
from .provenance import file_sha256, source_fingerprint
from .validation.evidence import comparison_passed
from .validation.geometry import (
    compare_mesh_surfaces,
    intersection_volume,
    translation_sweep,
)
from .validation.optical_envelopes import motion_bounds

OPTIONAL_PLANS = OPTIONAL_POWER_PLAN_KEYS
TOL = 1e-5
# These are operating ray reservations, not physical bodies. Keep this exact
# allowlist separate from all body/tray/connector/tool bounds and unknown names.
FUNCTIONAL_OPTICAL_FIELDS = frozenset(
    {
        "MTF02POpticalClearanceReserve",
        "MTF02PContinuousOpticalFieldBound",
        "MTF01PContinuousOpticalFieldBound",
    }
)


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


def _installation_context(main, plan_key):
    context = _main_shapes(main)
    if plan_key == "TETHER_BEC_SVPDB":
        context.pop("ModuleBatteryEnvelope", None)
        context.pop("MaximumBatteryEnvelope", None)
    return context


def _placed(shapes, pose):
    return {name: placed_shape(shape, pose) for name, shape in shapes.items()}


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
    return conflicts


def _xy_registration_bound(shape):
    """Continuous coupled XY/yaw bound from the common opposed carrier slots."""
    return stack_interface.rigid_float_shape_bound(shape)


@functools.lru_cache(None)
def _registration_bounds(plan_key):
    physical, reserves = power_mount.local_shapes(plan_key, packaging=PORTAL)
    result = dict(stack_interface.rigid_float_component_bounds())
    result.update(
        {
            "PowerFoot" + name: shape
            for name, shape in stack_interface.clamp_hardware_float_bounds()
        }
    )
    result["PowerDeck"] = _xy_registration_bound(
        mounting_plate.shape(power_mount.DECK_BOTTOM_Z)
    )
    result.update(
        {
            name: _xy_registration_bound(shape)
            for name, shape in {**physical, **reserves}.items()
            if name.startswith("PowerModule")
        }
    )
    return result


def _disconnected_service_context(context):
    """Retain every obstacle except the named, inactive optical ray fields.

    Disconnected maintenance does not require optical operation. The selected
    sensor and both alternatives' continuous body, tray, connector and tool
    reservations remain obstacles; this exemption never changes seated checks.
    """
    return {
        name: shape
        for name, shape in context.items()
        if name not in FUNCTIONAL_OPTICAL_FIELDS
    }


def _portal_foot_service_conflicts(physical, pose, context, off_rail_names):
    """Bench access; only the detached rail and its tape are absent.

    Keep the complete host and every physical/access obstacle conservatively.
    The inactive optical ray fields are not solid maintenance obstacles. The
    matching operated bolt/nut pair is the only local tool-contact exemption.
    """
    tools = _placed(dict(stack_interface.clamp_tool_reservations()), pose)
    obstacles = {
        name: shape
        for name, shape in _disconnected_service_context(context).items()
        if name not in off_rail_names
    }
    conflicts = _collisions(tools, obstacles)
    for name, tool in tools.items():
        index = name.rsplit("_", 1)[1]
        operated = {"PowerFootBolt" + index, "PowerFootNut" + index}
        conflicts.extend(
            _collisions(
                {name: tool},
                {
                    part: shape
                    for part, shape in physical.items()
                    if part not in operated
                },
            )
        )
    return [{**row, "phase": "off-rail foot-fastener service"} for row in conflicts]


def _configuration_conflicts(
    plan_key, pose, context, host_name, *, packaging=PORTAL, off_rail_names=()
):
    local_physical, local_reserves = power_mount.local_shapes(
        plan_key, packaging=packaging
    )
    physical, reserves = local_physical, local_reserves
    physical, reserves = _placed(physical, pose), _placed(reserves, pose)
    nominal = (
        _collisions(physical, context)
        + _collisions(reserves, context)
        + _internal_collisions(physical, reserves)
    )
    host_shape = context.get(stack_interface.MECHANICAL_HOSTS[host_name])
    if host_shape is None:
        nominal.append(
            {
                "first": "PowerPlatform",
                "second": host_name,
                "reason": "Missing structural host solid",
            }
        )
    else:
        local_host = host_shape.copy()
        local_host.Placement = pose.inverse().multiply(local_host.Placement)
        attachment = (
            power_mount.direct_attachment_check(local_host, local_physical)
            if packaging == DIRECT_CARRIER
            else power_mount.attachment_check(local_host)
        )
        if not attachment["passed"]:
            nominal.append(
                {
                    "first": "PowerPlatform",
                    "second": host_name,
                    "reason": "Incomplete declared host support or obstructed attachment",
                    "attachment": attachment,
                }
            )
    if packaging == DIRECT_CARRIER:
        service_context = _disconnected_service_context(context)
        for name, shape in physical.items():
            sweep, _ = translation_sweep(
                shape, tuple(pose.Rotation.multVec(App.Vector(0, 0, 32)))
            )
            nominal += [
                {**row, "phase": "disconnected board removal"}
                for row in _collisions(
                    {name: sweep},
                    {
                        **service_context,
                        **{
                            other: body
                            for other, body in physical.items()
                            if other != name
                        },
                    },
                )
            ]
        return [{"phase": "nominal", **row} for row in nominal]
    # The documented sequence removes the carrier from the rail before this
    # bench operation. Installed/registration checks still retain rail and tape.
    nominal += _portal_foot_service_conflicts(physical, pose, context, off_rail_names)
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
    return [{"phase": "nominal", **row} for row in nominal] + [
        {**row, "phase": "conservative seated registration"} for row in float_conflicts
    ]


def _optical_attachment_description(optical):
    from .parts.optical_interface import attachment_description

    return (
        json.loads(json.dumps(attachment_description(optical)))
        if optical is not None
        else None
    )


def screen_configurations(main_doc):
    """Retain every packaging/host/plan choice and compose navigation conflicts."""
    from .contracts.equipment_options import NAVIGATION_PROFILES, get_navigation_profile
    from .parts import equipment_envelopes, wiring_reserves

    off_rail_names = frozenset(
        obj.Name
        for category in ("RailSegments", "TapeReferences")
        for obj in getattr(main_doc.DesignRegistry, category, ())
    )
    optical = main_doc.getObject("OpticalFlowModule")
    optical_attachment = _optical_attachment_description(optical)
    optical_bounds = motion_bounds(optical) if optical is not None else {}
    contexts = {}
    for plan_key in OPTIONAL_PLANS:
        context = _installation_context(main_doc, plan_key)
        context.update(optical_bounds)
        contexts[plan_key] = context

    def evaluate(plan_key, packaging, host_name, context, configuration_conflicts=()):
        row = {"host": host_name, "plan": plan_key, "packaging": packaging}
        try:
            pose = power_mount.host_placement(
                main_doc, host_name, plan_key, packaging=packaging
            )
        except ValueError as error:
            return {
                **row,
                "status": "rejected",
                "reason": str(error),
                "collisions": list(configuration_conflicts),
                "permitted": False,
            }
        conflicts = [
            *configuration_conflicts,
            *_configuration_conflicts(
                plan_key,
                pose,
                context,
                host_name,
                packaging=packaging,
                off_rail_names=off_rail_names,
            ),
        ]
        return {
            **row,
            "status": "rejected" if conflicts else "clear",
            "collisions": conflicts,
            "permitted": not conflicts,
        }

    rows = [
        {"host": host_name, "plan": plan_key, "packaging": packaging}
        for packaging in POWER_PACKAGINGS
        for host_name in stack_interface.MECHANICAL_HOSTS
        for plan_key in OPTIONAL_PLANS
    ]
    navigation_rows = []
    accessory_pose = main_doc.AccessoryEquipmentModule.getGlobalPlacement()
    for profile in NAVIGATION_PROFILES.values():
        installations = (
            ("direct_sma", "remote_sma")
            if profile.external_antenna
            else ("integrated",)
        )
        for installation in installations:
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
            replacements = _placed(replacements, accessory_pose)
            for plan_key in OPTIONAL_PLANS:
                fixed = {
                    name: shape
                    for name, shape in contexts[plan_key].items()
                    if name
                    not in (
                        "ModulePASEnvelope",
                        "PASConnectorReserve",
                        "NavigationDirectAntennaReserve",
                    )
                }
                # This check composes navigation with existing optics and every
                # other retained object. Testing power-vs-context alone misses
                # collisions between two members of the substituted context.
                combined_conflicts = [
                    {**hit, "phase": "navigation and retained assembly"}
                    for hit in _collisions(replacements, fixed)
                ]
                context = {**fixed, **replacements}
                for packaging in POWER_PACKAGINGS:
                    for host_name in stack_interface.MECHANICAL_HOSTS:
                        navigation_rows.append(
                            {
                                **evaluate(
                                    plan_key,
                                    packaging,
                                    host_name,
                                    context,
                                    combined_conflicts,
                                ),
                                "navigation": profile.key,
                                "antenna_installation": installation,
                            }
                        )
    selected = get_navigation_profile()
    selected_installation = "direct_sma" if selected.external_antenna else "integrated"
    # Default arrangement rows use exactly the same composed decisions as the
    # navigation matrix, including the saved optical attachment.
    for row in rows:
        match = next(
            probe
            for probe in navigation_rows
            if all(probe[k] == row[k] for k in ("host", "plan", "packaging"))
            and probe["navigation"] == selected.key
            and probe["antenna_installation"] == selected_installation
        )
        row.update(
            {
                key: value
                for key, value in match.items()
                if key not in ("navigation", "antenna_installation")
            }
        )
    permitted = {
        plan_key: [
            {"host": row["host"], "packaging": row["packaging"]}
            for row in rows
            if row["plan"] == plan_key and row["permitted"]
        ]
        for plan_key in OPTIONAL_PLANS
    }
    default = next(
        row
        for row in rows
        if row["host"] == power_mount.DEFAULT_HOST
        and row["plan"] == power_mount.DEFAULT_PLAN
        and row["packaging"] == power_mount.DEFAULT_PACKAGING
    )
    inactive_fields = sorted(
        FUNCTIONAL_OPTICAL_FIELDS.intersection(
            {name for context in contexts.values() for name in context}
        )
    )
    return {
        "foot_fastener_service": {
            "mode": "Disconnected carrier and complete portal removed from the rail for bench service",
            "excluded_only_during_bench_service": sorted(off_rail_names),
            "inactive_optical_fields_excluded_only_during_service": inactive_fields,
            "retained_obstacles": "Complete host, platform, boards, sensor bodies, trays, connector/tool reservations and unknown objects remain obstacles. Only each tool's operated bolt/nut pair is an intended-contact exemption; operating optical ray fields are inactive during disconnected bench maintenance.",
            "scope": "Disconnect leads and remove the complete carrier from the rail first. This is a conservative bench tool-space check, not permission to reach through installed tape or the balloon; no connected harness or hand clearance is qualified.",
        },
        "direct_board_service": {
            "mode": "Unpowered boards, leads disconnected and adhesive released before the checked 32 mm lift",
            "inactive_optical_fields_excluded_only_during_service": inactive_fields,
            "retained_obstacles": "All physical parts, the other board, continuous sensor body/tray bounds, connector/tool reservations and unknown objects. The complete optical field remains mandatory for seated configurations.",
        },
        "saved_optical_attachment": optical_attachment,
        "configurations": rows,
        "default_configuration_clear": default["permitted"],
        "permitted_hosts_by_plan": {
            key: sorted({row["host"] for row in value})
            for key, value in permitted.items()
        },
        "permitted_installations_by_plan": permitted,
        "source_selected_navigation": selected.key,
        "navigation_compatibility_probes": navigation_rows,
        "seated_registration_scope": "Portal choices retain the continuous conservative opposed-slot XY/yaw bounds. Direct boards are nominal adhesive placements on the vacated battery carrier, with measured intact land/body overlap; adhesive placement and retention remain physical checks.",
        "scope": "Composed geometric configurations: selected power packaging, mutually exclusive battery/tether inventory, navigation/antenna and the common FC/optical instrument platform. Both sensors' continuous field, body, tray and connector bounds include the full pitch range and conservative registration reserve. Actual fit and angular rocking are unqualified. Retained solid bodies/access reserves and disconnected direct-board removal are screened. Inactive optical ray fields alone may be crossed during disconnected maintenance; seated optical field checks are unchanged. No installed tether, remote antenna, adhesive strength, cooling or electrical qualification.",
        "passed": all(permitted.values())
        and len(rows)
        == len(POWER_PACKAGINGS)
        * len(stack_interface.MECHANICAL_HOSTS)
        * len(OPTIONAL_PLANS)
        and len(navigation_rows) == 4 * len(rows),
    }


def _manifest(doc, manufacturing):
    part = manufacturing.PowerPlatform
    printed = print_shape(part)
    bounds = printed.optimalBoundingBox(False, False)
    sizes = [bounds.XLength, bounds.YLength, bounds.ZLength]
    local = part.Shape.optimalBoundingBox(False, False)
    return {
        "source_fingerprint": source_fingerprint(),
        "manufacturing": print_specification(),
        "print_files": {"stl": ARTIFACT_NAMES[1], "step": ARTIFACT_NAMES[2]},
        "optional_only": True,
        "included_in_default_installed_inventory": False,
        "default_host": power_mount.DEFAULT_HOST,
        "illustrated_power_plan": get_power_plan(power_mount.DEFAULT_PLAN).contract(),
        "illustrated_packaging": power_mount.DEFAULT_PACKAGING,
        "illustrated_optical_attachment": json.loads(
            doc.PowerOptionModule.OpticalAttachment
        ),
        "installed_additional_printed_quantity": 0,
        "manufacturing_document": POWER_PLATFORM_DOCUMENT_NAME,
        "manufacturing_packaging": PORTAL,
        "printed_quantity": 1,
        "printed_quantity_scope": "One optional portal manufacture, only used by PORTAL configurations. No added print is installed in the illustrated direct-tether assembly.",
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
        "additional_hardware": {},
        "portal_additional_hardware": {"M2X8_BUTTON_HEAD": 2, "M2_HEX_NUT": 2},
        "size_mm": sizes,
        "size_check": print_size_check(
            [local.XLength, local.YLength, local.ZLength], sizes
        ),
        "platform_contract": power_mount.platform_contract(),
        "power_options": power_option_contract(),
        "context_scope": "Saved optional-installation context preserves the reused carrier and selected optical geometry independently of main CAD display properties. The battery is absent for tether power. Context shapes are not optional manufacturing parts or additional bought parts.",
    }


def _context_roles(main):
    registry = main.DesignRegistry
    return {
        obj.Name: role
        for category, role in (
            ("PrintedParts", "Printed"),
            ("HardwareParts", "Hardware"),
            ("ReferenceParts", "Reference"),
            ("TapeReferences", "Tape"),
            ("ClearanceVolumes", "Clearance"),
        )
        for obj in getattr(registry, category)
    }


def export_power_options(main_doc, output_dir=None):
    out = Path(output_dir or OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    doc = manufacturing = None
    try:
        doc = power_mount.create_option_document(main_doc)
        context = create_group(
            doc, "AssemblyContext", "REFERENCE | installed optional arrangement"
        )
        roles = _context_roles(main_doc)
        for name, shape in _installation_context(
            main_doc, power_mount.DEFAULT_PLAN
        ).items():
            obj = create_reference(
                doc,
                context,
                "Context_" + name,
                name,
                shape,
                "Copied optional installation context; not an added print or purchased part",
            )
            set_property(obj, "SourceObjectName", name)
            set_property(obj, "SourceRole", roles[name])
            obj.Label = "CONTEXT | " + name
            if App.GuiUp:
                obj.ViewObject.Visibility = False
        set_property(doc.PowerOptionModule, "SourceFingerprint", source_fingerprint())
        doc.recompute()
        native_path = out / ARTIFACT_NAMES[0]
        doc.saveAs(str(native_path))
        App.closeDocument(doc.Name)
        doc = App.openDocument(str(native_path))
        # A separate manufacturing source keeps the retained portal out of the
        # installed direct-tether inventory and gives its exports an auditable BRep.
        manufacturing = App.newDocument("PowerPortalManufacturing")
        manufacturing.Label = print_label(
            "Optional portal | PORTAL configurations only"
        )
        group = create_group(
            manufacturing, "PowerPrintSource", "Optional portal print source"
        )
        set_property(group, "PowerPackaging", PORTAL)
        set_property(group, "SourceFingerprint", source_fingerprint())
        platform = create_printed_part(
            manufacturing,
            group,
            "PowerPlatform",
            "OPTIONAL PRINT | raised power portal",
            power_mount.platform_shape().copy(),
            App.Rotation(App.Vector(1, 0, 0), 180),
            power_mount.platform_contract()["support_scope"],
        )
        set_print_sku(platform, "PowerPlatform")
        manufacturing.recompute()
        print_path = out / POWER_PLATFORM_DOCUMENT_NAME
        manufacturing.saveAs(str(print_path))
        App.closeDocument(manufacturing.Name)
        manufacturing = App.openDocument(str(print_path))
        shape = print_shape(manufacturing.PowerPlatform)
        mesh_from_shape(shape).write(str(out / ARTIFACT_NAMES[1]))
        shape.exportStep(str(out / ARTIFACT_NAMES[2]))
        (out / ARTIFACT_NAMES[3]).write_text(
            json.dumps(_manifest(doc, manufacturing), indent=2) + "\n"
        )
        return {"artifacts": list(ARTIFACT_NAMES), "optional_only": True}
    finally:
        for opened in (doc, manufacturing):
            if opened is not None:
                App.closeDocument(opened.Name)


def _same_shape(first, second):
    result = geometry_comparison(first, second)
    return comparison_passed(result, TOL)


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
    option = manufacturing = None
    try:
        option = App.openDocument(str(out / ARTIFACT_NAMES[0]))
        manufacturing = App.openDocument(str(out / POWER_PLATFORM_DOCUMENT_NAME))
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
        report["optical_attachment_matches"] = json.loads(
            option.PowerOptionModule.OpticalAttachment
        ) == _optical_attachment_description(main.getObject("OpticalFlowModule"))
        report["option_pose_matches"] = group.Placement.isSame(pose, TOL)
        report["option_source_matches"] = (
            str(group.SourceFingerprint) == source_fingerprint()
        )
        report["option_selection_matches"] = (
            str(group.PowerPlan) == power_mount.DEFAULT_PLAN
            and str(group.StackHostName) == power_mount.DEFAULT_HOST
            and str(group.PowerPackaging) == power_mount.DEFAULT_PACKAGING
        )
        report["option_contract_matches"] = json.loads(
            group.PowerPlatformContract
        ) == json.loads(json.dumps(power_mount.platform_contract()))
        report["power_plan_contract_matches"] = json.loads(
            group.PowerPlanContract
        ) == json.loads(json.dumps(get_power_plan(power_mount.DEFAULT_PLAN).contract()))
        report["installation_contract_matches"] = json.loads(
            group.PowerInstallationContract
        ) == json.loads(
            json.dumps(
                power_mount.installation_contract(
                    power_mount.DEFAULT_PLAN, power_mount.DEFAULT_PACKAGING
                )
            )
        )
        report["native_shape_checks"] = {
            name: option.getObject(name) is not None
            and option.getObject(name).getParentGeoFeatureGroup() == group
            and _same_shape(option.getObject(name).Shape, shape)
            for name, shape in expected.items()
        }
        report["native_inventory_matches"] = {
            obj.Name for obj in group.Group if hasattr(obj, "Shape")
        } == set(expected)
        main_shapes = _installation_context(main, power_mount.DEFAULT_PLAN)
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
        ] == []
        print_part = manufacturing.getObject("PowerPlatform")
        report["manufacturing_source_matches"] = (
            print_part is not None
            and str(getattr(print_part, "PrintSKU", "")) == "PowerPlatform"
            and print_metadata_matches(print_part)
            and print_part.getParentGeoFeatureGroup() == manufacturing.PowerPrintSource
            and str(manufacturing.PowerPrintSource.PowerPackaging) == PORTAL
            and str(manufacturing.PowerPrintSource.SourceFingerprint)
            == source_fingerprint()
            and _same_shape(print_part.Shape, power_mount.platform_shape())
            and [
                obj.Name
                for obj in manufacturing.Objects
                if obj.isDerivedFrom("Part::Feature") and not obj.Shape.isNull()
            ]
            == ["PowerPlatform"]
            and [
                obj.Name
                for obj in manufacturing.Objects
                if getattr(obj, "PrintPart", False)
            ]
            == ["PowerPlatform"]
        )
        report["context_inventory_matches"] = set(context) == set(main_shapes)
        roles = _context_roles(main)
        report["context_roles_match"] = report["context_inventory_matches"] and all(
            getattr(context[name], "SourceRole", None) == roles[name]
            for name in main_shapes
        )
        report["context_shapes_match"] = report["context_inventory_matches"] and all(
            _same_shape(world_shape(context[name]), shape)
            for name, shape in main_shapes.items()
        )
        actual_manifest = json.loads((out / ARTIFACT_NAMES[3]).read_text())
        report["manifest_matches"] = actual_manifest == json.loads(
            json.dumps(_manifest(option, manufacturing))
        )
        report["print_size_passed"] = bool(
            actual_manifest.get("size_check", {}).get("passed")
        )
        from .validation.equipment import carrier_opening_checks

        report["plate_openings"] = carrier_opening_checks(
            print_part.Shape,
            bottom=power_mount.DECK_BOTTOM_Z,
            thickness=power_mount.DECK_THICKNESS_MM,
            through_bottom=0.0,
            through_depth=stack_interface.TOP_BEAM_THICKNESS,
            centre_hole_diameter=mounting_plate.CENTRE_HOLE_DIAMETER_MM,
        )
        expected_print = print_shape(print_part)
        step = Part.Shape()
        step.read(str(out / ARTIFACT_NAMES[2]))
        report["step_comparison"] = print_solid_comparison(expected_print, step, TOL)
        mesh = Mesh.Mesh(str(out / ARTIFACT_NAMES[1]))
        report["mesh_checks"] = mesh_checks(expected_print, mesh)
        report["mesh_surface_comparison"] = compare_mesh_surfaces(
            mesh, mesh_from_shape(expected_print)
        )
        report["mesh_matches_native_tessellation"] = report["mesh_surface_comparison"][
            "passed"
        ]
        report["configuration_screen"] = screen_configurations(main)
        report["illustrated_configuration_screen"] = screen_configurations(main)
        report["illustrated_configuration_clear"] = report[
            "illustrated_configuration_screen"
        ].get("default_configuration_clear", False)
        report["source_sha256_after"] = file_sha256(source)
        report["artifact_hashes"] = {
            name: file_sha256(out / name) for name in ARTIFACT_NAMES
        }
        report["read_only_artifacts"] = (
            report["source_sha256"] == report["source_sha256_after"]
            and report["artifact_hashes_before"] == report["artifact_hashes"]
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
                    "optical_attachment_matches",
                    "illustrated_configuration_clear",
                    "main_optional_contract_matches",
                    "option_source_matches",
                    "option_selection_matches",
                    "option_contract_matches",
                    "power_plan_contract_matches",
                    "installation_contract_matches",
                    "manufacturing_source_matches",
                    "native_inventory_matches",
                    "context_names_unique",
                    "complete_shape_inventory_matches",
                    "optional_print_inventory_matches",
                    "context_inventory_matches",
                    "context_roles_match",
                    "context_shapes_match",
                    "manifest_matches",
                    "print_size_passed",
                    "mesh_matches_native_tessellation",
                    "read_only_artifacts",
                    "source_code_unchanged",
                )
            )
            and all(report["native_shape_checks"].values())
            and report["plate_openings"]["passed"]
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
        if manufacturing is not None:
            App.closeDocument(manufacturing.Name)
        App.closeDocument(main.Name)
    (out / REPORT_NAME).write_text(json.dumps(report, indent=2) + "\n")
    return report
