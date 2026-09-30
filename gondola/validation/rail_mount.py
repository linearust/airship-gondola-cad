"""Saved side-slot rail, integral L seats and installed M2 hardware checks."""

import json

import FreeCAD as App
import Part

from gondola.cad import placed_shape, translated_shape
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
    ("PropulsionFixedFrame", "MainPropulsionModule", None, 12.5, 32.0),
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


def _foot_placement(module, inverse):
    return inverse.multiply(module.getGlobalPlacement()).multiply(
        App.Placement(V(_offset(module), 0, 0), App.Rotation())
    )


def tape_station_alignment(rail_object, modules, tapes, shapes):
    """Saved attachment-axis proximity, not an adhesion or support pass flag."""
    inverse = rail_object.getGlobalPlacement().inverse()
    tape_bounds = [
        (obj.Name, placed_shape(shapes[obj.Name], inverse).BoundBox) for obj in tapes
    ]
    rows = []
    for module in modules:
        x = _foot_placement(module, inverse).Base.x
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
            name, bounds = min(candidates, key=lambda item: abs(item[1].Center.x - x))
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
            {"module": module.Name, "station_x_mm": x, "nearest_tapes": nearest}
        )
    return {
        "modules": rows,
        "scope": "Saved tape/attachment positions in the rail frame only. Under-base adhesive is unmodeled. Tape proximity neither proves adhesion/load capacity nor prohibits other supported slot positions; qualify retention and routing after relocation.",
    }


def _literal_protected_mount(length=16):
    """Independent16mm L seat, horizontal M2 bore and unchanged print datums."""
    leg = Part.makeBox(length, 2.5, 9.2, V(-length / 2, -3.75, 2.2))
    roof = Part.makeBox(length, 5, 1.9, V(-length / 2, -3.75, 9.5))
    return (
        leg.fuse(roof)
        .cut(Part.makeCylinder(1.2, 7, V(0, -4.75, 6.5), V(0, 1, 0)))
        .removeSplitter()
    )


def _lower_crop(offset=0, length=16):
    return Part.makeBox(length, 5, 9.2, V(offset - length / 2, -3.75, 2.2))


def _independent_base_witnesses():
    """Literal 6-to-4.5 mm smooth waists; preserve the entire 1.5 mm section.

    Omit only the final 3 mm at each rounded rail end. These independent
    witnesses must not inherit a defective profile from the rail generator.
    """
    reliefs = []
    for first, last in (
        (-128, -111),
        (-89, -81),
        (-59, -51),
        (-31, -25),
        (25, 31),
        (51, 59),
        (81, 89),
        (111, 128),
    ):
        middle, sixth = (first + last) / 2, (last - first) / 6
        for sign in (-1, 1):
            edges = []
            for poles in (
                (
                    (first, 3),
                    (first + sixth, 3),
                    (middle - sixth, 2.25),
                    (middle, 2.25),
                ),
                (
                    (middle, 2.25),
                    (middle + sixth, 2.25),
                    (last - sixth, 3),
                    (last, 3),
                ),
            ):
                curve = Part.BezierCurve()
                curve.setPoles([V(x, sign * y, 0) for x, y in poles])
                edges.append(curve.toShape())
            edges.append(Part.makeLine(V(last, sign * 3, 0), V(first, sign * 3, 0)))
            reliefs.append(Part.Face(Part.Wire(edges)).extrude(V(0, 0, 1.5)))
    removed = Part.makeCompound(reliefs)
    retained = Part.makeBox(294, 6, 1.5, V(-147, -3, 0)).cut(removed)
    return retained, removed


def _independent_wall_top_sections(shape):
    """Literal nine wall intervals above the slots, independent of generator data."""
    line = Part.makeLine(V(-151, 0, 8.5), V(151, 0, 8.5))
    actual = sorted(
        (edge.BoundBox.XMin, edge.BoundBox.XMax) for edge in shape.common(line).Edges
    )
    expected = (
        (-150, -128),
        (-111, -89),
        (-81, -59),
        (-51, -31),
        (-25, 25),
        (31, 51),
        (59, 81),
        (89, 111),
        (128, 150),
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
        crop, literal = (
            _lower_crop(offset, length),
            translated_shape(_literal_protected_mount(length), x=offset),
        )
        lower, source_lower = (
            geometry_comparison(actual.common(crop), literal),
            geometry_comparison(source.common(crop), literal),
        )
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
                    "error": "Missing integral L solid",
                }
            )
            continue
        foot_placement = _foot_placement(module, inverse)
        position = foot_placement.Base
        position_check = rail.attachment_position_check(
            position.x, contact_length=length
        )
        centred = abs(position.y) < TOL and abs(position.z) < TOL
        printed_in_rail = placed_shape(shapes[name], inverse)
        overlap = intersection_volume(printed_in_rail, rail_shape)
        lower = translated_shape(
            local_shape(part).common(_lower_crop(offset, length)), x=-offset
        )
        local_rail = placed_shape(rail_shape, foot_placement.inverse())
        attachment = rail.attachment_check(local_rail, lower, contact_length=length)
        hardware_rows = []
        for suffix, expected, sku in (
            ("RailMountScrew", rail.attachment_screw_shape(), "M2X8_BUTTON_HEAD"),
            ("RailMountNut", rail.nut_shape(), "M2_HEX_NUT"),
        ):
            hardware_name = module.Name + suffix
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
                in_module, translated_shape(expected, x=offset)
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
        base_witness, waist_reliefs = _independent_base_witnesses()
        missing_base = abs(base_witness.cut(actual).Volume)
        filled_reliefs = abs(waist_reliefs.common(actual).Volume)
        wings = []
        for x in (-140, 0, 140):
            pad = rail.rounded_plate(x)
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
                "filled_flexure_relief_mm3": filled_reliefs,
                "independent_base_witness_scope": "Literal 6-to-4.5 mm cubic waist profiles across all eight wall gaps and the full 1.5 mm base thickness within X +/-147 mm; rounded end tips are covered by the separate full-shape comparison.",
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
                and filled_reliefs < TOL
                and len(mounts) == 4
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
                    rail.attachment_contract(contact_length, length=contract_length),
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
    tape_inventory = (
        sorted(tape_positions)
        == sorted((x, sign) for x in (-140, 0, 140) for sign in (-1, 1))
        and len({row["object"] for row in tapes}) == 6
    )
    return {
        "rail_count": len(objects),
        "module_inventory_matches": module_inventory,
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
        "scope": "Saved solids, actual poses, registry and nominal local contact only. M2 friction clamping, base and tape geometry do not qualify load capacity, creep, physical fits, tool access or bonded curvature.",
        "passed": len(objects) == 1
        and len(rows) == 1
        and len(tapes) == 6
        and module_inventory
        and tape_inventory
        and len(integral) == 4
        and all(row["passed"] for row in integral + rows + tapes)
        and all(row["matches_current_attachment_contract"] for row in annotations),
    }
