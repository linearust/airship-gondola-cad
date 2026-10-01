"""Manufacturer horn geometry, prepared holes and nominal coupling evidence.

A PASS establishes nominal geometry and limited registration, not delivered
concentricity, installed seating, printed fit, preload, strength or gear runout.
"""

import json

import FreeCAD as App
import Part

from gondola.cad import world_shape
from gondola.contracts import servo_horns
from gondola.contracts.drive import drive_for_document
from gondola.parts import servo_coupling as coupling

from .propulsion_service import (
    continuous_path,
    fastener_service_check,
    input_service_path,
    module_service_shapes,
    retained_obstacles,
    servo_bench_members,
)
from .servo_module import servo_module_service_check

TOL = 1e-5
V = App.Vector


def coupling_frame(doc, prefix):
    """Map horn-local geometry through the actual mirrored input-drive parents."""
    mirror = App.Rotation(V(0, 0, 1), 180 if prefix == "Starboard" else 0)
    return (
        doc.getObject(prefix + "InputDrive")
        .getGlobalPlacement()
        .multiply(App.Placement(V(), mirror))
        .multiply(App.Placement(V(0, coupling.HORN_BOTTOM_Y, 0), App.Rotation()))
    )


def _difference(first, second):
    return abs(first.cut(second).Volume) + abs(second.cut(first).Volume)


def _plane_contact(first, second, y):
    plane = Part.Face(
        Part.makePolygon(
            [
                V(x, y, z)
                for x, z in ((-20, -20), (25, -20), (25, 20), (-20, 20), (-20, -20))
            ]
        )
    )
    return first.common(plane).common(second.common(plane)).Area


def nut_recess_check(adapter, x, allowance):
    """Saved floor, radial float and minimum-nut turn barriers, independent of cutters."""
    rows = []
    radial_limit = 0.2 + allowance
    for offset in (-radial_limit, 0.0, radial_limit):
        for transverse in (-0.1, 0.0, 0.1):
            nut = coupling._hex_along_axis(
                2.9, 1.2, (x + offset, 6.5, transverse), (0, 1, 0)
            )
            overlap = abs(nut.common(adapter).Volume)
            turns = []
            for angle in (-30, 30):
                turned = nut.copy()
                turned.rotate(V(x + offset, 0, transverse), V(0, 1, 0), angle)
                turns.append(abs(turned.common(adapter).Volume))
            rows.append(
                {
                    "centre_offset_xz_mm": [offset, transverse],
                    "aligned_overlap_mm3": overlap,
                    "turn_30deg_obstruction_mm3": turns,
                    "passed": overlap < TOL and min(turns) > TOL,
                }
            )
    floors = []
    for z in (-1.2, 1.2):
        line = Part.makeLine(V(x, 3.5, z), V(x, 6.5, z))
        floors.append(adapter.common(line).Length)
    return {
        "minimum_nut_af_mm": 2.9,
        "centre_cases": rows,
        "retained_floor_lengths_mm": floors,
        "scope": "Nominal unchamfered minimum-nut screens, not torque or physical fit qualification. Shallow engagement must be checked against actual nut chamfers and printed flat spacing; no axial captivity.",
        "passed": all(row["passed"] for row in rows)
        and all(abs(length - 3.0) < TOL for length in floors),
    }


