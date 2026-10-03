"""Read-only rail- or carrier-mounted optical evidence and clearance audit.

Mechanism and connector-access checks sample five pitch attitudes at the saved attachment position. The separate broad
optical cone conservatively contains the external field over the entire angle
range; neither check qualifies physical fit, friction, cables or gravity trim.
"""

import itertools
import json
import math
from dataclasses import asdict
from functools import partial

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, world_shape
from gondola.contracts.design import MODULE_STATIONS
from gondola.contracts.optical_attachment import resolve_mount_mode
from gondola.contracts.optical_sensors import SENSOR_PROFILES, get_sensor_profile
from gondola.parts import (
    mounting_plate,
    optical_interface,
    optical_mount,
    optical_sensor,
    rail,
    slot_bearing,
    wiring_reserves,
)
from gondola.print_export import geometry_comparison

from .evidence import comparison_passed
from .geometry import intersection_volume, local_shape, translation_sweep
from .optical_envelopes import PITCH_SAMPLE_ANGLES, external_field_bound
from .optical_service import pitch_disassembly_check, pitch_tool_check, pitch_tool_shape
from .wiring import RESERVES, collision_hits, measure_clearances, named_gap_checks

TOL = 1e-5
V = App.Vector


def _matches(first, second):
    result = geometry_comparison(first, second)
    return result, comparison_passed(result, TOL)


def _same_placement(first, second):
    return (first.Base - second.Base).Length < TOL and first.Rotation.isSame(
        second.Rotation, TOL
    )


def _json_equal(first, second):
    try:
        return json.loads(str(first)) == json.loads(str(second))
    except (TypeError, ValueError):
        return False


def _native_structure_check(doc):
    """Reject incomplete native assemblies before any geometry probe or mutation."""
    required = {
        "DesignRegistry": (
            "PrintedParts",
            "HardwareParts",
            "ReferenceParts",
            "ClearanceVolumes",
            "FitCoupons",
            "OpticalMountParts",
            "TapeReferences",
            "RailLocks",
            "Modules",
            "EquipmentMounts",
        ),
        "OpticalFlowModule": (
            "OpticalMountContract",
            "OpticalInterfaceContract",
            "OpticalAttachmentMode",
            "HoldingTorqueVerified",
            "SelfLevelling",
            "OpticalFitVerified",
            "SensorModel",
            "SupportedSensorModels",
        ),
        "OpticalPitchStage": ("Pitch", "MinimumAngle", "MaximumAngle"),
    }
    required.update(
        {
            name: ("Shape", "SensorModel", "SensorProfileContract")
            for name in (
                "ModuleMTF02PEnvelope",
                "MTF02POpticalClearanceReserve",
                "MTF02PConnectorReserve",
            )
        }
    )
    errors = []
    for name, properties in required.items():
        obj = doc.getObject(name)
        if obj is None:
            errors.append({"object": name, "error": "missing object"})
        else:
            missing = [key for key in properties if key not in obj.PropertiesList]
            if missing:
                errors.append({"object": name, "missing_properties": missing})
    group = doc.getObject("OpticalFlowModule")
    try:
        mode = resolve_mount_mode(str(group.OpticalAttachmentMode))
    except (AttributeError, ValueError):
        mode = None
        errors.append({"error": "Missing or invalid optical attachment mode"})
    parents = {
        "OpticalFlowModule": (
            {None} if mode == "rail" else set(optical_interface.SUPPORTED_HOSTS)
        ),
        "OpticalPitchStage": {"OpticalFlowModule"},
    }
    for name, allowed in parents.items():
        obj = doc.getObject(name)
        if obj is None:
            continue
        parent = obj.getParentGeoFeatureGroup()
        parent_name = parent.Name if parent is not None else None
        if parent_name not in allowed:
            errors.append(
                {
                    "object": name,
                    "parent": parent_name,
                    "expected_parents": list(allowed),
                }
            )
    if group is not None and mode == "carrier":
        parent = group.getParentGeoFeatureGroup()
        if getattr(group, "CarrierHostName", None) != (parent.Name if parent else None):
            errors.append(
                {"error": "Optical carrier metadata differs from native parent"}
            )
        if str(getattr(group, "MountSide", "")) not in optical_interface.SIDES:
            errors.append({"error": "Unknown optical carrier side"})
        if "RailPositionX" in group.PropertiesList:
            errors.append(
                {"error": "Carrier optical attachment has an independent rail control"}
            )
    elif group is not None and mode == "rail":
        forbidden = {"CarrierHostName", "MountSide"}.intersection(group.PropertiesList)
        required_controls = {
            "RailPositionX",
            "RailAttachmentOffsetX",
            "RailAttachmentOffsetsX",
            "RailContactLength",
            "RailAttachmentContract",
            "ModulePlacementContract",
        }
        missing = sorted(required_controls.difference(group.PropertiesList))
        if forbidden or missing:
            errors.append(
                {
                    "object": group.Name,
                    "forbidden_properties": sorted(forbidden),
                    "missing_properties": missing,
                }
            )
    if (
        doc.getObject("OpticalRollStage") is not None
        or doc.getObject("OpticalRollBracket") is not None
    ):
        errors.append(
            {"error": "Obsolete roll mechanism remains in single-axis assembly"}
        )
    return {"errors": errors, "passed": not errors}


