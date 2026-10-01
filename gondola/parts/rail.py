"""Flexible PA12 base with segmented walls and recessed M3 U mounts.

Each wall slot permits local longitudinal adjustment. A fitted U mount bears
on both sides of the wall. An open-bottom hex recess retains a printed nut-bearing
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
from gondola.contracts.rail_attachments import (
    CARRIER_ATTACHMENT,
    PROPULSION_ATTACHMENT,
    attachment_pattern,
)

V = App.Vector
LENGTH = RAIL_LENGTH_MM
PAD_CENTRES = (-140.0, 0.0, 140.0)
PAD_LENGTH, PAD_WIDTH, PAD_THICKNESS = 14.0, 32.0, RAIL_BASE_THICKNESS_MM
BASE_WIDTH = 6.0
BASE_END_CHAMFER_MM = 1.0
WALL_LENGTH, WALL_PITCH = 20.0, 28.0
WALL_CENTRES = tuple(index * WALL_PITCH for index in range(-5, 6))
WEB_THICKNESS, WEB_TOP_Z = 2.5, 9.5
SLOT_HEIGHT, BOLT_AXIS_Z = 3.4, 6.0
SLOT_CENTRE_HALF_SPAN = 3.0
SHARED_SPINE_LENGTH = PROPULSION_ATTACHMENT.contact_length_mm
SHARED_LOAD_ZONE_LENGTH = 10.0
SHARED_BOLT_HALF_RANGE = 3.0
# The 30 mm bolt pair sits 1 mm outward of the 28 mm wall-centre pair.
# Individual bolt travel and complete module travel are different quantities.
SHARED_TRIM_HALF_RANGE = 2.0
SHARED_MINIMUM_WALL_SEAT = 14.0
SHARED_MINIMUM_TOTAL_SEAT = 32.0
MOUNT_LENGTH, MOUNT_LEG_THICKNESS = CARRIER_ATTACHMENT.contact_length_mm, 4.0
MOUNT_BOTTOM_Z, MOUNT_TOP_Z = 1.5, CARRIER_ATTACHMENT.seat_z_mm
MOUNT_INNER_ROOF_Z = 9.7
MOUNT_OUTER_Y = -WEB_THICKNESS / 2 - MOUNT_LEG_THICKNESS
HEAD_RECESS_DIAMETER, HEAD_RECESS_DEPTH = 6.4, 2.0
HEAD_BEARING_Y = MOUNT_OUTER_Y + HEAD_RECESS_DEPTH
NUT_FLOOR_THICKNESS = 2.0
FAR_LEG_INNER_Y = WEB_THICKNESS / 2
FAR_LEG_OUTER_Y = -MOUNT_OUTER_Y
FAR_LEG_THICKNESS = FAR_LEG_OUTER_Y - FAR_LEG_INNER_Y
NUT_BEARING_Y = FAR_LEG_INNER_Y + NUT_FLOOR_THICKNESS
NUT_POCKET_AF = 5.9
MINIMUM_NUT_CAPTURE_DEPTH = 1.5
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
    return plate_shape(0, length, BASE_WIDTH, chamfer=BASE_END_CHAMFER_MM)


def _full_width_base_centre_limit(length, contact_length):
    """Stop the complete bottom contact before the base's end corner cuts."""
    return length / 2 - BASE_END_CHAMFER_MM - contact_length / 2


def attachment_windows(
    length=LENGTH, contact_length=MOUNT_LENGTH, *, shared_drive=False
):
    """Intersect bolt travel with the explicitly selected contact policy.

    Carrier feet retain their complete footprint and 0.8 mm end reserve.
    A shared drive has a continuous 40 mm spine across two walls. Each bolt
    may travel ±3 mm while its 10 mm load zone retains 2 mm to the wall ends.
    The 30 mm bolt pair on 28 mm wall pitch has only ±2 mm module travel.
    Separate saved-solid checks require14mm side-wall overlap per wall and32mm total.
    A paired module must also keep its full bottom datum inside the rail base.
    """
    contact_length = _contact_length(contact_length)
    attachment_pattern(shared_drive)
    if shared_drive and abs(contact_length - SHARED_SPINE_LENGTH) > TOL:
        raise ValueError("Shared support requires the complete40mm spine extent")
    clearance = (SLOT_HEIGHT - fasteners.RAIL_THREAD_DIAMETER) / 2
    inset = (
        WALL_LENGTH / 2 - SHARED_BOLT_HALF_RANGE
        if shared_drive
        else _slot_end_inset(contact_length) - clearance
    )
    inset = max(inset, WALL_LENGTH / 2 - SLOT_CENTRE_HALF_SPAN - clearance)
    # The end chamfer removes the outer edges of the bilateral bottom lands.
    # A complete ordinary foot must stop before it; paired spines are clipped
    # by their module-centre bound after intersecting both individual windows.
    base_limit = _full_width_base_centre_limit(length, contact_length)
    rows = []
    for first, last in wall_segments(length):
        low, high = first + inset, last - inset
        if not shared_drive:
            low, high = max(low, -base_limit), min(high, base_limit)
        if low > high + TOL:
            continue
        rows.append(
            {
                "wall_x_range_mm": (first, last),
                "axis_travel_x_range_mm": (low, high),
            }
        )
    return tuple(rows)


