"""Nominal rail contact, fastener load paths and removal checks.

These production checks consume rail builders; saved-geometry validation keeps
its separate literal witnesses in rail_mount.py. No physical retention is certified.
"""

import math
from numbers import Real

import FreeCAD as App
import Part

from gondola.cad import box, translated_shape, union
from gondola.contracts import fasteners
from gondola.contracts.rail_attachments import attachment_pattern
from gondola.parts import rail

V = App.Vector


def flex_relief_check(rail_section=None, length=rail.LENGTH):
    section = (
        rail.rail_shape(length, () if length < rail.LENGTH else rail.PAD_CENTRES)
        if rail_section is None
        else rail_section
    )
    rows = []
    for first, last in rail.flex_spans(length):
        witness = box(
            last - first,
            rail.BASE_WIDTH,
            rail.WEB_TOP_Z - rail.PAD_THICKNESS + 0.1,
            (first, -rail.BASE_WIDTH / 2, rail.PAD_THICKNESS),
        )
        overlap = abs(section.common(witness).Volume)
        rows.append(
            {
                "x_range_mm": (first, last),
                "above_base_obstruction_mm3": overlap,
                "passed": overlap < rail.TOL,
            }
        )
    return {
        "open_spans": rows,
        "base_thickness_mm": rail.PAD_THICKNESS,
        "free_span_minimum_width_mm": rail.BASE_WIDTH,
        "scope": "Open above-base spans only; no stiffness, bend-radius or fatigue rating.",
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }


def _rail_seat_contacts(section, mount, zone_length):
    """Probe the two bottom lands, relieved roof and opposed rail faces."""
    # Bilateral bottom lands are the vertical datum. The inner roof deliberately
    # clears the rail top; forcing three planes into contact overconstrains fit.
    bottom_contacts = []
    for side_sign in (-1, 1):
        y = -rail.BASE_WIDTH / 2 if side_sign < 0 else rail.WEB_THICKNESS / 2
        width = (rail.BASE_WIDTH - rail.WEB_THICKNESS) / 2
        below = box(
            zone_length, width, 0.01, (-zone_length / 2, y, rail.PAD_THICKNESS - 0.01)
        )
        above = translated_shape(below, z=0.01)
        missing = abs(below.cut(section).Volume) + abs(above.cut(mount).Volume)
        bottom_contacts.append(
            {
                "side": side_sign,
                "minimum_area_mm2": zone_length * width,
                "missing_contact_mm3": missing,
                "passed": missing < rail.TOL,
            }
        )
    roof_relief = box(
        zone_length,
        rail.WEB_THICKNESS,
        rail.MOUNT_INNER_ROOF_Z - rail.WEB_TOP_Z,
        (-zone_length / 2, -rail.WEB_THICKNESS / 2, rail.WEB_TOP_Z),
    )
    blocked_roof_relief = abs(roof_relief.common(mount).Volume)
    # Both side faces, above and below the longitudinal rail slot, must contact.
    side = box(
        zone_length,
        0.01,
        rail.WEB_TOP_Z - rail.MOUNT_BOTTOM_Z,
        (-zone_length / 2, -rail.WEB_THICKNESS / 2 - 0.01, rail.MOUNT_BOTTOM_Z),
    ).cut(rail._slot(-zone_length, zone_length))
    missing_side = abs(side.cut(mount).Volume) + abs(
        translated_shape(side, y=0.01).cut(section).Volume
    )
    opposite_side = translated_shape(side, y=rail.WEB_THICKNESS + 0.01)
    missing_opposite = abs(opposite_side.cut(mount).Volume) + abs(
        translated_shape(opposite_side, y=-0.01).cut(section).Volume
    )

    return {
        "bottom_datum_contacts": bottom_contacts,
        "inner_roof_clearance_mm": rail.MOUNT_INNER_ROOF_Z - rail.WEB_TOP_Z,
        "blocked_inner_roof_relief_mm3": blocked_roof_relief,
        "missing_flat_side_contact_mm3": missing_side,
        "missing_opposite_side_contact_mm3": missing_opposite,
    }


