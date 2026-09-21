"""PA12 T rail, over-tape wings and bidirectional M2 clamp.

All dimensions mm. The rail lies on the envelope at Z0. Tape is laid OVER
each lateral wing and continues onto the envelope. It never crosses the
central running head. Commercial threads are documented, not tessellated.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import (
    box,
    create_group,
    create_printed_part,
    polygon_extrusion,
    set_property,
    translated_shape,
    union,
)
from gondola.design_contract import RAIL_LENGTH_MM
from gondola.parts import fastener_spec as fastener

V = App.Vector
LENGTH = RAIL_LENGTH_MM
PAD_CENTRES = (-162.0, -108.0, -54.0, 0.0, 54.0, 108.0, 162.0)
PAD_LENGTH, PAD_WIDTH, PAD_THICKNESS = 14.0, 32.0, 1.2
BASE_WIDTH, WEB_WIDTH = 6.0, 3.0
HEAD_WIDTH, HEAD_BOTTOM, HEAD_TOP = 10.0, 5.4, 7.0
SHOE_LENGTH, SHOE_WIDTH, SHOE_BOTTOM, TOP_Z = 18.0, 22.0, 2.2, 10.2
CLEARANCE = 0.45
CLAMP_Z = 6.2
CLAMP_SHIFT_Y = 0.45
NUT_AF = fastener.SQUARE_NUT_AF
NUT_POCKET_AF, NUT_THICKNESS = 4.6, fastener.SQUARE_NUT_HEIGHT
NUT_POCKET_Y, NUT_POCKET_DEPTH = 6.95, 2.2
CLAMP_LAND_OFFSET = 4.0
RELEASE_TRAVEL = 1.2
LAND_PITCH, FLEX_GAP = 18.0, 4.5
SCREW_LENGTH = fastener.SET_SCREW_LENGTH
TAPE_THICKNESS = 0.15
SOURCE = "https://creallo.com/ko/guide/design-spec-guide"


def half_turn(s):
    a = s.copy()
    a.rotate(V(), V(0, 0, 1), 180)
    return a


def rounded_plate(x, length=PAD_LENGTH, width=PAD_WIDTH):
    p = box(length, width, PAD_THICKNESS, (x - length / 2, -width / 2, 0))
    es = [e for e in p.Edges if e.BoundBox.ZLength > PAD_THICKNESS - 0.01]
    return p.makeFillet(min(3.0, width / 3, length / 3), es)


def rail_shape(length=LENGTH, pads=PAD_CENTRES):
    # Closely spaced head lands preserve a sliding path; narrow reliefs allow
    # bending through the unbroken base instead of a stiff full-height beam.
    base = rounded_plate(0, length, BASE_WIDTH)
    web = box(
        length,
        WEB_WIDTH,
        HEAD_BOTTOM - PAD_THICKNESS,
        (-length / 2, -WEB_WIDTH / 2, PAD_THICKNESS),
    )
    cap = box(
        length,
        HEAD_WIDTH,
        HEAD_TOP - HEAD_BOTTOM,
        (-length / 2, -HEAD_WIDTH / 2, HEAD_BOTTOM),
    )
    # Round plan-view cap ends without reducing the running capture section.
    cap = cap.makeFillet(0.7, [e for e in cap.Edges if e.BoundBox.ZLength > 1.59])
    s = union([base, web, cap] + [rounded_plate(x) for x in pads])
    for i in range(
        -int(math.ceil(length / LAND_PITCH)), int(math.ceil(length / LAND_PITCH)) + 1
    ):
        x = (i + 0.5) * LAND_PITCH
        if abs(x) < length / 2:
            s = s.cut(box(FLEX_GAP, 12, 7, (x - FLEX_GAP / 2, -6, PAD_THICKNESS)))
    s = s.removeSplitter()
    # Longer reliefs offset the thicker flexure; preserve 0.5 mm root fillets.
    # This is a bending-compliance design choice, not a fatigue qualification.
    roots = [
        e
        for e in s.Edges
        if abs(e.BoundBox.ZMin - PAD_THICKNESS) < 1e-7
        and abs(e.BoundBox.ZMax - PAD_THICKNESS) < 1e-7
        and e.BoundBox.XLength < 1e-7
        and abs(e.BoundBox.YLength - WEB_WIDTH) < 1e-7
        and abs(e.CenterOfMass.x) < length / 2 - 0.1
    ]
    if roots:
        s = s.makeFillet(0.5, roots).removeSplitter()
    return s


def capture_void():
    length = 22
    return union(
        [
            box(
                length,
                WEB_WIDTH + 2 * CLEARANCE,
                HEAD_BOTTOM - CLEARANCE + 3,
                (-length / 2, -WEB_WIDTH / 2 - CLEARANCE, -3),
            ),
            box(
                length,
                HEAD_WIDTH + 2 * CLEARANCE,
                HEAD_TOP - HEAD_BOTTOM + 2 * CLEARANCE,
                (-length / 2, -HEAD_WIDTH / 2 - CLEARANCE, HEAD_BOTTOM - CLEARANCE),
            ),
        ]
    )


def hex_along_y(af, y0, length):
    r = af / math.sqrt(3)
    return polygon_extrusion(
        [
            (r * math.cos(math.radians(a)), y0, CLAMP_Z + r * math.sin(math.radians(a)))
            for a in range(0, 360, 60)
        ],
        (0, length, 0),
    )


def nut_pocket_void(width=NUT_POCKET_AF):
    # Square flats retain useful rotation blocking with M2 supplier tolerances.
    # Load from +X before equipment installation; validate the actual coupon.
    return box(
        11 + width / 2,
        NUT_POCKET_DEPTH,
        width,
        (-width / 2, NUT_POCKET_Y, CLAMP_Z - width / 2),
    )


def screw_bore_void():
    return Part.makeCylinder(1.4, 10, V(0, 4, CLAMP_Z), V(0, 1, 0))


def shoe_shape():
    s = box(
        SHOE_LENGTH,
        SHOE_WIDTH,
        TOP_Z - SHOE_BOTTOM,
        (-SHOE_LENGTH / 2, -SHOE_WIDTH / 2, SHOE_BOTTOM),
    )
    void = union([nut_pocket_void(), screw_bore_void()])
    s = s.cut(capture_void()).cut(void).cut(half_turn(void)).removeSplitter()
    if not s.isValid() or len(s.Solids) != 1:
        raise RuntimeError("Invalid integral rail shoe")
    return s


def set_screw_shape():
    # In the locked assembly the shoe moves +Y .45 until its far jaw seats.
    tip = HEAD_WIDTH / 2 - CLAMP_SHIFT_Y
    s = Part.makeCone(0.65, 1.0, 0.35, V(0, tip, CLAMP_Z), V(0, 1, 0)).fuse(
        Part.makeCylinder(
            1.0, SCREW_LENGTH - 0.35, V(0, tip + 0.35, CLAMP_Z), V(0, 1, 0)
        )
    )
    recess = hex_along_y(fastener.SET_SCREW_KEY, tip + SCREW_LENGTH - 1.2, 1.3)
    return s.cut(recess)


def nut_shape(across_flats=NUT_AF, thickness=NUT_THICKNESS):
    # Clamp load seats the nut against the outside wall of the loading slot.
    return box(
        across_flats,
        thickness,
        across_flats,
        (
            -across_flats / 2,
            NUT_POCKET_Y + NUT_POCKET_DEPTH - thickness,
            CLAMP_Z - across_flats / 2,
        ),
    ).cut(Part.makeCylinder(1.0, 4, V(0, 6.5, CLAMP_Z), V(0, 1, 0)))


def _hardware(doc, parent, name, label, shape, sku, notes):
    obj = doc.addObject("Part::Feature", name)
    parent.addObject(obj)
    obj.Label = "BUY | " + label
    obj.Shape = shape
    for key, value in [
        ("Role", "Purchased metric hardware"),
        ("HardwareSKU", sku),
        ("ThreadStandard", "ISO metric coarse M2 x 0.4, right hand"),
        ("Notes", notes),
        ("ModelDetail", "Simplified thread envelope; do not print"),
        (
            "SourceURL",
            "https://www.bossard.com/us-en/eshop/set-screws/hex-socket-set-screws-with-flat-point/p/617/",
        ),
    ]:
        set_property(obj, key, value)
    set_property(
        obj, "NominalThreadDiameter", fastener.THREAD_DIAMETER, "App::PropertyLength"
    )
    set_property(obj, "ThreadPitch", fastener.THREAD_PITCH, "App::PropertyLength")
    set_property(obj, "PrintPart", False, "App::PropertyBool")
    set_property(obj, "MaterialSelection", "A2 stainless steel")
    if App.GuiUp:
        obj.ViewObject.ShapeColor = (0.92, 0.64, 0.19)
    return obj


def build_clamp_hardware(doc, parent, prefix, side_expression):
    screw = _hardware(
        doc,
        parent,
        prefix + "RailClampScrew",
        "M2 x 6 flat-point socket set screw",
        set_screw_shape(),
        "M2x6_ISO4026_DIN913",
        "ISO4026 / DIN913 M2x0.4 x6, flat point, 0.9mm hex key. Friction clamp; no removable printed key. "
        "Loosen three turns (1.2mm) to slide. Hand snug only; no qualified torque or holding force. "
        "Screw remains in the captured nut during normal adjustment.",
    )
    nut = _hardware(
        doc,
        parent,
        prefix + "RailClampNut",
        "M2 DIN562 square nut, AF4 x1.2",
        nut_shape(),
        "M2_SQUARE_NUT_DIN562",
        "Metric M2x0.4 DIN562 square nut AF4mm, thickness1.2mm. PositiveY port loads from+X; negativeY port loads from-X. Choose one port before mounting equipment. "
        "Insert screw to retain nut. Square pocket is4.6mm wide; actual nut width/corners and coupon fit must be checked. Do not substitute a hex nut. "
        "Model seats the nut against the outside slot wall under clamp load; thin-nut torque and retention remain unqualified.",
    )
    from gondola.parts.metric_hardware import SQUARE_NUT_SOURCE

    nut.SourceURL = SQUARE_NUT_SOURCE
    for o in (screw, nut):
        set_property(
            o,
            "ClampSideNotes",
            "Follows AssemblySettings clamp approach: PositiveY or NegativeY. Exactly one screw/nut pair per base. Opposed port stays empty.",
        )
        o.setExpression(
            "Placement.Rotation.Angle", side_expression + " == 0 ? 0 deg : 180 deg"
        )
        o.Placement.Rotation.Axis = V(0, 0, 1)
    return [screw, nut]


def tape_shape(x, sign=1):
    # Separate left/right strips: accessible placement from outside, no threading.
    yz = [
        (6, PAD_THICKNESS),
        (16, PAD_THICKNESS),
        (20, 0),
        (36, 0),
        (36, TAPE_THICKNESS),
        (20, TAPE_THICKNESS),
        (16, PAD_THICKNESS + TAPE_THICKNESS),
        (6, PAD_THICKNESS + TAPE_THICKNESS),
    ]
    s = polygon_extrusion([(x - 6, sign * y, z) for y, z in yz], (12, 0, 0))
    return s


def build_rail(doc):
    group = create_group(
        doc,
        "ContinuousRailSystem",
        f"{LENGTH:g}mm continuous rail | single-sided tape over wings",
    )
    o = create_printed_part(
        doc,
        group,
        "ContinuousRail",
        f"PRINT | PA12 continuous T rail {LENGTH:g}mm",
        rail_shape(),
        App.Rotation(),
        f"PA12 SLS preferred, MJF alternative; one-piece target {LENGTH:g}x32x7mm; export oriented45deg inXY for size screening. Confirm process and one-piece acceptance with supplier before ordering. "
        "Single-sided tape covers each exposed lateral wing and extends onto balloon. Do not cover the central T head. "
        "Unbroken1.2mm base;13.5mm head lands separated by4.5mm flex reliefs at18mm pitch with0.5mm web-root fillets. Shoe bridges the narrow gaps. "
        f"Clamp only on a full land, preferably within+/-4mm of its centre, with the whole shoe supported (centre |X| <= {(LENGTH - SHOE_LENGTH) / 2:g}mm). Curvature and tape grip require a physical trial. No printed rail lock pins. "
        "The1.2mm narrow base is an intentional flexure: it exceeds generic0.8mm nylon minimum but is NOT blanket compliance with the3mm long/broad PA12 recommendation. Supplier review and physical curvature/tape trial required.",
    )
    set_property(o, "PrintProcess", "PA12 SLS or MJF")
    set_property(
        o,
        "ManufacturingException",
        f"1.2mm narrow continuous flexure and tape wings require supplier review as functional flexures; do not treat as an ordinary {LENGTH:g}mm broad plate.",
    )
    set_property(o, "SourceURL", SOURCE)
    tapes = []
    tg = create_group(
        doc,
        "TapeAttachmentReference",
        "REFERENCE | tape OVER lateral wings, adhesive down",
    )
    for i, x in enumerate(PAD_CENTRES):
        for sign in (-1, 1):
            t = doc.addObject(
                "Part::Feature", "TapeWing%d%s" % (i, "L" if sign < 0 else "R")
            )
            tg.addObject(t)
            t.Label = "REFERENCE | single-sided tape over wing"
            t.Shape = tape_shape(x, sign)
            set_property(t, "Role", "Tape application reference; not a printable part")
            set_property(
                t,
                "Notes",
                "12mm-wide strip, nominal0.15mm thickness. Place adhesive-down OVER wing then onto envelope. Each side is independent. Keep hinge gaps free. No tape under rail and no tape across sliding cap.",
            )
            tapes.append(t)
    return {"group": group, "printed": [o], "tapes": tapes}


def build_coupons(doc):
    group = create_group(
        doc, "ContinuousRailFitCoupons", "Print first | rail and M2 captive-nut fit"
    )
    r = create_printed_part(
        doc,
        group,
        "RailFitSample",
        "PRINT FIRST | 48mm T rail with tape wing",
        rail_shape(48, (0,)),
        App.Rotation(),
        "PA12 SLS/MJF sample for sliding, clamp and tape-over-wing fit. Same section as full rail.",
    )
    s = create_printed_part(
        doc,
        group,
        "ShoeFitSample",
        "PRINT FIRST | integral rail shoe with M2 nut slot",
        shoe_shape(),
        App.Rotation(),
        "Use purchased M2x6 DIN913 and M2 DIN562 square nut. Sample checks nut loading, rotation blocking, screw access and the sliding fit. No printed threads.",
    )
    return {"group": group, "printed": [r, s]}


def validate_mechanism():
    r = rail_shape(48, (0,))
    b = shoe_shape()
    locked = translated_shape(b, y=CLAMP_SHIFT_Y)

    def vol(a, b):
        return abs(a.common(b).Volume)

    phases = []
    for x in (-50, -24, -12, 0, 12, 24, 50):
        phases.append(
            {
                "translation_x_mm": x,
                "rail_shoe_overlap_mm3": vol(r, translated_shape(b, x=x)),
            }
        )
    t = union([tape_shape(0, 1), tape_shape(0, -1)])
    rows = {
        "rail_shoe": vol(r, locked),
        "rail_screw": vol(r, translated_shape(set_screw_shape(), y=CLAMP_SHIFT_Y)),
        "shoe_screw": vol(b, set_screw_shape()),
        "shoe_nut": vol(b, nut_shape()),
        "nut_screw": vol(nut_shape(), set_screw_shape()),
        "tape_shoe": vol(t, locked),
        "tape_rail": vol(t, r),
    }
    capture = {
        direction: vol(r, translated_shape(b, **delta))
        for direction, delta in [
            ("lift", {"z": 1}),
            ("left", {"y": 1}),
            ("right", {"y": -1}),
        ]
    }
    symmetry = abs(b.cut(half_turn(b)).Volume) + abs(half_turn(b).cut(b).Volume)
    negative = {
        "rail_shoe": vol(r, translated_shape(b, y=-CLAMP_SHIFT_Y)),
        "rail_screw": vol(
            r, translated_shape(half_turn(set_screw_shape()), y=-CLAMP_SHIFT_Y)
        ),
        "shoe_screw": vol(b, half_turn(set_screw_shape())),
        "shoe_nut": vol(b, half_turn(nut_shape())),
    }
    return {
        "passed": max(rows.values()) < 1e-6
        and max(negative.values()) < 1e-6
        and symmetry < 1e-6
        and all(p["rail_shoe_overlap_mm3"] < 1e-6 for p in phases)
        and all(v > 1e-5 for v in capture.values()),
        "rail_length_mm": LENGTH,
        "continuous_single_rail": True,
        "unbroken_base": True,
        "head_land_pitch_mm": LAND_PITCH,
        "head_relief_gap_mm": FLEX_GAP,
        "head_is_uninterrupted": False,
        "nominal_mating_side_gap_mm": CLEARANCE,
        "nominal_width_gap_mm": 0.9,
        "worst_case_width_gap_using_two_0_3mm_size_errors_mm": 0.3,
        "manufacturing_tolerance_rule": "Creallo SLS/MJF +/-0.3%, minimum+/-0.3mm; tolerances are not a promise of achieved local surface fit.",
        "shoe_180deg_symmetry_difference_mm3": symmetry,
        "negative_side_intersections_mm3": negative,
        "side_selection": "AssemblySettings clamp approach enumeration drives shoe seating offset and installed hardware orientation. Only one pair is installed.",
        "locked_shoe_shift_y_mm": CLAMP_SHIFT_Y,
        "seated_intersections_mm3": rows,
        "capture_collision_probes_mm3": capture,
        "released_slide_path": phases,
        "release": "Loosen M2x0.4 screw three turns, slide along rail; remove at an open rail end. No lift-off in the middle.",
        "axial_lock": "Friction only; no numerical retention/torque qualification.",
        "tape": "Two separate strips over each side wing, not under rail, not across central cap",
        "tape_to_shoe_nominal_vertical_gap_mm": SHOE_BOTTOM
        - PAD_THICKNESS
        - TAPE_THICKNESS,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(validate_mechanism(), indent=2))