def _rail_native_controls(group, registry):
    """Bind adjustable rail X to a supported canonical station and native pose."""
    from .baseline import module_attachment_pose

    station = next(
        (item for item in MODULE_STATIONS if item.object_name == group.Name), None
    )
    if station is None:
        return {
            "mode": "rail",
            "passed": False,
            "error": "No selected optical rail station",
        }
    pose = module_attachment_pose(station, group)
    expected = (
        App.Placement(
            V(float(group.RailPositionX), 0, 0),
            App.Rotation(V(0, 0, 1), station.yaw_deg),
        )
        if pose.get("passed")
        else None
    )
    contracts = _json_equal(
        group.ModulePlacementContract, json.dumps(asdict(station))
    ) and _json_equal(
        group.RailAttachmentContract, json.dumps(rail.attachment_contract(16.0))
    )
    return {
        "mode": "rail",
        "supported_attachment": pose,
        "passed": pose.get("passed", False)
        and contracts
        and list(registry.Modules).count(group) == 1
        and group.getParentGeoFeatureGroup() is None
        and _same_placement(group.Placement, expected)
        and [
            (path.lstrip("."), expression)
            for path, expression in group.ExpressionEngine
        ]
        == [("Placement.Base.x", "RailPositionX")],
    }


def _source_evidence(doc):
    """Bind saved shapes, placements, metadata and registries to source factories."""
    structure = _native_structure_check(doc)
    if not structure["passed"]:
        return {"native_structure": structure, "passed": False}
    selected_profile = get_sensor_profile()
    selected_model_matches = (
        str(doc.OpticalFlowModule.SensorModel) == selected_profile.key
    )
    if not selected_model_matches:
        return {
            "native_structure": structure,
            "saved_sensor_model": str(doc.OpticalFlowModule.SensorModel),
            "source_selected_sensor_model": selected_profile.key,
            "selected_model_matches_source": False,
            "passed": False,
        }
    expected_doc = App.newDocument("OpticalEvidenceReference")
    rows = []
    try:
        group = doc.OpticalFlowModule
        mode = resolve_mount_mode(str(group.OpticalAttachmentMode))
        host = (
            expected_doc.addObject("App::Part", group.CarrierHostName)
            if mode == "carrier"
            else None
        )
        kit = optical_mount.build_optical_mount(
            expected_doc,
            host,
            str(group.MountSide)
            if mode == "carrier"
            else optical_interface.DEFAULT_SIDE,
            mode=mode,
        )
        if mode == "rail":
            kit["hardware"] += rail.build_attachment_hardware(
                expected_doc, kit["group"], "OpticalFlowModule"
            )
        refs, reserves = optical_sensor.build_sensor(
            expected_doc, kit["pitch_stage"], selected_profile
        )
        expected_doc.recompute()
        registry = doc.DesignRegistry
        inventory = {}
        for category, objects in (
            ("PrintedParts", kit["printed"]),
            ("HardwareParts", kit["hardware"]),
            ("ReferenceParts", refs),
            ("ClearanceVolumes", reserves),
        ):
            actual_names = [
                obj.Name
                for obj in getattr(registry, category)
                if belongs_to_group(obj, doc.OpticalFlowModule)
            ]
            inventory[category] = sorted(actual_names) == sorted(
                obj.Name for obj in objects
            )
            for expected in objects:
                actual = doc.getObject(expected.Name)
                if actual is None:
                    rows.append(
                        {"object": expected.Name, "passed": False, "error": "missing"}
                    )
                    continue
                comparison, geometry_ok = _matches(
                    local_shape(actual), local_shape(expected)
                )
                parent_ok = (
                    actual.getParentGeoFeatureGroup() is not None
                    and actual.getParentGeoFeatureGroup().Name
                    == expected.getParentGeoFeatureGroup().Name
                )
                metadata = {}
                metadata_names = {
                    "OpticalMountContract",
                    "OpticalInterfaceContract",
                    "MountingEvidence",
                    "ConnectorEvidence",
                    "WiringContract",
                    "SourceURL",
                    "ProductSource",
                    "DimensionDrawingSource",
                    "FirmwareOrientationSource",
                    "HardwareSKU",
                    "MaterialSelection",
                    "ThreadStandard",
                    "ThreadGeometry",
                    "Role",
                    "ShapeModelNotes",
                    "PrintPart",
                    "ListedMassGrams",
                    "OpticalDirection",
                    "PlannedConnectorDirection",
                    "PublishedOpticalFlowFOV",
                    "PublishedToFFOV",
                    "ReservedOpticalDistance",
                    "HoldingTorqueVerified",
                    "OpticalFitVerified",
                    "MountingStackVerified",
                    "PCBHeightMeasured",
                    "InstalledConnectorFitVerified",
                    "InstalledOpticalFieldVerified",
                    "OpticalOriginsMeasured",
                }
                # Sensor profiles carry source, dimensions and qualification scope.
                # Bind every factory-created design property, not a stale shortlist.
                metadata_names.update(
                    name
                    for name in expected.PropertiesList
                    if expected.getGroupOfProperty(name) == "Design"
                )
                for name in sorted(metadata_names):
                    if name not in expected.PropertiesList:
                        continue
                    present = name in actual.PropertiesList
                    first, second = getattr(actual, name, None), getattr(expected, name)
                    metadata[name] = present and (
                        first == second
                        or (
                            name.endswith(("Contract", "Evidence"))
                            and _json_equal(first, second)
                        )
                    )
                placement_ok = _same_placement(actual.Placement, expected.Placement)
                registered = actual in getattr(registry, category)
                exclusive = all(
                    actual not in getattr(registry, other)
                    for other in (
                        "PrintedParts",
                        "HardwareParts",
                        "ReferenceParts",
                        "ClearanceVolumes",
                        "FitCoupons",
                    )
                    if other != category
                )
                rows.append(
                    {
                        "object": actual.Name,
                        "source_comparison": comparison,
                        "local_placement_matches": placement_ok,
                        "parent_matches": parent_ok,
                        "registered_exclusively": registered and exclusive,
                        "metadata_matches": metadata,
                        "passed": geometry_ok
                        and placement_ok
                        and parent_ok
                        and registered
                        and exclusive
                        and all(metadata.values()),
                    }
                )
        group = doc.OpticalFlowModule
        if mode == "carrier":
            attachment_controls = {
                "mode": mode,
                "passed": group.getParentGeoFeatureGroup() in registry.Modules
                and group.getParentGeoFeatureGroup().Name == group.CarrierHostName
                and group not in registry.Modules
                and "RailPositionX" not in group.PropertiesList
                and _same_placement(group.Placement, kit["group"].Placement)
                and list(group.ExpressionEngine) == list(kit["group"].ExpressionEngine),
            }
        else:
            attachment_controls = _rail_native_controls(group, registry)
        module_ok = (
            _json_equal(group.OpticalMountContract, kit["group"].OpticalMountContract)
            and _json_equal(
                group.OpticalInterfaceContract, kit["group"].OpticalInterfaceContract
            )
            and str(group.SensorModel) == selected_profile.key
            and list(group.SupportedSensorModels) == list(SENSOR_PROFILES)
            and not group.HoldingTorqueVerified
            and not group.SelfLevelling
            and not group.OpticalFitVerified
            and attachment_controls["passed"]
            and sorted(
                obj.Name for obj in registry.RailLocks if belongs_to_group(obj, group)
            )
            == (
                ["OpticalFlowModuleRailMountNut", "OpticalFlowModuleRailMountScrew"]
                if mode == "rail"
                else []
            )
            and {obj.Name for obj in registry.OpticalMountParts}
            == {obj.Name for obj in kit["printed"]}
        )
        controls = []
        for name, key in (("OpticalPitchStage", "Pitch"),):
            actual, expected = doc.getObject(name), expected_doc.getObject(name)
            valid = (
                actual.getParentGeoFeatureGroup().Name
                == expected.getParentGeoFeatureGroup().Name
                and (actual.Placement.Base - expected.Placement.Base).Length < TOL
                and actual.MinimumAngle.Value == -optical_mount.ANGLE_LIMIT_DEG
                and actual.MaximumAngle.Value == optical_mount.ANGLE_LIMIT_DEG
                and list(actual.ExpressionEngine) == list(expected.ExpressionEngine)
                and key in actual.PropertiesList
            )
            controls.append({"stage": name, "passed": valid})
        return {
            "native_structure": structure,
            "saved_sensor_model": str(group.SensorModel),
            "source_selected_sensor_model": selected_profile.key,
            "selected_model_matches_source": selected_model_matches,
            "objects": rows,
            "registered_kit_inventory_matches_factory": inventory,
            "module_contract_and_registry": module_ok,
            "native_controls": controls,
            "attachment_controls": attachment_controls,
            "passed": module_ok
            and all(inventory.values())
            and all(row["passed"] for row in rows + controls),
        }
    finally:
        App.closeDocument(expected_doc.Name)


