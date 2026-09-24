"""Read-only substitution checks for mutually exclusive equipment regions.

Alternative purchased envelopes are evaluated without replacing saved objects.
Source-generated optical poses screen only the changed equipment; the complete
saved optical assembly retains its independent, more detailed optical audit.
"""

import itertools
import json

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, world_shape
from gondola.contracts.equipment_options import (
    NAVIGATION_PROFILES,
    RADIO_PROFILES,
    get_navigation_profile,
    get_radio_profile,
)
from gondola.contracts.optical_sensors import SENSOR_PROFILES
from gondola.parts import (
    equipment_envelopes as devices,
)
from gondola.parts import (
    equipment_mounts as mounts,
)
from gondola.parts import (
    optical_mount,
    optical_sensor,
    stack_interface,
    wiring_reserves,
)
from gondola.print_export import geometry_comparison

from .geometry import intersection_volume, local_shape, translation_sweep
from .optical import ANGLES, _external_field_bound
from .wiring import collision_hits, measure_clearances, named_gap_checks

V = App.Vector
TOL = 1e-5
BODY_NAMES = ("ModulePASEnvelope", "ModuleLR900Envelope")
OPTION_RESERVES = (
    "PASConnectorReserve",
    "LR900NegativeXConnectorReserve",
    "LR900PositiveXConnectorReserve",
    "NavigationDirectAntennaReserve",
)


def _placed(shape, placement):
    result = shape.copy()
    result.Placement = placement.multiply(result.Placement)
    return result


def _matches(first, second):
    comparison = geometry_comparison(first, second)
    return comparison, all(
        comparison[key] < TOL
        for key in ("difference_mm3", "bounds_difference_mm", "volume_difference_mm3")
    )


def adhesive_support_check(support, body, centre, size):
    """Check intact printed pad and actual nominal plan overlap, not full coverage.

    The shorter LR24 body covers 24 of the 26 mm pad length. That is valid support
    with trimmed adhesive, not a reason to enlarge the purchased module envelope.
    All shapes are expressed in the same carrier-local frame.
    """
    pad = Part.makeBox(
        *size,
        mounts.DECK_THICKNESS,
        V(centre[0] - size[0] / 2, centre[1] - size[1] / 2, mounts.DECK_BOTTOM_Z),
    )
    bounds = body.BoundBox
    footprint = Part.makeBox(
        bounds.XLength,
        bounds.YLength,
        mounts.DECK_THICKNESS,
        V(bounds.XMin, bounds.YMin, mounts.DECK_BOTTOM_Z),
    )
    missing = abs(pad.cut(support).Volume)
    overlap = intersection_volume(pad, footprint) / mounts.DECK_THICKNESS
    expected = min(size[0], bounds.XLength) * min(size[1], bounds.YLength)
    gap = bounds.ZMin - mounts.SUPPORT_FACE_Z
    return {
        "continuous_support_area_mm2": size[0] * size[1],
        "nominal_supported_overlap_mm2": overlap,
        "required_centered_overlap_mm2": expected,
        "missing_pad_material_mm3": missing,
        "adhesive_allowance_mm": gap,
        "scope": "Nominal plan overlap only. Trim adhesive to supported contact; actual backside contact, component loading, insulation and retention are unqualified.",
        "passed": missing < TOL
        and expected > 0
        and abs(overlap - expected) < TOL
        and abs(gap - mounts.ADHESIVE_ALLOWANCE) < TOL,
    }


