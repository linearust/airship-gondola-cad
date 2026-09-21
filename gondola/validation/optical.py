"""Read-only saved optical-stack evidence, clearance and service audit.

Moving-part collision checks sample 25 attitudes per host. The separate broad
optical cone conservatively contains the external field over the entire angle
range; neither check qualifies physical fit, friction, cables or gravity trim.
"""

import itertools
import json
import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, world_shape
from gondola.manufacturing import geometry_comparison
from gondola.parts import (
    equipment_mounts,
    optical_mount,
    optical_sensor,
    stack_interface,
)

from .geometry import intersection_volume, local_shape, translation_sweep

TOL = 1e-5
V = App.Vector
ANGLES = (-20, -10, 0, 10, 20)


def _matches(first, second):
    result = geometry_comparison(first, second)
    return result, all(
        result[key] < TOL
        for key in ("difference_mm3", "bounds_difference_mm", "volume_difference_mm3")
    )


def _same_placement(first, second):
    return (first.Base - second.Base).Length < TOL and first.Rotation.isSame(
        second.Rotation, TOL
    )


def _hits(shape, obstacles):
    return [
        {"object": name, "intersection_mm3": volume}
        for name, other in obstacles.items()
        if (volume := intersection_volume(shape, other)) > TOL
    ]


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
            "StackInterfaceContract",
            "StackHostName",
            "HoldingTorqueVerified",
            "SelfLevelling",
            "StackFitVerified",
        ),
        "OpticalRollStage": ("Roll", "MinimumAngle", "MaximumAngle"),
        "OpticalPitchStage": ("Pitch", "MinimumAngle", "MaximumAngle"),
    }
    required.update({name: () for name in stack_interface.SUPPORTED_HOSTS})
    required.update(
        {
            name: ("Shape", "StackInterfaceContract", "StackFitVerified")
            for name in stack_interface.SUPPORTED_HOSTS.values()
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
        "OpticalFlowModule": set(stack_interface.SUPPORTED_HOSTS),
        "OpticalRollStage": {"OpticalFlowModule"},
        "OpticalPitchStage": {"OpticalRollStage"},
        **{
            support: {host} for host, support in stack_interface.SUPPORTED_HOSTS.items()
        },
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
                    "expected_parents": sorted(allowed),
                }
            )
    return {"errors": errors, "passed": not errors}