def _corners(shape):
    b = shape.BoundBox
    return [
        V(x, y, z)
        for x, y, z in itertools.product(
            (b.XMin, b.XMax), (b.YMin, b.YMax), (b.ZMin, b.ZMax)
        )
    ]


def _placement_checks(doc, physical, kit, *, profile=None):
    profile = profile or optical_sensor.profile_for_document(doc)
    group = doc.OpticalFlowModule
    validation_cache = {}
    find_hits = partial(
        collision_hits, tolerance=TOL, validation_cache=validation_cache
    )
    fixed = {obj.Name: world_shape(obj) for obj in physical if obj not in kit}
    rotor = {
        obj.Name: world_shape(obj)
        for obj in doc.DesignRegistry.ClearanceVolumes
        if "Sweep" in obj.Name and ("Port" in obj.Name or "Starboard" in obj.Name)
    }
    rotor_complete = set(rotor) == {"PortSweepBound", "StarboardSweepBound"}
    reservations = {
        obj.Name: world_shape(obj)
        for obj in doc.DesignRegistry.ClearanceVolumes
        if obj.Name not in rotor and not belongs_to_group(obj, group)
    }
    # Required named external reservations cannot disappear from the registry.
    # Own connector and whole-footprint field are design reservations, not lens
    # or installed-plug datums; they are excluded from one another's obstacles.
    # Their possible overlap does not qualify actual connected-harness optics.
    for name in RESERVES:
        if name in ("MTF02PConnectorReserve", "MTF02POpticalClearanceReserve"):
            continue
        if name not in reservations:
            reservations[name] = None
    external = {**fixed, **rotor}
    mode = resolve_mount_mode(str(group.OpticalAttachmentMode))
    tool_reserve = pitch_tool_shape(mode)
    tool_reserve.Placement = group.getGlobalPlacement()
    rows = []
    maximum_depth = -math.inf
    for pitch in PITCH_SAMPLE_ANGLES:
        optical_mount.set_pitch(doc, pitch)
        own = {obj.Name: world_shape(obj) for obj in kit}
        collisions = []
        reserved_hits = []
        for name, shape in own.items():
            collisions += [
                {"moving": name, **hit} for hit in find_hits(shape, external)
            ]
            reserved_hits += [
                {"moving": name, **hit} for hit in find_hits(shape, reservations)
            ]
        for (name, shape), (other, target) in itertools.combinations(own.items(), 2):
            volume = intersection_volume(shape, target)
            if volume > TOL:
                collisions.append(
                    {"moving": name, "object": other, "intersection_mm3": volume}
                )
        obstacles = {
            **external,
            **{
                name: shape
                for name, shape in own.items()
                if name != "ModuleMTF02PEnvelope"
            },
        }
        optical_reserve = world_shape(doc.MTF02POpticalClearanceReserve)
        connector_reserve = world_shape(doc.MTF02PConnectorReserve)
        optic_hits = find_hits(optical_reserve, obstacles)
        connector_hits = find_hits(connector_reserve, obstacles)
        optical_reserve_hits = find_hits(optical_reserve, reservations)
        connector_reserve_gaps = measure_clearances(
            connector_reserve,
            reservations,
            minimum_gap_mm=wiring_reserves.CONNECTOR_SERVICE_GAP_MM,
            tolerance=TOL,
            validation_cache=validation_cache,
        )
        registration_checks = []
        inverse_group = group.getGlobalPlacement().inverse()
        for name, shape in (
            ("body", own["ModuleMTF02PEnvelope"]),
            ("connector", connector_reserve),
            ("pitch_tool", tool_reserve),
        ):
            local = shape.copy()
            local.Placement = inverse_group.multiply(local.Placement)
            bound = optical_interface.registration_bound(local, mode)
            bound.Placement = group.getGlobalPlacement()
            hits = find_hits(bound, external)
            gaps = measure_clearances(
                bound,
                reservations,
                minimum_gap_mm=wiring_reserves.CONNECTOR_SERVICE_GAP_MM
                if name == "connector"
                else 0.0,
                tolerance=TOL,
                validation_cache=validation_cache,
            )
            registration_checks.append(
                {
                    "component": name,
                    "external_obstructions": hits,
                    "reserved_space_clearances": gaps,
                    "passed": not hits and all(row["passed"] for row in gaps),
                }
            )
        neighbour_gaps = named_gap_checks(
            {
                **fixed,
                **own,
                **reservations,
                "MTF02POpticalClearanceReserve": optical_reserve,
                "MTF02PConnectorReserve": connector_reserve,
            },
            wiring_reserves.MINIMUM_NEIGHBOUR_GAPS,
            tolerance=TOL,
            validation_cache=validation_cache,
        )
        pitch_tool = pitch_tool_check(group, {**external, **own, **reservations})
        inverse = doc.OpticalPitchStage.getGlobalPlacement().inverse()
        depth = max(
            inverse.multVec(point).z
            - optical_sensor.SENSOR_BOTTOM_Z
            - profile.optical_origin_min_z_mm
            for shape in obstacles.values()
            for point in _corners(shape)
        )
        maximum_depth = max(maximum_depth, depth)
        control_ok = doc.OpticalPitchStage.Placement.Rotation.isSame(
            App.Rotation(V(0, 1, 0), pitch), TOL
        )
        rows.append(
            {
                "pitch_deg": pitch,
                "physical_collisions": collisions,
                "reserved_space_intrusions": reserved_hits,
                "optical_obstructions": optic_hits,
                "connector_obstructions": connector_hits,
                "optical_reserved_space_intrusions": optical_reserve_hits,
                "connector_reserved_space_clearances": connector_reserve_gaps,
                "neighbour_clearance_buffers": neighbour_gaps,
                "pitch_clamp_tool_access": pitch_tool,
                "assembly_registration_checks": registration_checks,
                "body_forward_extent_mm": depth,
                "native_rotation_matches": control_ok,
                "passed": not collisions
                and not reserved_hits
                and not optic_hits
                and not connector_hits
                and not optical_reserve_hits
                and all(
                    row["passed"] for row in connector_reserve_gaps + neighbour_gaps
                )
                and all(row["passed"] for row in registration_checks)
                and control_ok
                and pitch_tool["passed"]
                and depth <= optical_sensor.OPTICAL_RESERVE_LENGTH_MM + TOL,
            }
        )
    optical_mount.set_pitch(doc, 0)
    bound, dimensions = external_field_bound(group, profile)
    bound_hits = find_hits(bound, external)
    bound_reserve_hits = find_hits(bound, reservations)
    pivot = group.getGlobalPlacement().multVec(V(*optical_mount.pivot_centre(mode)))
    # Norm bounds every forward projection for all pitch angles.
    depth_bound = (
        max(
            (point - pivot).Length
            for shape in {**external, **{o.Name: world_shape(o) for o in kit}}.values()
            for point in _corners(shape)
        )
        + optical_sensor.SENSOR_BOTTOM_Z
        + profile.optical_origin_min_z_mm
    )
    continuous = {
        **dimensions,
        "external_obstructions": bound_hits,
        "external_reserved_space_intrusions": bound_reserve_hits,
        "all_angles_body_depth_upper_bound_mm": depth_bound,
        "method": "Conservative full-angle circular cone with the broad assembly-registration reserve and nominal rail-fit allowance against external parts, complete rotor bounds and named wire/access reservations; norm bound covers modeled-body depth. Printed angular rocking and deformation are unqualified.",
        "passed": not bound_hits
        and not bound_reserve_hits
        and depth_bound <= optical_sensor.OPTICAL_RESERVE_LENGTH_MM + TOL,
    }
    return {
        "attachment_mode": mode,
        "carrier_host": getattr(group, "CarrierHostName", None),
        "carrier_side": str(group.MountSide) if mode == "carrier" else None,
        "pitch_pivot_world_mm": tuple(pivot),
        "sensor_model": profile.key,
        "both_complete_rotor_bounds_present": rotor_complete,
        "sampled_attitudes": rows,
        "maximum_sampled_forward_extent_mm": maximum_depth,
        "continuous_external_optical_bound": continuous,
        "passed": rotor_complete
        and all(row["passed"] for row in rows)
        and continuous["passed"],
    }


