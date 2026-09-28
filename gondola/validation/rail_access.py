"""Continuous finite top-tool service for direct carbon-to-rail screws.

The purchased rail screws have solid design envelopes rather than modeled
sockets. The audit therefore declares a 0..2 mm socket-insertion acceptance
range, retains surrounding head material and checks the complete shifted tool.
Actual socket fit, the exact bend and hand clearance still need a physical trial.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import translated_shape

from .geometry import (
    certify_translation_clearance,
    intersection_volume,
    translation_sweep,
)

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
        centre_z = 0.0
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
        1.2,
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


def _outward_translation_check(shape, vector, obstacles):
    """Retain boundary contact only when a supporting plane proves separation.

    Canonical +Y motion cannot enter a closed obstacle wholly behind the
    moving solid's initial minimum-Y plane. This includes the key tip exactly
    at the carbon top after full socket insertion. Bounds enclose every point;
    no angle samples, invented clearance or omitted interior overlap is used.
    """
    plane = shape.optimalBoundingBox(False, False).YMin
    outward = abs(vector[0]) < 1e-12 and abs(vector[2]) < 1e-12 and vector[1] > 0
    separated = {
        name: other.optimalBoundingBox(False, False).YMax
        for name, other in obstacles.items()
        if outward and other.optimalBoundingBox(False, False).YMax <= plane + 1e-9
    }
    remaining = {
        name: other for name, other in obstacles.items() if name not in separated
    }
    # The independent geometric certificate permits boundary contact only;
    # every obstacle that extends in front of the plane keeps the strict gate.
    if remaining:
        result = certify_translation_clearance(shape, vector, remaining)
    else:
        result = {
            "method": "continuous supporting-plane separation",
            "passed": bool(obstacles),
        }
    return {
        **result,
        "obstacles": sorted(obstacles),
        "supporting_plane_mm": plane,
        "outward_supporting_plane_obstacles": separated,
    }


def _key_working_check(axial, bent, obstacles, axis, *, axial_range):
    # The complete circular shaft is coaxial with the rotation axis, hence it
    # has exactly the same shape at every key angle. Check only its continuous
    # translation, then independently certify the whole bent handle. Their
    # union is the tool envelope; no obstacle or part of the tool is dropped.
    start, end = axial_range
    axial_check = _outward_translation_check(
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
        result = _outward_translation_check(
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


def top_key_service_check(
    obstacles,
    *,
    screw,
    screw_name,
    placement=None,
    release_travel_mm=None,
    inserted_leg="short",
    clock_deg=0.0,
):
    """Certify top access and complete removal of an actual downward screw.

    Inputs are world shapes. ``placement`` defines the rigid joint frame whose
    +Z is the removal direction. The checked tool remains the same finite
    catalog envelope; only its reference frame changes. Remove a covering FC
    or other device first, with that prerequisite independently validated.
    """
    if screw_name not in obstacles:
        raise ValueError("Operated rail screw is absent from the obstacle inventory")
    placement = placement or App.Placement()
    # The distance-bound implementation works about canonical +Y. Rotate this
    # complete frame so canonical +Y is the joint's actual +Z tool direction.
    canonical = placement.multiply(App.Placement(V(), App.Rotation(V(1, 0, 0), 90)))
    inverse = canonical.inverse()
    local_obstacles = {}
    for name, shape in obstacles.items():
        local = shape.copy()
        local.Placement = inverse.multiply(local.Placement)
        local_obstacles[name] = local
    local_screw = screw.copy()
    local_screw.Placement = inverse.multiply(local_screw.Placement)
    bounds = local_screw.optimalBoundingBox(False, False)
    axis = V((bounds.XMin + bounds.XMax) / 2, 0, (bounds.ZMin + bounds.ZMax) / 2)
    release = (
        bounds.YLength + 1 if release_travel_mm is None else float(release_travel_mm)
    )
    if not math.isfinite(release) or release < bounds.YLength:
        raise ValueError(
            "Top service must withdraw the complete screw beyond its original envelope"
        )
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
    # This bounded socket allowance is only for tool engagement. The complete
    # unchanged screw is separately swept against every other retained solid.
    local_obstacles[screw_name] = local_obstacles[screw_name].cut(socket_acceptance)
    axial, bent = _key_components(
        bounds.YMax, axis.x, axis.z, inserted_leg=inserted_leg
    )
    if not math.isfinite(float(clock_deg)):
        raise ValueError("Tool clocking must be finite")
    bent.rotate(axis, V(0, 1, 0), float(clock_deg))
    tool = axial.fuse(bent).removeSplitter()
    working = _key_working_check(
        axial,
        bent,
        local_obstacles,
        axis,
        axial_range=(-SOCKET_INSERTION_ACCEPTANCE_MM - TOOL_FACE_RESERVE_MM, release),
    )
    # Withdraw vertically instead of assuming an unlimited side exit through
    # neighbouring modules. The finite handle and bend are both retained.
    clear_offset = release + KEY_REINDEX_OFFSET_MM
    removal = _translation_path(
        tool,
        [(0, release, 0), (0, clear_offset, 0), (0, clear_offset + KEY_LONG_ARM_MM, 0)],
        local_obstacles,
    )
    reindex = []
    for angle in KEY_WORKING_SECTOR_DEG:
        indexed = tool.copy()
        indexed.rotate(axis, V(0, 1, 0), angle)
        reindex.append(
            _translation_path(
                indexed,
                [
                    (0, -SOCKET_INSERTION_ACCEPTANCE_MM - TOOL_FACE_RESERVE_MM, 0),
                    (0, clear_offset, 0),
                ],
                local_obstacles,
            )
        )
    reindex_arc = _key_working_check(
        axial,
        bent,
        local_obstacles,
        axis,
        axial_range=(KEY_REINDEX_OFFSET_MM, clear_offset),
    )
    swept, method = translation_sweep(local_screw, (0, release, 0))
    screw_hits = [
        {"part": name, "intersection_mm3": volume}
        for name, shape in local_obstacles.items()
        if name != screw_name and (volume := intersection_volume(swept, shape)) > TOL
    ]
    screw_removal = {
        "method": method,
        "travel_mm": release,
        "checked_objects": sorted(set(local_obstacles) - {screw_name}),
        "collisions": screw_hits,
        "passed": not screw_hits,
    }
    collisions = (
        working["collisions"]
        + reindex_arc["collisions"]
        + screw_hits
        + [
            hit
            for path in [removal, *reindex]
            for segment in path["segments"]
            for hit in segment["collisions"]
        ]
    )
    return {
        "approach": "joint-local +Z",
        "tool_clock_deg": float(clock_deg),
        "tool": "Dimensionally checked 1.5 mm AF, 50 × 16 mm L-key",
        "reference_catalog_item": "GEDORE red R36601508 / 3301282, catalogue page 66",
        "reference_conflict": "The live product title lists45×14mm; confirm the actual tool dimensions against the larger50×16mm envelope used here.",
        "tool_source": KEY_SOURCE,
        "inserted_leg": inserted_leg,
        "socket_insertion_acceptance_mm": [0.0, SOCKET_INSERTION_ACCEPTANCE_MM],
        "checked_objects": sorted(obstacles),
        "continuous_working_sector": working,
        "complete_screw_removal": screw_removal,
        "staged_key_removal_and_reverse_insertion": removal,
        "disengaged_reindex_paths": reindex,
        "disengaged_reindex_arc": reindex_arc,
        "collisions": collisions,
        "scope": "Nominal finite top-tool and complete screw travel after the declared covering-device removal. The operated screw is retained except for a bounded engagement accommodation; its unchanged solid is swept separately. No installed-FC top access, real socket fit, hand room, torque or retention qualification is inferred.",
        "passed": working["passed"]
        and removal["passed"]
        and reindex_arc["passed"]
        and screw_removal["passed"]
        and all(row["passed"] for row in reindex),
    }
