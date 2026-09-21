"""FreeCAD-independent purchase grouping and explicit hardware material identity."""

import json
from pathlib import Path

from .config import ARTIFACT_SCHEMA_VERSION
from .contracts.design import hardware_bom_scope
from .provenance import source_fingerprint

HARDWARE_MATERIAL_CODES = {
    "A2 stainless steel": "A2",
    "Nylon PA66": "PA66",
}


def hardware_material_code(description):
    """Require the declared grade; the word nylon alone does not establish PA66."""
    try:
        return HARDWARE_MATERIAL_CODES[description]
    except (KeyError, TypeError) as error:
        raise ValueError(
            f"Unknown or ambiguous hardware material: {description!r}"
        ) from error


def purchase_code(sku, material):
    return sku + "_" + hardware_material_code(material)


PURCHASE_EVIDENCE_FIELDS = {
    "labels": "Label",
    "notes": "Notes",
    "thread_descriptions": "ThreadStandard",
    "sources": "SourceURL",
}


def purchase_evidence(instances):
    """Preserve every role's evidence when one SKU is shared across mechanisms."""
    return {
        field: sorted({str(getattr(part, property_name, "")) for part in instances})
        for field, property_name in PURCHASE_EVIDENCE_FIELDS.items()
    }


# Mandatory procurement fields must be identical for every instance of a SKU.
# Candidate URLs and evidence notes may be empty when no item is selected.
PURCHASE_METADATA_FIELDS = {
    "purchase_search_query": "PurchaseSearchQuery",
    "purchase_search_url": "PurchaseSearchURL",
    "purchase_requirements": "PurchaseRequirements",
    "purchase_candidate_url": "PurchaseCandidateURL",
    "purchase_evidence_notes": "PurchaseEvidenceNotes",
    "purchasing_status": "PurchasingStatus",
}
REQUIRED_PURCHASE_FIELDS = frozenset(
    (
        "purchase_search_query",
        "purchase_search_url",
        "purchase_requirements",
        "purchasing_status",
    )
)


def purchase_metadata(instances):
    """Reject a shared SKU whose instances disagree on what must be bought."""
    fields = {}
    for field, property_name in PURCHASE_METADATA_FIELDS.items():
        values = {str(getattr(part, property_name, "")) for part in instances}
        if len(values) != 1 or (
            field in REQUIRED_PURCHASE_FIELDS and not next(iter(values), "")
        ):
            raise ValueError(
                f"Missing or conflicting {property_name} for shared hardware SKU"
            )
        fields[field] = values.pop()
    return fields


def export_hardware_bom(objects, out, stem):
    """Group bought instances by both metric specification and material."""
    objects = list(objects)
    buckets, seen_names = {}, set()
    for obj in objects:
        if obj.Name in seen_names:
            raise ValueError(
                "Hardware BOM counts an instance more than once: " + obj.Name
            )
        seen_names.add(obj.Name)
        material = str(getattr(obj, "MaterialSelection", ""))
        hardware_material_code(material)
        buckets.setdefault((str(obj.HardwareSKU), material), []).append(obj)

    rows = []
    for (sku, material), instances in sorted(buckets.items()):
        instances.sort(key=lambda part: part.Name)
        rows.append(
            {
                "sku": sku,
                "purchase_code": purchase_code(sku, material),
                "quantity": len(instances),
                "material": material,
                **purchase_evidence(instances),
                **purchase_metadata(instances),
                "instances": [part.Name for part in instances],
            }
        )
    result = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "source_fingerprint": source_fingerprint(),
        "purchased_hardware_quantity": len(objects),
        "unique_purchase_spec_count": len(rows),
        "all_threads": "Modeled mechanism fasteners use M2 x0.4 ISO metric coarse threads. Unmodeled device/OEM fasteners are outside this list; consult their verified interfaces and unresolved mounting requirements.",
        "purchase_scope": hardware_bom_scope(),
        "color": "Gold = purchased hardware; not a material or finish specification.",
        "purchasing_status": "Specifications and source drawings; no marketplace SKU or seller lot verified.",
        "items": rows,
    }
    Path(out, stem + "_hardware_bom.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    return result