def _seated_foot_lift_sweep(shape, distance):
    """Continuously lift the actual locator separately from the backed foot.

    The transverse pitch-ear cylinder otherwise makes the generic sweep use
    one bounding prism, extending the locator's low Z across the whole foot.
    Splitting at the known seating plane retains all actual saved material;
    each component still uses the conservative continuous sweep unchanged.
    """
    if distance <= 0:
        raise ValueError("Optical foot lift must be positive")
    bounds = shape.BoundBox
    below = shape.common(
        Part.makeBox(
            bounds.XLength + 2,
            bounds.YLength + 2,
            max(0, -bounds.ZMin) + 1,
            V(bounds.XMin - 1, bounds.YMin - 1, min(0, bounds.ZMin) - 1),
        )
    )
    above = shape.cut(below)
    pieces, methods = [], []
    for component in (below, above):
        if component.Volume <= TOL:
            continue
        swept, method = translation_sweep(component, (0, 0, distance))
        pieces.append(swept)
        methods.append(method)
    return Part.makeCompound(pieces), "seating-plane partition: " + "; ".join(methods)


def _carrier_interface_checks(doc):
    """Saved material witnesses for seating, slot axes and clamp bearing lands."""
    from gondola.cad import box

    group = doc.OpticalFlowModule
    carrier = doc.getObject(optical_interface.SUPPORTED_HOSTS[group.CarrierHostName])
    inverse = group.getGlobalPlacement().inverse()
    plate = world_shape(carrier)
    plate.Placement = inverse.multiply(plate.Placement)
    foot = world_shape(doc.OpticalMountBase)
    foot.Placement = inverse.multiply(foot.Placement)
    rows = []
    for x in (-4.0, 2.0):
        for target, z, face in ((plate, -0.2, "carrier"), (foot, 0.0, "foot")):
            witness = box(2, 18, 0.2, (x, -9, z))
            missing = witness.cut(target).Volume
            rows.append(
                {
                    "kind": "foot_support_strip",
                    "surface": face,
                    "x_min_mm": x,
                    "missing_material_mm3": missing,
                    "passed": missing <= TOL,
                }
            )
    # Independent material witness: a narrow peg, shortened/rotated tongue or
    # a historical two-bolt foot cannot certify this single-clamp connection.
    locator_core = box(2.4, 6.0, 1.2, (-1.2, -5.0, -1.2))
    missing = locator_core.cut(foot).Volume
    rows.append(
        {
            "kind": "rigid_locator_full_length_and_section",
            "missing_material_mm3": missing,
            "passed": missing <= TOL,
        }
    )
    underside = box(8, 18, 10, (-4, -9, -mounting_plate.THICKNESS_MM - 10))
    intrusion = intersection_volume(underside, foot)
    rows.append(
        {
            "kind": "locator_stays_above_carrier_underside",
            "obstruction_mm3": intrusion,
            "passed": intrusion <= TOL,
        }
    )
    # The upward sweep is the same occupied set as the reversed insertion.
    insertion, method = _seated_foot_lift_sweep(foot, 2.0)
    blockage = intersection_volume(insertion, plate)
    rows.append(
        {
            "kind": "continuous_full_seating_insertion",
            "method": method,
            "obstruction_mm3": blockage,
            "passed": blockage <= TOL,
        }
    )
    for index, (x, y) in optical_interface.CLAMP_CENTRES.items():
        axis = Part.makeCylinder(1.0, 4.0, V(x, y, -mounting_plate.THICKNESS_MM))
        obstruction = intersection_volume(axis, plate) + intersection_volume(axis, foot)
        rows.append(
            {
                "kind": "M2_axis_through_slot_and_foot",
                "index": index,
                "obstruction_mm3": obstruction,
                "passed": obstruction <= TOL,
            }
        )
        rows.append(
            {
                "kind": "centred_slot_head_bearing",
                "index": index,
                **slot_bearing.check(
                    plate,
                    (x, y),
                    -mounting_plate.THICKNESS_MM,
                    maximum_slot_width=optical_interface.HOST_SLOT_WIDTH
                    + optical_interface.DIMENSION_ALLOWANCE,
                    minimum_screw_diameter=optical_interface.MINIMUM_RECEIVED_BOLT_DIAMETER,
                ),
            }
        )
        for side in (-1, 1):
            lower_x = x + (1.35 if side == 1 else -1.7)
            for material, z in ((plate, -mounting_plate.THICKNESS_MM), (foot, 1.3)):
                witness = box(0.35, 1.0, 0.2, (lower_x, y - 0.5, z))
                missing = witness.cut(material).Volume
                rows.append(
                    {
                        "kind": "transverse_clamp_bearing_land",
                        "index": index,
                        "side": side,
                        "surface": "carrier_head" if z < 0 else "foot_nut",
                        "missing_material_mm3": missing,
                        "passed": missing <= TOL,
                    }
                )
    overlap = intersection_volume(plate, foot)
    return {
        "carrier": carrier.Name,
        "witnesses": rows,
        "overlap_mm3": overlap,
        "scope": "Nominal saved geometry, not bearing pressure or retention qualification. Full flat support strips, the rigid locator and one axial passage plus nominal transverse head/nut lands must retain material. Insertion is a rigid translation, not a fit-force, preload or retention qualification.",
        "passed": overlap <= TOL and all(row["passed"] for row in rows),
    }


