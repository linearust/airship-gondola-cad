"""Read-only audit of service reservations, bought hardware, and source metadata."""

import json
import os
from collections import Counter
from pathlib import Path

import FreeCAD as App
import Part

from gondola.cad import (
    world_shape,
)
from gondola.config import ARTIFACT_SCHEMA_VERSION, ARTIFACT_STEM, OUTPUT_DIR, REPO_ROOT
from gondola.contracts import equipment_interfaces as interfaces
from gondola.contracts import stack_adapter as adapter_specification
from gondola.contracts.design import (
    EXPECTED_INVENTORY,
    FC_INSTALLATION_LOCAL_YAW_DEG,
    HARDWARE_MATERIALS,
    MODULE_STATIONS,
    PURCHASED_HARDWARE_QUANTITIES,
    WIRING_PURCHASE_PLAN,
    hardware_bom_scope,
)
from gondola.contracts.equipment_options import (
    get_navigation_profile,
    get_radio_profile,
)
from gondola.parts import equipment_envelopes as devices
from gondola.parts import equipment_layout as layout
from gondola.parts import equipment_mounts as mounts
from gondola.parts import stack_interface, stock_adapter
from gondola.print_export import geometry_comparison
from gondola.procurement import (
    PURCHASE_METADATA_FIELDS,
    REQUIRED_PURCHASE_FIELDS,
    purchase_code,
    purchase_evidence,
)
from gondola.provenance import file_sha256, source_fingerprint

from . import wiring as wiring_validation
from .geometry import (
    intersection_volume,
    local_shape,
    translation_sweep,
)
from .optical import mtf_sensor_check

TOL = 1e-6


def _comparison_passed(comparison):
    return all(
        comparison[key] < TOL
        for key in ("difference_mm3", "bounds_difference_mm", "volume_difference_mm3")
    )


def _in_parent_frame(shape, parent):
    result = shape.copy()
    result.Placement = parent.getGlobalPlacement().multiply(result.Placement)
    return result


def fc_installation_check(doc):
    """Check FC identity and orientation beyond its symmetric reference solid."""
    board = doc.getObject("ModuleFCEnvelope")
    parent = doc.getObject("ElectronicsEquipmentModule")
    station = next(
        station
        for station in MODULE_STATIONS
        if station.object_name == "ElectronicsEquipmentModule"
    )
    if board is None or parent is None:
        return {"passed": False, "error": "Missing FC or electronics carrier"}
    intended_local = App.Placement(
        App.Vector(*mounts.FC_CENTRE_XY, devices.FC_BOTTOM_Z),
        App.Rotation(
            App.Vector(0, 0, 1),
            mounts.FC_ROTATION_DEG + FC_INSTALLATION_LOCAL_YAW_DEG,
        ),
    )
    native_pose_matches = board.Placement.isSame(intended_local, TOL)
    expected_carrier_rotation = App.Rotation(App.Vector(0, 0, 1), station.yaw_deg)
    carrier_rotation_matches = parent.Placement.Rotation.isSame(
        expected_carrier_rotation, TOL
    )
    metadata_matches = (
        "InstallationYawInCarrier" in board.PropertiesList
        and abs(float(board.InstallationYawInCarrier) - FC_INSTALLATION_LOCAL_YAW_DEG)
        < TOL
    )
    try:
        contract_matches = json.loads(
            str(board.FlightControllerContract)
        ) == json.loads(json.dumps(interfaces.flight_controller_contract()))
    except (AttributeError, TypeError, ValueError):
        contract_matches = False
    correct_parent = board.getParentGeoFeatureGroup() == parent
    return {
        "installation_turn_in_carrier_deg": FC_INSTALLATION_LOCAL_YAW_DEG,
        "carrier_yaw_deg": station.yaw_deg,
        "native_board_placement_matches": native_pose_matches,
        "carrier_rotation_matches": carrier_rotation_matches,
        "native_installation_marker_matches": metadata_matches,
        "native_flight_controller_contract_matches": contract_matches,
        "board_parent_matches": correct_parent,
        "scope": "Native design orientation relative to the previous FC installation only. The square envelope cannot identify the physical board arrow; verify the received FC orientation and firmware configuration during assembly.",
        "passed": native_pose_matches
        and carrier_rotation_matches
        and metadata_matches
        and contract_matches
        and correct_parent,
    }


