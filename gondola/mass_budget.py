"""Estimate installed CAD mass without claiming measured all-up flight mass."""

import math
import re

from .contracts.design import SCOPED_LISTED_EQUIPMENT_MASS_G, SELECTED_EQUIPMENT
from .procurement import hardware_material_code

DENSITIES_G_CM3 = {
    "PA12": 1.01,
    "A2": 7.9,
    "SS304": 7.9,
    "PA66": 1.14,
    "CarbonSteel": 7.85,
    "Al6061": 2.70,
    "CopperAlloy": 8.5,
    "UnverifiedAluminium": 2.70,
    "BearingSteel": 7.85,
    "Aluminium": 2.70,
    "UnverifiedHorn": None,
}
PA12_DENSITY_SOURCE = "https://creallo.com/ko/capability/material/SLS/SLSPA12"

EXCLUDED_ITEMS = (
    "Fit coupons and spare parts; only supplied installed-part lists are counted.",
    "Balloon, lifting gas and ground equipment.",
    "Tape, adhesive, hook-and-loop, insulating pads and strain relief.",
    "Wiring, connectors, pigtails and heat-shrink beyond any included equipment mass.",
    "Unmodeled FC/P-AS mounting spacers, dampers and fastening stacks; their bearing planes and screw lengths are unverified.",
    "Unmodeled OEM motor/horn retaining fasteners and interfaces represented only as clearance reservations.",
    "Four M3 gear set screws: inclusion, exact dimensions and mass unverified; gear envelopes exclude their mass.",
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
        reference_mass = getattr(obj, "ReferenceMassGrams", None) if hardware else None
        reference_source = str(getattr(obj, "ReferenceMassSource", ""))
        if reference_mass is not None:
            reference_mass = float(reference_mass)
            if (
                not math.isfinite(reference_mass)
                or reference_mass <= 0
                or not reference_source
            ):
                raise ValueError(f"Invalid reference mass or source for {name}")
        buckets.setdefault((sku, material), []).append(
            (name, volume_mm3, reference_mass, reference_source)
        )

    rows = []
    for (sku, material), instances in sorted(buckets.items()):
        instances.sort()
        volume_mm3 = math.fsum(item[1] for item in instances)
        volume_cm3 = volume_mm3 / 1000
        density = DENSITIES_G_CM3[material]
        reference_values = {(item[2], item[3]) for item in instances}
        has_reference = any(item[2] is not None for item in instances)
        if has_reference and (len(reference_values) != 1 or instances[0][2] is None):
            raise ValueError(f"Conflicting reference masses for hardware SKU {sku}")
        if has_reference:
            estimated_mass = math.fsum(item[2] for item in instances)
            mass_basis = "Published reference mass"
        elif density is None:
            estimated_mass = None
            mass_basis = "Material unverified; no assumed density or mass"
        else:
            estimated_mass = volume_cm3 * density
            mass_basis = "Modeled envelope volume times assumed density"
        rows.append(
            {
                "sku": sku,
                "material": material,
                "quantity": len(instances),
                "instances": [item[0] for item in instances],
                "instance_volumes_mm3": [item[1] for item in instances],
                "total_volume_mm3": volume_mm3,
                "total_volume_cm3": volume_cm3,
                "density_g_cm3": None if has_reference else density,
                "estimated_mass_g": estimated_mass,
                "mass_basis": mass_basis,
                "reference_unit_mass_g": instances[0][2] if has_reference else None,
                "reference_mass_source": instances[0][3] if has_reference else None,
            }
        )
    return rows


def mass_budget(printed, hardware):
    """Count supplied installed instances once; the caller must omit coupons.

    No document traversal or equipment-envelope volume is used. Printed solids use
    PA12 density; hardware requires explicit material metadata. Explicitly
    unverified material remains in the inventory with no mass estimate unless a
    sourced reference mass is available. Summing
    every instance volume avoids assuming that a shared SKU proves equal geometry.
    """
    seen_names = set()
    printed_rows = _grouped_masses(printed, hardware=False, seen_names=seen_names)
    hardware_rows = _grouped_masses(hardware, hardware=True, seen_names=seen_names)
    printed_g = math.fsum(row["estimated_mass_g"] for row in printed_rows)
    unknown_hardware = [
        {
            "sku": row["sku"],
            "material": row["material"],
            "quantity": row["quantity"],
            "instances": row["instances"],
            "reason": row["mass_basis"],
        }
        for row in hardware_rows
        if row["estimated_mass_g"] is None
    ]
    hardware_g = math.fsum(
        row["estimated_mass_g"]
        for row in hardware_rows
        if row["estimated_mass_g"] is not None
    )
    structure_g = printed_g + hardware_g
    equipment_g = SCOPED_LISTED_EQUIPMENT_MASS_G
    subtotal_g = structure_g + equipment_g
    return {
        "method": "BRep solid volume in mm3 / 1000 times density in g/cm3, except explicitly sourced reference masses (such as complete bearings). A part with explicitly unverified material and no reference mass has a null estimate, not zero. Purchased geometry is a dimensional envelope: gear teeth, internal bearing details and helical threads may be simplified. These are estimates, not measured samples.",
        "scope": "Modeled installed printed parts, modeled mechanism hardware and the design contract's scoped listed equipment masses. Equipment-envelope volumes are not weighed or converted to mass.",
        "totals_basis": "current_hardware_g, structure_hardware_g and accounted_subtotal_g are known modeled/listed subtotals. Hardware with null mass estimates, equipment with unmeasured mass and excluded items do not contribute; no complete assembly mass is implied.",
        "is_all_up_flight_mass": False,
        "modeled_hardware_mass_complete": not unknown_hardware,
        "complete_device_mounting_hardware_included": False,
        "device_mounting_hardware_scope": "X06 ear screws/nuts, purchased metal horns and four horn attachment screws are included in the modeled inventory. Horn mass uses its simplified envelope and assumed aluminium density, not a measured product mass. FC/P-AS fastening stacks and OEM motor/horn retaining screws remain unmodeled.",
        "comparison_limit": "Horn alloy, detailed hub geometry and actual mass remain unverified. Gear material and mass remain unverified; the 48T aluminium density and 16T generic copper-alloy density are calculation scenarios, not measured product claims. Generic bearing mass uses an annular solid envelope, not an ISC catalog mass. Compare modeled structure and mechanism hardware only; changing which parts have unknown mass can change the accounted subtotal without reducing physical mass. FC/P-AS spacers, dampers and mounting screws are not yet dimensioned or counted; add their actual mass before claiming net assembly savings.",
        "density_assumptions": {
            "PA12": {
                "density_g_cm3": DENSITIES_G_CM3["PA12"],
                "basis": "Provisional reference from Creallo's published SLS PA12 data, not a verified density for the eventual SLS/MJF grade or lot. Actual printed and finished parts remain unweighed.",
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
            **{
                material: {
                    "density_g_cm3": DENSITIES_G_CM3[material],
                    "basis": "Engineering assumption for modeled material volume; use sourced complete-part reference mass where available.",
                    "source": None,
                }
                for material in (
                    "CarbonSteel",
                    "Al6061",
                    "CopperAlloy",
                    "UnverifiedAluminium",
                    "BearingSteel",
                    "Aluminium",
                    "SS304",
                )
            },
            "UnverifiedHorn": {
                "density_g_cm3": None,
                "basis": "Explicitly unverified horn material category: no plastic or metal density is assumed. The selected purchased aluminium horn uses its separate material category.",
                "source": None,
            },
        },
        "printed": printed_rows,
        "hardware": hardware_rows,
        "hardware_with_unmeasured_mass": unknown_hardware,
        "printed_part_count": sum(row["quantity"] for row in printed_rows),
        "hardware_part_count": sum(row["quantity"] for row in hardware_rows),
        "current_printed_g": printed_g,
        "current_hardware_g": hardware_g,
        "structure_hardware_g": structure_g,
        "scoped_listed_equipment_g": equipment_g,
        "equipment_with_unmeasured_mass": [
            {"model": item.model, "quantity": item.quantity}
            for item in SELECTED_EQUIPMENT
            if item.listed_unit_mass_g is None
        ],
        "accounted_subtotal_g": subtotal_g,
        "excluded_items": list(EXCLUDED_ITEMS),
    }
