"""Read-only audit of service reservations, bought hardware, and source metadata."""

import itertools
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
from gondola.design_contract import EXPECTED_INVENTORY
from gondola.manufacturing import geometry_comparison
from gondola.parts import equipment_envelopes as devices
from gondola.parts import equipment_mounts as mounts
from gondola.parts import mounting_interfaces as interfaces
from gondola.provenance import file_sha256, source_fingerprint

from .geometry import intersection_volume, local_shape

TOL = 1e-6
RESERVES = (
    "XT30ServiceReserve",
    "CapacitorServiceReserve",
    "PortPhaseLeadLoopReserve",
    "StarboardPhaseLeadLoopReserve",
    "MTF02POpticalClearanceReserve",
    "FCWiringClearanceReserve",
)
EXPECTED_PURCHASE_QUANTITIES = {
    "M2X14_SOCKET_CAP": 4,
    "M2x6_ISO4026_DIN913": 3,
    "M2_HEX_NUT": 4,
    "M2_SQUARE_NUT_DIN562": 3,
    "M2_WASHER_2.2_5_0.3": 8,
}


def reserve_checks(doc):
    registry = doc.DesignRegistry
    physical = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    shapes = {obj.Name: world_shape(obj) for obj in physical}
    checks = []
    for name in RESERVES:
        obj = doc.getObject(name)
        shape = world_shape(obj)
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
                "notes": str(getattr(obj, "Notes", "")),
                "passed": not intersections
                and shape.isValid()
                and len(shape.Solids) == 1
                and all(row["intersection_mm3"] < TOL for row in sweeps)
                and clearance_only,
            }
        )
    pairs = []
    for index, name in enumerate(RESERVES):
        for other_name in RESERVES[index + 1 :]:
            pairs.append(
                {
                    "a": name,
                    "b": other_name,
                    "intersection_mm3": intersection_volume(
                        world_shape(doc.getObject(name)),
                        world_shape(doc.getObject(other_name)),
                    ),
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
        (
            "ElectronicsMount",
            "ModuleMTF02PEnvelope",
            mounts.MTF02P_CENTRE_XY,
            mounts.MTF02P_ADHESIVE_SIZE,
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
        # A complete envelope rectangle is conservative around the rotated FC.
        space = Part.makeBox(
            bounds.XLength,
            bounds.YLength,
            expected_gap,
            App.Vector(bounds.XMin, bounds.YMin, support_top),
        )
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
            actual, _in_parent_frame(mounts.fc_wiring_reserve_shape(), parent)
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
            "scope": "Eight-mm-high open wiring corridor offset from mounting axes. Future damper/spacer envelopes and plugged leads require actual dimensions.",
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
        "ModuleMTF02PEnvelope",
    ):
        bounds = shapes[name].optimalBoundingBox(False, False)
        sweep = Part.makeBox(
            bounds.XLength,
            bounds.YLength,
            bounds.ZLength + 32,
            App.Vector(bounds.XMin, bounds.YMin, bounds.ZMin),
        )
        hits = [
            obj.Name
            for obj in physical
            if obj.Name != name and intersection_volume(sweep, shapes[obj.Name]) > TOL
        ]
        service_rows.append(
            {
                "device": name,
                "upward_travel_mm": 32,
                "method": "Continuous conservative bounding-prism sweep",
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
        unverified = not bool(obj.MountingStackVerified) and not bool(
            obj.PCBHeightMeasured
        )
        pending_metadata.append(
            {
                "device": name,
                "evidence_matches": documented,
                "mounting_stack_and_pcb_height_unverified": unverified,
                "passed": documented and unverified,
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


def mtf_sensor_check(doc):
    """Check the included sensor and restore every temporary tilt probe."""
    registry = doc.DesignRegistry
    sensor = doc.getObject("ModuleMTF02PEnvelope")
    reserve = doc.getObject("MTF02POpticalClearanceReserve")
    if sensor is None or reserve is None:
        return {
            "passed": False,
            "error": "MTF-02P sensor or optical reserve is missing.",
        }
    body = world_shape(sensor)
    optical = world_shape(reserve)
    body_bounds = body.optimalBoundingBox(False, False)
    optical_bounds = optical.optimalBoundingBox(False, False)
    direction = sensor.getGlobalPlacement().Rotation.multVec(sensor.OpticalDirection)
    body_comparison = geometry_comparison(
        local_shape(sensor), devices.mtf02p_envelope_shape()
    )
    optical_comparison = geometry_comparison(
        local_shape(reserve), devices.mtf02p_optical_reserve_shape()
    )
    upper = world_shape(doc.ElectronicsMount)
    upper_bounds = upper.optimalBoundingBox(False, False)
    support_probe = Part.makeBox(
        body_bounds.XLength,
        body_bounds.YLength,
        mounts.DECK_THICKNESS,
        App.Vector(
            body_bounds.XMin,
            body_bounds.YMin,
            upper_bounds.ZMax - mounts.DECK_THICKNESS,
        ),
    )
    support_area = intersection_volume(upper, support_probe) / mounts.DECK_THICKNESS
    mounting_gap = body_bounds.ZMin - upper_bounds.ZMax
    adjacent_optical_clearances = []
    for name in ("ModuleLR900Envelope", "ModulePASEnvelope"):
        neighbor = world_shape(doc.getObject(name))
        distance = optical.distToShape(neighbor)[0]
        adjacent_optical_clearances.append(
            {
                "object": name,
                "nominal_minimum_distance_mm": distance,
                "required_nominal_distance_mm": 1.0,
                "passed": distance >= 1.0 - TOL,
            }
        )
    physical = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    pods = list(registry.TiltingPods)
    original_tilts = [float(pod.Tilt) for pod in pods]
    tilt_rows = []
    try:
        for angles in itertools.product((-150.0, 0.0, 150.0), repeat=len(pods)):
            for pod, angle in zip(pods, angles):
                pod.Tilt = angle
            doc.recompute()
            body_hits, optical_hits = [], []
            for obj in physical:
                if obj == sensor:
                    continue
                other = world_shape(obj)
                body_volume = intersection_volume(body, other)
                optical_volume = intersection_volume(optical, other)
                if body_volume > TOL:
                    body_hits.append(
                        {"object": obj.Name, "intersection_mm3": body_volume}
                    )
                if optical_volume > TOL:
                    optical_hits.append(
                        {"object": obj.Name, "intersection_mm3": optical_volume}
                    )
            tilt_rows.append(
                {
                    "tilt_degrees": dict(zip((pod.Name for pod in pods), angles)),
                    "sensor_collisions": body_hits,
                    "optical_reserve_obstructions": optical_hits,
                    "passed": not body_hits and not optical_hits,
                }
            )
    finally:
        for pod, angle in zip(pods, original_tilts):
            pod.Tilt = angle
        doc.recompute()
    registered = (
        sensor in registry.ReferenceParts
        and sensor not in registry.PrintedParts
        and sensor not in registry.HardwareParts
        and reserve in registry.ClearanceVolumes
    )
    direction_matches = (
        abs(direction.x) < TOL and abs(direction.y) < TOL and abs(direction.z - 1) < TOL
    )
    report = {
        "source": devices.MTF02P_SOURCE,
        "published_size_mm": list(devices.MTF02P_SIZE_MM),
        "published_module_mass_g": devices.MTF02P_MASS_G,
        "body_source_comparison": body_comparison,
        "optical_reserve_source_comparison": optical_comparison,
        "optical_direction_world": [direction.x, direction.y, direction.z],
        "optical_face_world_z_mm": body_bounds.ZMax,
        "optical_reserve_start_world_z_mm": optical_bounds.ZMin,
        "optical_reserve_distance_mm": optical_bounds.ZLength,
        "available_board_material_under_footprint_mm2": support_area,
        "nominal_insulating_adhesive_allowance_mm": mounting_gap,
        "adjacent_optical_clearances": adjacent_optical_clearances,
        "tilt_checks": tilt_rows,
        "no_new_printed_or_metric_fastener_parts": registered,
        "installed_optical_field_verified": False,
        "limits": "Whole-face42deg near-field reservation only. Actual lens origins, in-plane firmware orientation, backside adhesive contact, cable routing and usable ground field require the purchased module; no sensor mounting screws are specified.",
    }
    report["passed"] = (
        registered
        and direction_matches
        and body.isValid()
        and len(body.Solids) == 1
        and optical.isValid()
        and len(optical.Solids) == 1
        and body_comparison["difference_mm3"] < TOL
        and optical_comparison["difference_mm3"] < TOL
        and abs(float(sensor.ListedMassGrams) - devices.MTF02P_MASS_G) < TOL
        and abs(optical_bounds.ZMin - body_bounds.ZMax) < TOL
        and abs(optical_bounds.ZLength - devices.MTF02P_OPTICAL_RESERVE_MM) < TOL
        and abs(mounting_gap - 1.0) < TOL
        and support_area > TOL
        and all(row["passed"] for row in adjacent_optical_clearances)
        and len(pods) == 2
        and len(tilt_rows) == 9
        and all(row["passed"] for row in tilt_rows)
    )
    return report


def hardware_check(doc, source):
    registry = doc.DesignRegistry
    quantities = Counter(str(obj.HardwareSKU) for obj in registry.HardwareParts)
    materials, checks = {}, []
    for obj in registry.HardwareParts:
        materials.setdefault(str(obj.HardwareSKU), set()).add(
            str(obj.MaterialSelection)
        )
        expected = "A2 stainless steel"
        checks.append(
            {
                "object": obj.Name,
                "material": str(obj.MaterialSelection),
                "passed": expected in str(obj.MaterialSelection),
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
            matched = (
                row["quantity"] == len(instances)
                and all(
                    row["sku"] == str(obj.HardwareSKU)
                    and row["material"] == str(obj.MaterialSelection)
                    for obj in instances
                )
                and row.get("thread_descriptions")
                == sorted(
                    {str(getattr(obj, "ThreadStandard", "")) for obj in instances}
                )
                and row.get("sources")
                == sorted({str(getattr(obj, "SourceURL", "")) for obj in instances})
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
        "passed": dict(quantities) == EXPECTED_PURCHASE_QUANTITIES
        and all(row["passed"] for row in checks)
        and identity_matches
        and all(row["matches_native_instances"] for row in bom_rows),
    }


def validate(source=None):
    fingerprint_before = source_fingerprint()
    source = Path(source).resolve() if source else OUTPUT_DIR / (STEM + ".FCStd")
    before = file_sha256(source)
    doc = App.openDocument(str(source), hidden=True)
    try:
        registry = doc.DesignRegistry
        checks, reserve_pairs = reserve_checks(doc)
        mtf = mtf_sensor_check(doc)
        mounting = mounting_check(doc)
        hardware = hardware_check(doc, source)
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
            "reference_sources": sources,
            "limits": [
                "These are reserved clear spaces, not verified dimensions of selected XT30 or capacitor products.",
                "The toroidal reserves are not proven wire routes, bend radii, strain relief or validated phase-lead slack through 300 degrees.",
                "The MTF-02P optical reserve screens the first80mm from the entire front face; it is not a calibrated or physically verified field of view.",
                "No physical fit, electrical insulation/current capacity, clamp force or structural test was performed.",
            ],
        }
    finally:
        App.closeDocument(doc.Name)
    after = file_sha256(source)
    report["source_sha256_after"] = after
    report["source_unchanged"] = before == after
    report["source_code_unchanged"] = fingerprint_before == source_fingerprint()
    report["passed"] = (
        before == after
        and report["source_code_unchanged"]
        and mtf["passed"]
        and mounting["passed"]
        and all(row["passed"] for row in checks)
        and all(row["intersection_mm3"] < TOL for row in reserve_pairs)
        and hardware["passed"]
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
