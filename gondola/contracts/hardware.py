"""Portable purchase and stock-preparation contracts.

Project purchase keys distinguish selected options; they are not manufacturer
part numbers or received-lot certification. Native geometry lives in parts.
"""

import re
from urllib.parse import quote_plus

from gondola.contracts.drive import GEARS, MODULE_MM, PRESSURE_ANGLE_DEG
from gondola.contracts.equipment_interfaces import (
    BEARING_SOURCE,
    HORN_SOURCE,
    SHAFT_SOURCE,
)
from gondola.contracts.fasteners import KIT_SOURCE

FASTENER_KIT_SOURCE = KIT_SOURCE
CLAMP_SCREW_SOURCE = FASTENER_KIT_SOURCE
STACK_SCREW_SOURCE = FASTENER_KIT_SOURCE
HEX_NUT_SOURCE = FASTENER_KIT_SOURCE
SERVO_SCREW_SOURCE = "https://www.aliexpress.com/item/1005006265286201.html"
SERVO_NUT_SOURCE = "https://www.aliexpress.com/item/32977174437.html"
PURCHASING_STATUS = (
    "Design purchase/preparation specification. Selected seller options and "
    "dimensional references are distinguished in each item; received-lot "
    "dimensions, material, fit and strength remain unverified."
)

# Specification key, native CAD property, exported BOM field. Keep attachment
# and export mappings together so neither side silently loses purchase data.
PROCUREMENT_FIELDS = (
    ("search_query", "PurchaseSearchQuery", "purchase_search_query"),
    ("search_url", "PurchaseSearchURL", "purchase_search_url"),
    ("requirements", "PurchaseRequirements", "purchase_requirements"),
    ("candidate_url", "PurchaseCandidateURL", "purchase_candidate_url"),
    ("evidence_notes", "PurchaseEvidenceNotes", "purchase_evidence_notes"),
    ("status", "PurchasingStatus", "purchasing_status"),
)

