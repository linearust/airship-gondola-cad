"""Read-only substitution checks for mutually exclusive equipment regions.

Alternative purchased envelopes are evaluated without replacing saved objects.
Actual saved instrument descendants screen the changed equipment; the complete
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
    instrument_mount,
    optical_interface,
    optical_sensor,
    wiring_reserves,
)
from gondola.print_export import geometry_comparison

from .evidence import comparison_passed
from .geometry import intersection_volume, local_shape, translation_sweep
from .instrument import certify_pitch_clearance
from .optical_envelopes import (
    PITCH_SAMPLE_ANGLES,
    instrument_context,
    motion_bounds,
    pitch_bound,
)
from .optical_service import mount_tool_shapes
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


def _optical_attachment(doc):
    """Bind the rigid sensor head to the actual shared instrument stage."""
    selected = doc.getObject("OpticalFlowModule")
    module, stage, frame, _ = instrument_context(selected)
    return {
        "mechanism": "rigid optical head on common FC instrument platform",
        "native_parent": stage.Name,
        "fixed_sensor_frame": frame.Name,
        "rail_module": module.Name,
        "rail_station_x_mm": float(module.RailPositionX),
        "instrument_pitch_range_deg": (-20.0, 20.0),
        "origin_cad_mm": tuple(selected.getGlobalPlacement().Base),
    }


def _optical_screens(doc):
    """Both sensors with actual saved platform descendants; never mutate CAD."""
    attachment = _optical_attachment(doc)
    selected = doc.OpticalFlowModule
    module, stage, frame, _ = instrument_context(selected)
    registry = doc.DesignRegistry
    for index in (1, 2):
        for kind, sku in (("Bolt", "M2X8_BUTTON_HEAD"), ("Nut", "M2_HEX_NUT")):
            obj = doc.getObject(f"OpticalFoot{kind}{index}")
            if (
                obj is None
                or obj not in registry.HardwareParts
                or obj.getParentGeoFeatureGroup() != selected
                or getattr(obj, "HardwareSKU", None) != sku
                or not hasattr(obj, "Shape")
                or obj.Shape.isNull()
                or not obj.Shape.isValid()
                or not obj.Shape.Solids
            ):
                raise ValueError(
                    "Incomplete or inconsistent saved optical mount hardware"
                )
    physical = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    inverse = stage.getGlobalPlacement().inverse()

    def in_stage(obj):
        shape = world_shape(obj)
        shape.Placement = inverse.multiply(shape.Placement)
        return shape

    moving = {
        obj.Name: in_stage(obj) for obj in physical if belongs_to_group(obj, stage)
    }
    moving_reserves = {
        obj.Name: in_stage(obj)
        for obj in registry.ClearanceVolumes
        if belongs_to_group(obj, stage) and not belongs_to_group(obj, selected)
    }
    if "ModuleFCEnvelope" not in moving or "ElectronicsMount" not in moving:
        raise ValueError("Incomplete saved common instrument physical inventory")
    optical_frame = selected.Placement.multiply(frame.Placement)
    all_bounds = motion_bounds(selected)
    for name, shape in {**moving, **moving_reserves}.items():
        if name in ("OpticalSensorTray", "ModuleMTF02PEnvelope"):
            continue  # These two solids have tighter registered optical bounds.
        relative = shape.copy()
        relative.translate(V(0, 0, -8))
        bound = pitch_bound(relative, 20)
        bound.translate(V(0, 0, 27.5))
        all_bounds["Instrument/" + name] = placed_shape(
            bound, module.getGlobalPlacement()
        )
    screens = []
    for profile in SENSOR_PROFILES.values():
        poses = []
        for pitch in PITCH_SAMPLE_ANGLES:
            stage_pose = module.getGlobalPlacement().multiply(
                instrument_mount.stage_placement(pitch)
            )
            sensor_pose = stage_pose.multiply(optical_frame)

            def registered(shape):
                return placed_shape(
                    optical_interface.registration_bound(shape), sensor_pose
                )

            shapes = {
                name: placed_shape(shape, stage_pose) for name, shape in moving.items()
            }
            shapes["ModuleMTF02PEnvelope"] = registered(
                optical_sensor.envelope_shape(profile)
            )
            poses.append(
                {
                    "instrument_pitch_deg": pitch,
                    "physical": shapes,
                    "instrument_reserves": {
                        name: placed_shape(shape, stage_pose)
                        for name, shape in moving_reserves.items()
                    },
                    "field": placed_shape(
                        optical_sensor.optical_reserve_shape(profile), sensor_pose
                    ),
                    "connector": registered(
                        optical_sensor.connector_reserve_shape(profile)
                    ),
                    "mount_tools": {
                        name: registered(shape)
                        for name, shape in mount_tool_shapes().items()
                    },
                }
            )
        screens.append(
            {
                "attachment": attachment,
                "saved_moving_parts": sorted(moving),
                "sensor": profile.key,
                "poses": poses,
                "continuous_bounds": {
                    name: shape
                    for name, shape in all_bounds.items()
                    if name.startswith(profile.key)
                    or name.startswith("Instrument/")
                    or name == "OpticalMountToolAccessBound"
                },
                "continuous_field": all_bounds[
                    f"{profile.key}ContinuousOpticalFieldBound"
                ],
                "instrument_stock": {
                    "Instrument/" + name: shape
                    for name, shape in {**moving, **moving_reserves}.items()
                    if name not in ("OpticalSensorTray", "ModuleMTF02PEnvelope")
                },
                "module_inverse": module.getGlobalPlacement().inverse(),
            }
        )
    return screens


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
                **pose["instrument_reserves"],
                "OpticalField": pose["field"],
                "OpticalConnector": pose["connector"],
                **{
                    "MountTool/" + key: shape
                    for key, shape in pose["mount_tools"].items()
                },
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
                    "instrument_pitch_deg": pose["instrument_pitch_deg"],
                    "collisions": hits,
                    "connector_service_clearances": gaps,
                    "passed": not hits and all(row["passed"] for row in gaps),
                }
            )
        continuous = []
        for name, shape in screen["continuous_bounds"].items():
            clearances = measure_clearances(
                shape,
                obstacles,
                minimum_gap_mm=wiring_reserves.CONNECTOR_SERVICE_GAP_MM
                if antenna and name.endswith("OpticalFieldBound")
                else 0,
                tolerance=TOL,
                validation_cache=validation_cache,
            )
            for clearance in clearances:
                if clearance["passed"] or name not in screen["instrument_stock"]:
                    continue
                # An all-angle AABB is sufficient when clear, but can fill a
                # real empty corner. Certify the complete actual saved solid
                # continuously before overturning that conservative rejection.
                obstacle = placed_shape(
                    obstacles[clearance["object"]], screen["module_inverse"]
                )
                certificate = certify_pitch_clearance(
                    screen["instrument_stock"][name], obstacle
                )
                clearance["conservative_bound_clearance"] = dict(clearance)
                clearance["actual_stock_pitch_certificate"] = certificate
                clearance["passed"] = certificate["passed"]
            continuous.append(
                {
                    "bound": name,
                    "clearances": clearances,
                    "passed": all(row["passed"] for row in clearances),
                }
            )
        rows.append(
            {
                "attachment": screen["attachment"],
                "saved_moving_parts": screen["saved_moving_parts"],
                "sensor_model": screen["sensor"],
                "sampled_attitudes": samples,
                "continuous_external_bounds": continuous,
                "remove_direct_antenna_before_service": antenna,
                "passed": all(row["passed"] for row in samples + continuous),
            }
        )
    selection_ok = required_mount is None or all(
        row["attachment"] == required_mount for row in rows
    )
    return {
        "sensor_screens": rows,
        "required_installed_attachment": required_mount,
        "installed_attachment_matches": selection_ok,
        "configuration_scope": "Both sensors rigidly mounted to the shared FC platform. Every sampled pitch transforms the complete saved moving inventory and its cable reserves; the sensor body and connector include assembly registration. Continuous optical envelopes retain all changed-option obstacles. Unknown saved moving parts are included. Remote antenna location, harness flex and physical retention remain unqualified.",
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
                    for name, gap in wiring_reserves.neighbour_gap_pairs()[
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
                required_mount=_optical_attachment(doc)
                if navigation.key == get_navigation_profile().key
                else None,
            )
            antenna = {
                "installed_clearance_collisions": collisions,
                "optical_clearance": optics,
                "scope": "Conservative possible SMA positions and antenna height, not an exact installation. Direct antenna points along CAD +Z, away from balloon; mechanical screening does not validate GNSS reception. Remote antenna is off-gondola and unplaced. Remove direct antenna before bench servicing.",
                "passed": not collisions and optics["passed"],
            }
        base_passed = (
            not hits
            and all(row["passed"] for row in buffers)
            and all(row["passed"] for row in support_rows + service)
            and optical["passed"]
        )
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
                "base_installation_passed": base_passed,
                "remote_antenna": {
                    "supported_conditionally": base_passed,
                    "location_modeled": False,
                    "scope": "The onboard module and connector reservation are screened. A remote antenna requires a separately chosen off-gondola location, cable route and retention; none is modeled or qualified here.",
                }
                if navigation.external_antenna is not None
                else None,
                "passed": base_passed and (antenna is None or antenna["passed"]),
            }
        )
    selected = {
        "navigation_model": get_navigation_profile().key,
        "radio_model": get_radio_profile().key,
    }
    selected_rows = [
        row for row in rows if all(row[k] == v for k, v in selected.items())
    ]
    screened = len(rows) == len(NAVIGATION_PROFILES) * len(RADIO_PROFILES) and bool(
        rows
    )
    selected_passed = len(selected_rows) == 1 and selected_rows[0]["passed"]
    return {
        "source_evidence": evidence,
        "combinations": rows,
        "selected_combination": selected,
        "selected_combination_passed": selected_passed,
        "all_options_screened": screened,
        "all_options_supported": all(row["passed"] for row in rows),
        "scope": "All three navigation choices receive conservative verdicts with the underside LR24-F-Mini and both optical models on the common FC platform. Overall success requires the selected combination to pass, not every alternative to fit. A failed direct-antenna verdict remains blocked for this layout and pitch range; remote placement is conditional and unmodeled. Actual saved moving stock follows continuous setup pitch. This audit does not qualify adhesive, actual connectors, radio/compass performance, electrical capacity or a remote antenna installation. Disconnect leads and remove direct antenna before bare-device service. Detach the accessory carrier for underside-radio bench access. Setup or rail relocation requires renewed checks.",
        "passed": screened and selected_passed,
    }