def _foot_service_checks(doc, physical, kit):
    """Continuous ordered removal on the detached, supported carrier bench."""
    group = doc.OpticalFlowModule
    host = group.getParentGeoFeatureGroup()
    inverse = group.getGlobalPlacement().inverse()

    def local(obj):
        shape = world_shape(obj)
        shape.Placement = inverse.multiply(shape.Placement)
        return shape

    host_parts = {
        obj.Name: local(obj)
        for obj in physical
        if belongs_to_group(obj, host) and obj not in kit
    }
    remaining = {obj.Name: local(obj) for obj in kit}
    rows = []

    def path(name, shape, points, obstacles):
        segments = []
        for start, end in zip(points, points[1:]):
            moving = shape.copy()
            moving.translate(V(*start))
            if (
                name == "CompleteOpticalMount/OpticalMountBase"
                and start == (0, 0, 0)
                and end[:2] == (0, 0)
                and end[2] > 0
            ):
                swept, method = _seated_foot_lift_sweep(moving, end[2])
            else:
                swept, method = translation_sweep(
                    moving, tuple(b - a for a, b in zip(start, end))
                )
            hits = [
                {"object": other, "intersection_mm3": volume}
                for other, target in obstacles.items()
                if (volume := intersection_volume(swept, target)) > TOL
            ]
            segments.append(
                {
                    "start_mm": start,
                    "end_mm": end,
                    "method": method,
                    "collisions": hits,
                    "passed": not hits,
                }
            )
        rows.append(
            {
                "part": name,
                "segments": segments,
                "passed": all(row["passed"] for row in segments),
            }
        )

    release_z = (
        optical_interface.CLAMP_SCREW_LENGTH
        - mounting_plate.THICKNESS_MM
        - optical_interface.FOOT_NUT_SEAT_Z
        + 0.2
    )
    screw_withdrawal = optical_interface.CLAMP_SCREW_LENGTH + 0.2
    for index in optical_interface.CLAMP_CENTRES:
        name = f"OpticalFootNut{index}"
        shape = remaining.pop(name)
        # First unthread beyond the bolt tip, then move outside the tray and lift.
        path(
            name,
            shape,
            [(0, 0, 0), (0, 0, release_z), (20, 0, release_z), (20, 0, 40)],
            {**host_parts, **remaining},
        )
    for index in optical_interface.CLAMP_CENTRES:
        name = f"OpticalFootBolt{index}"
        shape = remaining.pop(name)
        path(
            name,
            shape,
            [(0, 0, 0), (0, 0, -screw_withdrawal)],
            {**host_parts, **remaining},
        )
    for name, shape in remaining.items():
        path("CompleteOpticalMount/" + name, shape, [(0, 0, 0), (0, 0, 40)], host_parts)
    return {
        "scope": f"Disconnect leads; detach the populated carrier from the rail and support it on a bench. Turn the underside screw to release the pocket-held foot nut {release_z:g} mm, slide20 mm along optical-local+X outside the tray and lift; withdraw its screw{screw_withdrawal:g} mm toward carrier underside, then lift the complete mount40 mm, clearing the integral 1.2 mm tongue. The balloon, hand/tool and connected harness are outside this bench-service model.",
        "paths": rows,
        "passed": all(row["passed"] for row in rows),
    }


