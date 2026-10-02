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
WALL_LENGTH, WALL_PITCH = 18.0, 28.0
WALL_CENTRES = tuple(index * WALL_PITCH for index in range(-5, 6))
WEB_THICKNESS, WEB_TOP_Z = 2.5, 9.5
SLOT_HEIGHT, BOLT_AXIS_Z = 3.4, 6.0
SLOT_CENTRE_HALF_SPAN = 3.0
SHARED_SPINE_LENGTH = PROPULSION_ATTACHMENT.contact_length_mm
LOCAL_CONTACT_LENGTH = 10.0
WALL_END_ROOT_RADIUS, WALL_SIDE_ROOT_RADIUS = 1.0, 0.5
LOCAL_TILT_SCREEN_DEGREES = 2.0
SHARED_LOAD_ZONE_LENGTH = 10.0
SHARED_BOLT_HALF_RANGE = 3.0
# Matching bolt and wall pitches lets both local stations travel together.
SHARED_TRIM_HALF_RANGE = 3.0
MOUNT_LENGTH, MOUNT_LEG_THICKNESS = CARRIER_ATTACHMENT.contact_length_mm, 4.0
MOUNT_TOP_Z = CARRIER_ATTACHMENT.seat_z_mm
# Every shoe uses the same wall-top seat and clear lower legs. A rigid frame
# joining two shoes holds those two rail walls in a common seating plane.
CARRIER_LEG_BOTTOM_Z, CARRIER_INNER_ROOF_Z = 2.5, 9.5
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
    """Local cheek contact, independently of the upper structural envelope."""
    _contact_length(contact_length)
    return LOCAL_CONTACT_LENGTH / 2 + SLOT_END_SUPPORT_RESERVE


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
    """Retain complete identical supports including both end-root blends."""
    length = _positive(length, "Rail length")
    if length > LENGTH + TOL:
        raise ValueError("Rail length exceeds the designed wall layout")
    return tuple(
        (centre - WALL_LENGTH / 2, centre + WALL_LENGTH / 2)
        for centre in WALL_CENTRES
        if abs(centre) + WALL_LENGTH / 2 + WALL_END_ROOT_RADIUS <= length / 2 + TOL
    )


def flex_spans(length=LENGTH):
    """Unthickened base intervals between the end-root tangencies."""
    segments = wall_segments(length)
    return tuple(
        (left[1] + WALL_END_ROOT_RADIUS, right[0] - WALL_END_ROOT_RADIUS)
        for left, right in zip(segments, segments[1:])
    )


def base_shape(length=LENGTH):
    """Constant-width strip; only its four end corners are chamfered."""
    length = _positive(length, "Rail length")
    return plate_shape(0, length, BASE_WIDTH, chamfer=BASE_END_CHAMFER_MM)


def attachment_windows(
    length=LENGTH, contact_length=MOUNT_LENGTH, *, shared_drive=False
):
    """Slot adjustment with ten-millimetre side contact and wall-top seating.

    A sixteen-millimetre shoe roof retains at least fourteen millimetres of
    wall-top overlap through the intended ±3 mm trim. Upper structure may
    overhang a wall or rail end. The extra 0.2 mm radial slot clearance is
    for fit, not intended travel.
    """
    contact_length = _contact_length(contact_length)
    pattern = attachment_pattern(shared_drive)
    if shared_drive and abs(contact_length - pattern.contact_length_mm) > TOL:
        raise ValueError("Paired support requires the complete44mm shoe extent")
    inset = max(
        _slot_end_inset(contact_length),
        WALL_LENGTH / 2 - SLOT_CENTRE_HALF_SPAN,
    )
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
    """Individual bolt windows for the common local shoe interface."""
    return tuple(
        row["axis_travel_x_range_mm"]
        for row in attachment_windows(length, contact_length, shared_drive=shared_drive)
    )


def shared_module_ranges(length=LENGTH):
    """Paired module travel with both shoes supported on adjacent walls."""
    windows = supported_slot_ranges(length, SHARED_SPINE_LENGTH, shared_drive=True)
    half_spacing = PROPULSION_ATTACHMENT.half_spacing_mm
    ranges = []
    for first, second in zip(windows, windows[1:]):
        low = max(first[0] + half_spacing, second[0] - half_spacing)
        high = min(first[1] + half_spacing, second[1] - half_spacing)
        if low <= high + TOL:
            ranges.append((low, high))
    return tuple(ranges)