def source_evidence(doc):
    """Reject stale option identities, source envelopes or saved access lanes."""
    parent = doc.getObject("ElectronicsEquipmentModule")
    registry = doc.getObject("DesignRegistry")
    if parent is None or registry is None:
        return {"passed": False, "error": "Missing electronics carrier or registry"}
    rows = []
    for name, profile, factory, field in (
        (
            BODY_NAMES[0],
            get_navigation_profile(),
            devices.navigation_envelope_shape,
            "NavigationProfile",
        ),
        (
            BODY_NAMES[1],
            get_radio_profile(),
            devices.radio_envelope_shape,
            "RadioProfile",
        ),
    ):
        obj = doc.getObject(name)
        if obj is None:
            rows.append({"object": name, "passed": False, "error": "Missing device"})
            continue
        comparison, geometry_ok = _matches(
            world_shape(obj), _placed(factory(profile), parent.getGlobalPlacement())
        )
        try:
            metadata_ok = json.loads(str(getattr(obj, field))) == json.loads(
                json.dumps(profile.contract())
            )
            metadata_ok &= (
                str(getattr(obj, field.replace("Profile", "Model"))) == profile.key
            )
        except (AttributeError, TypeError, ValueError):
            metadata_ok = False
        rows.append(
            {
                "object": name,
                "source_comparison": comparison,
                "profile_metadata_matches": metadata_ok,
                "passed": geometry_ok
                and metadata_ok
                and obj.getParentGeoFeatureGroup() == parent
                and obj in registry.ReferenceParts
                and obj not in registry.PrintedParts
                and obj not in registry.HardwareParts,
            }
        )
    expected = wiring_reserves.reserve_shapes()
    contracts = wiring_reserves.reserve_contracts()
    for name in OPTION_RESERVES:
        obj = doc.getObject(name)
        if name not in expected:
            rows.append(
                {
                    "object": name,
                    "absent_for_selected_profile": obj is None,
                    "passed": obj is None,
                }
            )
            continue
        if obj is None:
            rows.append(
                {"object": name, "passed": False, "error": "Missing reservation"}
            )
            continue
        comparison, geometry_ok = _matches(
            world_shape(obj), _placed(expected[name], parent.getGlobalPlacement())
        )
        try:
            metadata_ok = json.loads(str(obj.WiringContract)) == json.loads(
                json.dumps(contracts[name])
            )
        except (AttributeError, TypeError, ValueError):
            metadata_ok = False
        rows.append(
            {
                "object": name,
                "source_comparison": comparison,
                "contract_matches": metadata_ok,
                "passed": geometry_ok
                and metadata_ok
                and obj in registry.ClearanceVolumes
                and obj.getParentGeoFeatureGroup() == parent,
            }
        )
    return {"objects": rows, "passed": all(row["passed"] for row in rows)}


def _optical_screens(doc):
    """Build both sensor/host pose screens in a separate, disposable document."""
    temporary = App.newDocument("EquipmentOptionOpticalScreens")
    screens = []
    try:
        hosts = {}
        for name in stack_interface.SUPPORTED_HOSTS:
            hosts[name] = temporary.addObject("App::Part", name)
            hosts[name].Placement = doc.getObject(name).getGlobalPlacement()
        kit = optical_mount.build_optical_mount(temporary, next(iter(hosts.values())))
        physical = kit["printed"] + kit["hardware"]
        for name, host in hosts.items():
            stack_interface.attach_to_host(kit["group"], host)
            placement = kit["group"].getGlobalPlacement()
            service = [
                (tool, _placed(shape, placement))
                for tool, shape in stack_interface.clamp_tool_reservations()
            ]
            for index in range(2):
                for kind, z in (("Bolt", -12), ("Nut", 4)):
                    obj = temporary.getObject(f"OpticalStackFoot{kind}{index}")
                    swept, _ = translation_sweep(
                        world_shape(obj), tuple(placement.Rotation.multVec(V(0, 0, z)))
                    )
                    service.append((obj.Name + "Removal", swept))
            for profile in SENSOR_PROFILES.values():
                poses = []
                for roll, pitch in itertools.product(ANGLES, repeat=2):
                    optical_mount.set_angles(temporary, roll, pitch)
                    pitch_placement = kit["pitch_stage"].getGlobalPlacement()
                    shapes = {obj.Name: world_shape(obj) for obj in physical}
                    shapes["ModuleMTF02PEnvelope"] = _placed(
                        optical_sensor.envelope_shape(profile), pitch_placement
                    )
                    poses.append(
                        {
                            "roll_deg": roll,
                            "pitch_deg": pitch,
                            "physical": shapes,
                            "field": _placed(
                                optical_sensor.optical_reserve_shape(profile),
                                pitch_placement,
                            ),
                            "connector": _placed(
                                optical_sensor.connector_reserve_shape(profile),
                                pitch_placement,
                            ),
                        }
                    )
                optical_mount.set_angles(temporary, 0, 0)
                bound, _ = _external_field_bound(kit["group"], profile)
                tower_sweep, _ = translation_sweep(
                    Part.makeCompound([world_shape(obj) for obj in physical]),
                    tuple(placement.Rotation.multVec(V(0, 0, 32))),
                )
                screens.append(
                    {
                        "host": name,
                        "sensor": profile.key,
                        "poses": poses,
                        "continuous_field": bound,
                        "service": service + [("CompleteTowerLift", tower_sweep)],
                    }
                )
        return screens
    finally:
        App.closeDocument(temporary.Name)


