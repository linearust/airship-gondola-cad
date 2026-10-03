"""Saved evidence for a rigid optical head on the shared FC instrument platform.

Both sensor alternatives follow the same native stage as the FC. Sampled
internal contacts supplement conservative continuous external envelopes; neither
is a qualification of print fit, clamp retention, cable flex or calibration.
"""

import itertools
import json
import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, placed_shape, union, world_shape
from gondola.contracts.optical_sensors import SENSOR_PROFILES, get_sensor_profile
from gondola.parts import (
    instrument_mount,
    optical_interface,
    optical_mount,
    optical_sensor,
    propulsion_wiring,
    slot_bearing,
    wiring_reserves,
)
from gondola.print_export import geometry_comparison

from .evidence import comparison_passed
from .geometry import intersection_volume, local_shape
from .optical_envelopes import PITCH_SAMPLE_ANGLES, instrument_context, motion_bounds
from .optical_service import (
    CLAMP_CENTRES,
    mount_tool_check,
    mounting_service_check,
    tray_stock_enclosures,
)
from .wiring import RESERVES, collision_hits, measure_clearances, named_gap_checks

TOL = 1e-5
V = App.Vector


def _matches(first, second):
    if first.isNull() or not first.isValid() or not first.Solids:
        return {"error": "Invalid saved solid"}, False
    result = geometry_comparison(first, second)
    return result, comparison_passed(result, TOL)


def _json_equal(first, second):
    try:
        return json.loads(str(first)) == json.loads(str(second))
    except (TypeError, ValueError):
        return False


def _native_structure_check(doc):
    """Reject missing objects and wrong native ancestry before any mutation."""
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
            "SensorModel",
            "SupportedSensorModels",
        ),
        "InstrumentPitchStage": ("Pitch", "MinimumAngle", "MaximumAngle"),
        "OpticalSensorFrame": ("Placement",),
        "ElectronicsMount": ("Shape",),
        "ModuleFCEnvelope": ("Shape",),
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
    try:
        instrument_context(doc.getObject("OpticalFlowModule"))
    except (AttributeError, TypeError, ValueError) as error:
        errors.append({"error": str(error)})
    parents = {
        "ElectronicsMount": "InstrumentPitchStage",
        "ModuleFCEnvelope": "InstrumentPitchStage",
        "ModuleMTF02PEnvelope": "OpticalSensorFrame",
        "MTF02POpticalClearanceReserve": "OpticalSensorFrame",
        "MTF02PConnectorReserve": "OpticalSensorFrame",
    }
    for name, expected in parents.items():
        obj = doc.getObject(name)
        if obj is None:
            continue
        parent = obj.getParentGeoFeatureGroup()
        if parent is None or parent.Name != expected or list(obj.ExpressionEngine):
            errors.append(
                {
                    "object": name,
                    "expected_fixed_parent": expected,
                    "error": "Incorrect parent or independent expression",
                }
            )
    for name in (
        "OpticalPitchBolt",
        "OpticalPitchNut",
        "OpticalRollBracket",
        "OpticalFlowModuleRailMountScrew",
        "OpticalFlowModuleRailMountNut",
    ):
        if doc.getObject(name) is not None:
            errors.append(
                {"object": name, "error": "Obsolete independent optical mechanism"}
            )
    return {"errors": errors, "passed": not errors}


def _metadata_matches(actual, expected):
    names = {
        name
        for name in expected.PropertiesList
        if expected.getGroupOfProperty(name) in ("Design", "Printing")
    }
    names.update(
        name
        for name in (
            "HardwareSKU",
            "MaterialSelection",
            "SourceURL",
            "SourceEvidence",
            "ThreadStandard",
            "ThreadPitch",
            "NominalThreadDiameter",
            "ThreadGeometry",
            "ModelDetail",
            "Role",
            "Notes",
            "PrintPart",
        )
        if name in expected.PropertiesList
    )
    result = {}
    for name in names:
        present = name in actual.PropertiesList
        first, second = getattr(actual, name, None), getattr(expected, name)
        if name in ("PrintPlacement", "PrintRotation"):
            equal = present and first.isSame(second, TOL)
        else:
            equal = present and (
                first == second
                or (
                    name.endswith(("Contract", "Evidence"))
                    and _json_equal(first, second)
                )
            )
        result[name] = bool(equal)
    return result


