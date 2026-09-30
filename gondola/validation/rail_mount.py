"""Saved side-slot rail, integral U saddles and recessed M3 hardware checks."""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import placed_shape
from gondola.parts import equipment_mounts, propulsion, rail
from gondola.print_export import geometry_comparison

from .evidence import comparison_passed
from .geometry import belongs_to_group, intersection_volume, local_shape

V = App.Vector
TOL = 1e-5
_BINDINGS = (
    ("BatteryMount", "BatteryEquipmentModule", "battery", 0.0, 16.0),
    ("ElectronicsMount", "ElectronicsEquipmentModule", "electronics", 0.0, 16.0),
    ("AccessoryMount", "AccessoryEquipmentModule", "accessory", 0.0, 16.0),
    ("PropulsionFixedFrame", "MainPropulsionModule", None, 17.0, 24.0),
)


def _contract_matches(obj, property_name, expected):
    try:
        return json.loads(getattr(obj, property_name)) == json.loads(
            json.dumps(expected)
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _offset(module):
    return next(
        (offset for _, parent, _, offset, _ in _BINDINGS if parent == module.Name), 0
    )


def _attachment_sites(module_name, offset=0):
    """Literal independent site inventory; do not infer a missing second clamp."""
    if module_name == "MainPropulsionModule":
        return (
            {"prefix": "", "x_offset": 17.0, "side": 1},
            {"prefix": "Opposite", "x_offset": -17.0, "side": -1},
        )
    return ({"prefix": "", "x_offset": offset, "side": 1},)


def _site_placement(site):
    return App.Placement(
        V(site["x_offset"], 0, 0),
        App.Rotation(V(0, 0, 1), 180 if site["side"] < 0 else 0),
    )


def _foot_placement(module, inverse, site=None):
    if site is None:
        site = _attachment_sites(module.Name, _offset(module))[0]
    return inverse.multiply(module.getGlobalPlacement()).multiply(_site_placement(site))


def tape_station_alignment(rail_object, modules, tapes, shapes):
    """Saved attachment-axis proximity, not an adhesion or support pass flag."""
    inverse = rail_object.getGlobalPlacement().inverse()
    tape_bounds = [
        (obj.Name, placed_shape(shapes[obj.Name], inverse).BoundBox) for obj in tapes
    ]
    rows = []
    for module in modules:
        for site in _attachment_sites(module.Name, _offset(module)):
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


def _literal_protected_mount(length=16, *, shared=False):
    """Independent U saddle, direct-web nut window and optional head recess."""
    leg = Part.makeBox(length, 4, 10.3, V(-length / 2, -5.25, 2.2))
    roof = Part.makeBox(length, 9.2, 2, V(-length / 2, -5.25, 10.5))
    guard = Part.makeBox(length, 2.5, 10.3, V(-length / 2, 1.45, 2.2))
    radius = 5.9 / math.sqrt(3)
    vertices = [
        V(
            radius * math.cos(math.radians(a)),
            1.35,
            7 + radius * math.sin(math.radians(a)),
        )
        for a in range(0, 360, 60)
    ]
    nut_window = Part.Face(Part.makePolygon(vertices + vertices[:1])).extrude(
        V(0, 2.7, 0)
    )
    result = (
        leg.fuse(roof)
        .fuse(guard)
        .cut(nut_window)
        .cut(Part.makeCylinder(1.7, 11.2, V(0, -6.25, 7), V(0, 1, 0)))
    )
    if not shared:
        result = result.cut(Part.makeCylinder(3.2, 2.1, V(0, -5.35, 7), V(0, 1, 0)))
    return result.removeSplitter()


def _lower_crop(offset=0, length=16):
    return Part.makeBox(length, 9.2, 10.3, V(offset - length / 2, -5.25, 2.2))


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
    """Full literal 300x5x1.5mm strip and three14x32mm wings, including chamfers."""
    retained = _literal_plate(0, 300, 5, 1)
    for centre in (-136, 0, 136):
        retained = retained.fuse(_literal_plate(centre, 14, 32, 2))
    region = Part.makeBox(302, 34, 1.5, V(-151, -17, 0))
    return retained.removeSplitter(), region


def _independent_wall_top_sections(shape):
    """Literal nine wall intervals above the slots, independent of generator data."""
    line = Part.makeLine(V(-151, 0, 9.5), V(151, 0, 9.5))
    actual = sorted(
        (edge.BoundBox.XMin, edge.BoundBox.XMax) for edge in shape.common(line).Edges
    )
    expected = (
        (-149, -123),
        (-115, -89),
        (-81, -55),
        (-47, -21),
        (-13, 13),
        (21, 47),
        (55, 81),
        (89, 115),
        (123, 149),
    )
    return {
        "sample_yz_mm": [0, 9.5],
        "actual_wall_intervals_x_mm": actual,
        "expected_wall_intervals_x_mm": expected,
        "passed": len(actual) == len(expected)
        and all(
            abs(value - target) < TOL
            for pair, reference in zip(actual, expected)
            for value, target in zip(pair, reference)
        ),
    }


def saved_integral_mount_checks(doc, registry):
    printed, equipment = list(registry.PrintedParts), list(registry.EquipmentMounts)
    expected = [name for name, _, kind, _, _ in _BINDINGS if kind is not None]
    inventory = sorted(obj.Name for obj in equipment) == sorted(expected) and all(
        obj == doc.getObject(obj.Name) for obj in equipment
    )
    rows = []
    for name, parent_name, kind, offset, length in _BINDINGS:
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
        sites = _attachment_sites(parent_name, offset)
        crops = [
            placed_shape(_lower_crop(0, length), _site_placement(site))
            for site in sites
        ]
        literals = [
            placed_shape(
                _literal_protected_mount(length, shared=kind is None),
                _site_placement(site),
            )
            for site in sites
        ]
        crop, literal = Part.makeCompound(crops), Part.makeCompound(literals)
        lower, source_lower = (
            geometry_comparison(actual.common(crop), literal),
            geometry_comparison(source.common(crop), literal),
        )
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
        for part, parent, kind, offset, length in _BINDINGS
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
        for site in _attachment_sites(module.Name, offset):
            site_placement = _site_placement(site)
            foot_placement = _foot_placement(module, inverse, site)
            position = foot_placement.Base
            position_check = rail.attachment_position_check(
                position.x, contact_length=length
            )
            centred = abs(position.y) < TOL and abs(position.z) < TOL
            printed_in_rail = placed_shape(shapes[name], inverse)
            overlap = intersection_volume(printed_in_rail, rail_shape)
            canonical_part = placed_shape(local_shape(part), site_placement.inverse())
            lower = canonical_part.common(_lower_crop(0, length))
            local_rail = placed_shape(rail_shape, foot_placement.inverse())
            shared = module.Name == "MainPropulsionModule"
            screw_length, head_face_y = (12.0, -7.75) if shared else (8.0, -3.25)
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
                crop = Part.makeBox(length, 4.5, 10.3, V(-length / 2, -9.75, 2.2))
                head_support = placed_shape(
                    bridge_in_module, site_placement.inverse()
                ).common(crop)
            attachment = rail.attachment_check(
                local_rail,
                lower,
                contact_length=length,
                screw_length=screw_length,
                head_face_y=head_face_y,
                head_support=head_support,
            )
            hardware_rows = []
            for suffix, expected, sku in (
                (
                    "RailMountScrew",
                    rail.attachment_screw_shape(screw_length, head_face_y=head_face_y),
                    f"M3X{screw_length:g}_BUTTON_HEAD",
                ),
                ("RailMountNut", rail.nut_shape(), "M3_HEX_NUT"),
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
                    in_module, placed_shape(expected, site_placement)
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
                    "installed_hardware": hardware_rows,
                    "passed": belongs_to_group(part, module)
                    and position_check["passed"]
                    and centred
                    and lower.Volume > TOL
                    and overlap < TOL
                    and attachment["passed"]
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
        for x in (-136, 0, 136):
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
        flex = rail.flex_relief_check(actual)
        wall_sections = _independent_wall_top_sections(actual)
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
                "independent_base_witness_scope": "Complete literal300x5x1.5mm base with1mm planar end chamfers, plus three14x32x1.5mm tape wings with2mm planar corners atX=-136,0,136mm. Both missing and excess underside material are checked independently of the generator.",
                "open_wall_spans": flex,
                "independent_wall_top_sections": wall_sections,
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
                for _, parent, _, _, length in _BINDINGS
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
        parent for _, parent, _, _, _ in _BINDINGS
    )
    expected_lock_names = sorted(
        parent + site["prefix"] + suffix
        for _, parent, _, offset, _ in _BINDINGS
        for site in _attachment_sites(parent, offset)
        for suffix in ("RailMountScrew", "RailMountNut")
    )
    lock_inventory = sorted(
        obj.Name for obj in registry.RailLocks
    ) == expected_lock_names and all(
        obj is doc.getObject(obj.Name) for obj in registry.RailLocks
    )
    tape_inventory = (
        sorted(tape_positions)
        == sorted((x, sign) for x in (-136, 0, 136) for sign in (-1, 1))
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