def stock_adapter_check(doc):
    """Audit four bought plates and exact fasteners, without certifying laminate."""
    from gondola.parts import rail

    registry = doc.DesignRegistry
    stack = doc.getObject("OpticalFlowModule")
    with_portal = (
        stack is not None
        and stack.getParentGeoFeatureGroup()
        == doc.getObject("ElectronicsEquipmentModule")
    )
    expected = stock_adapter.hardware_shapes(with_portal=with_portal)
    rows_by_name = {}
    for row in stock_adapter.joint_specs():
        rows_by_name[row["plate_name"]] = (
            adapter_specification.PART_SKU,
            row["parent_name"],
        )
        for clamp in rail.clamp_rows(
            plate_thickness_mm=row["plate_thickness_mm"],
            centre_xy_mm=row["local_centre_xy"],
            parent_z_mm=row["parent_z_mm"],
        ):
            name = row["clamp_prefix"] + clamp["suffix"]
            expected[name] = clamp["shape"]
            rows_by_name[name] = (clamp["sku"], row["parent_name"])
    for row in stock_adapter.fc_hardware_rows(with_portal):
        rows_by_name[row["name"]] = (row["sku"], "ElectronicsEquipmentModule")
    purchased = list(registry.HardwareParts)
    printed = list(registry.PrintedParts)
    rows = []
    for name, shape in expected.items():
        obj = doc.getObject(name)
        if obj is None:
            rows.append(
                {
                    "object": name,
                    "passed": False,
                    "error": "Missing bought interface part",
                }
            )
            continue
        # Factory shapes may retain their parent-local translation as native
        # Placement. Stripping it would compare a screw at the origin instead
        # of auditing the actual installed axis.
        comparison = geometry_comparison(obj.Shape.copy(), shape)
        sku, parent_name = rows_by_name[name]
        identity = (
            obj.getParentGeoFeatureGroup() == doc.getObject(parent_name)
            and purchased.count(obj) == 1
            and obj not in printed
            and not bool(getattr(obj, "PrintPart", True))
            and str(getattr(obj, "HardwareSKU", "")) == sku
        )
        rows.append(
            {
                "object": name,
                "source_comparison": comparison,
                "purchased_identity_matches": identity,
                "passed": identity and _comparison_passed(comparison),
            }
        )
    plate_checks = []
    bores = []
    for row in stock_adapter.joint_specs():
        obj = doc.getObject(row["plate_name"])
        if obj is None:
            plate_checks.append({"object": row["plate_name"], "passed": False})
            continue
        kind = row["kind"]
        try:
            contract = json.loads(obj.StockAdapterContract) == json.loads(
                json.dumps(
                    stock_adapter.mounting_contract(
                        kind, with_portal and kind == "electronics"
                    )
                )
            )
            contract &= json.loads(obj.MountContract) == json.loads(
                json.dumps(mounts.mount_contract(kind))
            )
            contract &= str(obj.MountKind) == kind
            contract &= (
                not obj.ExactContourModeled
                and not obj.PhysicalFitVerified
                and not obj.MountingStackVerified
            )
            contract &= (
                abs(float(obj.ReferenceMassGrams) - adapter_specification.LISTED_MASS_G)
                < TOL
            )
            contract &= (
                str(obj.ReferenceMassSource) == adapter_specification.PRODUCT_URL
            )
            contract &= abs(float(obj.EquipmentFaceZ) - stock_adapter.PLATE_TOP_Z) < TOL
            contract &= bool(obj.FCPortalInstalled) == (
                with_portal and kind == "electronics"
            )
        except (AttributeError, TypeError, ValueError):
            contract = False
        plate_checks.append(
            {
                "object": obj.Name,
                "nominal_metadata_and_uncertainty_match": contract,
                "passed": contract,
            }
        )
        for hole in mounts.plate_hole_rows(kind):
            if hole["plate"] != obj.Name:
                continue
            probe = Part.makeCylinder(
                hole["diameter_mm"] / 2,
                adapter_specification.THICKNESS_MM,
                App.Vector(*hole["centre_xy_mm"], stock_adapter.PLATE_BOTTOM_Z),
            )
            blocked = intersection_volume(local_shape(obj), probe)
            bores.append(
                {
                    "object": obj.Name,
                    "centre_xy_mm": hole["centre_xy_mm"],
                    "obstruction_mm3": blocked,
                    "passed": blocked < TOL,
                }
            )
    expected_names = {row["plate_name"] for row in stock_adapter.joint_specs()}
    registered_names = {
        obj.Name
        for obj in purchased
        if getattr(obj, "HardwareSKU", "") == adapter_specification.PART_SKU
    }
    obsolete = [
        obj.Name
        for obj in doc.Objects
        if obj.Name in ("BatteryMount", "ElectronicsMount", "AccessoryMount")
        or obj.Name.startswith("FCAdapterSaddle")
    ]
    passed = (
        expected_names == registered_names
        and not obsolete
        and all(row["passed"] for row in rows + plate_checks + bores)
    )
    allowed = (
        [
            name
            for name, (_, parent) in rows_by_name.items()
            if parent == "ElectronicsEquipmentModule"
            and name != stock_adapter.PLATE_OBJECT_NAME
        ]
        if passed
        else []
    )
    return {
        "purchased_parts": rows,
        "plate_metadata": plate_checks,
        "nominal_purchased_bores": bores,
        "obsolete_printed_mounts_or_saddle_parts": obsolete,
        "registered_carbon_names": sorted(registered_names),
        "fc_portal_selected": with_portal,
        "allowed_underbody_clamp_fasteners": allowed,
        "exact_carbon_contact_qualified": False,
        "scope": "Four bought carbon envelopes, their direct rail clamps and independent FC studs. Exact source/identity checks do not establish unknown cutout/contact area, laminate strength, adhesive support, insulation or complete upper FC retention.",
        "passed": passed,
    }