def _source_evidence(doc):
    """Bind actual saved optical inventory, shape, placement and source metadata."""
    structure = _native_structure_check(doc)
    if not structure["passed"]:
        return {"native_structure": structure, "passed": False}
    profile = get_sensor_profile()
    group = doc.OpticalFlowModule
    if str(group.SensorModel) != profile.key:
        return {
            "native_structure": structure,
            "selected_model_matches_source": False,
            "passed": False,
        }
    expected_doc = App.newDocument("OpticalEvidenceReference")
    rows, inventory = [], {}
    try:
        module = expected_doc.addObject("App::Part", "ElectronicsEquipmentModule")
        stage = expected_doc.addObject("App::Part", "InstrumentPitchStage")
        module.addObject(stage)
        kit = optical_mount.build_optical_mount(expected_doc, stage)
        refs, reserves = optical_sensor.build_sensor(
            expected_doc, kit["sensor_frame"], profile
        )
        expected_doc.recompute()
        registry = doc.DesignRegistry
        inventory["all_native_shape_descendants"] = {
            obj.Name
            for obj in doc.Objects
            if "Shape" in obj.PropertiesList and belongs_to_group(obj, group)
        } == {obj.Name for obj in kit["printed"] + kit["hardware"] + refs + reserves}
        for category, objects in (
            ("PrintedParts", kit["printed"]),
            ("HardwareParts", kit["hardware"]),
            ("ReferenceParts", refs),
            ("ClearanceVolumes", reserves),
        ):
            actual_names = [
                obj.Name
                for obj in getattr(registry, category)
                if belongs_to_group(obj, group)
            ]
            inventory[category] = sorted(actual_names) == sorted(
                obj.Name for obj in objects
            )
            for expected in objects:
                actual = doc.getObject(expected.Name)
                if actual is None:
                    rows.append(
                        {"object": expected.Name, "error": "missing", "passed": False}
                    )
                    continue
                comparison, geometry_ok = _matches(
                    local_shape(actual), local_shape(expected)
                )
                parent = actual.getParentGeoFeatureGroup()
                parent_ok = (
                    parent is not None
                    and parent.Name == expected.getParentGeoFeatureGroup().Name
                )
                placement_ok = actual.Placement.isSame(expected.Placement, TOL)
                metadata = _metadata_matches(actual, expected)
                registered = list(getattr(registry, category)).count(actual) == 1
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
        group_metadata = _metadata_matches(group, kit["group"])
        fixed_frame = (
            doc.OpticalSensorFrame.Placement.isSame(kit["sensor_frame"].Placement, TOL)
            and not list(doc.OpticalSensorFrame.ExpressionEngine)
            and not any(
                name in doc.OpticalSensorFrame.PropertiesList
                for name in ("Pitch", "Roll", "MinimumAngle", "MaximumAngle")
            )
        )
        module_ok = (
            all(group_metadata.values())
            and fixed_frame
            and group not in registry.Modules
            and not any(belongs_to_group(obj, group) for obj in registry.RailLocks)
            and sorted(obj.Name for obj in registry.OpticalMountParts)
            == sorted(obj.Name for obj in kit["printed"])
        )
        return {
            "native_structure": structure,
            "selected_model_matches_source": True,
            "objects": rows,
            "registered_kit_inventory_matches_factory": inventory,
            "module_metadata_matches": group_metadata,
            "fixed_sensor_frame": fixed_frame,
            "module_contract_and_registry": module_ok,
            "passed": module_ok
            and all(inventory.values())
            and all(row["passed"] for row in rows),
        }
    finally:
        App.closeDocument(expected_doc.Name)