PROCUREMENT_SPECS = {
    "M1_6X8_PAN_HEAD_KIT": {
        "search_query": "M1.6x8 Phillips pan head stainless screw",
        "candidate_url": SERVO_SCREW_SOURCE,
        "requirements": "Use the user's assorted M1.4/M1.6 Phillips screw kit; M1.6 x 0.35, nominal 8 mm under-head length for the four X06 mounting-ear joints. Design acceptance envelope: head diameter at most 3.5 mm, height at most 1.6 mm. These are clearance limits, not measured supplier dimensions or DIN84 certification. The length assortment is user-confirmed; select each assembled length for full nut engagement without protruding into moving parts. Use OEM screws at the servo spline and motor where appropriate; no M1.6 substitution at those threads.",
        "evidence_notes": "Saved cart selects the 500-piece M1.4/M1.6 kit. User confirms assorted lengths. Head and drive-recess dimensions remain unmeasured; the model deliberately does not invent a Phillips recess or a DIN head profile.",
    },
    "M1_6_HEX_NUT_DIN934": {
        "search_query": "M1.6 DIN934 304 hex nut 3.2mm 1.3mm",
        "candidate_url": SERVO_NUT_SOURCE,
        "requirements": "Selected seller DIN 934 / ISO 4032, 304 stainless claim, M1.6 x 0.35 hex nut, 3.2 mm across flats and 1.3 mm nominal height. Four X06 mounting-ear joints only, accessible with a small wrench; the replacement metal horns have threaded holes and need no separate horn nuts. These match the M1.6x8 screws; other joints use the selected M2 hex nuts. No washers; check actual engagement and printed support faces.",
    },
    "BEARING_3X6X2_5": {
        "search_query": "3x6x2.5mm miniature ball bearing",
        "candidate_url": BEARING_SOURCE,
        "requirements": "User-selected generic miniature bearing, nominal bore 3 mm, outside diameter 6 mm, width 2.5 mm; four on the two output axes. Check the actual shields, race lands, fit, free rotation and endplay. The servo supports its input gear through the horn coupling; no extra input bearing is selected. Do not load bearing shields or bridge the inner and outer rings with a shaft spacer.",
        "evidence_notes": "The saved cart establishes only the selected 3x6x2.5mm size option, not NSK/ISC identity, tolerance, mass or abutment limits. Retained ISC MR63ZZ references guide the nominal integral outer-ring capture clearance: housing opening at least 5.4 mm. Verify those contacts on the received generic part. ISC's 0.27 g is comparison data, not this seller's measured mass.",
    },
    "ALI_PTK_15T_4MM_HORN": {
        "search_query": "15T Single 4.0mm CNC metal servo horn M1.6 PTK",
        "candidate_url": HORN_SOURCE,
        "requirements": "Buy two horns of selected option 15T Single 4.0mm from item 1005012006498403; the project SKU is not a manufacturer part number. Use the horn's existing M1.6 threaded holes without drilling the purchased horn, two attachment screws per side at the first and third holes and no horn nuts. Keep the X06 OEM centre retaining screw; its thread is not an M1.6 assumption. The user accepts X06 V6 spline compatibility as the design premise and confirms all three arm holes are threaded M1.6. Check actual seating, centre screw engagement, adapter fit, runout and bidirectional loaded retention before powered operation.",
        "evidence_notes": "The retained seller drawing specifies overall length 18.2 mm, root width 6.1 mm, arm thickness 1.6 mm, first attachment radius 6.6 mm and one 2.8 mm interval. The third-hole 12.2 mm design radius repeats the only dimensioned 2.8 mm interval and is not independently specified; the adapter provides +/-0.4 mm radial slot travel there. The drawing does not fully establish hub diameter/height, concentricity, spline seating depth or usable thread engagement. Aluminium is a seller claim and mass is unmeasured. Verify the actual pack quantity when ordering two installed horns; title 2PCS alone is not an option-level packing confirmation.",
    },
    "M1_6X4_PAN_HEAD_KIT": {
        "search_query": "M1.6x4 Phillips pan head stainless screw",
        "candidate_url": SERVO_SCREW_SOURCE,
        "requirements": "Use four M1.6 x 0.35 screws from the user's assorted micro-screw kit, nominal 4 mm under-head length, two per metal horn. The nominal joint has 2.6 mm adapter grip and 1.4 mm horn engagement, leaving 0.2 mm behind a 1.6 mm arm; these design values require received-part checks. They fasten through the printed adapter into existing M1.6 horn threads without nuts. Require a flat under-head bearing diameter of at least 3.0 mm, within a maximum head diameter of 3.5 mm and height of 1.6 mm. Check real adapter thickness, full usable horn thread engagement and backside protrusion through the entire tilt range; choose a shorter kit length or shorten/deburr if needed. Never substitute these screws for the OEM spline retaining screw.",
        "evidence_notes": "Assorted kit lengths and all three M1.6 horn holes are user-confirmed; received head size, thread depth and installed clearance are not measured. The 4 mm selection is a nominal assembly design, not proof of safe tightening torque or actual engagement.",
    },
    "M2_HEX_NUT": {
        "search_query": "M2 black steel hex nut 4mm AF 1.6mm",
        "candidate_url": HEX_NUT_SOURCE,
        "requirements": "Selected M2 x 0.4 black-steel hex nut from the screw/nut kit. Nominal design envelope: 4 mm across flats and 1.6 mm height; accept measured nuts only within 3.8-4.0 mm across flats and 1.4-1.6 mm height. Shared by rail clamps, propulsion mounts, optical feet and pivots. No washers. Finish the nominal-4.15mm rail hex seat/port to 4.05-4.25 mm across flats and verify capture with the physical coupon: raw PA12 dimensional tolerance alone does not guarantee anti-rotation. Check actual kit dimensions, fit and usable thread engagement before tightening. Exposed nuts need a holding tool.",
        "evidence_notes": "The selected kit establishes hex nuts, not the previous thin DIN 562 square nuts. CAD dimensions are design acceptance envelopes pending receipt; they are not a measured supplier drawing or strength-class certification.",
    },
}

for _length in (6, 8):
    PROCUREMENT_SPECS[f"M2X{_length}_BUTTON_HEAD"] = {
        "search_query": f"M2x{_length} black steel button head hex socket screw",
        "candidate_url": FASTENER_KIT_SOURCE,
        "requirements": (
            f"Selected black-steel M2 x 0.4 button-head screw, {_length} mm "
            "under-head length, from the user's screw/nut kit. Design clearance "
            "envelope: head diameter 4.5 mm and head height 2 mm. Check actual "
            "head, length, 1.5 mm hex-key access and the documented joint grip. "
            + (
                "For the two optical foot clamps, require a measured flat under-head "
                "bearing diameter at least 3.5 mm and thread crest diameter at least "
                "1.8 mm; the 4.5 mm maximum head envelope alone does not establish "
                "bearing contact. Both printed clearance holes must be at most 2.9 mm. "
                if _length == 8
                else ""
            )
            + "No washers. Use minimal preload and verify PA12 retention "
            "and creep; these are not OEM motor or horn screws."
        ),
        "evidence_notes": (
            "Kit image identifies a button head, lengths 5/6/8 mm and a "
            "1.5 mm hex key. Head envelopes are deliberate design allowances, "
            "not seller-dimensioned maxima or an ISO conformity claim. The "
            "seller's 10.9 statement is unverified for the received lot. "
            "No socket recess depth or exact crown profile is assumed."
        ),
    }

