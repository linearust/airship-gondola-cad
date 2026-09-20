"""Estimate installed CAD mass without claiming measured all-up flight mass."""

import math
import re

from .design_contract import SCOPED_LISTED_EQUIPMENT_MASS_G

DENSITIES_G_CM3 = {"PA12": 1.01, "A2": 7.9, "PA66": 1.14}
PA12_DENSITY_SOURCE = "https://creallo.com/ko/capability/material/SLS/SLSPA12"

# Archived Rev J BRep audit, before M2/lightweight geometry and MTF-02P addition.
# These are CAD-derived estimates, never weighed parts or a flight-mass baseline.
REV_J_SOURCE_COMMIT = "ecb0f602bfd00d4e4d0f43584f0dc7b6f91db327"
REV_J_CAD_SHA256 = "044c31c25d4c68df93372a7128e1b06a3fa276b5a4ef90fa80259f273660a093"
REV_J_PRINTED_VOLUME_CM3 = 52.148785813539824
REV_J_HARDWARE_MASS_G = 20.343155229055647
REV_J_LISTED_EQUIPMENT_MASS_G = 55.932

EXCLUDED_ITEMS = (
    "Fit coupons and spare parts; only supplied installed-part lists are counted.",
    "Balloon, lifting gas and ground equipment.",
    "Tape, adhesive, hook-and-loop, insulating pads and strain relief.",
    "Wiring, connectors, pigtails and heat-shrink beyond any included equipment mass.",
    "OEM motor/servo mounting fasteners, servo horns and unfinished torque couplings.",
    "Antennas, capacitor, regulators and accessory parts not included in listed equipment masses.",
    "Finish, moisture, manufacturing variation and differences from actual purchased parts.",
)


def _hardware_material(obj):
    description = str(getattr(obj, "MaterialSelection", ""))
    matches = [
        material
        for material in ("A2", "PA66")
        if re.search(rf"\b{material}\b", description, re.IGNORECASE)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Unknown or ambiguous hardware material for {obj.Name}: {description!r}"
        )
    return matches[0]


def _grouped_masses(objects, *, hardware, seen_names):
    buckets = {}
    for obj in objects:
        name = str(obj.Name)
        if name in seen_names:
            raise ValueError(f"Mass budget counts an instance more than once: {name}")
        seen_names.add(name)
        if str(getattr(obj, "PrintCategory", "")) == "Fit samples":
            raise ValueError(f"Mass budget requires installed parts, not coupon {name}")
        volume_mm3 = float(obj.Shape.Volume)
        if not math.isfinite(volume_mm3) or volume_mm3 <= 0:
            raise ValueError(f"Invalid positive solid volume for {name}: {volume_mm3}")
        if hardware:
            material = _hardware_material(obj)
            sku = str(obj.HardwareSKU)
        else:
            if getattr(obj, "HardwareSKU", ""):
                raise ValueError(f"Purchased hardware in installed print list: {name}")
            description = str(getattr(obj, "MaterialSelection", ""))
            if description and not re.search(r"\bPA12\b", description, re.IGNORECASE):
                raise ValueError(
                    f"Unknown printed material for {name}: {description!r}"
                )
            material = "PA12"
            sku = str(getattr(obj, "PrintSKU", name))
        buckets.setdefault((sku, material), []).append((name, volume_mm3))

    rows = []
    for (sku, material), instances in sorted(buckets.items()):
        instances.sort()
        volume_mm3 = math.fsum(volume for _, volume in instances)
        volume_cm3 = volume_mm3 / 1000
        density = DENSITIES_G_CM3[material]
        rows.append(
            {
                "sku": sku,
                "material": material,
                "quantity": len(instances),
                "instances": [name for name, _ in instances],
                "instance_volumes_mm3": [volume for _, volume in instances],
                "total_volume_mm3": volume_mm3,
                "total_volume_cm3": volume_cm3,
                "density_g_cm3": density,
                "estimated_mass_g": volume_cm3 * density,
            }
        )
    return rows