def _rail_interface_checks(doc):
    """Use the standard saved lower-shoe material audit without carrier foot assumptions."""
    from .rail_mount import saved_integral_mount_checks

    rows = saved_integral_mount_checks(
        doc, doc.DesignRegistry, module_names=("OpticalFlowModule",)
    )
    return {
        "attachment_mode": "rail",
        "saved_mounts": rows,
        "passed": len(rows) == 1
        and rows[0].get("part") == "OpticalMountBase"
        and rows[0]["passed"],
        "scope": "Standard rail shoe, independent lower-stock comparison and complete saved base. Seating, M3 hardware and ordered removal are additionally checked by the common rail audit.",
    }


def _attachment_service_checks(doc, physical, kit):
    mode = resolve_mount_mode(str(doc.OpticalFlowModule.OpticalAttachmentMode))
    if mode == "carrier":
        return _foot_service_checks(doc, physical, kit)
    from .rail_access import rail_attachment_service

    return rail_attachment_service(
        doc, doc.DesignRegistry, physical, module_names=("OpticalFlowModule",)
    )


def _nut_recess_checks(doc):
    """Saved shallow seats restrain minimum M2 nuts without raising outer surfaces."""
    from gondola.parts.purchased_hardware import hex_prism

    rows = []
    for name, part, parent, origin, rotation in (
        (
            "OpticalFootNut1",
            "OpticalMountBase",
            doc.OpticalFlowModule,
            V(0, 5, 1.5),
            App.Rotation(),
        ),
        (
            "OpticalPitchNut",
            "OpticalSensorTray",
            doc.OpticalPitchStage,
            V(0, 1.5, 0),
            App.Rotation(V(1, 0, 0), -90),
        ),
    ):
        if (
            name == "OpticalFootNut1"
            and str(doc.OpticalFlowModule.OpticalAttachmentMode) == "rail"
        ):
            continue
        support = world_shape(doc.getObject(part))
        support.Placement = (
            parent.getGlobalPlacement().inverse().multiply(support.Placement)
        )
        frame = App.Placement(origin, rotation)
        support.Placement = frame.inverse().multiply(support.Placement)
        nut = hex_prism(3.8, 1.35).cut(Part.makeCylinder(1.0, 1.55, V(0, 0, -0.1)))
        overlap = abs(nut.common(support).Volume)
        turns = []
        for angle in (-30, 30):
            turned = nut.copy()
            turned.rotate(V(), V(0, 0, 1), angle)
            turns.append(abs(turned.common(support).Volume))
        floor_lengths = [
            support.common(Part.makeLine(V(x, 0, -1.5), V(x, 0, 0))).Length
            for x in (-1.5, 1.5)
        ]
        actual = doc.getObject(name)
        parent_ok = actual.getParentGeoFeatureGroup() == parent
        rows.append(
            {
                "nut": name,
                "support": part,
                "aligned_minimum_nut_overlap_mm3": overlap,
                "turn_30deg_obstruction_mm3": turns,
                "nut_follows_its_seat": parent_ok,
                "retained_floor_lengths_mm": floor_lengths,
                "passed": overlap < TOL
                and min(turns) > TOL
                and parent_ok
                and all(abs(length - 1.5) < TOL for length in floor_lengths),
            }
        )
    return {
        "seats": rows,
        "scope": "Nominal minimum AF3.8 x1.35 nut without chamfers; actual chamfer engagement, print fit, tightening and PA12 creep remain unqualified. Pockets are open and do not retain a loose nut axially.",
        "passed": all(row["passed"] for row in rows),
    }


