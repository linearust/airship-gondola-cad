"""Read-only carrier-mounted optical evidence and clearance audit.

Mechanism and connector-access checks sample five pitch attitudes at the saved carrier position. The separate broad
optical cone conservatively contains the external field over the entire angle
range; neither check qualifies physical fit, friction, cables or gravity trim.
"""

import itertools
import json
import math
from functools import partial

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, world_shape
from gondola.contracts.optical_sensors import SENSOR_PROFILES, get_sensor_profile
from gondola.parts import (
    optical_interface,
    optical_mount,
    optical_sensor,
    rail,
    wiring_reserves,
)
from gondola.print_export import geometry_comparison

from .evidence import comparison_passed
from .geometry import intersection_volume, local_shape, translation_sweep
from .wiring import RESERVES, collision_hits, measure_clearances, named_gap_checks

TOL = 1e-5
V = App.Vector
ANGLES = (-20, -10, 0, 10, 20)


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
        ),
        "OpticalFlowModule": (
            "OpticalMountContract",
            "OpticalInterfaceContract",
            "CarrierHostName",
            "MountSide",
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
    parents = {
        "OpticalFlowModule": set(optical_interface.SUPPORTED_HOSTS),
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
    group = doc.getObject("OpticalFlowModule")
    if group is not None:
        parent = group.getParentGeoFeatureGroup()
        if getattr(group, "CarrierHostName", None) != (parent.Name if parent else None):
            errors.append(
                {"error": "Optical carrier metadata differs from native parent"}
            )
        if str(getattr(group, "MountSide", "")) not in optical_interface.SIDES:
            errors.append({"error": "Unknown optical carrier side"})
        if "RailPositionX" in group.PropertiesList:
            errors.append(
                {"error": "Obsolete independent optical rail control remains"}
            )
    if (
        doc.getObject("OpticalRollStage") is not None
        or doc.getObject("OpticalRollBracket") is not None
    ):
        errors.append(
            {"error": "Obsolete roll mechanism remains in single-axis assembly"}
        )
    return {"errors": errors, "passed": not errors}


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
        host = expected_doc.addObject(
            "App::Part", doc.OpticalFlowModule.CarrierHostName
        )
        kit = optical_mount.build_optical_mount(
            expected_doc, host, str(doc.OpticalFlowModule.MountSide)
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
                and obj not in registry.RailLocks
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
                        _json_equal(first, second)
                        if name.endswith(("Contract", "Evidence"))
                        else first == second
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
            and group.getParentGeoFeatureGroup() in registry.Modules
            and group.getParentGeoFeatureGroup().Name == group.CarrierHostName
            and group not in registry.Modules
            and "RailPositionX" not in group.PropertiesList
            and _same_placement(group.Placement, kit["group"].Placement)
            and list(group.ExpressionEngine) == list(kit["group"].ExpressionEngine)
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


def _external_field_bound(group, profile=None):
    """Contain the entire one-axis field, including nominal transverse rail clearance."""
    profile = profile or optical_sensor.profile_for_document(group.Document)
    angle = math.radians(optical_mount.ANGLE_LIMIT_DEG)
    half_x, half_y = (v / 2 for v in profile.size_mm[:2])
    front = optical_sensor.SENSOR_BOTTOM_Z + profile.optical_origin_min_z_mm
    pivot = optical_mount.PIVOT_CENTRE
    z = pivot[2] + front * math.cos(angle) - half_x * math.sin(angle)
    registration = rail.HEAD_SIDE_CLEARANCE + math.hypot(
        optical_interface.MAX_REGISTRATION_X, optical_interface.MAX_REGISTRATION_Y
    )
    radius = math.sqrt(half_x**2 + half_y**2 + front**2) + registration
    angular_bound = angle + math.atan(
        math.sqrt(2) * math.tan(math.radians(profile.flow_fov_deg / 2))
    )
    axial_depth = optical_sensor.OPTICAL_RESERVE_LENGTH_MM
    # Cover the far corners of the rectangular field too: after pitch, a
    # corner can extend farther in carrier Z than the nominal axial distance.
    height = (
        math.hypot(
            front + axial_depth,
            half_x + axial_depth * math.tan(math.radians(profile.flow_fov_deg / 2)),
        )
        + pivot[2]
        - z
    )
    bound = Part.makeCone(
        radius,
        radius + height * math.tan(angular_bound),
        height,
        V(pivot[0], pivot[1], z),
    )
    bound.Placement = group.getGlobalPlacement()
    return bound, {
        "minimum_front_z_in_module_frame_mm": z,
        "initial_radius_mm": radius,
        "assembly_registration_radius_allowance_mm": registration,
        "half_angle_deg": math.degrees(angular_bound),
        "height_mm": height,
    }


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
    rows = []
    maximum_depth = -math.inf
    for pitch in ANGLES:
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
        ):
            local = shape.copy()
            local.Placement = inverse_group.multiply(local.Placement)
            bound = optical_interface.registration_bound(local)
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
                and depth <= optical_sensor.OPTICAL_RESERVE_LENGTH_MM + TOL,
            }
        )
    optical_mount.set_pitch(doc, 0)
    bound, dimensions = _external_field_bound(group, profile)
    bound_hits = find_hits(bound, external)
    bound_reserve_hits = find_hits(bound, reservations)
    pivot = group.getGlobalPlacement().multVec(V(*optical_mount.PIVOT_CENTRE))
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
        "method": "Conservative full-angle circular cone with carrier registration and nominal rail-fit allowance against external parts, complete rotor bounds and named wire/access reservations; norm bound covers modeled-body depth. Printed angular rocking and deformation are unqualified.",
        "passed": not bound_hits
        and not bound_reserve_hits
        and depth_bound <= optical_sensor.OPTICAL_RESERVE_LENGTH_MM + TOL,
    }
    return {
        "carrier_host": group.CarrierHostName,
        "carrier_side": str(group.MountSide),
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
    from gondola.parts import mounting_plate

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
            witness = box(2, 16, 0.2, (x, -8, z))
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
    locator_core = box(1.7, 6.0, 0.9, (-0.85, -5.0, -0.9))
    missing = locator_core.cut(foot).Volume
    rows.append(
        {
            "kind": "rigid_locator_full_length_and_section",
            "missing_material_mm3": missing,
            "passed": missing <= TOL,
        }
    )
    underside = box(8, 16, 10, (-4, -8, -mounting_plate.THICKNESS_MM - 10))
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
        for side in (-1, 1):
            lower_x = x + (1.35 if side == 1 else -1.7)
            for material, z in ((plate, -mounting_plate.THICKNESS_MM), (foot, 1.8)):
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

    for index in optical_interface.CLAMP_CENTRES:
        name = f"OpticalFootNut{index}"
        shape = remaining.pop(name)
        # First unthread beyond the bolt tip, then move outside the tray and lift.
        path(
            name,
            shape,
            [(0, 0, 0), (0, 0, 4.2), (20, 0, 4.2), (20, 0, 40)],
            {**host_parts, **remaining},
        )
    for index in optical_interface.CLAMP_CENTRES:
        name = f"OpticalFootBolt{index}"
        shape = remaining.pop(name)
        path(name, shape, [(0, 0, 0), (0, 0, -8.2)], {**host_parts, **remaining})
    for name, shape in remaining.items():
        path("CompleteOpticalMount/" + name, shape, [(0, 0, 0), (0, 0, 40)], host_parts)
    return {
        "scope": "Disconnect leads; detach the populated carrier from the rail and support it on a bench. Unthread the foot nut 4.2 mm, slide20 mm along optical-local+X outside the tray and lift; withdraw its screw8.2 mm toward carrier underside, then lift the complete mount40 mm, clearing the integral 1.2 mm tongue. The rail, balloon, hand/tool and connected harness are outside this bench-service model.",
        "paths": rows,
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
    """Audit both sensors on the saved carrier and edge; never save."""
    report = {
        "scope": "Saved CAD only: both mutually exclusive sensors, five sampled pitch attitudes and a conservative continuous external field. The carrier rail audit covers host seating and ordered end removal; the optical foot requires separate off-rail bench service. Actual print distortion, angular rocking, retention, optical origins, cables and pointing remain unqualified; host, side and rail-position changes require renewed clearance checks."
    }
    evidence = _source_evidence(doc)
    report["source_evidence"] = evidence
    if not evidence["passed"]:
        report["passed"] = False
        return report
    interface = _carrier_interface_checks(doc)
    report["carrier_interface"] = interface
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
            alternatives[key]["bench_service"] = _foot_service_checks(
                doc, physical, kit
            )
            alternatives[key]["passed"] &= alternatives[key]["bench_service"]["passed"]
        report["carrier_host"] = group.CarrierHostName
        report["carrier_side"] = str(group.MountSide)
        report["selected_sensor_model"] = old_model
        report["sensor_alternatives"] = alternatives
        report["passed"] = interface["passed"] and all(
            row["passed"] for row in alternatives.values()
        )
        return report
    finally:
        _restore_sensor_state(doc, saved_sensor_state)
        group.SensorModel = old_model
        optical_mount.set_pitch(doc, old_pitch)
