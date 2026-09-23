"""Continuous separation of installed solids belonging to different tilt groups."""

import math

from gondola.cad import belongs_to_group, world_shape
from gondola.contracts.design import MODULE_STATIONS
from gondola.contracts.drive import drive_for_document
from gondola.parts import rail

from .geometry import intersection_volume
from .rotation_envelope import full_orbit_envelope

MINIMUM_GAP_MM = 0.1
TOL = 1e-7


def _input_drive_membership(parts):
    """Require the selected metal-stub mechanism to share each input motion."""
    suffixes = (
        "ServoHorn",
        "DriverGear",
        "HornGearAdapter",
        "HornGearClampNearBolt",
        "HornGearClampFarBolt",
        "HornGearClampNearNut",
        "HornGearClampFarNut",
        "InputShaft",
        "InputShaftClampBolt",
        "InputShaftClampNut",
    )
    rows = []
    for prefix in ("Port", "Starboard"):
        expected = {prefix + suffix for suffix in suffixes}
        actual = {
            part["name"] for part in parts if part["group"] == prefix + "InputDrive"
        }
        rows.append(
            {
                "group": prefix + "InputDrive",
                "expected_parts": sorted(expected),
                "actual_parts": sorted(actual),
                "passed": actual == expected,
            }
        )
    return rows


def _static_expression_contract(doc, spec):
    """Allow only the source architecture's closed, manual-control dependencies.

    The four tilt formulas are the only expressions depending on the pod motion.
    Every other permitted formula reads literal manual properties. Inspecting
    *all* expression engines also rejects an expression added to one of those
    input properties, an intervening group, or an indirect helper object. A
    finite pose probe cannot establish this absence of nonlinear dependence.
    Static placements without expressions remain valid, including a moved root.
    """
    allowed = {}
    for station in MODULE_STATIONS:
        control = "AssemblySettings." + station.clamp_control
        allowed[station.object_name] = {
            "Placement.Base.x": "RailPositionX",
            "Placement.Base.y": f"{control}==0?{rail.CLAMP_SHIFT_Y:g}mm:-{rail.CLAMP_SHIFT_Y:g}mm",
        }
        for suffix in ("Screw", "Nut"):
            allowed[station.object_name + "RailClamp" + suffix] = {
                "Placement.Rotation.Angle": control + "==0?0deg:180deg"
            }
    for prefix in ("Port", "Starboard"):
        allowed[prefix + "Pod"] = {
            "Placement.Rotation.Angle": "min(MaximumTilt;max(MinimumTilt;Tilt))"
        }
        allowed[prefix + "InputDrive"] = {
            "Placement.Rotation.Angle": f"-{prefix}Pod.Placement.Rotation.Angle/{spec.ratio:g}"
        }
    for coordinate in ("Roll", "Pitch"):
        allowed["Optical" + coordinate + "Stage"] = {
            "Placement.Rotation.Angle": f"min(MaximumAngle;max(MinimumAngle;{coordinate}))"
        }
    allowed["ModuleBatteryEnvelope"] = {
        "Placement.Base.x": "CentreX-(Length*cos(InPlaneRotation)-Width*sin(InPlaneRotation))/2",
        "Placement.Base.y": "CentreY-(Length*sin(InPlaneRotation)+Width*cos(InPlaneRotation))/2",
        "Placement.Base.z": "BottomZ",
        "Placement.Rotation.Angle": "InPlaneRotation",
    }
    count = 0
    for obj in doc.Objects:
        for path, expression in getattr(obj, "ExpressionEngine", ()):
            path = path.lstrip(".")
            if allowed.get(obj.Name, {}).get(path) != "".join(expression.split()):
                raise ValueError(
                    "Native motion expression contract rejects " + obj.Name + "." + path
                )
            count += 1
    return {
        "checked_expression_count": count,
        "scope": "Closed source expression allowlist across every native object. Additional expressions on manual controls, child features, intervening groups or indirect helper properties are rejected; static placements are allowed.",
        "passed": True,
    }


def _gap(first, second):
    return max(first[0] - second[1], second[0] - first[1], 0.0)


