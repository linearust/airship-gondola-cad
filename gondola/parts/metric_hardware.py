"""Purchased M2 stack hardware, modeled as simple dimensional envelopes.

No modeled helical threads, no custom printed fasteners. The exact procurement
item remains unselected; the cited manufacturers substantiate the purchasing
geometry, not a tested marketplace SKU. All objects are excluded from STL lists.
"""

import functools
import math
from functools import partial
from urllib.parse import quote_plus

import FreeCAD as App
import Part

from gondola.cad import set_property as _set_property
from gondola.cad import translated_shape

from .fastener_spec import BODY_LENGTH as BODY_LENGTH
from .fastener_spec import FEMALE_DEPTH as FEMALE_DEPTH
from .fastener_spec import FEMALE_DEPTH_PURCHASE_MIN as FEMALE_DEPTH_PURCHASE_MIN
from .fastener_spec import JOURNAL_SCREW_LENGTH as JOURNAL_SCREW_LENGTH
from .fastener_spec import NUT_AF as NUT_AF
from .fastener_spec import NUT_HEIGHT as NUT_HEIGHT
from .fastener_spec import SCREW_HEAD_DIAMETER as SCREW_HEAD_DIAMETER
from .fastener_spec import SCREW_HEAD_HEIGHT as SCREW_HEAD_HEIGHT
from .fastener_spec import SCREW_LENGTH as SCREW_LENGTH
from .fastener_spec import SET_SCREW_KEY as SET_SCREW_KEY
from .fastener_spec import SET_SCREW_LENGTH as SET_SCREW_LENGTH
from .fastener_spec import SOCKET_DEPTH as SOCKET_DEPTH
from .fastener_spec import SOCKET_KEY as SOCKET_KEY
from .fastener_spec import SQUARE_NUT_AF as SQUARE_NUT_AF
from .fastener_spec import SQUARE_NUT_HEIGHT as SQUARE_NUT_HEIGHT
from .fastener_spec import SQUARE_NUT_MIN_AF as SQUARE_NUT_MIN_AF
from .fastener_spec import SQUARE_NUT_MIN_HEIGHT as SQUARE_NUT_MIN_HEIGHT
from .fastener_spec import STANDOFF_AF as STANDOFF_AF
from .fastener_spec import STUD_LENGTH as STUD_LENGTH
from .fastener_spec import THREAD_DIAMETER as THREAD_DIAMETER
from .fastener_spec import THREAD_PITCH as THREAD_PITCH
from .fastener_spec import WASHER_ID as WASHER_ID
from .fastener_spec import WASHER_OD as WASHER_OD
from .fastener_spec import WASHER_THICKNESS as WASHER_THICKNESS
from .universal_board import BOARD_THICKNESS, STACK_CENTRES

set_property = partial(_set_property, group="Purchased hardware")

V = App.Vector
PURCHASED_COLOR = (0.86, 0.67, 0.27)
STANDOFF_SOURCE = (
    "https://everhardwarestore.com/wp-content/uploads/2018/03/Nylon-Standoff-1.pdf"
)
WASHER_SOURCE = (
    "https://www.orbitalfasteners.co.uk/products/"
    "m2-form-a-flat-washer-stainless-steel-a2-304-din-125-2-2x5-0x0-3mm-"
)
SCREW_SOURCE = "https://www.accu.co.uk/metric-cap-head-screws/3792-SSCF-M2-6-A2"
JOURNAL_SCREW_SOURCE = (
    "https://www.accu.co.uk/metric-cap-head-screws/3796-SSCF-M2-14-A2"
)
NUT_SOURCE = "https://www.accu.co.uk/hexagon-nuts/7884-HPN-M2-A2"
SQUARE_NUT_SOURCE = "https://www.accu.co.uk/flat-square-nuts/21324-HFSN-M2-A2"
SQUARE_NUT_PTS_SOURCE = (
    "https://www.pts-uk.com/products/nuts/square-nuts/metric-a2/a56202"
)
THREAD_SOURCE = SCREW_SOURCE
NYLON_STANDOFF_CANDIDATE = (
    "https://everhardwarestore.com/product/m2-0-4-nylon-standoff-hex-m-f-spacers"
)
PURCHASING_STATUS = (
    "Specification only; no AliExpress SKU, supplier lot or actual purchased sample "
    "has been verified. Search results and cited dimensional examples are not "
    "approved purchase selections."
)