def _fastener_seat_contacts(
    clamp, mount, head_support, head_face_y, nut_bearing_y, frame_contact_y
):
    """Probe head/nut bearing lands and both optional frame/saddle faces."""

    def annulus(y, depth):
        return Part.makeCylinder(
            fasteners.RAIL_SCREW_HEAD_DIAMETER / 2,
            depth,
            V(0, y, rail.BOLT_AXIS_Z),
            V(0, 1, 0),
        ).cut(
            Part.makeCylinder(
                rail.SLOT_HEIGHT / 2,
                depth + 0.02,
                V(0, y - 0.01, rail.BOLT_AXIS_Z),
                V(0, 1, 0),
            )
        )

    missing_head = abs(annulus(head_face_y, 0.01).cut(clamp).Volume)
    nut_floor = rail._nut_outer(
        fasteners.RAIL_HEX_NUT_AF,
        rail.NUT_FLOOR_THICKNESS,
        bearing_y=nut_bearing_y - rail.NUT_FLOOR_THICKNESS,
    ).cut(
        Part.makeCylinder(
            rail.SLOT_HEIGHT / 2,
            rail.NUT_FLOOR_THICKNESS + 0.02,
            V(0, nut_bearing_y - rail.NUT_FLOOR_THICKNESS - 0.01, rail.BOLT_AXIS_Z),
            V(0, 1, 0),
        )
    )
    missing_floor = abs(nut_floor.cut(clamp).Volume)
    nut_face = rail._nut_outer(
        fasteners.RAIL_HEX_NUT_AF, 0.01, bearing_y=nut_bearing_y - 0.01
    ).cut(
        Part.makeCylinder(
            rail.SLOT_HEIGHT / 2,
            0.03,
            V(0, nut_bearing_y - 0.02, rail.BOLT_AXIS_Z),
            V(0, 1, 0),
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
                    "passed": max(missing_frame, missing_saddle) < rail.TOL,
                }
            )
    return {
        "missing_head_support_mm3": missing_head,
        "missing_nut_support_mm3": missing_nut,
        "missing_printed_nut_floor_mm3": missing_floor,
        "nut_bearing_area_outside_bore_mm2": nut_area,
        "frame_saddle_contact_faces": frame_faces,
    }


