"""Estimate installed CAD mass without claiming measured all-up flight mass."""

import math
import re

from .contracts.design import SCOPED_LISTED_EQUIPMENT_MASS_G
from .procurement import hardware_material_code

DENSITIES_G_CM3 = {"PA12": 1.01, "A2": 7.9, "PA66": 1.14}
PA12_DENSITY_SOURCE = "https://creallo.com/ko/capability/material/SLS/SLSPA12"

EXCLUDED_ITEMS = (
    "Fit coupons and spare parts; only supplied installed-part lists are counted.",
    "Balloon, lifting gas and ground equipment.",
    "Tape, adhesive, hook-and-loop, insulating pads and strain relief.",
    "Wiring, connectors, pigtails and heat-shrink beyond any included equipment mass.",
    "Unmodeled FC/P-AS mounting spacers, dampers and fastening stacks; their bearing planes and screw lengths are unverified.",
    "OEM motor/servo mounting fasteners, servo horns and unfinished torque couplings.",
    "Antennas, capacitor, regulators and accessory parts not included in listed equipment masses.",
    "Finish, moisture, manufacturing variation and differences from actual purchased parts.",
)


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
            try:
                material = hardware_material_code(obj.MaterialSelection)
            except (AttributeError, ValueError) as error:
                raise ValueError(f"Invalid hardware material for {name}") from error
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
    return {
        "method": "BRep solid volume in mm3 / 1000 times density in g/cm3. Purchased hardware is a dimensional envelope with no helical threads; neither hardware mass nor density is verified on purchased samples.",
        "scope": "Modeled installed printed parts, modeled mechanism hardware and the design contract's scoped listed equipment masses. Equipment-envelope volumes are not weighed or converted to mass.",
        "is_all_up_flight_mass": False,
        "device_mounting_hardware_included": False,
        "comparison_limit": "Compare modeled structure and mechanism hardware only. FC/P-AS spacers, dampers and mounting screws are not yet dimensioned or counted; add their actual mass before claiming net assembly savings.",
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
    }
