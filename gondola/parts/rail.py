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
from gondola.contracts import fasteners
from gondola.contracts.design import RAIL_LENGTH_MM
from gondola.contracts.hardware import HEX_NUT_SOURCE

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
NUT_AF = fasteners.HEX_NUT_AF
NUT_POCKET_AF, NUT_THICKNESS = 4.15, fasteners.HEX_NUT_HEIGHT
# Finished acceptance limits, not a claim about unprocessed powder-bed parts.
# The smaller corner/flat difference of a hex nut cannot absorb the former
# square slot's +/-0.3 mm variation and still guarantee rotation blocking.
NUT_FINISHED_MIN_AF, NUT_FINISHED_MAX_AF = 4.05, 4.25
NUT_POCKET_Y, NUT_POCKET_DEPTH = 6.95, 2.2
CLAMP_LAND_OFFSET = 4.0
RELEASE_TRAVEL = 1.2
LAND_PITCH, FLEX_GAP = 18.0, 4.5
SCREW_LENGTH = fasteners.RAIL_SCREW_LENGTH
TAPE_THICKNESS = 0.15
SOURCE = "https://creallo.com/ko/guide/design-spec-guide"


def half_turn(shape):
    rotated_shape = shape.copy()
    rotated_shape.rotate(V(), V(0, 0, 1), 180)
    return rotated_shape


def rounded_plate(x, length=PAD_LENGTH, width=PAD_WIDTH):
    plate = box(length, width, PAD_THICKNESS, (x - length / 2, -width / 2, 0))
    vertical_edges = [
        e for e in plate.Edges if e.BoundBox.ZLength > PAD_THICKNESS - 0.01
    ]
    return plate.makeFillet(min(3.0, width / 3, length / 3), vertical_edges)


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
    rail = union([base, web, cap] + [rounded_plate(x) for x in pads])
    for i in range(
        -int(math.ceil(length / LAND_PITCH)), int(math.ceil(length / LAND_PITCH)) + 1
    ):
        x = (i + 0.5) * LAND_PITCH
        if abs(x) < length / 2:
            rail = rail.cut(box(FLEX_GAP, 12, 7, (x - FLEX_GAP / 2, -6, PAD_THICKNESS)))
    rail = rail.removeSplitter()
    # Longer reliefs offset the thicker flexure; preserve 0.5 mm root fillets.
    # This is a bending-compliance design choice, not a fatigue qualification.
    web_root_edges = [
        e
        for e in rail.Edges
        if abs(e.BoundBox.ZMin - PAD_THICKNESS) < 1e-7
        and abs(e.BoundBox.ZMax - PAD_THICKNESS) < 1e-7
        and e.BoundBox.XLength < 1e-7
        and abs(e.BoundBox.YLength - WEB_WIDTH) < 1e-7
        and abs(e.CenterOfMass.x) < length / 2 - 0.1
    ]
    if web_root_edges:
        rail = rail.makeFillet(0.5, web_root_edges).removeSplitter()
    return rail


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


def hex_along_y(across_flats, y0, length):
    radius = across_flats / math.sqrt(3)
    return polygon_extrusion(
        [
            (
                radius * math.cos(math.radians(angle)),
                y0,
                CLAMP_Z + radius * math.sin(math.radians(angle)),
            )
            for angle in range(0, 360, 60)
        ],
        (0, length, 0),
    )


def nut_pocket_void(width=NUT_POCKET_AF):
    # A hex seat locates the nut; the flat-sided port loads from +X. The bolt
    # retains the nut laterally. Finish the port to the coupon acceptance range
    # and check the bought nut rather than claiming as-printed antirotation.
    return union(
        [
            hex_along_y(width, NUT_POCKET_Y, NUT_POCKET_DEPTH),
            box(
                SHOE_LENGTH / 2 + 1,
                NUT_POCKET_DEPTH,
                width,
                (0, NUT_POCKET_Y, CLAMP_Z - width / 2),
            ),
        ]
    )