# A CAD SKU denotes the required interface, not an identified seller's listing.
# Keep these requirements with the native bought-part objects so a generated BOM
# contains the purchase conditions without relying on a separate guide.
PROCUREMENT_SPECS = {
    "M2_MF_30_PLUS_5": {
        "search_query": "M2 30+5 PA66 nylon male female standoff 4mm hex",
        "requirements": (
            "PA66 nylon, M2 x 0.4 right-hand male/female hex standoff. "
            "Shoulder-to-shoulder body length 30 mm plus 5 mm male stud; not "
            "30 mm overall. Nominal across flats 4 mm; usable female thread "
            "depth at least 4 mm (CAD nominal depth 5 mm). Confirm all dimensions "
            "and material with seller."
        ),
        "candidate_url": NYLON_STANDOFF_CANDIDATE,
        "evidence_notes": (
            "Ever Hardware's drawing lists M2*30+5, PA66, L30, male D5, "
            "female E5 and across-flats B4. The linked product page quotes "
            "1000-piece quantities. A small-quantity seller, usable thread "
            "depth, tolerances and actual sample remain unverified."
        ),
    },
    "M2X6_SOCKET_CAP": {
        "search_query": "M2x6 DIN912 A2 socket cap screw",
        "requirements": (
            "A2 stainless steel, M2 x 0.4 right-hand, 6 mm under-head length. "
            "DIN 912 / ISO 4762 socket cap shape; nominal head diameter 3.8 mm, "
            "head height 2 mm and 1.5 mm hex key."
        ),
    },
    "M2X14_SOCKET_CAP": {
        "search_query": "M2x14 DIN912 A2 socket cap screw",
        "requirements": (
            "A2 stainless steel, M2 x 0.4 right-hand, 14 mm under-head length. "
            "DIN 912 / ISO 4762 socket cap shape; nominal head diameter 3.8 mm, "
            "head height 2 mm and 1.5 mm hex key. Retains the printed sleeve; "
            "it is not a substitute for an unspecified OEM motor or horn screw."
        ),
    },
    "M2x6_ISO4026_DIN913": {
        "search_query": "M2x6 DIN913 flat point stainless set screw",
        "requirements": (
            "A2 stainless steel, M2 x 0.4 right-hand, 6 mm overall length. "
            "DIN 913 / ISO 4026 flat-point set screw with 0.9 mm hex key. "
            "Do not substitute a cup point or cone point. One screw/nut pair "
            "per bottom module; the unused opposite clamp port stays empty."
        ),
    },
    "M2_HEX_NUT": {
        "search_query": "M2 DIN934 A2 hex nut 4 1.6",
        "requirements": (
            "A2 stainless steel, DIN 934 M2 x 0.4 right-hand hex nut; nominal "
            "across flats 4 mm and height 1.6 mm. Eight nuts for stack and "
            "journal retention; rail clamps require separate DIN 562 square nuts. Confirm these dimensions "
            "rather than substituting on an ISO 4032 label alone."
        ),
    },
    "M2_SQUARE_NUT_DIN562": {
        "search_query": "M2 DIN562 A2 flat square nut 4 1.2",
        "requirements": (
            "A2 stainless steel, DIN 562 M2 x 0.4 right-hand flat square nut. "
            "Nominal width 4 mm and height 1.2 mm; accepted width 3.6-4.0 mm "
            "and height 0.8-1.2 mm. Three rail clamps only. Preserve square "
            "corners for anti-rotation; verify actual corner form and captive "
            "fit with the printed coupon. Do not substitute a hex nut."
        ),
        "candidate_url": SQUARE_NUT_SOURCE,
        "evidence_notes": (
            "Accu HFSN-M2-A2 lists width 4 +0/-0.4 mm (minimum 3.6 mm) "
            "and height 1.2 +0/-0.4 mm. PTS A56202 lists width 4.0-3.7 mm "
            "and height 1.2-0.8 mm: " + SQUARE_NUT_PTS_SOURCE + ". "
            "The tolerance check uses the broader Accu minimum width 3.6 mm. "
            "The dimensional examples do not verify the selected seller lot, "
            "corner form, thread strength or printed pocket retention."
        ),
    },
    "M2_WASHER_2.2_5_0.3": {
        "search_query": "M2 stainless washer 2.2 5 0.3",
        "requirements": (
            "A2 stainless steel flat washer, unthreaded; nominal bore 2.2 mm, "
            "outside diameter 5 mm and thickness 0.3 mm. Same specification "
            "for stack and journal retention."
        ),
    },
}