def supported_slot_ranges(
    length=LENGTH, contact_length=MOUNT_LENGTH, *, shared_drive=False
):
    """Individual bolt windows with full-foot or paired-spine contact bounds."""
    return tuple(
        row["axis_travel_x_range_mm"]
        for row in attachment_windows(length, contact_length, shared_drive=shared_drive)
    )


def shared_module_ranges(length=LENGTH):
    """Module-centre travel from both bolt windows and complete bottom lands."""
    windows = supported_slot_ranges(length, SHARED_SPINE_LENGTH, shared_drive=True)
    half_spacing = attachment_pattern(True).half_spacing_mm
    base_limit = _full_width_base_centre_limit(length, SHARED_SPINE_LENGTH)
    ranges = []
    for first, second in zip(windows, windows[1:]):
        low = max(first[0] + half_spacing, second[0] - half_spacing, -base_limit)
        high = min(first[1] + half_spacing, second[1] - half_spacing, base_limit)
        if low <= high + TOL:
            ranges.append((low, high))
    return tuple(ranges)


def spine_base_position_check(x):
    """The full-width bottom datum stops before the rail's1mm end chamfers."""
    limit = _full_width_base_centre_limit(LENGTH, SHARED_SPINE_LENGTH)
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


def cut_shared_bolt_passage(shape):
    """Cut the common frame/saddle clamp axes without depending on either part."""
    pattern = PROPULSION_ATTACHMENT
    outer_y = -pattern.frame_half_width_mm - pattern.extra_cheek_mm
    for sign in (-1, 1):
        shape = shape.cut(
            Part.makeCylinder(
                SLOT_HEIGHT / 2,
                2 * -outer_y + 2,
                V(sign * pattern.half_spacing_mm, sign * (outer_y - 1), BOLT_AXIS_Z),
                V(0, sign, 0),
            )
        )
    return shape.removeSplitter()


def head_recess_shape(outer_y, *, x=0, z=BOLT_AXIS_Z):
    """Head recess open downwards only; its axial bearing floor remains intact."""
    round_top = Part.makeCylinder(
        HEAD_RECESS_DIAMETER / 2,
        HEAD_RECESS_DEPTH + 0.01,
        V(x, outer_y - 0.01, z),
        V(0, 1, 0),
    )
    opening = box(
        HEAD_RECESS_DIAMETER,
        HEAD_RECESS_DEPTH + 0.01,
        z + 1,
        (x - HEAD_RECESS_DIAMETER / 2, outer_y - 0.01, -1),
    )
    return union([round_top, opening]).removeSplitter()


def nut_pocket_shape(inner_y, outer_y, *, x=0, z=BOLT_AXIS_Z):
    """Open-bottom hex recess with vertical flats and a 2 mm bearing floor."""
    if not all(
        isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)
        for value in (inner_y, outer_y, x, z)
    ):
        raise ValueError("Nut pocket positions must be finite numbers")
    bearing_y = inner_y + NUT_FLOOR_THICKNESS
    if outer_y - bearing_y < MINIMUM_NUT_CAPTURE_DEPTH - TOL:
        raise ValueError("Nut pocket must retain at least 1.5 mm nominal recess depth")
    pocket = translated_shape(
        _nut_outer(NUT_POCKET_AF, outer_y - bearing_y + 0.01, bearing_y=bearing_y),
        x=x,
        z=z - BOLT_AXIS_Z,
    )
    opening = box(
        NUT_POCKET_AF,
        outer_y - bearing_y + 0.01,
        z + 1,
        (x - NUT_POCKET_AF / 2, bearing_y, -1),
    )
    return union([pocket, opening]).removeSplitter()


