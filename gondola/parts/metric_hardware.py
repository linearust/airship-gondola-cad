"""Rev I purchased M3 stack hardware, modeled as simple dimensional envelopes.

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

from .universal_board import BOARD_THICKNESS, STACK_CENTRES

set_property = partial(_set_property, group="Purchased hardware")

V = App.Vector
THREAD_DIAMETER = 3.0
THREAD_PITCH = 0.5
BODY_LENGTH = 30.0
STUD_LENGTH = 6.0
STANDOFF_AF = 6.0
FEMALE_DEPTH = 7.0
SCREW_LENGTH = 6.0
SCREW_HEAD_DIAMETER = 5.5
SCREW_HEAD_HEIGHT = 3.0
NUT_AF = 5.5
NUT_HEIGHT = 2.4
WASHER_ID = 3.2
WASHER_OD = 7.0
WASHER_THICKNESS = 0.5
PURCHASED_COLOR = (0.86, 0.67, 0.27)
STANDOFF_SOURCE = "https://www.vital-parts.co.uk/threaded-hex-standoffs-male-female/11442-hmf-m3-30-s6-alu"
WASHER_SOURCE = (
    "https://www.pgb-europe.com/en-gb/9763/flat-washer-din-125a-m-3-a2-320-7-05"
)
SCREW_SOURCE = "https://www.accu.co.uk/metric-cap-head-screws/152193-SSCF-M3-6-A2-BL"
NUT_SOURCE = (
    "https://www.owlett-jaton.com/media/wysiwyg/PDFs/Owlett-Jaton_The_Catalogue_1.pdf"
)
THREAD_SOURCE = "https://www.bossard.com/-/media/bossard-group/website/documents/technical-resources/en/f-079-en.pdf"
NYLON_STANDOFF_CANDIDATE = (
    "https://www.rctimer.com/10pcs-m3x306mm-nylon-hex-standoff-male-female-p0683.html"
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
    "M3_MF_30_PLUS_6": {
        "search_query": "M3 30+6 PA66 nylon male female standoff",
        "requirements": (
            "PA66 nylon, M3 x 0.5 right-hand male/female hex standoff. "
            "Shoulder-to-shoulder body length 30 mm plus 6 mm male stud; not "
            "30 mm overall. Across flats at most 6 mm; usable female thread "
            "depth at least 6 mm. Confirm all dimensions and material with seller."
        ),
        "candidate_url": NYLON_STANDOFF_CANDIDATE,
        "evidence_notes": (
            "Rctimer documents a nylon M3 30+6 product family; PA66 grade, across "
            "flats and female thread depth remain unverified. SourceURL is an "
            "aluminium dimensional example, not evidence of PA66 material or "
            "a selected procurement item."
        ),
    },
    "M3X6_SOCKET_CAP": {
        "search_query": "M3x6 DIN912 A2 socket cap screw",
        "requirements": (
            "A2 stainless steel, M3 x 0.5 right-hand, 6 mm under-head length. "
            "DIN 912 / ISO 4762 socket cap shape; nominal head diameter 5.5 mm, "
            "head height 3 mm and 2.5 mm hex key."
        ),
    },
    "M3X16_SOCKET_CAP": {
        "search_query": "M3x16 DIN912 A2 socket cap screw",
        "requirements": (
            "A2 stainless steel, M3 x 0.5 right-hand, 16 mm under-head length. "
            "DIN 912 / ISO 4762 socket cap shape; nominal head diameter 5.5 mm, "
            "head height 3 mm and 2.5 mm hex key. Retains the printed sleeve; "
            "it is not a substitute for an unspecified OEM motor or horn screw."
        ),
    },
    "M3x8_ISO4026_DIN913": {
        "search_query": "M3x8 DIN913 flat point stainless set screw",
        "requirements": (
            "A2 stainless steel, M3 x 0.5 right-hand, 8 mm overall length. "
            "DIN 913 / ISO 4026 flat-point set screw with 1.5 mm hex key. "
            "Do not substitute a cup point or cone point. One screw/nut pair "
            "per bottom module; the unused opposite clamp port stays empty."
        ),
    },
    "M3_HEX_NUT": {
        "search_query": "M3 DIN934 A2 hex nut 5.5 2.4",
        "requirements": (
            "A2 stainless steel, regular M3 x 0.5 right-hand hex nut; nominal "
            "across flats 5.5 mm and height 2.4 mm. Same specification for "
            "stack, rail clamps and journal retention."
        ),
    },
    "M3_WASHER_3.2_7_0.5": {
        "search_query": "M3 stainless washer 3.2 7 0.5",
        "requirements": (
            "A2 stainless steel flat washer, unthreaded; nominal bore 3.2 mm, "
            "outside diameter 7 mm and thickness 0.5 mm. Same specification "
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
    drive = hex_prism(2.5, 1.4, -3.1)
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
        "ISO metric coarse M3 x 0.5; right-hand. Washer is unthreaded.",
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
        "thread": "M3 x 0.5 ISO metric coarse, right-hand",
        "standoff": {
            "body_length_mm": BODY_LENGTH,
            "male_stud_length_mm": STUD_LENGTH,
            "across_flats_envelope_mm": STANDOFF_AF,
            "female_thread_depth_mm": FEMALE_DEPTH,
            "female_depth_purchase_requirement_mm": 6.0,
            "material": "Nylon PA66 selected for mass; verify supplier drawing matches this envelope",
            "source": STANDOFF_SOURCE,
            "procurement": procurement_spec("M3_MF_30_PLUS_6"),
        },
        "base_screw": {
            "size": "M3 x 6 socket cap screw",
            "head_diameter_mm": SCREW_HEAD_DIAMETER,
            "head_height_mm": SCREW_HEAD_HEIGHT,
            "hex_key_mm": 2.5,
            "source": SCREW_SOURCE,
        },
        "top_nut": {
            "size": "M3 standard hex nut",
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
        "material_commonality": "PA66 M/F posts; stainless steel nuts, washers and screws. One common M3 nut and washer specification across rail, stack and propulsion reduces distinct procurement items.",
        "purchasing_sku_count_for_base_assembly": 6,
        "choice_rationale": "M/F posts retain the same four clearance holes and allow another level with four new posts; F/F alternatives need different connecting hardware for expansion.",
        "assembly_order": "Fit base screws and washers to the lower board off the rail, then add posts; remove the complete module from the rail before accessing bottom screws.",
        "choice_of_rail_screw_direction": "Independent of stack fasteners; the symmetric shoe provides two opposed clamp ports.",
        "adding_level": "Move the existing top washers and nuts to the new top board. Screw four new M/F standoffs directly onto the preceding studs through the intermediate board. This preserves the32mm pitch.",
        "purchase_quantities": {
            "M3_MF_30_plus_6_standoff": 4 * levels,
            "M3x6_screw": 4,
            "M3_hex_nut": 4,
            "M3_flat_washer_3.2x7x0.5": 8,
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
                "BUY | M3 male/female hex standoff30+6mm",
                standoff_shape(),
                "M3_MF_30_PLUS_6",
                "30mm shoulder-to-shoulder body,6mm male stud, nominal6mm A/F envelope and7mm female depth. "
                "Purchase PA66 nylon M3x0.5, female thread depth at least6mm. Check the chosen supplier drawing. "
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
            "BUY | M3 flat washer3.2×7×0.5",
            washer_shape(),
            "M3_WASHER_3.2_7_0.5",
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
            "BUY | M3×6 socket cap screw",
            screw_shape(),
            "M3X6_SOCKET_CAP",
            "M3x0.5 thread,6mm length measured from the bearing face. Through2mm board and0.5mm washer, nominal female engagement is3.5mm. "
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
            "BUY | M3 flat washer3.2×7×0.5",
            washer_shape(),
            "M3_WASHER_3.2_7_0.5",
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
            "BUY | M3 standard hex nut",
            nut_shape(),
            "M3_HEX_NUT",
            "M3x0.5, nominal5.5mm A/F and2.4mm height. With2mm board and0.5mm washer on a6mm stud, full nut engagement leaves1.1mm stud projection. "
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
    post = translated_shape(standoff_shape(), z=10)
    bolt = translated_shape(screw_shape(), z=7.5)
    upper = translated_shape(nut_shape(), z=42.5)
    bottom_washer = translated_shape(washer_shape(), z=7.5)
    top_washer = translated_shape(washer_shape(), z=42)
    following = translated_shape(standoff_shape(), z=42)
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
            "base_screw": 3.5,
            "next_standoff": 4.0,
            "top_nut": 2.4,
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
