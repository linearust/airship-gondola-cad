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
from gondola.parts import stack_interface
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


def mounting_pad_check(
    shape, centre, *, bottom, thickness, hole_diameter, pad_diameter
):
    """Measure the entire bearing annulus and bore, not a few points on a grid."""
    origin = App.Vector(centre[0], centre[1], bottom)
    bore = Part.makeCylinder(hole_diameter / 2, thickness, origin)
    annulus = Part.makeCylinder(pad_diameter / 2, thickness, origin).cut(bore)
    obstruction = intersection_volume(shape, bore)
    missing_material = annulus.cut(shape).Volume
    return {
        "centre_xy_mm": list(centre),
        "hole_diameter_mm": hole_diameter,
        "pad_diameter_mm": pad_diameter,
        "nominal_radial_wall_mm": (pad_diameter - hole_diameter) / 2,
        "bore_obstruction_mm3": obstruction,
        "missing_full_thickness_bearing_annulus_mm3": missing_material,
        "passed": obstruction < TOL
        and missing_material < TOL
        and (pad_diameter - hole_diameter) / 2 >= 1.5 - TOL,
    }


def mounting_check(doc):
    """Inspect saved supports, confirmed XY axes, free space and removal paths.

    Pending device fasteners, PCB bearing planes and compressed dampers are not
    modeled. These tests prove the printed interfaces and explicit reservations;
    they do not claim a completed, retained equipment assembly.
    """
    from gondola.parts import wiring_reserves as wiring_clearances

    from .equipment_options import adhesive_support_check

    registry = doc.DesignRegistry
    physical_objects = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    physical_shapes_by_name = {obj.Name: world_shape(obj) for obj in physical_objects}
    support_rows = []
    expected_supports = {name: kind for kind, name in mounts.MOUNT_NAMES.items()}
    for name, kind in expected_supports.items():
        obj = doc.getObject(name)
        if obj is None:
            support_rows.append({"object": name, "passed": False, "error": "missing"})
            continue
        shape = local_shape(obj)
        comparison = geometry_comparison(shape, mounts.mount_shape(kind))
        expected_contract = json.loads(json.dumps(mounts.mount_contract(kind)))
        try:
            contract_matches = json.loads(obj.MountContract) == expected_contract
        except (AttributeError, ValueError, TypeError):
            contract_matches = False
        no_posts = abs(shape.BoundBox.ZMax - mounts.SUPPORT_FACE_Z) < TOL
        unverified_stack = "MountingStackVerified" in obj.PropertiesList and not bool(
            obj.MountingStackVerified
        )
        support_rows.append(
            {
                "object": name,
                "kind": kind,
                "source_comparison": comparison,
                "contract_matches": contract_matches,
                "single_valid_solid": shape.isValid() and len(shape.Solids) == 1,
                "no_unverified_device_posts_above_support_face": no_posts,
                "mounting_stack_remains_unverified": unverified_stack,
                "passed": obj in registry.EquipmentMounts
                and obj in registry.PrintedParts
                and shape.isValid()
                and len(shape.Solids) == 1
                and _comparison_passed(comparison)
                and contract_matches
                and no_posts
                and unverified_stack,
            }
        )
    carriers = {
        "ModuleFCEnvelope": doc.getObject("ElectronicsMount"),
        "ModulePASEnvelope": doc.getObject("AccessoryMount"),
    }
    if any(carrier is None for carrier in carriers.values()):
        return {"supports": support_rows, "passed": False}
    mounting_rows = []
    navigation_profile = get_navigation_profile()
    radio_profile = get_radio_profile()
    device_specs = [
        (
            "ModuleFCEnvelope",
            mounts.FC_HOLE_CENTRES,
            interfaces.FC_HOLE_DIAMETER,
            devices.fc_envelope_shape,
        ),
    ]
    if navigation_profile.key == "PAS":
        device_specs.append(
            (
                "ModulePASEnvelope",
                mounts.PAS_HOLE_CENTRES,
                interfaces.PAS_HOLE_DIAMETER,
                devices.navigation_envelope_shape,
            ),
        )
    for name, centres, device_hole_diameter, factory in device_specs:
        carrier = carriers[name]
        carrier_shape = local_shape(carrier)
        parent = carrier.getParentGeoFeatureGroup()
        if name == "ModuleFCEnvelope":
            rotation = App.Rotation(App.Vector(0, 0, 1), mounts.FC_ROTATION_DEG)
            published_hole_axes = [
                rotation.multVec(App.Vector(x, y, 0))
                + App.Vector(*mounts.FC_CENTRE_XY, 0)
                for x, y in interfaces.FC_HOLE_CENTRES
            ]
        else:
            published_hole_axes = [
                App.Vector(
                    x + mounts.NAVIGATION_CENTRE_XY[0],
                    y + mounts.NAVIGATION_CENTRE_XY[1],
                    0,
                )
                for x, y in interfaces.PAS_HOLE_CENTRES
            ]
        axes_match = len(centres) == len(published_hole_axes) and all(
            min(
                (App.Vector(*centre, 0) - expected).Length
                for expected in published_hole_axes
            )
            < TOL
            for centre in centres
        )
        obj = doc.getObject(name)
        body = physical_shapes_by_name[name]
        comparison = geometry_comparison(body, _in_parent_frame(factory(), parent))
        bounds = body.optimalBoundingBox(False, False)
        holes = []
        for centre in centres:
            pad = mounting_pad_check(
                carrier_shape,
                centre,
                bottom=mounts.DECK_BOTTOM_Z,
                thickness=mounts.DECK_THICKNESS,
                hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
                pad_diameter=mounts.MOUNT_PAD_DIAMETER,
            )
            world_axis = parent.getGlobalPlacement().multVec(App.Vector(*centre, 0))
            axis_probe = Part.makeCylinder(
                device_hole_diameter / 2,
                bounds.ZLength + 2,
                App.Vector(world_axis.x, world_axis.y, bounds.ZMin - 1),
            )
            obstruction = intersection_volume(body, axis_probe)
            pad["device_hole_diameter_mm"] = device_hole_diameter
            pad["device_hole_axis_obstruction_mm3"] = obstruction
            pad["passed"] &= obstruction < TOL
            holes.append(pad)
        mounting_rows.append(
            {
                "device": name,
                "confirmed_hole_count": len(centres),
                "mount_axes_match_published_device_pattern": axes_match,
                "device_source_comparison": comparison,
                "carrier": carrier.Name,
                "device_parent_matches_carrier": obj.getParentGeoFeatureGroup()
                == parent,
                "holes": holes,
                "passed": axes_match
                and _comparison_passed(comparison)
                and obj.getParentGeoFeatureGroup() == parent
                and all(row["passed"] for row in holes),
            }
        )
    adhesive_rows = []
    adhesive_specs = [
        ("BatteryMount", "ModuleBatteryEnvelope", (0, 0), mounts.BATTERY_DECK_SIZE),
        (
            "AccessoryMount",
            "ModuleRadioEnvelope",
            mounts.RADIO_CENTRE_XY,
            mounts.RADIO_ADHESIVE_SIZE,
        ),
    ]
    if navigation_profile.key != "PAS":
        adhesive_specs.append(
            (
                "AccessoryMount",
                "ModulePASEnvelope",
                mounts.NAVIGATION_CENTRE_XY,
                mounts.GPS_ADHESIVE_SIZE,
            )
        )
    for mount_name, device_name, centre, size in adhesive_specs:
        support = doc.getObject(mount_name)
        owner = support.getParentGeoFeatureGroup()
        device_local = physical_shapes_by_name[device_name].copy()
        device_local.Placement = (
            owner.getGlobalPlacement().inverse().multiply(device_local.Placement)
        )
        adhesive_rows.append(
            {
                "device": device_name,
                **adhesive_support_check(
                    local_shape(support), device_local, centre, size
                ),
            }
        )
    free_height_rows = []
    for name, expected_gap in (
        ("ModuleFCEnvelope", mounts.FC_WIRING_CLEARANCE),
        (
            "ModulePASEnvelope",
            layout.navigation_bottom(navigation_profile) - mounts.SUPPORT_FACE_Z,
        ),
    ):
        parent = carriers[name].getParentGeoFeatureGroup()
        bounds = physical_shapes_by_name[name].optimalBoundingBox(False, False)
        support_top = (
            parent.getGlobalPlacement()
            .multVec(App.Vector(0, 0, mounts.SUPPORT_FACE_Z))
            .z
        )
        gap = bounds.ZMin - support_top
        # Preserve the complete device rectangle in its actual rotated frame;
        # a world bounding box would falsely occupy the FC's empty corners.
        dimensions = (
            interfaces.FC_SIZE_MM
            if name == "ModuleFCEnvelope"
            else navigation_profile.size_mm
        )
        centre = (
            mounts.FC_CENTRE_XY
            if name == "ModuleFCEnvelope"
            else layout.navigation_centre()
        )
        space = Part.makeBox(
            dimensions[0],
            dimensions[1],
            expected_gap,
            App.Vector(-dimensions[0] / 2, -dimensions[1] / 2, mounts.SUPPORT_FACE_Z),
        )
        if name == "ModuleFCEnvelope":
            space.rotate(App.Vector(), App.Vector(0, 0, 1), mounts.FC_ROTATION_DEG)
        space.translate(App.Vector(*centre, 0))
        space = _in_parent_frame(space, parent)
        hits = [
            {
                "object": other.Name,
                "intersection_mm3": intersection_volume(
                    space, physical_shapes_by_name[other.Name]
                ),
            }
            for other in physical_objects
            if intersection_volume(space, physical_shapes_by_name[other.Name]) > TOL
        ]
        free_height_rows.append(
            {
                "device": name,
                "measured_underbody_gap_mm": gap,
                "required_underbody_gap_mm": expected_gap,
                "full_underbody_reservation_collisions": hits,
                "passed": abs(gap - expected_gap) < TOL and not hits,
            }
        )
    reserve = doc.getObject("FCWiringClearanceReserve")
    parent = doc.ElectronicsEquipmentModule
    wiring_report = {"passed": False, "error": "missing FC wiring corridor"}
    if reserve is not None:
        actual = world_shape(reserve)
        comparison = geometry_comparison(
            actual,
            _in_parent_frame(
                wiring_clearances.reserve_shapes()["FCWiringClearanceReserve"], parent
            ),
        )
        hits = [
            obj.Name
            for obj in physical_objects
            if intersection_volume(actual, physical_shapes_by_name[obj.Name]) > TOL
        ]
        local_reserve = actual.copy()
        local_reserve.Placement = (
            parent.getGlobalPlacement().inverse().multiply(local_reserve.Placement)
        )
        axis_distances = []
        for x, y in mounts.FC_HOLE_CENTRES:
            axis = Part.makeLine(
                App.Vector(x, y, mounts.SUPPORT_FACE_Z),
                App.Vector(x, y, mounts.SUPPORT_FACE_Z + mounts.FC_WIRING_CLEARANCE),
            )
            distance = local_reserve.distToShape(axis)[0]
            axis_distances.append(
                {
                    "mount_axis_xy_mm": [x, y],
                    "distance_mm": distance,
                    "passed": distance >= 5.0 - TOL,
                }
            )
        wiring_report = {
            "source_comparison": comparison,
            "physical_collisions": hits,
            "clearance_from_confirmed_mount_axes": axis_distances,
            "scope": "Connected eight-mm underbody corridor, peripheral housing band and two planning exit bends. Future damper/spacer envelopes, exact plugged leads and qualified cable bend radii require actual dimensions.",
            "passed": reserve in registry.ClearanceVolumes
            and reserve not in registry.PrintedParts
            and reserve not in registry.HardwareParts
            and _comparison_passed(comparison)
            and not hits
            and all(row["passed"] for row in axis_distances),
        }
    service_rows = []
    for name in (
        "ModuleBatteryEnvelope",
        "ModuleFCEnvelope",
        "ModulePASEnvelope",
        "ModuleRadioEnvelope",
    ):
        sweep, sweep_method = translation_sweep(
            physical_shapes_by_name[name], (0, 0, 32)
        )
        optical_group = doc.getObject("OpticalFlowModule")
        device_parent = doc.getObject(name).getParentGeoFeatureGroup()
        release_head = (
            optical_group is not None
            and optical_group.getParentGeoFeatureGroup() == device_parent
        )
        removed_head_names = {
            obj.Name
            for obj in physical_objects
            if release_head
            and stack_interface.is_removable_head_part(obj, optical_group)
        }
        hits = [
            obj.Name
            for obj in physical_objects
            if obj.Name != name
            and obj.Name not in removed_head_names
            and intersection_volume(sweep, physical_shapes_by_name[obj.Name]) > TOL
        ]
        service_rows.append(
            {
                "device": name,
                "upward_travel_mm": 32,
                "optical_head_must_be_removed_first": release_head,
                "complete_optical_tower_removed": release_head,
                "temporarily_removed_head_parts": sorted(removed_head_names),
                "method": sweep_method,
                "prerequisite": "Disconnect leads and release device retention. When this carrier hosts the optical stack, detach the carrier from the rail for bench access, support the tower, remove both foot nuts and withdraw both foot screws downward before lifting the complete tower along optical+Z. The balloon is not modeled, so in-place underside access is not established. Bare-device path, not a connected harness.",
                "collisions": hits,
                "passed": not hits,
            }
        )
    evidence_matches = all(
        json.loads(str(carrier.MountingEvidence)) == interfaces.MOUNTING_EVIDENCE
        for carrier in carriers.values()
    )
    pending_metadata = []
    for name, key in (
        ("ModuleFCEnvelope", "FC"),
        ("ModulePASEnvelope", navigation_profile.interface_key),
        ("ModuleRadioEnvelope", radio_profile.interface_key),
        ("ModuleMTF02PEnvelope", doc.OpticalFlowModule.SensorModel),
    ):
        obj = doc.getObject(name)
        documented = (
            json.loads(str(obj.MountingEvidence)) == interfaces.MOUNTING_EVIDENCE[key]
        )
        try:
            connector_evidence_matches = (
                json.loads(str(obj.ConnectorEvidence))
                == interfaces.DEVICE_CONNECTOR_EVIDENCE[key]
            )
        except (AttributeError, TypeError, ValueError):
            connector_evidence_matches = False
        connector_unverified = (
            "InstalledConnectorFitVerified" in obj.PropertiesList
            and not obj.InstalledConnectorFitVerified
        )
        unverified = not bool(obj.MountingStackVerified) and not bool(
            obj.PCBHeightMeasured
        )
        pending_metadata.append(
            {
                "device": name,
                "evidence_matches": documented,
                "mounting_stack_and_pcb_height_unverified": unverified,
                "connector_evidence_matches_sources": connector_evidence_matches,
                "installed_connector_fit_unverified": connector_unverified,
                "passed": documented
                and unverified
                and connector_evidence_matches
                and connector_unverified,
            }
        )
    registered_names = {obj.Name for obj in registry.EquipmentMounts}
    fc_installation = fc_installation_check(doc)
    return {
        "supports": support_rows,
        "confirmed_device_holes": mounting_rows,
        "continuous_adhesive_pads": adhesive_rows,
        "underbody_clearance": free_height_rows,
        "fc_wiring_corridor": wiring_report,
        "fc_installation": fc_installation,
        "device_upward_service": service_rows,
        "native_mounting_evidence_matches_sources": evidence_matches,
        "pending_device_mounting_evidence": pending_metadata,
        "limits": "Printed XY mounting interfaces and reservations only. Purchase FC dampers and device mounting hardware after confirming PCB bearing planes, compressed damper heights and bolt/spacer lengths. Lift checks assume adhesive/retaining hardware has been released; no complete retained device mounting stack is claimed.",
        "passed": registered_names == set(expected_supports)
        and len(registry.EquipmentMounts) == len(expected_supports)
        and all(
            row["passed"]
            for row in support_rows
            + mounting_rows
            + adhesive_rows
            + free_height_rows
            + service_rows
        )
        and wiring_report["passed"]
        and fc_installation["passed"]
        and evidence_matches
        and all(row["passed"] for row in pending_metadata),
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
