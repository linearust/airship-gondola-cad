"""Saved planning-route audit; it deliberately cannot qualify moving wires."""

import json

import FreeCAD as App
import Part

from gondola.cad import world_shape
from gondola.parts import propulsion_wiring as wiring
from gondola.print_export import geometry_comparison

from .wiring import collision_hits

TOL = 1e-6
CONNECTION_CAPTURE_RADIUS_MM = 8.0


def connection_check(shape, fc_reserve, endpoint):
    """Permit overlap only around the declared final entry into the FC band."""
    if shape is None or fc_reserve is None or shape.isNull() or fc_reserve.isNull():
        return {"passed": False, "error": "missing route or FC access reservation"}
    connection = shape.common(fc_reserve)
    volume = abs(connection.Volume)
    gate = Part.makeSphere(CONNECTION_CAPTURE_RADIUS_MM, App.Vector(*endpoint))
    remote_overlap = abs(connection.cut(gate).Volume) if volume > TOL else 0.0
    return {
        "connected_volume_mm3": volume,
        "connection_capture_radius_mm": CONNECTION_CAPTURE_RADIUS_MM,
        "overlap_outside_terminal_region_mm3": remote_overlap,
        "passed": volume > TOL and remote_overlap < TOL,
    }


def route_geometry_check(actual, expected, obstacles, fc_reserve, endpoint):
    if (
        actual is None
        or actual.isNull()
        or not actual.isValid()
        or len(actual.Solids) != 1
    ):
        return {"passed": False, "error": "route must be one valid connected solid"}
    comparison = geometry_comparison(actual, expected)
    source_matches = all(
        comparison[key] < TOL
        for key in ("difference_mm3", "bounds_difference_mm", "volume_difference_mm3")
    )
    hits = collision_hits(actual, obstacles)
    connection = connection_check(actual, fc_reserve, endpoint)
    return {
        "source_comparison": comparison,
        "layout_geometry_matches": source_matches,
        "continuous_reserved_space_collisions": hits,
        "fc_terminal_connection": connection,
        "passed": source_matches and not hits and connection["passed"],
    }


def _world_geometry(shape, placement):
    result = shape.copy()
    result.Placement = placement.multiply(result.Placement)
    return result


def check(doc):
    """Check current module poses; a saved corridor cannot silently follow a slide."""
    registry = doc.DesignRegistry
    propulsion_placement = doc.MainPropulsionModule.getGlobalPlacement()
    electronics_placement = doc.ElectronicsEquipmentModule.getGlobalPlacement()
    physical = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    obstacles = {obj.Name: world_shape(obj) for obj in physical}
    fc = doc.getObject("FCWiringClearanceReserve")
    fc_shape = world_shape(fc) if fc is not None else None
    rows = []
    for prefix, sign in wiring.PREFIX_SIGNS:
        name = prefix + "PhaseLeadLoopReserve"
        obj = doc.getObject(name)
        row = {"object": name}
        if obj is None:
            rows.append({**row, "passed": False, "error": "missing route"})
            continue
        try:
            geometry = wiring.route_geometry(
                sign, propulsion_placement, electronics_placement
            )
            contract = wiring.route_contract(
                sign, propulsion_placement, electronics_placement
            )
        except (ValueError, RuntimeError) as error:
            rows.append({**row, "passed": False, "error": str(error)})
            continue
        expected = _world_geometry(geometry["shape"], propulsion_placement)
        endpoint = propulsion_placement.multVec(App.Vector(*geometry["points"][-1]))
        route_obstacles = dict(obstacles)
        route_obstacles.update(
            {
                item.Name: world_shape(item)
                for item in registry.ClearanceVolumes
                if item.Name not in (name, "FCWiringClearanceReserve")
            }
        )
        result = route_geometry_check(
            world_shape(obj),
            expected,
            route_obstacles,
            fc_shape,
            (endpoint.x, endpoint.y, endpoint.z),
        )
        try:
            contract_matches = json.loads(obj.WiringContract) == json.loads(
                json.dumps(contract)
            )
        except (AttributeError, TypeError, ValueError):
            contract_matches = False
        unqualified = all(
            name in obj.PropertiesList and not getattr(obj, name)
            for name in ("MovingWireSweepVerified", "CompleteHarnessModeled")
        )
        clearance_only = (
            obj in registry.ClearanceVolumes
            and obj not in physical
            and getattr(obj, "Role", "") == "Clearance"
        )
        fc_registered = fc is not None and fc in registry.ClearanceVolumes
        rows.append(
            {
                **row,
                **result,
                "native_contract_matches": contract_matches,
                "moving_harness_remains_unqualified": unqualified,
                "clearance_only": clearance_only,
                "fc_reservation_registered": fc_registered,
                "source_url_matches": getattr(obj, "SourceURL", "")
                == wiring.SOURCE_URL,
                "passed": result["passed"]
                and contract_matches
                and unqualified
                and clearance_only
                and fc_registered
                and getattr(obj, "SourceURL", "") == wiring.SOURCE_URL,
            }
        )
    return {
        "scope": "Continuous stationary planning volume, current-pose source identity and complete rigid obstacle/sweep bounds. This audit does not connect the actual motor exit or simulate cable deformation, fatigue, friction, tie retention or winding history.",
        "routes": rows,
        "moving_wire_sweep_verified": False,
        "strain_relief_fit_verified": False,
        "servo_connected_route_verified": False,
        "passed": len(rows) == 2 and all(row["passed"] for row in rows),
    }