def procurement_spec(sku):
    """Return a fresh, serializable purchase contract for a modeled CAD SKU."""
    spec = dict(PROCUREMENT_SPECS[sku])
    spec["search_url"] = (
        "https://www.aliexpress.com/wholesale?SearchText="
        + quote_plus(spec["search_query"])
    )
    spec.setdefault("candidate_url", "")
    spec.setdefault(
        "evidence_notes",
        "SourceURL supports the nominal dimensions. Verify selected seller "
        "options, material and actual dimensions before purchasing; the "
        "AliExpress URL is a search link, not a verified listing.",
    )
    spec["status"] = PURCHASING_STATUS
    return spec


def add_procurement_properties(obj):
    """Annotate a bought part without altering its geometry or placement.

    Also applies to the rail's independently created clamp parts.
    Unknown future SKUs retain their existing metadata instead of silently
    acquiring an unrelated specification.
    """
    sku = str(obj.HardwareSKU)
    if sku not in PROCUREMENT_SPECS:
        return obj
    spec = procurement_spec(sku)
    for name, key in (
        ("PurchaseSearchQuery", "search_query"),
        ("PurchaseSearchURL", "search_url"),
        ("PurchaseRequirements", "requirements"),
        ("PurchaseCandidateURL", "candidate_url"),
        ("PurchaseEvidenceNotes", "evidence_notes"),
        ("PurchasingStatus", "status"),
    ):
        set_property(obj, name, spec[key])
    return obj


def hex_prism(across_flats, height, z=0):
    radius = across_flats / math.sqrt(3)
    vertices = [
        V(radius * math.cos(math.pi * i / 3), radius * math.sin(math.pi * i / 3), z)
        for i in range(6)
    ]
    return Part.Face(Part.makePolygon(vertices + [vertices[0]])).extrude(
        V(0, 0, height)
    )


@functools.lru_cache(None)
def standoff_shape(
    body_length=BODY_LENGTH,
    stud_length=STUD_LENGTH,
    across_flats=STANDOFF_AF,
    female_depth=FEMALE_DEPTH,
):
    body = hex_prism(across_flats, body_length)
    stud = Part.makeCylinder(THREAD_DIAMETER / 2, stud_length, V(0, 0, body_length))
    female = Part.makeCylinder(THREAD_DIAMETER / 2, female_depth + 0.1, V(0, 0, -0.1))
    return body.fuse(stud).cut(female).removeSplitter()


@functools.lru_cache(None)
def screw_shape(length=SCREW_LENGTH):
    # The bearing face is Z0; the head is below it and the shank points +Z.
    head = Part.makeCylinder(
        SCREW_HEAD_DIAMETER / 2, SCREW_HEAD_HEIGHT, V(0, 0, -SCREW_HEAD_HEIGHT)
    )
    shank = Part.makeCylinder(THREAD_DIAMETER / 2, length)
    drive = hex_prism(SOCKET_KEY, SOCKET_DEPTH + 0.1, -SCREW_HEAD_HEIGHT - 0.1)
    return head.fuse(shank).cut(drive).removeSplitter()