def _saved_sensor_state(doc):
    """Snapshot only properties the temporary profile switch may replace."""
    state = {}
    for name in (
        "ModuleMTF02PEnvelope",
        "MTF02POpticalClearanceReserve",
        "MTF02PConnectorReserve",
    ):
        obj = doc.getObject(name)
        properties = {"Shape", "Placement", "Label"} | {
            key for key in obj.PropertiesList if obj.getGroupOfProperty(key) == "Design"
        }
        state[name] = {}
        for key in properties:
            value = getattr(obj, key)
            state[name][key] = value.copy() if hasattr(value, "copy") else value
    return state


def _restore_sensor_state(doc, state):
    for name, properties in state.items():
        obj = doc.getObject(name)
        for key, value in properties.items():
            setattr(obj, key, value)


def mtf_sensor_check(doc):
    """Audit both sensors on the saved rail or carrier attachment; never save."""
    report = {
        "scope": "Saved CAD only: both mutually exclusive sensors, five sampled pitch attitudes and a conservative continuous external field. The standard rail audit covers selected module seating and ordered removal. Carrier mode additionally checks the optical foot on its detached host; rail mode releases its own M3 pair before bench pitch service. Actual print distortion, angular rocking, retention, optical origins, cables and pointing remain unqualified; host, side and rail-position changes require renewed clearance checks."
    }
    evidence = _source_evidence(doc)
    report["source_evidence"] = evidence
    if not evidence["passed"]:
        report["passed"] = False
        return report
    mode = resolve_mount_mode(str(doc.OpticalFlowModule.OpticalAttachmentMode))
    interface = (
        _carrier_interface_checks(doc)
        if mode == "carrier"
        else _rail_interface_checks(doc)
    )
    report[mode + "_interface"] = interface
    report["attachment_mode"] = mode
    nut_recesses = _nut_recess_checks(doc)
    report["nut_recesses"] = nut_recesses
    group = doc.OpticalFlowModule
    old_model = group.SensorModel
    saved_sensor_state = _saved_sensor_state(doc)
    old_pitch = doc.OpticalPitchStage.Pitch.Value
    try:
        registry = doc.DesignRegistry
        physical = (
            list(registry.PrintedParts)
            + list(registry.HardwareParts)
            + list(registry.ReferenceParts)
            + list(registry.TapeReferences)
        )
        kit = [obj for obj in physical if belongs_to_group(obj, group)]
        alternatives = {}
        for key, profile in SENSOR_PROFILES.items():
            optical_sensor.apply_profile(doc, profile)
            alternatives[key] = _placement_checks(doc, physical, kit, profile=profile)
            alternatives[key]["bench_service"] = _attachment_service_checks(
                doc, physical, kit
            )
            alternatives[key]["pitch_disassembly"] = pitch_disassembly_check(doc, kit)
            alternatives[key]["passed"] &= alternatives[key]["bench_service"]["passed"]
            alternatives[key]["passed"] &= alternatives[key]["pitch_disassembly"][
                "passed"
            ]
        report["carrier_host"] = getattr(group, "CarrierHostName", None)
        report["carrier_side"] = str(group.MountSide) if mode == "carrier" else None
        report["selected_sensor_model"] = old_model
        report["sensor_alternatives"] = alternatives
        report["passed"] = (
            interface["passed"]
            and nut_recesses["passed"]
            and all(row["passed"] for row in alternatives.values())
        )
        return report
    finally:
        _restore_sensor_state(doc, saved_sensor_state)
        group.SensorModel = old_model
        optical_mount.set_pitch(doc, old_pitch)