def _optical_option_check(screens, obstacles, *, antenna=False, validation_cache=None):
    validation_cache = {} if validation_cache is None else validation_cache
    rows = []
    for screen in screens:
        samples = []
        for pose in screen["poses"]:
            hits = []
            for name, shape in {
                **pose["physical"],
                "OpticalField": pose["field"],
                "OpticalConnector": pose["connector"],
            }.items():
                hits.extend(
                    {"moving": name, **hit}
                    for hit in collision_hits(
                        shape,
                        obstacles,
                        tolerance=TOL,
                        validation_cache=validation_cache,
                    )
                )
            gaps = measure_clearances(
                pose["connector"],
                {
                    name: shape
                    for name, shape in obstacles.items()
                    if name in OPTION_RESERVES
                },
                minimum_gap_mm=wiring_reserves.CONNECTOR_SERVICE_GAP_MM,
                tolerance=TOL,
                validation_cache=validation_cache,
            )
            samples.append(
                {
                    "roll_deg": pose["roll_deg"],
                    "pitch_deg": pose["pitch_deg"],
                    "collisions": hits,
                    "connector_service_clearances": gaps,
                    "passed": not hits and all(row["passed"] for row in gaps),
                }
            )
        bound_clearances = measure_clearances(
            screen["continuous_field"],
            obstacles,
            minimum_gap_mm=wiring_reserves.CONNECTOR_SERVICE_GAP_MM if antenna else 0.0,
            tolerance=TOL,
            validation_cache=validation_cache,
        )
        bound_hits = [row for row in bound_clearances if not row["passed"]]
        # Direct antenna is removed before servicing the tower; its installed
        # field and mechanism clearance is still checked above.
        service_hits = (
            []
            if antenna
            else [
                {"tool_or_sweep": name, **hit}
                for name, shape in screen["service"]
                for hit in collision_hits(
                    shape, obstacles, tolerance=TOL, validation_cache=validation_cache
                )
            ]
        )
        rows.append(
            {
                "host": screen["host"],
                "sensor_model": screen["sensor"],
                "sampled_attitudes": samples,
                "continuous_external_field_collisions": bound_hits,
                "continuous_external_field_clearances": bound_clearances,
                "tower_service_collisions": service_hits,
                "remove_direct_antenna_before_service": antenna,
                "passed": not bound_hits
                and not service_hits
                and all(row["passed"] for row in samples),
            }
        )
    return {
        "hosts_and_sensors": rows,
        "passed": len(rows) == 4 and all(row["passed"] for row in rows),
    }