@functools.lru_cache(None)
def nut_shape():
    return (
        hex_prism(NUT_AF, NUT_HEIGHT)
        .cut(Part.makeCylinder(THREAD_DIAMETER / 2, NUT_HEIGHT + 0.2, V(0, 0, -0.1)))
        .removeSplitter()
    )


@functools.lru_cache(None)
def washer_shape():
    return (
        Part.makeCylinder(WASHER_OD / 2, WASHER_THICKNESS)
        .cut(Part.makeCylinder(WASHER_ID / 2, WASHER_THICKNESS + 0.2, V(0, 0, -0.1)))
        .removeSplitter()
    )


def add_hardware(
    doc,
    parent,
    name,
    label,
    shape,
    sku,
    notes,
    source="",
    material="Nylon PA66; verify selected supplier drawing",
):
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Invalid purchased envelope: " + name)
    obj = doc.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape.copy()
    if parent is not None:
        parent.addObject(obj)
    set_property(obj, "Role", "Purchased metric hardware")
    set_property(obj, "PrintPart", False, "App::PropertyBool")
    set_property(
        obj, "ManufacturingRoute", "Purchase separately; never export as a print part"
    )
    set_property(obj, "HardwareSKU", sku)
    set_property(
        obj,
        "ThreadStandard",
        "ISO metric coarse M2 x 0.4; right-hand. Washer is unthreaded.",
    )
    set_property(obj, "NominalThreadDiameter", THREAD_DIAMETER, "App::PropertyLength")
    set_property(obj, "ThreadPitch", THREAD_PITCH, "App::PropertyLength")
    set_property(
        obj,
        "ThreadGeometry",
        "Simplified nominal cylinders/bore only; no helical thread or thread-retention simulation",
    )
    set_property(obj, "MaterialSelection", material)
    set_property(
        obj,
        "PurchasingStatus",
        PURCHASING_STATUS,
    )
    set_property(obj, "SourceURL", source)
    set_property(obj, "Notes", notes)
    set_property(
        obj,
        "CADColorMeaning",
        "Gold denotes purchased hardware; it does not claim the selected part is brass or gold-coloured",
    )
    add_procurement_properties(obj)
    if App.GuiUp:
        obj.ViewObject.ShapeColor = PURCHASED_COLOR
        obj.ViewObject.LineColor = (0.31, 0.22, 0.07)
        obj.ViewObject.DisplayMode = "Flat Lines"
        obj.ViewObject.Visibility = True
    return obj


