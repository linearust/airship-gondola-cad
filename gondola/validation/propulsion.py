"""Recompute local propulsion fit and removal evidence from current geometry.

These rigid envelopes keep the OEM motor fasteners, servo saddle retention,
and horn-to-sleeve torque connection unresolved. They prove no loaded operation.
"""

import json
import math
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

from gondola.cad import (
    translated_shape,
    world_shape,
)
from gondola.config import OUTPUT_DIR, STEM
from gondola.manufacturing import geometry_comparison, mesh_checks, print_shape
from gondola.parts import fastener_spec as fastener
from gondola.parts import propulsion, rail

from .evidence import overlap_failures
from .geometry import intersection_volume, local_shape, translation_sweep

TOL = 1e-5


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


def _axial_contact_area(first, second):
    """Area of actual coincident Y-normal faces in the simplified CAD stack."""
    area = 0.0
    for a in first.Faces:
        if a.BoundBox.YLength > 1e-7:
            continue
        for b in second.Faces:
            if (
                b.BoundBox.YLength < 1e-7
                and abs(a.CenterOfMass.y - b.CenterOfMass.y) < 1e-7
            ):
                area += a.common(b).Area
    return area


def _journal_rotation_envelope(shape):
    """Continuous full-turn envelope, with original-solid coverage verified.

    Axial vertex levels split the flange, neck, square nut and head. Each slab is
    bounded by a coaxial cylinder. Coverage is checked against the actual BRep,
    so an unrepresented curved extremum fails instead of understating the sweep.
    """
    bounds = shape.BoundBox
    levels = sorted(
        {bounds.YMin, bounds.YMax} | {round(v.Point.y, 9) for v in shape.Vertexes}
    )
    pieces = []
    for low, high in zip(levels, levels[1:]):
        if high - low < 1e-8:
            continue
        slab = Part.makeBox(
            bounds.XLength + 2,
            high - low,
            bounds.ZLength + 2,
            App.Vector(bounds.XMin - 1, low, bounds.ZMin - 1),
        )
        section = shape.common(slab)
        if abs(section.Volume) < 1e-10:
            continue
        radius = (
            max(
                math.hypot(v.Point.x, v.Point.z - propulsion.PIVOT_Z)
                for v in section.Vertexes
            )
            + 1e-7
        )
        pieces.append(
            Part.makeCylinder(
                radius,
                high - low,
                App.Vector(0, low, propulsion.PIVOT_Z),
                App.Vector(0, 1, 0),
            )
        )
    if not pieces:
        raise ValueError("No journal rotation envelope sections")
    envelope = (
        pieces[0].multiFuse(pieces[1:]).removeSplitter()
        if len(pieces) > 1
        else pieces[0]
    )
    if not envelope.isValid() or abs(shape.cut(envelope).Volume) > TOL:
        raise ValueError("Journal full-turn envelope does not contain the actual solid")
    return envelope


