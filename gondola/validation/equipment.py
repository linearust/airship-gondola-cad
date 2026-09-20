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
from gondola.parts import universal_board as board
from gondola.provenance import file_sha256, source_fingerprint

from .geometry import intersection_volume, local_shape

TOL = 1e-6
RESERVES = (
    "XT30ServiceReserve",
    "CapacitorServiceReserve",
    "PortPhaseLeadLoopReserve",
    "StarboardPhaseLeadLoopReserve",
    "MTF02POpticalClearanceReserve",
)
EXPECTED_PURCHASE_QUANTITIES = {
    "M2_MF_30_PLUS_5": 4,
    "M2X6_SOCKET_CAP": 4,
    "M2X14_SOCKET_CAP": 4,
    "M2x6_ISO4026_DIN913": 3,
    "M2_HEX_NUT": 8,
    "M2_SQUARE_NUT_DIN562": 3,
    "M2_WASHER_2.2_5_0.3": 16,
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
    upper = world_shape(doc.UpperUniversalBoard)
    upper_bounds = upper.optimalBoundingBox(False, False)
    support_probe = Part.makeBox(
        body_bounds.XLength,
        body_bounds.YLength,
        board.BOARD_THICKNESS,
        App.Vector(
            body_bounds.XMin,
            body_bounds.YMin,
            upper_bounds.ZMax - board.BOARD_THICKNESS,
        ),
    )
    support_area = intersection_volume(upper, support_probe) / board.BOARD_THICKNESS
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
        expected = (
            "PA66" if obj.HardwareSKU == "M2_MF_30_PLUS_5" else "A2 stainless steel"
        )
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