def stack_contract(levels=1):
    return {
        "thread": "M2 x 0.4 ISO metric coarse, right-hand",
        "standoff": {
            "body_length_mm": BODY_LENGTH,
            "male_stud_length_mm": STUD_LENGTH,
            "across_flats_envelope_mm": STANDOFF_AF,
            "female_thread_depth_mm": FEMALE_DEPTH,
            "female_depth_purchase_requirement_mm": FEMALE_DEPTH_PURCHASE_MIN,
            "material": "Nylon PA66 selected for mass; verify supplier drawing matches this envelope",
            "source": STANDOFF_SOURCE,
            "procurement": procurement_spec("M2_MF_30_PLUS_5"),
        },
        "base_screw": {
            "size": "M2 x 6 socket cap screw",
            "head_diameter_mm": SCREW_HEAD_DIAMETER,
            "head_height_mm": SCREW_HEAD_HEIGHT,
            "hex_key_mm": SOCKET_KEY,
            "source": SCREW_SOURCE,
        },
        "top_nut": {
            "size": "M2 DIN 934 hex nut",
            "across_flats_mm": NUT_AF,
            "height_mm": NUT_HEIGHT,
            "source": NUT_SOURCE,
        },
        "flat_washer": {
            "id_mm": WASHER_ID,
            "od_mm": WASHER_OD,
            "thickness_mm": WASHER_THICKNESS,
            "source": WASHER_SOURCE,
        },
        "board_thickness_mm": BOARD_THICKNESS,
        "clear_board_gap_mm": BODY_LENGTH,
        "board_pitch_mm": BODY_LENGTH + BOARD_THICKNESS,
        "bottom_screw_thread_engagement_mm": SCREW_LENGTH
        - BOARD_THICKNESS
        - WASHER_THICKNESS,
        "next_standoff_thread_engagement_mm": STUD_LENGTH - BOARD_THICKNESS,
        "top_stud_after_board_and_washer_mm": STUD_LENGTH
        - BOARD_THICKNESS
        - WASHER_THICKNESS,
        "top_nut_engagement_mm": NUT_HEIGHT,
        "stud_projection_above_top_nut_mm": STUD_LENGTH
        - BOARD_THICKNESS
        - WASHER_THICKNESS
        - NUT_HEIGHT,
        "washer_arrangement": "Washers only under bottom screw heads and top nuts. Standoff shoulders seat directly on board pads.",
        "material_commonality": "PA66 M/F posts; stainless steel nuts, washers and screws. Stack and propulsion share one M2 hex-nut and washer specification. The three rail clamps use separate DIN 562 square nuts for captive anti-rotation.",
        "purchasing_sku_count_for_base_assembly": len(PROCUREMENT_SPECS),
        "choice_rationale": "M/F posts retain the same four clearance holes and allow another level with four new posts; F/F alternatives need different connecting hardware for expansion.",
        "assembly_order": "Fit base screws and washers to the lower board off the rail, then add posts; remove the complete module from the rail before accessing bottom screws.",
        "choice_of_rail_screw_direction": "Independent of stack fasteners; the symmetric shoe provides two opposed clamp ports.",
        "adding_level": "Move the existing top washers and nuts to the new top board. Screw four new M/F standoffs directly onto the preceding studs through the intermediate board. This preserves the32mm pitch.",
        "purchase_quantities": {
            "M2_MF_30_plus_5_standoff": 4 * levels,
            "M2x6_screw": 4,
            "M2_hex_nut": 4,
            "M2_flat_washer_2.2x5x0.3": 8,
        },
        "thread_standard_source": THREAD_SOURCE,
        "limits": "Dimensional envelope and nominal engagement only; supplier dimensions, thread strength, fastening torque and assembled fit remain to be checked.",
    }


def build_stack(doc, parent, prefix="MetricStack", lower_board_bottom_z=10.2, levels=1):
    if levels < 1:
        raise ValueError("At least one added stack level is required")
    posts, locks, washers = [], [], []
    for level in range(levels):
        z = (
            lower_board_bottom_z
            + BOARD_THICKNESS
            + level * (BODY_LENGTH + BOARD_THICKNESS)
        )
        for index, (x, y) in enumerate(STACK_CENTRES, 1):
            obj = add_hardware(
                doc,
                parent,
                prefix + "Post" + str(level + 1) + "_" + str(index),
                "BUY | M2 male/female hex standoff 30+5 mm",
                standoff_shape(),
                "M2_MF_30_PLUS_5",
                "30 mm shoulder-to-shoulder body, 5 mm male stud, nominal 4 mm A/F and 5 mm female depth. "
                "Purchase PA66 nylon M2x0.4, usable female thread depth at least 4 mm. Check the chosen supplier drawing and sample. "
                "No washer under the female end; it bears directly on the board pad.",
                STANDOFF_SOURCE,
            )
            obj.Placement.Base = V(x, y, z)
            posts.append(obj)
    upper_top = (
        lower_board_bottom_z
        + BOARD_THICKNESS
        + levels * (BODY_LENGTH + BOARD_THICKNESS)
    )
    for index, (x, y) in enumerate(STACK_CENTRES, 1):
        bw = add_hardware(
            doc,
            parent,
            prefix + "BottomWasher" + str(index),
            "BUY | M2 flat washer 2.2×5×0.3 mm",
            washer_shape(),
            "M2_WASHER_2.2_5_0.3",
            "Distributes screw-head pressure on the lower printed corner pad.",
            WASHER_SOURCE,
            "A2 stainless steel",
        )
        bw.Placement.Base = V(x, y, lower_board_bottom_z - WASHER_THICKNESS)
        washers.append(bw)
        bolt = add_hardware(
            doc,
            parent,
            prefix + "BaseScrew" + str(index),
            "BUY | M2×6 socket cap screw",
            screw_shape(),
            "M2X6_SOCKET_CAP",
            "M2x0.4 thread, 6 mm length measured from the bearing face. Through 2 mm board and 0.3 mm washer, nominal female engagement is 3.7 mm. "
            "Source documents common head dimensions; the final supplier lot is unselected.",
            SCREW_SOURCE,
            "A2 stainless steel",
        )
        bolt.Placement.Base = V(x, y, lower_board_bottom_z - WASHER_THICKNESS)
        locks.append(bolt)
        tw = add_hardware(
            doc,
            parent,
            prefix + "TopWasher" + str(index),
            "BUY | M2 flat washer 2.2×5×0.3 mm",
            washer_shape(),
            "M2_WASHER_2.2_5_0.3",
            "Install between the final top board and nut. Move this washer and nut to the new top when adding a stack level.",
            WASHER_SOURCE,
            "A2 stainless steel",
        )
        tw.Placement.Base = V(x, y, upper_top)
        washers.append(tw)
        nut = add_hardware(
            doc,
            parent,
            prefix + "TopNut" + str(index),
            "BUY | M2 DIN 934 hex nut",
            nut_shape(),
            "M2_HEX_NUT",
            "M2x0.4, nominal 4 mm A/F and 1.6 mm height. With 2 mm board and 0.3 mm washer on a 5 mm stud, full nut engagement leaves 1.1 mm stud projection. "
            "Purchase a matching standard metric nut; simplified CAD bore does not model thread strength.",
            NUT_SOURCE,
            "A2 stainless steel",
        )
        nut.Placement.Base = V(x, y, upper_top + WASHER_THICKNESS)
        locks.append(nut)
    doc.recompute()
    return {
        "hardware": posts + locks + washers,
        "purchased": posts + locks + washers,
        "posts": posts,
        "locks": locks,
        "washers": washers,
        "printed": [],
        "metrics": stack_contract(levels),
    }