def screw_bore_void():
    return Part.makeCylinder(1.4, 10, V(0, 4, CLAMP_Z), V(0, 1, 0))


def shoe_shape(nut_pocket_af=NUT_POCKET_AF):
    shoe = box(
        SHOE_LENGTH,
        SHOE_WIDTH,
        TOP_Z - SHOE_BOTTOM,
        (-SHOE_LENGTH / 2, -SHOE_WIDTH / 2, SHOE_BOTTOM),
    )
    clamp_void = union([nut_pocket_void(nut_pocket_af), screw_bore_void()])
    shoe = (
        shoe.cut(capture_void())
        .cut(clamp_void)
        .cut(half_turn(clamp_void))
        .removeSplitter()
    )
    if not shoe.isValid() or len(shoe.Solids) != 1:
        raise RuntimeError("Invalid integral rail shoe")
    return shoe


def clamp_screw_shape():
    # In the locked assembly the shoe moves +Y .45 until its far jaw seats.
    tip_y = HEAD_WIDTH / 2 - CLAMP_SHIFT_Y
    # The unknown screw-tip chamfer is conservatively bounded by a full shank.
    # Inspect the real end for a usable bearing face/burrs before pressing PA12.
    # An 8 mm screw puts its head 1.55 mm outside the shoe; a 6 mm one would
    # collide with the outer wall before reaching this contact plane.
    return union(
        [
            Part.makeCylinder(
                fasteners.THREAD_DIAMETER / 2,
                SCREW_LENGTH,
                V(0, tip_y, CLAMP_Z),
                V(0, 1, 0),
            ),
            Part.makeCylinder(
                fasteners.SCREW_HEAD_DIAMETER / 2,
                fasteners.SCREW_HEAD_HEIGHT,
                V(0, tip_y + SCREW_LENGTH, CLAMP_Z),
                V(0, 1, 0),
            ),
        ]
    )


def nut_shape(across_flats=NUT_AF, thickness=NUT_THICKNESS):
    # Clamp load seats the nut against the outside wall of the loading slot.
    return hex_along_y(
        across_flats, NUT_POCKET_Y + NUT_POCKET_DEPTH - thickness, thickness
    ).cut(Part.makeCylinder(1.0, 4, V(0, 6.5, CLAMP_Z), V(0, 1, 0)))