def _part(shape, name, *, group="Fixed", prefix="", axis=(0, 0, 0), rate=0.0):
    bounds = shape.BoundBox
    limits = [
        (bounds.XMin, bounds.XMax),
        (bounds.YMin, bounds.YMax),
        (bounds.ZMin, bounds.ZMax),
    ]
    envelope, radius, orbit = shape, 0.0, limits
    if rate:
        envelope, evidence = full_orbit_envelope(shape, axis)
        radius = evidence["radius_mm"]
        orbit = [
            (axis[0] - radius, axis[0] + radius),
            limits[1],
            (axis[2] - radius, axis[2] + radius),
        ]
    return dict(
        shape=shape,
        name=name,
        group=group,
        prefix=prefix,
        axis=axis,
        rate=rate,
        bounds=limits,
        envelope=envelope,
        radius=radius,
        orbit=orbit,
    )


def _certify_pair(first, second, *, max_depth=18, max_evaluations=2048):
    """Positive lower bounds cover closed intervals; contact/work limits fail."""
    import FreeCAD as App

    result = {"parts": [first["name"], second["name"]]}
    bounds = [
        ("invariant axial projection", _gap(first["bounds"][1], second["bounds"][1])),
        (
            "full orbit containing boxes",
            math.sqrt(
                sum(_gap(a, b) ** 2 for a, b in zip(first["orbit"], second["orbit"]))
            ),
        ),
    ]
    for method, bound in bounds:
        if bound > MINIMUM_GAP_MM + TOL:
            return dict(
                result,
                passed=True,
                method=method,
                guaranteed_gap_mm=bound,
                evaluations=0,
            )
    bound = first["envelope"].distToShape(second["envelope"])[0]
    if bound > MINIMUM_GAP_MM + TOL:
        return dict(
            result,
            passed=True,
            method="full orbit containing cylinders",
            guaranteed_gap_mm=bound,
            evaluations=1,
        )
    if first["prefix"] and second["prefix"] and first["prefix"] != second["prefix"]:
        return dict(
            result,
            passed=False,
            error="Independent axes have overlapping full-orbit envelopes; synchronized samples cannot certify them.",
        )

    pending, count, intervals = [(-180.0, 180.0, 0)], 0, 0
    lower, minimum = math.inf, math.inf
    while pending:
        start, end, depth = pending.pop()
        midpoint = (start + end) / 2
        shapes = []
        for part in (first, second):
            shape = part["shape"].copy()
            if part["rate"]:
                shape.rotate(
                    App.Vector(*part["axis"]),
                    App.Vector(0, 1, 0),
                    part["rate"] * midpoint,
                )
            shapes.append(shape)
        distance = shapes[0].distToShape(shapes[1])[0]
        count += 1
        minimum = min(minimum, distance)
        if distance <= MINIMUM_GAP_MM + TOL:
            return dict(
                result,
                passed=False,
                method="insufficient nominal clearance",
                output_angle_deg=midpoint,
                gap_mm=distance,
                intersection_mm3=intersection_volume(*shapes),
                evaluations=count,
            )
        half_interval = math.radians((end - start) / 2)
        displacement = sum(
            2
            * part["radius"]
            * math.sin(min(math.pi, abs(part["rate"]) * half_interval) / 2)
            for part in (first, second)
        )
        bound = distance - displacement
        if bound > MINIMUM_GAP_MM + TOL:
            lower = min(lower, bound)
            intervals += 1
        elif depth >= max_depth or count >= max_evaluations:
            return dict(
                result,
                passed=False,
                method="uncertified rotation interval",
                unresolved_interval_deg=[start, end],
                evaluations=count,
                sampled_minimum_gap_mm=minimum,
            )
        else:
            pending.extend(((midpoint, end, depth + 1), (start, midpoint, depth + 1)))
    return dict(
        result,
        passed=True,
        method="adaptive continuous rotation distance",
        guaranteed_gap_mm=lower,
        sampled_minimum_gap_mm=minimum,
        certified_intervals=intervals,
        evaluations=count,
    )


def _cylindrical_faces(part, radius, axis):
    """Locate real coaxial bore/shaft faces rather than trusting part labels."""
    for face in part["shape"].Faces:
        surface = face.Surface
        if type(surface).__name__ != "Cylinder":
            continue
        if (
            abs(surface.Radius - radius) < TOL
            and abs(abs(surface.Axis.y) - 1) < TOL
            and math.hypot(surface.Center.x - axis[0], surface.Center.z - axis[2]) < TOL
        ):
            yield face


