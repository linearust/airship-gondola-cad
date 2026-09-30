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
PAD_CENTRES = (-136.0, 0.0, 136.0)
PAD_LENGTH, PAD_WIDTH, PAD_THICKNESS = 14.0, 32.0, RAIL_BASE_THICKNESS_MM
BASE_WIDTH = 5.0
WALL_LENGTH, WALL_PITCH = 26.0, 34.0
WALL_CENTRES = tuple(index * WALL_PITCH for index in range(-4, 5))
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


def _contact_length(value):
    length = _positive(value, "Mount contact length")
    if length < MOUNT_LENGTH - TOL:
        raise ValueError("Mount must retain the16mm minimum contact length")
    return length


def _slot_end_inset(contact_length=MOUNT_LENGTH):
    """Nominal slot-circle inset before accounting for bolt clearance."""
    return contact_length / 2 + SLOT_END_SUPPORT_RESERVE


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


def plate_shape(x, length=PAD_LENGTH, width=PAD_WIDTH, *, chamfer=2.0):
    """Straight plate outline with four small planar corner cuts."""
    left, right, half_width = x - length / 2, x + length / 2, width / 2
    return polygon_extrusion(
        [
            (left + chamfer, -half_width, 0),
            (right - chamfer, -half_width, 0),
            (right, -half_width + chamfer, 0),
            (right, half_width - chamfer, 0),
            (right - chamfer, half_width, 0),
            (left + chamfer, half_width, 0),
            (left, half_width - chamfer, 0),
            (left, -half_width + chamfer, 0),
        ],
        (0, 0, PAD_THICKNESS),
    )


def wall_segments(length=LENGTH):
    """Retain complete identical supports; shorter coupons never truncate a wall."""
    length = _positive(length, "Rail length")
    if length > LENGTH + TOL:
        raise ValueError("Rail length exceeds the designed wall layout")
    return tuple(
        (centre - WALL_LENGTH / 2, centre + WALL_LENGTH / 2)
        for centre in WALL_CENTRES
        if abs(centre) + WALL_LENGTH / 2 <= length / 2 + TOL
    )


def flex_spans(length=LENGTH):
    """Wall-free intervals between the selected clamp-support sections."""
    segments = wall_segments(length)
    return tuple((left[1], right[0]) for left, right in zip(segments, segments[1:]))


def base_shape(length=LENGTH):
    """Constant-width strip; only its four end corners are chamfered."""
    length = _positive(length, "Rail length")
    return plate_shape(0, length, BASE_WIDTH, chamfer=1.0)


def attachment_windows(length=LENGTH, contact_length=MOUNT_LENGTH):
    """Intersect the physical bolt slot with the requested full-foot support."""
    contact_length = _contact_length(contact_length)
    clearance = (SLOT_HEIGHT - fasteners.THREAD_DIAMETER) / 2
    inset = _slot_end_inset(max(MOUNT_LENGTH, contact_length)) - clearance
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

    Every26mm wall supports either a16mm carrier foot or the24mm propulsion
    foot. The longer foot has only0.4mm total trim. These are geometry limits,
    not a loaded fit.
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
    pieces = [base_shape(length)] + [plate_shape(x) for x in pads]
    inset = _slot_end_inset()
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
    length = _contact_length(length)
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


def _attachment_fastener(shared_drive):
    if not isinstance(shared_drive, bool):
        raise ValueError("Shared drive attachment must be a boolean")
    if shared_drive:
        from . import servo_bridge

        return servo_bridge.SHARED_SCREW_LENGTH, servo_bridge.CHEEK_OUTER_Y
    return SCREW_LENGTH, MOUNT_OUTER_Y


