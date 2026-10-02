#!/usr/bin/env python3
"""Export simulation datums from validated saved CAD; never regenerate or save it.

Run with normal Python. The launcher reuses the project's FreeCAD runtime.
This exports geometry, not a complete airship dynamics model or measured CG.
"""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.cad_snapshot import open_validated_cad  # noqa: E402


def vector_m(value):
    return [round(float(component) / 1000, 9) for component in value]


def optical_pitch_degrees(stage):
    """Read signed local-Y pose; the saved command may exceed native limits."""
    import FreeCAD as App

    try:
        command = float(stage.Pitch)
        minimum, maximum = float(stage.MinimumAngle), float(stage.MaximumAngle)
        rotation = stage.Placement.Rotation
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Optical pitch metadata is missing or invalid.") from error
    if not all(math.isfinite(value) for value in (command, minimum, maximum)):
        raise ValueError("Optical pitch metadata must be finite.")
    if abs(minimum + 20) > 1e-8 or abs(maximum - 20) > 1e-8:
        raise ValueError("Optical pitch limits changed; review the exported frame.")
    if not all(math.isfinite(value) for value in rotation.Q):
        raise ValueError("Optical pitch rotation must be finite.")
    local_x = rotation.multVec(App.Vector(1, 0, 0))
    angle = math.degrees(math.atan2(-local_x.z, local_x.x))
    if not math.isfinite(angle) or not rotation.isSame(
        App.Rotation(App.Vector(0, 1, 0), angle), 1e-8
    ):
        raise ValueError("Optical pitch must be a pure local-Y rotation.")
    if not minimum - 1e-8 <= angle <= maximum + 1e-8:
        raise ValueError("Actual optical pitch is outside its declared limits.")
    # Suppress floating-point serialization noise without replacing the pose
    # with a clamped command or changing the existing degrees-valued field.
    return round(angle, 9)


def printed_carrier_mass_properties(shape):
    """Uniform PA12 estimate for this print alone, about its own centroid."""
    from gondola.mass_budget import DENSITIES_G_CM3, PA12_DENSITY_SOURCE

    if len(shape.Solids) != 1:
        raise ValueError("Printed carrier inertia requires exactly one solid.")
    solid = shape.Solids[0]
    density = DENSITIES_G_CM3["PA12"]
    inertia = solid.MatrixOfInertia
    # FreeCAD's geometric inertia has units mm^5. Convert density g/cm^3 to
    # kg/mm^3 (1e-6), then the squared distance mm^2 to m^2 (another 1e-6).
    factor = density * 1e-12
    return {
        "density_kg_m3": density * 1000,
        "density_source": PA12_DENSITY_SOURCE,
        "mass_kg": solid.Volume * density * 1e-6,
        "centre_from_tilt_axis_neutral_m": vector_m(solid.CenterOfMass),
        "inertia_about_print_cg_neutral_kg_m2": [
            [getattr(inertia, f"A{row}{column}") * factor for column in (1, 2, 3)]
            for row in (1, 2, 3)
        ],
        "scope": "Uniform-density CAD estimate of the printed motor carrier only; excludes motor, propeller, shafts, gears, fasteners and wires. Not installed rotating-assembly CG or inertia. Axes are the pod's neutral local axes; inertia is about this print's own CG.",
    }


