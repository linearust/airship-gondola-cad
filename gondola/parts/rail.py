"""Flexible PA12 base with segmented walls and recessed M3 U mounts.

Each wall slot permits local longitudinal adjustment. A fitted U mount bears
on both sides of the wall. A blind hex pocket retains a printed nut-bearing
floor; segment gaps retain compliance outside the supported joint footprint.
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
from gondola.contracts.rail_attachments import attachment_pattern

V = App.Vector
LENGTH = RAIL_LENGTH_MM
PAD_CENTRES = (-136.0, 0.0, 136.0)
PAD_LENGTH, PAD_WIDTH, PAD_THICKNESS = 14.0, 32.0, RAIL_BASE_THICKNESS_MM
BASE_WIDTH = 6.0
WALL_LENGTH, WALL_PITCH = 26.0, 34.0
WALL_CENTRES = tuple(index * WALL_PITCH for index in range(-4, 5))
WEB_THICKNESS, WEB_TOP_Z = 2.5, 10.5
SLOT_HEIGHT, BOLT_AXIS_Z = 3.4, 7.0
SLOT_CENTRE_HALF_SPAN = 6.0
SHARED_SPINE_LENGTH = 58.0
SHARED_LOAD_ZONE_LENGTH = 12.0
SHARED_TRIM_HALF_RANGE = 6.0
SHARED_MINIMUM_WALL_SEAT = 19.0
SHARED_MINIMUM_TOTAL_SEAT = 45.0
MOUNT_LENGTH, MOUNT_LEG_THICKNESS = 16.0, 4.0
MOUNT_BOTTOM_Z, MOUNT_TOP_Z = 1.5, 12.5
MOUNT_INNER_ROOF_Z = 10.7
MOUNT_OUTER_Y = -WEB_THICKNESS / 2 - MOUNT_LEG_THICKNESS
HEAD_RECESS_DIAMETER, HEAD_RECESS_DEPTH = 6.4, 2.0
HEAD_BEARING_Y = MOUNT_OUTER_Y + HEAD_RECESS_DEPTH
NUT_FLOOR_THICKNESS = 2.0
FAR_LEG_INNER_Y = WEB_THICKNESS / 2
FAR_LEG_OUTER_Y = 6.95
FAR_LEG_THICKNESS = FAR_LEG_OUTER_Y - FAR_LEG_INNER_Y
NUT_BEARING_Y = FAR_LEG_INNER_Y + NUT_FLOOR_THICKNESS
NUT_POCKET_AF = 5.9
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
    """Full-foot end allowance before accounting for bolt clearance."""
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


def attachment_windows(
    length=LENGTH, contact_length=MOUNT_LENGTH, *, shared_drive=False
):
    """Intersect bolt travel with the explicitly selected contact policy.

    Carrier feet retain their complete footprint and 0.8 mm end reserve.
    A shared drive instead has a continuous 58 mm spine across two walls;
    its 12 mm centred clamp zones retain 1 mm to each wall end at ±6 mm.
    Separate saved-solid checks require19mm side-wall overlap per wall and45mm total.
    A paired module must also keep its full bottom datum inside the rail base.
    """
    contact_length = _contact_length(contact_length)
    attachment_pattern(shared_drive)
    if shared_drive and abs(contact_length - SHARED_SPINE_LENGTH) > TOL:
        raise ValueError("Shared support requires the complete58mm spine extent")
    clearance = (SLOT_HEIGHT - fasteners.RAIL_THREAD_DIAMETER) / 2
    inset = (
        WALL_LENGTH / 2 - SHARED_TRIM_HALF_RANGE
        if shared_drive
        else _slot_end_inset(contact_length) - clearance
    )
    inset = max(inset, WALL_LENGTH / 2 - SLOT_CENTRE_HALF_SPAN - clearance)
    return tuple(
        {
            "wall_x_range_mm": (first, last),
            "axis_travel_x_range_mm": (first + inset, last - inset),
        }
        for first, last in wall_segments(length)
        if first + inset <= last - inset + TOL
    )


def supported_slot_ranges(
    length=LENGTH, contact_length=MOUNT_LENGTH, *, shared_drive=False
):
    """Nominal centres: full carrier foot or qualified shared-spine geometry."""
    return tuple(
        row["axis_travel_x_range_mm"]
        for row in attachment_windows(length, contact_length, shared_drive=shared_drive)
    )


def spine_base_position_check(x):
    """The full-width bottom datum stops before the rail's1mm end chamfers."""
    limit = LENGTH / 2 - 1.0 - SHARED_SPINE_LENGTH / 2
    valid = not isinstance(x, bool) and isinstance(x, Real) and math.isfinite(x)
    return {
        "module_x_mm": x,
        "full_width_base_centre_limits_mm": [-limit, limit],
        "passed": bool(valid and abs(x) <= limit + TOL),
    }