for _gear in GEARS.values():
    PROCUREMENT_SPECS[_gear.sku] = {
        "search_query": f"Kailash module {MODULE_MM:g} {_gear.teeth}T gear {_gear.bore_mm:g}mm bore",
        "candidate_url": _gear.item_url,
        "requirements": (
            f"User-selected Kailash Store option: {_gear.teeth} teeth, module "
            f"{MODULE_MM:g}, pressure angle {PRESSURE_ANGLE_DEG:g} degrees, {_gear.bore_mm:g} mm bore "
            f"({_gear.bore_tolerance}), {_gear.face_width_mm:g} mm face, "
            f"{_gear.total_length_mm:g} mm overall length, "
            f"{_gear.hub_diameter_mm:g} mm hub diameter. "
            f"Material statement: {_gear.material_claim}. "
            "Radial thread is M3; screw length, point and quantity to buy "
            "separately remain to be selected after the actual interface is "
            "checked. Do not assume an included screw. Both bores are plain "
            "round nominal-3mm bores, not X06 splines."
        ),
        "evidence_notes": (
            "Selected saved supplier page and user-provided 16T drawings are "
            "retained in references/kailash_gears_selected_evidence.md. "
            "These project keys are not manufacturer order codes. The 48T "
            "material attribute conflicts with its aluminium description; "
            "the user deferred material/mass resolution without changing the "
            "selected item. Neither gear has a measured mass. The 16T "
            "drawing locates the M3 axis 2.5 mm from the hub end; the 48T "
            "axis is unpublished. Confirm mesh, axial alignment and grip "
            "with the received parts."
        ),
    }


def _shaft_dimensions(sku):
    """Decode cut lengths and optional hand-prepared flats on selected rod."""
    match = re.fullmatch(r"SS304_CUT3_L(\d+)(?:_FLAT(\d+)_A(\d+))?", sku)
    if match is None:
        if sku.startswith("SS304_CUT3_"):
            raise ValueError("Invalid nominal-3mm cut-rod preparation key")
        return None
    length = int(match.group(1))
    if not 1 <= length <= 200:
        raise ValueError("Cut length must be 1 to 200 mm for selected rod stock")
    flat_length = int(match.group(2)) if match.group(2) is not None else None
    offset = int(match.group(3)) if match.group(3) is not None else None
    if flat_length is not None and not (
        1 <= flat_length <= length and offset + flat_length <= length
    ):
        raise ValueError("Local flat must have positive length and fit within shaft")
    return length, flat_length, offset


def procurement_spec(sku, *, allow_unknown=False):
    """Return a fresh purchase/preparation contract; invalid known keys raise."""
    shaft = _shaft_dimensions(sku)
    if shaft is not None:
        length, flat_length, offset = shaft
        flat_requirement = (
            "Leave the rod round; no flat is specified. "
            if flat_length is None
            else (
                f"Prepare one local flat, nominal depth 0.5 mm, length "
                f"{flat_length} mm, starting {offset} mm from the reference "
                "end shown in CAD. A full-length flat is permitted on the "
                "input stub because it has no bearing journal. Keep every "
                "output-bearing journal round. Align the actual gear's radial "
                "set screw with the flat; tooth-to-screw clocking is not specified. "
            )
        )
        spec = {
            "search_query": "304 stainless round rod 3mm 100mm 200mm",
            "candidate_url": SHAFT_SOURCE,
            "requirements": (
                f"{sku}: cut the selected nominal-diameter-3mm 304 stainless rod "
                f"to {length} mm length. The cart contains 100/200 mm stock; this "
                "project key describes workshop preparation, not a supplier "
                "finished-shaft order. Cut square and deburr without a raised "
                "edge. " + flat_requirement + "Measure diameter, straightness "
                "and actual bearing/gear fit before cutting the full batch. Tolerance evidence is not a design blocker; the user accepts a replacement precision shaft if necessary. "
                "Use a precision nominal-3mm replacement rod if fit is "
                "inadequate; do not force an oversized or bent rod through "
                "bearings. Retention and torque transfer require physical trials."
            ),
            "evidence_notes": (
                "User selected nominal-3mm 304 rod options (100 mm and 200 mm) "
                "and authorized cutting/local-flat preparation. Seller "
                "diameter, roundness, straightness, material and length "
                "tolerances are unspecified. No h5 class, hard chrome, "
                "factory flat or guaranteed slip fit is claimed."
            ),
        }
    else:
        if allow_unknown and sku not in PROCUREMENT_SPECS:
            return None
        spec = dict(PROCUREMENT_SPECS[sku])
    spec["search_url"] = (
        "https://www.aliexpress.com/wholesale?SearchText="
        + quote_plus(spec["search_query"])
    )
    spec.setdefault("candidate_url", "")
    spec.setdefault(
        "evidence_notes",
        "The cited reference supports nominal dimensions, not a received "
        "supplier lot. Verify actual options, interfaces and material. Search "
        "links alone do not establish product selection or compatibility.",
    )
    spec["status"] = PURCHASING_STATUS
    return spec