def _source_evidence(doc):
    """Bind saved shapes, placements, metadata and registries to source factories."""
    structure = _native_structure_check(doc)
    if not structure["passed"]:
        return {"native_structure": structure, "passed": False}
    expected_doc = App.newDocument("OpticalEvidenceReference")
    rows = []
    try:
        host = expected_doc.addObject("App::Part", "BatteryEquipmentModule")
        kit = optical_mount.build_optical_mount(expected_doc, host)
        stack_interface.attach_to_host(kit["group"], host)
        kit["hardware"] += stack_interface.build_stack_hardware(
            expected_doc, kit["group"]
        )
        refs, reserves = optical_sensor.build_sensor(expected_doc, kit["pitch_stage"])
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
                for name in (
                    "OpticalMountContract",
                    "StackInterfaceContract",
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
                    "StackEnd",
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
                    "StackFitVerified",
                    "MountingStackVerified",
                    "PCBHeightMeasured",
                    "InstalledConnectorFitVerified",
                    "InstalledOpticalFieldVerified",
                    "OpticalOriginsMeasured",
                ):
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
                group.StackInterfaceContract, kit["group"].StackInterfaceContract
            )
            and not group.HoldingTorqueVerified
            and not group.SelfLevelling
            and not group.StackFitVerified
            and group.getParentGeoFeatureGroup().Name in stack_interface.SUPPORTED_HOSTS
            and group.StackHostName == group.getParentGeoFeatureGroup().Name
            and _same_placement(group.Placement, kit["group"].Placement)
            and {obj.Name for obj in registry.OpticalMountParts}
            == {obj.Name for obj in kit["printed"]}
        )
        controls = []
        for name, key in (("OpticalRollStage", "Roll"), ("OpticalPitchStage", "Pitch")):
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
        host_rows = []
        for name, kind in (
            ("BatteryMount", "battery"),
            ("ElectronicsMount", "electronics"),
        ):
            obj = doc.getObject(name)
            comparison, ok = _matches(
                local_shape(obj), equipment_mounts.mount_shape(kind)
            )
            contract_ok = _json_equal(
                obj.StackInterfaceContract,
                json.dumps(stack_interface.interface_contract()),
            )
            host_rows.append(
                {
                    "object": name,
                    "source_comparison": comparison,
                    "interface_contract_matches": contract_ok,
                    "passed": ok and contract_ok and not obj.StackFitVerified,
                }
            )
        return {
            "native_structure": structure,
            "objects": rows,
            "registered_kit_inventory_matches_factory": inventory,
            "module_contract_and_registry": module_ok,
            "native_controls": controls,
            "both_host_interfaces": host_rows,
            "passed": module_ok
            and all(inventory.values())
            and all(row["passed"] for row in rows + controls + host_rows),
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


def _external_field_bound(group):
    """A broad circular cone containing every rectangular field orientation."""
    angle = math.radians(optical_mount.ANGLE_LIMIT_DEG)
    c, s = math.cos(angle), math.sin(angle)
    half_x, half_y = (v / 2 for v in optical_sensor.SIZE_MM[:2])
    front = optical_sensor.SENSOR_BOTTOM_Z + optical_sensor.SIZE_MM[2]
    offset = optical_mount.PITCH_PIVOT_OFFSET_Z
    z = (
        optical_mount.ROLL_PIVOT_Z
        + offset * c
        + front * c * c
        - half_x * s * c
        - half_y * s
    )
    radius = offset + math.sqrt(half_x**2 + half_y**2 + front**2)
    angular_bound = math.acos(c * c) + math.atan(
        math.sqrt(2) * math.tan(math.radians(optical_sensor.FLOW_FOV_DEG / 2))
    )
    height = optical_sensor.OPTICAL_RESERVE_LENGTH_MM
    bound = Part.makeCone(
        radius, radius + height * math.tan(angular_bound), height, V(0, 0, z)
    )
    bound.Placement = group.getGlobalPlacement()
    return bound, {
        "minimum_front_z_in_stack_frame_mm": z,
        "initial_radius_mm": radius,
        "half_angle_deg": math.degrees(angular_bound),
        "height_mm": height,
    }


def _host_checks(doc, host, physical, kit):
    group = doc.OpticalFlowModule
    stack_interface.attach_to_host(group, host)
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
    external = {**fixed, **rotor}
    rows = []
    maximum_depth = -math.inf
    for roll, pitch in itertools.product(ANGLES, repeat=2):
        optical_mount.set_angles(doc, roll, pitch)
        own = {obj.Name: world_shape(obj) for obj in kit}
        collisions = []
        reserved_hits = []
        for name, shape in own.items():
            collisions += [{"moving": name, **hit} for hit in _hits(shape, external)]
            reserved_hits += [
                {"moving": name, **hit} for hit in _hits(shape, reservations)
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
        optic_hits = _hits(world_shape(doc.MTF02POpticalClearanceReserve), obstacles)
        connector_hits = _hits(world_shape(doc.MTF02PConnectorReserve), obstacles)
        inverse = doc.OpticalPitchStage.getGlobalPlacement().inverse()
        depth = max(
            inverse.multVec(point).z
            - optical_sensor.SENSOR_BOTTOM_Z
            - optical_sensor.SIZE_MM[2]
            for shape in obstacles.values()
            for point in _corners(shape)
        )
        maximum_depth = max(maximum_depth, depth)
        control_ok = doc.OpticalRollStage.Placement.Rotation.isSame(
            App.Rotation(V(1, 0, 0), roll), TOL
        ) and doc.OpticalPitchStage.Placement.Rotation.isSame(
            App.Rotation(V(0, 1, 0), pitch), TOL
        )
        rows.append(
            {
                "roll_deg": roll,
                "pitch_deg": pitch,
                "physical_collisions": collisions,
                "reserved_space_intrusions": reserved_hits,
                "optical_obstructions": optic_hits,
                "connector_obstructions": connector_hits,
                "body_forward_extent_mm": depth,
                "native_rotation_matches": control_ok,
                "passed": not collisions
                and not reserved_hits
                and not optic_hits
                and not connector_hits
                and control_ok
                and depth <= optical_sensor.OPTICAL_RESERVE_LENGTH_MM + TOL,
            }
        )
    optical_mount.set_angles(doc, 0, 0)
    bound, dimensions = _external_field_bound(group)
    bound_hits = _hits(bound, external)
    pivot = group.getGlobalPlacement().multVec(V(0, 0, optical_mount.ROLL_PIVOT_Z))
    # Norm bounds every forward projection for all roll/pitch combinations.
    depth_bound = (
        max(
            (point - pivot).Length
            for shape in {**external, **{o.Name: world_shape(o) for o in kit}}.values()
            for point in _corners(shape)
        )
        + optical_mount.PITCH_PIVOT_OFFSET_Z
        + optical_sensor.SENSOR_BOTTOM_Z
        + optical_sensor.SIZE_MM[2]
    )
    continuous = {
        **dimensions,
        "external_obstructions": bound_hits,
        "all_angles_body_depth_upper_bound_mm": depth_bound,
        "method": "Conservative full-angle circular cone against external parts and complete rotor bounds; norm upper bound covers full modeled-body depth",
        "passed": not bound_hits
        and depth_bound <= optical_sensor.OPTICAL_RESERVE_LENGTH_MM + TOL,
    }
    service = []
    retained = [
        obj
        for obj in physical
        if not stack_interface.is_removable_head_part(obj, group)
    ]
    for name in (
        "ModuleBatteryEnvelope",
        "ModuleFCEnvelope",
        "ModulePASEnvelope",
        "ModuleLR900Envelope",
    ):
        device = doc.getObject(name)
        if device.getParentGeoFeatureGroup() != host:
            continue
        sweep, method = translation_sweep(world_shape(device), (0, 0, 32))
        hits = _hits(
            sweep, {obj.Name: world_shape(obj) for obj in retained if obj != device}
        )
        service.append(
            {
                "device": name,
                "upward_travel_mm": 32,
                "method": method,
                "columns_and_lower_fasteners_retained": True,
                "collisions": hits,
                "passed": not hits,
            }
        )
    return {
        "host": host.Name,
        "both_complete_rotor_bounds_present": rotor_complete,
        "sampled_attitudes": rows,
        "maximum_sampled_forward_extent_mm": maximum_depth,
        "continuous_external_optical_bound": continuous,
        "bare_device_removal_after_head_release": service,
        "passed": rotor_complete
        and all(row["passed"] for row in rows + service)
        and continuous["passed"],
    }


def mtf_sensor_check(doc):
    """Temporarily probe both hosts and restore all native changes; never save."""
    report = {
        "scope": "Saved CAD geometry only. 25 sampled self-mechanism attitudes per host; continuous conservative external optical bound. No self-levelling, torque, strength, adhesive, real cable or calibrated optical qualification."
    }
    evidence = _source_evidence(doc)
    report["source_evidence"] = evidence
    if not evidence["passed"]:
        report["passed"] = False
        return report
    group = doc.OpticalFlowModule
    old_host = group.getParentGeoFeatureGroup()
    old_placement = group.Placement.copy()
    saved_properties = {
        name: getattr(group, name)
        for name in ("StackHostName", "StackInterfaceContract", "StackFitVerified")
    }
    old_angles = (doc.OpticalRollStage.Roll.Value, doc.OpticalPitchStage.Pitch.Value)
    try:
        registry = doc.DesignRegistry
        physical = (
            list(registry.PrintedParts)
            + list(registry.HardwareParts)
            + list(registry.ReferenceParts)
            + list(registry.TapeReferences)
        )
        kit = [obj for obj in physical if belongs_to_group(obj, group)]
        hosts = [
            _host_checks(doc, doc.getObject(name), physical, kit)
            for name in stack_interface.SUPPORTED_HOSTS
        ]
        report["hosts"] = hosts
        report["service_prerequisite"] = (
            "Disconnect leads, remove the two upper screws and complete optical head before releasing/lifting the host device. Keep both columns and lower screws; device mounting hardware and adhesive must be released. No connected-harness removal claim."
        )
        report["passed"] = all(row["passed"] for row in hosts)
        return report
    finally:
        stack_interface.attach_to_host(group, old_host)
        group.Placement = old_placement
        for name, value in saved_properties.items():
            setattr(group, name, value)
        optical_mount.set_angles(doc, *old_angles)
