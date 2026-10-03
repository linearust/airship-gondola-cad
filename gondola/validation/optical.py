"""Saved evidence for a rigid optical head on the shared FC instrument platform.

Both sensor alternatives follow the same native stage as the FC. Sampled
internal contacts supplement conservative continuous external envelopes; neither
is a qualification of print fit, clamp retention, cable flex or calibration.
"""

import itertools
import json

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, placed_shape, world_shape
from gondola.contracts.optical_sensors import SENSOR_PROFILES, get_sensor_profile
from gondola.parts import (
    instrument_mount,
    optical_mount,
    optical_sensor,
    propulsion_wiring,
    wiring_reserves,
)
from gondola.print_export import geometry_comparison

from .evidence import comparison_passed
from .geometry import intersection_volume, local_shape
from .optical_envelopes import PITCH_SAMPLE_ANGLES, instrument_context, motion_bounds
from .optical_service import mounting_service_check
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
            "InstrumentMountParts",
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
        "OpticalSensorTray",
        "OpticalFootBolt1",
        "OpticalFootBolt2",
        "OpticalFootNut1",
        "OpticalFootNut2",
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
        support = doc.ElectronicsMount
        inventory["integral_support"] = (
            list(registry.PrintedParts).count(support) == 1
            and list(registry.InstrumentMountParts).count(support) == 1
            and list(registry.EquipmentMounts).count(support) == 1
            and support not in registry.HardwareParts
            and support not in registry.ReferenceParts
            and support not in registry.ClearanceVolumes
            and getattr(support, "PrintSKU", "") == "InstrumentCarrier"
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
    """Independent stock witnesses for the integral bridge and adhesive pad."""
    shape = local_shape(doc.ElectronicsMount)
    witnesses = [
        ("negative_diagonal_post", Part.makeBox(4, 4, 22, V(-31.5, -31.5, 19))),
        ("positive_diagonal_post", Part.makeBox(4, 4, 22, V(27.5, 27.5, 19))),
        ("continuous_adhesive_pad", Part.makeBox(18, 12, 2, V(-9, -6, 42))),
    ]
    diagonal_length = 62 * 2**0.5
    roof = Part.makeBox(diagonal_length, 5, 3, V(-diagonal_length / 2, -2.5, 41))
    roof.rotate(V(), V(0, 0, 1), 45)
    witnesses.append(("diagonal_roof", roof))
    rows = []
    for name, witness in witnesses:
        missing = abs(witness.cut(shape).Volume)
        rows.append(
            {"kind": name, "missing_stock_mm3": missing, "passed": missing <= TOL}
        )
    # Complete36mm-square underbody footprint, not only a narrow wire lane.
    underbody = Part.makeBox(36, 36, 8, V(-18, -18, 19))
    underbody.rotate(V(), V(0, 0, 1), -45)
    intrusion = intersection_volume(shape, underbody)
    wire = wiring_reserves.reserve_shapes()["FCWiringClearanceReserve"]
    wire_intrusion = intersection_volume(shape, wire)
    # Empty channel beneath the optical bridge remains available for FC
    # service. It is independent of any source-generated cavity or mesh.
    channel = Part.makeBox(16, 57, 21.5, V(-8, -28.5, 19.5))
    channel_intrusion = intersection_volume(shape, channel)
    sensor_floor = local_shape(doc.ModuleMTF02PEnvelope).BoundBox.ZMin
    adhesive_gap = sensor_floor - 44
    return {
        "support": "ElectronicsMount",
        "witnesses": rows,
        "fc_underbody_intrusion_mm3": intrusion,
        "fc_connector_and_wire_intrusion_mm3": wire_intrusion,
        "central_channel_intrusion_mm3": channel_intrusion,
        "nominal_adhesive_allowance_mm": adhesive_gap,
        "passed": all(row["passed"] for row in rows)
        and intrusion <= TOL
        and wire_intrusion <= TOL
        and channel_intrusion <= TOL
        and abs(adhesive_gap - 1) <= TOL,
        "scope": "The optical pad, one 5×3 mm diagonal roof beam and two 4×4 mm posts are one solid with the FC carrier. Independent literal stock and clearance witnesses preserve the continuous 18×12×2 mm pad, full FC underbody and central channel. No foot fasteners, independent hinge or inferred self-alignment are credited. Printed stiffness, adhesive retention and actual sensor registration remain unqualified.",
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
        for name, shape in (
            ("body", optical_sensor.envelope_shape(profile)),
            ("connector", optical_sensor.connector_reserve_shape(profile)),
        ):
            bound = placed_shape(shape, frame.getGlobalPlacement())
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
        - 8
        + optical_sensor.SENSOR_BOTTOM_Z
        + profile.optical_origin_min_z_mm
    )
    continuous = []
    for name in (
        f"{profile.key}ContinuousOpticalFieldBound",
        f"{profile.key}ContinuousBodyBound",
        f"{profile.key}ContinuousConnectorBound",
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
        "scope": "Both optical sensor alternatives and connector reserves share the FC's bounded native stage. The complete integral carrier is source-bound and checked by the instrument audit. Relative instrument geometry remains fixed; conservative continuous bounds check external solids and all named reserves. The separate instrument-joint audit checks the plate, FC and intended pivot/arc-lock contacts.",
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
        "scope": "One integral carrier supports FC and optical sensor on the common pitch stage. Both mutually exclusive sensors, complete saved stock, fixed relative transform, continuous external envelopes and disconnected sensor service are checked. No separate optical bracket, foot fasteners or independent pitch is modeled. Print fit, clamp retention, adhesive positioning, FC damper compliance, optical origins and measured calibration remain unqualified."
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
        report["passed"] = report["rigid_interface"]["passed"] and all(
            row["passed"] for row in alternatives.values()
        )
        return report
    finally:
        _restore_sensor_state(doc, state)
        group.SensorModel = old_model
        instrument_mount.set_pitch(doc, old_pitch)
