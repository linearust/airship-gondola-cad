"""Saved common instrument platform: native datums, clamps and bounded motion.

The pitch certificate uses a chord bound for every point, not endpoint-only
sampling. Every moving descendant is checked against retained fixed solids;
contacts between co-moving installed instruments belong to their own interfaces.
"""

import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, placed_shape, union
from gondola.parts import instrument_mount, mounting_plate, rail

from .geometry import TOL, intersection_volume, local_shape, planar_contact_area
from .propulsion_service import continuous_path

V = App.Vector


def _pose(degrees):
    rotation = App.Rotation(V(0, 1, 0), degrees)
    return App.Placement(V(0, 0, 27.5) - rotation.multVec(V(0, 0, 8)), rotation)


def _box_gap(a, b):
    return math.sqrt(
        sum(
            max(
                0,
                getattr(a, axis + "Min") - getattr(b, axis + "Max"),
                getattr(b, axis + "Min") - getattr(a, axis + "Max"),
            )
            ** 2
            for axis in ("X", "Y", "Z")
        )
    )


def certify_pitch_clearance(
    shape, obstacle, *, low=-20.0, high=20.0, max_depth=18, max_evaluations=4096
):
    """Continuous rigid Y rotation; nonpositive distance or a limit fails closed."""
    if not all(math.isfinite(v) for v in (low, high)) or not -20 <= low <= high <= 20:
        raise ValueError("Finite ordered angle bounds within ±20 degrees required")
    for value in (shape, obstacle):
        if value.isNull() or not value.isValid() or not value.Solids:
            raise ValueError("Pitch certification requires valid solids")
    return _certify_validated(shape, obstacle, low, high, max_depth, max_evaluations)


def _certify_validated(
    shape, obstacle, low=-20.0, high=20.0, max_depth=18, max_evaluations=4096
):
    """Audit-local immutable solids have already passed the public validity gate."""
    b, o = shape.BoundBox, obstacle.BoundBox
    y_gap = max(o.YMin - b.YMax, b.YMin - o.YMax)
    if y_gap > TOL:
        return {
            "passed": True,
            "method": "invariant Y separation",
            "minimum_gap_bound_mm": y_gap,
            "evaluations": 0,
        }
    radius = math.hypot(
        max(abs(b.XMin), abs(b.XMax)), max(abs(b.ZMin - 8), abs(b.ZMax - 8))
    )
    # Every swept point lies in this XZ cylinder, regardless of angle. The
    # rectangular enclosure is deliberately conservative and cheap to reject.
    radial_box = App.BoundBox(
        -radius, b.YMin, 27.5 - radius, radius, b.YMax, 27.5 + radius
    )
    radial_gap = _box_gap(radial_box, o)
    if radial_gap > TOL:
        return {
            "passed": True,
            "method": "full-orbit conservative bounds",
            "minimum_gap_bound_mm": radial_gap,
            "evaluations": 0,
        }
    pending = [(low, high, 0)]
    evaluations = 0
    minimum = math.inf
    intervals = 0
    while pending:
        start, end, depth = pending.pop()
        if evaluations >= max_evaluations:
            return {
                "passed": False,
                "reason": "pitch certificate evaluation limit",
                "evaluations": evaluations,
            }
        middle = (start + end) / 2
        placed = placed_shape(shape, _pose(middle))
        chord = 2 * radius * math.sin(math.radians(end - start) / 4)
        gap = _box_gap(placed.BoundBox, o)
        if gap <= chord + TOL:
            gap = placed.distToShape(obstacle)[0]
        evaluations += 1
        if gap <= TOL:
            return {
                "passed": False,
                "angle_deg": middle,
                "gap_mm": gap,
                "overlap_mm3": intersection_volume(placed, obstacle),
                "evaluations": evaluations,
            }
        if gap > chord + TOL:
            minimum = min(minimum, gap - chord)
            intervals += 1
        elif depth >= max_depth:
            return {
                "passed": False,
                "reason": "unresolved pitch interval",
                "interval_deg": [start, end],
                "evaluations": evaluations,
            }
        else:
            pending.extend(((start, middle, depth + 1), (middle, end, depth + 1)))
    return {
        "passed": True,
        "method": "continuous midpoint distance minus maximum rotation chord",
        "angle_range_deg": [low, high],
        "minimum_gap_bound_mm": minimum,
        "evaluations": evaluations,
        "certified_intervals": intervals,
    }


