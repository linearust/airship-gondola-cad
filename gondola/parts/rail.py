"""Flexible PA12 base with segmented walls and side-access M2 L mounts.

Each wall slot permits local longitudinal adjustment. A flat L mount seats on
one wall; an ordinary exposed nut clamps it without a captive pocket, snap fit,
printed thread or a second flexing ear. Segment gaps preserve base compliance.
"""

import json
import math
from numbers import Real

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
from gondola.contracts.design import RAIL_BASE_THICKNESS_MM, RAIL_LENGTH_MM

V = App.Vector
LENGTH = RAIL_LENGTH_MM
PAD_CENTRES = (-140.0, 0.0, 140.0)
PAD_LENGTH, PAD_WIDTH, PAD_THICKNESS = 14.0, 32.0, RAIL_BASE_THICKNESS_MM
BASE_WIDTH = 6.0
SEGMENT_PITCH, FLEX_GAP = 50.0, 12.0
CENTRAL_WALL_LENGTH = 50.0
WEB_THICKNESS, WEB_TOP_Z = 2.5, 9.5
SLOT_HEIGHT, BOLT_AXIS_Z = 2.4, 6.5
MOUNT_LENGTH, MOUNT_LEG_THICKNESS = 16.0, 2.5
MOUNT_BOTTOM_Z, MOUNT_TOP_Z = 2.2, 11.4
MOUNT_OUTER_Y = -WEB_THICKNESS / 2 - MOUNT_LEG_THICKNESS
SLOT_END_SUPPORT_RESERVE = 1.0
SCREW_LENGTH = fasteners.RAIL_SCREW_LENGTH
TAPE_THICKNESS = 0.15
SOURCE = "https://creallo.com/ko/guide/design-spec-guide"
TOL = 1e-6


def _positive(value, description):
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(description + " must be a finite positive number")
    return float(value)


def _stations(values, length, footprint, description):
    try:
        values = tuple(values)
    except TypeError as error:
        raise ValueError(description + " must be finite numbers") from error
    if any(
        isinstance(x, bool) or not isinstance(x, Real) or not math.isfinite(x)
        for x in values
    ):
        raise ValueError(description + " must be finite numbers")
    if len(set(values)) != len(values):
        raise ValueError(description + " must be distinct")
    if any(abs(x) + footprint / 2 > length / 2 + TOL for x in values):
        raise ValueError(description + " must fit within the requested rail length")
    return tuple(float(x) for x in values)


def rounded_plate(x, length=PAD_LENGTH, width=PAD_WIDTH):
    shape = box(length, width, PAD_THICKNESS, (x - length / 2, -width / 2, 0))
    edges = [
        edge for edge in shape.Edges if edge.BoundBox.ZLength > PAD_THICKNESS - 0.01
    ]
    return shape.makeFillet(min(3.0, width / 3, length / 3), edges)


def wall_segments(length=LENGTH):
    """Clip a common 50mm wall grid; preserve only usable end remnants."""
    length = _positive(length, "Rail length")
    half_wall = (SEGMENT_PITCH - FLEX_GAP) / 2
    count = math.ceil(length / (2 * SEGMENT_PITCH))
    segments = []
    for index in range(-count, count + 1):
        centre = index * SEGMENT_PITCH
        half = CENTRAL_WALL_LENGTH / 2 if index == 0 else half_wall
        first = max(-length / 2, centre - half)
        last = min(length / 2, centre + half)
        if last - first >= MOUNT_LENGTH + 2 * SLOT_END_SUPPORT_RESERVE - TOL:
            segments.append((first, last))
    return tuple(segments)


def attachment_windows(length=LENGTH, contact_length=MOUNT_LENGTH):
    """Intersect the physical bolt slot with the requested full-foot support."""
    contact_length = _positive(contact_length, "Mount contact length")
    clearance = (SLOT_HEIGHT - fasteners.THREAD_DIAMETER) / 2
    physical_inset = MOUNT_LENGTH / 2 + SLOT_END_SUPPORT_RESERVE - clearance
    support_inset = contact_length / 2 + SLOT_END_SUPPORT_RESERVE - clearance
    inset = max(physical_inset, support_inset)
    return tuple(
        {
            "wall_x_range_mm": (first, last),
            "axis_travel_x_range_mm": (first + inset, last - inset),
        }
        for first, last in wall_segments(length)
        if first + inset <= last - inset + TOL
    )