def attachment_position_check(
    x, length=LENGTH, contact_length=MOUNT_LENGTH, *, shared_drive=False
):
    if isinstance(x, bool) or not isinstance(x, Real) or not math.isfinite(x):
        return {"x_mm": x, "passed": False, "error": "Position must be finite"}
    for row in attachment_windows(length, contact_length, shared_drive=shared_drive):
        first, last = row["wall_x_range_mm"]
        low, high = row["axis_travel_x_range_mm"]
        if low - TOL <= x <= high + TOL:
            zone = SHARED_LOAD_ZONE_LENGTH if shared_drive else contact_length
            margin = min(x - zone / 2 - first, last - x - zone / 2)
            return {
                "x_mm": x,
                **row,
                "contact_length_mm": contact_length,
                "support_policy": "paired_spine" if shared_drive else "full_foot",
                "centred_load_zone_length_mm": zone,
                "minimum_centred_contact_end_margin_mm": margin,
                **(
                    {"minimum_full_foot_end_margin_mm": margin}
                    if not shared_drive
                    else {}
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
    for first, last in segments:
        wall = box(
            last - first,
            WEB_THICKNESS,
            WEB_TOP_Z - PAD_THICKNESS,
            (first, -WEB_THICKNESS / 2, PAD_THICKNESS),
        )
        centre = (first + last) / 2
        pieces.append(
            wall.cut(
                _slot(centre - SLOT_CENTRE_HALF_SPAN, centre + SLOT_CENTRE_HALF_SPAN)
            )
        )
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


def nut_pocket_shape(inner_y, outer_y, *, x=0, z=BOLT_AXIS_Z):
    """Outside-entry hex cutter retaining a nominal 2 mm load-bearing floor."""
    if not all(
        isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)
        for value in (inner_y, outer_y, x, z)
    ):
        raise ValueError("Nut pocket positions must be finite numbers")
    bearing_y = inner_y + NUT_FLOOR_THICKNESS
    if outer_y - bearing_y < fasteners.RAIL_HEX_NUT_HEIGHT - TOL:
        raise ValueError("Nut pocket must contain the complete nominal nut height")
    return translated_shape(
        _nut_outer(NUT_POCKET_AF, outer_y - bearing_y + 0.01, bearing_y=bearing_y),
        x=x,
        z=z - BOLT_AXIS_Z,
    )


def mount_base_shape(top_z=MOUNT_TOP_Z, *, length=MOUNT_LENGTH, recess_head=True):
    """Fitted carrier U seat with two loaded legs and a blind nut pocket.

    The paired propulsion frame uses its own continuous U spine; its nut
    pocket belongs to the outer servo saddle, beyond both frame side faces.
    """
    top_z = _positive(top_z, "Mount top")
    length = _contact_length(length)
    if not isinstance(recess_head, bool):
        raise ValueError("Recess head must be a boolean")
    if top_z < MOUNT_INNER_ROOF_Z + PAD_THICKNESS - TOL:
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
                FAR_LEG_OUTER_Y - MOUNT_OUTER_Y,
                top_z - MOUNT_INNER_ROOF_Z,
                (-length / 2, MOUNT_OUTER_Y, MOUNT_INNER_ROOF_Z),
            ),
            box(
                length,
                FAR_LEG_THICKNESS,
                top_z - MOUNT_BOTTOM_Z,
                (-length / 2, FAR_LEG_INNER_Y, MOUNT_BOTTOM_Z),
            ),
        ]
    )
    result = result.cut(
        Part.makeCylinder(
            SLOT_HEIGHT / 2,
            FAR_LEG_OUTER_Y - MOUNT_OUTER_Y + 2,
            V(0, MOUNT_OUTER_Y - 1, BOLT_AXIS_Z),
            V(0, 1, 0),
        )
    )
    result = result.cut(nut_pocket_shape(FAR_LEG_INNER_Y, FAR_LEG_OUTER_Y))
    if recess_head:
        result = result.cut(head_recess_shape(MOUNT_OUTER_Y))
    result = result.removeSplitter()
    if not result.isValid() or len(result.Solids) != 1:
        raise RuntimeError("Rail mount must remain one valid solid")
    return result


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