def _exact(expected, actual):
    return {
        "missing_mm3": abs(expected.cut(actual).Volume),
        "extra_mm3": abs(actual.cut(expected).Volume),
    }


def _module_shape(obj, module):
    return placed_shape(
        local_shape(obj),
        module.getGlobalPlacement().inverse().multiply(obj.getGlobalPlacement()),
    )


def _split(shape, boxes):
    regions = [shape.common(box) for box in boxes]
    regions = [s for s in regions if s.Volume > TOL]
    if not regions or abs(shape.cut(union(regions)).Volume) > TOL:
        raise ValueError("Saved instrument stock exceeds its decomposition")
    return regions


def _physical_inventory(doc, stage, module, include_installed):
    registry = doc.getObject("DesignRegistry")
    if include_installed and registry is None:
        raise ValueError("Installed instrument audit requires DesignRegistry")
    moving = {
        o.Name: placed_shape(
            local_shape(o),
            stage.getGlobalPlacement().inverse().multiply(o.getGlobalPlacement()),
        )
        for o in doc.Objects
        if "Shape" in o.PropertiesList
        and not o.Shape.isNull()
        and belongs_to_group(o, stage)
    }
    if not moving or "ElectronicsMount" not in moving:
        raise ValueError("Missing moving instrument stock")
    if include_installed:
        names = set()
        for prop in (
            "PrintedParts",
            "ReferenceParts",
            "HardwareParts",
            "ClearanceVolumes",
            "TapeReferences",
        ):
            if prop not in registry.PropertiesList:
                raise ValueError("Incomplete installed inventory: " + prop)
            names.update(o.Name for o in getattr(registry, prop))
        if not set(moving) <= names:
            raise ValueError("Unregistered moving instrument descendant")
        if not {"ModuleFCEnvelope", "FCWiringClearanceReserve"} <= set(moving):
            raise ValueError("FC and wiring must share the rigid instrument stage")
    else:
        names = {
            o.Name
            for o in doc.Objects
            if "Shape" in o.PropertiesList
            and not o.Shape.isNull()
            and belongs_to_group(o, module)
        }
    fixed = {n: _module_shape(doc.getObject(n), module) for n in names - set(moving)}
    return moving, fixed


def _hardware_witnesses():
    # Independent nominal M3 primitives, including the nut's through bore.
    radius = 5.5 / math.sqrt(3)
    points = [
        V(radius * math.cos(i * math.pi / 3), radius * math.sin(i * math.pi / 3), 0)
        for i in range(6)
    ]
    nut = (
        Part.Face(Part.makePolygon(points + points[:1]))
        .extrude(V(0, 0, 2.4))
        .cut(Part.makeCylinder(1.5, 2.6, V(0, 0, -0.1)))
    )
    bolt = (
        Part.makeCylinder(3, 2, V(0, 0, -2))
        .fuse(Part.makeCylinder(1.5, 16))
        .removeSplitter()
    )
    result = {}
    for joint, x in (("Pivot", 0), ("Lock", 9)):
        for kind, source, seat in (("Bolt", bolt, -7.1), ("Nut", nut, 5.6)):
            shape = source.copy()
            shape.rotate(V(), V(1, 0, 0), -90)
            shape.translate(V(x, seat, 27.5))
            result["Instrument" + joint + kind] = shape
    return result