def mount_base_shape(top_z=MOUNT_TOP_Z, *, length=MOUNT_LENGTH, recess_head=True):
    """Fitted carrier U seat with two loaded legs and an open-bottom nut recess.

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
            for a in range(30, 390, 60)
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
            "M3 rail hex nut | open-bottom recess on a printed bearing floor",
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
        "supported_module_centre_ranges_x_mm": shared_module_ranges(length)
        if shared_drive
        else supported_slot_ranges(length, contact_length),
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
            "Complete40mm spine extent: both lower lands contact the continuous base; side walls bridge the rail-wall gap."
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
        "shared_individual_bolt_half_range_mm": SHARED_BOLT_HALF_RANGE
        if shared_drive
        else None,
        "shared_usable_trim_half_range_mm": SHARED_TRIM_HALF_RANGE
        if shared_drive
        else None,
        "mount_section": "Fitted U; two opposed rail-contact legs, bilateral bottom datum, relieved inner roof and open-bottom nut-bearing pocket",
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
        "nut_capture_depth_mm": pocket_outer_y - nut_bearing_y,
        "nut_captive_without_screw": False,
        "recess_access": "Only the outer head/nut recesses open toward local -Z; the round through-bores and axial bearing floors remain closed. Vertical hex flats stop nut rotation. Hold a loose nut while starting the screw; the recess is not a captive-nut mechanism.",
        "carrier_side_legs_equal_thickness_mm": None
        if shared_drive
        else MOUNT_LEG_THICKNESS,
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
        "fastener": f"M3x{screw_length:g} recessed button-head bolt and M3 hex nut in an open-bottom load-bearing recess; unmeasured design envelopes",
        "shared_joint_service": (
            "Two opposed bolts30mm apart retain the servo saddle and continuous40mm frame spine on adjacent20mm walls at28mm pitch. Individual bolt windows are±3mm; their intersection gives±2mm module trim, including the endmost wall pairs; each bolt retains a10mm centred load zone with at least2mm to the wall ends. At travel extremes the spine overlaps14mm and18mm of wall (32mm total); at neutral it overlaps16mm each. The10mm zones retain2mm of longitudinal stock beyond the diameter6mm fastener-bearing face. The shorter footprint reduces contact area; equal stiffness or retention is not established. Both lower legs seat on the rail base atZ1.5; the inner roof retains0.2mm nominal clearance above the wall. These are contact-geometry checks, not equal-stiffness or loaded-retention claims. Support both modules during release and seat both walls before alternating tightening. The spine locally restrains rail curvature; do not force a curved rail straight."
            if shared_drive
            else None
        ),
        "assembly": (
            "Shared saddle cheeks are both 5 mm; the nut sits in a 3 mm-deep pocket. "
            if shared_drive
            else "Carrier legs are both 4 mm; the nut sits 2 mm into its pocket and may protrude. "
        )
        + "Fit both bottom lands and opposed U side faces before installing hardware; retain the0.2mm inner-roof relief. Insert the M3 nut from positiveY into the open-bottom recess until it contacts the printed floor; insert the bolt from negativeY. The opposite shared station is half-turned about Z. Both shared rail lands and both servo/frame side faces must seat before alternating tightening. Loosen to slide only inside supported wall intervals. Moving between segments needs hardware removal and lift-off; no full-length continuous adjustment or self-centering mechanism.",
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
        "One straight6x1.5mm PA12 strip with three tape-wing pairs. Eleven identical20mm walls at28mm pitch retain ten8mm flex gaps. Each3.4x9.4mm slot leaves5.3mm end ligaments. Ordinary16mm feet retain±1.2mm full-foot travel, clipped to1mm toward each rail end to preserve the chamfered base lands. The paired continuous40mm propulsion spine uses30mm screw spacing and permits±2mm module trim from the intersection of two±3mm individual bolt windows, including the endmost wall pairs, with independently checked10mm clamp zones,2mm wall-end reserves, and at least14mm side-wall overlap per wall/32mm total. Fitted opposed legs and open-bottom recess floors carry the nominal clamp stack. Qualify actual fit, loaded curvature, lateral/torsional stability, friction retention, creep and adhesion; no stiffness, holding-force or strength rating.",
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
            "Same20mm wall/fitted U-seat geometry as full rail. Use the actual M3x10 bolt and M3 nut; test recessed head fit, open-bottom recess seating, both rail-contact faces, local sliding and side tool access. Finish only high spots while retaining at least1.5mm nut/head floors. Reject or reprint a loose or warped seat; do not pull a rigid clearance gap closed with the bolt. The companion50mm rail sample has one complete support and no inter-wall gap; it does not qualify the paired servo/frame interface, loaded clamping, full rail bending, adhesion or creep.",
        )
        set_property(
            obj,
            "RailAttachmentContract",
            json.dumps(attachment_contract(length=50), sort_keys=True),
        )
        printed.append(obj)
    return {"group": group, "printed": printed}