def _rigid_interface_checks(doc):
    """Literal stock and bearing witnesses for the two opposed M2 clamps."""
    group = doc.OpticalFlowModule
    inverse = group.getGlobalPlacement().inverse()
    plate = world_shape(doc.ElectronicsMount)
    plate.Placement = inverse.multiply(plate.Placement)
    foot = local_shape(doc.OpticalSensorTray)
    witness = Part.makeBox(54, 8, 1.5, V(-27, -4, 0))
    witness = witness.cut(Part.makeBox(12, 5, 2, V(-6, -4, 0)))
    for x, y in CLAMP_CENTRES.values():
        witness = witness.cut(Part.makeCylinder(1.1, 1.7, V(x, y, -0.1)))
    missing = abs(witness.cut(foot).Volume)
    rows = [
        {
            "kind": "complete_1_5mm_foot_floor",
            "missing_stock_mm3": missing,
            "passed": missing <= TOL,
        }
    ]
    notch_stock = intersection_volume(foot, Part.makeBox(12, 5, 2, V(-6, -4, 0)))
    rows.append(
        {
            "kind": "FC_underbody_notch",
            "unexpected_stock_mm3": notch_stock,
            "passed": notch_stock <= TOL,
        }
    )
    # Rotate the real plate so the existing independent slot-bearing test's
    # transverse X direction corresponds to this pair's transverse Y direction.
    transverse = plate.copy()
    transverse.rotate(V(), V(0, 0, 1), -90)
    for index, (x, y) in CLAMP_CENTRES.items():
        passage = Part.makeCylinder(1, 4, V(x, y, -2))
        volume = intersection_volume(passage, plate) + intersection_volume(
            passage, foot
        )
        rows.append(
            {
                "kind": "complete_M2_passage",
                "index": index,
                "intersection_mm3": volume,
                "passed": volume <= TOL,
            }
        )
        rows.append(
            {
                "kind": "centred_slot_head_bearing",
                "index": index,
                **slot_bearing.check(
                    transverse,
                    (y, -x),
                    -2,
                    maximum_slot_width=2.9,
                    minimum_screw_diameter=1.8,
                ),
            }
        )
        for side in (-1, 1):
            land = Part.makeBox(
                1, 0.35, 0.2, V(x - 0.5, y + (1.35 if side == 1 else -1.7), 1.3)
            )
            loss = abs(land.cut(foot).Volume)
            rows.append(
                {
                    "kind": "nut_floor_bearing_land",
                    "index": index,
                    "side": side,
                    "missing_stock_mm3": loss,
                    "passed": loss <= TOL,
                }
            )
    overlap = intersection_volume(plate, foot)
    # Maximum slot and foot-hole size, minimum received shank. Translation and
    # yaw follow the two separate screw axes; no unmodeled locator is credited.
    axis_allowance = (2.9 - 1.8) / 2 + (2.5 - 1.8) / 2
    yaw = math.asin(2 * axis_allowance / 38)
    x_bound = axis_allowance + 19 * (1 - math.cos(yaw))
    registration = {
        "required_xy_bound_mm": (x_bound, axis_allowance),
        "required_yaw_bound_deg": math.degrees(yaw),
        "passed": optical_interface.MAX_REGISTRATION_X >= x_bound
        and optical_interface.MAX_REGISTRATION_Y >= axis_allowance
        and optical_interface.MAX_REGISTRATION_YAW_RAD >= yaw,
    }
    return {
        "support": "ElectronicsMount",
        "witnesses": rows,
        "overlap_mm3": overlap,
        "registration_bound": registration,
        "passed": overlap <= TOL
        and registration["passed"]
        and all(row["passed"] for row in rows),
        "scope": "Two opposed slot-end clamps on the same common plate, without a locating tongue or independent pitch joint. Literal foot floor, complete M2 passages and head/nut bearing lands are required. The conservative assembly registration reserve includes pre-clamp hole clearance; actual flat-head centring, print finishing, preload, PA12 creep and physical FC/sensor calibration remain unqualified.",
    }