def hex_nut_capture_check():
    """Conditional geometry screen for a measured/finished hex capture.

    This deliberately does not pass the former raw +/-0.3 mm tolerance claim.
    The nut must be measured and the coupon fitted before a production print.
    A retained bolt constrains the nut axis during the rotation probes.
    """
    largest_pocket = shoe_shape(NUT_FINISHED_MAX_AF)
    tightest_pocket = shoe_shape(NUT_FINISHED_MIN_AF)
    rotations = []
    for width, height, shoe, kind in (
        (NUT_AF, NUT_THICKNESS, shoe_shape(), "nominal"),
        (
            fasteners.HEX_NUT_MIN_AF,
            fasteners.HEX_NUT_MIN_HEIGHT,
            largest_pocket,
            "smallest_accepted_nut_in_largest_finished_pocket",
        ),
    ):
        for angle in (-30, 30):
            nut = nut_shape(width, height)
            nut.rotate(V(0, 0, CLAMP_Z), V(0, 1, 0), angle)
            volume = abs(nut.common(shoe).Volume)
            rotations.append(
                {
                    "case": kind,
                    "rotation_deg": angle,
                    "blocking_intersection_mm3": volume,
                    "passed": volume > 1e-5,
                }
            )
    insertion_samples = []
    for offset in (0, 0.5, 1, 2, 4, 6, 9, 12):
        nut = translated_shape(nut_shape(), x=offset)
        volume = abs(nut.common(tightest_pocket).Volume)
        insertion_samples.append(
            {
                "translation_x_mm": offset,
                "intersection_mm3": volume,
                "passed": volume < 1e-5,
            }
        )
    corner_diameter = 2 * fasteners.HEX_NUT_MIN_AF / math.sqrt(3)
    return {
        "accepted_hex_nut_af_range_mm": [fasteners.HEX_NUT_MIN_AF, NUT_AF],
        "accepted_hex_nut_height_range_mm": [
            fasteners.HEX_NUT_MIN_HEIGHT,
            NUT_THICKNESS,
        ],
        "finished_pocket_af_range_mm": [NUT_FINISHED_MIN_AF, NUT_FINISHED_MAX_AF],
        "minimum_total_insertion_clearance_mm": NUT_FINISHED_MIN_AF - NUT_AF,
        "minimum_hex_corner_diameter_mm": corner_diameter,
        "rotation_blocking_width_margin_mm": corner_diameter - NUT_FINISHED_MAX_AF,
        "minimum_geometric_thread_turns": fasteners.HEX_NUT_MIN_HEIGHT
        / fasteners.THREAD_PITCH,
        "rotation_cases": rotations,
        "insertion_samples": insertion_samples,
        "as_printed_capture_guaranteed": False,
        "physical_fit_verified": False,
        "scope": "Nominal and finished-size geometric checks only. Inspect actual nut corners, finish the coupon to the stated size range and test insertion/rotation blocking. Raw powder-bed +/-0.3mm tolerance cannot guarantee this hex capture. No torque, thread-strength or PA12 retention qualification.",
        "passed": all(row["passed"] for row in rotations + insertion_samples),
    }


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
            fasteners.KIT_SOURCE,
        ),
    ]:
        set_property(obj, key, value)
    set_property(
        obj, "NominalThreadDiameter", fasteners.THREAD_DIAMETER, "App::PropertyLength"
    )
    set_property(obj, "ThreadPitch", fasteners.THREAD_PITCH, "App::PropertyLength")
    set_property(obj, "PrintPart", False, "App::PropertyBool")
    set_property(obj, "MaterialSelection", fasteners.KIT_MATERIAL)
    set_property(
        obj,
        "ShapeModelNotes",
        fasteners.HEAD_ENVELOPE_NOTE
        if sku.endswith("_BUTTON_HEAD")
        else "Accepted hex-nut envelope; actual kit flats, height, chamfers and threads must be measured.",
    )
    if App.GuiUp:
        obj.ViewObject.ShapeColor = (0.92, 0.64, 0.19)
    return obj


def build_clamp_hardware(doc, parent, prefix, side_expression):
    screw = _hardware(
        doc,
        parent,
        prefix + "RailClampScrew",
        "M2 x 8 kit button-head screw | design head envelope",
        clamp_screw_shape(),
        "M2X8_BUTTON_HEAD",
        "M2x0.4 x8 from the kit. Friction clamp; inspect the actual screw end and test its PA12 contact. "
        "Loosen three turns (1.2mm) to slide. Hand snug only; no qualified torque or holding force. "
        "Screw remains in the captured nut during normal adjustment. "
        + fasteners.HEAD_ENVELOPE_NOTE,
    )
    nut = _hardware(
        doc,
        parent,
        prefix + "RailClampNut",
        "M2 kit hex nut | accepted AF4 x1.6 envelope",
        nut_shape(),
        "M2_HEX_NUT",
        "M2x0.4 hex nut, accepted AF3.8-4.0mm and height1.4-1.6mm; measure the purchased lot. PositiveY port loads from+X; negativeY port loads from-X. Choose one port before mounting equipment. "
        "Insert screw to retain nut. Nominal hex seat/port AF4.15; finished flat separation must be4.05-4.25mm and rotation blocking must be verified with the coupon. Raw +/-0.3mm printing tolerance does not guarantee the hex capture. "
        "Nut seats against the outside slot wall under clamp load; torque and retention remain unqualified.",
    )
    nut.SourceURL = HEX_NUT_SOURCE
    for hardware in (screw, nut):
        set_property(
            hardware,
            "ClampSideNotes",
            "Follows AssemblySettings clamp approach: PositiveY or NegativeY. Exactly one screw/nut pair per base. Opposed port stays empty.",
        )
        hardware.setExpression(
            "Placement.Rotation.Angle", side_expression + " == 0 ? 0 deg : 180 deg"
        )
        hardware.Placement.Rotation.Axis = V(0, 0, 1)
    return [screw, nut]


