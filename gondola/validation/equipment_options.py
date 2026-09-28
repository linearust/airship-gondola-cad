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
from gondola.parts import equipment_layout as layout
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
BODY_NAMES = ("ModulePASEnvelope", "ModuleRadioEnvelope")
OPTION_RESERVES = tuple(
    name
    for name, parent in wiring_reserves.RESERVE_PARENTS.items()
    if parent == "AccessoryEquipmentModule"
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


def adhesive_support_check(support, body, centre, size, *, face="top"):
    """Check pad/body placement and plate identity, never inferred carbon contact."""
    from gondola.parts import stock_adapter

    if face not in ("top", "bottom"):
        raise ValueError("Adhesive support face must be 'top' or 'bottom'")
    comparison, source_ok = _matches(
        support, stock_adapter.plate_shape(centre_xy_mm=centre)
    )
    pad = Part.makeBox(*size, 1, V(centre[0] - size[0] / 2, centre[1] - size[1] / 2, 0))
    bounds = body.BoundBox
    footprint = Part.makeBox(
        bounds.XLength, bounds.YLength, 1, V(bounds.XMin, bounds.YMin, 0)
    )
    overlap = intersection_volume(pad, footprint)
    expected = min(size[0], bounds.XLength) * min(size[1], bounds.YLength)
    gap = (
        bounds.ZMin - mounts.SUPPORT_FACE_Z
        if face == "top"
        else stock_adapter.PLATE_BOTTOM_Z - bounds.ZMax
    )
    return {
        "support_face": face,
        "reserved_pad_area_mm2": size[0] * size[1],
        "nominal_body_pad_overlap_mm2": overlap,
        "required_centered_overlap_mm2": expected,
        "source_plate_comparison": comparison,
        "adhesive_allowance_mm": gap,
        "continuous_support_area_verified": False,
        "received_contact_area_mm2": None,
        "physical_contact_qualified": False,
        "scope": "Insulating-pad/body placement reservation and conservative source-plate identity only. Actual cutouts, contact, insulation, compressed pad height, strap retention and bending remain unverified; no filled-model material is treated as a continuous adhesive patch.",
        "passed": source_ok
        and face == "top"
        and expected > 0
        and abs(overlap - expected) < TOL
        and abs(gap - mounts.ADHESIVE_ALLOWANCE) < TOL,
    }


def source_evidence(doc):
    """Reject stale option identities, source envelopes or saved access lanes."""
    parent = doc.getObject("AccessoryEquipmentModule")
    registry = doc.getObject("DesignRegistry")
    if parent is None or registry is None:
        return {"passed": False, "error": "Missing accessory carrier or registry"}
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
            kind = next(
                kind
                for kind, part in mounts.MOUNT_NAMES.items()
                if part == stack_interface.SUPPORTED_HOSTS[name]
            )
            mounts.build_mount(temporary, hosts[name], kind)
        kit = optical_mount.build_optical_mount(temporary, next(iter(hosts.values())))
        for name, host in hosts.items():
            stack_interface.attach_to_host(kit["group"], host)
            # Host changes recreate portal-foot hardware. Reacquire live native
            # objects instead of retaining handles to removed features.
            physical = [
                obj
                for obj in temporary.Objects
                if belongs_to_group(obj, kit["group"])
                and (
                    bool(getattr(obj, "PrintPart", False))
                    or "HardwareSKU" in obj.PropertiesList
                )
            ]
            placement = kit["group"].getGlobalPlacement()
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
                # Pivot fasteners are released first. Only the movable head
                # and sensor lift; the fixed portal stays attached to carbon.
                neutral_sensor = _placed(
                    optical_sensor.envelope_shape(profile),
                    kit["pitch_stage"].getGlobalPlacement(),
                )
                head_sweep, _ = translation_sweep(
                    Part.makeCompound(
                        [
                            world_shape(obj)
                            for obj in kit["printed"]
                            if stack_interface.is_removable_head_part(obj, kit["group"])
                        ]
                        + [neutral_sensor]
                    ),
                    tuple(placement.Rotation.multVec(V(0, 0, 32))),
                )
                screens.append(
                    {
                        "host": name,
                        "sensor": profile.key,
                        "poses": poses,
                        "continuous_field": bound,
                        "service": [("ReleasedMovingHeadLift", head_sweep)],
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
    """Screen every selected navigation/radio combination without saving CAD."""
    evidence = source_evidence(doc)
    if not evidence["passed"]:
        return {"source_evidence": evidence, "passed": False}
    registry = doc.DesignRegistry
    parent = doc.AccessoryEquipmentModule
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
    supports = {
        BODY_NAMES[0]: local_shape(doc.StockNavigationAdapter),
        BODY_NAMES[1]: local_shape(doc.StockRadioAdapter),
    }
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
                    supports[BODY_NAMES[1]],
                    local_bodies[BODY_NAMES[1]],
                    mounts.RADIO_CENTRE_XY,
                    mounts.RADIO_ADHESIVE_SIZE,
                    face="top",
                ),
            }
        ]
        support_rows.append(
            {
                "device": BODY_NAMES[0],
                **adhesive_support_check(
                    supports[BODY_NAMES[0]],
                    local_bodies[BODY_NAMES[0]],
                    mounts.NAVIGATION_CENTRE_XY,
                    mounts.GPS_ADHESIVE_SIZE,
                ),
            }
        )
        service = []
        for name, shape in bodies.items():
            service_fixed = fixed
            local_travel = V(*layout.device_removal_vector(name))
            world_travel = placement.Rotation.multVec(local_travel)
            sweep, method = translation_sweep(shape, tuple(world_travel))
            collisions = collision_hits(
                sweep,
                {
                    **service_fixed,
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
                    "local_removal_vector_mm": tuple(local_travel),
                    "world_removal_vector_mm": tuple(world_travel),
                    "bench_access_required": False,
                    "service_collision_scope": "Installed assembly; carbon plates retained",
                    "off_carrier_parts_excluded_for_bench_service": sorted(
                        set(fixed) - set(service_fixed)
                    ),
                    "prerequisite": "Disconnect leads and release retention; lift the bare device from the outer support face. Carbon plates and all other mounted parts remain. No connected-harness service is claimed.",
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
                "bare_device_service": service,
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
        "scope": "Three mutually exclusive navigation choices with the LR24-F-Mini on the same outer face, both optical models and both carbon-mounted optical hosts. Separate identical bought plates support navigation and radio. Fixed portals remain; only movable optical heads can be released. This audit does not qualify adhesive, actual connectors, radio/compass performance, electrical capacity or a remote antenna installation. Disconnect leads and remove direct antenna before bare-device service. The accessory plates are not optical hosts.",
        "passed": len(rows) == len(NAVIGATION_PROFILES) * len(RADIO_PROFILES)
        and bool(rows)
        and all(row["passed"] for row in rows),
    }
