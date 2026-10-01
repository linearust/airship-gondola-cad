"""Read-only substitution checks for mutually exclusive equipment regions.

Alternative purchased envelopes are evaluated without replacing saved objects.
Source-generated optical poses screen only the changed equipment; the complete
saved optical assembly retains its independent, more detailed optical audit.
"""

import itertools
import json

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, placed_shape, world_shape
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
    optical_interface,
    optical_mount,
    optical_sensor,
    wiring_reserves,
)
from gondola.print_export import geometry_comparison

from .evidence import comparison_passed
from .geometry import intersection_volume, local_shape, translation_sweep
from .optical import ANGLES, _external_field_bound
from .optical_service import pitch_tool_shape
from .wiring import collision_hits, measure_clearances, named_gap_checks

V = App.Vector
TOL = 1e-5
BODY_NAMES = ("ModulePASEnvelope", "ModuleRadioEnvelope")
OPTION_RESERVES = tuple(
    name
    for name, parent in wiring_reserves.RESERVE_PARENTS.items()
    if parent == "AccessoryEquipmentModule"
)


def _matches(first, second):
    comparison = geometry_comparison(first, second)
    return comparison, comparison_passed(comparison, TOL)


def adhesive_support_check(support, body, centre, size, *, face="top"):
    """Check intact printed pad and actual nominal plan overlap, not full coverage.

    Adhesive contact may be smaller than the purchased module footprint. Check
    the declared intact patch without enlarging the purchased module envelope.
    All shapes are expressed in the same carrier-local frame.
    """
    if face not in ("top", "bottom"):
        raise ValueError("Adhesive support face must be 'top' or 'bottom'")
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
    gap = (
        bounds.ZMin - mounts.SUPPORT_FACE_Z
        if face == "top"
        else mounts.DECK_BOTTOM_Z - bounds.ZMax
    )
    correct_side = gap >= -TOL
    return {
        "support_face": face,
        "continuous_support_area_mm2": size[0] * size[1],
        "nominal_supported_overlap_mm2": overlap,
        "required_centered_overlap_mm2": expected,
        "missing_pad_material_mm3": missing,
        "adhesive_allowance_mm": gap,
        "body_on_requested_side": correct_side,
        "scope": "Nominal plan overlap only. Trim adhesive to supported contact; actual backside contact, component loading, insulation and retention are unqualified.",
        "passed": missing < TOL
        and expected > 0
        and abs(overlap - expected) < TOL
        and correct_side
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
            world_shape(obj),
            placed_shape(factory(profile), parent.getGlobalPlacement()),
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
            world_shape(obj), placed_shape(expected[name], parent.getGlobalPlacement())
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
    """Both sensors at the saved carrier attachment, without mutating CAD."""
    temporary = App.newDocument("EquipmentOptionOpticalScreens")
    screens = []
    try:
        selected = doc.OpticalFlowModule
        parent = selected.getParentGeoFeatureGroup()
        host = temporary.addObject("App::Part", parent.Name)
        host.Placement = parent.getGlobalPlacement()
        kit = optical_mount.build_optical_mount(
            temporary, host, str(selected.MountSide)
        )
        physical = kit["printed"] + kit["hardware"]
        for profile in SENSOR_PROFILES.values():
            poses = []
            for pitch in ANGLES:
                optical_mount.set_pitch(temporary, pitch)
                pose = kit["pitch_stage"].getGlobalPlacement()
                shapes = {obj.Name: world_shape(obj) for obj in physical}

                def registered_shape(shape):
                    pitched = placed_shape(shape, kit["pitch_stage"].Placement)
                    return placed_shape(
                        optical_interface.registration_bound(pitched),
                        kit["group"].getGlobalPlacement(),
                    )

                shapes["ModuleMTF02PEnvelope"] = registered_shape(
                    optical_sensor.envelope_shape(profile)
                )
                poses.append(
                    {
                        "pitch_deg": pitch,
                        "physical": shapes,
                        "field": placed_shape(
                            optical_sensor.optical_reserve_shape(profile), pose
                        ),
                        "connector": registered_shape(
                            optical_sensor.connector_reserve_shape(profile)
                        ),
                        "pitch_tool": placed_shape(
                            optical_interface.registration_bound(pitch_tool_shape()),
                            kit["group"].getGlobalPlacement(),
                        ),
                    }
                )
            optical_mount.set_pitch(temporary, 0)
            bound, _ = _external_field_bound(kit["group"], profile)
            screens.append(
                {
                    "carrier_mount": (
                        selected.CarrierHostName,
                        str(selected.MountSide),
                    ),
                    "sensor": profile.key,
                    "poses": poses,
                    "continuous_field": bound,
                }
            )
        return screens
    finally:
        App.closeDocument(temporary.Name)


def _optical_option_check(
    screens,
    obstacles,
    *,
    antenna=False,
    validation_cache=None,
    required_mount=None,
    navigation_key=None,
):
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
                "OpticalPitchToolAccess": pose["pitch_tool"],
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
        rows.append(
            {
                "carrier_mount": screen["carrier_mount"],
                "sensor_model": screen["sensor"],
                "sampled_attitudes": samples,
                "continuous_external_field_collisions": bound_hits,
                "continuous_external_field_clearances": bound_clearances,
                "remove_direct_antenna_before_service": antenna,
                "passed": not bound_hits and all(row["passed"] for row in samples),
            }
        )
    selection_ok = required_mount is None or all(
        row["carrier_mount"] == required_mount for row in rows
    )
    return {
        "sensor_screens": rows,
        "required_installed_carrier_mount": required_mount,
        "installed_carrier_mount_matches": selection_ok,
        "configuration_scope": "Optical foot on the saved carrier and side, including conservative XY/yaw registration of both sensor bodies and connectors; all navigation substitutions are screened against both optical sensors. Remote antenna location and harness remain unmodeled. Carrier/side changes require renewed checks.",
        "passed": len(rows) == len(SENSOR_PROFILES)
        and all(row["passed"] for row in rows)
        and selection_ok,
    }


def _body_and_connector_collisions(bodies, reserves, fixed, fixed_reserves):
    """Retain ordered collision evidence for each body and connector reserve."""
    hits = []
    for moving in (bodies, reserves):
        for name, shape in moving.items():
            obstacles = {**fixed, **fixed_reserves}
            for group in (bodies, reserves):
                obstacles.update(
                    (other, target)
                    for other, target in group.items()
                    if group is not moving or other != name
                )
            hits.extend(
                {"source": name, **hit}
                for hit in collision_hits(shape, obstacles, tolerance=TOL)
            )
    return hits


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
    support = local_shape(doc.AccessoryMount)
    bench_fixed = {
        obj.Name: fixed[obj.Name]
        for obj in physical
        if obj.Name in fixed and belongs_to_group(obj, parent)
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
            name: placed_shape(shape, placement) for name, shape in local_bodies.items()
        }
        reserves = {
            name: placed_shape(shape, placement)
            for name, shape in wiring_reserves.reserve_shapes(navigation, radio).items()
            if name in OPTION_RESERVES and name != "NavigationDirectAntennaReserve"
        }
        hits = _body_and_connector_collisions(bodies, reserves, fixed, fixed_reserves)
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
                "centre_xy_mm": centre,
                "size_xy_mm": size,
                **adhesive_support_check(
                    support,
                    local_bodies[BODY_NAMES[1]],
                    centre,
                    size,
                    face="bottom",
                ),
            }
            for centre, size in mounts.RADIO_ADHESIVE_REGIONS
        ]
        if navigation.key != "PAS":
            support_rows.extend(
                {
                    "device": BODY_NAMES[0],
                    "centre_xy_mm": centre,
                    "size_xy_mm": size,
                    **adhesive_support_check(
                        support,
                        local_bodies[BODY_NAMES[0]],
                        centre,
                        size,
                    ),
                }
                for centre, size in mounts.GPS_ADHESIVE_REGIONS
            )
        service = []
        for name, shape in bodies.items():
            detached_carrier = name == "ModuleRadioEnvelope"
            service_fixed = bench_fixed if detached_carrier else fixed
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
                    "bench_access_required": detached_carrier,
                    "service_collision_scope": "Detached carrier assembly only"
                    if detached_carrier
                    else "Installed assembly after releasing device retention",
                    "off_carrier_parts_excluded_for_bench_service": sorted(
                        set(fixed) - set(service_fixed)
                    ),
                    "prerequisite": "Disconnect leads and release retention. For the underside radio, detach the carrier from the rail for bench access; in-place underside access is not qualified.",
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
            direct = placed_shape(direct, placement)
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
                navigation_key=navigation.key,
                validation_cache=validation_cache,
                required_mount=(
                    (
                        doc.OpticalFlowModule.CarrierHostName,
                        str(doc.OpticalFlowModule.MountSide),
                    )
                    if navigation.key == get_navigation_profile().key
                    else None
                ),
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
        "scope": "Three mutually exclusive navigation choices with the underside LR24-F-Mini air unit and both optical models. Both optical sensors are screened at the saved carrier and side. One accessory plate supports navigation and radio; this geometry audit does not qualify adhesive, actual connectors, radio/compass performance, electrical capacity or a remote antenna installation. Disconnect leads and remove direct antenna before bare-device service. Detach the carrier for underside-radio bench access. Optical carrier relocation is a separate assembly change requiring renewed checks.",
        "passed": len(rows) == len(NAVIGATION_PROFILES) * len(RADIO_PROFILES)
        and bool(rows)
        and all(row["passed"] for row in rows),
    }