def _nut_recess_checks(doc):
    from gondola.parts.purchased_hardware import hex_prism

    rows = []
    for index, (x, y) in CLAMP_CENTRES.items():
        support = local_shape(doc.OpticalSensorTray)
        support.translate(V(-x, -y, -1.5))
        nut = hex_prism(3.8, 1.35).cut(Part.makeCylinder(1, 1.55, V(0, 0, -0.1)))
        overlap = intersection_volume(nut, support)
        turns = []
        for angle in (-30, 30):
            rotated = nut.copy()
            rotated.rotate(V(), V(0, 0, 1), angle)
            turns.append(intersection_volume(rotated, support))
        lengths = [
            support.common(
                Part.makeLine(V(0, side * 1.5, -1.5), V(0, side * 1.5, 0))
            ).Length
            for side in (-1, 1)
        ]
        actual = doc.getObject(f"OpticalFootNut{index}")
        follows = (
            actual is not None
            and actual.getParentGeoFeatureGroup() == doc.OpticalFlowModule
        )
        rows.append(
            {
                "nut": f"OpticalFootNut{index}",
                "support": "OpticalSensorTray",
                "aligned_minimum_nut_overlap_mm3": overlap,
                "turn_30deg_obstruction_mm3": turns,
                "nut_follows_its_seat": follows,
                "retained_floor_lengths_mm": lengths,
                "passed": overlap <= TOL
                and min(turns) > TOL
                and follows
                and all(abs(length - 1.5) <= TOL for length in lengths),
            }
        )
    return {
        "seats": rows,
        "passed": len(rows) == 2 and all(row["passed"] for row in rows),
        "scope": "Open shallow pockets resist a minimum nominal nut's rotation but do not retain a loose nut axially. Chamfers, physical fit and loaded retention require inspection.",
    }