def _cylindrical_datum(part, radius, axis):
    return any(_cylindrical_faces(part, radius, axis))


def _horn_case_clearance(horn, servo):
    """Exempt only the sourced spline volume, never the entire servo case.

    Both solids are already in the neutral propulsion frame. Deriving the
    spline interval from its actual cylindrical face preserves native mirrored
    placement. Its length must still match the sourced projection. The full
    remaining case and both ears stay in the continuous motion certificate.
    """
    import FreeCAD as App
    import Part

    from gondola.contracts.equipment_interfaces import PROPULSION_EVIDENCE

    evidence = PROPULSION_EVIDENCE["X06"]
    radius = evidence["spline_major_diameter_mm"] / 2
    length = evidence["overall_height_with_spline_mm"] - evidence["case_size_mm"][2]
    faces = list(_cylindrical_faces(servo, radius, horn["axis"]))
    if len(faces) != 1 or abs(faces[0].BoundBox.YLength - length) > TOL:
        return {"passed": False, "error": "Missing unique sourced servo spline face"}
    bounds = faces[0].BoundBox
    axis = horn["axis"]
    spline = Part.makeCylinder(
        radius,
        length,
        App.Vector(axis[0], bounds.YMin, axis[2]),
        App.Vector(0, 1, 0),
    )
    case = servo["shape"].cut(spline)
    if case.isNull() or not case.isValid() or not case.Solids:
        return {"passed": False, "error": "Invalid servo case after spline separation"}
    result = _certify_pair(horn, _part(case, servo["name"] + "CaseAndEars"))
    return {
        **result,
        "excluded_spline_radius_mm": radius,
        "excluded_spline_axial_interval_mm": [bounds.YMin, bounds.YMax],
        "scope": "Continuous nominal horn separation from the actual case and ears, excluding only the sourced cylindrical spline projection. The 0.1 mm screen is not a manufacturing allowance. Actual stock horn seating, case tolerances and the unmodeled OEM retaining screw require physical checks.",
    }


def _functional_pairs(parts, spec):
    """Classify exactly eight intended interfaces; these are not clearance proofs."""
    by_name, rows, keys = {part["name"]: part for part in parts}, [], set()
    for prefix in ("Port", "Starboard"):
        definitions = [
            (
                "OutputShaft" + side,
                "OutputBearing" + side,
                "Pod",
                "Fixed",
                1.5,
                1.5,
                "output bearing support",
            )
            for side in ("Negative", "Positive")
        ] + [
            (
                "ServoHorn",
                "Servo",
                "InputDrive",
                "Fixed",
                1.95,
                1.95,
                "stock horn/spline seating",
            ),
            (
                "OutputGear",
                "DriverGear",
                "Pod",
                "InputDrive",
                spec.output.bore_mm / 2,
                spec.driver.bore_mm / 2,
                "gear engagement and native coupled motion",
            ),
        ]
        for (
            a,
            b,
            first_group,
            second_group,
            first_radius,
            second_radius,
            check,
        ) in definitions:
            names = [prefix + a, prefix + b]
            row = {
                "parts": names,
                "required_separate_validation": check,
                "continuous_clearance_claimed": False,
            }
            keys.add(frozenset(names))
            first, second = (by_name.get(name) for name in names)
            if first is None or second is None:
                rows.append(
                    dict(
                        row,
                        classification_passed=False,
                        error="Missing functional interface part",
                    )
                )
                continue
            first_axis = first["axis"]
            second_axis = second["axis"] if second["rate"] else first_axis
            groups = first["group"] == prefix + first_group and second["group"] == (
                prefix + second_group if second_group != "Fixed" else "Fixed"
            )
            datums = _cylindrical_datum(
                first, first_radius, first_axis
            ) and _cylindrical_datum(second, second_radius, second_axis)
            overlap = intersection_volume(first["shape"], second["shape"])
            if a == "OutputGear":
                separation = math.hypot(
                    first_axis[0] - second_axis[0], first_axis[2] - second_axis[2]
                )
                datums = datums and abs(separation - spec.center_distance_mm) < TOL
            else:
                datums = datums and first["shape"].distToShape(second["shape"])[0] < TOL
            row = dict(
                row,
                classification_passed=groups and datums and overlap < 1e-5,
                neutral_intersection_mm3=overlap,
                native_groups_match=groups,
                cylindrical_datums_match=datums,
            )
            if a == "ServoHorn":
                row["case_and_ears_clearance"] = _horn_case_clearance(first, second)
                row["classification_passed"] = (
                    row["classification_passed"]
                    and row["case_and_ears_clearance"]["passed"]
                )
            rows.append(row)
    return rows, keys


