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
        coupon_rows = []
        expected_coupons = stack_interface.build_fit_coupons(expected_doc)["printed"]
        for expected in expected_coupons:
            actual = doc.getObject(expected.Name)
            if actual is None:
                coupon_rows.append(
                    {
                        "object": expected.Name,
                        "passed": False,
                        "error": "missing coupon",
                    }
                )
                continue
            comparison, geometry_ok = _matches(
                local_shape(actual), local_shape(expected)
            )
            rotation_ok = (
                "PrintRotation" in actual.PropertiesList
                and actual.PrintRotation.isSame(expected.PrintRotation, TOL)
            )
            registered = actual in registry.FitCoupons and all(
                actual not in getattr(registry, category)
                for category in (
                    "PrintedParts",
                    "HardwareParts",
                    "ReferenceParts",
                    "ClearanceVolumes",
                    "TapeReferences",
                )
            )
            contract_ok = (
                "StackInterfaceContract" in actual.PropertiesList
                and _json_equal(
                    actual.StackInterfaceContract, expected.StackInterfaceContract
                )
            )
            coupon_rows.append(
                {
                    "object": actual.Name,
                    "source_comparison": comparison,
                    "production_orientation_matches": rotation_ok,
                    "registered_only_as_coupon": registered,
                    "interface_contract_matches": contract_ok,
                    "passed": geometry_ok
                    and rotation_ok
                    and registered
                    and contract_ok,
                }
            )
        return {
            "native_structure": structure,
            "objects": rows,
            "registered_kit_inventory_matches_factory": inventory,
            "module_contract_and_registry": module_ok,
            "native_controls": controls,
            "both_host_interfaces": host_rows,
            "latch_qualification_coupons": coupon_rows,
            "passed": module_ok
            and all(inventory.values())
            and all(row["passed"] for row in rows + controls + host_rows + coupon_rows),
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


def tower_attachment_check(doc, host):
    """Probe broad seats and positive underside capture on the saved solids."""
    base = world_shape(doc.OpticalMountBase)
    carrier = world_shape(doc.getObject(stack_interface.SUPPORTED_HOSTS[host.Name]))
    seated_overlap = intersection_volume(base, carrier)
    rows = []
    placement = doc.OpticalFlowModule.getGlobalPlacement()
    for index, (x, y) in enumerate(stack_interface.ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        clip = Part.makeBox(
            18, 14, 8, V(radius - 5, -7, -stack_interface.TOWER_HEIGHT - 5)
        )
        clip.rotate(V(), V(0, 0, 1), math.degrees(math.atan2(y, x)))
        clip.Placement = placement.multiply(clip.Placement)
        foot = base.common(clip)
        down = foot.copy()
        down.translate(placement.Rotation.multVec(V(0, 0, -0.1)))
        seat_area = intersection_volume(down, carrier) / 0.1
        up = foot.copy()
        up.translate(
            placement.Rotation.multVec(V(0, 0, stack_interface.NOMINAL_CLEARANCE + 0.1))
        )
        hook_area = intersection_volume(up, carrier) / 0.1
        rows.append(
            {
                "foot": index,
                "upper_seat_contact_area_mm2": seat_area,
                "positive_hook_contact_area_mm2": hook_area,
                "passed": seat_area > 35 and hook_area > 12,
            }
        )
    fit = stack_interface.latch_fit_contract()
    return {
        "nominal_seated_overlap_mm3": seated_overlap,
        "positive_latch_seats": rows,
        "dimensional_and_strain_screen": fit,
        "scope": "Actual saved solid support and underside hook engagement. Worst combined dimensional error, radial float and yaw are bounded separately. Unpadded play is real; the geometrical pass does not certify optical angular stiffness, PA12 elasticity, retention or cycle life. Qualify the mating coupons and remove actual rocking with a measured existing adhesive pad before accepting pointing.",
        "passed": seated_overlap < TOL
        and len(rows) == 2
        and all(row["passed"] for row in rows)
        and fit["minimum_capture_after_dimension_error_and_radial_float_mm"] > 0.5
        and fit["minimum_remaining_guide_engagement_mm"] > 1.5,
    }


def _tower_service_check(doc, fixed, kit):
    """Bound elastic leg release separately, then lift the released tower."""
    # Shapes are immutable after placement in this audit. Validate each once,
    # including the large purchased gears, rather than for every tip interval.
    find_hits = partial(collision_hits, tolerance=TOL, validation_cache={})
    placement = doc.OpticalFlowModule.getGlobalPlacement()
    fixed_support = stack_interface.fixed_load_support_shape()
    fixed_support.Placement = placement.multiply(fixed_support.Placement)
    release_obstacles = {**fixed, "OpticalRigidLoadSupports": fixed_support}
    release = []
    for index, local, vector in stack_interface.latch_release_envelopes():
        local.Placement = placement.multiply(local.Placement)
        displacement = placement.Rotation.multVec(vector)
        sweep, method = translation_sweep(local, tuple(displacement))
        hits = find_hits(sweep, release_obstacles)
        release.append(
            {
                "foot": index,
                "maximum_radial_release_mm": vector.Length,
                "method": method,
                "collisions": hits,
                "passed": not hits,
            }
        )
    rotating_tips = []
    for index, interval, local in stack_interface.hook_rotation_release_envelopes():
        local.Placement = placement.multiply(local.Placement)
        hits = find_hits(local, release_obstacles)
        rotating_tips.append(
            {
                "foot": index,
                "interval": interval,
                "collisions": hits,
                "passed": not hits,
            }
        )
    access = []
    for index, local in stack_interface.latch_press_reservations():
        local.Placement = placement.multiply(local.Placement)
        hits = find_hits(local, fixed)
        access.append(
            {"foot": index, "manual_access_collisions": hits, "passed": not hits}
        )
    lift = []
    for obj in kit:
        shape = world_shape(obj)
        if obj.Name == "OpticalMountBase":
            proxy = stack_interface.released_tower_envelope().fuse(
                Part.makeBox(
                    optical_mount.EAR_THICKNESS,
                    2 * optical_mount.EAR_RADIUS,
                    optical_mount.ROLL_PIVOT_Z + optical_mount.EAR_RADIUS,
                    V(-optical_mount.EAR_THICKNESS, -optical_mount.EAR_RADIUS, 0),
                )
            )
            proxy.Placement = obj.getGlobalPlacement()
            shape = proxy
        sweep, method = translation_sweep(shape, (0, 0, 40))
        hits = find_hits(sweep, fixed)
        lift.append(
            {
                "object": obj.Name,
                "upward_travel_mm": 40,
                "method": method,
                "collisions": hits,
                "passed": not hits,
            }
        )
    return {
        "elastic_hook_release": release,
        "manual_release_access": access,
        "hook_rotation_and_shortening_screen": rotating_tips,
        "whole_tower_lift": lift,
        "scope": "Peel anti-rattle adhesive contact and disconnect leads. Support tower and push toward carrier until rigid feet seat and hooks unload; spread both spring fingers outward only enough to clear hooks (4.95 mm maximum screened including float, dimensional error and yaw), then withdraw40mm away from carrier along optical+Z while holding release until hooks clear. Spring-finger lateral envelopes are supplemented by continuous interval bounds on tip rotation and axial shortening under a cantilever kinematic screen; fixed load feet do not flex. These are not elastic/contact FEA or force/life certification. Nominal clearances only: measure the coupon release path including minimum axial gap, finish its contact if required, and reject binding. Printed CAD is the unstressed shape. Manual access reserves are simple design envelopes, not measured hands/tools.",
        "passed": len(release) == 2
        and len(access) == 2
        and bool(lift)
        and all(row["passed"] for row in release + rotating_tips + access + lift),
    }


def _tower_float_clearance_check(doc, host, obstacles):
    """Continuous coupled XY/yaw/axial play bounds; pad-controlled rocking excluded."""
    find_hits = partial(collision_hits, tolerance=TOL, validation_cache={})
    rows = []
    placement = doc.OpticalMountBase.getGlobalPlacement()
    external = {
        name: shape
        for name, shape in obstacles.items()
        if name != stack_interface.SUPPORTED_HOSTS[host.Name]
    }
    for name, shape in stack_interface.rigid_float_component_bounds():
        shape.Placement = placement.multiply(shape.Placement)
        hits = find_hits(shape, external)
        wire = external.get("FCWiringClearanceReserve")
        wire_gap = shape.distToShape(wire)[0] if wire is not None else None
        rows.append(
            {
                "component": name,
                "collisions": hits,
                "fc_wiring_gap_mm": wire_gap,
                "passed": not hits and (wire_gap is None or wire_gap >= 1.5 - TOL),
            }
        )
    return {
        "component_bounds": rows,
        "scope": "Continuous conservative bounds from two rigid guides with coupled XY translation/yaw and declared axial play. Intended host contacts excluded; all other physical objects and named external reservations checked. Rocking is not certified and must be removed during physical pad/pointing acceptance.",
        "passed": len(rows) == 6 and all(row["passed"] for row in rows),
    }


def _host_checks(doc, host, physical, kit):
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
    # The sensor's own connector/field share a designed boundary and are excluded.
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
    bound, dimensions = _external_field_bound(group)
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
        + optical_sensor.SIZE_MM[2]
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
    float_clearance = _tower_float_clearance_check(
        doc, host, {**external, **reservations}
    )
    attachment = tower_attachment_check(doc, host)
    tower_service = _tower_service_check(
        doc,
        {
            **external,
            **reservations,
        },
        kit,
    )
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
        hits = find_hits(
            sweep, {obj.Name: world_shape(obj) for obj in retained if obj != device}
        )
        service.append(
            {
                "device": name,
                "upward_travel_mm": 32,
                "method": method,
                "complete_tower_removed": True,
                "tower_foot_fasteners_present": False,
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
        "integral_tower_attachment": attachment,
        "rigid_guide_float_clearance": float_clearance,
        "integral_tower_service": tower_service,
        "passed": rotor_complete
        and all(row["passed"] for row in rows + service)
        and continuous["passed"]
        and attachment["passed"]
        and float_clearance["passed"]
        and tower_service["passed"],
    }


def mtf_sensor_check(doc):
    """Temporarily probe both hosts and restore all native changes; never save."""
    report = {
        "scope": "Saved CAD geometry only. 25 sampled mechanism and connector-access attitudes per host; continuous conservative external optical bound. No self-levelling, torque, strength, adhesive, real cable or calibrated optical qualification."
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
            "Disconnect leads, peel any anti-rattle adhesive contact, push toward the carrier to unload hooks, spread both spring fingers and withdraw the complete integral optical tower along optical+Z before releasing/lifting the host device. Release device mounting hardware and adhesive separately. No connected-harness removal claim."
        )
        report["passed"] = all(row["passed"] for row in hosts)
        return report
    finally:
        stack_interface.attach_to_host(group, old_host)
        group.Placement = old_placement
        for name, value in saved_properties.items():
            setattr(group, name, value)
        optical_mount.set_angles(doc, *old_angles)