def mass_budget(printed, hardware):
    """Count supplied installed instances once; the caller must omit coupons.

    No document traversal or equipment-envelope volume is used. Printed solids use
    PA12 density; hardware requires explicit A2 or PA66 material metadata. Summing
    every instance volume avoids assuming that a shared SKU proves equal geometry.
    """
    seen_names = set()
    printed_rows = _grouped_masses(printed, hardware=False, seen_names=seen_names)
    hardware_rows = _grouped_masses(hardware, hardware=True, seen_names=seen_names)
    printed_g = math.fsum(row["estimated_mass_g"] for row in printed_rows)
    hardware_g = math.fsum(row["estimated_mass_g"] for row in hardware_rows)
    structure_g = printed_g + hardware_g
    equipment_g = SCOPED_LISTED_EQUIPMENT_MASS_G
    subtotal_g = structure_g + equipment_g
    baseline_printed_g = REV_J_PRINTED_VOLUME_CM3 * DENSITIES_G_CM3["PA12"]
    baseline_structure_g = baseline_printed_g + REV_J_HARDWARE_MASS_G
    baseline_original_subtotal_g = baseline_structure_g + REV_J_LISTED_EQUIPMENT_MASS_G
    saving_g = baseline_structure_g - structure_g
    return {
        "method": "BRep solid volume in mm3 / 1000 times density in g/cm3. Purchased hardware is a dimensional envelope with no helical threads; neither hardware mass nor density is verified on purchased samples.",
        "scope": "Installed printed parts, installed purchased hardware and the design contract's scoped listed equipment masses. Equipment-envelope volumes are not weighed or converted to mass.",
        "is_all_up_flight_mass": False,
        "density_assumptions": {
            "PA12": {
                "density_g_cm3": DENSITIES_G_CM3["PA12"],
                "basis": "Creallo published SLS PA12 density; actual printed and finished parts remain unweighed.",
                "source": PA12_DENSITY_SOURCE,
            },
            "A2": {
                "density_g_cm3": DENSITIES_G_CM3["A2"],
                "basis": "Engineering assumption, not a verified part or supplier-lot density.",
                "source": None,
            },
            "PA66": {
                "density_g_cm3": DENSITIES_G_CM3["PA66"],
                "basis": "Engineering assumption, not a verified part or supplier-lot density.",
                "source": None,
            },
        },
        "printed": printed_rows,
        "hardware": hardware_rows,
        "printed_part_count": sum(row["quantity"] for row in printed_rows),
        "hardware_part_count": sum(row["quantity"] for row in hardware_rows),
        "current_printed_g": printed_g,
        "current_hardware_g": hardware_g,
        "structure_hardware_g": structure_g,
        "scoped_listed_equipment_g": equipment_g,
        "accounted_subtotal_g": subtotal_g,
        "excluded_items": list(EXCLUDED_ITEMS),
        "comparison_to_rev_j": {
            "source_commit": REV_J_SOURCE_COMMIT,
            "cad_sha256": REV_J_CAD_SHA256,
            "basis": "Archived Rev J installed BRep volume audit using the same PA12/A2/PA66 density assumptions. CAD estimates, not measured masses. Same-equipment comparison adds the current equipment scope to both structures.",
            "printed_volume_cm3": REV_J_PRINTED_VOLUME_CM3,
            "printed_g": baseline_printed_g,
            "hardware_g": REV_J_HARDWARE_MASS_G,
            "structure_hardware_g": baseline_structure_g,
            "original_scoped_listed_equipment_g": REV_J_LISTED_EQUIPMENT_MASS_G,
            "original_accounted_subtotal_g": baseline_original_subtotal_g,
            "new_equipment_increment_g": equipment_g - REV_J_LISTED_EQUIPMENT_MASS_G,
            "same_equipment_scope_subtotal_g": baseline_structure_g + equipment_g,
            "structure_hardware_saving_g": saving_g,
            "structure_hardware_saving_percent": 100 * saving_g / baseline_structure_g,
            "accounted_subtotal_change_from_original_scope_g": subtotal_g
            - baseline_original_subtotal_g,
        },
    }
