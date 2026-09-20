"""Read-only audit of service reservations, bought hardware, and source metadata."""

import json
import os
from collections import Counter
from pathlib import Path

import FreeCAD as App

from gondola.cad import (
    world_shape,
)
from gondola.config import ARTIFACT_SCHEMA_VERSION, OUTPUT_DIR, ROOT, STEM
from gondola.design_contract import EXPECTED_INVENTORY
from gondola.provenance import file_sha256, source_fingerprint

from .geometry import intersection_volume

TOL = 1e-6
RESERVES = (
    "XT30ServiceReserve",
    "CapacitorServiceReserve",
    "PortPhaseLeadLoopReserve",
    "StarboardPhaseLeadLoopReserve",
)
EXPECTED_PURCHASE_QUANTITIES = {
    "M3_MF_30_PLUS_6": 4,
    "M3X6_SOCKET_CAP": 4,
    "M3X16_SOCKET_CAP": 4,
    "M3x8_ISO4026_DIN913": 3,
    "M3_HEX_NUT": 11,
    "M3_WASHER_3.2_7_0.5": 16,
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


def hardware_check(doc, source):
    registry = doc.DesignRegistry
    quantities = Counter(str(obj.HardwareSKU) for obj in registry.HardwareParts)
    materials, checks = {}, []
    for obj in registry.HardwareParts:
        materials.setdefault(str(obj.HardwareSKU), set()).add(
            str(obj.MaterialSelection)
        )
        expected = (
            "PA66" if obj.HardwareSKU == "M3_MF_30_PLUS_6" else "A2 stainless steel"
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
        hardware = hardware_check(doc, source)
        sources = {}
        for name in ("ModulePASEnvelope", "ModuleLR900Envelope"):
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
            "scope": "Read-only clearance-volume and purchased-hardware audit of the saved native assembly. No CAD objects or placements were changed.",
            "actual_object_counts": {
                "printed": len(registry.PrintedParts),
                "hardware": len(registry.HardwareParts),
                "equipment_references": len(registry.ReferenceParts),
                "tape_references": len(registry.TapeReferences),
            },
            "reserve_checks": checks,
            "reserve_pair_checks": reserve_pairs,
            "hardware": hardware,
            "reference_sources": sources,
            "limits": [
                "These are reserved clear spaces, not verified dimensions of selected XT30 or capacitor products.",
                "The toroidal reserves are not proven wire routes, bend radii, strain relief or validated phase-lead slack through 300 degrees.",
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
