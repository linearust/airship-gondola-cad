"""Continuous nominal service envelope for a short-arm 1.5 mm hex L-key.

The purchased rail screws have solid design envelopes rather than modeled
sockets. The audit therefore declares a 0..2 mm socket-insertion acceptance
range, retains surrounding head material and checks the complete shifted tool.
Actual socket fit, the exact bend and hand clearance still need a physical trial.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import translated_shape
from gondola.parts import rail

from .geometry import certify_translation_clearance, intersection_volume

TOL = 1e-5
KEY_SOURCE = (
    "https://www.gedore.com/-/media/files/catalogues/gedorered-catalogue-2022-2023.pdf"
)
KEY_AF_MM = 1.5
KEY_RADIUS_MM = 1.0  # Exceeds the 1.5 mm hex circumradius of 0.866 mm.
KEY_LONG_ARM_MM = 50.0
KEY_SHORT_ARM_MM = 16.0
KEY_AXIAL_CENTRELINE_MM = KEY_SHORT_ARM_MM - KEY_RADIUS_MM
KEY_WORKING_SECTOR_DEG = (0.0, 60.0)
KEY_REINDEX_OFFSET_MM = 1.5
SOCKET_INSERTION_ACCEPTANCE_MM = 2.0
SOCKET_VALIDATION_RADIUS_MM = KEY_RADIUS_MM + 0.1
TOOL_FACE_RESERVE_MM = 0.1
V = App.Vector


def _key_components(head_end_y, centre_x=0.0, centre_z=None, *, inserted_leg="short"):
    """Conservative external bars and a filled 4×4 mm inside-bend reservation."""
    if centre_z is None:
        centre_z = rail.CLAMP_Z
    if inserted_leg not in ("short", "long"):
        raise ValueError("Insert either the short or long L-key leg")
    axial_length = (
        KEY_SHORT_ARM_MM if inserted_leg == "short" else KEY_LONG_ARM_MM
    ) - KEY_RADIUS_MM
    handle_length = KEY_LONG_ARM_MM if inserted_leg == "short" else KEY_SHORT_ARM_MM
    start = head_end_y + TOOL_FACE_RESERVE_MM
    elbow = start + axial_length
    pieces = [
        Part.makeCylinder(
            KEY_RADIUS_MM,
            axial_length,
            V(centre_x, start, centre_z),
            V(0, 1, 0),
        ),
        Part.makeCylinder(
            KEY_RADIUS_MM,
            handle_length,
            V(centre_x, elbow, centre_z),
            V(-1, 0, 0),
        ),
        Part.makeBox(4, 4, 2, V(centre_x - 4, elbow - 4, centre_z - 1)),
    ]
    return pieces[0], pieces[1].fuse(pieces[2]).removeSplitter()


def key_envelope(head_end_y, centre_x=0.0, centre_z=None, *, inserted_leg="short"):
    axial, bent = _key_components(
        head_end_y, centre_x, centre_z, inserted_leg=inserted_leg
    )
    return axial.fuse(bent).removeSplitter()


def _box_distance(first, second):
    return math.sqrt(
        sum(
            max(
                getattr(first, axis + "Min") - getattr(second, axis + "Max"),
                getattr(second, axis + "Min") - getattr(first, axis + "Max"),
                0.0,
            )
            ** 2
            for axis in ("X", "Y", "Z")
        )
    )


def working_sector_check(
    tool,
    obstacles,
    axis,
    *,
    sector=KEY_WORKING_SECTOR_DEG,
    axial_range=(
        -SOCKET_INSERTION_ACCEPTANCE_MM - TOOL_FACE_RESERVE_MM,
        rail.RELEASE_TRAVEL,
    ),
    max_depth=22,
    max_evaluations=4096,
):
    """Certify the whole angle × axial-loosening rectangle by distance bounds.

    Rigid distance changes no faster than the maximum point displacement.
    A midpoint separation exceeding the rotation chord plus half axial travel
    certifies an entire parameter cell. Undecided cells subdivide and contact,
    depth or work limits fail closed. Each installed obstacle is retained.
    """
    angle_start, angle_end = map(float, sector)
    axial_start, axial_end = map(float, axial_range)
    if (
        not all(
            math.isfinite(value)
            for value in (angle_start, angle_end, axial_start, axial_end)
        )
        or not 60 <= angle_end - angle_start <= 180
        or axial_start > axial_end
    ):
        raise ValueError(
            "Rail service requires a full hex indexing sector and ordered axial range"
        )
    if tool.isNull() or not tool.isValid() or not tool.Solids:
        raise ValueError("Rail service requires a valid solid tool envelope")
    bounds = tool.BoundBox
    radius = math.hypot(
        max(abs(bounds.XMin - axis.x), abs(bounds.XMax - axis.x)),
        max(abs(bounds.ZMin - axis.z), abs(bounds.ZMax - axis.z)),
    )
    # Rotation leaves the Y projection unchanged; extending it by the complete
    # release travel gives an inexpensive conservative broad phase.
    orbit = App.BoundBox(
        axis.x - radius,
        bounds.YMin + axial_start,
        axis.z - radius,
        axis.x + radius,
        bounds.YMax + axial_end,
        axis.z + radius,
    )
    result = {
        "method": "adaptive continuous rotation-and-translation distance certificate",
        "sector_deg": [angle_start, angle_end],
        "axial_offset_range_mm": [axial_start, axial_end],
        "checked_objects": sorted(obstacles),
        "evaluated_positions": 0,
        "certified_cells": 0,
        "collisions": [],
        "passed": False,
    }
    relevant = []
    for name, shape in obstacles.items():
        if shape.isNull() or not shape.isValid() or not shape.Solids:
            raise ValueError("Invalid rail service obstacle: " + name)
        if _box_distance(orbit, shape.BoundBox) <= TOL:
            relevant.append(name)
    if not relevant:
        result.update(passed=bool(obstacles), certified_cells=1)
        return result
    pending = [(angle_start, angle_end, axial_start, axial_end, 0, tuple(relevant))]
    while pending:
        amin, amax, ymin, ymax, depth, names = pending.pop()
        if result["evaluated_positions"] >= max_evaluations:
            result["error"] = "Continuous rail-tool certificate reached its work limit"
            return result
        angle, offset = (amin + amax) / 2, (ymin + ymax) / 2
        placed = tool.copy()
        placed.rotate(axis, V(0, 1, 0), angle)
        placed.translate(V(0, offset, 0))
        result["evaluated_positions"] += 1
        rotation_bound = 2 * radius * math.sin(math.radians(amax - amin) / 4)
        translation_bound = (ymax - ymin) / 2
        displacement = rotation_bound + translation_bound
        unresolved = []
        for name in names:
            obstacle = obstacles[name]
            if _box_distance(placed.BoundBox, obstacle.BoundBox) > displacement + TOL:
                continue
            gap = float(placed.distToShape(obstacle)[0])
            if not math.isfinite(gap) or gap < 0:
                result["error"] = "Invalid kernel distance for " + name
                return result
            if gap <= TOL:
                result["collisions"].append(
                    {
                        "part": name,
                        "angle_deg": angle,
                        "axial_offset_mm": offset,
                        "intersection_mm3": intersection_volume(placed, obstacle),
                    }
                )
                return result
            if gap <= displacement + TOL:
                unresolved.append(name)
        if not unresolved:
            result["certified_cells"] += 1
        elif depth >= max_depth:
            result["error"] = (
                "Continuous rail-tool certificate could not resolve an interval"
            )
            result["unresolved_objects"] = unresolved
            return result
        elif rotation_bound >= translation_bound:
            pending.extend(
                [
                    (amin, angle, ymin, ymax, depth + 1, tuple(unresolved)),
                    (angle, amax, ymin, ymax, depth + 1, tuple(unresolved)),
                ]
            )
        else:
            pending.extend(
                [
                    (amin, amax, ymin, offset, depth + 1, tuple(unresolved)),
                    (amin, amax, offset, ymax, depth + 1, tuple(unresolved)),
                ]
            )
    result["passed"] = bool(obstacles)
    return result


def _key_working_check(axial, bent, obstacles, axis, *, axial_range):
    # The complete circular shaft is coaxial with the rotation axis, hence it
    # has exactly the same shape at every key angle. Check only its continuous
    # translation, then independently certify the whole bent handle. Their
    # union is the tool envelope; no obstacle or part of the tool is dropped.
    start, end = axial_range
    axial_check = certify_translation_clearance(
        translated_shape(axial, y=start), (0, end - start, 0), obstacles
    )
    bend_check = working_sector_check(bent, obstacles, axis, axial_range=axial_range)
    axial_collision = axial_check.get("collision")
    collisions = bend_check["collisions"] + (
        []
        if axial_collision is None
        else [{"part": axial_collision["obstacle"], **axial_collision}]
    )
    return {
        "method": "rotation-invariant axial cylinder plus continuous bent-handle certificate",
        "sector_deg": list(KEY_WORKING_SECTOR_DEG),
        "axial_offset_range_mm": list(axial_range),
        "checked_objects": sorted(obstacles),
        "axial_leg_translation": axial_check,
        "bent_handle_rotation_and_translation": bend_check,
        "collisions": collisions,
        "passed": axial_check["passed"] and bend_check["passed"],
    }


def _translation_path(tool, waypoints, obstacles):
    rows = []
    for start, end in zip(waypoints, waypoints[1:]):
        result = certify_translation_clearance(
            translated_shape(tool, *start),
            tuple(b - a for a, b in zip(start, end)),
            obstacles,
        )
        collision = result.get("collision")
        hits = (
            [] if collision is None else [{"part": collision["obstacle"], **collision}]
        )
        rows.append(
            {"start_mm": list(start), "end_mm": list(end), **result, "collisions": hits}
        )
    return {
        "segments": rows,
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }


def rail_key_service_check(
    obstacles,
    *,
    side=1,
    placement=None,
    screw=None,
    screw_name=None,
    inserted_leg="short",
):
    """Check both finite key travel and a continuous, reindexable working arc."""
    if side not in (-1, 1):
        raise ValueError("Rail key approach side must be -1 or +1")
    placement = placement or App.Placement()
    canonical = placement.multiply(
        App.Placement(V(), App.Rotation(V(0, 0, 1), 180 if side < 0 else 0))
    )
    inverse = canonical.inverse()
    local_obstacles = {}
    for name, shape in obstacles.items():
        local = shape.copy()
        local.Placement = inverse.multiply(local.Placement)
        local_obstacles[name] = local
    if screw is None:
        screw = rail.clamp_screw_shape()
    else:
        screw = screw.copy()
        screw.Placement = inverse.multiply(screw.Placement)
    bounds = screw.optimalBoundingBox(False, False)
    axis = V((bounds.XMin + bounds.XMax) / 2, 0, (bounds.ZMin + bounds.ZMax) / 2)
    socket_acceptance = Part.makeCylinder(
        SOCKET_VALIDATION_RADIUS_MM,
        SOCKET_INSERTION_ACCEPTANCE_MM + 2 * TOOL_FACE_RESERVE_MM,
        V(
            axis.x,
            bounds.YMax - SOCKET_INSERTION_ACCEPTANCE_MM - TOOL_FACE_RESERVE_MM,
            axis.z,
        ),
        V(0, 1, 0),
    )
    if screw_name is not None:
        if screw_name not in local_obstacles:
            raise ValueError(
                "Operated rail screw is absent from the obstacle inventory"
            )
        # This is a declared validation acceptance volume, not a CAD alteration
        # or an assertion that an unknown kit screw has a 2 mm deep socket.
        local_obstacles[screw_name] = local_obstacles[screw_name].cut(socket_acceptance)
    axial, bent = _key_components(
        bounds.YMax, axis.x, axis.z, inserted_leg=inserted_leg
    )
    tool = axial.fuse(bent).removeSplitter()
    working = _key_working_check(
        axial,
        bent,
        local_obstacles,
        axis,
        axial_range=(
            -SOCKET_INSERTION_ACCEPTANCE_MM - TOOL_FACE_RESERVE_MM,
            rail.RELEASE_TRAVEL,
        ),
    )
    # After each engaged stroke, withdraw before resetting the key angle;
    # turning back while engaged would undo the stroke. The separate certified
    # disengaged reindex arc below returns the key to the sector start. For
    # final removal, keep the tip beyond the external head by the reindex
    # offset plus face reserve, then take the key out of the module. This is an absolute clear
    # position, not travel measured from an engaged tip. Insertion reverses it.
    parked = tool.copy()
    parked.rotate(axis, V(0, 1, 0), KEY_WORKING_SECTOR_DEG[0])
    clear_offset = rail.RELEASE_TRAVEL + KEY_REINDEX_OFFSET_MM
    exit_offset = (
        (-70, clear_offset, 0)
        if inserted_leg == "short"
        else (0, clear_offset + KEY_LONG_ARM_MM, 0)
    )
    waypoints = [(0, rail.RELEASE_TRAVEL, 0), (0, clear_offset, 0), exit_offset]
    removal = _translation_path(parked, waypoints, local_obstacles)
    # A reindex cycle withdraws/reinserts at either end of the sector. It is
    # needed repeatedly because a 60 degree stroke alone cannot loosen 3 turns.
    reindex = []
    for angle in KEY_WORKING_SECTOR_DEG:
        indexed = tool.copy()
        indexed.rotate(axis, V(0, 1, 0), angle)
        reindex.append(
            _translation_path(
                indexed,
                [
                    (0, -SOCKET_INSERTION_ACCEPTANCE_MM - TOOL_FACE_RESERVE_MM, 0),
                    (0, rail.RELEASE_TRAVEL + KEY_REINDEX_OFFSET_MM, 0),
                ],
                local_obstacles,
            )
        )
    reindex_arc = _key_working_check(
        axial,
        bent,
        local_obstacles,
        axis,
        axial_range=(
            KEY_REINDEX_OFFSET_MM,
            KEY_REINDEX_OFFSET_MM + rail.RELEASE_TRAVEL,
        ),
    )
    collisions = (
        working["collisions"]
        + reindex_arc["collisions"]
        + [
            hit
            for path in [removal, *reindex]
            for segment in path["segments"]
            for hit in segment["collisions"]
        ]
    )
    return {
        "approach_side_y": side,
        "tool": "Dimensionally checked 1.5 mm AF, 50 × 16 mm L-key",
        "reference_catalog_item": "GEDORE red R36601508 / 3301282, catalogue page 66",
        "reference_conflict": "The live product title lists 45 × 14 mm; the catalogue/reference is 50 × 16 mm. Confirm the actual tool geometry rather than approving the SKU alone.",
        "tool_source": KEY_SOURCE,
        "inserted_leg": inserted_leg,
        "tool_radius_mm": KEY_RADIUS_MM,
        "inside_bend_reservation_mm": [4.0, 4.0, 2.0],
        "socket_insertion_acceptance_mm": [0.0, SOCKET_INSERTION_ACCEPTANCE_MM],
        "reindex_tip_clearance_beyond_head_mm": KEY_REINDEX_OFFSET_MM
        + TOOL_FACE_RESERVE_MM,
        "operated_screw_socket_acceptance_only": screw_name,
        "socket_validation_radius_mm": SOCKET_VALIDATION_RADIUS_MM,
        "checked_objects": sorted(obstacles),
        "continuous_working_sector": working,
        "staged_key_removal_and_reverse_insertion": removal,
        "reindex_withdrawal_at_both_arc_ends": reindex,
        "continuous_disengaged_reindex_arc": reindex_arc,
        "collisions": collisions,
        "scope": "Conservative L-key envelope against all supplied installed solids; only the operated screw receives a declared coaxial socket-acceptance void in this audit. Continuous 60 degree indexed working arc includes every 0..2 mm socket insertion and complete 1.2 mm screw release; disengagement then a sideways short-leg exit or axial long-leg exit is reversible. Socket-acceptance radius is a validation accommodation for intended key engagement, not a specified factory socket. Actual tool dimensions, socket fit, bend tolerance, hand room and clamp force require a physical trial.",
        "passed": working["passed"]
        and removal["passed"]
        and reindex_arc["passed"]
        and all(row["passed"] for row in reindex),
    }