def supported_slot_ranges(length=LENGTH, contact_length=MOUNT_LENGTH):
    """Permitted nominal centres, retaining at least0.8mm full-foot end reserve.

    The32mm propulsion foot has shorter permitted travel than the physical slot
    and cannot use19mm end walls. These are geometry limits, not a loaded fit.
    """
    return tuple(
        row["axis_travel_x_range_mm"]
        for row in attachment_windows(length, contact_length)
    )


def attachment_position_check(x, length=LENGTH, contact_length=MOUNT_LENGTH):
    if isinstance(x, bool) or not isinstance(x, Real) or not math.isfinite(x):
        return {"x_mm": x, "passed": False, "error": "Position must be finite"}
    for row in attachment_windows(length, contact_length):
        first, last = row["wall_x_range_mm"]
        low, high = row["axis_travel_x_range_mm"]
        if low - TOL <= x <= high + TOL:
            return {
                "x_mm": x,
                **row,
                "contact_length_mm": contact_length,
                "minimum_full_foot_end_margin_mm": min(
                    x - contact_length / 2 - first, last - x - contact_length / 2
                ),
                "passed": True,
            }
    return {
        "x_mm": x,
        "contact_length_mm": contact_length,
        "passed": False,
        "error": "Bolt axis outside supported wall slots",
    }


def _slot(first, last):
    radius = SLOT_HEIGHT / 2
    pieces = [
        Part.makeCylinder(
            radius,
            WEB_THICKNESS + 2,
            V(x, -WEB_THICKNESS / 2 - 1, BOLT_AXIS_Z),
            V(0, 1, 0),
        )
        for x in (first, last)
    ]
    if last > first:
        pieces.append(
            box(
                last - first,
                WEB_THICKNESS + 2,
                SLOT_HEIGHT,
                (first, -WEB_THICKNESS / 2 - 1, BOLT_AXIS_Z - radius),
            )
        )
    return union(pieces)


def rail_shape(length=LENGTH, pads=PAD_CENTRES):
    length = _positive(length, "Rail length")
    pads = _stations(pads, length, PAD_LENGTH, "Tape-wing centres")
    segments = wall_segments(length)
    if not segments:
        raise ValueError("Rail must contain at least one usable wall segment")
    pieces = [rounded_plate(0, length, BASE_WIDTH)] + [rounded_plate(x) for x in pads]
    inset = MOUNT_LENGTH / 2 + SLOT_END_SUPPORT_RESERVE
    for first, last in segments:
        wall = box(
            last - first,
            WEB_THICKNESS,
            WEB_TOP_Z - PAD_THICKNESS,
            (first, -WEB_THICKNESS / 2, PAD_THICKNESS),
        )
        pieces.append(wall.cut(_slot(first + inset, last - inset)))
    result = union(pieces).removeSplitter()
    if not result.isValid() or len(result.Solids) != 1:
        raise RuntimeError("Rail must remain one valid solid")
    return result


def mount_base_shape(top_z=MOUNT_TOP_Z, *, length=MOUNT_LENGTH):
    """One flat clamp leg and one seating roof; head and nut remain exposed."""
    top_z = _positive(top_z, "Mount top")
    length = _positive(length, "Mount length")
    if length < MOUNT_LENGTH - TOL:
        raise ValueError("Mount must retain the16mm minimum contact length")
    if top_z < WEB_TOP_Z + PAD_THICKNESS - TOL:
        raise ValueError("Mount roof must retain at least1.5mm")
    result = union(
        [
            box(
                length,
                MOUNT_LEG_THICKNESS,
                top_z - MOUNT_BOTTOM_Z,
                (-length / 2, MOUNT_OUTER_Y, MOUNT_BOTTOM_Z),
            ),
            box(
                length,
                WEB_THICKNESS + MOUNT_LEG_THICKNESS,
                top_z - WEB_TOP_Z,
                (-length / 2, MOUNT_OUTER_Y, WEB_TOP_Z),
            ),
        ]
    )
    result = result.cut(
        Part.makeCylinder(
            SLOT_HEIGHT / 2,
            WEB_THICKNESS + MOUNT_LEG_THICKNESS + 2,
            V(0, MOUNT_OUTER_Y - 1, BOLT_AXIS_Z),
            V(0, 1, 0),
        )
    ).removeSplitter()
    if not result.isValid() or len(result.Solids) != 1:
        raise RuntimeError("Rail mount must remain one valid solid")
    return result