def compatibility_check(doc):
    """Screen all six navigation/radio combinations, never mutate or save CAD."""
    evidence = source_evidence(doc)
    if not evidence["passed"]:
        return {"source_evidence": evidence, "passed": False}
    registry = doc.DesignRegistry
    parent = doc.ElectronicsEquipmentModule
    placement = parent.getGlobalPlacement()
    physical = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    fixed = {
        obj.Name: world_shape(obj)
        for obj in physical
        if obj.Name not in BODY_NAMES
        and not belongs_to_group(obj, doc.OpticalFlowModule)
    }
    fixed_reserves = {
        obj.Name: world_shape(obj)
        for obj in registry.ClearanceVolumes
        if obj.Name not in OPTION_RESERVES
        and not belongs_to_group(obj, doc.OpticalFlowModule)
    }
    support = local_shape(doc.ElectronicsMount)
    screens = _optical_screens(doc)
    validation_cache = {}
    rows = []
    for navigation, radio in itertools.product(
        NAVIGATION_PROFILES.values(), RADIO_PROFILES.values()
    ):
        local_bodies = {
            BODY_NAMES[0]: devices.navigation_envelope_shape(navigation),
            BODY_NAMES[1]: devices.radio_envelope_shape(radio),
        }
        bodies = {
            name: _placed(shape, placement) for name, shape in local_bodies.items()
        }
        reserves = {
            name: _placed(shape, placement)
            for name, shape in wiring_reserves.reserve_shapes(navigation, radio).items()
            if name in OPTION_RESERVES and name != "NavigationDirectAntennaReserve"
        }
        hits = []
        for name, shape in bodies.items():
            obstacles = {
                **fixed,
                **fixed_reserves,
                **{other: target for other, target in bodies.items() if other != name},
                **reserves,
            }
            hits.extend(
                {"source": name, **hit}
                for hit in collision_hits(shape, obstacles, tolerance=TOL)
            )
        for name, shape in reserves.items():
            obstacles = {
                **fixed,
                **fixed_reserves,
                **bodies,
                **{
                    other: target for other, target in reserves.items() if other != name
                },
            }
            hits.extend(
                {"source": name, **hit}
                for hit in collision_hits(shape, obstacles, tolerance=TOL)
            )
        buffers = named_gap_checks(
            {**fixed, **fixed_reserves, **bodies, **reserves},
            {
                "FCWiringClearanceReserve": {
                    name: gap
                    for name, gap in wiring_reserves.MINIMUM_NEIGHBOUR_GAPS[
                        "FCWiringClearanceReserve"
                    ].items()
                    if name in BODY_NAMES
                }
            },
            tolerance=TOL,
            validation_cache=validation_cache,
        )
        support_rows = [
            {
                "device": BODY_NAMES[1],
                **adhesive_support_check(
                    support,
                    local_bodies[BODY_NAMES[1]],
                    mounts.LR_CENTRE_XY,
                    mounts.LR_ADHESIVE_SIZE,
                ),
            }
        ]
        if navigation.key != "PAS":
            support_rows.append(
                {
                    "device": BODY_NAMES[0],
                    **adhesive_support_check(
                        support,
                        local_bodies[BODY_NAMES[0]],
                        mounts.GPS_CENTRE_XY,
                        mounts.GPS_ADHESIVE_SIZE,
                    ),
                }
            )
        service = []
        for name, shape in bodies.items():
            sweep, method = translation_sweep(
                shape, tuple(placement.Rotation.multVec(V(0, 0, 32)))
            )
            collisions = collision_hits(
                sweep,
                {
                    **fixed,
                    **{
                        other: target
                        for other, target in bodies.items()
                        if other != name
                    },
                },
                tolerance=TOL,
            )
            service.append(
                {
                    "device": name,
                    "method": method,
                    "collisions": collisions,
                    "passed": not collisions,
                }
            )
        optical = _optical_option_check(
            screens, {**bodies, **reserves}, validation_cache=validation_cache
        )
        antenna = None
        direct = wiring_reserves.direct_antenna_reserve_shape(navigation)
        if direct is not None:
            direct = _placed(direct, placement)
            collisions = collision_hits(
                direct,
                {
                    **fixed,
                    **fixed_reserves,
                    BODY_NAMES[1]: bodies[BODY_NAMES[1]],
                    **{
                        name: shape
                        for name, shape in reserves.items()
                        if name != "PASConnectorReserve"
                    },
                },
                tolerance=TOL,
            )
            optics = _optical_option_check(
                screens,
                {"NavigationDirectAntennaReserve": direct},
                antenna=True,
                validation_cache=validation_cache,
            )
            antenna = {
                "installed_clearance_collisions": collisions,
                "optical_clearance": optics,
                "scope": "Conservative possible SMA positions and antenna height, not an exact installation. Direct antenna points along CAD +Z, away from balloon; mechanical screening does not validate GNSS reception. Remote antenna is off-gondola and unplaced. Remove direct antenna before bench servicing.",
                "passed": not collisions and optics["passed"],
            }
        rows.append(
            {
                "navigation_model": navigation.key,
                "radio_model": radio.key,
                "body_and_connector_collisions": hits,
                "neighbour_clearance_buffers": buffers,
                "adhesive_supports": support_rows,
                "bare_device_service_after_tower_release": service,
                "optical_compatibility": optical,
                "direct_antenna": antenna,
                "passed": not hits
                and all(row["passed"] for row in buffers)
                and all(row["passed"] for row in support_rows + service)
                and optical["passed"]
                and (antenna is None or antenna["passed"]),
            }
        )
    return {
        "source_evidence": evidence,
        "combinations": rows,
        "scope": "Six mutually exclusive navigation/radio combinations, both optical models and both hosts. Printed supports are shared; this geometry audit does not qualify adhesive, actual connectors, radio/compass performance, electrical capacity or a remote antenna installation. Disconnect leads, remove direct antenna and release the complete optical tower before bare-device service.",
        "passed": len(rows) == 6 and all(row["passed"] for row in rows),
    }