def tape_shape(x, sign=1):
    # Separate left/right strips: accessible placement from outside, no threading.
    tape_profile_yz = [
        (6, PAD_THICKNESS),
        (16, PAD_THICKNESS),
        (20, 0),
        (36, 0),
        (36, TAPE_THICKNESS),
        (20, TAPE_THICKNESS),
        (16, PAD_THICKNESS + TAPE_THICKNESS),
        (6, PAD_THICKNESS + TAPE_THICKNESS),
    ]
    tape = polygon_extrusion(
        [(x - 6, sign * y, z) for y, z in tape_profile_yz], (12, 0, 0)
    )
    return tape


def build_rail(doc):
    group = create_group(
        doc,
        "ContinuousRailSystem",
        f"{LENGTH:g}mm continuous rail | single-sided tape over wings",
    )
    printed_rail = create_printed_part(
        doc,
        group,
        "ContinuousRail",
        f"PRINT | PA12 continuous T rail {LENGTH:g}mm",
        rail_shape(),
        App.Rotation(),
        f"PA12 design basis, SLS or MJF pending supplier agreement; one-piece target {LENGTH:g}x32x7mm; export oriented45deg inXY for size screening. Confirm grade, process, finish and one-piece acceptance with supplier before ordering. "
        "Single-sided tape covers each exposed lateral wing and extends onto balloon. Do not cover the central T head. "
        "Unbroken1.2mm base;13.5mm head lands separated by4.5mm flex reliefs at18mm pitch with0.5mm web-root fillets. Shoe bridges the narrow gaps. "
        f"Clamp only on a full land, preferably within+/-4mm of its centre, with the whole shoe supported (centre |X| <= {(LENGTH - SHOE_LENGTH) / 2:g}mm). Curvature and tape grip require a physical trial. No printed rail lock pins. "
        "The1.2mm narrow base is an intentional flexure: it exceeds generic0.8mm nylon minimum but is NOT blanket compliance with the3mm long/broad PA12 recommendation. Supplier review and physical curvature/tape trial required.",
    )
    set_property(printed_rail, "PrintProcess", "PA12 SLS or MJF")
    set_property(
        printed_rail,
        "ManufacturingException",
        f"1.2mm narrow continuous flexure and tape wings require supplier review as functional flexures; do not treat as an ordinary {LENGTH:g}mm broad plate.",
    )
    set_property(printed_rail, "SourceURL", SOURCE)
    tapes = []
    tape_group = create_group(
        doc,
        "TapeAttachmentReference",
        "REFERENCE | tape OVER lateral wings, adhesive down",
    )
    for i, x in enumerate(PAD_CENTRES):
        for sign in (-1, 1):
            tape_reference = doc.addObject(
                "Part::Feature", "TapeWing%d%s" % (i, "L" if sign < 0 else "R")
            )
            tape_group.addObject(tape_reference)
            tape_reference.Label = "REFERENCE | single-sided tape over wing"
            tape_reference.Shape = tape_shape(x, sign)
            set_property(
                tape_reference,
                "Role",
                "Tape application reference; not a printable part",
            )
            set_property(
                tape_reference,
                "Notes",
                "12mm-wide strip, nominal0.15mm thickness. Place adhesive-down OVER wing then onto envelope. Each side is independent. Keep hinge gaps free. No tape under rail and no tape across sliding cap.",
            )
            tapes.append(tape_reference)
    return {"group": group, "printed": [printed_rail], "tapes": tapes}