def horn_registration_check(doc, prefix):
    """Validate the selected bought profile against the one common printed part."""
    horn_obj = doc.getObject(prefix + "ServoHorn")
    if horn_obj is None or doc.getObject(prefix + "InputDrive") is None:
        return {
            "passed": False,
            "missing_objects": [prefix + "ServoHorn/InputDrive"],
            "physical_concentricity_verified": False,
        }
    try:
        profile = servo_horns.profile(str(horn_obj.HornProfile))
    except (AttributeError, KeyError):
        return {
            "passed": False,
            "error": "Missing or unsupported saved horn profile",
            "physical_concentricity_verified": False,
        }
    selection_matches = profile.key == servo_horns.profile(side=prefix).key
    try:
        saved_contract = json.loads(str(horn_obj.HornInterfaceContract))
        contract_matches = saved_contract == json.loads(
            json.dumps(coupling.assembly_contract(profile))
        )
    except (AttributeError, ValueError):
        contract_matches = False
    expected_hardware = {
        name: shape for name, shape, _ in coupling.horn_hardware_shapes(profile)
    }
    names = (
        "ServoHorn",
        "HornGearAdapter",
        *("HornGearClamp" + name for name in expected_hardware),
    )
    missing = [prefix + name for name in names if doc.getObject(prefix + name) is None]
    if missing:
        return {
            "passed": False,
            "missing_objects": missing,
            "physical_concentricity_verified": False,
        }
    obsolete = [
        name for name in ("HornCenteringJig",) if doc.getObject(name) is not None
    ]
    inverse = coupling_frame(doc, prefix).inverse()
    shapes = {}
    for suffix in names:
        shape = world_shape(doc.getObject(prefix + suffix))
        shape.Placement = inverse.multiply(shape.Placement)
        shapes[suffix] = shape
    horn, adapter = shapes["ServoHorn"], shapes["HornGearAdapter"]
    adapter_difference = _difference(adapter, coupling.adapter_shape())
    horn_difference = _difference(horn, coupling.horn_shape(profile))
    adapter_obj = doc.getObject(prefix + "HornGearAdapter")
    export_difference = 0.0
    if hasattr(adapter_obj, "PrintBlankShape"):
        exported = adapter_obj.PrintBlankShape.copy()
        exported.Placement = (
            inverse.multiply(adapter_obj.getGlobalPlacement())
            .multiply(adapter_obj.Placement.inverse())
            .multiply(exported.Placement)
        )
        export_difference = _difference(exported, adapter)
    rows = []
    for label, x, elongation in zip(
        ("Near", "Far"),
        profile.attachment_radii_mm,
        coupling.HORN_ADAPTER_OPENING_ALLOWANCES,
    ):
        bolt = shapes["HornGearClamp" + label + "Bolt"]
        difference = _difference(bolt, expected_hardware[label + "Bolt"])
        bearing = shapes["HornGearClamp" + label + "Nut"]
        difference += _difference(bearing, expected_hardware[label + "Nut"])
        diameter = coupling.HORN_CLAMP_THREAD_DIAMETER
        passage = Part.makeCylinder(
            diameter / 2,
            coupling.FASTENER_SEAT_Y - profile.blade_bottom_mm,
            V(x, profile.blade_bottom_mm, 0),
            V(0, 1, 0),
        )
        blocked = horn.common(passage).Volume + adapter.common(passage).Volume
        contact = _plane_contact(adapter, bearing, coupling.FASTENER_SEAT_Y)
        engagement = servo_horns.NUT_HEIGHT_MM
        rear_contact = _plane_contact(horn, bolt, profile.blade_bottom_mm)
        overlap = sum(
            first.common(second).Volume
            for first, second in (
                (bolt, adapter),
                (bolt, horn),
                (bearing, adapter),
                (bearing, horn),
                (bearing, bolt),
            )
        )
        support = []
        # Check front bearing at the actual shank-travel extremes, including
        # circular clearance; a round near hole has no added elongation.
        allowance = elongation + (coupling.SLOT_WIDTH - diameter) / 2
        for offset in (-allowance, 0.0, allowance):
            land = coupling._hex_along_axis(
                servo_horns.NUT_MIN_AF_MM,
                servo_horns.NUT_HEIGHT_MM,
                (x + offset, coupling.FASTENER_SEAT_Y, 0),
                (0, 1, 0),
            )
            area = _plane_contact(adapter, land, coupling.FASTENER_SEAT_Y)
            support.append(
                {
                    "radial_offset_mm": offset,
                    "flat_bearing_contact_mm2": area,
                    "passed": area >= 1.0,
                }
            )
        capture = nut_recess_check(adapter, x, elongation)
        rows.append(
            {
                "joint": label,
                "nut_recess_capture": capture,
                "nominal_fastener_difference_mm3": difference,
                "factory_thread_passage_blockage_mm3": blocked,
                "front_nut_to_adapter_contact_mm2": contact,
                "rear_head_to_horn_contact_mm2": rear_contact,
                "nominal_thread_engagement_mm": engagement,
                "nominal_overlap_mm3": overlap,
                "separate_nut_required": True,
                "minimum_head_support": support,
                "passed": difference < TOL
                and blocked < TOL
                and contact > 1
                and rear_contact > 1
                and overlap < TOL
                and engagement >= 1
                and all(r["passed"] for r in support)
                and capture["passed"],
            }
        )
    collar = adapter.common(
        Part.makeBox(
            20,
            profile.height_mm - coupling.BODY_BACK_Y,
            20,
            V(-10, coupling.BODY_BACK_Y, -10),
        )
    )
    register_rows = []
    for direction in ((-1, 0), (0, -1), (0, 1)):
        moved = horn.copy()
        moved.translate(V(direction[0] * 0.4, 0, direction[1] * 0.4))
        penetration = moved.common(collar).Volume
        register_rows.append(
            {
                "horn_offset_xz_mm": [v * 0.4 for v in direction],
                "register_probe_penetration_mm3": penetration,
                "passed": penetration > TOL,
            }
        )
    seating = _plane_contact(horn, adapter, profile.height_mm)
    measured = bool(getattr(horn_obj, "PurchasedHornMeasured", True))
    axial_unknown = not bool(getattr(horn_obj, "AxialSeatingMeasured", True))
    compatibility = bool(getattr(horn_obj, "X06CompatibilityAccepted", False))
    from gondola.parts.oem_servo_horn import STEP_SHA256

    manufacturer_matches = (
        bool(getattr(horn_obj, "ManufacturerGeometryProvided", False))
        and str(getattr(horn_obj, "ManufacturerGeometrySHA256", "")) == STEP_SHA256
    )
    threads = bool(getattr(horn_obj, "FactoryM1_6ThreadsConfirmed", False))
    preparation = bool(getattr(horn_obj, "HornPreparationRequired", False))
    return {
        "pod": prefix,
        "profile": profile.key,
        "source_selection_matches": selection_matches,
        "saved_contract_matches": contract_matches,
        "adapter_difference_mm3": adapter_difference,
        "selected_horn_difference_mm3": horn_difference,
        "print_export_difference_mm3": export_difference,
        "obsolete_horn_parts": obsolete,
        "joints": rows,
        "register_directional_stops": register_rows,
        "horn_to_adapter_seating_area_mm2": seating,
        "purchased_horn_measurement_explicitly_unknown": not measured,
        "physical_concentricity_verified": False,
        "axial_seating_explicitly_unmeasured": axial_unknown,
        "x06_compatibility_accepted": compatibility,
        "manufacturer_geometry_matches": manufacturer_matches,
        "factory_m1_6_threads_confirmed": threads,
        "preparation_required": preparation,
        "scope": "Saved manufacturer half-arm geometry, prepared Ø1.5 holes and rear M1.4x8/front-nut hardware. The near round hole bounds translation; the far short slot accommodates pitch variation before clamping, not running flexibility. Nominal source shape does not qualify received seating, runout, strength or retention.",
        "passed": selection_matches
        and contract_matches
        and adapter_difference < TOL
        and horn_difference < TOL
        and export_difference < TOL
        and not obsolete
        and not measured
        and axial_unknown
        and compatibility
        and manufacturer_matches
        and not threads
        and preparation
        and seating > 1
        and all(r["passed"] for r in rows + register_rows),
    }


