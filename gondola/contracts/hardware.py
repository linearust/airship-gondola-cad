"""Portable purchase and stock-preparation contracts.

Project purchase keys distinguish selected options; they are not manufacturer
part numbers or received-lot certification. Native geometry lives in parts.
"""

import re
from urllib.parse import quote_plus

from gondola.contracts import servo_horns
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
        "requirements": "Selected seller DIN 934 / ISO 4032, 304 stainless claim, M1.6 x 0.35 hex nut, 3.2 mm across flats and 1.3 mm nominal height. Four X06 mounting-ear joints only, seated in shallow antirotation recesses. For service, remove the ear screws before lifting out the nuts; follow the checked screw-first sequence. These match the M1.6x8 screws. The selected X06 stock plastic horns use separate M1 hex bolts and nuts. Structural M2 joints use the selected M2 hex nuts. No washers; check actual engagement and printed support faces.",
    },
    "BEARING_3X6X2_5": {
        "search_query": "3x6x2.5mm miniature ball bearing",
        "candidate_url": BEARING_SOURCE,
        "requirements": "Keep the four purchased generic miniature bearings, nominal bore 3 mm, outside diameter 6 mm, width 2.5 mm, on the two output axes; no replacement bearing purchase. Check actual shields, race lands, fixed-seat fit, free rotation and endplay with the split housing, outer-ring shoulders and removable cap. The two M2x10 screws seat each cap on hard frame lands, not on the bearing. The servo supports its input gear through the horn coupling; no extra input bearing is selected. Do not load bearing shields or bridge the inner and outer rings with a shaft spacer.",
        "evidence_notes": "The user confirms purchase of the original-final-cart 3x6x2.5mm option, not NSK/ISC identity, tolerance, mass or abutment limits. Retained ISC MR63ZZ references guide the outer-ring contact clearance: housing opening at least 5.4 mm. Verify those contacts on the received generic part; the printed diameter5.6 openings are design values, not proof of shield clearance. ISC's 0.27 g is comparison data, not this seller's measured mass.",
    },
    "KST_X06_STOCK_HALF_ARM_1": {
        "search_query": "KST X06 stock plastic half servo arm 1",
        "candidate_url": HORN_SOURCE,
        "requirements": servo_horns.preparation_note(),
        "evidence_notes": "Manufacturer nominal STEP retained unchanged in gondola/data/kst_x06_half_arm_1.step; original archive and hash manifest retained. Material, actual mass, delivered tolerances, spline seating and loaded retention remain unmeasured.",
    },
    "M1X6_HEX_HEAD": {
        "search_query": "M1 x 0.25 x 6 miniature external hex bolt",
        "candidate_url": "",
        "requirements": servo_horns.preparation_note(),
        "evidence_notes": "User confirmed owned metric M1 hex bolts/nuts on2026-10-02, but no length, head dimensions or material. M1 defines the thread, not a universal external-head envelope; use the coupling contract's acceptance bounds. Design length is not confirmation of owned stock. No substitution at the OEM centre screw.",
    },
    "M1_HEX_NUT": {
        "search_query": "M1 x 0.25 miniature hex nut 2.5mm AF",
        "candidate_url": "",
        "requirements": servo_horns.preparation_note(),
        "evidence_notes": "Owned M1 nut confirmed by user, actual dimensions/material not measured. Reference dimensions and design acceptance limits do not certify the owned lot. The historical cart's M1.4 brass nuts are superseded for this interface.",
    },
    "M2_HEX_NUT": {
        "search_query": "M2 black steel hex nut 4mm AF 1.6mm",
        "candidate_url": HEX_NUT_SOURCE,
        "requirements": "Selected M2 x 0.4 black-steel ordinary hex nut from the screw/nut kit. Nominal design envelope: 4 mm across flats and 1.6 mm height; accept measured nuts only within 3.8-4.0 mm across flats and 1.35-1.6 mm height. Shared by propulsion mechanism joints, the optical carrier foot/pitch joints and optional power feet. The five rail joints use separate M3 hardware. No washers. Rotor and optical joints use recessed nut seats; bearing caps use accessible ordinary hex-nut seats, and the input-shaft clamps retain their existing nut pockets. Trial actual nut chamfers, flank engagement, seating and removal in each finished feature. General PA12 tolerance alone does not guarantee fit or torque restraint. Check usable thread engagement before tightening. Optional power-portal foot nuts still need a holding tool. No flange, locknut or thin-nut substitution is qualified.",
        "evidence_notes": "The selected kit establishes hex nuts, not the previous thin DIN 562 square nuts. The Fastenal DIN934 dimensional reference lists M2 AF3.82-4.0 and height1.35-1.6 mm; the accepted minimum AF3.8 is conservative. These are CAD acceptance dimensions, not a measured supplier drawing or strength-class certification of the selected lot.",
    },
    "M3_HEX_NUT": {
        "search_query": "M3 0.5 hex nut 5.5mm AF 2.4mm A2 stainless",
        "candidate_url": "",
        "requirements": "Five ordinary M3 x 0.5 hex nuts for the three carrier rail shoes and two opposed integrated-propulsion rail joints. Nominal design acceptance envelope: 5.5 mm across flats and 2.4 mm height. The opposite U leg has a 5.9 mm across-flats hex pocket with a 2 mm nominal floor; ordinary carrier legs are symmetric 4 mm stock with 2 mm recess depth, so the nut is partly exposed; the nut bears on printed stock, not the rail. Check actual antirotation fit, bearing contact, thread engagement and straight outward removal. No washers or printed threads. A2 stainless steel is the design material selection, not confirmation of the owned stock grade.",
        "evidence_notes": "M3 hardware is already owned, but no selected supplier drawing, received dimensions or grade certificate establishes this envelope. Verify the stock before printing and replace it if needed. The CAD hex pocket is externally accessible for insertion, withdrawal and powder removal; nominal clearance does not qualify print fit or loaded retention.",
    },
}