def build_coupons(doc):
    group = create_group(
        doc, "ContinuousRailFitCoupons", "Print first | rail and M2 captive-nut fit"
    )
    rail_coupon = create_printed_part(
        doc,
        group,
        "RailFitSample",
        "PRINT FIRST | 48mm T rail with tape wing",
        rail_shape(48, (0,)),
        App.Rotation(),
        "PA12 SLS/MJF sample for sliding, clamp and tape-over-wing fit. Same section as full rail.",
    )
    shoe_coupon = create_printed_part(
        doc,
        group,
        "ShoeFitSample",
        "PRINT FIRST | integral rail shoe with M2 nut slot",
        shoe_shape(),
        App.Rotation(),
        "Use kit M2x8 headed screw and M2 hex nut. Finish nut seat/port to AF4.05-4.25mm; verify insertion and rotation blocking with the actual nut, head/tool access, screw-tip contact and sliding fit. Raw printing tolerance is not sufficient for hex capture. No printed threads.",
    )
    return {"group": group, "printed": [rail_coupon, shoe_coupon]}


def validate_mechanism():
    rail = rail_shape(48, (0,))
    shoe = shoe_shape()
    locked_shoe = translated_shape(shoe, y=CLAMP_SHIFT_Y)

    def intersection_volume(first_shape, second_shape):
        return abs(first_shape.common(second_shape).Volume)

    slide_samples = []
    for x in (-50, -24, -12, 0, 12, 24, 50):
        slide_samples.append(
            {
                "translation_x_mm": x,
                "rail_shoe_overlap_mm3": intersection_volume(
                    rail, translated_shape(shoe, x=x)
                ),
            }
        )
    tape = union([tape_shape(0, 1), tape_shape(0, -1)])
    seated_intersections = {
        "rail_shoe": intersection_volume(rail, locked_shoe),
        "rail_screw": intersection_volume(
            rail, translated_shape(clamp_screw_shape(), y=CLAMP_SHIFT_Y)
        ),
        "shoe_screw": intersection_volume(shoe, clamp_screw_shape()),
        "shoe_nut": intersection_volume(shoe, nut_shape()),
        "nut_screw": intersection_volume(nut_shape(), clamp_screw_shape()),
        "tape_shoe": intersection_volume(tape, locked_shoe),
        "tape_rail": intersection_volume(tape, rail),
    }
    capture_intersections = {
        direction: intersection_volume(rail, translated_shape(shoe, **delta))
        for direction, delta in [
            ("lift", {"z": 1}),
            ("left", {"y": 1}),
            ("right", {"y": -1}),
        ]
    }
    symmetry_difference = abs(shoe.cut(half_turn(shoe)).Volume) + abs(
        half_turn(shoe).cut(shoe).Volume
    )
    negative_side_intersections = {
        "rail_shoe": intersection_volume(
            rail, translated_shape(shoe, y=-CLAMP_SHIFT_Y)
        ),
        "rail_screw": intersection_volume(
            rail, translated_shape(half_turn(clamp_screw_shape()), y=-CLAMP_SHIFT_Y)
        ),
        "shoe_screw": intersection_volume(shoe, half_turn(clamp_screw_shape())),
        "shoe_nut": intersection_volume(shoe, half_turn(nut_shape())),
    }
    return {
        "passed": max(seated_intersections.values()) < 1e-6
        and max(negative_side_intersections.values()) < 1e-6
        and symmetry_difference < 1e-6
        and all(p["rail_shoe_overlap_mm3"] < 1e-6 for p in slide_samples)
        and all(v > 1e-5 for v in capture_intersections.values()),
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
        "shoe_180deg_symmetry_difference_mm3": symmetry_difference,
        "negative_side_intersections_mm3": negative_side_intersections,
        "side_selection": "AssemblySettings clamp approach enumeration drives shoe seating offset and installed hardware orientation. Only one pair is installed.",
        "locked_shoe_shift_y_mm": CLAMP_SHIFT_Y,
        "seated_intersections_mm3": seated_intersections,
        "capture_collision_probes_mm3": capture_intersections,
        "released_slide_path": slide_samples,
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