def assembled_servo_service_check(doc, module, prefix, *, module_release=None):
    """KST sequence keeps its reverse screws in the horn during bridge removal."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"passed": False, "missing_parts": missing, "pod": prefix}
    sign = 1 if prefix == "Port" else -1
    if module_release is None:
        module_release = servo_module_service_check(doc, module)
    bench = servo_bench_members(doc, shapes)
    shapes = {n: shapes[n] for n in bench}
    driver = prefix + "DriverGear"
    driver_path = continuous_path(
        shapes[driver],
        [(0, 0, 0), (0, sign * 35, 0)],
        retained_obstacles(shapes, {driver}),
    )
    shaft = prefix + "InputShaft"
    shaft_path = continuous_path(
        shapes[shaft],
        [(0, 0, 0), (0, sign * 20, 0)],
        retained_obstacles(shapes, {driver, shaft}),
    )
    removed = {driver, shaft}
    ear_rows = []
    for side in ("Lower", "Upper"):
        name = prefix + "ServoEar" + side
        pair = {name + "Bolt", name + "Nut"}
        ear_rows.append(
            {
                "bolt": name + "Bolt",
                **fastener_service_check(
                    shapes[name + "Bolt"],
                    shapes[name + "Nut"],
                    retained_obstacles(shapes, removed | pair),
                    thread_diameter=1.6,
                    guided_nut=True,
                    capture_depth_mm=0.5,
                ),
            }
        )
        removed.update(pair)
    moving = {
        prefix + s
        for s in (
            "Servo",
            "ServoHorn",
            "HornGearAdapter",
            "HornGearClampNearBolt",
            "HornGearClampFarBolt",
            "HornGearClampNearNut",
            "HornGearClampFarNut",
            "InputShaftClampBolt",
            "InputShaftClampNut",
        )
    }
    fixed = retained_obstacles(shapes, removed | moving)
    points = [(0, 0, 0), (0, sign * 12.5, 0), (sign * 40, sign * 12.5, 0)]
    spec = drive_for_document(doc)
    paths = []
    for n in sorted(moving):
        if n.endswith("HornGearAdapter"):
            b = shapes[n].BoundBox
            envelope = Part.makeBox(
                b.XLength, b.YLength, b.ZLength, V(b.XMin, b.YMin, b.ZMin)
            )
            path = continuous_path(envelope, points, fixed)
            path["scope"] = (
                "Conservative full adapter box; horn and servo move with it."
            )
        else:
            path = input_service_path(n, shapes[n], points, fixed, spec, sign)
        paths.append({"part": n, "waypoints_mm": points, **path})
    # Once the servo is free of the bridge, the small rear holding stem clears
    # the case. A standard large screwdriver is not assumed to fit this gap.
    inverse = coupling_frame(doc, prefix).inverse()
    profile = servo_horns.profile(str(doc.getObject(prefix + "ServoHorn").HornProfile))
    local_names = {
        "horn": "ServoHorn",
        "adapter": "HornGearAdapter",
        "servo": "Servo",
        "shaft_bolt": "InputShaftClampBolt",
        "shaft_nut": "InputShaftClampNut",
        **{
            name: "HornGearClamp" + name
            for name, _, _ in coupling.horn_hardware_shapes(profile)
        },
    }
    local = {}
    for key, suffix in local_names.items():
        shape = world_shape(doc.getObject(prefix + suffix))
        shape.Placement = inverse.multiply(shape.Placement)
        local[key] = shape
    holding = []
    for x in profile.attachment_radii_mm:
        stem = Part.makeCylinder(
            servo_horns.KST_TOOL_STEM_DIAMETER_MM / 2,
            30,
            V(x, profile.blade_bottom_mm - servo_horns.KST_SCREW_HEAD_HEIGHT_MM, 0),
            V(0, -1, 0),
        )
        hits = {
            prefix + local_names[key]: stem.common(local[key]).Volume
            for key in ("servo",)
        }
        holding.append(
            {
                "radius_mm": x,
                "retained_part_overlaps_mm3": hits,
                "passed": all(volume < TOL for volume in hits.values()),
            }
        )
    fasteners = []
    removed_nuts = []
    nut_release_y = (
        profile.blade_bottom_mm
        + profile.screw_length_mm
        - coupling.FASTENER_SEAT_Y
        + 0.2
    )
    # Remove outer front nut first, then inner. Rear screws remain in the horn
    # until the adapter has cleared their forward tips.
    for label in ("Far", "Near"):
        n = label + "Nut"
        nut = local[n]
        obstacles = {k: s for k, s in local.items() if k != n}
        first = continuous_path(nut, [(0, 0, 0), (0, nut_release_y, 0)], obstacles)
        x = profile.attachment_radii_mm[0 if label == "Near" else 1]
        outer = coupling._hex_along_axis(
            servo_horns.NUT_AF_MM,
            servo_horns.NUT_HEIGHT_MM,
            (x, coupling.FASTENER_SEAT_Y, 0),
            (0, 1, 0),
        )
        second = continuous_path(
            outer, [(0, nut_release_y, 0), (20, nut_release_y, 0)], obstacles
        )
        route = {
            "segments": first["segments"] + second["segments"],
            "passed": first["passed"] and second["passed"],
            "scope": "Turn the accessible rear screw while the shallow pocket restrains its nut; lift the nut axially clear of its recess and screw tip, then use the filled outer-hex lateral release envelope.",
        }
        x = profile.attachment_radii_mm[0 if label == "Near" else 1]
        # The rear screw first lifts the restrained nut out of its recess;
        # full-height fine-plier access is needed only after that release.
        plier_lift = coupling.HORN_NUT_RECESS_DEPTH + 0.2
        jaws = Part.makeCompound(
            [
                Part.makeBox(
                    6,
                    0.7,
                    1,
                    V(x - 0.5, coupling.FASTENER_SEAT_Y + plier_lift + 0.3, z),
                )
                for z in (-2.5, 1.5)
            ]
        )
        collisions = {
            k: jaws.common(s).Volume
            for k, s in obstacles.items()
            if jaws.common(s).Volume > TOL
        }
        fasteners.append(
            {
                "joint": label,
                "bolt": prefix + "HornGearClamp" + label + "Bolt",
                "nut": prefix + "HornGearClamp" + label + "Nut",
                "retained_parts": [prefix + local_names[k] for k in obstacles],
                "removed_prior_parts": sorted(removed) + removed_nuts.copy(),
                "removed_part": prefix + "HornGearClamp" + n,
                "front_nut_release": route,
                "fine_plier_access_after_nut_lift_mm": plier_lift,
                "fine_plier_jaw_collisions_mm3": collisions,
                "passed": route["passed"] and not collisions,
            }
        )
        local.pop(n)
        removed_nuts.append(prefix + "HornGearClamp" + n)
    adapter_moving = {"adapter", "shaft_bolt", "shaft_nut"}
    adapter_obstacles = {
        prefix + local_names[k]: shape
        for k, shape in local.items()
        if k not in adapter_moving
    }
    adapter_points = [
        (0, 0, 0),
        (0, coupling.RETAINED_BOLT_RELEASE_TRAVEL, 0),
        (40, coupling.RETAINED_BOLT_RELEASE_TRAVEL, 0),
    ]
    adapter_route = continuous_path(
        coupling.service_envelope(retain_screws=True), adapter_points, adapter_obstacles
    )
    clamp_paths = [
        {
            "part": prefix + local_names[key],
            **continuous_path(local[key], adapter_points, adapter_obstacles),
        }
        for key in ("shaft_bolt", "shaft_nut")
    ]
    adapter_route["retained_clamp_hardware_paths"] = clamp_paths
    adapter_route["passed"] = adapter_route["passed"] and all(
        row["passed"] for row in clamp_paths
    )
    passed = (
        module_release["passed"]
        and driver_path["passed"]
        and shaft_path["passed"]
        and adapter_route["passed"]
        and all(r["passed"] for r in ear_rows + paths + holding + fasteners)
    )
    return {
        "pod": prefix,
        "service_mode": "preassembled_servo_unit",
        "module_removal_passed": module_release["passed"],
        "required_prior_check": "servo_module_service",
        "driver_gear_removal": driver_path,
        "input_stub_removal": shaft_path,
        "ear_fastener_release": ear_rows,
        "part_paths": paths,
        "moving_parts": sorted(moving),
        "retained_parts": sorted(fixed),
        "bench_members": sorted(bench),
        "rear_holding_tool_off_bridge": holding,
        "adapter_clamp_release": {
            "fasteners": fasteners,
            "passed": all(r["passed"] for r in fasteners),
        },
        "adapter_release_off_bridge": adapter_route,
        "scope": "KST only: remove paired module and selected driver/stub, then withdraw each M1.6 ear screw and lift its nut out of the shallow cradle pocket. Withdraw the complete servo/horn/adapter unit with the ear hardware removed. Off the bridge, turn the rear horn screws to release the pocket-held front nuts. Retain the horn screws in the supplied arm until the adapter clears their tips. A narrow <=1.5mm rear stem and fine pliers are explicit envelopes; actual tools/recess fit remain checks. Reverse for assembly, fitting OEM spline screw before adapter. Full shaft-stop floor retained.",
        "passed": passed,
    }


def profile_compatibility_checks():
    """Exercise every profile on both mirrored sides without changing saved CAD."""
    from gondola.parts import propulsion, servo_envelope

    rows = []
    original = dict(servo_horns.SELECTED_BY_SIDE)
    active = App.ActiveDocument.Name if App.ActiveDocument else None
    try:
        for key, profile in servo_horns.PROFILES.items():
            servo_horns.SELECTED_BY_SIDE.update(Port=key, Starboard=key)
            doc = App.newDocument("HornProfileAudit" + key)
            try:
                module = propulsion.build_propulsion_module(doc)
                doc.recompute()
                registration = [
                    horn_registration_check(doc, p) for p in ("Port", "Starboard")
                ]
                case = servo_envelope.shape()
                case.translate(V(0, -coupling.HORN_BOTTOM_Y, 0))
                from .servo_interface import horn_spline_contact, sourced_spline_volume

                spline, spline_evidence = sourced_spline_volume(
                    case, (0, 0, 0), (0, 1, 0)
                )
                if spline is None:
                    raise ValueError(spline_evidence)
                case_and_ears = case.cut(spline)
                moving = {
                    "adapter": coupling.adapter_shape(),
                    "horn": coupling.horn_shape(profile),
                    **{n: s for n, s, _ in coupling.horn_hardware_shapes(profile)},
                }
                overlaps = []
                for angle in range(-60, 61, 5):
                    for name, shape in moving.items():
                        turned = shape.copy()
                        turned.rotate(V(), V(0, 1, 0), angle)
                        contact = (
                            horn_spline_contact(turned, case, (0, 0, 0), (0, 1, 0))
                            if name == "horn"
                            else None
                        )
                        volume = turned.common(
                            case_and_ears if name == "horn" else case
                        ).Volume
                        if volume > TOL or (
                            contact is not None and not contact["passed"]
                        ):
                            overlaps.append(
                                {"angle_deg": angle, "part": name, "volume_mm3": volume}
                            )
                module_release = servo_module_service_check(doc, module)
                service = [
                    assembled_servo_service_check(
                        doc, module, p, module_release=module_release
                    )
                    for p in ("Port", "Starboard")
                ]
                adapter = coupling.adapter_shape()
                web_rows = []
                for name, start, end, minimum in (
                    (
                        "slot_end_web",
                        (14.5, 5.0, 0),
                        (coupling.PLATE_X_MAX, 5.0, 0),
                        1.5,
                    ),
                    ("near_nut_socket_wall", (1.55, 8.0, 0), (2.65, 8.0, 0), 1.1),
                    (
                        "root_register_wall",
                        (-coupling.REGISTER_OUTER_RADIUS, 2.5, 0),
                        (-coupling.REGISTER_INNER_RADIUS, 2.5, 0),
                        coupling.REGISTER_OUTER_RADIUS - coupling.REGISTER_INNER_RADIUS,
                    ),
                ):
                    thickness = adapter.common(Part.makeLine(V(*start), V(*end))).Length
                    web_rows.append(
                        {
                            "feature": name,
                            "thickness_mm": thickness,
                            "minimum_mm": minimum,
                            "passed": thickness >= minimum - TOL,
                        }
                    )
                rows.append(
                    {
                        "profile": key,
                        "functional_webs": web_rows,
                        "registration": registration,
                        "servo_sweep_angles_deg": list(range(-60, 61, 5)),
                        "servo_sweep_overlaps": overlaps,
                        "conditional_service": service,
                        "scope": "Nominal profile envelopes and sampled input rotation; no elastic/runout/strength or received-part certification.",
                        "passed": not overlaps
                        and all(r["passed"] for r in registration + service + web_rows),
                    }
                )
            finally:
                App.closeDocument(doc.Name)
    finally:
        servo_horns.SELECTED_BY_SIDE.clear()
        servo_horns.SELECTED_BY_SIDE.update(original)
        if active:
            App.setActiveDocument(active)
    return rows