def attachment_screw_shape(screw_length=SCREW_LENGTH):
    length = _positive(screw_length, "Screw length")
    return union(
        [
            Part.makeCylinder(
                fasteners.THREAD_DIAMETER / 2,
                length,
                V(0, MOUNT_OUTER_Y, BOLT_AXIS_Z),
                V(0, 1, 0),
            ),
            Part.makeCylinder(
                fasteners.SCREW_HEAD_DIAMETER / 2,
                fasteners.SCREW_HEAD_HEIGHT,
                V(0, MOUNT_OUTER_Y, BOLT_AXIS_Z),
                V(0, -1, 0),
            ),
        ]
    )


def _nut_outer(across_flats, thickness):
    radius = across_flats / math.sqrt(3)
    return polygon_extrusion(
        [
            (
                radius * math.cos(math.radians(a)),
                WEB_THICKNESS / 2,
                BOLT_AXIS_Z + radius * math.sin(math.radians(a)),
            )
            for a in range(0, 360, 60)
        ],
        (0, thickness, 0),
    )


def nut_shape(across_flats=fasteners.HEX_NUT_AF, thickness=fasteners.HEX_NUT_HEIGHT):
    return _nut_outer(across_flats, thickness).cut(
        Part.makeCylinder(
            fasteners.THREAD_DIAMETER / 2,
            thickness + 2,
            V(0, WEB_THICKNESS / 2 - 1, BOLT_AXIS_Z),
            V(0, 1, 0),
        )
    )


def build_attachment_hardware(doc, parent, prefix, *, x_offset=0):
    result = []
    for suffix, label, shape, sku in (
        (
            "RailMountScrew",
            "M2 x8 side rail bolt | design head envelope",
            attachment_screw_shape(),
            "M2X8_BUTTON_HEAD",
        ),
        (
            "RailMountNut",
            "M2 exposed rail hex nut | design envelope",
            nut_shape(),
            "M2_HEX_NUT",
        ),
    ):
        obj = doc.addObject("Part::Feature", prefix + suffix)
        parent.addObject(obj)
        obj.Label = "BUY | " + label
        obj.Shape = translated_shape(shape, x=x_offset)
        for key, value in (
            ("Role", "Purchased metric hardware"),
            ("HardwareSKU", sku),
            ("ThreadStandard", "ISO metric coarse M2 x0.4, right hand"),
            (
                "Notes",
                fasteners.HEAD_ENVELOPE_NOTE
                + " Nut dimensions are acceptance envelopes; hold the exposed nut with a tool. Full thread engagement and actual fit require inspection.",
            ),
            ("ModelDetail", "Simplified thread envelope; do not print"),
            ("MaterialSelection", fasteners.KIT_MATERIAL),
            ("SourceEvidence", fasteners.KIT_SOURCE),
        ):
            set_property(obj, key, value)
        set_property(obj, "NominalThreadDiameter", 2.0, "App::PropertyLength")
        set_property(obj, "ThreadPitch", 0.4, "App::PropertyLength")
        set_property(obj, "PrintPart", False, "App::PropertyBool")
        if App.GuiUp:
            obj.ViewObject.ShapeColor = (0.92, 0.64, 0.19)
        result.append(obj)
    return result


def tape_shape(x, sign=1):
    profile = [
        (7.8, PAD_THICKNESS),
        (16, PAD_THICKNESS),
        (20, 0),
        (36, 0),
        (36, TAPE_THICKNESS),
        (20, TAPE_THICKNESS),
        (16, PAD_THICKNESS + TAPE_THICKNESS),
        (7.8, PAD_THICKNESS + TAPE_THICKNESS),
    ]
    return polygon_extrusion([(x - 6, sign * y, z) for y, z in profile], (12, 0, 0))


