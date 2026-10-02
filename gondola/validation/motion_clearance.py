"""Continuous output-carrier clearance from live solids, including axial play.

The carrier is enclosed in three solids invariant under a complete rotation
about its native Y axis. Containment is a BRep difference, including curved
faces. Distances from these envelopes to actual fixed fasteners therefore bound
all output angles, without replacing close sampled poses with a motion proof.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import world_shape

TOL = 1e-5
MINIMUM_METAL_RESERVE_MM = 1.5
# Declared, reviewable envelope; changes to the live carrier must still fit it.
GUARD_SPHERE_RADIUS_MM = math.hypot(16.0, 25.0)
RIB_CYLINDER_RADIUS_MM = math.hypot(16.0, 4.0)
CARRIER_HALF_WIDTH_MM = 31.25
FORWARD_RIB_CYLINDER_RADIUS_MM = math.hypot(16.0, 4.0)
FORWARD_RIB_HALF_WIDTH_MM = 29.25
# This band lies on the clamp end and the retained bearing-cup stop sectors.
STOP_WITNESS_INNER_MM = 2.81
STOP_WITNESS_OUTER_MM = 3.20


def _in_pod_coordinates(obj, pod):
    shape = world_shape(obj)
    shape.Placement = pod.getGlobalPlacement().inverse().multiply(shape.Placement)
    return shape


def _solid(shape):
    return not shape.isNull() and shape.isValid() and bool(shape.Solids)


def _y_faces(shape):
    """Collect actual planar faces normal to the physical output axis."""
    result = []
    for face in shape.Faces:
        if type(face.Surface).__name__ != "Plane":
            continue
        normal = face.normalAt(0, 0)
        if abs(abs(normal.y) - 1) <= 1e-7:
            result.append((face.CenterOfMass.y, face))
    return result


def _annular_face(y):
    centre, axis = App.Vector(0, y, 0), App.Vector(0, 1, 0)
    outer = Part.Face(Part.Wire(Part.makeCircle(STOP_WITNESS_OUTER_MM, centre, axis)))
    inner = Part.Face(Part.Wire(Part.makeCircle(STOP_WITNESS_INNER_MM, centre, axis)))
    return outer.cut(inner)


def _faces_at(faces, y):
    return Part.makeCompound(
        [face for position, face in faces if abs(position - y) < TOL]
    )


def carrier_axial_travel(doc, prefix):
    """Measure opposing gear/housing and carrier/housing annular stops.

    Both moving faces are on the same rotor and shaft. The split inboard
    housing lies between them. Full-circle radial witnesses bound contact
    through every angle without using bearing shields as thrust stops.
    """
    pod = doc.getObject(prefix + "Pod")
    names = (
        prefix + "MotorCarrier",
        prefix + "OutputGear",
        "PropulsionFixedFrame",
        prefix + "BearingCap",
    )
    objects = [doc.getObject(name) for name in names]
    if pod is None or any(obj is None for obj in objects):
        return {
            "pod": prefix,
            "passed": False,
            "error": "Missing rotor axial stop component",
        }
    shapes = [_in_pod_coordinates(obj, pod) for obj in objects]
    if prefix == "Starboard":
        shapes = [shape.mirror(App.Vector(), App.Vector(0, 1, 0)) for shape in shapes]
    carrier, gear, frame, cap = shapes
    fixed = Part.makeCompound([frame, cap])
    if not all(_solid(shape) for shape in shapes):
        return {
            "pod": prefix,
            "passed": False,
            "error": "Invalid rotor axial stop solid",
        }
    fixed_faces = _y_faces(fixed)
    # Normalize each side so +Y points outboard. The fixed housing must lie
    # between the gear's outer face and the carrier's inner face.
    ends = (
        (-1, carrier, carrier.optimalBoundingBox(False, False).YMin),
        (1, gear, gear.optimalBoundingBox(False, False).YMax),
    )
    rows = []
    for sign, moving, end in ends:
        witness = _annular_face(end)
        moving_area = _faces_at(_y_faces(moving), end).common(witness).Area
        direction = sign if prefix == "Port" else -sign
        row = {
            "direction": "negative" if direction < 0 else "positive",
            "moving_stop_part": prefix + ("MotorCarrier" if sign < 0 else "OutputGear"),
            "moving_end_y_mm": end,
            "witness_radial_band_mm": [STOP_WITNESS_INNER_MM, STOP_WITNESS_OUTER_MM],
            "witness_area_mm2": witness.Area,
            "moving_contact_area_mm2": moving_area,
            "passed": False,
        }
        if moving_area < 0.5 * witness.Area:
            row["error"] = "Moving stop lacks the required annular contact"
            rows.append(row)
            continue
        candidates = sorted(
            {round(y, 8) for y, _ in fixed_faces if sign * (y - end) >= -TOL},
            key=lambda y: sign * (y - end),
        )
        for position in candidates:
            fixed_witness = _annular_face(position)
            uncovered = fixed_witness.cut(_faces_at(fixed_faces, position)).Area
            fixed_area = fixed_witness.Area - uncovered
            overlap = moving_area + fixed_area - fixed_witness.Area
            if overlap < 0.25 * witness.Area - TOL:
                continue
            travel = sign * (position - end)
            row.update(
                frame_stop_y_mm=position,
                frame_uncovered_witness_area_mm2=uncovered,
                frame_contact_area_mm2=fixed_area,
                all_angles_contact_lower_bound_mm2=overlap,
                required_contact_lower_bound_mm2=0.25 * witness.Area,
                travel_mm=max(0.0, travel),
                passed=travel >= -TOL,
            )
            break
        if not row["passed"]:
            row["error"] = "No fixed stop with sufficient all-angle contact"
        rows.append(row)
    rows.sort(key=lambda row: row["direction"] != "negative")
    passed = all(row["passed"] for row in rows)
    return {
        "pod": prefix,
        "stops": rows,
        "negative_mm": rows[0].get("travel_mm"),
        "positive_mm": rows[1].get("travel_mm"),
        "maximum_mm": max(row["travel_mm"] for row in rows) if passed else None,
        "scope": "Actual gear/housing and carrier/housing planar contacts in a rotation-invariant annulus. Inclusion-exclusion proves at least 25 percent contact at every rotor angle. Bearing shields are not stops. This requires the shaft/carrier clamp and purchased gear set screw to retain the rotating stack; CAD does not qualify their grip, preload, wear or strength.",
        "passed": passed,
    }


def carrier_metal_clearance_check(doc, prefix):
    """Prove the required reserve from the rotating carrier to fixed mounting metalwork.

    A guard sphere, a full-width clamp cylinder and an axially shorter cylinder
    for the forward connections are necessary. A sphere enclosing the full carrier
    would include empty corners and incorrectly consume the nut clearance.
    After proving actual BRep containment, the minimum envelope-to-fastener
    distance is reduced by the measured maximum axial travel. Euclidean
    distance is 1-Lipschitz under translation, so this remains a conservative
    bound for simultaneous full rotation and any allowed axial displacement.
    """
    pod = doc.getObject(prefix + "Pod")
    names = [
        prefix + suffix
        for suffix in ("MotorCarrier", "Motor", "PropellerDisk", "Shaft")
    ] + [
        prefix + "OutputClamp" + side + kind
        for side in (("Negative",) if prefix == "Port" else ("Positive",))
        for kind in ("Bolt", "Nut")
    ]
    metal_names = [
        prefix + "ServoEar" + side + kind
        for side in ("Lower", "Upper")
        for kind in ("Bolt", "Nut")
    ]
    metal_names.extend(
        prefix + "BearingCap" + side + kind
        for side in ("Negative", "Positive", "Input")
        for kind in ("Bolt", "Nut")
    )
    objects = [doc.getObject(name) for name in names + metal_names]
    if pod is None or any(obj is None for obj in objects):
        return {
            "pod": prefix,
            "passed": False,
            "error": "Missing carrier or fixed mounting hardware",
        }
    shapes = dict(
        zip(names + metal_names, (_in_pod_coordinates(obj, pod) for obj in objects))
    )
    if not all(_solid(shape) for shape in shapes.values()):
        return {
            "pod": prefix,
            "passed": False,
            "error": "Invalid carrier or hardware solid",
        }
    sphere = Part.makeSphere(GUARD_SPHERE_RADIUS_MM)
    cylinder = Part.makeCylinder(
        RIB_CYLINDER_RADIUS_MM,
        CARRIER_HALF_WIDTH_MM * 2,
        App.Vector(0, -CARRIER_HALF_WIDTH_MM, 0),
        App.Vector(0, 1, 0),
    )
    forward = Part.makeCylinder(
        FORWARD_RIB_CYLINDER_RADIUS_MM,
        FORWARD_RIB_HALF_WIDTH_MM * 2,
        App.Vector(0, -FORWARD_RIB_HALF_WIDTH_MM, 0),
        App.Vector(0, 1, 0),
    )
    envelope = sphere.fuse(cylinder).fuse(forward)
    containment = [
        {"object": name, "outside_envelope_mm3": abs(shapes[name].cut(envelope).Volume)}
        for name in names
    ]
    for row in containment:
        row["passed"] = row["outside_envelope_mm3"] <= TOL
    axial = carrier_axial_travel(doc, prefix)
    rows, frame_rows = [], []
    if axial["passed"]:
        from .rotation_envelope import full_orbit_envelope

        frame = Part.makeCompound(
            [
                _in_pod_coordinates(doc.PropulsionFixedFrame, pod),
                _in_pod_coordinates(doc.getObject(prefix + "BearingCap"), pod),
            ]
        )
        for name in names:
            orbit, evidence = full_orbit_envelope(shapes[name], (0, 0, 0))
            gap = orbit.distToShape(frame)[0]
            remaining = gap - axial["maximum_mm"]
            frame_rows.append(
                {
                    "moving": name,
                    "envelope": evidence,
                    "nominal_frame_gap_lower_bound_mm": gap,
                    "remaining_gap_after_axial_travel_mm": remaining,
                    "passed": remaining >= -TOL,
                }
            )
        for name in metal_names:
            distances = {
                "guard_sphere": sphere.distToShape(shapes[name])[0],
                "ribs_and_clamps_cylinder": cylinder.distToShape(shapes[name])[0],
                "inboard_forward_ribs_cylinder": forward.distToShape(shapes[name])[0],
            }
            lower_bound = min(distances.values()) - axial["maximum_mm"]
            rows.append(
                {
                    "fixed": name,
                    "nominal_envelope_distance_mm": distances,
                    "axial_travel_reserve_mm": axial["maximum_mm"],
                    "continuous_clearance_lower_bound_mm": lower_bound,
                    "passed": lower_bound >= MINIMUM_METAL_RESERVE_MM - TOL,
                }
            )
    return {
        "pod": prefix,
        "moving_objects": names,
        "minimum_required_reserve_mm": MINIMUM_METAL_RESERVE_MM,
        "envelope": {
            "guard_sphere_radius_mm": GUARD_SPHERE_RADIUS_MM,
            "rib_cylinder_radius_mm": RIB_CYLINDER_RADIUS_MM,
            "rib_cylinder_y_mm": [-CARRIER_HALF_WIDTH_MM, CARRIER_HALF_WIDTH_MM],
            "forward_rib_cylinder_radius_mm": FORWARD_RIB_CYLINDER_RADIUS_MM,
            "forward_rib_cylinder_y_mm": [
                -FORWARD_RIB_HALF_WIDTH_MM,
                FORWARD_RIB_HALF_WIDTH_MM,
            ],
            "containment": containment,
        },
        "axial_travel": axial,
        "fixed_hardware": rows,
        "frame_clearance": frame_rows,
        "minimum_clearance_lower_bound_mm": min(
            (row["continuous_clearance_lower_bound_mm"] for row in rows), default=None
        ),
        "scope": "Continuous full 360-degree output rotation plus measured axial play, from live carrier, motor, propeller and clamp BRep containment and distances to live servo-module and split-bearing-cap mounting bolts/nuts. Complete orbit cylinders additionally prove no frame penetration through the measured axial travel; equality is the classified carrier/frame stop contact. The required reserve is a design margin, not a manufacturing-tolerance certification. Bearing/shaft mating, gear teeth, carrier/frame and gear/frame axial-stop contact, input drive and wiring are separate functional interfaces.",
        "passed": axial["passed"]
        and all(row["passed"] for row in containment)
        and len(frame_rows) == len(names)
        and all(row["passed"] for row in frame_rows)
        and len(rows) == len(metal_names)
        and all(row["passed"] for row in rows),
    }
