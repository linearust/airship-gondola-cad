"""Shared propulsion service geometry, independent of report coordination.

Inventory every physical module obstacle and certify ordered rigid-part paths
without changing the scope of the calling assembly or removal check.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, translated_shape, union, world_shape
from gondola.contracts.drive import DRIVE_INWARD_OFFSET_MM, FACE_WIDTH_MM, MODULE_MM
from gondola.parts import propulsion

from .geometry import TOL, intersection_volume, translation_sweep


def module_service_shapes(doc, module):
    """Require every retained physical obstacle, in the local propulsion frame."""
    group = module["group"]
    expected = {
        obj.Name
        for obj in doc.Objects
        if belongs_to_group(obj, group)
        and obj.isDerivedFrom("Part::Feature")
        and obj.Shape.Solids
        and getattr(obj, "Role", "") != "Clearance"
    }
    objects = module["printed"] + module["hardware"] + module["references"]
    shapes = {obj.Name: world_shape(obj) for obj in objects if obj.Name in expected}
    inverse = group.getGlobalPlacement().inverse()
    for shape in shapes.values():
        shape.Placement = inverse.multiply(shape.Placement)
    return shapes, sorted(expected - shapes.keys())


def servo_bench_members(doc, shapes):
    """Physical parts in the fixed grouping of individually removable inputs."""
    return {
        name
        for name in shapes
        if belongs_to_group(doc.getObject(name), doc.ServoDriveModule)
    }


def retained_obstacles(physical, excluded, *, members=None):
    """Retain installed obstacles within the declared whole-module or bench scope."""
    return {
        name: shape
        for name, shape in physical.items()
        if name not in excluded and (members is None or name in members)
    }


def continuous_path(shape, waypoints, obstacles):
    """Check every point of a piecewise translation, not just its waypoints."""
    rows = []
    for start, end in zip(waypoints, waypoints[1:]):
        placed = translated_shape(shape, *start)
        swept, method = translation_sweep(
            placed, tuple(b - a for a, b in zip(start, end))
        )
        collisions = {
            name: intersection_volume(swept, obstacle)
            for name, obstacle in obstacles.items()
        }
        rows.append(
            {
                "start_mm": list(start),
                "end_mm": list(end),
                "method": method,
                "intersection_mm3": collisions,
                "passed": all(v < TOL for v in collisions.values()),
            }
        )
    return {
        "obstacles": sorted(obstacles),
        "segments": rows,
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }


def contained_region_paths(shape, regions, waypoints, obstacles):
    """Sweep named stock regions only after accounting for the complete part.

    Callers define their own conservative stock. Keeping regions separate avoids
    filling empty corners with one bounding box; their union must contain every
    part feature so an omitted region cannot silently pass the path check.
    """
    regions = tuple(regions)
    uncovered = (
        abs(shape.cut(union([part for _, part in regions])).Volume)
        if regions
        else abs(shape.Volume)
    )
    rows = [
        {"region": label, **continuous_path(part, waypoints, obstacles)}
        for label, part in regions
    ]
    return {
        "regions": rows,
        "uncovered_volume_mm3": uncovered,
        "passed": bool(rows) and uncovered < TOL and all(row["passed"] for row in rows),
    }


def split_housing_vertical_service(shape, obstacles, *, bearing_centre_y=None):
    """Certify +Z30 removal from the split housing, in positive-side coordinates.

    A cap point starts at or above Z50. Moving it upward increases its radial
    distance from the bearing axis, so its concave cylindrical void cannot
    sweep into a bearing. A bearing point remaining below Z50 moves toward the
    axis plane and stays inside the original diameter-6 cavity. Above Z50 its
    entire swept stock is bounded by the independent upper rectangular prism.
    Released fastener and shaft bores may be conservatively filled.
    """
    axis = App.Vector(0, 1, 0)
    if bearing_centre_y is None:
        reference = Part.makeBox(18, 19, 4.5, App.Vector(-9, 25, 50))
        stop = Part.makeCylinder(4.5, 1, App.Vector(0, 24, 50), axis).common(
            Part.makeBox(10, 1, 4.5, App.Vector(-5, 24, 50))
        )
        reference = reference.fuse(stop).cut(
            Part.makeCylinder(2.8, 20, App.Vector(0, 24, 50), axis)
        )
        for centre in (28.0, 41.0):
            reference = reference.cut(
                Part.makeCylinder(3, 3, App.Vector(0, centre - 1.5, 50), axis)
            )
        for x in (-9.0, 6.0):
            reference = reference.cut(Part.makeBox(3, 3, 1.5, App.Vector(x, 28, 50)))
        swept = reference.fuse(Part.makeBox(18, 20, 30, App.Vector(-9, 24, 54.5)))
        method = "continuous split-cap radial-monotonicity envelope"
    else:
        if bearing_centre_y not in (28.0, 41.0):
            raise ValueError("Unknown split-housing bearing station")
        reference = Part.makeCylinder(
            3, 2.5, App.Vector(0, bearing_centre_y - 1.25, 50), axis
        )
        swept = reference.fuse(
            Part.makeBox(6, 2.5, 33, App.Vector(-3, bearing_centre_y - 1.25, 50))
        )
        method = "continuous bearing upward half-space envelope"
    outside = abs(shape.cut(reference).Volume)
    end = translated_shape(shape, z=30)
    missing_end = abs(end.cut(swept).Volume)
    hits = {
        name: intersection_volume(swept, obstacle)
        for name, obstacle in obstacles.items()
    }
    return {
        "obstacles": sorted(obstacles),
        "uncovered_start_stock_mm3": outside,
        "uncovered_end_stock_mm3": missing_end,
        "segments": [
            {
                "start_mm": [0, 0, 0],
                "end_mm": [0, 0, 30],
                "method": method,
                "intersection_mm3": hits,
                "passed": all(value < TOL for value in hits.values()),
            }
        ],
        "passed": outside < TOL
        and missing_end < TOL
        and all(value < TOL for value in hits.values()),
    }


def driver_full_rotation_clearance_check(shape, obstacle, placement, sign, spec):
    """Contain the actual driver in separate coaxial hub and tooth cylinders.

    Both cylinders are invariant under every angle about the input shaft. The
    smaller hub occupies only its own five-millimetre axial band, avoiding the
    empty corners of a full-width tooth-radius cylinder.
    """
    from .relative_motion import MINIMUM_GAP_MM
    from .relative_motion import TOL as CLEARANCE_TOL

    reference = Part.makeCylinder(
        6, 5, App.Vector(0, sign * 22.5, 0), App.Vector(0, sign, 0)
    ).fuse(
        Part.makeCylinder(
            12.5, 3, App.Vector(0, sign * 27.5, 0), App.Vector(0, sign, 0)
        )
    )
    reference.Placement = placement.multiply(reference.Placement)
    outside = abs(shape.cut(reference).Volume)
    gap = reference.distToShape(obstacle)[0]
    contract_ok = (
        spec.driver.teeth == 48
        and spec.driver.hub_diameter_mm == 12
        and spec.driver.hub_extension_mm == 5
        and spec.driver.face_width_mm == 3
        and spec.driver.outside_diameter_mm == 25
        and spec.driver.total_length_mm == 8
    )
    return {
        "method": "containment-checked hub and tooth cylinders for every rotation angle",
        "literal_hub_diameter_length_mm": [12, 5],
        "literal_tooth_diameter_length_mm": [25, 3],
        "selected_drive_contract_matches": contract_ok,
        "outside_full_rotation_envelope_mm3": outside,
        "guaranteed_gap_mm": gap,
        "minimum_nominal_gap_mm": MINIMUM_GAP_MM,
        "passed": contract_ok
        and outside < TOL
        and gap > MINIMUM_GAP_MM + CLEARANCE_TOL,
    }


def driver_service_segment_check(shape, start, end, obstacles, spec, sign):
    """Contain every point of one pure X or Y gear translation.

    A single bounding box fills the empty corners around the large gear and
    falsely hits the retained small gear. These exact swept cylinders enclose
    the complete bought gear; containment of the actual CAD is checked first.
    """
    if (
        sign not in (-1, 1)
        or len(start) != 3
        or len(end) != 3
        or not all(math.isfinite(value) for value in (*start, *end))
    ):
        return {"passed": False, "error": "Expected finite three-dimensional poses"}
    dx, dy, dz = (b - a for a, b in zip(start, end))
    lateral = abs(dx) > TOL and abs(dy) < TOL and abs(dz) < TOL
    axial = abs(dy) > TOL and abs(dx) < TOL and abs(dz) < TOL
    if not (lateral or axial):
        return {"passed": False, "error": "Expected one pure X or Y translation"}
    axis = App.Vector(0, sign, 0)
    x, z = sign * spec.input_x_mm, spec.input_z_mm
    reference, swept = [], []
    for y, height, radius in (
        (propulsion.GEAR_HUB_START_Y, 5, spec.driver.hub_diameter_mm / 2),
        (
            propulsion.GEAR_FACE_START_Y,
            FACE_WIDTH_MM,
            MODULE_MM * (spec.driver.teeth + 2) / 2,
        ),
    ):
        origin = App.Vector(x, sign * y, z)
        cylinder = Part.makeCylinder(radius, height, origin, axis)
        reference.append(cylinder)
        if axial:
            # Fill the entire axial interval, including any gap between the
            # endpoint cylinders. Endpoint union alone is not a sweep.
            swept.append(
                Part.makeCylinder(
                    radius,
                    height + abs(dy),
                    App.Vector(
                        x + start[0],
                        min(sign * y, sign * (y + height)) + min(start[1], end[1]),
                        z + start[2],
                    ),
                    App.Vector(0, 1, 0),
                )
            )
        else:
            first = translated_shape(cylinder, *start)
            last = translated_shape(cylinder, *end)
            bridge = Part.makeBox(
                abs(dx),
                height,
                2 * radius,
                App.Vector(
                    x + min(start[0], end[0]),
                    min(sign * y, sign * (y + height)) + start[1],
                    z - radius + start[2],
                ),
            )
            swept.append(first.fuse(last).fuse(bridge))
    envelope = reference[0].fuse(reference[1])
    outside = abs(shape.cut(envelope).Volume)
    sweep = swept[0].fuse(swept[1])
    hits = {
        name: intersection_volume(sweep, other) for name, other in obstacles.items()
    }
    return {
        "obstacles": sorted(obstacles),
        "segments": [
            {
                "start_mm": list(start),
                "end_mm": list(end),
                "method": "continuous tooth-disk and hub "
                + ("full axial intervals" if axial else "swept-cylinder union"),
                "intersection_mm3": hits,
                "passed": all(value < TOL for value in hits.values()),
            }
        ],
        "gear_outside_reference_envelope_mm3": outside,
        "passed": outside < TOL and all(value < TOL for value in hits.values()),
    }


def driver_lateral_service_check(shape, start, end, obstacles, spec, sign):
    """Keep the lateral-only API explicit for callers with one X stroke."""
    if start[1:] != end[1:]:
        return {"passed": False, "error": "Expected a pure X translation"}
    return driver_service_segment_check(shape, start, end, obstacles, spec, sign)


def servo_lateral_service_check(shape, start, end, obstacles):
    """Partition the actual servo at its axial steps before continuous sweeping.

    The ear tips do not extend along the whole case depth. Sweeping one box
    around case, ears and spline fills those absent corners. Axial slabs from
    the live shape preserve them, and a coverage check prevents missing solid.
    """
    bounds = shape.BoundBox
    planes = sorted({round(vertex.Point.y, 9) for vertex in shape.Vertexes})
    pieces, segments = [], []
    for low, high in zip(planes, planes[1:]):
        if high - low < TOL:
            continue
        slab = shape.common(
            Part.makeBox(
                bounds.XLength + 2,
                high - low,
                bounds.ZLength + 2,
                App.Vector(bounds.XMin - 1, low, bounds.ZMin - 1),
            )
        )
        if abs(slab.Volume) < TOL:
            continue
        pieces.append(slab)
        result = continuous_path(slab, [start, end], obstacles)
        segments.extend(
            {"source_axial_slab_mm": [low, high], **row} for row in result["segments"]
        )
    covered = Part.makeCompound(pieces)
    missing = abs(shape.cut(covered).Volume) if pieces else abs(shape.Volume)
    return {
        "obstacles": sorted(obstacles),
        "segments": segments,
        "uncovered_servo_volume_mm3": missing,
        "passed": bool(segments)
        and missing < TOL
        and all(row["passed"] for row in segments),
    }


def adapter_service_check(shape, waypoints, obstacles, spec, sign):
    """Fill the forward clamp voids while preserving the rear horn socket.

    The transverse shaft screw hole prevents the generic coaxial sweep from
    retaining the horn pocket. A solid block around the forward clamp is a
    conservative replacement for that region only. The live adapter must fit
    completely within this reference before its continuous sweep is accepted.
    Every retained obstacle remains checked, including the retained purchased horn.
    """
    from gondola.parts import servo_coupling as coupling

    envelope = coupling.service_envelope()
    envelope.translate(App.Vector(0, coupling.HORN_BOTTOM_Y, 0))
    if sign < 0:
        envelope.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
    envelope.translate(
        App.Vector(
            sign * spec.input_x_mm, -sign * DRIVE_INWARD_OFFSET_MM, spec.input_z_mm
        )
    )
    outside = abs(shape.cut(envelope).Volume)
    result = continuous_path(envelope, waypoints, obstacles)
    return {
        **result,
        "adapter_outside_reference_envelope_mm3": outside,
        "reference_envelope": "Actual nominal horn socket with forward shaft-clamp voids conservatively filled; no obstacle exclusions",
        "passed": outside < TOL and result["passed"],
    }


def _axial_then_lateral_path(shape, waypoints, obstacles, *, kind, spec, sign):
    axial = continuous_path(shape, waypoints[:2], obstacles)
    lateral = (
        driver_lateral_service_check(
            shape, waypoints[1], waypoints[2], obstacles, spec, sign
        )
        if kind == "gear"
        else servo_lateral_service_check(shape, waypoints[1], waypoints[2], obstacles)
    )
    return {
        **lateral,
        "segments": axial["segments"] + lateral["segments"],
        "passed": axial["passed"] and lateral["passed"],
    }


def input_service_path(name, shape, waypoints, obstacles, spec, sign):
    """Select each part's conservative envelope for the ordered release path."""
    if name.endswith("DriverGear") or name.endswith("Servo"):
        return _axial_then_lateral_path(
            shape,
            waypoints,
            obstacles,
            kind="gear" if name.endswith("DriverGear") else "servo",
            spec=spec,
            sign=sign,
        )
    if name.endswith("HornGearAdapter"):
        return adapter_service_check(shape, waypoints, obstacles, spec, sign)
    return continuous_path(shape, waypoints, obstacles)