def tape_attachment_contract():
    return {
        "wing_stations_x_mm": PAD_CENTRES,
        "wing_count": 2 * len(PAD_CENTRES),
        "base_width_mm": BASE_WIDTH,
        "attachment": "Conform before bonding. Thin double-sided tape under the continuous6mm base can distribute local loads and cover wing undersides. Six optional over-wing strips reinforce peel retention. Keep side bolts and open flex gaps accessible.",
        "reference_scope": "Saved tape solids show only optional12mm over-wing strips. Under-base adhesive thickness, mass and envelope deformation are not modeled. Z0 is the rail underside, not a certified balloon surface.",
        "qualification": "Three isolated wing pairs are not load-qualified. Check actual tape/envelope compatibility, peel, creep and loaded curvature; no adhesion strength, minimum bend radius or fatigue life is claimed.",
    }


def attachment_contract(contact_length=MOUNT_LENGTH):
    return {
        "wall_segments_x_mm": wall_segments(),
        "supported_bolt_axis_ranges_x_mm": supported_slot_ranges(
            contact_length=contact_length
        ),
        "web_thickness_mm": WEB_THICKNESS,
        "web_top_z_mm": WEB_TOP_Z,
        "outer_flex_gap_mm": FLEX_GAP,
        "central_wall_length_mm": CENTRAL_WALL_LENGTH,
        "central_adjacent_flex_gap_mm": (SEGMENT_PITCH - CENTRAL_WALL_LENGTH) / 2
        + FLEX_GAP / 2,
        "minimum_base_mm": PAD_THICKNESS,
        "slot_height_mm": SLOT_HEIGHT,
        "bolt_axis_z_mm": BOLT_AXIS_Z,
        "mount_contact_length_mm": contact_length,
        "fastener": "M2x8 button-head kit bolt and exposed M2 hex nut; unmeasured design envelopes",
        "assembly": "Lower the L seat onto one wall, insert bolt from negativeY, hold the positiveY nut and clamp both flat faces. Loosen to slide only inside that wall's supported slot. Moving between segments needs bolt removal and lift-off; no full-length continuous adjustment or self-centering mechanism.",
        "physical_acceptance": "Process-matched coupon must seat flat without rocking. Finish contact faces or reprint warped parts. Slot clearance enables assembly/alignment, not acceptable looseness in use. Hold the ordinary nut with a tool; no printed nut capture. Inspect thread engagement, head/tool access and under-base adhesive after installation.",
        "as_printed_fit_guaranteed": False,
        "physical_fit_verified": False,
        "holding_force_verified": False,
    }


def build_rail(doc):
    group = create_group(
        doc, "ContinuousRailSystem", f"{LENGTH:g}mm segmented side-slot rail"
    )
    printed = create_printed_part(
        doc,
        group,
        "ContinuousRail",
        f"PRINT | side-slot rail {LENGTH:g}mm",
        rail_shape(),
        App.Rotation(),
        "One PA12 strip with1.5mm closed base and three tape-wing pairs.2.5mm upright walls have local M2 slots; the central50mm wall has6mm free spans beside it, other gaps12mm. The broad centre supports propulsion while the continuous base permits bending. No T lips, nut pockets, printed threads or snap fit. Qualify loaded curvature, friction retention, creep and adhesion with the actual parts.",
    )
    set_property(
        printed,
        "RailAttachmentContract",
        json.dumps(attachment_contract(), sort_keys=True),
    )
    set_property(
        printed,
        "TapeAttachmentContract",
        json.dumps(tape_attachment_contract(), sort_keys=True),
    )
    set_property(printed, "SourceURL", SOURCE)
    tape_group = create_group(
        doc,
        "TapeAttachmentReference",
        "REFERENCE | optional over-wing tape; underside adhesive not modeled",
    )
    tapes = []
    for index, x in enumerate(PAD_CENTRES):
        for sign in (-1, 1):
            obj = doc.addObject(
                "Part::Feature", f"TapeWing{index}{'L' if sign < 0 else 'R'}"
            )
            tape_group.addObject(obj)
            obj.Label = "REFERENCE | optional single-sided tape over wing"
            obj.Shape = tape_shape(x, sign)
            set_property(
                obj, "Role", "Tape application reference; not a printable part"
            )
            set_property(
                obj,
                "Notes",
                "Optional12mm-wide,0.15mm-thick over-wing strip. Under-base double-sided tape is not modeled; qualify the actual bonded curvature.",
            )
            tapes.append(obj)
    return {"group": group, "printed": [printed], "tapes": tapes}