def journal_stack_check(sleeve, hardware, frame, carrier, side):
    """Nominal contact, full nut engagement, axial capture and free rotation."""
    parts = {"Sleeve": sleeve, **hardware}
    assembled = Part.makeCompound(list(parts.values()))
    outward = translated_shape(assembled, y=side)
    inward = translated_shape(assembled, y=-side)
    outward_block = intersection_volume(outward, carrier)
    inward_block = intersection_volume(inward, frame)
    contacts = []
    contact_parts = {**parts, "CarrierCap": carrier}
    chain = ["Bolt", "Sleeve", "CarrierCap", "Nut"]
    for first, second in zip(chain, chain[1:]):
        area = _axial_contact_area(contact_parts[first], contact_parts[second])
        contacts.append(
            {
                "parts": [first, second],
                "bearing_contact_area_mm2": area,
                "passed": area > TOL,
            }
        )
    nut = hardware["Nut"].BoundBox
    bolt = hardware["Bolt"].BoundBox
    nut_low = nut.YMin if side > 0 else -nut.YMax
    bolt_low = bolt.YMin if side > 0 else -bolt.YMax
    core = Part.makeCylinder(
        fastener.THREAD_DIAMETER * 0.4,
        nut.YLength,
        App.Vector(0, nut.YMin, propulsion.PIVOT_Z),
        App.Vector(0, 1, 0),
    )
    missing_core = abs(core.cut(hardware["Bolt"]).Volume)
    clearance_rows = []
    rotation_rows = []
    for name, shape in parts.items():
        frame_hit = intersection_volume(shape, frame)
        carrier_hit = intersection_volume(shape, carrier)
        clearance_rows.append(
            {
                "part": name,
                "frame_intersection_mm3": frame_hit,
                "carrier_intersection_mm3": carrier_hit,
                "passed": frame_hit < TOL and carrier_hit < TOL,
            }
        )
        envelope = _journal_rotation_envelope(shape)
        hit = intersection_volume(envelope, frame)
        rotation_rows.append(
            {"part": name, "full_turn_frame_intersection_mm3": hit, "passed": hit < TOL}
        )
    report = {
        "outward_1mm_blocking_intersection_mm3": outward_block,
        "inward_1mm_blocking_intersection_mm3": inward_block,
        "axial_capture": outward_block > TOL and inward_block > TOL,
        "contacts": contacts,
        "nominal_clearances": clearance_rows,
        "continuous_rotation": rotation_rows,
        "nut_engagement_length_mm": nut.YLength,
        "missing_bolt_thread_core_mm3": missing_core,
        "bolt_tip_beyond_nut_mm": nut_low - bolt_low,
        "scope": "Simplified nominal BRep contact/capture and a continuous full-turn clearance envelope; direct-bearing bolt/sleeve/carrier-cap/square-nut stack. No thread strength, PA12 bearing pressure, creep, tightening torque, wear or loaded retention qualification.",
    }
    report["passed"] = (
        report["axial_capture"]
        and all(r["passed"] for r in contacts + clearance_rows + rotation_rows)
        and missing_core < TOL
        and nut_low - bolt_low >= fastener.THREAD_PITCH - TOL
    )
    return report


