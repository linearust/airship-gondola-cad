"""Recompute local propulsion fit and removal evidence from current geometry.

These rigid envelopes deliberately keep the OEM motor fasteners, servo ears,
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

from .geometry import intersection_volume

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
                translated_shape(frame, y=0.45), rail.rail_shape()
            ),
            "negative_seated_rail_contact_overlap_mm3": intersection_volume(
                translated_shape(frame, y=-0.45), rail.rail_shape()
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
        key = Part.makeCylinder(0.9, 110, App.Vector(0, 12.7, 6.2), App.Vector(0, 1, 0))
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
                    positions += [(8, z) for z in (0.5, 1, 2)] + [
                        (dy, 2) for dy in (10, 15, 20, 30)
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
            and report["all_hardware_A2"]
            and report["no_rail_key_metadata"]
            and report["minimum_sleeve_flat_wall_mm"] >= 1 - TOL
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