def attachment_check(
    rail_section=None,
    mount=None,
    *,
    screw_length=rail.SCREW_LENGTH,
    contact_length=rail.MOUNT_LENGTH,
    head_face_y=rail.HEAD_BEARING_Y,
    head_support=None,
    nut_bearing_y=rail.NUT_BEARING_Y,
    nut_outer_y=rail.FAR_LEG_OUTER_Y,
    frame_contact_y=None,
    shared_drive=False,
):
    """Nominal fitted load stack and local release, not physical clamp strength.

    Shared checks supply both saddle cheeks in head_support, nut seat8/outer11,
    and frame_contact_y6. Independent saved validators also check actual parts.
    """
    from gondola.validation.geometry import translation_sweep

    contact_length = rail._contact_length(contact_length)
    attachment_pattern(shared_drive)
    if shared_drive and (
        abs(contact_length - rail.SHARED_SPINE_LENGTH) > rail.TOL or mount is None
    ):
        raise ValueError("Shared attachment requires the actual46mm frame spine")
    zone_length = rail.SHARED_LOAD_ZONE_LENGTH if shared_drive else contact_length
    if (
        not all(
            isinstance(value, Real)
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in (nut_bearing_y, nut_outer_y)
        )
        or nut_outer_y < nut_bearing_y + rail.MINIMUM_NUT_CAPTURE_DEPTH - rail.TOL
    ):
        raise ValueError("Nut pocket must retain at least 1.5 mm nominal recess depth")
    if frame_contact_y is not None:
        frame_contact_y = rail._positive(frame_contact_y, "Frame contact half-width")
    section = rail.rail_shape(50, (0,)) if rail_section is None else rail_section
    mount = rail.mount_base_shape(length=contact_length) if mount is None else mount
    clamp = mount if head_support is None else union([mount, head_support])
    screw = rail.attachment_screw_shape(screw_length, head_face_y=head_face_y)
    nut = rail.nut_shape(bearing_y=nut_bearing_y)
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
                rail.HEAD_RECESS_DIAMETER,
                rail.HEAD_RECESS_DEPTH,
                rail.HEAD_RECESS_DIAMETER,
                (
                    -rail.HEAD_RECESS_DIAMETER / 2,
                    head_face_y - rail.HEAD_RECESS_DEPTH,
                    rail.BOLT_AXIS_Z - rail.HEAD_RECESS_DIAMETER / 2,
                ),
            ),
            box(
                rail.SLOT_HEIGHT,
                -rail.WEB_THICKNESS / 2 - head_face_y,
                rail.SLOT_HEIGHT,
                (
                    -rail.SLOT_HEIGHT / 2,
                    head_face_y,
                    rail.BOLT_AXIS_Z - rail.SLOT_HEIGHT / 2,
                ),
            ),
            box(
                rail.SLOT_HEIGHT,
                nut_outer_y - rail.WEB_THICKNESS / 2,
                rail.SLOT_HEIGHT,
                (
                    -rail.SLOT_HEIGHT / 2,
                    rail.WEB_THICKNESS / 2,
                    rail.BOLT_AXIS_Z - rail.SLOT_HEIGHT / 2,
                ),
            ),
            rail._nut_outer(
                rail.NUT_POCKET_AF,
                nut_outer_y - nut_bearing_y,
                bearing_y=nut_bearing_y,
            ),
        ]
    ).removeSplitter()
    lift, method = translation_sweep(filled_mount, (0, 0, 25))
    lift_overlap = abs(lift.common(section).Volume)
    contacts = _rail_seat_contacts(section, mount, zone_length)
    supports = _fastener_seat_contacts(
        clamp, mount, head_support, head_face_y, nut_bearing_y, frame_contact_y
    )
    tip = head_face_y + screw_length
    engagement = tip - (nut_bearing_y + fasteners.RAIL_HEX_NUT_HEIGHT)
    nut_sweep, nut_method = translation_sweep(
        rail._nut_outer(
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
    turned_nut.rotate(V(0, 0, rail.BOLT_AXIS_Z), V(0, 1, 0), 30)
    nut_rotation_stop = abs(turned_nut.common(clamp).Volume)
    return {
        "support_policy": "paired_spine_clamp_zone" if shared_drive else "full_foot",
        "checked_centred_contact_length_mm": zone_length,
        "shared_support_scope": (
            "This local check covers only the12mm centred clamp zone. The saved paired-spine check must additionally verify complete bottom lands and both side-wall overlaps of minimum17/37mm."
            if shared_drive
            else None
        ),
        "seated_intersections_mm3": overlaps,
        "continuous_vertical_removal": {"method": method, "overlap_mm3": lift_overlap},
        "continuous_nut_release": {"method": nut_method, "overlap_mm3": nut_release},
        **contacts,
        "missing_head_support_mm3": supports["missing_head_support_mm3"],
        "missing_nut_support_mm3": supports["missing_nut_support_mm3"],
        "missing_printed_nut_floor_mm3": supports["missing_printed_nut_floor_mm3"],
        "nut_bearing_area_outside_bore_mm2": supports[
            "nut_bearing_area_outside_bore_mm2"
        ],
        "nut_floor_nominal_mm": rail.NUT_FLOOR_THICKNESS,
        "nut_bearing_y_mm": nut_bearing_y,
        "nut_pocket_outer_y_mm": nut_outer_y,
        "nut_capture_depth_mm": nut_outer_y - nut_bearing_y,
        "nominal_side_clearance_mm": 0.0,
        "frame_saddle_contact_faces": supports["frame_saddle_contact_faces"],
        "nut_30deg_rotation_stop_block_mm3": nut_rotation_stop,
        "bolt_length_mm": screw_length,
        "head_bearing_y_mm": head_face_y,
        "printed_grip_mm": nut_bearing_y - head_face_y,
        "shared_head_support_supplied": head_support is not None,
        "bolt_tip_beyond_nut_mm": engagement,
        "full_nominal_nut_height_engaged": engagement >= -rail.TOL,
        "minimum_thread_projection_mm": fasteners.RAIL_THREAD_PITCH,
        "thread_projection_margin_ok": engagement
        >= fasteners.RAIL_THREAD_PITCH - rail.TOL,
        "scope": "Nominal fitted U geometry with both rail-contact legs and a printed nut-bearing floor in the compression path. Shared saddle checks include both frame/saddle contact faces at the bolt load annulus. This is a line-to-line design, not an as-printed fit guarantee; qualify by coupon and finish high spots, rejecting loose or warped seats. No qualified torque, friction, creep, curvature, physical fit or whole-module tool-access claim.",
        "passed": max(overlaps.values()) < rail.TOL
        and lift_overlap < rail.TOL
        and nut_release < rail.TOL
        and max(
            contacts["blocked_inner_roof_relief_mm3"],
            contacts["missing_flat_side_contact_mm3"],
            contacts["missing_opposite_side_contact_mm3"],
            supports["missing_head_support_mm3"],
            supports["missing_nut_support_mm3"],
            supports["missing_printed_nut_floor_mm3"],
        )
        < rail.TOL
        and all(row["passed"] for row in contacts["bottom_datum_contacts"])
        and supports["nut_bearing_area_outside_bore_mm2"] > 0
        and all(row["passed"] for row in supports["frame_saddle_contact_faces"])
        and nut_rotation_stop > rail.TOL
        and engagement >= fasteners.RAIL_THREAD_PITCH - rail.TOL,
    }


def validate_mechanism():
    attachment, flex = attachment_check(), flex_relief_check()
    return {
        "passed": attachment["passed"] and flex["passed"],
        "attachment": attachment,
        "flex_relief": flex,
        "rail_length_mm": rail.LENGTH,
        "continuous_single_rail": True,
        "supported_bolt_axis_ranges_x_mm": rail.supported_slot_ranges(),
        "tape": rail.tape_attachment_contract(),
        "release": "Loosen the recessed side M3 bolt and slide within the current supported slot. To change wall segment remove bolt and nut, then lift the U seat. The open-bottom nut recess restrains rotation while allowing straight axial removal; both fitted contact faces must seat without forcing a rigid clearance gap closed. No full-length slide or automatic calibration.",
    }