def validate(source=None):
    """Build a fresh local module, check its fits, and write reproducible evidence."""
    source = Path(source).resolve() if source else OUTPUT_DIR / (STEM + ".FCStd")
    doc = App.newDocument("PropulsionSourceAudit")
    try:
        module = propulsion.build_propulsion_module(doc)
        frame = module["frame"].Shape
        physical = {
            obj.Name: world_shape(obj)
            for obj in module["printed"] + module["hardware"] + module["references"]
        }
        servo_names = {"PortServo", "StarboardServo"}
        report = {
            "scope": "Current source local fit and service envelopes; not a measured OEM or structural qualification.",
            "rail_contact_overlap_mm3": intersection_volume(
                translated_shape(frame, y=rail.CLAMP_SHIFT_Y), rail.rail_shape()
            ),
            "negative_seated_rail_contact_overlap_mm3": intersection_volume(
                translated_shape(frame, y=-rail.CLAMP_SHIFT_Y), rail.rail_shape()
            ),
            "clamp_screw_frame_overlap_mm3": intersection_volume(
                frame, rail.set_screw_shape()
            ),
            "clamp_nut_frame_overlap_mm3": intersection_volume(frame, rail.nut_shape()),
            "negative_clamp_nut_frame_overlap_mm3": intersection_volume(
                frame, rail.half_turn(rail.nut_shape())
            ),
            "negative_clamp_screw_frame_overlap_mm3": intersection_volume(
                frame, rail.half_turn(rail.set_screw_shape())
            ),
        }
        # Both side approaches must clear the fixed frame below the equipment.
        key = Part.makeCylinder(
            0.9,
            110,
            App.Vector(0, rail.SHOE_WIDTH / 2 + 0.7, rail.CLAMP_Z),
            App.Vector(0, 1, 0),
        )
        report["clamp_driver_frame_overlap_mm3"] = intersection_volume(frame, key)
        report["negative_clamp_driver_frame_overlap_mm3"] = intersection_volume(
            frame, rail.half_turn(key)
        )
        report["continuous_nut_loading"] = [
            continuous_path(rail.nut_shape(), [(0, 0, 0), (20, 0, 0)], physical),
            continuous_path(
                rail.half_turn(rail.nut_shape()),
                [(0, 0, 0), (-20, 0, 0)],
                physical,
            ),
        ]
        report["sleeve_service_servo_removed"] = []
        report["motor_and_prop_insertion"] = []
        report["assembled_journal_stacks"] = []
        report["journal_hardware_removal"] = []
        for prefix in ("Port", "Starboard"):
            carrier = world_shape(doc.getObject(prefix + "MotorCarrier"))
            for suffix, sign in (("Negative", -1), ("Positive", 1)):
                sleeve = world_shape(doc.getObject(prefix + "JournalSleeve" + suffix))
                driven = (prefix == "Port" and sign == -1) or (
                    prefix == "Starboard" and sign == 1
                )
                journal_name = prefix + "Journal" + suffix
                hardware_names = {journal_name + kind for kind in ("Bolt", "Nut")}
                sleeve_name = prefix + "JournalSleeve" + suffix
                sleeve_removed = {sleeve_name} | hardware_names
                if driven:
                    sleeve_removed.add(prefix + "Servo")
                report["sleeve_service_servo_removed"].append(
                    {
                        "sleeve": prefix + suffix,
                        "servo_must_be_removed": driven,
                        "journal_fasteners_must_be_removed": True,
                        "excluded_physical_parts": sorted(sleeve_removed),
                        "scope": "Local neutral-angle module after removal of the listed parts and any unmodeled horn coupling; every other modeled physical part remains an obstacle.",
                        "continuous_path": continuous_path(
                            sleeve,
                            [
                                (0, 0, 0),
                                (0, sign * 8, 0),
                                (0, sign * 8, propulsion.SLEEVE_SERVICE_LIFT),
                                (0, sign * 30, propulsion.SLEEVE_SERVICE_LIFT),
                            ]
                            if driven
                            else [(0, 0, 0), (0, sign * 30, 0)],
                            {
                                name: shape
                                for name, shape in physical.items()
                                if name not in sleeve_removed
                            },
                        ),
                    }
                )
                hardware = {
                    kind: world_shape(doc.getObject(prefix + "Journal" + suffix + kind))
                    for kind in ("Bolt", "Nut")
                }
                report["assembled_journal_stacks"].append(
                    {
                        "journal": prefix + suffix,
                        **journal_stack_check(sleeve, hardware, frame, carrier, sign),
                    }
                )
                # Remove the square nut first, then the bare bolt. The nut
                # is rotated off the real thread; CAD only
                # screens its axial envelope. Servo/horn removal is prerequisite.
                remaining = {
                    name: shape
                    for name, shape in physical.items()
                    if name not in servo_names
                }
                removed = set(servo_names)
                operations = [
                    (
                        "Nut",
                        ["Nut"],
                        [
                            (0, 0, 0),
                            (0, -sign * 4, 0),
                            (0, -sign * 4, 12),
                            (0, -sign * 20, 12),
                        ],
                    ),
                    (
                        "Bolt",
                        ["Bolt"],
                        [(0, 0, 0), (0, sign * 20, 0)],
                    ),
                ]
                for label, names, path in operations:
                    moving_names = [journal_name + name for name in names]
                    moving = Part.makeCompound(
                        [remaining.pop(name) for name in moving_names]
                    )
                    removed.update(moving_names)
                    report["journal_hardware_removal"].append(
                        {
                            "journal": prefix + suffix,
                            "operation": label,
                            "excluded_physical_parts": sorted(removed),
                            "scope": "Sequential neutral-angle removal after both servos/horns are released; every other modeled physical part remains an obstacle. Nominal rigid envelopes, not a thread/driver torque simulation.",
                            **continuous_path(moving, path, remaining),
                        }
                    )
            for name in ("Motor", "PropellerDisk"):
                shape = world_shape(doc.getObject(prefix + name))
                excluded = {prefix + name, prefix + "Shaft"}
                moving = shape
                if name == "Motor":
                    moving = Part.makeCompound([shape, physical[prefix + "Shaft"]])
                    excluded.add(prefix + "PropellerDisk")
                    scope = "Motor and shaft translate together with its propeller removed first; all other modeled physical parts remain installed at neutral tilt. OEM mounting fasteners are unresolved."
                else:
                    scope = "Propeller disk proxy translates alone with all other modeled physical parts installed at neutral tilt except its shaft. The full-disk proxy fills the unmodeled hub bore, so shaft engagement and bore fit remain unverified."
                report["motor_and_prop_insertion"].append(
                    {
                        "part": prefix + name,
                        "excluded_physical_parts": sorted(excluded),
                        "scope": scope,
                        "continuous_path": continuous_path(
                            moving,
                            [(0, 0, 0), (30, 0, 0)],
                            {
                                key: value
                                for key, value in physical.items()
                                if key not in excluded
                            },
                        ),
                    }
                )
        report["printed_parts"] = len(module["printed"])
        report["purchased_hardware"] = len(module["hardware"])
        # Verify the complete integral cap annulus in each actual carrier,
        # including the small through hole. The whole carrier must remain one
        # solid; a detached printed washer must never satisfy this check.
        cap_rows = []
        for prefix in ("Port", "Starboard"):
            shape = local_shape(doc.getObject(prefix + "MotorCarrier"))
            for side in (-1, 1):
                low = side * propulsion.CARRIER_CAP_INNER_Y
                cap = Part.makeCylinder(
                    6,
                    propulsion.CARRIER_CAP_THICKNESS,
                    App.Vector(0, low, 0),
                    App.Vector(0, side, 0),
                ).cut(
                    Part.makeCylinder(
                        propulsion.SLEEVE_BORE_RADIUS,
                        propulsion.CARRIER_CAP_THICKNESS,
                        App.Vector(0, low, 0),
                        App.Vector(0, side, 0),
                    )
                )
                missing = abs(cap.cut(shape).Volume)
                bore = Part.makeCylinder(
                    propulsion.SLEEVE_BORE_RADIUS - 1e-4,
                    propulsion.CARRIER_CAP_THICKNESS,
                    App.Vector(0, low, 0),
                    App.Vector(0, side, 0),
                )
                hole_hit = intersection_volume(bore, shape)
                cap_rows.append(
                    {
                        "carrier": prefix,
                        "side": side,
                        "missing_integral_cap_mm3": missing,
                        "through_hole_intersection_mm3": hole_hit,
                        "one_connected_carrier_solid": shape.isValid()
                        and len(shape.Solids) == 1,
                        "passed": missing < TOL
                        and hole_hit < TOL
                        and shape.isValid()
                        and len(shape.Solids) == 1,
                    }
                )
        report["integral_retention_caps"] = cap_rows
        report["minimum_sleeve_flat_wall_mm"] = (
            propulsion.SLEEVE_D_FLAT - propulsion.SLEEVE_BORE_RADIUS
        )
        # Measure changed walls on actual solids, independently of declarations.
        wall_probes = [
            (
                "sleeve_D_flat",
                "PortJournalSleevePositive",
                (0, 24, 1.19),
                (0, 24, 3.01),
            ),
            ("guard_radial", "PortMotorCarrier", (12, 0, 22.79), (12, 0, 24.31)),
        ]
        for side in (-1, 1):
            wall_probes.extend(
                [
                    (
                        f"foot_deck_{side}",
                        "PropulsionFixedFrame",
                        (4.5, side * 80, propulsion.BASE_Z - 0.01),
                        (
                            4.5,
                            side * 80,
                            propulsion.BASE_Z + propulsion.FOOT_THICKNESS + 0.01,
                        ),
                    ),
                ]
            )
            for index, x in enumerate(propulsion.SERVO_MOUNT_X):
                y = side * (
                    propulsion.PIVOT_HALF_SPAN
                    + propulsion.SERVO_MOUNT_PLANE_Y
                    - propulsion.SERVO_MOUNT_TAB_THICKNESS / 2
                )
                wall_probes.append(
                    (
                        f"servo_saddle_upper_land_{side}_{index}",
                        "PropulsionFixedFrame",
                        (x, y, propulsion.PIVOT_Z + 0.99),
                        (x, y, propulsion.PIVOT_Z + 3.51),
                    )
                )
            # Cross the steeper A-frame web approximately normal to its slope;
            # this measures its actual perpendicular width on each mirrored pod.
            for x in (-8, 15.5):
                wall_probes.append(
                    (
                        f"inclined_servo_support_{side}_{x}",
                        "PropulsionFixedFrame",
                        (x, side * 37.3, 24.0796296296),
                        (x, side * 40.5, 24.8203703704),
                    )
                )
        for side in (-1, 1):
            wall_probes.append(
                (
                    f"integral_carrier_cap_{side}",
                    "PortMotorCarrier",
                    (2, side * (propulsion.CARRIER_CAP_INNER_Y - 0.01), 0),
                    (2, side * (propulsion.SLEEVE_INNER_Y + 0.01), 0),
                )
            )
        wall_rows = []
        for label, name, start, end in wall_probes:
            section = local_shape(doc.getObject(name)).common(
                Part.makeLine(App.Vector(*start), App.Vector(*end))
            )
            thickness = sum(edge.Length for edge in section.Edges)
            wall_rows.append(
                {
                    "feature": label,
                    "measured_wall_mm": thickness,
                    "passed": thickness >= 1.5 - TOL,
                }
            )
        report["functional_wall_probes"] = wall_rows
        report["servo_mount_axes"] = []
        for side in (-1, 1):
            for x in propulsion.SERVO_MOUNT_X:
                start = side * (
                    propulsion.PIVOT_HALF_SPAN
                    + propulsion.SERVO_MOUNT_PLANE_Y
                    - propulsion.SERVO_MOUNT_TAB_THICKNESS
                    - 0.1
                )
                axis = Part.makeCylinder(
                    0.99,
                    propulsion.SERVO_MOUNT_TAB_THICKNESS + 0.2,
                    App.Vector(x, start, propulsion.PIVOT_Z),
                    App.Vector(0, side, 0),
                )
                report["servo_mount_axes"].append(
                    {
                        "side": side,
                        "x_mm": x,
                        "through_axis_overlap_mm3": intersection_volume(frame, axis),
                        "interface": "Open2mm saddle; ear thickness and final retention unverified",
                    }
                )
        report["servo_case_frame_clearance"] = [
            {
                "part": prefix + "Servo",
                "overlap_frame_mm3": intersection_volume(
                    world_shape(doc.getObject(prefix + "Servo")), frame
                ),
            }
            for prefix in ("Port", "Starboard")
        ]
        report["geometry"] = []
        for obj in module["printed"]:
            shape = print_shape(obj)
            mesh = MeshPart.meshFromShape(
                Shape=shape,
                LinearDeflection=0.03,
                AngularDeflection=0.08,
                Relative=False,
            )
            report["geometry"].append({"name": obj.Name, **mesh_checks(shape, mesh)})
        report["all_hardware_A2"] = all(
            obj.MaterialSelection == "A2 stainless steel" for obj in module["hardware"]
        )
        report["support_plane_z_mm"] = module["group"].SupportPlaneZ.Value
        sleeves = [
            print_shape(obj) for obj in module["printed"] if "JournalSleeve" in obj.Name
        ]
        report["identical_sleeve_SKU_difference_mm3"] = [
            geometry_comparison(sleeves[0], shape)["difference_mm3"]
            for shape in sleeves
        ]
        report["metrics"] = module["metrics"]
        failures = overlap_failures(report, TOL)
        report["overlap_failures"] = failures
        report["passed"] = (
            not failures
            and len(report["sleeve_service_servo_removed"]) == 4
            and len(report["motor_and_prop_insertion"]) == 4
            and len(report["geometry"]) == 7
            and len(report["servo_mount_axes"]) == 4
            and report["purchased_hardware"] == 8
            and len(report["assembled_journal_stacks"]) == 4
            and all(row["passed"] for row in report["assembled_journal_stacks"])
            and len(report["journal_hardware_removal"]) == 8
            and all(row["passed"] for row in report["journal_hardware_removal"])
            and all(row["passed"] for row in report["continuous_nut_loading"])
            and all(
                row["continuous_path"]["passed"]
                for row in report["sleeve_service_servo_removed"]
                + report["motor_and_prop_insertion"]
            )
            and len(report["integral_retention_caps"]) == 4
            and all(row["passed"] for row in report["integral_retention_caps"])
            and report["all_hardware_A2"]
            and report["minimum_sleeve_flat_wall_mm"] >= 1.5 - TOL
            and all(row["passed"] for row in report["functional_wall_probes"])
            and all(
                row["valid_brep"]
                and row["solid_count"] == 1
                and row["watertight_mesh"]
                and row["mesh_components"] == 1
                for row in report["geometry"]
            )
            and all(
                abs(value) < TOL
                for value in report["identical_sleeve_SKU_difference_mm3"]
            )
        )
        target = source.parent / (source.stem + "_propulsion_validation.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {"local_propulsion_report": str(target), "passed": report["passed"]}
            ),
            flush=True,
        )
        return report
    finally:
        App.closeDocument(doc.Name)