def build_coupons(doc):
    group = create_group(
        doc, "ContinuousRailFitCoupons", "Print first | M2 side-slot L fit"
    )
    samples = (
        (
            "RailFitSample",
            "PRINT FIRST | 50mm side-slot rail sample",
            rail_shape(50, (0,)),
        ),
        (
            "MountFitSample",
            "PRINT FIRST | side-slot L mount sample",
            mount_base_shape(),
        ),
    )
    printed = []
    for name, label, shape in samples:
        obj = create_printed_part(
            doc,
            group,
            name,
            label,
            shape,
            App.Rotation(),
            "Same wall/L-seat geometry as full rail. Use the actual M2x8 bolt and exposed nut; test flat seating, local sliding, side tool access and clamp retention. Short coupon does not qualify full rail adhesion, bending or creep.",
        )
        set_property(
            obj,
            "RailAttachmentContract",
            json.dumps(attachment_contract(), sort_keys=True),
        )
        printed.append(obj)
    return {"group": group, "printed": printed}


def flex_relief_check(rail_section=None, length=LENGTH):
    section = (
        rail_shape(length, () if length < LENGTH else PAD_CENTRES)
        if rail_section is None
        else rail_section
    )
    segments = wall_segments(length)
    rows = []
    for (_, first), (last, _) in zip(segments, segments[1:]):
        witness = box(
            last - first,
            BASE_WIDTH,
            WEB_TOP_Z - PAD_THICKNESS + 0.1,
            (first, -BASE_WIDTH / 2, PAD_THICKNESS),
        )
        overlap = abs(section.common(witness).Volume)
        rows.append(
            {
                "x_range_mm": (first, last),
                "above_base_obstruction_mm3": overlap,
                "passed": overlap < TOL,
            }
        )
    return {
        "open_spans": rows,
        "base_thickness_mm": PAD_THICKNESS,
        "scope": "Open above-base spans only; no stiffness, bend-radius or fatigue rating.",
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }


