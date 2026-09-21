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
from gondola.config import ARTIFACT_SCHEMA_VERSION, OUTPUT_DIR, ROOT, STEM
from gondola.design_contract import (
    EXPECTED_INVENTORY,
    HARDWARE_MATERIALS,
    PURCHASED_HARDWARE_QUANTITIES,
    WIRING_PURCHASE_PLAN,
    hardware_bom_scope,
)
from gondola.manufacturing import geometry_comparison
from gondola.parts import equipment_envelopes as devices
from gondola.parts import equipment_mounts as mounts
from gondola.parts import mounting_interfaces as interfaces
from gondola.parts import optical_sensor, stack_interface
from gondola.procurement import (
    PURCHASE_METADATA_FIELDS,
    REQUIRED_PURCHASE_FIELDS,
    purchase_code,
    purchase_evidence,
)
from gondola.provenance import file_sha256, source_fingerprint

from .geometry import (
    intersection_volume,
    local_shape,
    translation_sweep,
)
from .optical import mtf_sensor_check

TOL = 1e-6
RESERVES = (
    "XT30ServiceReserve",
    "CapacitorServiceReserve",
    "PortPhaseLeadLoopReserve",
    "StarboardPhaseLeadLoopReserve",
    "MTF02POpticalClearanceReserve",
    "FCWiringClearanceReserve",
    "LR900NegativeXConnectorReserve",
    "LR900PositiveXConnectorReserve",
    "PASConnectorReserve",
    "MTF02PConnectorReserve",
)


def connector_reserve_geometry_check(actual, expected, obstacles):
    """Check the complete continuous reserved volume, not just its endpoints."""
    if actual is None or actual.isNull():
        return {"passed": False, "error": "missing connector reservation"}
    comparison = geometry_comparison(actual, expected)
    hits = []
    for name, shape in obstacles.items():
        volume = intersection_volume(actual, shape)
        if volume > TOL:
            hits.append({"object": name, "intersection_mm3": volume})
    connected = actual.isValid() and len(actual.Solids) == 1
    return {
        "source_comparison": comparison,
        "one_connected_solid": connected,
        "continuous_reserved_space_collisions": hits,
        "passed": connected and _comparison_passed(comparison) and not hits,
    }


def connector_buffer_checks(fc_reserve, other_shapes):
    """Measure saved geometry gaps to neighbouring reservations and equipment."""
    from gondola.parts import wiring_clearance as wiring

    rows = []
    for name in (
        "MTF02POpticalClearanceReserve",
        "ModuleLR900Envelope",
        "ModulePASEnvelope",
        "XT30ServiceReserve",
    ):
        other = other_shapes.get(name)
        if fc_reserve is None or other is None:
            rows.append({"object": name, "passed": False, "error": "missing shape"})
            continue
        distance = fc_reserve.distToShape(other)[0]
        rows.append(
            {
                "object": name,
                "measured_gap_mm": distance,
                "minimum_design_gap_mm": wiring.FC_MINIMUM_NEIGHBOUR_GAP_MM,
                "passed": distance >= wiring.FC_MINIMUM_NEIGHBOUR_GAP_MM - TOL,
            }
        )
    return rows


