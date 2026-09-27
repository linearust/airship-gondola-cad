"""Read-only saved optical-stack evidence, clearance and service audit.

Mechanism and connector-access checks sample 25 attitudes per host. The separate broad
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
    equipment_mounts,
    optical_mount,
    optical_sensor,
    stack_interface,
    wiring_reserves,
)
from gondola.print_export import geometry_comparison

from .geometry import intersection_volume, local_shape, translation_sweep
from .wiring import RESERVES, collision_hits, measure_clearances, named_gap_checks

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
            "IntegratedCarrierName",
            "HoldingTorqueVerified",
            "SelfLevelling",
            "StackFitVerified",
            "SensorModel",
            "SupportedSensorModels",
        ),
        "OpticalRollStage": ("Roll", "MinimumAngle", "MaximumAngle"),
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
    required.update({name: () for name in stack_interface.SUPPORTED_HOSTS})
    required.update(
        {
            name: ("Shape", "IntegralOpticalSupport", "PrintSKU")
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
        host = expected_doc.addObject("App::Part", "BatteryEquipmentModule")
        equipment_mounts.build_mount(expected_doc, host, "battery")
        kit = optical_mount.build_optical_mount(expected_doc, host)
        stack_interface.attach_to_host(kit["group"], host)
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
                group.StackInterfaceContract, kit["group"].StackInterfaceContract
            )
            and str(group.SensorModel) == selected_profile.key
            and list(group.SupportedSensorModels) == list(SENSOR_PROFILES)
            and not group.HoldingTorqueVerified
            and not group.SelfLevelling
            and not group.StackFitVerified
            and group.getParentGeoFeatureGroup().Name in stack_interface.SUPPORTED_HOSTS
            and group.StackHostName == group.getParentGeoFeatureGroup().Name
            and group.IntegratedCarrierName == stack_interface.host_print(group).Name
            and doc.getObject("OpticalMountBase") is None
            and not any(o.Name.startswith("OpticalStackFoot") for o in doc.Objects)
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
                local_shape(obj),
                stack_interface.carrier_shape(
                    kind, obj == stack_interface.host_print(group)
                ),
            )
            selected = obj == stack_interface.host_print(group)
            contract_ok = (
                obj.IntegralOpticalSupport == selected
                and obj.PrintSKU == stack_interface.carrier_print_sku(kind, selected)
            )
            if selected:
                contract_ok = contract_ok and _json_equal(
                    obj.StackInterfaceContract,
                    json.dumps(stack_interface.interface_contract()),
                )
            host_rows.append(
                {
                    "object": name,
                    "source_comparison": comparison,
                    "interface_contract_matches": contract_ok,
                    "carrier_local_placement_matches": _same_placement(
                        obj.Placement, App.Placement()
                    ),
                    "passed": ok
                    and contract_ok
                    and _same_placement(obj.Placement, App.Placement()),
                }
            )
        return {
            "native_structure": structure,
            "saved_sensor_model": str(group.SensorModel),
            "source_selected_sensor_model": selected_profile.key,
            "selected_model_matches_source": selected_model_matches,
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


def _external_field_bound(group, profile=None):
    """A broad circular cone containing every rectangular field orientation."""
    profile = profile or optical_sensor.profile_for_document(group.Document)
    angle = math.radians(optical_mount.ANGLE_LIMIT_DEG)
    c, s = math.cos(angle), math.sin(angle)
    half_x, half_y = (v / 2 for v in profile.size_mm[:2])
    front = optical_sensor.SENSOR_BOTTOM_Z + profile.optical_origin_min_z_mm
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
        math.sqrt(2) * math.tan(math.radians(profile.flow_fov_deg / 2))
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


def tower_attachment_check(doc, host):
    """Require the complete integral print, actual root overlap and one solid."""
    carrier = doc.getObject(stack_interface.SUPPORTED_HOSTS[host.Name])
    kind = next(
        k for k, name in equipment_mounts.MOUNT_NAMES.items() if name == carrier.Name
    )
    expected = stack_interface.carrier_shape(kind, True)
    comparison, matches = _matches(local_shape(carrier), expected)
    missing_world_support = abs(
        optical_mount.fixed_base_shape(doc).cut(world_shape(carrier)).Volume
    )
    local_pose_matches = _same_placement(carrier.Placement, App.Placement())
    rows = []
    low = equipment_mounts.mount_shape(kind)
    for name, root in stack_interface.structural_component_shapes():
        if not name.startswith("root_arm_"):
            continue
        root.translate(V(0, 0, stack_interface.STACK_TOP_Z))
        overlap = intersection_volume(low, root)
        missing = abs(root.cut(local_shape(carrier)).Volume)
        rows.append(
            {
                "root": name,
                "carrier_overlap_mm3": overlap,
                "missing_root_mm3": missing,
                "passed": overlap > 1 and missing < TOL,
            }
        )
    return {
        "source_comparison": comparison,
        "fixed_support_missing_from_actual_carrier_mm3": missing_world_support,
        "carrier_local_placement_matches": local_pose_matches,
        "integral_roots": rows,
        "carrier": carrier.Name,
        "valid_single_solid": carrier.Shape.isValid()
        and len(carrier.Shape.Solids) == 1,
        "scope": "Exact source-matching carrier and overlapping lower root arms; no detachable foot interface or registration float. Material continuity does not qualify print strength, creep or pointing stiffness.",
        "passed": matches
        and local_pose_matches
        and missing_world_support < TOL
        and carrier.Shape.isValid()
        and len(carrier.Shape.Solids) == 1
        and len(rows) == 2
        and all(row["passed"] for row in rows),
    }


def _bench_service_obstacles(doc, fixed):
    """Separate only named vehicle assemblies after complete carrier removal.

    Native ancestry, not an obstacle's label or name prefix, defines what stays
    on the bench. Unknown/synthetic obstacles are retained conservatively.
    """
    stack = doc.OpticalFlowModule
    host = stack.getParentGeoFeatureGroup()
    valid_host = host is not None and host.Name in stack_interface.SUPPORTED_HOSTS
    separated_names = (
        "ContinuousRailSystem",
        "TapeAttachmentReference",
        "MainPropulsionModule",
        *stack_interface.MECHANICAL_HOSTS,
    )
    separated = (
        [
            obj
            for name in separated_names
            if (obj := doc.getObject(name)) is not None and obj != host
        ]
        if valid_host
        else []
    )
    retained, removed = {}, []
    for name, shape in fixed.items():
        if name == "MaximumBatteryEnvelope":
            continue
        obj = doc.getObject(name)
        # A host descendant takes precedence even if a corrupted hierarchy
        # places another named assembly beneath the current carrier.
        owner = next(
            (
                group
                for group in separated
                if obj is not None
                and not belongs_to_group(obj, host)
                and belongs_to_group(obj, group)
            ),
            None,
        )
        if owner is None:
            retained[name] = shape
        else:
            removed.append({"object": name, "separated_vehicle_group": owner.Name})
    # Include all actual host descendants independently of the caller's mapping;
    # a shortened obstacle map cannot silently omit carried equipment or wires.
    if valid_host:
        for obj in doc.Objects:
            if (
                obj.isDerivedFrom("Part::Feature")
                and belongs_to_group(obj, host)
                and not belongs_to_group(obj, stack)
                and obj.Name != "MaximumBatteryEnvelope"
            ):
                retained.setdefault(obj.Name, world_shape(obj))
    return retained, {
        "host": host.Name if host is not None else None,
        "valid_supported_host": valid_host,
        "required_prior_step": "Disconnect external leads and remove the complete carrier from the rail using the separately audited module-removal sequence; support carrier on a bench before releasing the moving optical head or extracting the host device.",
        "retained_obstacles": sorted(retained),
        "removed_nonhost_objects": sorted(removed, key=lambda row: row["object"]),
        "scope": "Only descendants of explicitly identified separate vehicle assemblies are absent on the bench. Current-host equipment, wires, carrier hardware and unknown obstacles remain. This filtering applies only to bench service; installed motion, registration, optical field and connector audits retain the whole vehicle.",
    }


def _head_service_check(doc, fixed, kit):
    """Release the roll-axis pair and slide/lift only the moving optical head."""
    find_hits = partial(collision_hits, tolerance=TOL, validation_cache={})
    fixed, frame = _bench_service_obstacles(doc, fixed)
    placement = doc.OpticalFlowModule.getGlobalPlacement()
    roll_pair = {"OpticalRollBolt", "OpticalRollNut"}
    head = [obj for obj in kit if obj.Name not in roll_pair]
    rows = []
    for name, vector in (
        ("OpticalRollNut", (6, 0, 0)),
        ("OpticalRollBolt", (-12, 0, 0)),
    ):
        obj = doc.getObject(name)
        shape = world_shape(obj)
        direction = placement.Rotation.multVec(V(*vector))
        sweep, method = translation_sweep(shape, tuple(direction))
        obstacles = {**fixed, **{o.Name: world_shape(o) for o in head}}
        hits = find_hits(sweep, obstacles)
        rows.append(
            {
                "object": name,
                "step": "release roll-axis hardware",
                "method": method,
                "collisions": hits,
                "passed": not hits,
            }
        )
    for obj in head:
        shape = world_shape(obj)
        uncontained = 0.0
        if obj.Name == "OpticalRollBracket":
            # Bound individual ears/post; one whole box incorrectly fills the
            # empty negative-X region beside the fixed first-axis ear.
            shape = (
                Part.makeCylinder(
                    optical_mount.EAR_RADIUS,
                    optical_mount.EAR_THICKNESS,
                    V(),
                    V(1, 0, 0),
                )
                .fuse(
                    Part.makeBox(
                        optical_mount.ROLL_POST_WIDTH,
                        optical_mount.EAR_THICKNESS,
                        optical_mount.PITCH_PIVOT_OFFSET_Z
                        - optical_mount.ROLL_POST_BOTTOM_Z,
                        V(
                            0,
                            -optical_mount.EAR_THICKNESS,
                            optical_mount.ROLL_POST_BOTTOM_Z,
                        ),
                    )
                )
                .fuse(
                    Part.makeBox(
                        2 * optical_mount.EAR_RADIUS,
                        optical_mount.EAR_THICKNESS,
                        2 * optical_mount.EAR_RADIUS,
                        V(
                            -optical_mount.EAR_RADIUS,
                            -optical_mount.EAR_THICKNESS,
                            optical_mount.PITCH_PIVOT_OFFSET_Z
                            - optical_mount.EAR_RADIUS,
                        ),
                    )
                )
                .removeSplitter()
            )
            shape.Placement = obj.getGlobalPlacement().multiply(shape.Placement)
            uncontained = abs(world_shape(obj).cut(shape).Volume)
        for vector in ((4, 0, 0), (0, 0, 40)):
            direction = placement.Rotation.multVec(V(*vector))
            sweep, method = translation_sweep(shape, tuple(direction))
            hits = find_hits(sweep, fixed)
            rows.append(
                {
                    "object": obj.Name,
                    "step_vector_in_head_frame_mm": vector,
                    "method": method,
                    "proxy_uncontained_mm3": uncontained,
                    "collisions": hits,
                    "passed": not hits and uncontained < TOL,
                }
            )
            shape.translate(direction)
    neutral = (
        abs(doc.OpticalRollStage.Roll.Value) < TOL
        and abs(doc.OpticalPitchStage.Pitch.Value) < TOL
    )
    return {
        "bench_service_frame": frame,
        "neutral_manual_axes": neutral,
        "moving_head_release": rows,
        "scope": "Bench-supported carrier, disconnected sensor lead and both manual axes returned to zero. Remove roll nut and withdraw roll screw; translate head 4 mm toward +X away from fixed ear, then lift40 mm. Fixed portal/carrier remains installed. Tool hand clearance and physical print friction require bench confirmation.",
        "passed": frame["valid_supported_host"]
        and neutral
        and bool(rows)
        and all(r["passed"] for r in rows),
    }


def _integral_support_clearance_check(doc, host, obstacles):
    """Inspect exact integrated support with all installed external obstacles."""
    find_hits = partial(collision_hits, tolerance=TOL, validation_cache={})
    external = {
        n: s
        for n, s in obstacles.items()
        if n != stack_interface.SUPPORTED_HOSTS[host.Name]
    }
    support = optical_mount.fixed_base_shape(doc)
    hits = find_hits(support, external)
    gaps = {}
    for name in ("FCWiringClearanceReserve", "CapacitorServiceReserve"):
        target = external.get(name)
        gaps[name] = support.distToShape(target)[0] if target is not None else None
    return {
        "collisions": hits,
        "minimum_required_gap_mm": 1.5,
        "named_gaps_mm": gaps,
        "scope": "Actual fixed portal and roll support, excluding intentional root/carrier union. Whole installed vehicle and reservations retained. No detachable-joint registration exists.",
        "passed": not hits
        and all(g is not None and g >= 1.5 - TOL for g in gaps.values()),
    }


def _device_service_check(doc, host, fixed):
    """Ordered continuous bare-device bench extraction; portal stays an obstacle."""
    fixed, frame = _bench_service_obstacles(doc, fixed)
    find_hits = partial(collision_hits, tolerance=TOL, validation_cache={})
    rows = []
    for name in ("ModuleBatteryEnvelope", "ModuleFCEnvelope"):
        device = doc.getObject(name)
        if device is None or device.getParentGeoFeatureGroup() != host:
            continue
        # Fastener release and detached leads are prerequisites; their support
        # bodies and the actual carrier remain. The side extraction takes place
        # above the unchanged FC bolt tips, not through the standoffs. Keep
        # actual through-holes during axial lift so retained studs stay clear;
        # only the subsequent side step uses the filled conservative body.
        obstacles = {
            n: s
            for n, s in fixed.items()
            if n != name
            and n
            not in {
                "FCWiringClearanceReserve",
                "BatteryStrapReserve",
                "BatteryConnectorReserve",
                "FCConnectorReserve",
                "BatteryAdhesiveReference",
            }
        }
        shape = stack_interface.device_removal_shape(device)
        uncontained = abs(world_shape(device).cut(shape).Volume)
        actual = world_shape(device)
        segments = []
        for index, vector in enumerate(stack_interface.device_removal_segments(name)):
            direction = host.getGlobalPlacement().Rotation.multVec(V(*vector))
            moving = actual if name == "ModuleFCEnvelope" and index == 0 else shape
            sweep, method = translation_sweep(moving, tuple(direction))
            hits = find_hits(sweep, obstacles)
            segments.append(
                {
                    "carrier_frame_vector_mm": vector,
                    "method": method,
                    "collisions": hits,
                    "passed": not hits,
                }
            )
            shape.translate(direction)
            actual.translate(direction)
        rows.append(
            {
                "device": name,
                "segments": segments,
                "portal_remains": True,
                "proxy_uncontained_mm3": uncontained,
                "passed": uncontained < TOL and all(row["passed"] for row in segments),
            }
        )
    return {
        "bench_service_frame": frame,
        "devices": rows,
        "scope": "Remove movable optical head; disconnect leads, release device hold-down hardware/adhesive. FC lifts12 mm, battery lifts5 mm, then each travels diagonally through the open portal side. Integral carrier stays on the bench. No connected-harness extraction claim.",
        "passed": frame["valid_supported_host"]
        and bool(rows)
        and all(r["passed"] for r in rows),
    }


def _host_checks(doc, host, physical, kit, *, profile=None):
    profile = profile or optical_sensor.profile_for_document(doc)
    group = doc.OpticalFlowModule
    validation_cache = {}
    find_hits = partial(
        collision_hits, tolerance=TOL, validation_cache=validation_cache
    )
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
    for roll, pitch in itertools.product(ANGLES, repeat=2):
        optical_mount.set_angles(doc, roll, pitch)
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
    optical_mount.set_angles(doc, 0, 0)
    bound, dimensions = _external_field_bound(group, profile)
    bound_hits = find_hits(bound, external)
    bound_reserve_hits = find_hits(bound, reservations)
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
        + profile.optical_origin_min_z_mm
    )
    continuous = {
        **dimensions,
        "external_obstructions": bound_hits,
        "external_reserved_space_intrusions": bound_reserve_hits,
        "all_angles_body_depth_upper_bound_mm": depth_bound,
        "method": "Conservative full-angle circular cone against external parts, complete rotor bounds and named wire/access reservations; norm upper bound covers full modeled-body depth",
        "passed": not bound_hits
        and not bound_reserve_hits
        and depth_bound <= optical_sensor.OPTICAL_RESERVE_LENGTH_MM + TOL,
    }
    support_clearance = _integral_support_clearance_check(
        doc, host, {**external, **reservations}
    )
    attachment = tower_attachment_check(doc, host)
    head_service = _head_service_check(doc, {**external, **reservations}, kit)
    service = _device_service_check(doc, host, external)
    return {
        "host": host.Name,
        "sensor_model": profile.key,
        "both_complete_rotor_bounds_present": rotor_complete,
        "sampled_attitudes": rows,
        "maximum_sampled_forward_extent_mm": maximum_depth,
        "continuous_external_optical_bound": continuous,
        "bare_device_removal_after_head_release": service,
        "integral_tower_attachment": attachment,
        "integral_support_clearance": support_clearance,
        "moving_head_service": head_service,
        "passed": rotor_complete
        and all(row["passed"] for row in rows)
        and service["passed"]
        and continuous["passed"]
        and attachment["passed"]
        and support_clearance["passed"]
        and head_service["passed"],
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
    """Probe both mutually exclusive sensors on both hosts; never save changes."""
    report = {
        "scope": "Saved CAD geometry only. Each mutually exclusive sensor has 25 sampled mechanism and connector-access attitudes per host plus a continuous conservative external optical bound. One sensor is substituted in memory at a time; no simultaneous installation is claimed. No self-levelling, torque, strength, adhesive, real cable or calibrated optical qualification."
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
        for name in (
            "StackHostName",
            "StackInterfaceContract",
            "StackFitVerified",
            "SensorModel",
        )
    }
    saved_sensor_state = _saved_sensor_state(doc)
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
        alternatives = {}
        for key, profile in SENSOR_PROFILES.items():
            optical_sensor.apply_profile(doc, profile)
            hosts = [
                _host_checks(doc, doc.getObject(name), physical, kit, profile=profile)
                for name in stack_interface.SUPPORTED_HOSTS
            ]
            alternatives[key] = {
                "sensor_model": key,
                "hosts": hosts,
                "passed": all(row["passed"] for row in hosts),
            }
        report["selected_sensor_model"] = saved_properties["SensorModel"]
        report["sensor_alternatives"] = alternatives
        report["hosts"] = alternatives[saved_properties["SensorModel"]]["hosts"]
        report["service_prerequisite"] = (
            "Disconnect leads and remove complete carrier from rail using its independent service sequence. Bench-support the carrier, remove only the movable optical head, release device hold-down hardware/adhesive, then use its ordered upward/sideways extraction path. Integral portal stays with carrier. No connected-harness or on-balloon service claim."
        )
        report["passed"] = all(row["passed"] for row in alternatives.values())
        return report
    finally:
        _restore_sensor_state(doc, saved_sensor_state)
        stack_interface.attach_to_host(group, old_host)
        group.Placement = old_placement
        for name, value in saved_properties.items():
            setattr(group, name, value)
        optical_mount.set_angles(doc, *old_angles)
