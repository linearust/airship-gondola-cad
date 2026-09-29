"""Read-only independent optical-rail evidence and clearance audit.

Mechanism and connector-access checks sample five pitch attitudes at the saved station. The separate broad
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
    optical_mount,
    optical_sensor,
    rail,
    wiring_reserves,
)
from gondola.print_export import geometry_comparison

from .evidence import comparison_passed
from .geometry import intersection_volume, local_shape
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
            "RailPositionX",
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
        "OpticalFlowModule": {None},
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
        kit = optical_mount.build_optical_mount(expected_doc)
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
            and group.getParentGeoFeatureGroup() is None
            and group in registry.Modules
            and group.Placement.Rotation.isSame(App.Rotation(), TOL)
            and abs(group.Placement.Base.z) < TOL
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
    registration = rail.HEAD_SIDE_CLEARANCE
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
        "nominal_transverse_rail_clearance_allowance_mm": registration,
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
        "method": "Conservative full-angle circular cone with nominal transverse rail-fit allowance against external parts, complete rotor bounds and named wire/access reservations; norm bound covers modeled-body depth. Printed angular rocking and deformation are unqualified.",
        "passed": not bound_hits
        and not bound_reserve_hits
        and depth_bound <= optical_sensor.OPTICAL_RESERVE_LENGTH_MM + TOL,
    }
    return {
        "rail_station_x_mm": group.RailPositionX.Value,
        "sensor_model": profile.key,
        "both_complete_rotor_bounds_present": rotor_complete,
        "sampled_attitudes": rows,
        "maximum_sampled_forward_extent_mm": maximum_depth,
        "continuous_external_optical_bound": continuous,
        "passed": rotor_complete
        and all(row["passed"] for row in rows)
        and continuous["passed"],
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
    """Audit both sensors at the saved independent rail position; never save."""
    report = {
        "scope": "Saved CAD only: both mutually exclusive sensors, five sampled pitch attitudes and a conservative continuous external field. The common rail audit covers seating and ordered end removal. Actual print distortion, angular rocking, retention, optical origins, cables and pointing remain unqualified; arbitrary rail locations require renewed clearance checks."
    }
    evidence = _source_evidence(doc)
    report["source_evidence"] = evidence
    if not evidence["passed"]:
        report["passed"] = False
        return report
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
        report["rail_station_x_mm"] = group.RailPositionX.Value
        report["selected_sensor_model"] = old_model
        report["sensor_alternatives"] = alternatives
        report["passed"] = all(row["passed"] for row in alternatives.values())
        return report
    finally:
        _restore_sensor_state(doc, saved_sensor_state)
        group.SensorModel = old_model
        optical_mount.set_pitch(doc, old_pitch)