def attachment_check(
    rail_section=None,
    mount=None,
    *,
    screw_length=SCREW_LENGTH,
    contact_length=MOUNT_LENGTH,
):
    """Nominal local contact and release, not clamp force or whole-module service."""
    from gondola.validation.geometry import translation_sweep

    section = rail_shape(50, (0,)) if rail_section is None else rail_section
    mount = mount_base_shape(length=contact_length) if mount is None else mount
    screw, nut = attachment_screw_shape(screw_length), nut_shape()
    overlaps = {
        name: abs(first.common(second).Volume)
        for name, first, second in (
            ("rail_mount", section, mount),
            ("rail_screw", section, screw),
            ("mount_screw", mount, screw),
            ("rail_nut", section, nut),
            ("mount_nut", mount, nut),
            ("screw_nut", screw, nut),
        )
    }
    # Fill only the transverse bolt bore to form a strict planar superset.
    # Generic transverse-cylinder sweeps fall back to a bounding box that
    # incorrectly fills the open side of the L mount.
    filled_mount = mount.fuse(
        Part.makeCylinder(
            SLOT_HEIGHT / 2,
            MOUNT_LEG_THICKNESS,
            V(0, MOUNT_OUTER_Y, BOLT_AXIS_Z),
            V(0, 1, 0),
        )
    ).removeSplitter()
    lift, method = translation_sweep(filled_mount, (0, 0, 25))
    lift_overlap = abs(lift.common(section).Volume)
    # Exact full-width top seating; no guessed force/area multiplier.
    top_below = box(
        contact_length,
        WEB_THICKNESS,
        0.01,
        (-contact_length / 2, -WEB_THICKNESS / 2, WEB_TOP_Z - 0.01),
    )
    top_above = translated_shape(top_below, z=0.01)
    missing_top = abs(top_below.cut(section).Volume) + abs(top_above.cut(mount).Volume)
    # Side contact at both sides of the slot, across the entire foot.
    side = box(
        contact_length,
        0.01,
        WEB_TOP_Z - MOUNT_BOTTOM_Z,
        (-contact_length / 2, -WEB_THICKNESS / 2 - 0.01, MOUNT_BOTTOM_Z),
    )
    side = side.cut(_slot(-contact_length, contact_length))
    missing_side = abs(side.cut(mount).Volume) + abs(
        translated_shape(side, y=0.01).cut(section).Volume
    )
    head_face = Part.makeCylinder(
        fasteners.SCREW_HEAD_DIAMETER / 2,
        0.01,
        V(0, MOUNT_OUTER_Y, BOLT_AXIS_Z),
        V(0, 1, 0),
    ).cut(
        Part.makeCylinder(
            SLOT_HEIGHT / 2, 0.02, V(0, MOUNT_OUTER_Y, BOLT_AXIS_Z), V(0, 1, 0)
        )
    )
    missing_head = abs(head_face.cut(mount).Volume)
    # Ordinary nut intentionally turns freely; its support need not cover the slot.
    nut_face = _nut_outer(fasteners.HEX_NUT_AF, 0.01)
    nut_face = translated_shape(nut_face, y=-0.01).cut(
        _slot(-contact_length, contact_length)
    )
    missing_nut = abs(nut_face.cut(section).Volume)
    nut_area = nut_face.Volume / 0.01
    tip = MOUNT_OUTER_Y + screw_length
    engagement = tip - (WEB_THICKNESS / 2 + fasteners.HEX_NUT_HEIGHT)
    # Pulling the nut away in+Y leaves no pocket; exact filled-hex witness.
    nut_sweep, nut_method = translation_sweep(
        _nut_outer(fasteners.HEX_NUT_AF, fasteners.HEX_NUT_HEIGHT), (0, 10, 0)
    )
    nut_release = abs(nut_sweep.common(section).Volume) + abs(
        nut_sweep.common(mount).Volume
    )
    return {
        "seated_intersections_mm3": overlaps,
        "continuous_vertical_removal": {"method": method, "overlap_mm3": lift_overlap},
        "continuous_nut_release": {"method": nut_method, "overlap_mm3": nut_release},
        "missing_full_top_contact_mm3": missing_top,
        "missing_flat_side_contact_mm3": missing_side,
        "missing_head_support_mm3": missing_head,
        "missing_nut_support_mm3": missing_nut,
        "nut_bearing_area_outside_slot_mm2": nut_area,
        "bolt_tip_beyond_nut_mm": engagement,
        "full_nominal_nut_height_engaged": engagement >= -TOL,
        "scope": "Unloaded local geometry. Ordinary nut requires a tool; tighten after aligning. No qualified torque, friction, creep, curvature, physical fit or whole-module tool-access claim.",
        "passed": max(overlaps.values()) < TOL
        and lift_overlap < TOL
        and nut_release < TOL
        and max(missing_top, missing_side, missing_head, missing_nut) < TOL
        and nut_area > 0
        and engagement >= -TOL,
    }


def validate_mechanism():
    attachment, flex = attachment_check(), flex_relief_check()
    return {
        "passed": attachment["passed"] and flex["passed"],
        "attachment": attachment,
        "flex_relief": flex,
        "rail_length_mm": LENGTH,
        "continuous_single_rail": True,
        "supported_bolt_axis_ranges_x_mm": supported_slot_ranges(),
        "tape": tape_attachment_contract(),
        "release": "Loosen the side M2 bolt and slide within the current supported slot. To change wall segment remove the bolt and lift. Hold the ordinary nut with a tool; no full-length slide or automatic calibration.",
    }


if __name__ == "__main__":
    print(json.dumps(validate_mechanism(), indent=2))
