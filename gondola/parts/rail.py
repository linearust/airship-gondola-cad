"""Flexible twin-track PA12 rail with direct vertical metric clamps.

Bought carbon plates bridge two flat tracks. Ordinary M2 nuts enter from below
while the rail is off the balloon; the open guides do not retain an unbolted nut.
There is no sliding shoe, T-head fit or transverse screw pressing into plastic.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import (
    box,
    create_group,
    create_printed_part,
    polygon_extrusion,
    set_property,
    union,
)
from gondola.contracts import fasteners
from gondola.contracts.design import RAIL_LENGTH_MM
from gondola.contracts.hardware import HEX_NUT_SOURCE

from . import purchased_hardware

V = App.Vector
LENGTH = RAIL_LENGTH_MM
BAY_CENTRES = (-144.0, -96.0, -48.0, 0.0, 48.0, 96.0, 144.0)
BAY_PITCH = 48.0
LAND_PITCH = BAY_PITCH
BAY_LENGTH = 42.0
TRIM_LIMIT = 6.0
TRACK_OFFSET = 16.0 / math.sqrt(2)
TRACK_CENTRES_Y = (-TRACK_OFFSET, TRACK_OFFSET)
TRACK_WIDTH = 7.2
TOP_Z = 7.0
ROOF_THICKNESS = 2.0
NUT_TOP_Z = TOP_Z - ROOF_THICKNESS
NUT_GUIDE_WIDTH = 4.15
NUT_FINISHED_MIN_AF, NUT_FINISHED_MAX_AF = 4.05, 4.25
NUT_AF, NUT_THICKNESS = fasteners.HEX_NUT_AF, fasteners.HEX_NUT_HEIGHT
SLOT_WIDTH = 2.6
END_WEB_LENGTH = 2.0
BASE_THICKNESS = 1.2
FLEXURE_WIDTH = 3.0
FLEX_ROOT_RADIUS = 0.5
FLEX_GAP = BAY_PITCH - BAY_LENGTH
PAD_CENTRES = BAY_CENTRES
PAD_LENGTH, PAD_WIDTH, PAD_THICKNESS = 14.0, 52.0, BASE_THICKNESS
TAPE_THICKNESS = 0.15
SOURCE = "https://creallo.com/ko/guide/design-spec-guide"
CLAMP_CENTRES = tuple((0.0, y) for y in TRACK_CENTRES_Y)
CARBON_THICKNESS = 1.0
CARBON_HALF_DIAGONAL = 30.0 / math.sqrt(2)
CARBON_CONTACT_HALF_LENGTH = CARBON_HALF_DIAGONAL - (TRACK_OFFSET - TRACK_WIDTH / 2)


def half_turn(shape):
    result = shape.copy()
    result.rotate(V(), V(0, 0, 1), 180)
    return result


def rounded_plate(x, length=PAD_LENGTH, width=PAD_WIDTH):
    shape = box(length, width, PAD_THICKNESS, (x - length / 2, -width / 2, 0))
    edges = [
        edge for edge in shape.Edges if edge.BoundBox.ZLength > PAD_THICKNESS - 0.01
    ]
    return shape.makeFillet(min(3.0, width / 3, length / 3), edges)


def slot_shape(x=0.0, y=0.0, bottom=NUT_TOP_Z - 0.1, depth=ROOF_THICKNESS + 0.2):
    """One closed-ended longitudinal M2 slot; accepted centre travel is +/-6mm."""
    radius = SLOT_WIDTH / 2
    return union(
        [
            box(
                2 * TRIM_LIMIT, SLOT_WIDTH, depth, (x - TRIM_LIMIT, y - radius, bottom)
            ),
            Part.makeCylinder(radius, depth, V(x - TRIM_LIMIT, y, bottom)),
            Part.makeCylinder(radius, depth, V(x + TRIM_LIMIT, y, bottom)),
        ]
    ).removeSplitter()


def nut_access_shape(x=0.0, y=0.0, guide_width=NUT_GUIDE_WIDTH):
    """Open underside between solid end webs; no blind floor or screw-tip stop."""
    return box(
        BAY_LENGTH - 2 * END_WEB_LENGTH,
        guide_width,
        NUT_TOP_Z + 1,
        (x - BAY_LENGTH / 2 + END_WEB_LENGTH, y - guide_width / 2, -1),
    )


def bay_shape(x=0.0, *, guide_width=NUT_GUIDE_WIDTH):
    tracks = []
    for y in TRACK_CENTRES_Y:
        track = box(
            BAY_LENGTH, TRACK_WIDTH, TOP_Z, (x - BAY_LENGTH / 2, y - TRACK_WIDTH / 2, 0)
        )
        tracks.append(
            track.cut(nut_access_shape(x, y, guide_width)).cut(slot_shape(x, y))
        )
    shape = union(tracks + [rounded_plate(x)])
    # These openings are functional nut access, not cable-tie features. They
    # continue through the transverse tape rung and keep its outer wings intact.
    for y in TRACK_CENTRES_Y:
        shape = shape.cut(nut_access_shape(x, y, guide_width))
    return shape.removeSplitter()


def rail_shape(length=LENGTH, pads=None, *, guide_width=NUT_GUIDE_WIDTH):
    centres = (
        tuple(pads)
        if pads is not None
        else tuple(x for x in BAY_CENTRES if abs(x) + BAY_LENGTH / 2 <= length / 2)
    )
    if not centres or sorted(centres) != list(centres):
        raise ValueError("Rail requires ordered flat-bay centres")
    if any(abs(x) + BAY_LENGTH / 2 > length / 2 + 1e-7 for x in centres):
        raise ValueError("A flat bay extends beyond the selected rail length")
    shapes = [bay_shape(x, guide_width=guide_width) for x in centres]
    starts = [-length / 2] + [x + BAY_LENGTH / 2 - 1 for x in centres]
    ends = [x - BAY_LENGTH / 2 + 1 for x in centres] + [length / 2]
    for start, end in zip(starts, ends):
        if end <= start:
            continue
        for y in TRACK_CENTRES_Y:
            shapes.append(
                box(
                    end - start,
                    FLEXURE_WIDTH,
                    BASE_THICKNESS,
                    (start, y - FLEXURE_WIDTH / 2, 0),
                )
            )
    shape = union(shapes).removeSplitter()
    roots = [
        edge
        for edge in shape.Edges
        if edge.BoundBox.XLength < 1e-7
        and abs(edge.BoundBox.ZMin - BASE_THICKNESS) < 1e-7
        and abs(edge.BoundBox.ZMax - BASE_THICKNESS) < 1e-7
        and abs(edge.BoundBox.YLength - FLEXURE_WIDTH) < 1e-7
    ]
    if roots:
        shape = shape.makeFillet(FLEX_ROOT_RADIUS, roots).removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Twin-track rail must be one valid solid")
    return shape


def clamp_rows(
    *, plate_thickness_mm=CARBON_THICKNESS, centre_xy_mm=(0.0, 0.0), parent_z_mm=0.0
):
    """Local source shapes for two vertical joints; parent placement adds station.

    Carbon1mm uses M2x6; propulsion foot3mm uses M2x8. Both have the same
    nominal tipZ2 and nutZ3.4..5 before the parent-frame transform. parent_z_mm is4.8 for
    the raised propulsion group. No nut or bolt is shared with FC soft mounting.
    """
    if plate_thickness_mm not in (1.0, 3.0):
        raise ValueError(
            "Only validated nominal1mm plate or3mm frame grips are defined"
        )
    length = plate_thickness_mm + 5.0
    cx, cy = centre_xy_mm
    bearing_z = TOP_Z + plate_thickness_mm - parent_z_mm
    rows = []
    for sign, label in ((-1, "NegativeY"), (1, "PositiveY")):
        x, y = cx, cy + sign * TRACK_OFFSET
        screw = purchased_hardware.screw_shape(length).copy()
        screw.rotate(V(), V(1, 0, 0), 180)
        screw.translate(V(x, y, bearing_z))
        nut = purchased_hardware.hex_nut_shape().copy()
        nut.translate(V(x, y, NUT_TOP_Z - NUT_THICKNESS - parent_z_mm))
        for kind, shape, sku in (
            ("Screw", screw, f"M2X{int(length)}_BUTTON_HEAD"),
            ("Nut", nut, "M2_HEX_NUT"),
        ):
            rows.append(
                {
                    "suffix": f"RailClamp{label}{kind}",
                    "kind": kind.lower(),
                    "shape": shape,
                    "sku": sku,
                    "centre_xy_mm": (x, y),
                    "axis_direction": (0, 0, -1),
                    "bolt_length_mm": length,
                    "bearing_z_mm": bearing_z,
                    "head_top_z_mm": bearing_z + fasteners.SCREW_HEAD_HEIGHT,
                    "nut_top_z_mm": NUT_TOP_Z - parent_z_mm,
                    "plate_thickness_mm": plate_thickness_mm,
                }
            )
    return rows


def build_clamp_hardware(
    doc,
    parent,
    prefix,
    *,
    plate_thickness_mm=CARBON_THICKNESS,
    centre_xy_mm=(0.0, 0.0),
    parent_z_mm=0.0,
):
    objects = []
    for row in clamp_rows(
        plate_thickness_mm=plate_thickness_mm,
        centre_xy_mm=centre_xy_mm,
        parent_z_mm=parent_z_mm,
    ):
        note = (
            "Vertical rigid plate/frame clamp to the twin-track roof. Two independent M2 joints; "
            "the guide contains an ordinary hex nut. Loosen only enough to slide within the same flat bay. "
            "Disconnect equipment and remove the rail from the balloon for underside nut insertion/removal. "
            "An unbolted nut is not captured and can fall out. Do not clamp across a flexure or force warped contact flat. "
            "Verify actual screw length, full nut engagement, tip/balloon gap, roof contact, flatness and loaded retention. "
            "No qualified tightening torque, PA12 creep or holding force. "
        )
        obj = purchased_hardware.add_hardware(
            doc,
            parent,
            prefix + row["suffix"],
            "BUY | vertical M2 direct rail " + row["kind"],
            row["shape"],
            row["sku"],
            note
            + (
                fasteners.HEAD_ENVELOPE_NOTE
                if row["kind"] == "screw"
                else "Finish/check guide flat separation4.05-4.25mm against actual AF3.8-4.0 nut; raw PA12 tolerance does not guarantee insertion or antirotation."
            ),
            fasteners.KIT_SOURCE if row["kind"] == "screw" else HEX_NUT_SOURCE,
            material=fasteners.KIT_MATERIAL,
        )
        set_property(obj, "RailClampKind", row["kind"])
        set_property(obj, "RailClampJoint", prefix)
        set_property(
            obj,
            "RailClampContract",
            json.dumps(
                {key: value for key, value in row.items() if key != "shape"},
                sort_keys=True,
            ),
        )
        objects.append(obj)
    return objects


def nearest_bay(x):
    return min(BAY_CENTRES, key=lambda value: abs(x - value))


def rail_support_check(shape, x, *, half_contact_length_mm=CARBON_CONTACT_HALF_LENGTH):
    centre = nearest_bay(x)
    delta = x - centre
    slot_probes = [
        Part.makeCylinder(1.0, ROOF_THICKNESS + 0.2, V(x, y, NUT_TOP_Z - 0.1))
        for y in TRACK_CENTRES_Y
    ]
    overlaps = [abs(shape.common(probe).Volume) for probe in slot_probes]
    support_missing = []
    for y in TRACK_CENTRES_Y:
        for side in (-1, 1):
            inner = y + side * (SLOT_WIDTH / 2 + 0.1)
            outer = y + side * (TRACK_WIDTH / 2 - 0.1)
            strip = box(
                4.0,
                abs(outer - inner),
                ROOF_THICKNESS - 0.2,
                (x - 2, min(inner, outer), NUT_TOP_Z + 0.1),
            )
            support_missing.append(abs(strip.cut(shape).Volume))
    remaining = BAY_LENGTH / 2 - abs(delta) - half_contact_length_mm
    return {
        "bay_centre_mm": centre,
        "trim_mm": delta,
        "trim_limit_mm": TRIM_LIMIT,
        "filled_plate_contact_end_margin_mm": remaining,
        "fastener_path_overlap_mm3": overlaps,
        "roof_support_missing_mm3": support_missing,
        "scope": "Planar landing and fastener-path check only; filled carbon envelope is not proof of received material/contact or strength.",
        "passed": abs(delta) <= TRIM_LIMIT + 1e-7
        and remaining >= 0
        and all(v < 1e-6 for v in overlaps + support_missing),
    }


def flex_relief_check(rail_section=None, length=LENGTH):
    shape = rail_section if rail_section is not None else rail_shape(length)
    centres = [x for x in BAY_CENTRES if abs(x) + BAY_LENGTH / 2 <= length / 2]
    rows = []
    for left, right in zip(centres, centres[1:]):
        middle = (left + right) / 2
        for y in TRACK_CENTRES_Y:
            core = box(
                FLEX_GAP - 0.2,
                FLEXURE_WIDTH - 0.2,
                BASE_THICKNESS - 0.2,
                (middle - FLEX_GAP / 2 + 0.1, y - FLEXURE_WIDTH / 2 + 0.1, 0.1),
            )
            above = box(
                FLEX_GAP - 2 * FLEX_ROOT_RADIUS - 0.2,
                TRACK_WIDTH,
                TOP_Z,
                (
                    middle - FLEX_GAP / 2 + FLEX_ROOT_RADIUS + 0.1,
                    y - TRACK_WIDTH / 2,
                    BASE_THICKNESS + 0.01,
                ),
            )
            missing = abs(core.cut(shape).Volume)
            blocked = abs(above.common(shape).Volume)
            rows.append(
                {
                    "centre_xy_mm": [middle, y],
                    "missing_base_mm3": missing,
                    "blocked_relief_mm3": blocked,
                    "passed": missing < 1e-6 and blocked < 1e-6,
                }
            )
    return {
        "rows": rows,
        "passed": all(row["passed"] for row in rows),
        "scope": "Straight undeformed geometry only; no curvature, fatigue or tape qualification.",
    }


def fit_contract():
    return {
        "interface": "Direct carbon/frame vertical clamps on two flat slotted PA12 tracks",
        "rail_length_mm": LENGTH,
        "bay_centres_x_mm": BAY_CENTRES,
        "bay_length_mm": BAY_LENGTH,
        "bay_pitch_mm": BAY_PITCH,
        "accepted_trim_each_bay_mm": [-TRIM_LIMIT, TRIM_LIMIT],
        "track_centres_y_mm": TRACK_CENTRES_Y,
        "track_width_mm": TRACK_WIDTH,
        "support_face_z_mm": TOP_Z,
        "roof_thickness_mm": ROOF_THICKNESS,
        "slot_width_mm": SLOT_WIDTH,
        "slot_centre_travel_mm": [-TRIM_LIMIT, TRIM_LIMIT],
        "nut_guide_width_mm": NUT_GUIDE_WIDTH,
        "nut_finished_flat_separation_mm": [NUT_FINISHED_MIN_AF, NUT_FINISHED_MAX_AF],
        "nut_top_z_mm": NUT_TOP_Z,
        "open_bottom_guide": True,
        "unbolted_nut_captured": False,
        "shoe_required": False,
        "flexure_section_mm": [FLEXURE_WIDTH, BASE_THICKNESS],
        "flexure_gap_mm": FLEX_GAP,
        "flexure_root_radius_mm": FLEX_ROOT_RADIUS,
        "carbon_axes": "Two opposed16mm-pattern holes on Y after45deg plate rotation; four25.5mm FC axes remain separate.",
        "carbon_contact_half_length_mm": CARBON_CONTACT_HALF_LENGTH,
        "carbon_flat_contact_end_margin_at_max_trim_mm": BAY_LENGTH / 2
        - TRIM_LIMIT
        - CARBON_CONTACT_HALF_LENGTH,
        "clamp": "Carbon1mm uses twoM2x6 and ordinaryM2 nuts. A3mm propulsion foot uses twoM2x8. Both nominal screw tipsZ2; nutsZ3.4..5. Roof contact and actual nut/thread dimensions require inspection.",
        "service": "Fit and load nuts from below with rail detached from the balloon. Unscrew and lift the module to change bays. Sliding is limited to the same flat bay after loosening; it is not full-length shoe travel. Unbolted nuts can fall out. Remove overlying equipment when it blocks top driver access.",
        "tape": "Independent tape strips over exposed outer wings only. Keep tracks, underside nut openings and6mm flexure gaps free. No separate cable-tie holes.",
        "qualification": "Flat nominal CAD and geometric continuity do not qualify laminate contact, PA12 clamp strength/creep, curvature, flexure fatigue, adhesive retention or hardware fit. Print a matching one-bay coupon and test actual bought plates/nuts. Do not use flexible bay gaps as clamp stations.",
    }


def tape_shape(x, sign=1):
    inner = TRACK_OFFSET + TRACK_WIDTH / 2 + 1.0
    edge = PAD_WIDTH / 2
    profile = [
        (inner, PAD_THICKNESS),
        (edge, PAD_THICKNESS),
        (edge + 4, 0),
        (edge + 20, 0),
        (edge + 20, TAPE_THICKNESS),
        (edge + 4, TAPE_THICKNESS),
        (edge, PAD_THICKNESS + TAPE_THICKNESS),
        (inner, PAD_THICKNESS + TAPE_THICKNESS),
    ]
    return polygon_extrusion([(x - 6, sign * y, z) for y, z in profile], (12, 0, 0))


def build_rail(doc):
    group = create_group(
        doc,
        "ContinuousRailSystem",
        f"{LENGTH:g}mm flexible twin-track rail | direct metric clamps",
    )
    printed = create_printed_part(
        doc,
        group,
        "ContinuousRail",
        "PRINT | PA12 flexible twin-slot rail",
        rail_shape(),
        App.Rotation(),
        "One-piece340mm PA12 SLS/MJF candidate; supplier/process/finish acceptance pending. Seven42mm flat clamp bays at48mm pitch join through two3x1.2mm flexure strips across6mm gaps with0.5mm root fillets. Each7.2mm track has2mm roof,2.6mm top slot and open4.15mm nut guide. No shoe, side clamp or printed thread. Carbon uses its two16mm Y axes after45deg rotation; slide at most+/-6mm within one bay. Nut access continues through tape rungs; nuts are not captured when unbolted. Fit coupon first and verify actual contact, curvature, tape, hardware access, tightening and creep. Do not infer received carbon material from its filled clearance envelope.",
    )
    set_property(printed, "PrintProcess", "PA12 SLS or MJF")
    set_property(printed, "RailFitContract", json.dumps(fit_contract(), sort_keys=True))
    set_property(
        printed,
        "ManufacturingException",
        "1.2mm narrow flexures and tape wings need supplier and physical curvature/fatigue review; not ordinary broad-plate qualification.",
    )
    set_property(printed, "SourceURL", SOURCE)
    tapes = []
    tape_group = create_group(
        doc, "TapeAttachmentReference", "REFERENCE | tape over outer wings"
    )
    for index, x in enumerate(PAD_CENTRES):
        for sign in (-1, 1):
            obj = doc.addObject(
                "Part::Feature", f"TapeWing{index}{'L' if sign < 0 else 'R'}"
            )
            tape_group.addObject(obj)
            obj.Label = "REFERENCE | single-sided tape over wing"
            obj.Shape = tape_shape(x, sign)
            set_property(
                obj, "Role", "Tape application reference; not a printable part"
            )
            set_property(
                obj,
                "Notes",
                "12mm-wide strip over the outer wing then balloon; keep flexures, tracks and nut-access openings free. Adhesive/curvature qualification required.",
            )
            tapes.append(obj)
    return {"group": group, "printed": [printed], "tapes": tapes}


def build_coupons(doc):
    group = create_group(
        doc,
        "ContinuousRailFitCoupons",
        "Print first | direct plate clamp and nut guide",
    )
    coupon = create_printed_part(
        doc,
        group,
        "RailFitSample",
        "PRINT FIRST | one48mm twin-track bay",
        rail_shape(48, (0,)),
        App.Rotation(),
        "Use the selected bought carbon plate and twoM2x6/hex nuts to inspect this matched PA12 bay: guide fit and antirotation, full nut engagement, tip clearance, flat contact, +/-6mm trim, top tool/underside service and tape. An unbolted nut can fall out. Raw printing does not guarantee guide fit; measured finished AF4.05-4.25mm is conditional on the actual nut. No separate shoe coupon is needed.",
    )
    set_property(coupon, "RailFitContract", json.dumps(fit_contract(), sort_keys=True))
    return {"group": group, "printed": [coupon]}


def validate_mechanism():
    shape = rail_shape()
    support = [
        rail_support_check(shape, x + offset)
        for x in BAY_CENTRES
        for offset in (-TRIM_LIMIT, 0, TRIM_LIMIT)
    ]
    hardware = clamp_rows()
    collisions = [
        {"suffix": row["suffix"], "overlap_mm3": abs(shape.common(row["shape"]).Volume)}
        for row in hardware
    ]
    flexures = flex_relief_check(shape)
    return {
        "passed": shape.isValid()
        and len(shape.Solids) == 1
        and all(row["passed"] for row in support)
        and all(row["overlap_mm3"] < 1e-6 for row in collisions)
        and flexures["passed"],
        "fit_contract": fit_contract(),
        "support_checks": support,
        "nominal_hardware_collisions": collisions,
        "flexures": flexures,
        "physical_fit_verified": False,
    }