def reserve_checks(doc):
    from gondola.parts import wiring_clearance as wiring

    registry = doc.DesignRegistry
    physical = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    shapes = {obj.Name: world_shape(obj) for obj in physical}
    actual_reserves = {obj.Name: world_shape(obj) for obj in registry.ClearanceVolumes}
    expected_shapes = wiring.reserve_shapes()
    expected_shapes["MTF02PConnectorReserve"] = optical_sensor.connector_reserve_shape()
    expected_contracts = wiring.reserve_contracts()
    expected_contracts["MTF02PConnectorReserve"] = optical_sensor.connector_contract()
    checks = []
    for name in RESERVES:
        obj = doc.getObject(name)
        if obj is None:
            checks.append({"object": name, "passed": False, "error": "missing"})
            continue
        shape = world_shape(obj)
        source_check = None
        contract_matches = True
        source_url_matches = True
        fit_unverified = True
        if name in expected_shapes:
            source_check = connector_reserve_geometry_check(
                shape,
                _in_parent_frame(
                    expected_shapes[name],
                    doc.OpticalPitchStage
                    if name == "MTF02PConnectorReserve"
                    else doc.ElectronicsEquipmentModule,
                ),
                shapes,
            )
            try:
                contract_matches = json.loads(str(obj.WiringContract)) == json.loads(
                    json.dumps(expected_contracts[name])
                )
            except (AttributeError, TypeError, ValueError):
                contract_matches = False
            source_url_matches = (
                str(getattr(obj, "SourceURL", ""))
                == expected_contracts[name]["source_url"]
            )
            fit_unverified = (
                "InstalledConnectorFitVerified" in obj.PropertiesList
                and not obj.InstalledConnectorFitVerified
            )
        buffers = (
            connector_buffer_checks(shape, {**shapes, **actual_reserves})
            if name == "FCWiringClearanceReserve"
            else []
        )
        intersections, nearest = [], []
        for other_name, other in shapes.items():
            volume = intersection_volume(shape, other)
            if volume > TOL:
                intersections.append({"object": other_name, "volume_mm3": volume})
            nearest.append(
                {"object": other_name, "distance_mm": shape.distToShape(other)[0]}
            )
        bounds = shape.optimalBoundingBox(False, False)
        sweeps = []
        for sweep in registry.ClearanceVolumes:
            if "Sweep" not in sweep.Name:
                continue
            swept = world_shape(sweep)
            sweeps.append(
                {
                    "sweep": sweep.Name,
                    "intersection_mm3": intersection_volume(shape, swept),
                    "distance_mm": shape.distToShape(swept)[0],
                }
            )
        clearance_only = (
            obj in registry.ClearanceVolumes
            and obj not in registry.PrintedParts
            and obj not in registry.HardwareParts
            and obj not in registry.ReferenceParts
            and str(getattr(obj, "Role", "")) == "Clearance"
        )
        checks.append(
            {
                "object": name,
                "role": str(obj.Role),
                "in_clearance_registry": obj in registry.ClearanceVolumes,
                "not_in_print_or_hardware_registry": obj not in registry.PrintedParts
                and obj not in registry.HardwareParts,
                "valid_solid": shape.isValid() and len(shape.Solids) == 1,
                "bounds_world_mm": {
                    "min": [bounds.XMin, bounds.YMin, bounds.ZMin],
                    "max": [bounds.XMax, bounds.YMax, bounds.ZMax],
                },
                "intersections_with_printed_hardware_equipment_tape": intersections,
                "nearest_five_objects": sorted(
                    nearest, key=lambda row: row["distance_mm"]
                )[:5],
                "conservative_rotor_sweep_comparison": sweeps,
                "connector_geometry": source_check,
                "native_wiring_contract_matches": contract_matches,
                "native_source_url_matches": source_url_matches,
                "installed_connector_fit_remains_unverified": fit_unverified,
                "fc_neighbour_clearance_buffers": buffers,
                "notes": str(getattr(obj, "Notes", "")),
                "passed": not intersections
                and shape.isValid()
                and len(shape.Solids) == 1
                and all(row["intersection_mm3"] < TOL for row in sweeps)
                and (source_check is None or source_check["passed"])
                and contract_matches
                and source_url_matches
                and fit_unverified
                and all(row["passed"] for row in buffers)
                and clearance_only,
            }
        )
    pairs = []
    for index, name in enumerate(RESERVES):
        for other_name in RESERVES[index + 1 :]:
            first = actual_reserves.get(name)
            second = actual_reserves.get(other_name)
            present = first is not None and second is not None
            volume = intersection_volume(first, second) if present else None
            pairs.append(
                {
                    "a": name,
                    "b": other_name,
                    "intersection_mm3": volume,
                    "passed": present and volume < TOL,
                }
            )
    return checks, pairs


def _comparison_passed(comparison):
    return all(
        comparison[key] < TOL
        for key in ("difference_mm3", "bounds_difference_mm", "volume_difference_mm3")
    )