def validate_stack_envelopes():
    lower_board_bottom = 8.0
    post_bottom = lower_board_bottom + BOARD_THICKNESS
    upper_board_top = post_bottom + BODY_LENGTH + BOARD_THICKNESS
    base_bearing_face = lower_board_bottom - WASHER_THICKNESS
    post = translated_shape(standoff_shape(), z=post_bottom)
    bolt = translated_shape(screw_shape(), z=base_bearing_face)
    upper = translated_shape(nut_shape(), z=upper_board_top + WASHER_THICKNESS)
    bottom_washer = translated_shape(washer_shape(), z=base_bearing_face)
    top_washer = translated_shape(washer_shape(), z=upper_board_top)
    following = translated_shape(standoff_shape(), z=upper_board_top)
    shapes = {
        "post": post,
        "screw": bolt,
        "nut": upper,
        "bottom_washer": bottom_washer,
        "top_washer": top_washer,
    }
    collisions = []
    names = list(shapes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            volume = shapes[a].common(shapes[b]).Volume
            if volume > 1e-6:
                collisions.append({"a": a, "b": b, "volume_mm3": volume})
    next_overlap = post.common(following).Volume
    return {
        "valid_single_solids": all(
            s.isValid() and len(s.Solids) == 1 for s in shapes.values()
        ),
        "unintended_envelope_intersections": collisions,
        "next_level_standoff_envelope_intersection_mm3": next_overlap,
        "nominal_engagement_mm": {
            "base_screw": SCREW_LENGTH - BOARD_THICKNESS - WASHER_THICKNESS,
            "next_standoff": STUD_LENGTH - BOARD_THICKNESS,
            "top_nut": NUT_HEIGHT,
        },
        "thread_retention_is_simulated": False,
        "passed": not collisions
        and next_overlap < 1e-6
        and all(s.isValid() and len(s.Solids) == 1 for s in shapes.values()),
    }


if __name__ == "__main__":
    import json

    print(
        json.dumps(
            {"contract": stack_contract(), "checks": validate_stack_envelopes()},
            indent=2,
        ),
        flush=True,
    )