def attachment_screw_shape(screw_length=SCREW_LENGTH, *, head_face_y=MOUNT_OUTER_Y):
    length = _positive(screw_length, "Screw length")
    if (
        isinstance(head_face_y, bool)
        or not isinstance(head_face_y, Real)
        or not math.isfinite(head_face_y)
        or head_face_y > MOUNT_OUTER_Y
    ):
        raise ValueError("Screw head must bear on or outside the mount leg")
    return union(
        [
            Part.makeCylinder(
                fasteners.THREAD_DIAMETER / 2,
                length,
                V(0, head_face_y, BOLT_AXIS_Z),
                V(0, 1, 0),
            ),
            Part.makeCylinder(
                fasteners.SCREW_HEAD_DIAMETER / 2,
                fasteners.SCREW_HEAD_HEIGHT,
                V(0, head_face_y, BOLT_AXIS_Z),
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


def build_attachment_hardware(doc, parent, prefix, *, x_offset=0, shared_drive=False):
    screw_length, head_face_y = _attachment_fastener(shared_drive)
    result = []
    for suffix, label, shape, sku in (
        (
            "RailMountScrew",
            f"M2 x{screw_length:g} side rail bolt | design head envelope",
            attachment_screw_shape(screw_length, head_face_y=head_face_y),
            f"M2X{screw_length:g}_BUTTON_HEAD",
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
        "attachment": "Conform before bonding. Thin double-sided tape under the continuous5mm-wide base can distribute local loads and cover wing undersides. Six optional over-wing strips reinforce peel retention. Keep side bolts and open flex gaps accessible; adhesive changes compliance and must not be treated as an unloaded free-beam test.",
        "reference_scope": "Saved tape solids show only optional12mm over-wing strips. Under-base adhesive thickness, mass and envelope deformation are not modeled. Z0 is the rail underside, not a certified balloon surface.",
        "qualification": "Three isolated wing pairs are not load-qualified. Check actual tape/envelope compatibility, peel, creep and loaded curvature; no adhesion strength, minimum bend radius or fatigue life is claimed.",
    }


def attachment_contract(
    contact_length=MOUNT_LENGTH, *, length=LENGTH, shared_drive=False
):
    length = _positive(length, "Rail length")
    _contact_length(contact_length)
    spans = flex_spans(length)
    screw_length, head_face_y = _attachment_fastener(shared_drive)
    return {
        "rail_length_mm": length,
        "wall_count": len(wall_segments(length)),
        "wall_segments_x_mm": wall_segments(length),
        "supported_bolt_axis_ranges_x_mm": supported_slot_ranges(
            length, contact_length=contact_length
        ),
        "free_base_spans_x_mm": spans,
        "base_width_mm": BASE_WIDTH,
        "free_span_minimum_width_mm": BASE_WIDTH if spans else None,
        "free_span_profile": (
            "Straight constant-width and constant-thickness base. No waist, hinge, printed latch or qualified bend radius."
            if spans
            else "No free span in this rail section; clamp fit only."
        ),
        "web_thickness_mm": WEB_THICKNESS,
        "web_top_z_mm": WEB_TOP_Z,
        "minimum_base_mm": PAD_THICKNESS,
        "slot_height_mm": SLOT_HEIGHT,
        "bolt_axis_z_mm": BOLT_AXIS_Z,
        "mount_contact_length_mm": contact_length,
        "bolt_length_mm": screw_length,
        "head_bearing_y_mm": head_face_y,
        "printed_grip_mm": WEB_THICKNESS / 2 - head_face_y,
        "shared_servo_bridge_clamp": shared_drive,
        "fastener": f"M2x{screw_length:g} button-head kit bolt and exposed M2 hex nut; unmeasured design envelopes",
        "shared_joint_service": (
            "The same bolt retains the servo bridge and propulsion frame on the rail. Support both subassemblies whenever loosened or removed; keep the locating interface fully seated before tightening."
            if shared_drive
            else None
        ),
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
        "One straight5x1.5mm PA12 strip with three tape-wing pairs. Nine identical26mm-long walls at34mm pitch have local M2 slots and eight8mm free spans. Every wall supports either a16mm carrier foot or24mm propulsion foot; the latter has only0.4mm total adjustment. Small planar corner chamfers replace curved outlines. Qualify loaded curvature, lateral/torsional stability, friction retention, creep and adhesion; no whole-rail flexibility or strength rating.",
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
            "Same26mm wall/L-seat geometry as full rail. Use the actual M2x8 bolt and exposed nut; test flat seating, local sliding, side tool access and clamp retention. The companion50mm base coupon has one complete support and no inter-wall gap; it does not test full rail bending, adhesion or creep.",
        )
        set_property(
            obj,
            "RailAttachmentContract",
            json.dumps(attachment_contract(length=50), sort_keys=True),
        )
        printed.append(obj)
    return {"group": group, "printed": printed}


def flex_relief_check(rail_section=None, length=LENGTH):
    section = (
        rail_shape(length, () if length < LENGTH else PAD_CENTRES)
        if rail_section is None
        else rail_section
    )
    rows = []
    for first, last in flex_spans(length):
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
        "free_span_minimum_width_mm": BASE_WIDTH,
        "scope": "Open above-base spans only; no stiffness, bend-radius or fatigue rating.",
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }


def attachment_check(
    rail_section=None,
    mount=None,
    *,
    screw_length=SCREW_LENGTH,
    contact_length=MOUNT_LENGTH,
    head_face_y=MOUNT_OUTER_Y,
    head_support=None,
):
    """Nominal local contact and release, not clamp force or whole-module service."""
    from gondola.validation.geometry import translation_sweep

    contact_length = _contact_length(contact_length)
    section = rail_shape(50, (0,)) if rail_section is None else rail_section
    mount = mount_base_shape(length=contact_length) if mount is None else mount
    clamp = mount if head_support is None else union([mount, head_support])
    screw = attachment_screw_shape(screw_length, head_face_y=head_face_y)
    nut = nut_shape()
    overlaps = {
        name: abs(first.common(second).Volume)
        for name, first, second in (
            ("rail_mount", section, clamp),
            ("rail_screw", section, screw),
            ("mount_screw", clamp, screw),
            ("rail_nut", section, nut),
            ("mount_nut", clamp, nut),
            ("screw_nut", screw, nut),
        )
    }
    # Fill the rectangular bore envelope outside the rail web, preserving the
    # open L seat in the continuous vertical sweep. The shared locating key lies
    # away from this solid compression stack.
    filled_mount = clamp.fuse(
        box(
            SLOT_HEIGHT,
            -WEB_THICKNESS / 2 - head_face_y,
            SLOT_HEIGHT,
            (-SLOT_HEIGHT / 2, head_face_y, BOLT_AXIS_Z - SLOT_HEIGHT / 2),
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
        V(0, head_face_y, BOLT_AXIS_Z),
        V(0, 1, 0),
    ).cut(
        Part.makeCylinder(
            SLOT_HEIGHT / 2, 0.02, V(0, head_face_y, BOLT_AXIS_Z), V(0, 1, 0)
        )
    )
    missing_head = abs(head_face.cut(clamp).Volume)
    # Ordinary nut intentionally turns freely; its support need not cover the slot.
    nut_face = _nut_outer(fasteners.HEX_NUT_AF, 0.01)
    nut_face = translated_shape(nut_face, y=-0.01).cut(
        _slot(-contact_length, contact_length)
    )
    missing_nut = abs(nut_face.cut(section).Volume)
    nut_area = nut_face.Volume / 0.01
    tip = head_face_y + screw_length
    engagement = tip - (WEB_THICKNESS / 2 + fasteners.HEX_NUT_HEIGHT)
    # Pulling the nut away in+Y leaves no pocket; exact filled-hex witness.
    nut_sweep, nut_method = translation_sweep(
        _nut_outer(fasteners.HEX_NUT_AF, fasteners.HEX_NUT_HEIGHT), (0, 10, 0)
    )
    nut_release = abs(nut_sweep.common(section).Volume) + abs(
        nut_sweep.common(clamp).Volume
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
        "bolt_length_mm": screw_length,
        "head_bearing_y_mm": head_face_y,
        "printed_grip_mm": WEB_THICKNESS / 2 - head_face_y,
        "shared_head_support_supplied": head_support is not None,
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