def centre_accessory_check(shape):
    """Literal central bore plus a six-mm-wide under-deck access corridor."""
    if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1:
        return {"passed": False, "reason": "Invalid saved instrument upper"}
    bore = Part.makeCylinder(1.3, 2.2, V(0, 0, 16.9))
    corridor = Part.makeBox(6, 12, 4, V(-3, -6, 13))
    head = Part.makeCylinder(2.25, 2, V(0, 0, 15))
    below = shape.common(Part.makeCylinder(2.25, 17, V()))
    available = 17 - below.BoundBox.ZMax if below.Volume > TOL else 17
    rows = {
        "centre_bore_overlap_mm3": intersection_volume(shape, bore),
        "under_deck_corridor_overlap_mm3": intersection_volume(shape, corridor),
        "nominal_M2_head_overlap_mm3": intersection_volume(shape, head),
    }
    return {
        **rows,
        "available_head_clearance_mm": available,
        "corridor_width_mm": 6,
        "corridor_height_mm": 4,
        "passed": all(v < TOL for v in rows.values()) and available >= 4 - TOL,
        "scope": "Actual common-plate centre bore and nominal4.5x2mm M2 head inside a6x12x4mm access corridor. This is an optional accessory clearance, not an installed screw selection or an unrestricted through-stack.",
    }


def _driver_shape(bolt):
    b = bolt.BoundBox
    return union(
        [
            Part.makeCylinder(
                2, 140, V(b.Center.x, b.YMin - 0.1, b.Center.z), V(0, -1, 0)
            ),
            Part.makeCylinder(
                6, 40, V(b.Center.x, b.YMin - 140.1, b.Center.z), V(0, -1, 0)
            ),
        ]
    )


def _terminal_connections(doc, module, moving, fixed, include_installed):
    """Validate saved source and terminal before explicitly disconnected setup."""
    if not include_installed:
        return {}, []
    from gondola.parts import propulsion_wiring

    from .propulsion_wiring import connection_check

    fc = doc.FCWiringClearanceReserve
    registry = doc.DesignRegistry
    propulsion = doc.MainPropulsionModule.getGlobalPlacement()
    stage = doc.InstrumentPitchStage.getGlobalPlacement()
    to_module = module.getGlobalPlacement().inverse()
    physical = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    names, rows = set(), []
    for prefix, sign in propulsion_wiring.PREFIX_SIGNS:
        name = prefix + "PhaseLeadLoopReserve"
        obj = doc.getObject(name)
        if obj is None or name not in fixed:
            raise ValueError("Missing FC terminal planning route: " + name)
        geometry = propulsion_wiring.route_geometry(sign, propulsion, stage)
        endpoint = to_module.multVec(propulsion.multVec(V(*geometry["points"][-1])))
        expected = placed_shape(geometry["shape"], to_module.multiply(propulsion))
        actual = fixed[name]
        connected = connection_check(
            actual,
            placed_shape(moving[fc.Name], doc.InstrumentPitchStage.Placement),
            tuple(endpoint),
        )
        identity = _exact(expected, actual)
        clearance_only = all(
            o in registry.ClearanceVolumes
            and o not in physical
            and getattr(o, "Role", "") == "Clearance"
            for o in (obj, fc)
        )
        passed = clearance_only and connected["passed"] and max(identity.values()) < TOL
        row = {
            "moving": fc.Name,
            "fixed": name,
            "clearance_only": clearance_only,
            "source_stock": identity,
            "current_pose_connection": connected,
            "passed": passed,
            "scope": "Saved-pose source identity and the declared8mm terminal connection are checked. Disconnect and move both phase leads clear before adjustment; their frozen planning corridors do not represent connected lead motion. Regenerate and validate the route after locking the chosen angle.",
        }
        rows.append(row)
        if not passed:
            raise ValueError("FC terminal reserve exception not established: " + name)
        names.add(name)
    return names, rows