def _in_parent_frame(shape, parent):
    result = shape.copy()
    result.Placement = parent.getGlobalPlacement().multiply(result.Placement)
    return result


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
    from gondola.parts import wiring_clearance as wiring_clearances

    registry = doc.DesignRegistry
    physical = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    shapes = {obj.Name: world_shape(obj) for obj in physical}
    support_rows = []
    expected_supports = {"BatteryMount": "battery", "ElectronicsMount": "electronics"}
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
    carrier = doc.getObject("ElectronicsMount")
    if carrier is None:
        return {"supports": support_rows, "passed": False}
    carrier_shape = local_shape(carrier)
    parent = doc.ElectronicsEquipmentModule
    mounting_rows = []
    device_specs = (
        (
            "ModuleFCEnvelope",
            mounts.FC_HOLE_CENTRES,
            interfaces.FC_HOLE_DIAMETER,
            devices.fc_envelope_shape,
        ),
        (
            "ModulePASEnvelope",
            mounts.PAS_HOLE_CENTRES,
            interfaces.PAS_HOLE_DIAMETER,
            devices.pas_envelope_shape,
        ),
    )
    for name, centres, device_hole_diameter, factory in device_specs:
        if name == "ModuleFCEnvelope":
            rotation = App.Rotation(App.Vector(0, 0, 1), mounts.FC_ROTATION_DEG)
            confirmed = [
                rotation.multVec(App.Vector(x, y, 0))
                + App.Vector(*mounts.FC_CENTRE_XY, 0)
                for x, y in interfaces.FC_HOLE_CENTRES
            ]
        else:
            confirmed = [
                App.Vector(x + mounts.PAS_CENTRE_XY[0], y + mounts.PAS_CENTRE_XY[1], 0)
                for x, y in interfaces.PAS_HOLE_CENTRES
            ]
        axes_match = len(centres) == len(confirmed) and all(
            min((App.Vector(*centre, 0) - expected).Length for expected in confirmed)
            < TOL
            for centre in centres
        )
        obj = doc.getObject(name)
        body = shapes[name]
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
                "holes": holes,
                "passed": axes_match
                and _comparison_passed(comparison)
                and all(row["passed"] for row in holes),
            }
        )
    adhesive_rows = []
    for mount_name, device_name, centre, size in (
        ("BatteryMount", "ModuleBatteryEnvelope", (0, 0), mounts.BATTERY_DECK_SIZE),
        (
            "ElectronicsMount",
            "ModuleLR900Envelope",
            mounts.LR_CENTRE_XY,
            mounts.LR_ADHESIVE_SIZE,
        ),
    ):
        support = doc.getObject(mount_name)
        owner = support.getParentGeoFeatureGroup()
        pad = Part.makeBox(
            size[0],
            size[1],
            mounts.DECK_THICKNESS,
            App.Vector(
                centre[0] - size[0] / 2, centre[1] - size[1] / 2, mounts.DECK_BOTTOM_Z
            ),
        )
        pad_world = _in_parent_frame(pad, owner)
        missing = pad_world.cut(shapes[mount_name]).Volume
        pad_bounds = pad_world.optimalBoundingBox(False, False)
        device_bounds = shapes[device_name].optimalBoundingBox(False, False)
        covered = all(
            getattr(pad_bounds, axis + "Min")
            >= getattr(device_bounds, axis + "Min") - TOL
            and getattr(pad_bounds, axis + "Max")
            <= getattr(device_bounds, axis + "Max") + TOL
            for axis in ("X", "Y")
        )
        gap = device_bounds.ZMin - pad_bounds.ZMax
        adhesive_rows.append(
            {
                "device": device_name,
                "continuous_support_area_mm2": size[0] * size[1],
                "missing_pad_material_mm3": missing,
                "pad_within_device_plan_envelope": covered,
                "adhesive_allowance_mm": gap,
                "passed": missing < TOL
                and covered
                and abs(gap - mounts.ADHESIVE_ALLOWANCE) < TOL,
            }
        )
    free_height_rows = []
    for name, expected_gap in (
        ("ModuleFCEnvelope", mounts.FC_WIRING_CLEARANCE),
        ("ModulePASEnvelope", mounts.PAS_SERVICE_CLEARANCE),
    ):
        bounds = shapes[name].optimalBoundingBox(False, False)
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
            else interfaces.PAS_SIZE_MM
        )
        centre = (
            mounts.FC_CENTRE_XY if name == "ModuleFCEnvelope" else mounts.PAS_CENTRE_XY
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
                "intersection_mm3": intersection_volume(space, shapes[other.Name]),
            }
            for other in physical
            if intersection_volume(space, shapes[other.Name]) > TOL
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
    wiring = {"passed": False, "error": "missing FC wiring corridor"}
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
            for obj in physical
            if intersection_volume(actual, shapes[obj.Name]) > TOL
        ]
        local_reserve = local_shape(reserve)
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
        wiring = {
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
        "ModuleLR900Envelope",
    ):
        sweep, sweep_method = translation_sweep(shapes[name], (0, 0, 32))
        optical_group = doc.getObject("OpticalFlowModule")
        device_parent = doc.getObject(name).getParentGeoFeatureGroup()
        release_head = (
            optical_group is not None
            and optical_group.getParentGeoFeatureGroup() == device_parent
        )
        removed = {
            obj.Name
            for obj in physical
            if release_head
            and stack_interface.is_removable_head_part(obj, optical_group)
        }
        hits = [
            obj.Name
            for obj in physical
            if obj.Name != name
            and obj.Name not in removed
            and intersection_volume(sweep, shapes[obj.Name]) > TOL
        ]
        service_rows.append(
            {
                "device": name,
                "upward_travel_mm": 32,
                "optical_head_must_be_removed_first": release_head,
                "remaining_columns_and_lower_fasteners_checked": True,
                "temporarily_removed_head_parts": sorted(removed),
                "method": sweep_method,
                "prerequisite": "Disconnect leads, release device retention, and when this carrier hosts the stack remove its two upper screws and complete optical head first. Stack columns/lower screws remain installed and are checked. Bare-device path, not a connected harness.",
                "collisions": hits,
                "passed": not hits,
            }
        )
    evidence_matches = (
        json.loads(str(carrier.MountingEvidence)) == interfaces.MOUNTING_EVIDENCE
    )
    pending_metadata = []
    for name, key in (
        ("ModuleFCEnvelope", "FC"),
        ("ModulePASEnvelope", "PAS"),
        ("ModuleLR900Envelope", "LR"),
        ("ModuleMTF02PEnvelope", "MTF02P"),
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
    return {
        "supports": support_rows,
        "confirmed_device_holes": mounting_rows,
        "continuous_adhesive_pads": adhesive_rows,
        "underbody_clearance": free_height_rows,
        "fc_wiring_corridor": wiring,
        "device_upward_service": service_rows,
        "native_mounting_evidence_matches_sources": evidence_matches,
        "pending_device_mounting_evidence": pending_metadata,
        "limits": "Printed XY mounting interfaces and reservations only. Purchase FC dampers and device mounting hardware after confirming PCB bearing planes, compressed damper heights and bolt/spacer lengths. Lift checks assume adhesive/retaining hardware has been released; no complete retained device mounting stack is claimed.",
        "passed": registered_names == set(expected_supports)
        and len(registry.EquipmentMounts) == 2
        and all(
            row["passed"]
            for row in support_rows
            + mounting_rows
            + adhesive_rows
            + free_height_rows
            + service_rows
        )
        and wiring["passed"]
        and evidence_matches
        and all(row["passed"] for row in pending_metadata),
    }


def hardware_check(doc, source):
    registry = doc.DesignRegistry
    quantities = Counter(str(obj.HardwareSKU) for obj in registry.HardwareParts)
    materials, checks = {}, []
    for obj in registry.HardwareParts:
        materials.setdefault(str(obj.HardwareSKU), set()).add(
            str(obj.MaterialSelection)
        )
        expected = HARDWARE_MATERIALS.get(str(obj.HardwareSKU))
        checks.append(
            {
                "object": obj.Name,
                "material": str(obj.MaterialSelection),
                "passed": expected == str(obj.MaterialSelection),
            }
        )
    bom = json.loads((source.parent / (source.stem + "_hardware_bom.json")).read_text())
    bom_names = [name for row in bom["items"] for name in row["instances"]]
    model_hardware = {obj.Name: obj for obj in registry.HardwareParts}
    bom_rows = []
    for row in bom["items"]:
        instances = [model_hardware.get(name) for name in row["instances"]]
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
        "unique_sku_count": len(quantities),
        "sku_quantities": dict(quantities),
        "materials_by_sku": {sku: sorted(values) for sku, values in materials.items()},
        "material_checks": checks,
        "bom_source_identity_matches": identity_matches,
        "bom_purchase_scope_matches_contract": bom.get("purchase_scope")
        == hardware_bom_scope(),
        "bom_rows": bom_rows,
        "not_printed": all(
            obj not in registry.PrintedParts
            and not bool(getattr(obj, "PrintPart", False))
            for obj in registry.HardwareParts
        ),
        "bom_each_instance_exactly_once": len(bom_names)
        == EXPECTED_INVENTORY["purchased_hardware"]
        and len(set(bom_names)) == EXPECTED_INVENTORY["purchased_hardware"]
        and set(bom_names) == {obj.Name for obj in registry.HardwareParts},
        "bom_stated_quantity": bom["purchased_hardware_quantity"],
        "bom_stated_unique_specs": bom["unique_purchase_spec_count"],
        "passed": dict(quantities) == PURCHASED_HARDWARE_QUANTITIES
        and bom.get("purchase_scope") == hardware_bom_scope()
        and all(row["passed"] for row in checks)
        and identity_matches
        and all(row["matches_native_instances"] for row in bom_rows),
    }