def device_service_check(doc, name, physical_objects, physical_shapes_by_name):
    """Sweep every successive service segment with carbon, fixed portal and installed obstacles retained."""
    obj = doc.getObject(name)
    parent = obj.getParentGeoFeatureGroup()
    stack = doc.getObject("OpticalFlowModule")
    release_head = stack is not None and stack.getParentGeoFeatureGroup() == parent
    removed = {
        other.Name
        for other in physical_objects
        if release_head and stack_interface.is_removable_head_part(other, stack)
    }
    staged = name in ("ModuleFCEnvelope", "ModuleBatteryEnvelope")
    excluded = set()
    local_segments = (
        stack_interface.device_removal_segments(name)
        if staged
        else (layout.device_removal_vector(name),)
    )
    actual_body = physical_shapes_by_name[name]
    proxy = stack_interface.device_removal_shape(obj) if staged else actual_body.copy()
    outside_proxy = abs(actual_body.cut(proxy).Volume)
    moving = actual_body.copy() if name == "ModuleFCEnvelope" else proxy.copy()
    # This reserve is an alternative size of the same battery, not a second pack.
    alternative_references = (
        {"MaximumBatteryEnvelope"} if name == "ModuleBatteryEnvelope" else set()
    )
    segments = []
    all_hits = set()
    for index, local_vector in enumerate(local_segments):
        world_vector = parent.getGlobalPlacement().Rotation.multVec(
            App.Vector(*local_vector)
        )
        swept, method = translation_sweep(moving, tuple(world_vector))
        hits = [
            other.Name
            for other in physical_objects
            if other.Name != name
            and other.Name not in removed
            and other.Name not in excluded
            and other.Name not in alternative_references
            and intersection_volume(swept, physical_shapes_by_name[other.Name]) > TOL
        ]
        all_hits.update(hits)
        segments.append(
            {
                "index": index,
                "local_vector_mm": tuple(local_vector),
                "world_vector_mm": tuple(world_vector),
                "method": method,
                "collisions": hits,
                "passed": not hits,
            }
        )
        proxy.translate(world_vector)
        moving = proxy.copy()
    return {
        "device": name,
        "local_removal_vector_mm": tuple(local_segments[0])
        if len(local_segments) == 1
        else None,
        "local_removal_segments_mm": [tuple(vector) for vector in local_segments],
        "segments": segments,
        "actual_device_outside_service_proxy_mm3": outside_proxy,
        "alternative_same_device_reserves_excluded": sorted(alternative_references),
        "bench_access_required": False,
        "service_collision_scope": "Installed assembly; fixed portal, carbon and other equipment retained",
        "off_carrier_parts_excluded_for_bench_service": sorted(excluded),
        "optical_head_must_be_removed_first": release_head,
        "complete_optical_tower_removed": False,
        "fixed_portal_and_carbon_remain_obstacles": True,
        "temporarily_removed_head_parts": sorted(removed),
        "prerequisite": "Disconnect leads and release device retention. Remove the movable optical head first when this is its host, retaining the fixed portal, carbon and every other installed module. Remove the covering device before accessing its top rail screws; no detached-carrier prerequisite is used to bypass installed obstacles. Bare-device paths do not qualify a connected harness.",
        "collisions": sorted(all_hits),
        "passed": not all_hits and outside_proxy < TOL,
    }