def _nut_outer(across_flats, thickness, *, bearing_y=NUT_BEARING_Y):
    radius = across_flats / math.sqrt(3)
    return polygon_extrusion(
        [
            (
                radius * math.cos(math.radians(a)),
                bearing_y,
                BOLT_AXIS_Z + radius * math.sin(math.radians(a)),
            )
            for a in range(0, 360, 60)
        ],
        (0, thickness, 0),
    )


def nut_shape(
    across_flats=fasteners.RAIL_HEX_NUT_AF,
    thickness=fasteners.RAIL_HEX_NUT_HEIGHT,
    *,
    bearing_y=NUT_BEARING_Y,
):
    return _nut_outer(across_flats, thickness, bearing_y=bearing_y).cut(
        Part.makeCylinder(
            fasteners.RAIL_THREAD_DIAMETER / 2,
            thickness + 2,
            V(0, bearing_y - 1, BOLT_AXIS_Z),
            V(0, 1, 0),
        )
    )


def attachment_nut_shape(*, shared_drive=False):
    return nut_shape(bearing_y=attachment_pattern(shared_drive).nut_bearing_y_mm)


def attachment_sites(*, x_offset=0, shared_drive=False):
    """Local clamp centres and orientations; opposite is a half-turn about Z."""
    return attachment_pattern(shared_drive).sites(x_offset)


def attachment_site_shape(shape, site):
    result = shape.copy()
    if site["side"] < 0:
        result = result.mirror(V(), V(1, 0, 0)).mirror(V(), V(0, 1, 0))
    return translated_shape(result, x=site["x_offset"])


def build_attachment_hardware(doc, parent, prefix, *, x_offset=0, shared_drive=False):
    pattern = attachment_pattern(shared_drive)
    sites = pattern.sites(x_offset)
    screw_length = pattern.screw_length_mm
    head_face_y = pattern.head_bearing_y(MOUNT_OUTER_Y, HEAD_RECESS_DEPTH)
    hardware = (
        (
            "RailMountScrew",
            f"M3 x{screw_length:g} recessed side rail bolt | design head envelope",
            attachment_screw_shape(screw_length, head_face_y=head_face_y),
            f"M3X{screw_length:g}_BUTTON_HEAD",
        ),
        (
            "RailMountNut",
            "M3 rail hex nut | blind pocket on a printed bearing floor",
            nut_shape(bearing_y=pattern.nut_bearing_y_mm),
            "M3_HEX_NUT",
        ),
    )
    result = []
    for site in sites:
        for suffix, label, shape, sku in hardware:
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
                    + " The nut bears on a nominal2mm printed pocket floor. Fit both opposed contact faces before tightening; reject loose or warped seats instead of pulling a rigid clearance gap closed. Full thread engagement, floor thickness after finishing and actual fit require inspection.",
                ),
                ("ModelDetail", "Simplified thread envelope; do not print"),
                ("MaterialSelection", fasteners.RAIL_FASTENER_MATERIAL),
                ("SourceEvidence", fasteners.RAIL_FASTENER_SOURCE),
            ):
                set_property(obj, key, value)
            set_property(
                obj,
                "NominalThreadDiameter",
                fasteners.RAIL_THREAD_DIAMETER,
                "App::PropertyLength",
            )
            set_property(
                obj, "ThreadPitch", fasteners.RAIL_THREAD_PITCH, "App::PropertyLength"
            )
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
        "attachment": "Conform before bonding. Thin double-sided tape under the continuous rail base can distribute local loads and cover wing undersides. Six optional over-wing strips reinforce peel retention. Keep side bolts and open flex gaps accessible; adhesive changes compliance and must not be treated as an unloaded free-beam test.",
        "reference_scope": "Saved tape solids show only optional12mm over-wing strips. Under-base adhesive thickness, mass and envelope deformation are not modeled. Z0 is the rail underside, not a certified balloon surface.",
        "qualification": "Three isolated wing pairs are not load-qualified. Check actual tape/envelope compatibility, peel, creep and loaded curvature; no adhesion strength, minimum bend radius or fatigue life is claimed.",
    }