def output_support_geometry(doc, prefix):
    """Describe the saved fixed inboard pair and sole rotating output shaft."""
    from gondola.cad import belongs_to_group, world_shape

    names = {
        "Inboard": prefix + "OutputBearingInboard",
        "Outboard": prefix + "OutputBearingOutboard",
    }
    shaft_name = prefix + (
        "OutputShaftNegative" if prefix == "Port" else "OutputShaftPositive"
    )
    obsolete_shaft = prefix + (
        "OutputShaftPositive" if prefix == "Port" else "OutputShaftNegative"
    )
    assembly = doc.getObject(prefix + "Assembly")
    pod = doc.getObject(prefix + "Pod")
    frame = doc.getObject("PropulsionFixedFrame")
    cap = doc.getObject(prefix + "BearingCap")
    shaft = doc.getObject(shaft_name)
    bearings = {key: doc.getObject(name) for key, name in names.items()}
    installed_bearings = {
        obj.Name
        for obj in doc.Objects
        if obj.Name.startswith(prefix)
        and getattr(obj, "HardwareSKU", "") == "BEARING_3X6X2_5"
    }
    if (
        any(
            obj is None
            for obj in (assembly, pod, frame, cap, shaft, *bearings.values())
        )
        or doc.getObject("ServoDriveBridge") is not None
        or doc.getObject(obsolete_shaft) is not None
        or installed_bearings != set(names.values())
        or shaft.getParentGeoFeatureGroup() != pod
        or frame.getParentGeoFeatureGroup() != assembly.getParentGeoFeatureGroup()
        or not belongs_to_group(cap, assembly)
        or belongs_to_group(cap, pod)
        or any(
            not belongs_to_group(obj, assembly) or belongs_to_group(obj, pod)
            for obj in bearings.values()
        )
    ):
        raise ValueError(
            "Output support topology changed; review the exported assembly."
        )
    bearing_shapes = {key: world_shape(obj) for key, obj in bearings.items()}
    if any(len(shape.Solids) != 1 for shape in bearing_shapes.values()):
        raise ValueError("Output bearing geometry must contain one nominal solid each.")
    centres = {
        key: shape.Solids[0].CenterOfMass for key, shape in bearing_shapes.items()
    }
    local = {
        key: pod.getGlobalPlacement().inverse().multVec(centre)
        for key, centre in centres.items()
    }
    sign = 1 if prefix == "Port" else -1
    if (
        any(abs(point.x) > 1e-6 or abs(point.z) > 1e-6 for point in local.values())
        or not sign * local["Inboard"].y < sign * local["Outboard"].y < 0
    ):
        raise ValueError(
            "Both output bearings must remain coaxial and inboard of the rotor."
        )
    return {
        "arrangement": "two_fixed_inboard_bearings_open_outer_side",
        "integrated_fixed_frame": frame.Name,
        "fixed_bearing_cap": cap.Name,
        "bearings": {
            key: {
                "object": names[key],
                "centre_cad_m": vector_m(centres[key]),
                "centre_from_tilt_axis_neutral_m": vector_m(local[key]),
                "fixed_during_tilt": True,
            }
            for key in names
        },
        "bearing_centre_spacing_m": (centres["Outboard"] - centres["Inboard"]).Length
        / 1000,
        "output_shaft": {"object": shaft.Name, "rotating_parent": pod.Name},
        "idler_shafts": [],
        "scope": "Saved nominal support topology and bearing solid centroids. The outer side has no second shaft or support frame. This does not establish bearing clearance, shaft bending stiffness, installed alignment or load capacity.",
    }


