"""Read-only geometry, registry and access-margin checks for wiring reserves."""

import json
import math

from gondola.cad import world_shape
from gondola.parts import optical_sensor
from gondola.print_export import geometry_comparison

from .geometry import intersection_volume

TOL = 1e-6
RESERVES = (
    "XT30ServiceReserve",
    "CapacitorServiceReserve",
    "PortPhaseLeadLoopReserve",
    "StarboardPhaseLeadLoopReserve",
    "MTF02POpticalClearanceReserve",
    "FCWiringClearanceReserve",
    "LR900NegativeXConnectorReserve",
    "LR900PositiveXConnectorReserve",
    "PASConnectorReserve",
    "MTF02PConnectorReserve",
)
DIRECT_ANTENNA_RESERVE = "NavigationDirectAntennaReserve"


def _solid_shape_error(shape, validation_cache=None):
    if validation_cache is not None and id(shape) in validation_cache:
        return validation_cache[id(shape)][1]
    error = None
    if shape is None or shape.isNull():
        error = "missing solid shape"
    elif not shape.isValid() or not shape.Solids:
        error = "invalid or non-solid shape"
    if validation_cache is not None:
        # Retaining the immutable world copy prevents id reuse. The cache is
        # owned by one read-only audit/host probe and is never shared globally.
        validation_cache[id(shape)] = (shape, error)
    return error


def measure_clearances(
    shape,
    obstacles,
    *,
    minimum_gap_mm=0.0,
    tolerance=TOL,
    measure_distance=True,
    validation_cache=None,
):
    """Measure full solids; an optional audit-local cache requires immutable copies."""
    if not math.isfinite(minimum_gap_mm) or minimum_gap_mm < 0:
        raise ValueError("Minimum clearance must be finite and non-negative")
    rows = []
    source_error = _solid_shape_error(shape, validation_cache)
    for name, other in obstacles.items():
        row = {"object": name, "minimum_design_gap_mm": minimum_gap_mm}
        error = source_error or _solid_shape_error(other, validation_cache)
        if error:
            rows.append({**row, "error": error, "passed": False})
            continue
        volume = intersection_volume(shape, other)
        distance = (
            shape.distToShape(other)[0]
            if measure_distance or minimum_gap_mm > 0
            else None
        )
        row.update(intersection_mm3=volume)
        if distance is not None:
            row["measured_gap_mm"] = distance
        row["passed"] = (
            math.isfinite(volume)
            and 0 <= volume <= tolerance
            and (
                distance is None
                or (
                    math.isfinite(distance)
                    and distance >= 0
                    and distance >= minimum_gap_mm - tolerance
                )
            )
        )
        rows.append(row)
    return rows


def collision_hits(shape, obstacles, *, tolerance=TOL, validation_cache=None):
    """Return full-volume collisions or invalid geometry, without distance scans."""
    return _collision_hits(
        measure_clearances(
            shape,
            obstacles,
            tolerance=tolerance,
            measure_distance=False,
            validation_cache=validation_cache,
        )
    )


def _collision_hits(measurements):
    return [
        {key: row[key] for key in ("object", "intersection_mm3", "error") if key in row}
        for row in measurements
        if not row["passed"]
    ]


def named_gap_checks(shapes, minimum_gaps, *, tolerance=TOL, validation_cache=None):
    """Check every declared pair, including missing or invalid required shapes."""
    return [
        {"reserve": name, **row}
        for name, neighbours in minimum_gaps.items()
        for other_name, minimum in neighbours.items()
        for row in measure_clearances(
            shapes.get(name),
            {other_name: shapes.get(other_name)},
            minimum_gap_mm=minimum,
            tolerance=tolerance,
            validation_cache=validation_cache,
        )
    ]


def connector_reserve_geometry_check(actual, expected, obstacles):
    """Check the complete continuous reserved volume, not just its endpoints."""
    return _connector_geometry_check(
        actual, expected, collision_hits(actual, obstacles)
    )


def _connector_geometry_check(actual, expected, hits):
    error = _solid_shape_error(actual)
    if error:
        return {"passed": False, "error": error}
    comparison = geometry_comparison(actual, expected)
    connected = len(actual.Solids) == 1
    return {
        "source_comparison": comparison,
        "one_connected_solid": connected,
        "continuous_reserved_space_collisions": hits,
        "passed": connected and _comparison_passed(comparison) and not hits,
    }


