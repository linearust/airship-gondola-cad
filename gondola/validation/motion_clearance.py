"""Continuous output-carrier clearance from live solids, including axial play.

The carrier is enclosed in two solids invariant under a complete rotation
about its native Y axis. Containment is a BRep difference, including curved
faces. Distances from these envelopes to actual cap fasteners therefore bound
all output angles, without replacing close sampled poses with a motion proof.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import world_shape

TOL = 1e-5
MINIMUM_METAL_RESERVE_MM = 1.5
# Declared, reviewable envelope; changes to the live carrier must still fit it.
GUARD_SPHERE_RADIUS_MM = math.hypot(13.0, 24.3)
RIB_CYLINDER_RADIUS_MM = math.hypot(13.0, 3.2)
CARRIER_HALF_WIDTH_MM = 26.0
# This band lies on the clamp end and the complete bearing-cup shoulder.
STOP_WITNESS_INNER_MM = 2.95
STOP_WITNESS_OUTER_MM = 3.05


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
    """Measure both travel limits using real, rotation-independent stop faces.

    A complete fixed annular shoulder is required at each frame stop. The
    carrier must have an actual end-face patch in that radial band. Rotating
    this patch cannot escape a complete annulus, so it still stops axial travel
    at every tilt. This proves a nominal geometric stop, not its loaded wear,
    strength, printed tolerance, bearing preload or friction qualification.
    """
    pod = doc.getObject(prefix + "Pod")
    carrier_obj = doc.getObject(prefix + "MotorCarrier")
    frame_obj = doc.getObject("PropulsionFixedFrame")
    if any(obj is None for obj in (pod, carrier_obj, frame_obj)):
        return {
            "pod": prefix,
            "passed": False,
            "error": "Missing carrier or fixed frame",
        }
    carrier = _in_pod_coordinates(carrier_obj, pod)
    frame = _in_pod_coordinates(frame_obj, pod)
    if not all(_solid(shape) for shape in (carrier, frame)):
        return {
            "pod": prefix,
            "passed": False,
            "error": "Invalid carrier or frame solid",
        }
    carrier_faces, frame_faces = _y_faces(carrier), _y_faces(frame)
    bounds = carrier.optimalBoundingBox(False, False)
    stops = []
    for sign, end in ((-1, bounds.YMin), (1, bounds.YMax)):
        witness = _annular_face(end)
        end_faces = _faces_at(carrier_faces, end)
        moving_area = end_faces.common(witness).Area
        row = {
            "direction": "negative" if sign < 0 else "positive",
            "carrier_end_y_mm": end,
            "witness_radial_band_mm": [STOP_WITNESS_INNER_MM, STOP_WITNESS_OUTER_MM],
            "witness_area_mm2": witness.Area,
            "carrier_contact_area_mm2": moving_area,
            "passed": False,
        }
        # At least half the witness band must belong to an actual end face;
        # an isolated point or a tiny remnant is not accepted as an axial stop.
        if moving_area < 0.5 * witness.Area:
            row["error"] = "Carrier end lacks the required annular stop contact"
            stops.append(row)
            continue
        candidate_positions = sorted(
            {round(y, 8) for y, _ in frame_faces if sign * (y - end) >= -TOL},
            key=lambda y: sign * (y - end),
        )
        for position in candidate_positions:
            stop_witness = _annular_face(position)
            fixed_faces = _faces_at(frame_faces, position)
            uncovered = stop_witness.cut(fixed_faces).Area
            if uncovered > TOL:
                continue
            travel = sign * (position - end)
            row.update(
                frame_stop_y_mm=position,
                frame_uncovered_witness_area_mm2=uncovered,
                travel_mm=max(0.0, travel),
                passed=travel >= -TOL,
            )
            break
        if not row["passed"]:
            row["error"] = "No complete fixed annular end stop was found"
        stops.append(row)
    passed = all(row["passed"] for row in stops)
    return {
        "pod": prefix,
        "stops": stops,
        "negative_mm": stops[0].get("travel_mm"),
        "positive_mm": stops[1].get("travel_mm"),
        "maximum_mm": max(row["travel_mm"] for row in stops) if passed else None,
        "scope": "Actual planar carrier ends against complete fixed annular shoulder witnesses. Valid through all output rotations; nominal geometry only, without manufacturing tolerance or loaded stop qualification.",
        "passed": passed,
    }


def carrier_metal_clearance_check(doc, prefix):
    """Prove the required reserve from the rotating carrier to cap metalwork.

    Both a sphere around the guard and a narrower full-width cylinder around
    its connections are necessary. A single sphere enclosing the full carrier
    would include empty corners and incorrectly consume the nut clearance.
    After proving actual BRep containment, the minimum envelope-to-fastener
    distance is reduced by the measured maximum axial travel. Euclidean
    distance is 1-Lipschitz under translation, so this remains a conservative
    bound for simultaneous full rotation and any allowed axial displacement.
    """
    pod = doc.getObject(prefix + "Pod")
    names = [prefix + "MotorCarrier"] + [
        prefix + "OutputClamp" + side + kind
        for side in ("Negative", "Positive")
        for kind in ("Bolt", "Nut")
    ]
    metal_names = [
        prefix + "OutputBearingCap" + side + kind
        for side in ("Negative", "Positive")
        for kind in ("Bolt", "Nut")
    ]
    objects = [doc.getObject(name) for name in names + metal_names]
    if pod is None or any(obj is None for obj in objects):
        return {
            "pod": prefix,
            "passed": False,
            "error": "Missing carrier or cap hardware",
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
    envelope = sphere.fuse(cylinder)
    containment = [
        {"object": name, "outside_envelope_mm3": abs(shapes[name].cut(envelope).Volume)}
        for name in names
    ]
    for row in containment:
        row["passed"] = row["outside_envelope_mm3"] <= TOL
    axial = carrier_axial_travel(doc, prefix)
    rows = []
    if axial["passed"]:
        for name in metal_names:
            distances = {
                "guard_sphere": sphere.distToShape(shapes[name])[0],
                "ribs_and_clamps_cylinder": cylinder.distToShape(shapes[name])[0],
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
            "containment": containment,
        },
        "axial_travel": axial,
        "fixed_hardware": rows,
        "minimum_clearance_lower_bound_mm": min(
            (row["continuous_clearance_lower_bound_mm"] for row in rows), default=None
        ),
        "scope": "Continuous full 360-degree output rotation plus measured axial play, from live carrier/clamp BRep containment and distances to live bearing-cap bolts/nuts. The required reserve is a design margin, not a manufacturing-tolerance certification. Bearing/shaft mating, gear teeth, carrier/frame axial-stop contact, input drive and wiring are separate functional interfaces.",
        "passed": axial["passed"]
        and all(row["passed"] for row in containment)
        and len(rows) == len(metal_names)
        and all(row["passed"] for row in rows),
    }