def paired_attachment_position_check(x):
    """Both bolt axes remain in supported slots; roofs may overhang the ends."""
    valid = not isinstance(x, bool) and isinstance(x, Real) and math.isfinite(x)
    ranges = shared_module_ranges()
    return {
        "module_x_mm": x,
        "supported_module_centre_ranges_x_mm": ranges,
        "passed": bool(
            valid and any(low - TOL <= x <= high + TOL for low, high in ranges)
        ),
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
            zone = LOCAL_CONTACT_LENGTH
            margin = min(x - zone / 2 - first, last - x - zone / 2)
            return {
                "x_mm": x,
                **row,
                "contact_length_mm": contact_length,
                "support_policy": "wall_top_bearing",
                "centred_load_zone_length_mm": zone,
                "minimum_centred_contact_end_margin_mm": margin,
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


def _rooted_wall():
    """A blended wall above Z1.5, built on a temporary generous base.

    Making the endmost blend on the complete rail fails when its base tangent
    meets the strip end. Building this identical local profile first avoids
    that topological degeneracy without changing the retained strip geometry.
    """
    temporary_length = WALL_LENGTH + 2 * WALL_END_ROOT_RADIUS + 2
    result = union(
        [
            box(
                temporary_length,
                BASE_WIDTH,
                PAD_THICKNESS,
                (-temporary_length / 2, -BASE_WIDTH / 2, 0),
            ),
            box(
                WALL_LENGTH,
                WEB_THICKNESS,
                WEB_TOP_Z - PAD_THICKNESS,
                (-WALL_LENGTH / 2, -WEB_THICKNESS / 2, PAD_THICKNESS),
            ),
        ]
    ).removeSplitter()
    # Blend concave roots before cutting the slots. The end blends extend one
    # millimetre into each nominal wall gap; the narrow side blends preserve
    # 1.25 mm of flat base ledge on each side of the 2.5 mm web.
    end_edges = [
        edge
        for edge in result.Edges
        if abs(edge.Length - WEB_THICKNESS) < TOL
        and len(edge.Vertexes) == 2
        and all(
            abs(vertex.Point.z - PAD_THICKNESS) < TOL
            and abs(abs(vertex.Point.x) - WALL_LENGTH / 2) < TOL
            for vertex in edge.Vertexes
        )
    ]
    if len(end_edges) != 2:
        raise RuntimeError("Rail wall must expose two end-root edges")
    result = result.makeFillet(WALL_END_ROOT_RADIUS, end_edges).removeSplitter()
    side_edges = [
        edge
        for edge in result.Edges
        if abs(edge.Length - WALL_LENGTH) < TOL
        and len(edge.Vertexes) == 2
        and all(
            abs(vertex.Point.z - PAD_THICKNESS) < TOL
            and abs(abs(vertex.Point.y) - WEB_THICKNESS / 2) < TOL
            for vertex in edge.Vertexes
        )
    ]
    if len(side_edges) != 2:
        raise RuntimeError("Rail wall must expose two side-root edges")
    result = result.makeFillet(WALL_SIDE_ROOT_RADIUS, side_edges).removeSplitter()
    return result.common(
        box(
            temporary_length,
            BASE_WIDTH,
            WEB_TOP_Z - PAD_THICKNESS,
            (-temporary_length / 2, -BASE_WIDTH / 2, PAD_THICKNESS),
        )
    ).removeSplitter()


def rail_shape(length=LENGTH, pads=PAD_CENTRES):
    length = _positive(length, "Rail length")
    pads = _stations(pads, length, PAD_LENGTH, "Tape-wing centres")
    segments = wall_segments(length)
    if not segments:
        raise ValueError("Rail must contain at least one usable wall segment")
    pieces = [base_shape(length)] + [plate_shape(x) for x in pads]
    wall = _rooted_wall().cut(_slot(-SLOT_CENTRE_HALF_SPAN, SLOT_CENTRE_HALF_SPAN))
    for first, last in segments:
        centre = (first + last) / 2
        pieces.append(translated_shape(wall, x=centre))
    result = union(pieces).removeSplitter()
    if not result.isValid() or len(result.Solids) != 1:
        raise RuntimeError("Rail must remain one valid solid")
    return result


def cut_shared_bolt_passage(shape):
    """Cut the integrated-frame clamp axes without depending on either part."""
    pattern = PROPULSION_ATTACHMENT
    outer_y = MOUNT_OUTER_Y
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
    """Carrier U with a flat wall-top datum and lower legs clear of the base.

    The 16 mm roof overlaps at least 14 mm of one 18 mm wall through ±3 mm
    trim. Ten-millimetre cheeks retain the fitted side faces and M3 floors.
    The propulsion frame uses two exact copies of this same interface.
    """
    top_z = _positive(top_z, "Mount top")
    length = _contact_length(length)
    if not isinstance(recess_head, bool):
        raise ValueError("Recess head must be a boolean")
    if top_z < CARRIER_INNER_ROOF_Z + PAD_THICKNESS - TOL:
        raise ValueError("Mount roof must retain at least1.5mm")
    result = union(
        [
            box(
                LOCAL_CONTACT_LENGTH,
                MOUNT_LEG_THICKNESS,
                top_z - CARRIER_LEG_BOTTOM_Z,
                (-LOCAL_CONTACT_LENGTH / 2, MOUNT_OUTER_Y, CARRIER_LEG_BOTTOM_Z),
            ),
            box(
                length,
                FAR_LEG_OUTER_Y - MOUNT_OUTER_Y,
                top_z - CARRIER_INNER_ROOF_Z,
                (-length / 2, MOUNT_OUTER_Y, CARRIER_INNER_ROOF_Z),
            ),
            box(
                LOCAL_CONTACT_LENGTH,
                FAR_LEG_THICKNESS,
                top_z - CARRIER_LEG_BOTTOM_Z,
                (-LOCAL_CONTACT_LENGTH / 2, FAR_LEG_INNER_Y, CARRIER_LEG_BOTTOM_Z),
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


def attachment_shoe_shapes(top_z=MOUNT_TOP_Z, *, shared_drive=False):
    """Exact ordinary shoes at each station, ready to fuse into upper structure.

    Paired shoes have a forty-four-millimetre overall roof extent, with a
    twelve-millimetre gap between roofs. Joining them rigidly constrains both
    wall-top datums to be coplanar; no independent wall-tilt freedom is implied.
    """
    pattern = attachment_pattern(shared_drive)
    shoe = mount_base_shape(top_z, length=pattern.shoe_length_mm)
    sites = pattern.sites(pattern.half_spacing_mm)
    return tuple(attachment_site_shape(shoe, site) for site in sites)


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
    """One shoe interface, used singly or as a rigid pair on adjacent walls."""
    length = _positive(length, "Rail length")
    _contact_length(contact_length)
    pattern = attachment_pattern(shared_drive)
    spans = flex_spans(length)
    roof_length = pattern.shoe_length_mm if shared_drive else contact_length
    overlap = min(
        roof_length,
        WALL_LENGTH,
        (roof_length + WALL_LENGTH) / 2 - SLOT_CENTRE_HALF_SPAN,
    )
    head_face_y = pattern.head_bearing_y(MOUNT_OUTER_Y, HEAD_RECESS_DEPTH)
    nut_bearing_y = pattern.nut_bearing_y_mm
    return {
        "rail_length_mm": length,
        "wall_count": len(wall_segments(length)),
        "wall_segments_x_mm": wall_segments(length),
        "wall_end_root_radius_mm": WALL_END_ROOT_RADIUS,
        "wall_side_root_radius_mm": WALL_SIDE_ROOT_RADIUS,
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
            "Straight6x1.5mm base between R1 end-root tangencies; each10mm wall gap contains8mm of unthickened base. A rigid paired mount holds its two walls coplanar; bending remains outside that supported pair. No qualified bend radius."
            if spans
            else "No free span in this rail section; clamp fit only."
        ),
        "web_thickness_mm": WEB_THICKNESS,
        "web_top_z_mm": WEB_TOP_Z,
        "mount_bottom_datum_z_mm": None,
        "lower_leg_bottom_z_mm": CARRIER_LEG_BOTTOM_Z,
        "base_clearance_mm": CARRIER_LEG_BOTTOM_Z - PAD_THICKNESS,
        "mount_inner_roof_z_mm": CARRIER_INNER_ROOF_Z,
        "nominal_inner_roof_clearance_mm": 0.0,
        "top_bearing_z_mm": CARRIER_INNER_ROOF_Z,
        "top_bearing_roof_length_mm": roof_length,
        "minimum_top_bearing_overlap_mm": overlap,
        "top_bearing_width_mm": WEB_THICKNESS,
        "minimum_base_mm": PAD_THICKNESS,
        "slot_height_mm": SLOT_HEIGHT,
        "slot_cap_centre_span_mm": 2 * SLOT_CENTRE_HALF_SPAN,
        "slot_overall_length_mm": 2 * SLOT_CENTRE_HALF_SPAN + SLOT_HEIGHT,
        "geometric_bolt_centreline_half_range_mm": SLOT_CENTRE_HALF_SPAN
        + (SLOT_HEIGHT - fasteners.RAIL_THREAD_DIAMETER) / 2,
        "intended_bolt_half_range_mm": SLOT_CENTRE_HALF_SPAN,
        "wall_end_ligament_mm": WALL_LENGTH / 2
        - SLOT_CENTRE_HALF_SPAN
        - SLOT_HEIGHT / 2,
        "bolt_axis_z_mm": BOLT_AXIS_Z,
        "mount_contact_length_mm": contact_length,
        "contact_length_scope": (
            "Two identical16mm carrier roofs28mm apart give44mm overall extent, with a12mm gap between roofs. Each roof seats on14..16mm of its wall top through intended±3mm trim; each shoe has10mm cheeks."
            if shared_drive
            else "The16mm carrier roof seats on14..16mm of one wall top through intended±3mm trim; its10mm cheeks retain the opposed clamp faces."
        ),
        "support_policy": "wall_top_bearing",
        "centred_load_zone_length_mm": LOCAL_CONTACT_LENGTH,
        "minimum_local_cheek_wall_end_margin_mm": SLOT_END_SUPPORT_RESERVE,
        "local_wall_tilt_screen_degrees": None
        if shared_drive
        else LOCAL_TILT_SCREEN_DEGREES,
        "local_wall_tilt_screen_scope": (
            "The rigid paired frame requires both wall-top datums to be coplanar. No independent local-wall tilt screen or fixed-deck curvature freedom is claimed. Fit the rail to the common seating plane before clamping; bend outside the supported pair."
            if shared_drive
            else "Carrier and local wall rotate together about Y at the stated sample angles. The carrier follows the wall attitude; this is a sampled rigid local fit screen, not independent fixed-deck clearance or loaded-curvature qualification."
        ),
        "shared_minimum_wall_seat_length_mm": overlap if shared_drive else None,
        "shared_minimum_total_seat_length_mm": 2 * overlap if shared_drive else None,
        "shared_individual_bolt_half_range_mm": SHARED_BOLT_HALF_RANGE
        if shared_drive
        else None,
        "shared_usable_trim_half_range_mm": SHARED_TRIM_HALF_RANGE
        if shared_drive
        else None,
        "mount_section": "Symmetric U with a flat Z9.5 wall-top datum,16mm roof, two10mm local cheeks and flat lower edges atZ2.5; no lower base contact.",
        "mount_outer_y_mm": MOUNT_OUTER_Y,
        "head_recess_diameter_mm": HEAD_RECESS_DIAMETER,
        "head_recess_depth_mm": HEAD_RECESS_DEPTH,
        "ordinary_head_bearing_floor_mm": MOUNT_LEG_THICKNESS - HEAD_RECESS_DEPTH,
        "fitted_channel_width_mm": WEB_THICKNESS,
        "nominal_side_clearance_mm": 0.0,
        "far_leg_inner_y_mm": FAR_LEG_INNER_Y,
        "far_leg_outer_y_mm": FAR_LEG_OUTER_Y,
        "nut_pocket_across_flats_mm": NUT_POCKET_AF,
        "nut_capture_depth_mm": FAR_LEG_OUTER_Y - nut_bearing_y,
        "nut_captive_without_screw": False,
        "recess_access": "Head and nut recesses open toward local-Z; round through-bores and axial bearing floors remain closed. Vertical hex flats restrain nut rotation. Hold the nut while starting the screw; it is not axially captive.",
        "carrier_side_legs_equal_thickness_mm": MOUNT_LEG_THICKNESS,
        "nut_pocket_inner_y_mm": FAR_LEG_INNER_Y,
        "nut_pocket_outer_y_mm": FAR_LEG_OUTER_Y,
        "nut_floor_nominal_mm": NUT_FLOOR_THICKNESS,
        "minimum_finished_nut_floor_mm": 1.5,
        "nut_bearing_y_mm": nut_bearing_y,
        "nut_bearing_scope": "The nut bears on the far U-leg floor. Both fitted legs contact the rail; compression crosses both printed floors and the rail web.",
        "bolt_length_mm": pattern.screw_length_mm,
        "head_bearing_y_mm": head_face_y,
        "printed_grip_mm": nut_bearing_y - head_face_y,
        "bolt_tip_beyond_nut_mm": head_face_y
        + pattern.screw_length_mm
        - nut_bearing_y
        - fasteners.RAIL_HEX_NUT_HEIGHT,
        "paired_propulsion_clamp": shared_drive,
        "clamp_count": pattern.count,
        "clamp_spacing_mm": pattern.spacing_mm,
        "fastener": "M3x10 recessed button-head bolt and M3 hex nut in an open-bottom load-bearing recess; unmeasured design envelopes",
        "shared_joint_service": (
            "Two identical carrier shoes28mm apart retain the integrated frame on adjacent18mm rail walls. Both flat roofs and all fitted side faces must seat together before alternating tightening. Matching pitches permit±3mm trim, including endmost wall pairs; the roofs may overhang. Support the complete propulsion assembly, remove both hardware pairs and lift it off to change wall pairs. The rigid frame requires coplanar wall tops and deliberately limits bending within that pair."
            if shared_drive
            else None
        ),
        "assembly": (
            "Seat both shoe roofs fully on coplanar wall tops and all local side faces before installing the two M3x10 pairs. The opposite station is half-turned about Z. Alternate tightening only after both shoes are hand-seated. "
            if shared_drive
            else "Seat the roof fully on the wall top and both local side faces before installing the M3x10 pair. The carrier follows its wall's local pitch. "
        )
        + "Both legs are4mm thick with2mm head/nut floors. Check free lower-leg clearance and open-bottom recess access; do not tighten an unseated or warped joint into place. Loosen for intended±3mm trim and reseat before tightening. Remove bolts and nuts before lifting between wall segments.",
        "load_path_scope": "Flat top bearing geometrically opposes fore-aft rocking about Y. Compression reaches each wall through its1.8mm upper slot ligament; top bearing is only2.5mm wide. Fitted side cheeks and clamp friction remain essential for roll about X, pull-away loads and retained adjustment. No stronger wall or all-axis stiffness improvement is established.",
        "physical_acceptance": "Use a process-matched coupon and actual hardware. The top and side datums are nominal contact fits with no intended operating gap. Hand-seat them together, preserve at least1.5mm finished fastener floors and reject a warped or loose fit. Verify lower-leg clearance, top seating, nut restraint, tool access, thread engagement and retained attitude under load. Top-slot-ligament deflection, contact pressure, friction, creep and physical curvature remain unqualified.",
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
        "One straight6x1.5mm PA12 strip with three tape-wing pairs. Eleven18mm walls at28mm pitch have R1 end roots and R0.5 side roots; each10mm wall gap retains8mm of unthickened base. Each3.4x9.4mm slot leaves4.3mm end ligaments. Identical16mm carrier shoes seat on the wall tops atZ9.5 with10mm local cheeks and lower edges atZ2.5, clear of the base. The propulsion frame uses two such shoes28mm apart, giving44mm overall roof extent and requiring their wall-top datums to be coplanar. Matching28mm paired bolt spacing permits±3mm intended trim for every carrier and wall pair, including end stations; local cheeks retain at least1mm wall-end reserve. The upper structure may overhang a wall. An ordinary carrier can follow its local wall attitude; the paired frame holds two walls coplanar, with rail bending outside that supported pair. Neither condition qualifies physical curvature. Qualify contact pressure, fit, loaded curvature, torsional stability, friction retention, creep and adhesion; no stiffness, holding-force or strength rating.",
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
            "Same18mm wall and R1 end/R0.5 side roots as the full rail. The ordinary carrier coupon has a16mm roof bearing on the wall top atZ9.5,10mm local U cheeks and lower edges atZ2.5 clear of the base; it follows the wall attitude. Use the actual M3x10 bolt and M3 nut; test recessed head fit, open-bottom recess seating, both local rail-contact faces, sliding and side tool access. Finish only high spots while retaining at least1.5mm nut/head floors. Reject or reprint a loose or warped seat; do not pull a rigid clearance gap closed with the bolt. The companion50mm rail sample has one complete support and no inter-wall gap; it does not qualify the paired servo/frame interface, loaded clamping, full rail bending, adhesion or creep.",
        )
        set_property(
            obj,
            "RailAttachmentContract",
            json.dumps(attachment_contract(length=50), sort_keys=True),
        )
        printed.append(obj)
    return {"group": group, "printed": printed}