def reserve_checks(doc):
    from gondola.parts import wiring_reserves as wiring

    from .propulsion_wiring import check as propulsion_wiring_check

    registry = doc.DesignRegistry
    physical_objects = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    physical_shapes_by_name = {obj.Name: world_shape(obj) for obj in physical_objects}
    reserve_shapes_by_name = {
        obj.Name: world_shape(obj) for obj in registry.ClearanceVolumes
    }
    expected_shapes = wiring.reserve_shapes()
    profile = optical_sensor.profile_for_document(doc)
    expected_shapes["MTF02PConnectorReserve"] = optical_sensor.connector_reserve_shape(
        profile
    )
    expected_contracts = wiring.reserve_contracts()
    expected_contracts["MTF02PConnectorReserve"] = optical_sensor.connector_contract(
        profile
    )
    checks = []
    propulsion_routes = {
        row["object"]: row for row in propulsion_wiring_check(doc)["routes"]
    }
    validation_cache = {}
    reserve_names = RESERVES + (
        (DIRECT_ANTENNA_RESERVE,)
        if DIRECT_ANTENNA_RESERVE in expected_shapes
        or doc.getObject(DIRECT_ANTENNA_RESERVE) is not None
        else ()
    )
    for name in reserve_names:
        obj = doc.getObject(name)
        if name == DIRECT_ANTENNA_RESERVE and name not in expected_shapes:
            checks.append(
                {
                    "object": name,
                    "passed": False,
                    "error": "Unexpected direct antenna for selected navigation profile",
                }
            )
            continue
        if obj is None:
            checks.append({"object": name, "passed": False, "error": "missing"})
            continue
        shape = world_shape(obj)
        error = _solid_shape_error(shape, validation_cache)
        if error:
            checks.append({"object": name, "error": error, "passed": False})
            continue
        measurements = measure_clearances(
            shape,
            {
                key: value
                for key, value in physical_shapes_by_name.items()
                if not (
                    (
                        name == optical_sensor.FIELD_OBJECT
                        and key == optical_sensor.SENSOR_OBJECT
                    )
                    or (name == DIRECT_ANTENNA_RESERVE and key == "ModulePASEnvelope")
                )
            },
            validation_cache=validation_cache,
        )
        physical_hits = _collision_hits(measurements)
        source_check = None
        contract_matches = True
        source_url_matches = True
        fit_unverified = True
        if name in propulsion_routes:
            source_check = propulsion_routes[name]
        if name in expected_shapes:
            source_check = _connector_geometry_check(
                shape,
                _in_parent_frame(
                    expected_shapes[name],
                    doc.OpticalPitchStage
                    if name == "MTF02PConnectorReserve"
                    else doc.ElectronicsEquipmentModule,
                ),
                physical_hits,
            )
            try:
                contract_matches = json.loads(str(obj.WiringContract)) == json.loads(
                    json.dumps(expected_contracts[name])
                )
            except (AttributeError, TypeError, ValueError):
                contract_matches = False
            source_url_matches = (
                str(getattr(obj, "SourceURL", ""))
                == expected_contracts[name]["source_url"]
            )
            fit_unverified = (
                "InstalledConnectorFitVerified" in obj.PropertiesList
                and not obj.InstalledConnectorFitVerified
            )
        buffers = named_gap_checks(
            {**physical_shapes_by_name, **reserve_shapes_by_name},
            {name: wiring.MINIMUM_NEIGHBOUR_GAPS.get(name, {})},
            validation_cache=validation_cache,
        )
        intersections = [
            {
                "object": hit["object"],
                **(
                    {"volume_mm3": hit["intersection_mm3"]}
                    if "intersection_mm3" in hit
                    else {}
                ),
                **({"error": hit["error"]} if "error" in hit else {}),
            }
            for hit in physical_hits
        ]
        nearest = [
            {"object": row["object"], "distance_mm": row["measured_gap_mm"]}
            for row in measurements
            if "measured_gap_mm" in row
        ]
        bounds = shape.optimalBoundingBox(False, False)
        sweeps = []
        for sweep in registry.ClearanceVolumes:
            if "Sweep" not in sweep.Name:
                continue
            swept = world_shape(sweep)
            sweeps.append(
                {
                    "sweep": sweep.Name,
                    "intersection_mm3": intersection_volume(shape, swept),
                    "distance_mm": shape.distToShape(swept)[0],
                }
            )
        clearance_only = (
            obj in registry.ClearanceVolumes
            and obj not in registry.PrintedParts
            and obj not in registry.HardwareParts
            and obj not in registry.ReferenceParts
            and str(getattr(obj, "Role", "")) == "Clearance"
        )
        checks.append(
            {
                "object": name,
                "self_sensor_excluded_from_rear_plane_optical_screen": name
                == optical_sensor.FIELD_OBJECT,
                "own_navigation_body_inside_uncertain_antenna_seating_bound": name
                == DIRECT_ANTENNA_RESERVE,
                "role": str(obj.Role),
                "in_clearance_registry": obj in registry.ClearanceVolumes,
                "not_in_print_or_hardware_registry": obj not in registry.PrintedParts
                and obj not in registry.HardwareParts,
                "valid_solid": shape.isValid() and len(shape.Solids) == 1,
                "bounds_world_mm": {
                    "min": [bounds.XMin, bounds.YMin, bounds.ZMin],
                    "max": [bounds.XMax, bounds.YMax, bounds.ZMax],
                },
                "intersections_with_printed_hardware_equipment_tape": intersections,
                "nearest_five_objects": sorted(
                    nearest, key=lambda row: row["distance_mm"]
                )[:5],
                "conservative_rotor_sweep_comparison": sweeps,
                "connector_geometry": source_check,
                "native_wiring_contract_matches": contract_matches,
                "native_source_url_matches": source_url_matches,
                "installed_connector_fit_remains_unverified": fit_unverified,
                "neighbour_clearance_buffers": buffers,
                "notes": str(getattr(obj, "Notes", "")),
                "passed": not intersections
                and shape.isValid()
                and len(shape.Solids) == 1
                and all(row["intersection_mm3"] < TOL for row in sweeps)
                and (source_check is None or source_check["passed"])
                and contract_matches
                and source_url_matches
                and fit_unverified
                and all(row["passed"] for row in buffers)
                and clearance_only,
            }
        )
    pairs = []
    for index, name in enumerate(reserve_names):
        for other_name in reserve_names[index + 1 :]:
            first = reserve_shapes_by_name.get(name)
            second = reserve_shapes_by_name.get(other_name)
            measurement = measure_clearances(
                first,
                {other_name: second},
                measure_distance=False,
                validation_cache=validation_cache,
            )[0]
            route_name = next(
                (item for item in (name, other_name) if item in propulsion_routes),
                None,
            )
            connection = None
            if route_name is not None and "FCWiringClearanceReserve" in (
                name,
                other_name,
            ):
                route = propulsion_routes[route_name]
                connection = route.get("fc_terminal_connection")
                permitted_connection = route["passed"] and bool(
                    connection and connection["passed"]
                )
            else:
                permitted_connection = False
            own_optical_screen = {name, other_name} == {
                optical_sensor.FIELD_OBJECT,
                optical_sensor.CONNECTOR_OBJECT,
            }
            antenna_service_overlap = {name, other_name} == {
                DIRECT_ANTENNA_RESERVE,
                "PASConnectorReserve",
            }
            pairs.append(
                {
                    "a": name,
                    "b": other_name,
                    "intersection_mm3": measurement.get("intersection_mm3"),
                    "intentional_fc_terminal_connection": connection,
                    "own_conservative_optical_connector_overlap": own_optical_screen,
                    "remove_direct_antenna_before_navigation_connector_service": antenna_service_overlap,
                    "overlap_scope": (
                        "The rear-plane whole-footprint optical screen intentionally overbounds the sensor and its own edge lane. This is not a claim that an installed cable clears the actual apertures; inspect received lens/cable datums. Other reserves remain independent obstacles."
                        if own_optical_screen
                        else (
                            "Exact SMA position and seating plane are unknown; conservative direct-antenna bound overlaps its own signal lane. Remove helix before connector servicing. Simultaneous installed antenna/cable clearance remains unqualified."
                            if antenna_service_overlap
                            else None
                        )
                    ),
                    **(
                        {"error": measurement["error"]}
                        if "error" in measurement
                        else {}
                    ),
                    "passed": permitted_connection
                    or (own_optical_screen and "error" not in measurement)
                    or (antenna_service_overlap and "error" not in measurement)
                    or (
                        measurement["passed"] and measurement["intersection_mm3"] < TOL
                    ),
                }
            )
    return checks, pairs


def _comparison_passed(comparison):
    return all(
        comparison[key] < TOL
        for key in ("difference_mm3", "bounds_difference_mm", "volume_difference_mm3")
    )


def _in_parent_frame(shape, parent):
    result = shape.copy()
    result.Placement = parent.getGlobalPlacement().multiply(result.Placement)
    return result
