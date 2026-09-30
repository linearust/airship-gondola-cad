"""Flexible PA12 base with segmented walls and recessed M3 U mounts.

Each wall slot permits local longitudinal adjustment. A U mount surrounds the
wall with one loaded clamp leg and a clearance guard. The nut bears directly
on the rail through a hexagonal guard window; segment gaps retain compliance.
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
WEB_THICKNESS, WEB_TOP_Z = 2.5, 10.5
SLOT_HEIGHT, BOLT_AXIS_Z = 3.4, 7.0
MOUNT_LENGTH, MOUNT_LEG_THICKNESS = 16.0, 4.0
MOUNT_BOTTOM_Z, MOUNT_TOP_Z = 2.2, 12.5
MOUNT_OUTER_Y = -WEB_THICKNESS / 2 - MOUNT_LEG_THICKNESS
HEAD_RECESS_DIAMETER, HEAD_RECESS_DEPTH = 6.4, 2.0
HEAD_BEARING_Y = MOUNT_OUTER_Y + HEAD_RECESS_DEPTH
GUARD_GAP, GUARD_THICKNESS = 0.2, 2.5
GUARD_INNER_Y = WEB_THICKNESS / 2 + GUARD_GAP
GUARD_OUTER_Y = GUARD_INNER_Y + GUARD_THICKNESS
NUT_WINDOW_AF = 5.9
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
    clearance = (SLOT_HEIGHT - fasteners.RAIL_THREAD_DIAMETER) / 2
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


def head_recess_shape(outer_y, *, x=0, z=BOLT_AXIS_Z):
    """Counterbore cutter for an M3 head, entering from the negative-Y face."""
    return Part.makeCylinder(
        HEAD_RECESS_DIAMETER / 2,
        HEAD_RECESS_DEPTH + 0.01,
        V(x, outer_y - 0.01, z),
        V(0, 1, 0),
    )


def mount_base_shape(top_z=MOUNT_TOP_Z, *, length=MOUNT_LENGTH, recess_head=True):
    """U seat with a clamp leg, roof and unloaded positive-Y nut guard.

    Shared bridge/frame joints omit the foot counterbore so the additional
    bridge cheek can load the complete flat negative-Y face.
    """
    top_z = _positive(top_z, "Mount top")
    length = _contact_length(length)
    if not isinstance(recess_head, bool):
        raise ValueError("Recess head must be a boolean")
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
                GUARD_OUTER_Y - MOUNT_OUTER_Y,
                top_z - WEB_TOP_Z,
                (-length / 2, MOUNT_OUTER_Y, WEB_TOP_Z),
            ),
            box(
                length,
                GUARD_THICKNESS,
                top_z - MOUNT_BOTTOM_Z,
                (-length / 2, GUARD_INNER_Y, MOUNT_BOTTOM_Z),
            ),
        ]
    )
    result = result.cut(
        Part.makeCylinder(
            SLOT_HEIGHT / 2,
            GUARD_OUTER_Y - MOUNT_OUTER_Y + 2,
            V(0, MOUNT_OUTER_Y - 1, BOLT_AXIS_Z),
            V(0, 1, 0),
        )
    )
    # This is an open window: no guard material lies between nut and rail web.
    # The nut flats are restrained without clamping the clearance guard inward.
    result = result.cut(
        _nut_outer(NUT_WINDOW_AF, GUARD_OUTER_Y - WEB_THICKNESS / 2 + 0.1)
    )
    if recess_head:
        result = result.cut(head_recess_shape(MOUNT_OUTER_Y))
    result = result.removeSplitter()
    if not result.isValid() or len(result.Solids) != 1:
        raise RuntimeError("Rail mount must remain one valid solid")
    return result


def _attachment_fastener(shared_drive):
    if not isinstance(shared_drive, bool):
        raise ValueError("Shared drive attachment must be a boolean")
    if shared_drive:
        from . import servo_bridge

        return (
            servo_bridge.SHARED_SCREW_LENGTH,
            servo_bridge.CHEEK_OUTER_Y + HEAD_RECESS_DEPTH,
        )
    return SCREW_LENGTH, HEAD_BEARING_Y


def attachment_screw_shape(screw_length=SCREW_LENGTH, *, head_face_y=HEAD_BEARING_Y):
    length = _positive(screw_length, "Screw length")
    if (
        isinstance(head_face_y, bool)
        or not isinstance(head_face_y, Real)
        or not math.isfinite(head_face_y)
        or head_face_y > HEAD_BEARING_Y
    ):
        raise ValueError("Screw head must bear on or outside the mount leg")
    return union(
        [
            Part.makeCylinder(
                fasteners.RAIL_THREAD_DIAMETER / 2,
                length,
                V(0, head_face_y, BOLT_AXIS_Z),
                V(0, 1, 0),
            ),
            Part.makeCylinder(
                fasteners.RAIL_SCREW_HEAD_DIAMETER / 2,
                fasteners.RAIL_SCREW_HEAD_HEIGHT,
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


def nut_shape(
    across_flats=fasteners.RAIL_HEX_NUT_AF, thickness=fasteners.RAIL_HEX_NUT_HEIGHT
):
    return _nut_outer(across_flats, thickness).cut(
        Part.makeCylinder(
            fasteners.RAIL_THREAD_DIAMETER / 2,
            thickness + 2,
            V(0, WEB_THICKNESS / 2 - 1, BOLT_AXIS_Z),
            V(0, 1, 0),
        )
    )


def attachment_sites(*, x_offset=0, shared_drive=False):
    """Local clamp centres and orientations; opposite is a half-turn about Z."""
    _attachment_fastener(shared_drive)
    if shared_drive:
        from . import servo_bridge

        if abs(x_offset - servo_bridge.CLAMP_AXIS_X) > TOL:
            raise ValueError("Shared clamp offset must match the paired bridge")
        return (
            {"prefix": "", "x_offset": x_offset, "side": 1},
            {"prefix": "Opposite", "x_offset": -x_offset, "side": -1},
        )
    return ({"prefix": "", "x_offset": x_offset, "side": 1},)


def attachment_site_shape(shape, site):
    result = shape.copy()
    if site["side"] < 0:
        result = result.mirror(V(), V(1, 0, 0)).mirror(V(), V(0, 1, 0))
    return translated_shape(result, x=site["x_offset"])


def build_attachment_hardware(doc, parent, prefix, *, x_offset=0, shared_drive=False):
    screw_length, head_face_y = _attachment_fastener(shared_drive)
    result = []
    for site in attachment_sites(x_offset=x_offset, shared_drive=shared_drive):
        for suffix, label, shape, sku in (
            (
                "RailMountScrew",
                f"M3 x{screw_length:g} recessed side rail bolt | design head envelope",
                attachment_screw_shape(screw_length, head_face_y=head_face_y),
                f"M3X{screw_length:g}_BUTTON_HEAD",
            ),
            (
                "RailMountNut",
                "M3 rail hex nut | direct web bearing inside guard",
                nut_shape(),
                "M3_HEX_NUT",
            ),
        ):
            obj = doc.addObject("Part::Feature", prefix + site["prefix"] + suffix)
            parent.addObject(obj)
            obj.Label = "BUY | " + label
            obj.Shape = attachment_site_shape(shape, site)
            for key, value in (
                ("Role", "Purchased metric hardware"),
                ("HardwareSKU", sku),
                ("ThreadStandard", "ISO metric coarse M3 x0.5, right hand"),
                (
                    "Notes",
                    fasteners.RAIL_HEAD_ENVELOPE_NOTE
                    + " The nut bears directly on the rail web through the guard window; never substitute the guard for the compression stack. Full thread engagement, nut capture and actual fit require inspection.",
                ),
                ("ModelDetail", "Simplified thread envelope; do not print"),
                ("MaterialSelection", fasteners.RAIL_FASTENER_MATERIAL),
                ("SourceEvidence", fasteners.RAIL_FASTENER_SOURCE),
            ):
                set_property(obj, key, value)
            set_property(obj, "NominalThreadDiameter", 3.0, "App::PropertyLength")
            set_property(obj, "ThreadPitch", 0.5, "App::PropertyLength")
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
        "mount_section": "U; negative-Y clamp leg, seating roof, positive-Y clearance guard",
        "mount_outer_y_mm": MOUNT_OUTER_Y,
        "head_recess_diameter_mm": HEAD_RECESS_DIAMETER,
        "head_recess_depth_mm": HEAD_RECESS_DEPTH,
        "ordinary_head_bearing_floor_mm": MOUNT_LEG_THICKNESS - HEAD_RECESS_DEPTH,
        "guard_inner_y_mm": GUARD_INNER_Y,
        "guard_outer_y_mm": GUARD_OUTER_Y,
        "guard_clearance_to_web_mm": GUARD_GAP,
        "nut_window_across_flats_mm": NUT_WINDOW_AF,
        "nut_bearing_y_mm": WEB_THICKNESS / 2,
        "nut_bearing_scope": "Nut bears directly on the positive-Y rail web through the open hex guard window. The guard restrains nut rotation and lateral separation; it is outside the axial compression stack.",
        "bolt_length_mm": screw_length,
        "head_bearing_y_mm": head_face_y,
        "printed_grip_mm": WEB_THICKNESS / 2 - head_face_y,
        "shared_servo_bridge_clamp": shared_drive,
        "clamp_count": 2 if shared_drive else 1,
        "clamp_spacing_mm": 34.0 if shared_drive else None,
        "fastener": f"M3x{screw_length:g} recessed button-head bolt and M3 hex nut in a through guard window; unmeasured design envelopes",
        "shared_joint_service": (
            "Two opposed bolts 34 mm apart retain the servo saddle and propulsion frame on adjacent rail walls. Support both modules during release and seat both feet before alternating tightening. The 58 mm combined footprint locally restrains rail curvature; do not force a curved rail straight."
            if shared_drive
            else None
        ),
        "assembly": "Each canonical U seat lowers onto one wall; the propulsion counterpart is half-turned about Z. Both shared feet must seat simultaneously. Insert the M3 nut from positiveY through the guard window until it bears on the rail web; insert the bolt from negativeY into its head recess and tighten. The guard has 0.2mm clearance to the web and is not an axial clamp jaw. Loosen to slide only inside that wall's supported slot. Moving between segments needs hardware removal and lift-off; no full-length continuous adjustment or self-centering mechanism.",
        "physical_acceptance": "Process-matched coupon must seat flat without rocking. Finish contact faces or reprint warped parts. Slot clearance enables assembly/alignment, not acceptable looseness in use. The nut must contact the web, not bottom on guard material; check axial removal and resistance to turning in the hex window. Inspect actual M3 head/socket fit, thread engagement and under-base adhesive after installation.",
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
        "One straight5x1.5mm PA12 strip with three tape-wing pairs. Nine identical26mm-long walls at34mm pitch have local3.4mm slots for M3 bolts and eight8mm free spans. Every wall supports either a16mm carrier U foot or24mm propulsion U foot; the latter has only0.4mm total adjustment. U guards restrain lateral separation while nuts bear directly on the web. Small planar corner chamfers replace curved outlines. Qualify loaded curvature, lateral/torsional stability, friction retention, creep and adhesion; no whole-rail flexibility or strength rating.",
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
        doc, "ContinuousRailFitCoupons", "Print first | recessed M3 side-slot U fit"
    )
    samples = (
        (
            "RailFitSample",
            "PRINT FIRST | 50mm side-slot rail sample",
            rail_shape(50, (0,)),
        ),
        (
            "MountFitSample",
            "PRINT FIRST | side-slot U mount sample",
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
            "Same26mm wall/U-seat geometry as full rail. Use the actual M3x8 bolt and M3 nut; test recessed head fit, direct nut-to-web seating, nut-window fit, local sliding, side tool access and clamp retention. Keep the guard clear of the web by nominal0.2mm; it must not take the axial preload. The companion50mm base coupon has one complete support and no inter-wall gap; it does not test full rail bending, adhesion or creep.",
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
    head_face_y=HEAD_BEARING_Y,
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
    # Fill only the head recess, bore and guard window for a conservative
    # planar sweep. Keeping the U cavity open avoids a whole-box false collision.
    # These witnesses stay outside the web's two side planes.
    filled_mount = union(
        [
            clamp,
            box(
                HEAD_RECESS_DIAMETER,
                HEAD_RECESS_DEPTH,
                HEAD_RECESS_DIAMETER,
                (
                    -HEAD_RECESS_DIAMETER / 2,
                    head_face_y - HEAD_RECESS_DEPTH,
                    BOLT_AXIS_Z - HEAD_RECESS_DIAMETER / 2,
                ),
            ),
            box(
                SLOT_HEIGHT,
                -WEB_THICKNESS / 2 - head_face_y,
                SLOT_HEIGHT,
                (-SLOT_HEIGHT / 2, head_face_y, BOLT_AXIS_Z - SLOT_HEIGHT / 2),
            ),
            translated_shape(_nut_outer(NUT_WINDOW_AF, GUARD_THICKNESS), y=GUARD_GAP),
        ]
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
        fasteners.RAIL_SCREW_HEAD_DIAMETER / 2,
        0.01,
        V(0, head_face_y, BOLT_AXIS_Z),
        V(0, 1, 0),
    ).cut(
        Part.makeCylinder(
            SLOT_HEIGHT / 2, 0.02, V(0, head_face_y, BOLT_AXIS_Z), V(0, 1, 0)
        )
    )
    missing_head = abs(head_face.cut(clamp).Volume)
    # The window restrains rotation; only the rail web supports the nut axially.
    nut_face = _nut_outer(fasteners.RAIL_HEX_NUT_AF, 0.01)
    nut_face = translated_shape(nut_face, y=-0.01).cut(
        _slot(-contact_length, contact_length)
    )
    missing_nut = abs(nut_face.cut(section).Volume)
    nut_area = nut_face.Volume / 0.01
    tip = head_face_y + screw_length
    engagement = tip - (WEB_THICKNESS / 2 + fasteners.RAIL_HEX_NUT_HEIGHT)
    # The open guard window permits straight +Y loading/removal of the nut.
    nut_sweep, nut_method = translation_sweep(
        _nut_outer(fasteners.RAIL_HEX_NUT_AF, fasteners.RAIL_HEX_NUT_HEIGHT),
        (0, 10, 0),
    )
    nut_release = abs(nut_sweep.common(section).Volume) + abs(
        nut_sweep.common(clamp).Volume
    )
    guard_gap = box(
        contact_length,
        GUARD_GAP,
        WEB_TOP_Z - MOUNT_BOTTOM_Z,
        (-contact_length / 2, WEB_THICKNESS / 2, MOUNT_BOTTOM_Z),
    )
    guard_gap_overlap = abs(guard_gap.common(mount).Volume)
    nut_guard_axial_support = abs(nut_face.common(mount).Volume)
    # A turned filled hex must hit the window sidewalls; nominal acceptance
    # geometry only, not a measured lot or a qualified tightening torque.
    turned_nut = nut.copy()
    turned_nut.rotate(V(0, 0, BOLT_AXIS_Z), V(0, 1, 0), 30)
    nut_rotation_stop = abs(turned_nut.common(mount).Volume)
    return {
        "seated_intersections_mm3": overlaps,
        "continuous_vertical_removal": {"method": method, "overlap_mm3": lift_overlap},
        "continuous_nut_release": {"method": nut_method, "overlap_mm3": nut_release},
        "missing_full_top_contact_mm3": missing_top,
        "missing_flat_side_contact_mm3": missing_side,
        "missing_head_support_mm3": missing_head,
        "missing_nut_support_mm3": missing_nut,
        "nut_bearing_area_outside_slot_mm2": nut_area,
        "positive_guard_clearance_mm": GUARD_GAP,
        "guard_clearance_obstruction_mm3": guard_gap_overlap,
        "nut_axial_support_from_guard_mm3": nut_guard_axial_support,
        "nut_30deg_rotation_stop_block_mm3": nut_rotation_stop,
        "bolt_length_mm": screw_length,
        "head_bearing_y_mm": head_face_y,
        "printed_grip_mm": WEB_THICKNESS / 2 - head_face_y,
        "shared_head_support_supplied": head_support is not None,
        "bolt_tip_beyond_nut_mm": engagement,
        "full_nominal_nut_height_engaged": engagement >= -TOL,
        "scope": "Unloaded local U-seat geometry. The nut bears directly on the web and is restrained by a through hex guard window; its axial load does not pass through the clearance guard. Tighten after aligning. No qualified torque, friction, creep, curvature, physical fit or whole-module tool-access claim.",
        "passed": max(overlaps.values()) < TOL
        and lift_overlap < TOL
        and nut_release < TOL
        and max(missing_top, missing_side, missing_head, missing_nut) < TOL
        and nut_area > 0
        and guard_gap_overlap < TOL
        and nut_guard_axial_support < TOL
        and nut_rotation_stop > TOL
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
        "release": "Loosen the recessed side M3 bolt and slide within the current supported slot. To change wall segment remove bolt and nut, then lift the U seat. The nut window restrains rotation while allowing straight axial removal; no full-length slide or automatic calibration.",
    }


if __name__ == "__main__":
    print(json.dumps(validate_mechanism(), indent=2))
