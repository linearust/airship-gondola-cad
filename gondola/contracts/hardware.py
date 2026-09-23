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
SERVO_SCREW_SOURCE = (
    "https://www.accu.co.uk/metric-cheese-head-screws/6455-SFE-M1-6-8-A2"
)
SERVO_NUT_SOURCE = "https://www.ettinger.de/en/product-datasheet/4ca7065842fccd4de02bac906e3675ad/create"
BEARING_SPACER = {
    "sku": "HIROSUGI_F3035_5105T",
    "source": "https://hirosugi.co.jp/shop/g/gF2030-5805T/",
    "drawing": "https://hirosugi.co.jp/img/goods/1/Mbush_d.png",
    "material": "Free-cutting steel (trivalent chromate)",
    "bore_mm": 3.0,
    "bore_limits_mm": (3.0, 3.1),
    "neck_diameter_mm": 3.5,
    "neck_diameter_limits_mm": (3.4, 3.5),
    "flange_diameter_mm": 5.0,
    "flange_thickness_mm": 1.0,
    "neck_length_mm": 0.5,
    "overall_length_mm": 1.5,
    "scope": "Manufacturer table and drawing: neck length L excludes flange thickness t. Flange diameter, axial lengths, chamfers and received-part tolerances are not established by the published bore/neck tolerance. Used as an axial inner-ring spacer, not a replacement plain bearing. Actual bearing lands, fits, axial freedom and Korean supply remain unverified.",
}
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
    BEARING_SPACER["sku"]: {
        "search_query": "HIROSUGI F3035-5105T flanged metal bush 3 3.5 5",
        "candidate_url": BEARING_SPACER["source"],
        "requirements": "HIROSUGI F3035-5105T turned free-cutting steel flanged bush, trivalent chromate finish: bore3mm (+0.1/0), neckOD3.5mm (+0/-0.1), flangeOD5mm, flange thickness1mm and neck length0.5mm, overall1.5mm. Four used as output-bearing inner-ring spacers. Narrow neck faces the bearing; flange faces the rotating carrier. Verify actual inner-ring contact without shield/outer-ring rubbing, shaft slip fit, flange/neck length and assembled axial freedom before use. Do not substitute an ordinary M3 washer or a printed thin ring. Order acceptance, price and Korean availability are unconfirmed; manufacturer lists a50-piece minimum.",
        "evidence_notes": BEARING_SPACER["scope"],
    },
    "M1_6X8_CHEESE_HEAD": {
        "search_query": "M1.6x8 DIN84 A2 slotted cheese head screw 3mm head",
        "candidate_url": SERVO_SCREW_SOURCE,
        "requirements": "A2 stainless M1.6 x 0.35, 8 mm under-head length, DIN 84 slotted cheese head: maximum diameter 3 mm, height 1 mm, slot width 0.4 mm and depth 0.45 mm. Shared by four X06 ears and two prepared horn-tip joints. Ear screws have nominal 0.2 mm radial clearance in the published 2 mm holes and 0.5 mm head-to-case gap. Horn screws pass through a locally enlarged 1.8 mm tip hole; the head bears on the metal blade, not a printed rear strap. No washers. Check actual seating, full nut engagement and safe tightening; these are not the OEM spline-retaining screws.",
    },
    "M1_6_HEX_NUT_DIN934": {
        "search_query": "M1.6 DIN934 A2 hex nut 3.2mm 1.3mm",
        "candidate_url": SERVO_NUT_SOURCE,
        "requirements": "A2 stainless DIN 934 / ISO 4032 M1.6 x 0.35 hex nut, 3.2 mm across flats and 1.3 mm nominal height. Shared by the X06 ear and prepared horn-tip joints, accessible with a small wrench. These match the M1.6x8 screws; other joints use the selected M2 hex nuts. No washers; check actual engagement and printed support faces.",
    },
    "BEARING_3X6X2_5": {
        "search_query": "3x6x2.5mm miniature ball bearing",
        "candidate_url": BEARING_SOURCE,
        "requirements": "User-selected generic miniature bearing, nominal bore 3 mm, outside diameter 6 mm, width 2.5 mm; four on the two output axes. Check the actual shields, race lands, fit, free rotation and endplay. The servo supports its input gear through the horn coupling; no extra input bearing is selected. Do not load bearing shields or bridge the inner and outer rings with a shaft spacer.",
        "evidence_notes": "The saved cart establishes only the selected 3x6x2.5mm size option, not NSK/ISC identity, tolerance, mass or abutment limits. Retained ISC MR63ZZ references guide the nominal integral-shoulder and inner-ring-spacer clearance: inner abutment OD at most 3.7 mm and housing opening at least 5.4 mm. Verify those contacts on the received generic part. ISC's 0.27 g is comparison data, not this seller's measured mass.",
    },
    "KST_0415_13_TIP_D1_8": {
        "search_query": "KST 0415.13 aluminium servo arm 15T 4mm",
        "candidate_url": HORN_SOURCE,
        "requirements": "Buy KST 0415.13 aluminium horn, 15T / 4 mm spline class, then enlarge ONLY the existing nominal 1.0 mm tip hole at radius 13.2 mm to 1.8 mm for the M1.6 adapter screw. This project key specifies local preparation, not a manufacturer variant. Support the metal blade, preserve the existing hole centre, deburr both faces without countersinking, and reject a distorted or cracked arm. Keep all other holes, the spline and the correct OEM retaining screw unchanged; its thread/length are not inferred. The printed coupling locates the hub and tip and connects to the selected nominal-3mm input stub. Confirm actual horn revision, prepared hole, head bearing, clamping, backlash and loaded bidirectional retention before use. Do not substitute an unmeasured supplied plastic horn.",
        "evidence_notes": "KST's retained drawing establishes the original hole locations and nominal 1.6 mm blade thickness. The 1.8 mm prepared hole is a design modification; nominal residual web to the adjacent 0.8 mm hole is 0.4 mm. Alloy grade, edge quality, fatigue and joint strength remain unqualified. CAD motion checks do not qualify the modification.",
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
    match = re.fullmatch(r"AL6061_CUT3_L(\d+)(?:_FLAT(\d+)_A(\d+))?", sku)
    if match is None:
        if sku.startswith("AL6061_CUT3_"):
            raise ValueError("Invalid nominal-3mm cut-rod preparation key")
        return None
    length = int(match.group(1))
    if not 1 <= length <= 330:
        raise ValueError("Cut length must be 1 to 330 mm for selected rod stock")
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
            "search_query": "6061 aluminium round rod 3mm 330mm",
            "candidate_url": SHAFT_SOURCE,
            "requirements": (
                f"{sku}: cut the selected nominal-diameter-3mm 6061 aluminium rod "
                f"to {length} mm length. The cart stock is 330 mm long; this "
                "project key describes workshop preparation, not a supplier "
                "finished-shaft order. Cut square and deburr without a raised "
                "edge. " + flat_requirement + "Measure diameter, straightness "
                "and actual bearing/gear fit before cutting the full batch. "
                "Use a precision nominal-3mm replacement rod if fit is "
                "inadequate; do not force an oversized or bent rod through "
                "bearings. Retention and torque transfer require physical trials."
            ),
            "evidence_notes": (
                "User selected the cart's 3x330mm, five-piece 6061 rod option "
                "and authorized cutting/local-flat preparation. Seller "
                "diameter, roundness, straightness, alloy temper and length "
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