def _propulsion_orbits(doc, module, include_installed):
    """Every registered moving propulsion body, enclosed for all its own angles."""
    if not include_installed:
        return {}, []
    from gondola.contracts import servo_horns

    from .rotation_envelope import full_orbit_envelope

    registry = doc.DesignRegistry
    physical = {
        o.Name
        for key in ("PrintedParts", "ReferenceParts", "HardwareParts", "TapeReferences")
        for o in getattr(registry, key)
    }
    envelopes, rows = {}, []
    for prefix in ("Port", "Starboard"):
        for suffix in ("InputDrive", "Pod"):
            group = doc.getObject(prefix + suffix)
            if group is None:
                raise ValueError("Missing propulsion motion group")
            members = [
                o
                for o in doc.Objects
                if "Shape" in o.PropertiesList
                and not o.Shape.isNull()
                and belongs_to_group(o, group)
                and getattr(o, "Role", "") != "Clearance"
            ]
            names = {o.Name for o in members}
            if not names or not names <= physical:
                raise ValueError("Incomplete registered propulsion motion stock")
            if suffix == "InputDrive":
                required = {
                    prefix + item
                    for item in (
                        "ServoHorn",
                        "DriverGear",
                        "HornGearAdapter",
                        "HornGearClampNearBolt",
                        "HornGearClampFarBolt",
                        "InputShaft",
                        "InputShaftClampBolt",
                        "InputShaftClampNut",
                    )
                }
                if not servo_horns.profile(side=prefix).threaded:
                    required.update(
                        prefix + "HornGearClamp" + side + "Nut"
                        for side in ("Near", "Far")
                    )
                if names != required:
                    raise ValueError(
                        "Input motion inventory differs from selected horn hardware"
                    )
            inverse = group.getGlobalPlacement().inverse()
            to_module = (
                module.getGlobalPlacement()
                .inverse()
                .multiply(group.getGlobalPlacement())
            )
            for obj in members:
                local = placed_shape(
                    local_shape(obj), inverse.multiply(obj.getGlobalPlacement())
                )
                envelope, evidence = full_orbit_envelope(local, (0, 0, 0))
                envelopes[obj.Name + "AllAngles"] = placed_shape(envelope, to_module)
                rows.append({"part": obj.Name, "group": group.Name, **evidence})
    return envelopes, rows


