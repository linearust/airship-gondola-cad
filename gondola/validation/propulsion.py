"""Recompute local propulsion fit and removal evidence from current geometry.

These rigid envelopes keep the OEM motor fasteners, servo saddle retention,
and horn-to-sleeve torque connection unresolved. They prove no loaded operation.
"""

import json
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
from gondola.parts import propulsion, rail

from .geometry import intersection_volume, local_shape

TOL = 1e-5


def _overlap_failures(value, location=""):
    failures = []
    if isinstance(value, dict):
        for key, child in value.items():
            if (
                "overlap" in key
                and key.endswith("mm3")
                and isinstance(child, (int, float))
                and abs(child) > TOL
            ):
                failures.append({"field": location + "/" + key, "volume_mm3": child})
            failures.extend(_overlap_failures(child, location + "/" + key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            failures.extend(_overlap_failures(child, location + "/" + str(index)))
    return failures


def validate(source=None):
    """Build a fresh local module, check its fits, and write reproducible evidence."""
    source = Path(source).resolve() if source else OUTPUT_DIR / (STEM + ".FCStd")
    doc = App.newDocument("PropulsionSourceAudit")
    try:
        module = propulsion.build_propulsion_module(doc)
        frame = module["frame"].Shape
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
        report["nut_loading"] = [
            {
                "x_mm": dx,
                "overlap_mm3": intersection_volume(
                    frame, translated_shape(rail.nut_shape(), x=dx)
                ),
            }
            for dx in (0, 2, 4, 6, 8, 10, 15, 20)
        ]
        report["negative_nut_loading"] = [
            {
                "x_mm": -dx,
                "overlap_mm3": intersection_volume(
                    frame, rail.half_turn(translated_shape(rail.nut_shape(), x=dx))
                ),
            }
            for dx in (0, 2, 4, 6, 8, 10, 15, 20)
        ]
        report["sleeve_service_servo_removed"] = []
        report["motor_and_prop_insertion"] = []
        for prefix in ("Port", "Starboard"):
            carrier = world_shape(doc.getObject(prefix + "MotorCarrier"))
            for suffix, sign in (("Negative", -1), ("Positive", 1)):
                sleeve = world_shape(doc.getObject(prefix + "JournalSleeve" + suffix))
                driven = (prefix == "Port" and sign == -1) or (
                    prefix == "Starboard" and sign == 1
                )
                positions = [(dy, 0) for dy in (0, 0.2, 0.5, 1, 2, 4, 6, 7, 7.5, 8)]
                if driven:
                    positions += [
                        (8, z)
                        for z in (0.5, 1, 2, 5, 8, propulsion.SLEEVE_SERVICE_LIFT)
                    ] + [
                        (dy, propulsion.SLEEVE_SERVICE_LIFT) for dy in (10, 15, 20, 30)
                    ]
                else:
                    positions += [(dy, 0) for dy in (10, 15, 20, 30)]
                rows = []
                for dy, z in positions:
                    placed = translated_shape(sleeve, y=sign * dy, z=z)
                    rows.append(
                        {
                            "axial_outward_mm": dy,
                            "lift_z_mm": z,
                            "overlap_frame_mm3": intersection_volume(placed, frame),
                            "overlap_carrier_mm3": intersection_volume(placed, carrier),
                        }
                    )
                report["sleeve_service_servo_removed"].append(
                    {
                        "sleeve": prefix + suffix,
                        "servo_must_be_removed": driven,
                        "positions": rows,
                    }
                )
            for name in ("Motor", "PropellerDisk"):
                shape = world_shape(doc.getObject(prefix + name))
                report["motor_and_prop_insertion"].append(
                    {
                        "part": prefix + name,
                        "positions": [
                            {
                                "x_mm": dx,
                                "overlap_carrier_mm3": intersection_volume(
                                    translated_shape(shape, x=dx), carrier
                                ),
                                "overlap_frame_mm3": intersection_volume(
                                    translated_shape(shape, x=dx), frame
                                ),
                            }
                            for dx in (0, 1, 2, 5, 10, 15, 20, 30)
                        ],
                    }
                )
        report["printed_parts"] = len(module["printed"])
        report["purchased_hardware"] = len(module["hardware"])
        report["minimum_sleeve_flat_wall_mm"] = (
            propulsion.SLEEVE_D_FLAT - propulsion.SLEEVE_BORE_RADIUS
        )
        # Measure changed walls on actual solids, independently of declarations.
        wall_probes = [
            (
                "sleeve_D_flat",
                "PortJournalSleevePositive",
                (0, 24, 1.49),
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
                    (
                        f"foot_edge_rib_{side}",
                        "PropulsionFixedFrame",
                        (
                            4.89,
                            side * 80,
                            propulsion.BASE_Z + propulsion.FOOT_THICKNESS + 0.75,
                        ),
                        (
                            6.41,
                            side * 80,
                            propulsion.BASE_Z + propulsion.FOOT_THICKNESS + 0.75,
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
        report["journal_hardware_frame_clearance"] = [
            {
                "part": obj.Name,
                "overlap_frame_mm3": intersection_volume(world_shape(obj), frame),
            }
            for obj in module["hardware"]
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
        report["print_volume_mm3"] = module["metrics"]["printed_volume_mm3"]
        report["frame_print_bounds_mm"] = module["metrics"]["consolidation"][
            "fixed_frame_print_bounds_mm"
        ]
        report["all_hardware_A2"] = all(
            obj.MaterialSelection == "A2 stainless steel" for obj in module["hardware"]
        )
        report["no_rail_key_metadata"] = (
            "RailKeyVariant" not in module["group"].PropertiesList
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
        failures = _overlap_failures(report)
        report["overlap_failures"] = failures
        report["passed"] = (
            not failures
            and len(report["sleeve_service_servo_removed"]) == 4
            and len(report["motor_and_prop_insertion"]) == 4
            and len(report["geometry"]) == 7
            and len(report["servo_mount_axes"]) == 4
            and report["purchased_hardware"] == 16
            and report["all_hardware_A2"]
            and report["no_rail_key_metadata"]
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