def validate(source=None):
    fingerprint_before = source_fingerprint()
    source = Path(source).resolve() if source else OUTPUT_DIR / (STEM + ".FCStd")
    before = file_sha256(source)
    bom_path = source.parent / (source.stem + "_hardware_bom.json")
    bom_before = file_sha256(bom_path)
    doc = App.openDocument(str(source), hidden=True)
    try:
        registry = doc.DesignRegistry
        checks, reserve_pairs = reserve_checks(doc)
        mtf = mtf_sensor_check(doc)
        mounting = mounting_check(doc)
        hardware = hardware_check(doc, source)
        try:
            wiring_plan_matches = (
                json.loads(str(registry.WiringPurchasePlan)) == WIRING_PURCHASE_PLAN
            )
        except (AttributeError, TypeError, ValueError):
            wiring_plan_matches = False
        sources = {}
        for name in (
            "ModulePASEnvelope",
            "ModuleLR900Envelope",
            "ModuleMTF02PEnvelope",
        ):
            obj = doc.getObject(name)
            sources[name] = {
                key: str(getattr(obj, key))
                for key in obj.PropertiesList
                if "Source" in key or key == "Notes"
            }
        report = {
            "source_file": os.path.relpath(source, ROOT),
            "source_sha256": before,
            "hardware_bom_sha256_before": bom_before,
            "source_fingerprint": fingerprint_before,
            "scope": "Read-only saved-file clearance and purchased-hardware audit. Temporary in-memory MTF optical-obstruction tilt probes are restored; the native file is never saved.",
            "actual_object_counts": {
                "printed": len(registry.PrintedParts),
                "hardware": len(registry.HardwareParts),
                "equipment_references": len(registry.ReferenceParts),
                "tape_references": len(registry.TapeReferences),
            },
            "reserve_checks": checks,
            "reserve_pair_checks": reserve_pairs,
            "mtf02p_sensor": mtf,
            "equipment_mounts": mounting,
            "hardware": hardware,
            "native_wiring_purchase_plan_matches_contract": wiring_plan_matches,
            "reference_sources": sources,
            "limits": [
                "Connector catalog dimensions are retained evidence; reserved lanes do not verify installed PCB port datums, actual plug fit, withdrawal stroke or wire bends. The capacitor remains a provisional space allocation.",
                "The toroidal reserves are not proven wire routes, bend radii, strain relief or validated phase-lead slack through 300 degrees.",
                "The optical stack can use either common host. Its400mm whole-face field is checked to cover modeled-gondola depth; lens datums, actual optical calibration, gravity alignment and cable slack remain unverified.",
                "No physical fit, electrical insulation/current capacity, clamp force or structural test was performed.",
            ],
        }
    finally:
        App.closeDocument(doc.Name)
    after = file_sha256(source)
    report["source_sha256_after"] = after
    report["source_unchanged"] = before == after
    report["hardware_bom_sha256_after"] = file_sha256(bom_path)
    report["hardware_bom_unchanged"] = bom_before == report["hardware_bom_sha256_after"]
    report["source_code_unchanged"] = fingerprint_before == source_fingerprint()
    report["passed"] = (
        before == after
        and report["source_code_unchanged"]
        and report["hardware_bom_unchanged"]
        and mtf["passed"]
        and mounting["passed"]
        and all(row["passed"] for row in checks)
        and all(row["passed"] for row in reserve_pairs)
        and hardware["passed"]
        and wiring_plan_matches
        and hardware["not_printed"]
        and hardware["bom_each_instance_exactly_once"]
        and hardware["bom_stated_quantity"] == EXPECTED_INVENTORY["purchased_hardware"]
        and hardware["bom_stated_unique_specs"]
        == EXPECTED_INVENTORY["purchased_hardware_types"]
    )
    target = source.parent / (source.stem + "_equipment_validation.json")
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "equipment_report": str(target),
                "passed": report["passed"],
                "source_unchanged": before == after,
            }
        ),
        flush=True,
    )
    return report