def instrument_check(doc, *, include_installed=True):
    """Fail closed on changed native structure, missing stock or blocked paths."""
    result = {
        "scope": "Nominal saved CAD, continuous setup pitch ±20 degrees and ordered neutral bench removal. Clamps are released only for setup; no in-flight levelling. Co-moving adhesive/device/fastener interfaces have separate checks. Actual print fit, clamp preload, creep, FC damper compliance, connected leads and hands remain unqualified.",
        "installed_scope": include_installed,
        "passed": False,
    }
    try:
        module, stage = (
            doc.getObject("ElectronicsEquipmentModule"),
            doc.getObject("InstrumentPitchStage"),
        )
        lower, upper = (
            doc.getObject("InstrumentMountBase"),
            doc.getObject("ElectronicsMount"),
        )
        if any(o is None for o in (module, stage, lower, upper)):
            raise ValueError("Missing two-part instrument mount")
        if (
            stage.getParentGeoFeatureGroup() != module
            or lower.getParentGeoFeatureGroup() != module
            or upper.getParentGeoFeatureGroup() != stage
        ):
            raise ValueError("Instrument native hierarchy changed")
        if any(not o.Placement.isSame(App.Placement(), 1e-7) for o in (lower, upper)):
            raise ValueError("Printed instrument local placement changed")
        command = float(stage.Pitch)
        if (
            not math.isfinite(command)
            or float(stage.MinimumAngle) != -20
            or float(stage.MaximumAngle) != 20
        ):
            raise ValueError("Instrument pitch control limits changed")
        bounded = "min(MaximumAngle;max(MinimumAngle;Pitch))"
        expected = {
            "Placement.Rotation.Angle": bounded,
            "Placement.Base.x": "-8mm*sin(" + bounded + ")",
            "Placement.Base.z": "27.5mm-8mm*cos(" + bounded + ")",
        }
        actual = {p.lstrip("."): "".join(e.split()) for p, e in stage.ExpressionEngine}
        if actual != expected or not stage.Placement.isSame(
            _pose(max(-20, min(20, command))), 1e-7
        ):
            raise ValueError(
                "Instrument axis compensation or bounded expression changed"
            )
        checks = {"native_structure_and_controls": True}
        low, high = local_shape(lower), local_shape(upper)
        shape_rows = {
            "lower": _exact(instrument_mount.base_shape(), low),
            "upper": _exact(instrument_mount.upper_shape(), high),
        }
        checks["saved_print_stock_matches_source"] = all(
            max(r.values()) < TOL for r in shape_rows.values()
        )
        crop = Part.makeBox(400, 100, 12.5, V(-200, -50, 0))
        checks["standard_shoe_unchanged_below_roof"] = (
            max(_exact(rail.mount_base_shape(), low.common(crop)).values()) < TOL
        )
        checks["all_standard_plate_openings_retained"] = (
            max(
                _exact(
                    mounting_plate.shape(),
                    high.common(Part.makeBox(100, 100, 2, V(-50, -50, 17))),
                ).values()
            )
            < TOL
        )
        from .manufacturing import material_length_on_line

        relief = Part.makeBox(7.2, 8.2, 2.4, V(8.8, -4.1, 14.6))
        # Extract actual slot air in a contained strip of the lug, then measure
        # its distance to the intended relief floor. No builder cutter is reused.
        strip = Part.makeBox(5.5, 0.2, 4.6, V(6.5, -0.1, 10))
        slot_air = strip.cut(high)
        relief_gap = slot_air.distToShape(relief)[0] if slot_air.Solids else 0
        web_material = material_length_on_line(high, (9, 0, 13), (9, 0, 14.6))
        checks["spare_slot_relief_retains_1p5mm_arc_web"] = (
            relief_gap >= 1.5 - TOL
            and web_material >= 1.6 - TOL
            and intersection_volume(high, relief) < TOL
        )
        centre = centre_accessory_check(high)
        checks["centre_accessory_head_clearance"] = centre["passed"]
        moving, fixed = _physical_inventory(doc, stage, module, include_installed)
        hardware = _hardware_witnesses()
        hardware_rows = {}
        for name, expected_shape in hardware.items():
            obj = doc.getObject(name)
            if obj is None or obj.getParentGeoFeatureGroup() != module:
                raise ValueError(
                    "Missing or misplaced fixed instrument hardware: " + name
                )
            shape = _module_shape(obj, module)
            hardware_rows[name] = _exact(expected_shape, shape)
            checks[name + "_stock"] = max(hardware_rows[name].values()) < TOL
            checks[name + "_no_lower_interference"] = (
                intersection_volume(shape, low) < TOL
            )
            checks[name + "_bearing_contact"] = planar_contact_area(shape, low) > 15
            checks[name + "_sku"] = obj.HardwareSKU == (
                "M3X16_BUTTON_HEAD" if name.endswith("Bolt") else "M3_HEX_NUT"
            )
        engagement = {}
        for joint in ("Pivot", "Lock"):
            bolt = _module_shape(
                doc.getObject("Instrument" + joint + "Bolt"), module
            ).BoundBox
            nut = _module_shape(
                doc.getObject("Instrument" + joint + "Nut"), module
            ).BoundBox
            engagement[joint] = {
                "tip_beyond_nut_mm": bolt.YMax - nut.YMax,
                "nut_height_mm": nut.YLength,
            }
        checks["nominal_full_nut_engagement"] = all(
            abs(r["tip_beyond_nut_mm"] - 0.9) < TOL
            and abs(r["nut_height_mm"] - 2.4) < TOL
            for r in engagement.values()
        )
        capture_rows = {}
        for joint, x in (("Pivot", 0), ("Lock", 9)):
            nut = hardware["Instrument" + joint + "Nut"]
            collisions = []
            for angle in (-30, 30):
                rotated = nut.copy()
                rotated.rotate(V(x, 0, 27.5), V(0, 1, 0), angle)
                collisions.append(intersection_volume(rotated, low))
            capture_rows[joint] = collisions
        checks["both_nuts_have_geometric_rotation_stops"] = all(
            min(values) > 0.1 for values in capture_rows.values()
        )
        floor_rows = {}
        for joint, x in (("Pivot", 0), ("Lock", 9)):
            floor = Part.makeCylinder(2.7, 1.5, V(x, 4.1, 27.5), V(0, 1, 0)).cut(
                Part.makeCylinder(1.7, 1.7, V(x, 4, 27.5), V(0, 1, 0))
            )
            floor_rows[joint] = abs(floor.cut(low).Volume)
        checks["both_nut_floors_retain_1p5mm_stock"] = all(
            v < TOL for v in floor_rows.values()
        )
        if not all(checks.values()):
            result.update(
                checks=checks,
                source_stock=shape_rows,
                hardware_stock=hardware_rows,
                centre_accessory=centre,
                arc_web={
                    "actual_slot_to_relief_mm": relief_gap,
                    "material_on_web_probe_mm": web_material,
                },
                engagement=engagement,
                nut_floor_missing_mm3=floor_rows,
            )
            return result
        # Partition actual solids, preserving all stock. Invariant Y separation
        # certifies the snug cheek clearance without unnecessarily tiny time steps.
        upper_regions = _split(
            high,
            [
                Part.makeBox(200, 200, 100, V(-100, -100, -83)),
                Part.makeBox(200, 200, 100, V(-100, -100, 17)),
            ],
        )
        # First box ends at Y=-4.1, rather than overlapping the central region.
        lower_regions = _split(
            low,
            [
                Part.makeBox(200, 95.9, 200, V(-100, -100, -50)),
                Part.makeBox(200, 8.2, 200, V(-100, -4.1, -50)),
                Part.makeBox(200, 100, 200, V(-100, 4.1, -50)),
            ],
        )
        drivers = {
            "Instrument" + joint + "Driver": _driver_shape(
                hardware["Instrument" + joint + "Bolt"]
            )
            for joint in ("Pivot", "Lock")
        }
        propulsion_orbits, orbit_rows = _propulsion_orbits(
            doc, module, include_installed
        )
        pitch_fixed = {**fixed, **drivers, **propulsion_orbits}
        disconnected_routes, terminal_rows = _terminal_connections(
            doc, module, moving, fixed, include_installed
        )
        # Each immutable copied solid is validated once, rather than once per
        # pair. This is a local read-only audit cache, never a global trust flag.
        for shape in [
            *moving.values(),
            *pitch_fixed.values(),
            *upper_regions,
            *lower_regions,
        ]:
            if shape.isNull() or not shape.isValid() or not shape.Solids:
                raise ValueError("Invalid installed pitch stock or terminal crop")
        pairs = []
        for name, moving_shape in moving.items():
            regions = upper_regions if name == "ElectronicsMount" else [moving_shape]
            for fixed_name, fixed_shape in pitch_fixed.items():
                if fixed_name in disconnected_routes:
                    continue
                obstacles = (
                    lower_regions
                    if fixed_name == "InstrumentMountBase"
                    else [fixed_shape]
                )
                for i, region in enumerate(regions):
                    for j, obstacle in enumerate(obstacles):
                        row = _certify_validated(region, obstacle)
                        pairs.append(
                            {
                                "moving": name,
                                "moving_region": i,
                                "fixed": fixed_name,
                                "fixed_region": j,
                                **row,
                            }
                        )
        checks["continuous_installed_pitch_clearance"] = all(r["passed"] for r in pairs)
        result.update(
            checks=checks,
            pitch_pairs=pairs,
            independent_propulsion_full_orbits=orbit_rows,
            intentional_terminal_connections=terminal_rows,
        )
        # Both ordinary nuts withdraw first, then both screws. Each operation
        # retains every remaining physical object. Zero pitch is a prerequisite.
        service_clearance_names = set()
        if include_installed:
            registry = doc.DesignRegistry
            physical_names = {
                o.Name
                for key in (
                    "PrintedParts",
                    "ReferenceParts",
                    "HardwareParts",
                    "TapeReferences",
                )
                for o in getattr(registry, key)
            }
            for obj in registry.ClearanceVolumes:
                if (
                    obj.Name not in physical_names
                    and getattr(obj, "Role", "") == "Clearance"
                ):
                    service_clearance_names.add(obj.Name)
        # Bench removal disconnects flexible leads first. Field-of-view and
        # cable planning volumes are not physical stock carried through a
        # removal path; every actual body remains, including unknown descendants.
        neutral_moving = {
            n: placed_shape(s, _pose(0))
            for n, s in moving.items()
            if n not in service_clearance_names
        }
        retained = {
            **{n: s for n, s in fixed.items() if n not in service_clearance_names},
            **neutral_moving,
        }
        paths = []
        for joint in ("Pivot", "Lock"):
            bolt_name = "Instrument" + joint + "Bolt"
            tool = drivers["Instrument" + joint + "Driver"]
            obstacles = {n: s for n, s in retained.items() if n != bolt_name}
            paths.append(
                {
                    "operation": "driver_" + joint,
                    **continuous_path(tool, [(0, -25, 0), (0, 0, 0)], obstacles),
                }
            )
        for suffix, travel in (("Nut", 8), ("Bolt", -20)):
            for joint in ("Pivot", "Lock"):
                name = "Instrument" + joint + suffix
                shape = retained.pop(name)
                paths.append(
                    {
                        "operation": "remove_" + name,
                        **continuous_path(shape, [(0, 0, 0), (0, travel, 0)], retained),
                    }
                )
        fixed_remaining = {n: s for n, s in retained.items() if n not in moving}
        for name, shape in neutral_moving.items():
            # Separate plate and lower lug envelopes avoid filling empty space
            # between the broad deck and narrow hinge. Entire saved stock was
            # independently proved contained in the source regions above.
            regions = (
                [placed_shape(s, _pose(0)) for s in upper_regions]
                if name == "ElectronicsMount"
                else [shape]
            )
            for i, region in enumerate(regions):
                paths.append(
                    {
                        "operation": "lift_" + name,
                        "region": i,
                        **continuous_path(
                            region, [(0, 0, 0), (0, 0, 40)], fixed_remaining
                        ),
                    }
                )
        checks["ordered_neutral_service"] = all(r["passed"] for r in paths)
        result.update(
            checks=checks,
            source_stock=shape_rows,
            hardware_stock=hardware_rows,
            nut_floor_missing_mm3=floor_rows,
            nut_rotation_blockage_mm3=capture_rows,
            centre_accessory=centre,
            arc_web={
                "actual_slot_to_relief_mm": relief_gap,
                "material_on_web_probe_mm": web_material,
            },
            engagement=engagement,
            moving_inventory=sorted(moving),
            fixed_inventory=sorted(fixed),
            pitch_pairs=pairs,
            intentional_terminal_connections=terminal_rows,
            disconnected_phase_routes_during_setup=sorted(disconnected_routes),
            independent_propulsion_full_orbits=orbit_rows,
            connected_lead_motion_verified=False,
            driver_access_at_every_setup_angle=all(
                r["passed"] for r in pairs if r["fixed"] in drivers
            ),
            service_paths=paths,
            service_prerequisites=[
                "Set the platform to neutral and support its weight",
                "Disconnect and move leads clear before releasing either joint",
                "Keep propulsion stopped in its saved neutral service pose",
            ],
            nonphysical_service_reserves=sorted(service_clearance_names),
            passed=all(checks.values()),
        )
    except (AttributeError, TypeError, ValueError, RuntimeError) as error:
        result["error"] = str(error)
    return result