for _length in (6, 8, 10, 12):
    PROCUREMENT_SPECS[f"M2X{_length}_BUTTON_HEAD"] = {
        "search_query": f"M2x{_length} black steel button head hex socket screw",
        "candidate_url": FASTENER_KIT_SOURCE,
        "requirements": (
            f"Selected black-steel M2 x 0.4 button-head screw, {_length} mm "
            "under-head length, from the user's screw/nut kit. Design clearance "
            "envelope: head diameter 4.5 mm and head height 2 mm. Check actual "
            "head, length, 1.5 mm hex-key access and the documented joint grip. "
            + (
                "For the optical carrier-foot clamp and two optional power-platform foot clamps, require a measured flat under-head "
                "bearing diameter at least 3.5 mm and thread crest diameter at least "
                "1.8 mm; the 4.5 mm maximum head envelope alone does not establish "
                "bearing contact. Finished carrier slots and power-foot bores must be at most 2.9 mm wide. "
                "Centre each screw axis within 0.1 mm across its slot, fully tighten the seated "
                "clamp, and verify at least 0.2 mm of transverse bearing land on both sides "
                "at the head diameter. Full shank side clearance is not an accepted head position "
                "or operating motion; inspect final centring after tightening. "
                if _length == 8
                else ""
            )
            + "The five rail joints use separate M3 hardware. No washers by default; "
            "qualify actual bearing contact, PA12 retention and creep. These are "
            "not OEM motor or horn screws."
        ),
        "evidence_notes": (
            "Kit image identifies a button head and assorted lengths including6/8/10/12mm, with a "
            "1.5 mm hex key. Head envelopes are deliberate design allowances, "
            "not seller-dimensioned maxima or an ISO conformity claim. The "
            "seller's 10.9 statement is unverified for the received lot. "
            "No socket recess depth or exact crown profile is assumed."
        ),
    }

for _length in (10,):
    PROCUREMENT_SPECS[f"M3X{_length}_BUTTON_HEAD"] = {
        "search_query": f"M3x{_length} button head hex socket screw A2 stainless",
        "candidate_url": "",
        "requirements": (
            f"M3 x 0.5 screw with {_length} mm under-head length for "
            + "all five standard carrier-shoe rail joints, including both propulsion stations. "
            "A 2 mm recessed head floor, 2.5 mm rail web and 2 mm nut floor give "
            "6.5 mm effective grip. A nominal 2.4 mm nut leaves 1.1 mm tip projection. "
            "Support the complete propulsion assembly before releasing either paired clamp. "
            + "Design acceptance envelope: head diameter at most 6 mm and "
            "head height at most 2 mm. These limits are not a supplier drawing "
            "or a standard button-head conformity claim. Verify a flat bearing "
            "face beyond the 3.4 mm clearance opening, actual head/recess fit, "
            "key access, full thread engagement and clear projection. The "
            "opposite downward-open hex recess prevents ordinary M3 nut rotation "
            "on a nominal 2 mm bearing floor; hold the nut until the bolt engages. "
            "Fit both rigid U legs before tightening; do not use bolt "
            "force to close a loose channel. No washers or "
            "spring preload; actual clamping, PA12 creep and friction retention "
            "require physical checks. A2 stainless steel is the design material "
            "selection, not confirmation of the owned stock grade."
        ),
        "evidence_notes": (
            "M3 hardware is already owned; supplier head dimensions, grade, "
            "socket size/depth and exact crown profile remain unverified. "
            "The diameter 6 mm by height 2 mm head is an explicit design "
            "acceptance envelope, not measured stock or vendor conformity. "
            "Measure stock against the recessed joint before printing; select "
            "matching replacement hardware if the envelope is not met."
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
    match = re.fullmatch(r"SS304_CUT3_L(\d+)(?:_FLAT(\d+)(?:_GRIP(\d+))?_A(\d+))?", sku)
    if match is None:
        if sku.startswith("SS304_CUT3_"):
            raise ValueError("Invalid nominal-3mm cut-rod preparation key")
        return None
    length = int(match.group(1))
    if not 1 <= length <= 200:
        raise ValueError("Cut length must be 1 to 200 mm for selected rod stock")
    flat_length = int(match.group(2)) if match.group(2) is not None else None
    grip_length = int(match.group(3)) if match.group(3) is not None else None
    offset = int(match.group(4)) if match.group(4) is not None else None
    if flat_length is not None and not (
        1 <= flat_length <= length and offset + flat_length <= length
    ):
        raise ValueError("Local flat must have positive length and fit within shaft")
    if grip_length is not None and not (
        1 <= grip_length < length - offset - flat_length
    ):
        raise ValueError(
            "Opposite-end flats must leave a round bearing-journal interval"
        )
    return length, flat_length, offset, grip_length


def procurement_spec(sku, *, allow_unknown=False):
    """Return a fresh purchase/preparation contract; invalid known keys raise."""
    shaft = _shaft_dimensions(sku)
    if shaft is not None:
        length, flat_length, offset, grip_length = shaft
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
        if grip_length is not None:
            flat_requirement += (
                f"Prepare a second0.5mm-deep flat over the final{grip_length}mm "
                "from the opposite motor-grip end, on the same side of the rod. "
                "Leave the entire intervening bearing-journal interval round. "
                "The flats key torque; gear and carrier jack screws provide axial grip. "
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