def extract(doc):
    import FreeCAD as App

    from gondola.cad import world_shape

    def point(obj):
        return vector_m(obj.getGlobalPlacement().Base)

    def direction(obj, axis):
        return [
            round(v, 12)
            for v in obj.getGlobalPlacement().Rotation.multVec(App.Vector(*axis))
        ]

    rail = doc.ContinuousRail
    if (
        rail.getGlobalPlacement().Base.Length > 1e-8
        or abs(rail.getGlobalPlacement().Rotation.Angle) > 1e-8
        or abs(rail.Shape.BoundBox.ZMin) > 1e-8
        or abs(rail.Shape.BoundBox.Center.x) > 1e-8
        or abs(rail.Shape.BoundBox.Center.y) > 1e-8
    ):
        raise ValueError("Rail datum changed; review the exported frame definition.")
    propulsion = {}
    rotating_assemblies = {}
    for prefix in ("Port", "Starboard"):
        pod = doc.getObject(prefix + "Pod")
        motor = doc.getObject(prefix + "Motor")
        carrier = doc.getObject(prefix + "MotorCarrier")
        propeller = doc.getObject(prefix + "PropellerDisk")
        try:
            rotor_contract = json.loads(motor.RotorGeometryContract)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Missing saved motor/propeller datum contract.") from error
        if abs(float(pod.Tilt)) > 1e-8:
            raise ValueError("Export requires the validated neutral motor pose.")
        if direction(motor, (1, 0, 0)) != [1, 0, 0] or direction(pod, (0, 1, 0)) != [
            0,
            1,
            0,
        ]:
            raise ValueError(
                "Drive orientation changed; review the exported frame definition."
            )
        propulsion[prefix] = {
            "cad_label_not_verified_vehicle_side": True,
            "pivot_cad_m": point(pod),
            "motor_envelope_centre_cad_m": vector_m(world_shape(motor).CenterOfMass),
            "motor_mount_face_cad_m": vector_m(
                pod.getGlobalPlacement().multVec(
                    App.Vector(float(carrier.MotorMountFaceX), 0, 0)
                )
            ),
            "neutral_geometric_axis_cad": direction(motor, (1, 0, 0)),
            "positive_tilt_axis_cad": direction(pod, (0, 1, 0)),
            "positive_thrust_sign": None,
        }
        rotating_assemblies[prefix] = {
            "support_geometry": output_support_geometry(doc, prefix),
            "hardware_geometry_basis": rotor_contract,
            "illustrative_propeller_disk_centre_cad_m": vector_m(
                world_shape(propeller).CenterOfMass
            ),
            "actual_hub_seating_offset_m": None,
            "actual_hub_midplane_cad_m": None,
            "actual_blade_axial_envelope_m": None,
            "installed_rotating_mass_kg": None,
            "installed_rotating_cg_from_tilt_axis_neutral_m": None,
            "installed_rotating_inertia_about_cg_neutral_kg_m2": None,
            "printed_carrier_estimate": printed_carrier_mass_properties(carrier.Shape),
            "scope": "Actual hardware properties remain unknown. Hub midpoint relative to tilt axis is 0.0063+s metres using nominal motor dimensions; s is signed seating offset, not assumed zero for physical analysis. The displayed clearance disk uses illustrative s=0 and hub thickness as axial extent; it does not establish blade swept volume or aerodynamic centre.",
        }
    module_ids = (
        "MainPropulsionModule",
        "BatteryEquipmentModule",
        "ElectronicsEquipmentModule",
        "AccessoryEquipmentModule",
    )
    centres = (
        "ModuleBatteryEnvelope",
        "ModuleFCEnvelope",
        "ModulePASEnvelope",
        "ModuleRadioEnvelope",
        "ModuleMTF02PEnvelope",
    )
    points = {name: row["pivot_cad_m"] for name, row in propulsion.items()}
    optical = doc.OpticalFlowModule
    optical_host = doc.getObject(getattr(optical, "CarrierHostName", ""))
    optical_side = str(getattr(optical, "MountSide", ""))
    if (
        optical_host is None
        or optical_host.Name not in module_ids[1:]
        or optical.getParentGeoFeatureGroup() != optical_host
        or optical_side not in ("PositiveX", "NegativeX")
        or "RailPositionX" in optical.PropertiesList
    ):
        raise ValueError("Optical carrier binding changed; review host and side.")
    if (
        abs(points["Port"][0] - points["Starboard"][0]) > 1e-9
        or abs(points["Port"][2] - points["Starboard"][2]) > 1e-9
    ):
        raise ValueError("Pivot alignment changed; review the propulsion datum.")
    propulsion_origin = [
        round((points["Port"][axis] + points["Starboard"][axis]) / 2, 9)
        for axis in (0, 1)
    ] + [0.0]
    return {
        "frame": {
            "name": "native_CAD",
            "handedness": "right",
            "origin": "Straight rail midpoint at its nominal envelope-contact plane, Z=0. Not CV or CG; installed rail curvature is not represented.",
            "positive_x": "Along the rail and neutral motor geometric axes; vehicle-forward and thrust sign unverified.",
            "positive_y": "Toward the CAD object labelled Port; do not infer an FRD vehicle frame from side names.",
            "positive_z": "Away from the envelope, nominally downward.",
        },
        "exact_geometry": {
            "main_propulsors": propulsion,
            "propulsion_reference_frame": {
                "name": "propulsion_reference",
                "origin": "Actual pivot-pair midpoint projected onto the straight rail contact plane Z=0. Not CV or CG. Changes with rail trim and clamp seating.",
                "origin_cad_m": propulsion_origin,
                "rotation_to_cad_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "pivot_positions_m": {
                    name: [
                        round(value - origin, 9)
                        for value, origin in zip(point, propulsion_origin, strict=True)
                    ]
                    for name, point in points.items()
                },
                "coordinate_scope": "Exact translated CAD coordinates, not rounded simulation positions. Add origin_cad_m to recover native CAD positions before transforming to the vehicle frame.",
            },
            "main_pivot_span_m": math.dist(*points.values()),
            "pivot_height_from_rail_contact_m": points["Port"][2],
            "servo_to_output_angle_ratio": json.loads(
                doc.MainPropulsionModule.DriveContract
            )["angle_ratio"],
            "module_origins_cad_m": {
                name: point(doc.getObject(name)) for name in module_ids
            },
            "device_envelope_box_centres_cad_m": {
                name: {
                    "label": doc.getObject(name).Label,
                    "position_m": vector_m(
                        world_shape(doc.getObject(name)).BoundBox.Center
                    ),
                }
                for name in centres
            },
            "centre_scope": "Envelope bounding-box centres, NOT measured centres of mass, IMU locations, optical apertures or navigation antenna phase centres.",
            "optical_carrier_host": optical_host.Name,
            "optical_mount_side": optical_side,
            "optical_pitch_deg": optical_pitch_degrees(doc.OpticalPitchStage),
            "optical_pitch_pivot_cad_m": point(doc.OpticalPitchStage),
            "rail_length_m": float(doc.ContinuousRail.Shape.BoundBox.XLength) / 1000,
        },
        "whole_airship": {
            "ready_for_system_identification": False,
            "cv_definition": "Proposed: centre of displaced volume of the inflated fitted ellipsoid; confirm with the simulation team.",
            "cv_to_cad_origin_vehicle_m": None,
            "cad_to_vehicle_rotation_matrix": None,
            "ellipsoid_full_diameters_m": None,
            "ellipsoid_to_vehicle_rotation_matrix": None,
            "inflated_volume_m3": None,
            "helium_mole_fraction": None,
            "gas_temperature_K": None,
            "gas_absolute_pressure_Pa": None,
            "dry_mass_kg": None,
            "gas_mass_kg": None,
            "total_mass_including_gas_kg": None,
            "cv_to_cg_vehicle_m": None,
            "inertia_about_cg_vehicle_diagonal_kg_m2": None,
            "gas_inertia_convention": None,
            "cv_to_gondola_cg_vehicle_m": None,
            "cv_to_main_motor_pivots_vehicle_m": None,
            "aft_yaw_motor_position_vehicle_m": None,
            "aft_yaw_motor_axis_vehicle": None,
            "scope": "Fins and aft yaw installation are outside gondola CAD. A bare-hull aerodynamic approximation does not remove physically installed items from mass/CG/inertia. Null means unknown, never zero.",
        },
        "rotating_assembly_analysis": rotating_assemblies,
    }


def export(cad, output):
    with open_validated_cad(
        cad,
        output,
        tool_inputs={
            "exporter_sha256": __file__,
            "snapshot_helper_sha256": ROOT / "tools/cad_snapshot.py",
        },
    ) as snapshot:
        result = {
            "schema_version": 6,
            "units": {
                "length": "m",
                "mass": "kg",
                "inertia": "kg*m^2",
                "angle": "rad except explicitly named *_deg fields",
            },
            "basis": {
                **snapshot.provenance(),
                **snapshot.tool_hashes,
            },
            **extract(snapshot.doc),
        }
    snapshot.write_json(result, indent=2)
    print(f"Simulation parameter snapshot: {snapshot.output_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cad", type=Path, default=ROOT / "build/gondola.FCStd")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "build/simulation_parameters.json"
    )
    parser.add_argument("--native", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.native:
        export(args.cad.resolve(), args.output.resolve())
        return
    from gondola.freecad_runtime import run_native_python

    run_native_python(
        [
            __file__,
            "--native",
            "--cad",
            args.cad.resolve(),
            "--output",
            args.output.resolve(),
        ]
    )


if __name__ == "__main__":
    main()