def mounting_check(doc):
    """Source identity and geometric reservations; physical contact stays pending."""
    from gondola.parts import optical_mount
    from gondola.parts import wiring_reserves as wiring_clearances

    from .equipment_options import adhesive_support_check

    registry = doc.DesignRegistry
    physical_objects = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    physical = {obj.Name: world_shape(obj) for obj in physical_objects}
    stock = stock_adapter_check(doc)
    expected_supports = {row["plate_name"] for row in stock_adapter.joint_specs()}
    registered = [obj.Name for obj in registry.EquipmentMounts]
    support_identity = set(registered) == expected_supports and len(registered) == len(
        expected_supports
    )
    nav, radio = get_navigation_profile(), get_radio_profile()
    device_specs = (
        (
            "ModuleFCEnvelope",
            "ElectronicsEquipmentModule",
            devices.fc_envelope_shape(),
            "StockFCAdapter",
            mounts.FC_WIRING_CLEARANCE,
        ),
        (
            "ModulePASEnvelope",
            "AccessoryEquipmentModule",
            devices.navigation_envelope_shape(nav),
            "StockNavigationAdapter",
            mounts.ADHESIVE_ALLOWANCE,
        ),
        (
            "ModuleRadioEnvelope",
            "AccessoryEquipmentModule",
            devices.radio_envelope_shape(radio),
            "StockRadioAdapter",
            mounts.ADHESIVE_ALLOWANCE,
        ),
    )
    device_rows = []
    gaps = []
    for name, parent_name, source_shape, support_name, required in device_specs:
        obj, parent = doc.getObject(name), doc.getObject(parent_name)
        if obj is None or parent is None:
            device_rows.append(
                {"device": name, "passed": False, "error": "Missing device/parent"}
            )
            continue
        comparison = geometry_comparison(
            world_shape(obj), _in_parent_frame(source_shape, parent)
        )
        same_parent = (
            obj.getParentGeoFeatureGroup() == parent
            and doc.getObject(support_name).getParentGeoFeatureGroup() == parent
        )
        hits = [
            other.Name
            for other in physical_objects
            if other != obj
            and intersection_volume(physical[name], physical[other.Name]) > TOL
        ]
        device_rows.append(
            {
                "device": name,
                "source_comparison": comparison,
                "device_parent_matches_plate": same_parent,
                "physical_collisions": hits,
                "passed": same_parent and _comparison_passed(comparison) and not hits,
            }
        )
        local = physical[name].copy()
        local.Placement = (
            parent.getGlobalPlacement().inverse().multiply(local.Placement)
        )
        gap = local.BoundBox.ZMin - mounts.SUPPORT_FACE_Z
        gaps.append(
            {
                "device": name,
                "measured_underbody_gap_mm": gap,
                "required_underbody_gap_mm": required,
                "scope": "Body-to-carbon datum; the separate wire-strip and collision checks inspect usable free space between intentional fastener/support columns.",
                "passed": abs(gap - required) < TOL,
            }
        )
    adhesive = []
    device_by_role = {
        "battery": "ModuleBatteryEnvelope",
        "selected navigation module": "ModulePASEnvelope",
        "LR24-F-Mini": "ModuleRadioEnvelope",
    }
    for kind in stock_adapter.MOUNT_KINDS:
        for row in mounts.adhesive_reservations(kind):
            plate = doc.getObject(row["plate"])
            name = device_by_role[row["device"]]
            body = physical[name].copy()
            body.Placement = (
                plate.getParentGeoFeatureGroup()
                .getGlobalPlacement()
                .inverse()
                .multiply(body.Placement)
            )
            adhesive.append(
                {
                    "device": name,
                    **adhesive_support_check(
                        local_shape(plate), body, row["centre_xy_mm"], row["size_mm"]
                    ),
                }
            )
    reserve = doc.getObject("FCWiringClearanceReserve")
    wiring_report = {"passed": False, "error": "Missing FC reservation"}
    if reserve is not None:
        parent = doc.ElectronicsEquipmentModule
        actual = world_shape(reserve)
        comparison = geometry_comparison(
            actual,
            _in_parent_frame(wiring_clearances.reserve_shapes()[reserve.Name], parent),
        )
        hits = [
            obj.Name
            for obj in physical_objects
            if intersection_volume(actual, physical[obj.Name]) > TOL
        ]
        wire_core = _in_parent_frame(
            wiring_clearances.fc_underbody_reserve_shape(), parent
        )
        core_hits = [
            obj.Name
            for obj in physical_objects
            if intersection_volume(wire_core, physical[obj.Name]) > TOL
        ]
        wiring_report = {
            "source_comparison": comparison,
            "physical_collisions": hits,
            "underbody_strip_collisions": core_hits,
            "height_mm": mounts.FC_WIRING_CLEARANCE,
            "width_mm": mounts.FC_WIRING_CORRIDOR_WIDTH,
            "passed": reserve in registry.ClearanceVolumes
            and reserve not in registry.PrintedParts
            and reserve not in registry.HardwareParts
            and _comparison_passed(comparison)
            and not hits
            and not core_hits,
        }
    services = [
        device_service_check(doc, name, physical_objects, physical)
        for name in (
            "ModuleBatteryEnvelope",
            "ModuleFCEnvelope",
            "ModulePASEnvelope",
            "ModuleRadioEnvelope",
        )
    ]
    stack = doc.getObject("OpticalFlowModule")
    portal_identity = False
    if stack is not None:
        host = stack.getParentGeoFeatureGroup()
        portal = doc.getObject("OpticalMountBase")
        if (
            host is not None
            and host.Name in stack_interface.SUPPORTED_HOSTS
            and portal is not None
        ):
            compare = geometry_comparison(
                local_shape(portal), optical_mount.base_shape()
            )
            portal_identity = (
                str(getattr(stack, "HostPlateName", ""))
                == stack_interface.SUPPORTED_HOSTS[host.Name]
                and portal.getParentGeoFeatureGroup() == stack
                and portal in registry.PrintedParts
                and bool(portal.PrintPart)
                and _comparison_passed(compare)
            )
    pending = []
    for name, key in (
        ("ModuleFCEnvelope", "FC"),
        ("ModulePASEnvelope", nav.interface_key),
        ("ModuleRadioEnvelope", radio.interface_key),
        ("ModuleMTF02PEnvelope", stack.SensorModel if stack else ""),
    ):
        obj = doc.getObject(name)
        try:
            evidence = (
                json.loads(obj.MountingEvidence) == interfaces.MOUNTING_EVIDENCE[key]
            )
            connector = (
                json.loads(obj.ConnectorEvidence)
                == interfaces.DEVICE_CONNECTOR_EVIDENCE[key]
            )
            unverified = (
                not obj.MountingStackVerified
                and not obj.PCBHeightMeasured
                and not obj.InstalledConnectorFitVerified
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            evidence = connector = unverified = False
        pending.append(
            {
                "device": name,
                "evidence_matches": evidence,
                "connector_evidence_matches_sources": connector,
                "physical_stack_and_connector_fit_unverified": unverified,
                "passed": evidence and connector and unverified,
            }
        )
    fc = fc_installation_check(doc)
    passed = (
        support_identity
        and stock["passed"]
        and wiring_report["passed"]
        and portal_identity
        and fc["passed"]
        and all(
            row["passed"] for row in device_rows + gaps + adhesive + services + pending
        )
    )
    return {
        "bought_carbon_interfaces": stock,
        "four_bought_equipment_plates_registered": support_identity,
        "device_source_and_collision_checks": device_rows,
        "insulating_pad_reservations": adhesive,
        "underbody_clearance": gaps,
        "fc_wiring_corridor": wiring_report,
        "fc_installation": fc,
        "device_service": services,
        "separate_optical_portal_identity": portal_identity,
        "pending_device_mounting_evidence": pending,
        "physical_contact_verified": False,
        "limits": "CAD reservation/identity checks only. No continuous carbon adhesive area, P-AS bolt interface, laminate retention, foam compression or finished upper FC fastening is inferred. Device service precedes access to covered top rail-clamp screws.",
        "passed": passed,
    }


def hardware_check(doc, source):
    registry = doc.DesignRegistry
    sku_quantities = Counter(str(obj.HardwareSKU) for obj in registry.HardwareParts)
    materials_by_sku, material_checks = {}, []
    for obj in registry.HardwareParts:
        materials_by_sku.setdefault(str(obj.HardwareSKU), set()).add(
            str(obj.MaterialSelection)
        )
        expected = HARDWARE_MATERIALS.get(str(obj.HardwareSKU))
        material_checks.append(
            {
                "object": obj.Name,
                "material": str(obj.MaterialSelection),
                "passed": expected == str(obj.MaterialSelection),
            }
        )
    bom = json.loads((source.parent / (source.stem + "_hardware_bom.json")).read_text())
    bom_instance_names = [name for row in bom["items"] for name in row["instances"]]
    hardware_by_name = {obj.Name: obj for obj in registry.HardwareParts}
    bom_rows = []
    for row in bom["items"]:
        instances = [hardware_by_name.get(name) for name in row["instances"]]
        matched = bool(instances) and all(obj is not None for obj in instances)
        if matched:
            procurement_matches = all(
                field in row
                and all(
                    row[field] == str(getattr(obj, property_name, ""))
                    for obj in instances
                )
                and (field not in REQUIRED_PURCHASE_FIELDS or bool(row[field]))
                for field, property_name in PURCHASE_METADATA_FIELDS.items()
            )
            expected_material = HARDWARE_MATERIALS.get(row["sku"])
            matched = (
                procurement_matches
                and expected_material is not None
                and row.get("purchase_code")
                == purchase_code(row["sku"], expected_material)
                and all(
                    row.get(field) == values
                    for field, values in purchase_evidence(instances).items()
                )
                and row["quantity"] == len(instances)
                and all(
                    row["sku"] == str(obj.HardwareSKU)
                    and row["material"] == str(obj.MaterialSelection)
                    for obj in instances
                )
            )
        bom_rows.append({"sku": row["sku"], "matches_native_instances": matched})
    fingerprint = source_fingerprint()
    identity_matches = (
        bom.get("schema_version") == ARTIFACT_SCHEMA_VERSION
        and bom.get("source_fingerprint") == fingerprint
        and str(getattr(registry, "SourceFingerprint", "")) == fingerprint
    )
    return {
        "total_quantity": len(registry.HardwareParts),
        "unique_sku_count": len(sku_quantities),
        "sku_quantities": dict(sku_quantities),
        "materials_by_sku": {
            sku: sorted(values) for sku, values in materials_by_sku.items()
        },
        "material_checks": material_checks,
        "bom_source_identity_matches": identity_matches,
        "bom_purchase_scope_matches_contract": bom.get("purchase_scope")
        == hardware_bom_scope(),
        "bom_rows": bom_rows,
        "not_printed": all(
            obj not in registry.PrintedParts
            and not bool(getattr(obj, "PrintPart", False))
            for obj in registry.HardwareParts
        ),
        "bom_each_instance_exactly_once": len(bom_instance_names)
        == EXPECTED_INVENTORY["purchased_hardware"]
        and len(set(bom_instance_names)) == EXPECTED_INVENTORY["purchased_hardware"]
        and set(bom_instance_names) == {obj.Name for obj in registry.HardwareParts},
        "bom_stated_quantity": bom["purchased_hardware_quantity"],
        "bom_stated_unique_specs": bom["unique_purchase_spec_count"],
        "passed": dict(sku_quantities) == PURCHASED_HARDWARE_QUANTITIES
        and bom.get("purchase_scope") == hardware_bom_scope()
        and all(row["passed"] for row in material_checks)
        and identity_matches
        and all(row["matches_native_instances"] for row in bom_rows),
    }


def validate(source=None):
    from .equipment_options import compatibility_check

    fingerprint_before = source_fingerprint()
    source = (
        Path(source).resolve() if source else OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")
    )
    source_hash_before = file_sha256(source)
    bom_path = source.parent / (source.stem + "_hardware_bom.json")
    bom_hash_before = file_sha256(bom_path)
    doc = App.openDocument(str(source), hidden=True)
    try:
        registry = doc.DesignRegistry
        clearance_checks, reserve_pairs = wiring_validation.reserve_checks(doc)
        optical_report = mtf_sensor_check(doc)
        mounting_report = mounting_check(doc)
        options_report = compatibility_check(doc)
        hardware_report = hardware_check(doc, source)
        try:
            wiring_plan_matches = (
                json.loads(str(registry.WiringPurchasePlan)) == WIRING_PURCHASE_PLAN
            )
        except (AttributeError, TypeError, ValueError):
            wiring_plan_matches = False
        reference_sources = {}
        for name in (
            "ModulePASEnvelope",
            "ModuleRadioEnvelope",
            "ModuleMTF02PEnvelope",
        ):
            obj = doc.getObject(name)
            reference_sources[name] = {
                key: str(getattr(obj, key))
                for key in obj.PropertiesList
                if "Source" in key or key == "Notes"
            }
        report = {
            "source_file": os.path.relpath(source, REPO_ROOT),
            "source_sha256": source_hash_before,
            "hardware_bom_sha256_before": bom_hash_before,
            "source_fingerprint": fingerprint_before,
            "scope": "Read-only saved-file clearance and purchased-hardware audit. Temporary in-memory MTF optical-obstruction tilt probes are restored; the native file is never saved.",
            "actual_object_counts": {
                "printed": len(registry.PrintedParts),
                "hardware": len(registry.HardwareParts),
                "equipment_references": len(registry.ReferenceParts),
                "tape_references": len(registry.TapeReferences),
            },
            "reserve_checks": clearance_checks,
            "reserve_pair_checks": reserve_pairs,
            "mtf02p_sensor": optical_report,
            "equipment_mounts": mounting_report,
            "equipment_options": options_report,
            "hardware": hardware_report,
            "native_wiring_purchase_plan_matches_contract": wiring_plan_matches,
            "reference_sources": reference_sources,
            "limits": [
                "Connector catalog dimensions are retained evidence; reserved lanes do not verify installed PCB port datums, actual plug fit, withdrawal stroke or wire bends. The capacitor remains a provisional space allocation.",
                "The toroidal reserves are not proven wire routes, bend radii, strain relief or validated phase-lead slack over the bounded -180 to +180 degree output range.",
                "The optical stack can use either common host. Its400mm whole-face field is checked to cover modeled-gondola depth; lens datums, actual optical calibration, gravity alignment and cable slack remain unverified.",
                "No physical fit, electrical insulation/current capacity, clamp force or structural test was performed.",
            ],
        }
    finally:
        App.closeDocument(doc.Name)
    source_hash_after = file_sha256(source)
    report["source_sha256_after"] = source_hash_after
    report["source_unchanged"] = source_hash_before == source_hash_after
    report["hardware_bom_sha256_after"] = file_sha256(bom_path)
    report["hardware_bom_unchanged"] = (
        bom_hash_before == report["hardware_bom_sha256_after"]
    )
    report["source_code_unchanged"] = fingerprint_before == source_fingerprint()
    report["passed"] = (
        source_hash_before == source_hash_after
        and report["source_code_unchanged"]
        and report["hardware_bom_unchanged"]
        and optical_report["passed"]
        and mounting_report["passed"]
        and options_report["passed"]
        and all(row["passed"] for row in clearance_checks)
        and all(row["passed"] for row in reserve_pairs)
        and hardware_report["passed"]
        and wiring_plan_matches
        and hardware_report["not_printed"]
        and hardware_report["bom_each_instance_exactly_once"]
        and hardware_report["bom_stated_quantity"]
        == EXPECTED_INVENTORY["purchased_hardware"]
        and hardware_report["bom_stated_unique_specs"]
        == EXPECTED_INVENTORY["purchased_hardware_types"]
    )
    report_path = source.parent / (source.stem + "_equipment_validation.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "equipment_report": str(report_path),
                "passed": report["passed"],
                "source_unchanged": source_hash_before == source_hash_after,
            }
        ),
        flush=True,
    )
    return report