def _placement_checks(doc, physical, kit, *, profile=None):
    """Move the real common stage; never detach FC geometry from its sensor."""
    profile = profile or optical_sensor.profile_for_document(doc)
    group, stage = doc.OpticalFlowModule, doc.InstrumentPitchStage
    _, _, frame, _ = instrument_context(group)
    expected_relative = (
        doc.ModuleFCEnvelope.getGlobalPlacement()
        .inverse()
        .multiply(frame.getGlobalPlacement())
    )
    rows = []
    cache = {}
    pitches = tuple(
        dict.fromkeys((*PITCH_SAMPLE_ANGLES, max(-20, min(20, float(stage.Pitch)))))
    )
    for pitch in pitches:
        instrument_mount.set_pitch(doc, pitch)
        own = {obj.Name: world_shape(obj) for obj in kit}
        fixed = {obj.Name: world_shape(obj) for obj in physical if obj not in kit}
        rotor = {
            obj.Name: world_shape(obj)
            for obj in doc.DesignRegistry.ClearanceVolumes
            if obj.Name in ("PortSweepBound", "StarboardSweepBound")
        }
        reservations = {
            obj.Name: world_shape(obj)
            for obj in doc.DesignRegistry.ClearanceVolumes
            if obj.Name not in rotor and not belongs_to_group(obj, group)
        }
        for name in RESERVES:
            if name not in ("MTF02POpticalClearanceReserve", "MTF02PConnectorReserve"):
                reservations.setdefault(name, None)
        # These are setup planning paths, regenerated after manual adjustment;
        # the saved-current versions are independently bound before mutation.
        propulsion_pose = doc.MainPropulsionModule.getGlobalPlacement()
        for prefix, sign in propulsion_wiring.PREFIX_SIGNS:
            route = propulsion_wiring.route_geometry(
                sign, propulsion_pose, stage.getGlobalPlacement()
            )
            reservations[prefix + "PhaseLeadLoopReserve"] = placed_shape(
                route["shape"], propulsion_pose
            )
        external = {**fixed, **rotor}
        collisions, reserve_hits = [], []
        for name, shape in own.items():
            collisions.extend(
                {"moving": name, **hit}
                for hit in collision_hits(
                    shape, external, tolerance=TOL, validation_cache=cache
                )
            )
            reserve_hits.extend(
                {"moving": name, **hit}
                for hit in collision_hits(
                    shape, reservations, tolerance=TOL, validation_cache=cache
                )
            )
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
        field, connector = (
            world_shape(doc.MTF02POpticalClearanceReserve),
            world_shape(doc.MTF02PConnectorReserve),
        )
        field_hits = collision_hits(
            field, obstacles, tolerance=TOL, validation_cache=cache
        )
        connector_hits = collision_hits(
            connector, obstacles, tolerance=TOL, validation_cache=cache
        )
        field_reserve_hits = collision_hits(
            field, reservations, tolerance=TOL, validation_cache=cache
        )
        connector_gaps = measure_clearances(
            connector,
            reservations,
            minimum_gap_mm=wiring_reserves.CONNECTOR_SERVICE_GAP_MM,
            tolerance=TOL,
            validation_cache=cache,
        )
        registration = []
        tray_regions, missing_tray_stock = tray_stock_enclosures(
            local_shape(doc.OpticalSensorTray)
        )
        tray_registration = union(
            [optical_interface.registration_bound(region) for region in tray_regions]
        )
        for name, shape in (
            ("body", optical_sensor.envelope_shape(profile)),
            ("connector", optical_sensor.connector_reserve_shape(profile)),
        ):
            bound = placed_shape(
                optical_interface.registration_bound(shape), frame.getGlobalPlacement()
            )
            hits = collision_hits(
                bound, external, tolerance=TOL, validation_cache=cache
            )
            gaps = measure_clearances(
                bound,
                reservations,
                minimum_gap_mm=wiring_reserves.CONNECTOR_SERVICE_GAP_MM
                if name == "connector"
                else 0,
                tolerance=TOL,
                validation_cache=cache,
            )
            registration.append(
                {
                    "component": name,
                    "external_obstructions": hits,
                    "reserved_space_clearances": gaps,
                    "passed": not hits and all(row["passed"] for row in gaps),
                }
            )
        tray_bound = placed_shape(tray_registration, frame.getGlobalPlacement())
        tray_hits = collision_hits(
            tray_bound, external, tolerance=TOL, validation_cache=cache
        )
        tray_gaps = measure_clearances(
            tray_bound, reservations, tolerance=TOL, validation_cache=cache
        )
        registration.append(
            {
                "component": "bracket",
                "uncovered_saved_stock_mm3": missing_tray_stock,
                "external_obstructions": tray_hits,
                "reserved_space_clearances": tray_gaps,
                "passed": missing_tray_stock <= TOL
                and not tray_hits
                and all(row["passed"] for row in tray_gaps),
            }
        )
        neighbours = named_gap_checks(
            {
                **fixed,
                **own,
                **reservations,
                "MTF02POpticalClearanceReserve": field,
                "MTF02PConnectorReserve": connector,
            },
            wiring_reserves.neighbour_gap_pairs(),
            tolerance=TOL,
            validation_cache=cache,
        )
        tools = mount_tool_check(group, {**external, **own, **reservations})
        relative = (
            doc.ModuleFCEnvelope.getGlobalPlacement()
            .inverse()
            .multiply(frame.getGlobalPlacement())
        )
        invariant = relative.isSame(expected_relative, 1e-7)
        control = stage.Placement.isSame(instrument_mount.stage_placement(pitch), 1e-7)
        rows.append(
            {
                "instrument_pitch_deg": pitch,
                "physical_collisions": collisions,
                "reserved_space_intrusions": reserve_hits,
                "optical_obstructions": field_hits,
                "connector_obstructions": connector_hits,
                "optical_reserved_space_intrusions": field_reserve_hits,
                "connector_reserved_space_clearances": connector_gaps,
                "neighbour_clearance_buffers": neighbours,
                "mounting_tool_access": tools,
                "assembly_registration_checks": registration,
                "native_rotation_matches": control,
                "fc_to_sensor_transform_invariant": invariant,
                "planning_routes_regenerated_for_setup_pose": True,
                "passed": len(rotor) == 2
                and not any(
                    (
                        collisions,
                        reserve_hits,
                        field_hits,
                        connector_hits,
                        field_reserve_hits,
                    )
                )
                and all(
                    row["passed"] for row in connector_gaps + neighbours + registration
                )
                and tools["passed"]
                and control
                and invariant,
            }
        )
    instrument_mount.set_pitch(doc, 0)
    # Co-moving stock is checked above and has a fixed relative transform.
    # Only stock outside the common stage enters the continuous external test.
    external = {
        obj.Name: world_shape(obj)
        for obj in physical
        if not belongs_to_group(obj, stage)
    }
    reservations = {
        obj.Name: world_shape(obj)
        for obj in doc.DesignRegistry.ClearanceVolumes
        if not belongs_to_group(obj, stage)
        and obj.Name
        not in ("PortPhaseLeadLoopReserve", "StarboardPhaseLeadLoopReserve")
    }
    bounds = motion_bounds(group)
    pivot = doc.ElectronicsEquipmentModule.getGlobalPlacement().multVec(V(0, 0, 27.5))
    # A norm bound covers every possible forward projection of the modeled
    # gondola, including the selected sensor's offset from the common pivot.
    body_depth = (
        max(
            (V(x, y, z) - pivot).Length
            for obj in physical
            for box in (world_shape(obj).BoundBox,)
            for x, y, z in itertools.product(
                (box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax)
            )
        )
        + 19
        - 8
        + optical_sensor.SENSOR_BOTTOM_Z
        + profile.optical_origin_min_z_mm
        + math.sqrt(2)
    )
    continuous = []
    for name in (
        f"{profile.key}ContinuousOpticalFieldBound",
        f"{profile.key}ContinuousTrayBound",
        f"{profile.key}ContinuousBodyBound",
        f"{profile.key}ContinuousConnectorBound",
        "OpticalMountToolAccessBound",
    ):
        hits = collision_hits(
            bounds[name],
            {**external, **reservations},
            tolerance=TOL,
            validation_cache=cache,
        )
        continuous.append({"bound": name, "collisions": hits, "passed": not hits})
    return {
        "attachment": "rigid_on_common_instrument_stage",
        "sensor_model": profile.key,
        "sampled_attitudes": rows,
        "continuous_external_bounds": continuous,
        "all_angles_body_depth_upper_bound_mm": body_depth,
        "setup_planning_routes": {
            "objects": ["PortPhaseLeadLoopReserve", "StarboardPhaseLeadLoopReserve"],
            "continuous_connected_wire_motion_claimed": False,
            "checked_setup_angles_deg": pitches,
            "scope": "The two exact saved-current planning routes are source-bound separately. Each sampled setup pose regenerates both complete routes and checks all optical stock, fields and connectors against them. They are not stationary obstacles through adjustment and no interpolated or connected moving harness is qualified. Disconnect and reroute at each selected setup angle.",
        },
        "fc_to_sensor_transform_invariant": all(
            row["fc_to_sensor_transform_invariant"] for row in rows
        ),
        "passed": all(row["passed"] for row in rows + continuous)
        and body_depth <= optical_sensor.OPTICAL_RESERVE_LENGTH_MM + TOL,
        "scope": "All optical stock, sensor alternatives, connector and tool reserves share the FC's bounded native stage. Relative instrument geometry remains fixed; conservative continuous bounds check external solids and all named reserves. The separate instrument-joint audit checks the plate, FC and intended pivot/arc-lock contacts.",
    }


