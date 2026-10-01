"""Saved side-slot rail, integral U saddles and recessed M3 hardware checks."""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import placed_shape
from gondola.parts import equipment_mounts, propulsion, rail
from gondola.print_export import geometry_comparison

from . import rail_contact
from .evidence import comparison_passed
from .geometry import belongs_to_group, intersection_volume, local_shape
from .rail_interface import (
    MOUNT_BINDINGS,
    attachment_sites,
    mount_binding,
    site_placement,
)

V = App.Vector
TOL = 1e-5


def _contract_matches(obj, property_name, expected):
    try:
        return json.loads(getattr(obj, property_name)) == json.loads(
            json.dumps(expected)
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _offset(module):
    binding = mount_binding(module.Name)
    return binding[3] if binding is not None else 0


def _foot_placement(module, inverse, site=None):
    if site is None:
        site = attachment_sites(module.Name, _offset(module))[0]
    return inverse.multiply(module.getGlobalPlacement()).multiply(site_placement(site))


def tape_station_alignment(rail_object, modules, tapes, shapes):
    """Saved attachment-axis proximity, not an adhesion or support pass flag."""
    inverse = rail_object.getGlobalPlacement().inverse()
    tape_bounds = [
        (obj.Name, placed_shape(shapes[obj.Name], inverse).BoundBox) for obj in tapes
    ]
    rows = []
    for module in modules:
        for site in attachment_sites(module.Name, _offset(module)):
            x = _foot_placement(module, inverse, site).Base.x
            nearest = {}
            for side, label in ((-1, "negative_y"), (1, "positive_y")):
                candidates = [
                    (name, bounds)
                    for name, bounds in tape_bounds
                    if side * bounds.YMin > 0 and side * bounds.YMax > 0
                ]
                if not candidates:
                    nearest[label] = None
                    continue
                name, bounds = min(
                    candidates, key=lambda item: abs(item[1].Center.x - x)
                )
                nearest[label] = {
                    "object": name,
                    "centre_x_mm": bounds.Center.x,
                    "centre_distance_mm": abs(bounds.Center.x - x),
                    "station_within_tape_width": bounds.XMin - TOL
                    <= x
                    <= bounds.XMax + TOL,
                    "same_attachment_station": abs(bounds.Center.x - x) < TOL,
                }
            rows.append(
                {
                    "module": module.Name,
                    "attachment_prefix": site["prefix"],
                    "station_x_mm": x,
                    "nearest_tapes": nearest,
                }
            )
    return {
        "modules": rows,
        "scope": "Saved tape/attachment positions in the rail frame only. Under-base adhesive is unmodeled. Tape proximity neither proves adhesion/load capacity nor prohibits other supported slot positions; qualify retention and routing after relocation.",
    }


def _literal_protected_mount(length=16, *, shared=False, bolt_positions=(0,)):
    """Independent fitted U stock; shared frame carries no nut recess."""
    low, high = (-6.0, 6.0) if shared else (-5.25, 5.25)
    leg = Part.makeBox(length, -1.25 - low, 11, V(-length / 2, low, 1.5))
    roof = Part.makeBox(length, high - low, 2.8, V(-length / 2, low, 9.7))
    far_leg = Part.makeBox(length, high - 1.25, 11, V(-length / 2, 1.25, 1.5))
    result = leg.fuse(roof).fuse(far_leg)
    if not shared:
        radius = 5.9 / math.sqrt(3)
        vertices = [
            V(
                radius * math.cos(math.radians(a)),
                3.25,
                6 + radius * math.sin(math.radians(a)),
            )
            for a in range(30, 390, 60)
        ]
        pocket = Part.Face(Part.makePolygon(vertices + vertices[:1])).extrude(
            V(0, 3.8, 0)
        )
        result = result.cut(pocket).cut(
            Part.makeCylinder(3.2, 2.1, V(0, -5.35, 6), V(0, 1, 0))
        )
        result = result.cut(Part.makeBox(5.9, 3.8, 7, V(-2.95, 3.25, -1)))
        result = result.cut(Part.makeBox(6.4, 2.1, 7, V(-3.2, -5.35, -1)))
    for x in bolt_positions:
        result = result.cut(
            Part.makeCylinder(1.7, high - low + 2, V(x, low - 1, 6), V(0, 1, 0))
        )
    return result.removeSplitter()


def _lower_crop(offset=0, length=16, *, shared=False):
    low, width = (-6.0, 12.0) if shared else (-5.25, 10.5)
    return Part.makeBox(length, width, 11, V(offset - length / 2, low, 1.5))


def _literal_plate(x, length, width, chamfer):
    """Independent planar outline; all thickness/size inputs below are literals."""
    left, right, half_width = x - length / 2, x + length / 2, width / 2
    points = [
        V(left + chamfer, -half_width, 0),
        V(right - chamfer, -half_width, 0),
        V(right, -half_width + chamfer, 0),
        V(right, half_width - chamfer, 0),
        V(right - chamfer, half_width, 0),
        V(left + chamfer, half_width, 0),
        V(left, half_width - chamfer, 0),
        V(left, -half_width + chamfer, 0),
    ]
    return Part.Face(Part.makePolygon(points + points[:1])).extrude(V(0, 0, 1.5))


def _independent_base_witnesses():
    """Full literal 300x6x1.5mm strip and three14x32mm wings, including chamfers."""
    retained = _literal_plate(0, 300, 6, 1)
    for centre in (-140, 0, 140):
        retained = retained.fuse(_literal_plate(centre, 14, 32, 2))
    region = Part.makeBox(302, 34, 1.5, V(-151, -17, 0))
    return retained.removeSplitter(), region


def _independent_wall_top_sections(shape):
    """Literal eleven wall intervals above the slots, independent of generator data."""
    line = Part.makeLine(V(-151, 0, 8.5), V(151, 0, 8.5))
    actual = sorted(
        (edge.BoundBox.XMin, edge.BoundBox.XMax) for edge in shape.common(line).Edges
    )
    expected = (
        (-150, -130),
        (-122, -102),
        (-94, -74),
        (-66, -46),
        (-38, -18),
        (-10, 10),
        (18, 38),
        (46, 66),
        (74, 94),
        (102, 122),
        (130, 150),
    )
    return {
        "sample_yz_mm": [0, 8.5],
        "actual_wall_intervals_x_mm": actual,
        "expected_wall_intervals_x_mm": expected,
        "passed": len(actual) == len(expected)
        and all(
            abs(value - target) < TOL
            for pair, reference in zip(actual, expected)
            for value, target in zip(pair, reference)
        ),
    }


def _literal_rail_slot(centre):
    """Fresh independent slot witness, with the two caps fused in order."""
    slot = Part.makeBox(6, 4.5, 3.4, V(centre - 3, -2.25, 4.3))
    for offset in (-3, 3):
        slot = slot.fuse(
            Part.makeCylinder(1.7, 4.5, V(centre + offset, -2.25, 6), V(0, 1, 0))
        )
    return slot


def _independent_slot_sections(shape):
    """Literal 9.4x3.4 mm openings, including their complete end/web stock."""
    rows = []
    for centre in range(-140, 141, 28):
        stock = Part.makeBox(20, 2.5, 8, V(centre - 10, -1.25, 1.5))
        slot = _literal_rail_slot(centre)
        actual = shape.common(stock)
        comparison = (
            geometry_comparison(actual, stock.cut(slot))
            if not actual.isNull() and actual.Solids and abs(actual.Volume) > TOL
            else {
                "error": "Missing wall solid",
                "difference_mm3": abs(stock.cut(slot).Volume),
            }
        )
        rows.append(
            {
                "wall_centre_x_mm": centre,
                "comparison": comparison,
                "passed": "error" not in comparison
                and comparison_passed(comparison, TOL),
            }
        )
    return {
        "slot_cap_centre_span_mm": 6.0,
        "slot_overall_length_mm": 9.4,
        "wall_end_ligament_mm": 5.3,
        "upper_web_mm": 1.8,
        "lower_web_mm": 2.8,
        "walls": rows,
        "passed": len(rows) == 11 and all(row["passed"] for row in rows),
    }


def _paired_bottom_contacts(rail_in_module, frame):
    """Require both complete lower lands on the continuous rail base."""
    bottoms = []
    for side, y in ((-1, -3), (1, 1.25)):
        below = Part.makeBox(46, 1.75, 0.01, V(-23, y, 1.49))
        above = Part.makeBox(46, 1.75, 0.01, V(-23, y, 1.5))
        missing = abs(below.cut(rail_in_module).Volume) + abs(above.cut(frame).Volume)
        bottoms.append(
            {
                "side": side,
                "minimum_area_mm2": 80.5,
                "missing_contact_mm3": missing,
                "passed": missing < TOL,
            }
        )
    return bottoms


def _paired_wall_support(rail_in_module, frame, intervals, axis):
    """Check one bolt's wall overlap, load-zone margin and opposed side faces."""
    matches = [(low, high) for low, high in intervals if low <= axis <= high]
    if len(matches) != 1:
        return {
            "bolt_x_mm": axis,
            "passed": False,
            "error": "Each bolt must lie on one continuous wall",
        }
    first, last = matches[0]
    low, high = max(first, -23), min(last, 23)
    span = max(0.0, high - low)
    end_margin = min(axis - 6 - first, last - axis - 6)
    centre = (first + last) / 2
    slot = _literal_rail_slot(centre)
    faces = []
    for side, y in ((-1, -1.25), (1, 1.24)):
        inside = Part.makeBox(span, 0.01, 8, V(low, y, 1.5)).cut(slot)
        outside = inside.copy()
        outside.translate(V(0, side * 0.01, 0))
        missing = abs(inside.cut(rail_in_module).Volume) + abs(
            outside.cut(frame).Volume
        )
        faces.append(
            {
                "side": side,
                "area_mm2": inside.Volume / 0.01,
                "missing_contact_mm3": missing,
                "passed": missing < TOL,
            }
        )
    return {
        "bolt_x_mm": axis,
        "wall_interval_x_mm": [first, last],
        "supported_side_interval_x_mm": [low, high],
        "wall_overlap_length_mm": span,
        "side_contacts": faces,
        "centred_load_zone_length_mm": 12.0,
        "minimum_load_zone_end_margin_mm": end_margin,
        "standard_wall_length_mm": last - first,
        "passed": span >= 17 - TOL
        and abs(last - first - 20) < TOL
        and end_margin >= 1 - TOL
        and all(face["passed"] for face in faces),
    }


def paired_spine_support_check(rail_in_module, frame):
    """Independent full bottom datum and two supported rail-wall overlaps.

    The 46 mm spine may bridge an 8 mm rail-wall gap. Both complete lower
    lands bear on the continuous base; wall overlap and the local bolt zones
    are checked separately. The 0.2 mm roof gap is intentional fit relief.
    """
    bottoms = _paired_bottom_contacts(rail_in_module, frame)
    relief = Part.makeBox(46, 2.5, 0.2, V(-23, -1.25, 9.5))
    blocked_relief = abs(relief.common(frame).Volume)
    line = Part.makeLine(V(-200, 0, 8.5), V(200, 0, 8.5))
    intervals = sorted(
        (e.BoundBox.XMin, e.BoundBox.XMax) for e in rail_in_module.common(line).Edges
    )
    rows = [
        _paired_wall_support(rail_in_module, frame, intervals, axis)
        for axis in (-15, 15)
    ]
    total = sum(row.get("wall_overlap_length_mm", 0) for row in rows)
    pair_intervals = [row.get("wall_interval_x_mm") for row in rows]
    adjacent = (
        all(pair_intervals)
        and abs(pair_intervals[1][0] - pair_intervals[0][1] - 8) < TOL
    )
    return {
        "spine_extent_mm": 46.0,
        "bottom_datum_z_mm": 1.5,
        "bottom_datum_contacts": bottoms,
        "minimum_bottom_contact_area_mm2": 161.0,
        "inner_roof_clearance_mm": 0.2,
        "blocked_inner_roof_relief_mm3": blocked_relief,
        "minimum_wall_overlap_length_mm": 17.0,
        "minimum_total_wall_overlap_length_mm": 37.0,
        "wall_overlap_length_total_mm": total,
        "wall_supports": rows,
        "adjacent_standard_walls": adjacent,
        "scope": "Both full46x1.75mm bottom lands seat on the continuous base; the inner roof clears the rail by0.2mm nominal. Two wall overlaps retain12mm bolt-load zones and1mm end margins, at least17mm per wall/37mm total. Neutral overlaps19+19mm; travel extremes17+20mm. The30mm bolt spacing uses±1mm outward slot positions on28mm wall pitch; independent±3mm bolt travel intersects into±2mm module trim. Nominal geometry only; no printed-fit, equal-stiffness or loaded-retention claim.",
        "passed": len(rows) == 2
        and adjacent
        and total >= 37 - TOL
        and all(row["passed"] for row in rows + bottoms)
        and blocked_relief < TOL
        and rows[0].get("wall_interval_x_mm") != rows[1].get("wall_interval_x_mm"),
    }


def saved_integral_mount_checks(doc, registry):
    printed, equipment = list(registry.PrintedParts), list(registry.EquipmentMounts)
    expected = [name for name, _, kind, _, _ in MOUNT_BINDINGS if kind is not None]
    inventory = sorted(obj.Name for obj in equipment) == sorted(expected) and all(
        obj == doc.getObject(obj.Name) for obj in equipment
    )
    rows = []
    for name, parent_name, kind, offset, length in MOUNT_BINDINGS:
        obj = doc.getObject(name)
        if obj is None or not hasattr(obj, "Shape"):
            rows.append(
                {"part": name, "passed": False, "error": "Missing integral mount"}
            )
            continue
        actual = local_shape(obj)
        source = (
            propulsion.fixed_frame_shape()
            if kind is None
            else equipment_mounts.mount_shape(kind)
        )
        complete = geometry_comparison(actual, source)
        sites = attachment_sites(parent_name, offset)
        zone_length = 12.0 if kind is None else length
        crops = [
            placed_shape(
                _lower_crop(0, zone_length, shared=kind is None), site_placement(site)
            )
            for site in sites
        ]
        literals = [
            placed_shape(
                _literal_protected_mount(zone_length, shared=kind is None),
                site_placement(site),
            )
            for site in sites
        ]
        crop, literal = Part.makeCompound(crops), Part.makeCompound(literals)
        lower, source_lower = (
            geometry_comparison(actual.common(crop), literal),
            geometry_comparison(source.common(crop), literal),
        )
        if kind is None:
            # Full continuous spine, beyond the two local clamp zones.
            whole_crop = _lower_crop(0, 46, shared=True)
            whole_literal = _literal_protected_mount(
                46, shared=True, bolt_positions=(-15, 15)
            )
            lower = geometry_comparison(actual.common(whole_crop), whole_literal)
            source_lower = geometry_comparison(source.common(whole_crop), whole_literal)
        site_checks = [
            {
                "attachment_prefix": site["prefix"],
                "attachment_local_x_mm": site["x_offset"],
                "attachment_side": site["side"],
                "independent_lower_mount_comparison": geometry_comparison(
                    actual.common(region), witness
                ),
                "source_lower_mount_comparison": geometry_comparison(
                    source.common(region), witness
                ),
            }
            for site, region, witness in zip(sites, crops, literals)
        ]
        parent = doc.getObject(parent_name)
        parent_ok = parent is not None and obj.getParentGeoFeatureGroup() == parent
        registered = printed.count(obj) == 1
        placement_ok = (
            obj.Placement.Base.Length < TOL and abs(obj.Placement.Rotation.Angle) < TOL
        )
        rows.append(
            {
                "part": name,
                "attachment_local_x_mm": offset,
                "attachment_sites": site_checks,
                "source_comparison": complete,
                "independent_lower_mount_comparison": lower,
                "source_lower_mount_comparison": source_lower,
                "expected_parent": parent_name,
                "parent_matches": parent_ok,
                "registered_once_as_print": registered,
                "part_local_placement_identity": placement_ok,
                "equipment_registry_matches": inventory,
                "passed": parent_ok
                and placement_ok
                and registered
                and inventory
                and all(
                    comparison_passed(check, TOL)
                    for check in (complete, lower, source_lower)
                ),
            }
        )
    return rows


def _saved_mounts(registry, shapes, rail_obj, rail_shape):
    inverse = rail_obj.getGlobalPlacement().inverse()
    bindings = {
        parent: (part, kind, offset, length)
        for part, parent, kind, offset, length in MOUNT_BINDINGS
    }
    rows = []
    for module in registry.Modules:
        binding = bindings.get(module.Name)
        if binding is None:
            rows.append(
                {"module": module.Name, "passed": False, "error": "Unknown rail module"}
            )
            continue
        name, _, offset, length = binding
        part = registry.Document.getObject(name)
        if part is None or name not in shapes:
            rows.append(
                {
                    "module": module.Name,
                    "passed": False,
                    "error": "Missing integral U solid",
                }
            )
            continue
        shared = module.Name == "MainPropulsionModule"
        paired_support = None
        if shared:
            module_in_rail = inverse.multiply(module.getGlobalPlacement())
            paired_support = paired_spine_support_check(
                placed_shape(rail_shape, module_in_rail.inverse()), local_shape(part)
            )
        for site in attachment_sites(module.Name, offset):
            canonical_placement = site_placement(site)
            foot_placement = _foot_placement(module, inverse, site)
            position = foot_placement.Base
            position_check = rail.attachment_position_check(
                position.x, contact_length=length, shared_drive=shared
            )
            centred = abs(position.y) < TOL and abs(position.z) < TOL
            printed_in_rail = placed_shape(shapes[name], inverse)
            overlap = intersection_volume(printed_in_rail, rail_shape)
            canonical_part = placed_shape(
                local_shape(part), canonical_placement.inverse()
            )
            zone_length = 12.0 if shared else length
            lower = canonical_part.common(_lower_crop(0, zone_length, shared=shared))
            local_rail = placed_shape(rail_shape, foot_placement.inverse())
            screw_length, head_face_y = (20.0, -9.0) if shared else (10.0, -3.25)
            head_support = None
            if shared:
                bridge = registry.Document.getObject("ServoDriveBridge")
                if (
                    bridge is None
                    or bridge.Name not in shapes
                    or not belongs_to_group(bridge, module)
                    or list(registry.PrintedParts).count(bridge) != 1
                ):
                    rows.append(
                        {
                            "module": module.Name,
                            "passed": False,
                            "error": "Missing registered shared-clamp servo bridge",
                        }
                    )
                    continue
                bridge_in_module = placed_shape(
                    shapes[bridge.Name], module.getGlobalPlacement().inverse()
                )
                crop = Part.makeBox(zone_length, 22, 11, V(-zone_length / 2, -11, 1.5))
                head_support = placed_shape(
                    bridge_in_module, canonical_placement.inverse()
                ).common(crop)
            attachment = rail_contact.attachment_check(
                local_rail,
                lower,
                contact_length=length,
                screw_length=screw_length,
                head_face_y=head_face_y,
                head_support=head_support,
                nut_bearing_y=8.0 if shared else 3.25,
                nut_outer_y=11.0 if shared else 5.25,
                frame_contact_y=6.0 if shared else None,
                shared_drive=shared,
            )
            hardware_rows = []
            for suffix, expected, sku in (
                (
                    "RailMountScrew",
                    rail.attachment_screw_shape(screw_length, head_face_y=head_face_y),
                    f"M3X{screw_length:g}_BUTTON_HEAD",
                ),
                (
                    "RailMountNut",
                    rail.nut_shape(bearing_y=8.0 if shared else 3.25),
                    "M3_HEX_NUT",
                ),
            ):
                hardware_name = module.Name + site["prefix"] + suffix
                hardware = registry.Document.getObject(hardware_name)
                if hardware is None or hardware_name not in shapes:
                    hardware_rows.append(
                        {
                            "object": hardware_name,
                            "passed": False,
                            "error": "Missing installed rail hardware",
                        }
                    )
                    continue
                in_module = placed_shape(
                    shapes[hardware_name], module.getGlobalPlacement().inverse()
                )
                comparison = geometry_comparison(
                    in_module, placed_shape(expected, canonical_placement)
                )
                binding_ok = (
                    hardware.getParentGeoFeatureGroup() == module
                    and list(registry.RailLocks).count(hardware) == 1
                    and list(registry.HardwareParts).count(hardware) == 1
                )
                sku_ok = getattr(hardware, "HardwareSKU", None) == sku
                hardware_rows.append(
                    {
                        "object": hardware_name,
                        "source_comparison": comparison,
                        "binding_matches": binding_ok,
                        "sku_matches": sku_ok,
                        "passed": binding_ok
                        and sku_ok
                        and comparison_passed(comparison, TOL),
                    }
                )
            rows.append(
                {
                    "module": module.Name,
                    "part": name,
                    "attachment_prefix": site["prefix"],
                    "attachment_local_x_mm": site["x_offset"],
                    "attachment_side": site["side"],
                    "shared_servo_bridge_clamp": shared,
                    "attachment_axis_x_mm": position.x,
                    "supported_slot_position": position_check,
                    "centred_yz": centred,
                    "rail_overlap_mm3": overlap,
                    "saved_lower_mount_attachment": attachment,
                    "paired_spine_support": paired_support,
                    "installed_hardware": hardware_rows,
                    "passed": belongs_to_group(part, module)
                    and position_check["passed"]
                    and centred
                    and lower.Volume > TOL
                    and overlap < TOL
                    and attachment["passed"]
                    and (paired_support is None or paired_support["passed"])
                    and all(row["passed"] for row in hardware_rows),
                }
            )
    return rows


def rail_check(registry, shapes):
    objects = list(registry.RailSegments)
    rows = []
    for obj in objects:
        actual = local_shape(obj)
        comparison = geometry_comparison(actual, rail.rail_shape())
        bounds = actual.BoundBox
        base_witness, base_region = _independent_base_witnesses()
        missing_base = abs(base_witness.cut(actual).Volume)
        extra_base = abs(actual.common(base_region).cut(base_witness).Volume)
        wings = []
        for x in (-140, 0, 140):
            pad = _literal_plate(x, 14, 32, 2)
            margin = min(
                pad.BoundBox.XMin - bounds.XMin, bounds.XMax - pad.BoundBox.XMax
            )
            missing = abs(pad.cut(actual).Volume)
            wings.append(
                {
                    "centre_x_mm": x,
                    "nearest_rail_end_margin_mm": margin,
                    "missing_pad_material_mm3": missing,
                    "passed": margin >= -TOL and missing < TOL,
                }
            )
        flex = rail_contact.flex_relief_check(actual)
        wall_sections = _independent_wall_top_sections(actual)
        slot_sections = _independent_slot_sections(actual)
        mounts = _saved_mounts(registry, shapes, obj, actual)
        tape_contract_matches = _contract_matches(
            obj, "TapeAttachmentContract", rail.tape_attachment_contract()
        )
        rows.append(
            {
                "object": obj.Name,
                "source_comparison": comparison,
                "size_mm": [bounds.XLength, bounds.YLength, bounds.ZLength],
                "missing_unbroken_base_witness_mm3": missing_base,
                "extra_base_material_mm3": extra_base,
                "independent_base_witness_scope": "Complete literal300x6x1.5mm base with1mm planar end chamfers, plus three14x32x1.5mm tape wings with2mm planar corners atX=-140,0,140mm. Both missing and excess underside material are checked independently of the generator.",
                "open_wall_spans": flex,
                "independent_wall_top_sections": wall_sections,
                "independent_slot_geometry": slot_sections,
                "tape_wings": wings,
                "tape_attachment_contract_matches": tape_contract_matches,
                "installed_mounts": mounts,
                "single_valid_solid": actual.isValid() and len(actual.Solids) == 1,
                "passed": actual.isValid()
                and len(actual.Solids) == 1
                and comparison_passed(comparison, TOL)
                and abs(bounds.XLength - 300) < TOL
                and missing_base < TOL
                and extra_base < TOL
                and len(mounts) == 5
                and flex["passed"]
                and wall_sections["passed"]
                and slot_sections["passed"]
                and tape_contract_matches
                and all(row["passed"] for row in wings + mounts),
            }
        )
    doc = registry.Document
    integral = saved_integral_mount_checks(doc, registry)
    annotations = []
    for obj in (
        list(registry.Modules)
        + objects
        + [doc.getObject("RailFitSample"), doc.getObject("MountFitSample")]
    ):
        contact_length = next(
            (
                length
                for _, parent, _, _, length in MOUNT_BINDINGS
                if obj is not None and parent == obj.Name
            ),
            16.0,
        )
        contract_length = (
            50.0
            if obj is not None and obj.Name in ("RailFitSample", "MountFitSample")
            else 300.0
        )
        annotations.append(
            {
                "object": obj.Name if obj else "missing_coupon",
                "matches_current_attachment_contract": _contract_matches(
                    obj,
                    "RailAttachmentContract",
                    rail.attachment_contract(
                        contact_length,
                        length=contract_length,
                        shared_drive=obj is not None
                        and obj.Name == "MainPropulsionModule",
                    ),
                ),
            }
        )
    tapes, tape_positions = [], []
    for obj in registry.TapeReferences:
        if len(objects) != 1:
            tapes.append({"object": obj.Name, "passed": False})
            continue
        inverse = objects[0].getGlobalPlacement().inverse()
        shape = placed_shape(shapes[obj.Name], inverse)
        bounds = shape.BoundBox
        inner = min(abs(bounds.YMin), abs(bounds.YMax))
        side = -1 if bounds.Center.y < 0 else 1
        station = min(rail.PAD_CENTRES, key=lambda x: abs(x - bounds.Center.x))
        tape_positions.append((round(bounds.Center.x, 6), side))
        comparison = geometry_comparison(shape, rail.tape_shape(station, side))
        overlap = intersection_volume(shape, local_shape(objects[0]))
        tapes.append(
            {
                "object": obj.Name,
                "centre_x_mm": bounds.Center.x,
                "minimum_z_mm": bounds.ZMin,
                "inner_edge_abs_y_mm": inner,
                "source_comparison": comparison,
                "rail_overlap_mm3": overlap,
                "passed": bounds.ZMin >= -TOL
                and inner >= 7.8 - TOL
                and comparison_passed(comparison, TOL)
                and overlap < TOL,
            }
        )
    module_inventory = sorted(module.Name for module in registry.Modules) == sorted(
        parent for _, parent, _, _, _ in MOUNT_BINDINGS
    )
    expected_lock_names = sorted(
        parent + site["prefix"] + suffix
        for _, parent, _, offset, _ in MOUNT_BINDINGS
        for site in attachment_sites(parent, offset)
        for suffix in ("RailMountScrew", "RailMountNut")
    )
    lock_inventory = sorted(
        obj.Name for obj in registry.RailLocks
    ) == expected_lock_names and all(
        obj is doc.getObject(obj.Name) for obj in registry.RailLocks
    )
    tape_inventory = (
        sorted(tape_positions)
        == sorted((x, sign) for x in (-140, 0, 140) for sign in (-1, 1))
        and len({row["object"] for row in tapes}) == 6
    )
    return {
        "rail_count": len(objects),
        "module_inventory_matches": module_inventory,
        "rail_lock_inventory_matches": lock_inventory,
        "tape_inventory_matches": tape_inventory,
        "rails": rows,
        "saved_integral_mounts": integral,
        "native_attachment_annotations": annotations,
        "tape_over_wing_checks": tapes,
        "tape_station_alignment": tape_station_alignment(
            objects[0], registry.Modules, registry.TapeReferences, shapes
        )
        if len(objects) == 1
        else None,
        "scope": "Saved solids, actual poses, registry and nominal local contact only. M3 friction clamping, base and tape geometry do not qualify load capacity, creep, physical fits, tool access or bonded curvature.",
        "passed": len(objects) == 1
        and len(rows) == 1
        and len(tapes) == 6
        and module_inventory
        and lock_inventory
        and tape_inventory
        and len(integral) == 4
        and all(row["passed"] for row in integral + rows + tapes)
        and all(row["matches_current_attachment_contract"] for row in annotations),
    }