def attachment_contract(
    contact_length=MOUNT_LENGTH, *, length=LENGTH, shared_drive=False
):
    length = _positive(length, "Rail length")
    _contact_length(contact_length)
    spans = flex_spans(length)
    pattern = attachment_pattern(shared_drive)
    screw_length = pattern.screw_length_mm
    head_face_y = pattern.head_bearing_y(MOUNT_OUTER_Y, HEAD_RECESS_DEPTH)
    nut_bearing_y = pattern.nut_bearing_y_mm
    pocket_inner_y = pattern.frame_half_width_mm if shared_drive else FAR_LEG_INNER_Y
    pocket_outer_y = (
        pattern.frame_half_width_mm + pattern.extra_cheek_mm
        if shared_drive
        else FAR_LEG_OUTER_Y
    )
    return {
        "rail_length_mm": length,
        "wall_count": len(wall_segments(length)),
        "wall_segments_x_mm": wall_segments(length),
        "supported_bolt_axis_ranges_x_mm": supported_slot_ranges(
            length, contact_length=contact_length, shared_drive=shared_drive
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
        "mount_bottom_datum_z_mm": MOUNT_BOTTOM_Z,
        "mount_inner_roof_z_mm": MOUNT_INNER_ROOF_Z,
        "nominal_inner_roof_clearance_mm": MOUNT_INNER_ROOF_Z - WEB_TOP_Z,
        "minimum_base_mm": PAD_THICKNESS,
        "slot_height_mm": SLOT_HEIGHT,
        "slot_cap_centre_span_mm": 2 * SLOT_CENTRE_HALF_SPAN,
        "slot_overall_length_mm": 2 * SLOT_CENTRE_HALF_SPAN + SLOT_HEIGHT,
        "wall_end_ligament_mm": WALL_LENGTH / 2
        - SLOT_CENTRE_HALF_SPAN
        - SLOT_HEIGHT / 2,
        "bolt_axis_z_mm": BOLT_AXIS_Z,
        "mount_contact_length_mm": contact_length,
        "contact_length_scope": (
            "Complete58mm spine extent: both lower lands contact the continuous base; side walls bridge the rail-wall gap."
            if shared_drive
            else "Complete carrier foot length; the whole footprint retains at least0.8mm to wall ends."
        ),
        "support_policy": "paired_spine" if shared_drive else "full_foot",
        "centred_load_zone_length_mm": SHARED_LOAD_ZONE_LENGTH
        if shared_drive
        else contact_length,
        "shared_minimum_wall_seat_length_mm": SHARED_MINIMUM_WALL_SEAT
        if shared_drive
        else None,
        "shared_minimum_total_seat_length_mm": SHARED_MINIMUM_TOTAL_SEAT
        if shared_drive
        else None,
        "shared_full_width_base_centre_limits_mm": spine_base_position_check(0)[
            "full_width_base_centre_limits_mm"
        ]
        if shared_drive
        else None,
        "shared_usable_trim_half_range_mm": SHARED_TRIM_HALF_RANGE
        if shared_drive
        else None,
        "mount_section": "Fitted U; two opposed rail-contact legs, bilateral bottom datum, relieved inner roof and blind nut-bearing pocket",
        "mount_outer_y_mm": -pattern.frame_half_width_mm
        if shared_drive
        else MOUNT_OUTER_Y,
        "head_recess_diameter_mm": HEAD_RECESS_DIAMETER,
        "head_recess_depth_mm": HEAD_RECESS_DEPTH,
        "ordinary_head_bearing_floor_mm": MOUNT_LEG_THICKNESS - HEAD_RECESS_DEPTH,
        "fitted_channel_width_mm": WEB_THICKNESS,
        "nominal_side_clearance_mm": 0.0,
        "far_leg_inner_y_mm": FAR_LEG_INNER_Y,
        "far_leg_outer_y_mm": pattern.frame_half_width_mm
        if shared_drive
        else FAR_LEG_OUTER_Y,
        "nut_pocket_across_flats_mm": NUT_POCKET_AF,
        "nut_pocket_inner_y_mm": pocket_inner_y,
        "nut_pocket_outer_y_mm": pocket_outer_y,
        "nut_floor_nominal_mm": NUT_FLOOR_THICKNESS,
        "minimum_finished_nut_floor_mm": 1.5,
        "nut_bearing_y_mm": nut_bearing_y,
        "nut_bearing_scope": (
            "Nut bears on the far servo-saddle cheek floor. The nominal compression path crosses both saddle cheeks, both fitted frame legs and the rail web."
            if shared_drive
            else "Nut bears on the far U-leg floor. Both fitted legs contact the rail; no clearance guard is bypassed by direct nut-to-rail bearing."
        ),
        "bolt_length_mm": screw_length,
        "head_bearing_y_mm": head_face_y,
        "printed_grip_mm": nut_bearing_y - head_face_y,
        "bolt_tip_beyond_nut_mm": head_face_y
        + screw_length
        - nut_bearing_y
        - fasteners.RAIL_HEX_NUT_HEIGHT,
        "shared_servo_bridge_clamp": shared_drive,
        "clamp_count": pattern.count,
        "clamp_spacing_mm": pattern.spacing_mm,
        "fastener": f"M3x{screw_length:g} recessed button-head bolt and M3 hex nut in a blind load-bearing pocket; unmeasured design envelopes",
        "shared_joint_service": (
            "Two opposed bolts34mm apart retain the servo saddle and continuous58mm frame spine on adjacent walls. Default paired trim is±6mm; the outermost wall pairs are additionally limited by the full-width base ends; each bolt retains a12mm centred load zone with at least1mm to the wall ends. At the travel extremes the spine overlaps19mm and26mm of wall (45mm total); at neutral it overlaps25mm each. Both lower legs seat on the rail base atZ1.5; the inner roof retains0.2mm nominal clearance above the wall. These are contact-geometry checks, not equal-stiffness or loaded-retention claims. Support both modules during release and seat both walls before alternating tightening. The spine locally restrains rail curvature; do not force a curved rail straight."
            if shared_drive
            else None
        ),
        "assembly": "Fit both bottom lands and opposed U side faces before installing hardware; retain the0.2mm inner-roof relief. Insert the M3 nut from positiveY into the blind pocket until it contacts the printed floor; insert the bolt from negativeY. The opposite shared station is half-turned about Z. Both shared rail lands and both servo/frame side faces must seat before alternating tightening. Loosen to slide only inside supported wall intervals. Moving between segments needs hardware removal and lift-off; no full-length continuous adjustment or self-centering mechanism.",
        "physical_acceptance": "Use a process-matched coupon and actual hardware. The nominal channel is line-to-line with the rail; this is not an as-printed slip-fit guarantee. Finish only high spots while retaining at least1.5mm nut-floor and head-floor thickness. Reject or reprint loose or warped seats; do not force a rigid gap closed with the bolt. Verify bilateral bottom and side contact without rocking, a clear relieved roof, nut seating and anti-rotation, actual socket access, full thread engagement and loaded retention. Printed creep, clamp force and fit remain unqualified.",
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
        "One straight6x1.5mm PA12 strip with three tape-wing pairs. Nine identical26mm walls at34mm pitch retain eight8mm flex gaps. Each3.4x15.4mm slot leaves5.3mm end ligaments. Ordinary16mm feet retain±4.2mm full-foot travel. The paired continuous58mm propulsion spine permits±6mm default trim (endmost pairs are limited by full bottom-land support) with independently checked12mm clamp zones and at least19mm side-wall overlap per wall/45mm total. Fitted opposed legs and blind nut-pocket floors carry the nominal clamp stack. Qualify actual fit, loaded curvature, lateral/torsional stability, friction retention, creep and adhesion; no stiffness, holding-force or strength rating.",
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
            "Same26mm wall/fitted U-seat geometry as full rail. Use the actual M3x10 bolt and M3 nut; test recessed head fit, blind pocket seating, both rail-contact faces, local sliding and side tool access. Finish only high spots while retaining at least1.5mm nut/head floors. Reject or reprint a loose or warped seat; do not pull a rigid clearance gap closed with the bolt. The companion50mm rail sample has one complete support and no inter-wall gap; it does not qualify the paired servo/frame interface, loaded clamping, full rail bending, adhesion or creep.",
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
    nut_bearing_y=NUT_BEARING_Y,
    nut_outer_y=FAR_LEG_OUTER_Y,
    frame_contact_y=None,
    shared_drive=False,
):
    """Nominal fitted load stack and local release, not physical clamp strength.

    Shared checks supply both saddle cheeks in head_support, nut seat8/outer11,
    and frame_contact_y6. Independent saved validators also check actual parts.
    """
    from gondola.validation.geometry import translation_sweep

    contact_length = _contact_length(contact_length)
    attachment_pattern(shared_drive)
    if shared_drive and (
        abs(contact_length - SHARED_SPINE_LENGTH) > TOL or mount is None
    ):
        raise ValueError("Shared attachment requires the actual58mm frame spine")
    zone_length = SHARED_LOAD_ZONE_LENGTH if shared_drive else contact_length
    if (
        not all(
            isinstance(value, Real)
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in (nut_bearing_y, nut_outer_y)
        )
        or nut_outer_y < nut_bearing_y + fasteners.RAIL_HEX_NUT_HEIGHT - TOL
    ):
        raise ValueError("Nut bearing/pocket positions must contain the nominal nut")
    if frame_contact_y is not None:
        frame_contact_y = _positive(frame_contact_y, "Frame contact half-width")
    section = rail_shape(50, (0,)) if rail_section is None else rail_section
    mount = mount_base_shape(length=contact_length) if mount is None else mount
    clamp = mount if head_support is None else union([mount, head_support])
    screw = attachment_screw_shape(screw_length, head_face_y=head_face_y)
    nut = nut_shape(bearing_y=nut_bearing_y)
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
    # Fill only recesses and bores, keeping the fitted rail channel open.
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
            box(
                SLOT_HEIGHT,
                nut_outer_y - WEB_THICKNESS / 2,
                SLOT_HEIGHT,
                (-SLOT_HEIGHT / 2, WEB_THICKNESS / 2, BOLT_AXIS_Z - SLOT_HEIGHT / 2),
            ),
            _nut_outer(
                NUT_POCKET_AF,
                nut_outer_y - nut_bearing_y,
                bearing_y=nut_bearing_y,
            ),
        ]
    ).removeSplitter()
    lift, method = translation_sweep(filled_mount, (0, 0, 25))
    lift_overlap = abs(lift.common(section).Volume)
    # Bilateral bottom lands are the vertical datum. The inner roof deliberately
    # clears the rail top; forcing three planes into contact overconstrains fit.
    bottom_contacts = []
    for side_sign in (-1, 1):
        y = -BASE_WIDTH / 2 if side_sign < 0 else WEB_THICKNESS / 2
        width = (BASE_WIDTH - WEB_THICKNESS) / 2
        below = box(
            zone_length, width, 0.01, (-zone_length / 2, y, PAD_THICKNESS - 0.01)
        )
        above = translated_shape(below, z=0.01)
        missing = abs(below.cut(section).Volume) + abs(above.cut(mount).Volume)
        bottom_contacts.append(
            {
                "side": side_sign,
                "minimum_area_mm2": zone_length * width,
                "missing_contact_mm3": missing,
                "passed": missing < TOL,
            }
        )
    roof_relief = box(
        zone_length,
        WEB_THICKNESS,
        MOUNT_INNER_ROOF_Z - WEB_TOP_Z,
        (-zone_length / 2, -WEB_THICKNESS / 2, WEB_TOP_Z),
    )
    blocked_roof_relief = abs(roof_relief.common(mount).Volume)
    # Both side faces, above and below the longitudinal rail slot, must contact.
    side = box(
        zone_length,
        0.01,
        WEB_TOP_Z - MOUNT_BOTTOM_Z,
        (-zone_length / 2, -WEB_THICKNESS / 2 - 0.01, MOUNT_BOTTOM_Z),
    ).cut(_slot(-zone_length, zone_length))
    missing_side = abs(side.cut(mount).Volume) + abs(
        translated_shape(side, y=0.01).cut(section).Volume
    )
    opposite_side = translated_shape(side, y=WEB_THICKNESS + 0.01)
    missing_opposite = abs(opposite_side.cut(mount).Volume) + abs(
        translated_shape(opposite_side, y=-0.01).cut(section).Volume
    )

    def annulus(y, depth):
        return Part.makeCylinder(
            fasteners.RAIL_SCREW_HEAD_DIAMETER / 2,
            depth,
            V(0, y, BOLT_AXIS_Z),
            V(0, 1, 0),
        ).cut(
            Part.makeCylinder(
                SLOT_HEIGHT / 2, depth + 0.02, V(0, y - 0.01, BOLT_AXIS_Z), V(0, 1, 0)
            )
        )

    missing_head = abs(annulus(head_face_y, 0.01).cut(clamp).Volume)
    nut_floor = _nut_outer(
        fasteners.RAIL_HEX_NUT_AF,
        NUT_FLOOR_THICKNESS,
        bearing_y=nut_bearing_y - NUT_FLOOR_THICKNESS,
    ).cut(
        Part.makeCylinder(
            SLOT_HEIGHT / 2,
            NUT_FLOOR_THICKNESS + 0.02,
            V(0, nut_bearing_y - NUT_FLOOR_THICKNESS - 0.01, BOLT_AXIS_Z),
            V(0, 1, 0),
        )
    )
    missing_floor = abs(nut_floor.cut(clamp).Volume)
    nut_face = _nut_outer(
        fasteners.RAIL_HEX_NUT_AF, 0.01, bearing_y=nut_bearing_y - 0.01
    ).cut(
        Part.makeCylinder(
            SLOT_HEIGHT / 2, 0.03, V(0, nut_bearing_y - 0.02, BOLT_AXIS_Z), V(0, 1, 0)
        )
    )
    missing_nut = abs(nut_face.cut(clamp).Volume)
    nut_area = nut_face.Volume / 0.01
    frame_faces = []
    if frame_contact_y is not None:
        for side_sign in (-1, 1):
            face_y = side_sign * frame_contact_y
            inside = annulus(face_y if side_sign < 0 else face_y - 0.01, 0.01)
            outside = translated_shape(inside, y=side_sign * 0.01)
            missing_frame = abs(inside.cut(mount).Volume)
            missing_saddle = (
                outside.Volume
                if head_support is None
                else abs(outside.cut(head_support).Volume)
            )
            frame_faces.append(
                {
                    "side": side_sign,
                    "face_y_mm": face_y,
                    "missing_frame_support_mm3": missing_frame,
                    "missing_saddle_support_mm3": missing_saddle,
                    "passed": max(missing_frame, missing_saddle) < TOL,
                }
            )
    tip = head_face_y + screw_length
    engagement = tip - (nut_bearing_y + fasteners.RAIL_HEX_NUT_HEIGHT)
    nut_sweep, nut_method = translation_sweep(
        _nut_outer(
            fasteners.RAIL_HEX_NUT_AF,
            fasteners.RAIL_HEX_NUT_HEIGHT,
            bearing_y=nut_bearing_y,
        ),
        (0, 10, 0),
    )
    nut_release = abs(nut_sweep.common(section).Volume) + abs(
        nut_sweep.common(clamp).Volume
    )
    turned_nut = nut.copy()
    turned_nut.rotate(V(0, 0, BOLT_AXIS_Z), V(0, 1, 0), 30)
    nut_rotation_stop = abs(turned_nut.common(clamp).Volume)
    return {
        "support_policy": "paired_spine_clamp_zone" if shared_drive else "full_foot",
        "checked_centred_contact_length_mm": zone_length,
        "shared_support_scope": (
            "This local check covers only the12mm centred clamp zone. The saved paired-spine check must additionally verify complete bottom lands and both side-wall overlaps of minimum19/45mm."
            if shared_drive
            else None
        ),
        "seated_intersections_mm3": overlaps,
        "continuous_vertical_removal": {"method": method, "overlap_mm3": lift_overlap},
        "continuous_nut_release": {"method": nut_method, "overlap_mm3": nut_release},
        "bottom_datum_contacts": bottom_contacts,
        "inner_roof_clearance_mm": MOUNT_INNER_ROOF_Z - WEB_TOP_Z,
        "blocked_inner_roof_relief_mm3": blocked_roof_relief,
        "missing_flat_side_contact_mm3": missing_side,
        "missing_opposite_side_contact_mm3": missing_opposite,
        "missing_head_support_mm3": missing_head,
        "missing_nut_support_mm3": missing_nut,
        "missing_printed_nut_floor_mm3": missing_floor,
        "nut_bearing_area_outside_bore_mm2": nut_area,
        "nut_floor_nominal_mm": NUT_FLOOR_THICKNESS,
        "nut_bearing_y_mm": nut_bearing_y,
        "nut_pocket_outer_y_mm": nut_outer_y,
        "nominal_side_clearance_mm": 0.0,
        "frame_saddle_contact_faces": frame_faces,
        "nut_30deg_rotation_stop_block_mm3": nut_rotation_stop,
        "bolt_length_mm": screw_length,
        "head_bearing_y_mm": head_face_y,
        "printed_grip_mm": nut_bearing_y - head_face_y,
        "shared_head_support_supplied": head_support is not None,
        "bolt_tip_beyond_nut_mm": engagement,
        "full_nominal_nut_height_engaged": engagement >= -TOL,
        "minimum_thread_projection_mm": fasteners.RAIL_THREAD_PITCH,
        "thread_projection_margin_ok": engagement >= fasteners.RAIL_THREAD_PITCH - TOL,
        "scope": "Nominal fitted U geometry with both rail-contact legs and a printed nut-bearing floor in the compression path. Shared saddle checks include both frame/saddle contact faces at the bolt load annulus. This is a line-to-line design, not an as-printed fit guarantee; qualify by coupon and finish high spots, rejecting loose or warped seats. No qualified torque, friction, creep, curvature, physical fit or whole-module tool-access claim.",
        "passed": max(overlaps.values()) < TOL
        and lift_overlap < TOL
        and nut_release < TOL
        and max(
            blocked_roof_relief,
            missing_side,
            missing_opposite,
            missing_head,
            missing_nut,
            missing_floor,
        )
        < TOL
        and all(row["passed"] for row in bottom_contacts)
        and nut_area > 0
        and all(row["passed"] for row in frame_faces)
        and nut_rotation_stop > TOL
        and engagement >= fasteners.RAIL_THREAD_PITCH - TOL,
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
        "release": "Loosen the recessed side M3 bolt and slide within the current supported slot. To change wall segment remove bolt and nut, then lift the U seat. The blind nut pocket restrains rotation while allowing straight axial removal; both fitted contact faces must seat without forcing a rigid clearance gap closed. No full-length slide or automatic calibration.",
    }


if __name__ == "__main__":
    print(json.dumps(validate_mechanism(), indent=2))