def _saved_sensor_state(doc):
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
        for key, value in properties.items():
            setattr(doc.getObject(name), key, value)


def mtf_sensor_check(doc):
    """Audit the saved common instrument assembly without saving or retaining changes."""
    report = {
        "scope": "One rigid optical bracket shares the FC instrument stage. Both mutually exclusive sensors, complete saved stock, fixed relative transform, continuous external envelopes, two mounting joints and ordered disconnected service are checked. No independent optical pitch or separate rail attachment is modeled. Print fit, clamp retention, FC damper compliance, optical origins and measured calibration remain unqualified."
    }
    evidence = _source_evidence(doc)
    report["source_evidence"] = evidence
    if not evidence["passed"]:
        report["passed"] = False
        return report
    from .propulsion_wiring import check as saved_planning_route_check

    report["saved_planning_routes"] = saved_planning_route_check(doc)
    if not report["saved_planning_routes"]["passed"]:
        report["passed"] = False
        return report
    report["rigid_interface"] = _rigid_interface_checks(doc)
    report["nut_recesses"] = _nut_recess_checks(doc)
    group = doc.OpticalFlowModule
    old_model, old_pitch = str(group.SensorModel), float(doc.InstrumentPitchStage.Pitch)
    state = _saved_sensor_state(doc)
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
            instrument_mount.set_pitch(doc, old_pitch)
            optical_sensor.apply_profile(doc, profile)
            alternatives[key] = _placement_checks(doc, physical, kit, profile=profile)
            alternatives[key]["mounting_service"] = mounting_service_check(
                doc, physical, kit
            )
            alternatives[key]["passed"] &= alternatives[key]["mounting_service"][
                "passed"
            ]
        report.update(selected_sensor_model=old_model, sensor_alternatives=alternatives)
        report["passed"] = (
            report["rigid_interface"]["passed"]
            and report["nut_recesses"]["passed"]
            and all(row["passed"] for row in alternatives.values())
        )
        return report
    finally:
        _restore_sensor_state(doc, state)
        group.SensorModel = old_model
        instrument_mount.set_pitch(doc, old_pitch)