def fastener_service_check(
    bolt,
    nut,
    obstacles,
    *,
    thread_diameter=2.0,
    nut_lateral_direction=None,
    retain_bolt=False,
    guided_nut=False,
    side_entry_nut=False,
    capture_depth_mm=1.0,
):
    """Check an ordered threaded-fastener release and its head-tool approach."""
    if retain_bolt and nut_lateral_direction is not None:
        raise ValueError("A retained bolt requires axial nut disengagement")
    if retain_bolt and guided_nut:
        raise ValueError("A guided nut requires screw-first withdrawal")
    if side_entry_nut and (retain_bolt or guided_nut or nut_lateral_direction is None):
        raise ValueError(
            "A side-entry nut requires a separate screw-first lateral route"
        )
    if (
        not isinstance(capture_depth_mm, (int, float))
        or isinstance(capture_depth_mm, bool)
        or not math.isfinite(capture_depth_mm)
        or capture_depth_mm <= 0
    ):
        raise ValueError("Nut capture depth must be a positive finite number")
    release_lift = capture_depth_mm + 0.2 if guided_nut else 0.2
    bore = next(
        face.Surface
        for face in nut.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - thread_diameter / 2) < TOL
    )
    axis = bore.Axis
    if (
        nut.optimalBoundingBox(False, False).Center
        - bolt.optimalBoundingBox(False, False).Center
    ).dot(axis) < 0:
        axis = -axis
    thread_points = [
        vertex.Point.dot(axis)
        for face in bolt.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - thread_diameter / 2) < TOL
        for vertex in face.Vertexes
    ]
    thread_start, thread_end = min(thread_points), max(thread_points)
    nut_start = min(vertex.Point.dot(axis) for vertex in nut.Vertexes)
    nut_travel = thread_end - nut_start + 0.2
    bolt_travel = thread_end - thread_start + 0.2
    if nut_lateral_direction is None:
        nut_waypoints = [
            (0, 0, 0),
            tuple(axis * (max(release_lift, nut_travel) if guided_nut else nut_travel)),
        ]
        sequence = "Disengage the nut beyond the thread tip, then withdraw the bolt."
    else:
        offset = axis * release_lift
        lateral = App.Vector(*nut_lateral_direction) * 25
        nut_waypoints = [(0, 0, 0), tuple(offset), tuple(offset + lateral)]
        sequence = "Hold the nut and withdraw the bolt first, then move the unthreaded nut 0.2 mm away from its seat and 25 mm sideways."
    if guided_nut:
        sequence = (
            "Keep the nut flat between its guides while turning and withdrawing "
            "the screw from the head side. With the screw fully removed, lift "
            f"the nut axially at least {release_lift:g} mm to clear the {capture_depth_mm:g} mm capture walls before any "
            "sideways removal. For assembly seat the aligned hex nut flat and "
            "turn the screw head; do not try to turn the nut between the guides."
        )
    released_nut = nut
    if guided_nut or side_entry_nut:
        # The screw is already out. Fill its bore so an exact planar exterior
        # sweep can follow the free nut laterally, including a rotated module.
        # An axis-aligned box around a tilted bore would invent corner stock.
        bearing_face = next(
            face
            for face in nut.Faces
            if type(face.Surface).__name__ == "Plane"
            and face.normalAt(0, 0).dot(axis) < -0.99
        )
        nut_height = max(vertex.Point.dot(axis) for vertex in nut.Vertexes) - nut_start
        released_nut = Part.Face(bearing_face.OuterWire).extrude(axis * nut_height)
    nut_path = continuous_path(released_nut, nut_waypoints, obstacles)
    bolt_path = (
        None
        if retain_bolt
        else continuous_path(
            bolt,
            [(0, 0, 0), tuple(axis * -bolt_travel)],
            {**obstacles, "seated_guided_nut": nut}
            if guided_nut or side_entry_nut
            else obstacles,
        )
    )
    if retain_bolt:
        sequence = (
            "Disengage only the rear nut beyond the thread tip. Keep the bolt seated "
            "in the servo ear and carry it with the checked complete servo unit; "
            "remove it only after the horn adapter is detached off the bridge."
        )
    head_projection = min(vertex.Point.dot(axis) for vertex in bolt.Vertexes)
    tool_origin = bore.Center + axis * (head_projection - 0.1 - bore.Center.dot(axis))
    tool_radius = 1.0 if thread_diameter == 2 else 1.6
    tool = Part.makeCylinder(tool_radius, 15, tool_origin, -axis)
    tool_hits = {
        name: volume
        for name, shape in obstacles.items()
        if (volume := intersection_volume(tool, shape)) > TOL
    }
    return {
        "nut_axial_removal": nut_path,
        "bolt_axial_withdrawal": bolt_path,
        "bolt_retained_in_servo_unit": retain_bolt,
        "screw_first_with_nut_held_in_guides": guided_nut,
        "screw_first_side_entry_nut": side_entry_nut,
        "minimum_nut_lift_before_lateral_mm": release_lift,
        "released_nut_bore_filled_after_screw_removal": guided_nut or side_entry_nut,
        "driver_approach_collisions": tool_hits,
        "tool_reserve_radius_mm": tool_radius,
        "nut_thread_disengagement_travel_mm": nut_travel,
        "bolt_withdrawal_travel_mm": None if retain_bolt else bolt_travel,
        "service_order": sequence,
        "scope": "Axial nut disengagement includes 0.2 mm clearance; bolt withdrawal is checked only when the bolt is removed. Retained-bolt mode requires a separate complete-unit motion check. Named obstacles stay installed at neutral tilt. Cylindrical driver reservation: 1 mm radius for M2 hex socket, 1.6 mm for the M1.6 Phillips kit head. This is a tool-space envelope, not a measured bit or proof of recess engagement. Handling the released nut, bit match and wrench handling remain unverified.",
        "passed": nut_path["passed"]
        and (retain_bolt or bolt_path["passed"])
        and not tool_hits,
    }