def relative_motion_check(doc, module):
    """Audit nominal coupled motion; independently rotating opposite sides stay independent.

    Installed registry prints, hardware, equipment references and tape solids
    supplement the supplied module. Without a registry, every physical solid below the
    propulsion module must be explicitly supplied. Neither path ignores a solid
    merely because its Shape is missing or invalid. Rigid same-group contacts,
    flexible wiring, physical fits and additional axial travel need other checks.
    """
    import FreeCAD as App

    originals, rows, functional = {}, [], []
    result = {
        "minimum_nominal_gap_mm": MINIMUM_GAP_MM,
        "angle_domain_deg": [-180, 180],
        "scope": "Continuous nominal separation of supplied solids and registry PrintedParts, HardwareParts, ReferenceParts and TapeReferences, excluding clearance reserves and exactly eight separately classified functional interfaces. Horn/spline contact is excluded only within the sourced spline projection; each remaining case and both ears receive a separate continuous clearance check. Each input group must include its complete horn, gear, adapter, metal stub and clamp inventory. Same-group assembly contacts, jack-clamp retention, flexible wires, unmodeled gear set screws/OEM retaining screws, manufacturing tolerance, deformation and axial float are not certified here.",
    }
    try:
        spec = drive_for_document(doc)
        result["static_expression_contract"] = _static_expression_contract(doc, spec)
        root = doc.MainPropulsionModule
        declared = {
            obj.Name: obj
            for kind in ("printed", "hardware", "references")
            for obj in module[kind]
        }
        actual = {
            obj.Name
            for obj in doc.Objects
            if "Shape" in obj.PropertiesList
            and belongs_to_group(obj, root)
            and getattr(obj, "Role", "") != "Clearance"
        }
        if not actual.issubset(declared):
            raise ValueError(
                "Module inventory omits physical descendants: "
                + ", ".join(sorted(actual - set(declared)))
            )
        registry = doc.getObject("DesignRegistry")
        if registry is not None:
            for category in (
                "PrintedParts",
                "HardwareParts",
                "ReferenceParts",
                "TapeReferences",
            ):
                declared.update(
                    (obj.Name, obj) for obj in getattr(registry, category, [])
                )
        groups = {}
        for prefix in ("Port", "Starboard"):
            pod = doc.getObject(prefix + "Pod")
            if pod is None:
                raise ValueError("Missing native output pod")
            originals[prefix] = float(pod.Tilt)
            pod.Tilt = 0
            for suffix, rate in (("Pod", 1.0), ("InputDrive", -1 / spec.ratio)):
                group = doc.getObject(prefix + suffix)
                if group is None:
                    raise ValueError("Missing native motion group")
                expected_expression = (
                    "min(MaximumTilt;max(MinimumTilt;Tilt))"
                    if suffix == "Pod"
                    else f"-{prefix}Pod.Placement.Rotation.Angle/{spec.ratio:g}"
                )
                expressions = {
                    key.lstrip("."): "".join(value.split())
                    for key, value in group.ExpressionEngine
                }
                if expressions != {"Placement.Rotation.Angle": expected_expression}:
                    raise ValueError(
                        "Native motion expression differs from the bounded linear contract"
                    )
                if suffix == "Pod" and (
                    float(group.MinimumTilt) != -180 or float(group.MaximumTilt) != 180
                ):
                    raise ValueError(
                        "Native motion limits differ from the certified domain"
                    )
                groups[group.Name] = dict(object=group, prefix=prefix, rate=rate)
        doc.recompute()
        inverse = root.getGlobalPlacement().inverse()
        for info in groups.values():
            placement = inverse.multiply(info["object"].getGlobalPlacement())
            info.update(placement=placement, axis=tuple(placement.Base))
        fixed_state = {}
        for name, obj in declared.items():
            if getattr(obj, "Role", "") == "Clearance":
                continue
            if (
                "Shape" not in obj.PropertiesList
                or obj.Shape.isNull()
                or not obj.Shape.isValid()
                or not obj.Shape.Solids
            ):
                raise ValueError("Invalid installed solid: " + name)
            if not any(
                belongs_to_group(obj, info["object"]) for info in groups.values()
            ):
                shape = obj.Shape
                bounds = shape.BoundBox
                fixed_state[name] = (
                    obj.getGlobalPlacement(),
                    (
                        bounds.XMin,
                        bounds.XMax,
                        bounds.YMin,
                        bounds.YMax,
                        bounds.ZMin,
                        bounds.ZMax,
                        shape.Volume,
                    ),
                )
        # Verify the live expressions actually generate the assumed parallel-axis
        # motion. Root placement is never changed; transformed assemblies work.
        doc.PortPod.Tilt, doc.StarboardPod.Tilt = 1, -1
        doc.recompute()
        for info in groups.values():
            placement = inverse.multiply(info["object"].getGlobalPlacement())
            requested = 1 if info["prefix"] == "Port" else -1
            expected = App.Rotation(App.Vector(0, 1, 0), requested * info["rate"])
            delta = placement.Rotation.multiply(info["placement"].Rotation.inverted())
            if (
                placement.Base - info["placement"].Base
            ).Length > TOL or not delta.isSame(expected, TOL):
                raise ValueError(
                    "Native motion differs from the certified fixed Y-axis rotation"
                )
        for name, (before, dimensions) in fixed_state.items():
            obj = declared[name]
            after, bounds = obj.getGlobalPlacement(), obj.Shape.BoundBox
            current = (
                bounds.XMin,
                bounds.XMax,
                bounds.YMin,
                bounds.YMax,
                bounds.ZMin,
                bounds.ZMax,
                obj.Shape.Volume,
            )
            if (
                (after.Base - before.Base).Length > TOL
                or not after.Rotation.isSame(before.Rotation, TOL)
                or any(abs(a - b) > TOL for a, b in zip(dimensions, current))
            ):
                raise ValueError("Declared fixed obstacle changes with tilt: " + name)
        doc.PortPod.Tilt = doc.StarboardPod.Tilt = 0
        doc.recompute()
        parts = []
        for name, obj in declared.items():
            if getattr(obj, "Role", "") == "Clearance":
                continue
            if (
                "Shape" not in obj.PropertiesList
                or obj.Shape.isNull()
                or not obj.Shape.isValid()
                or not obj.Shape.Solids
            ):
                raise ValueError("Invalid installed solid: " + name)
            shape = world_shape(obj)
            shape.Placement = inverse.multiply(shape.Placement)
            membership = [
                info
                for info in groups.values()
                if belongs_to_group(obj, info["object"])
            ]
            if len(membership) > 1:
                raise ValueError("Ambiguous motion ancestry: " + name)
            arguments = {}
            if membership:
                info = membership[0]
                arguments = dict(
                    group=info["object"].Name,
                    prefix=info["prefix"],
                    axis=info["axis"],
                    rate=info["rate"],
                )
            parts.append(_part(shape, name, **arguments))
        membership = _input_drive_membership(parts)
        result["input_drive_membership"] = membership
        if not all(row["passed"] for row in membership):
            raise ValueError(
                "Selected input drive has missing or misplaced physical parts"
            )
        functional, exemptions = _functional_pairs(parts, spec)
        for index, first in enumerate(parts):
            for second in parts[index + 1 :]:
                if (
                    not (first["rate"] or second["rate"])
                    or first["group"] == second["group"]
                ):
                    continue
                if frozenset((first["name"], second["name"])) in exemptions:
                    continue
                rows.append(_certify_pair(first, second))
        result.update(
            installed_solid_count=len(parts),
            clearance_pair_count=len(rows),
            certified_pair_count=sum(row["passed"] for row in rows),
            passed=bool(rows)
            and all(row["passed"] for row in rows)
            and len(functional) == 8
            and all(row["classification_passed"] for row in functional),
        )
    except (AttributeError, KeyError, ValueError) as exc:
        result.update(passed=False, error=str(exc))
    finally:
        for prefix, angle in originals.items():
            doc.getObject(prefix + "Pod").Tilt = angle
        if originals:
            doc.recompute()
    return dict(result, functional_interfaces=functional, clearance_pairs=rows)
