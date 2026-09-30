"""Shared Creallo order specification; object identities do not encode manufacture.

All current prints and fit coupons use unfilled PA12 in the supplier's combined
SLS/MJF category. Actual process, grade and finish must match the qualified coupons.
Powder-bed solid geometry has no FDM infill percentage.
"""

import re

PRINT_PROCESS_DESCRIPTION = (
    "Creallo SLS/MJF | PA12 unfilled; process/grade/finish agreement pending"
)
PRINT_LABEL_PREFIX = "SLS/MJF | PA12 unfilled | "
PRINT_METADATA = {
    "PrintSupplier": "Creallo",
    "PrintProcess": "SLS/MJF",
    "MaterialSelection": "PA12 (unfilled)",
    "PrintInfill": "Not applicable: powder-bed solid CAD geometry",
}


def print_specification():
    return {
        "supplier": "Creallo",
        "process_category": "SLS/MJF",
        "material": "PA12 (unfilled)",
        "fdm_infill_percent": None,
        "process_grade_finish_confirmed": False,
    }


def print_label(description):
    return PRINT_LABEL_PREFIX + description


def print_filename(sku, extension):
    """Portable order filename; the stable native SKU remains separate."""
    stem = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", sku).lower()
    return f"SLS-MJF_PA12__{stem}.{extension}"


def print_metadata_matches(obj):
    return str(getattr(obj, "Label", "")).startswith(PRINT_LABEL_PREFIX) and all(
        str(getattr(obj, key, "")) == value for key, value in PRINT_METADATA.items()
    )
