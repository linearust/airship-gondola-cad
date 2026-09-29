#!/usr/bin/env python3
"""Export simulation datums from validated saved CAD; never regenerate or save it.

Run with normal Python. The launcher reuses the project's FreeCAD runtime.
This exports geometry, not a complete airship dynamics model or measured CG.
"""

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gondola.provenance import file_sha256, source_fingerprint  # noqa: E402


def vector_m(value):
    return [round(float(component) / 1000, 9) for component in value]


def approximation(points):
    """A deliberately explicit BF approximation, never an automatic CAD edit.

    Refuse a materially changed layout instead of reusing its convenient numbers.
    The exact saved positions are always exported separately.
    """
    simple = {"Port": [0, 0.065, 0.050], "Starboard": [0, -0.065, 0.050]}
    if any(
        len(points[name]) != 3 or not all(math.isfinite(v) for v in points[name])
        for name in simple
    ):
        raise ValueError("Expected finite 3D pivot coordinates in metres.")
    errors = {name: math.dist(points[name], simple[name]) for name in simple}
    if any(error > 0.002 for error in errors.values()):
        return {
            "available": False,
            "reason": "Layout changed; review a new approximation.",
        }
    return {
        "available": True,
        "status": "Optional preliminary model only; CAD and manufacturing dimensions are unchanged.",
        "pivot_positions_cad_m": simple,
        "span_m": 0.130,
        "rail_contact_to_pivot_m": 0.050,
        "position_error_m": errors,
        "absolute_moment_error_bound_Nm_per_N": errors,
        "error_scope": "Per motor: |delta torque| <= |delta position| * |force| in the same frame. Not a relative error bound or an inertia approximation.",
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
    for prefix in ("Port", "Starboard"):
        pod = doc.getObject(prefix + "Pod")
        motor = doc.getObject(prefix + "Motor")
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
            "propeller_envelope_centre_cad_m": vector_m(
                world_shape(doc.getObject(prefix + "PropellerDisk")).CenterOfMass
            ),
            "neutral_geometric_axis_cad": direction(motor, (1, 0, 0)),
            "positive_tilt_axis_cad": direction(pod, (0, 1, 0)),
            "positive_thrust_sign": None,
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
            "optical_host": doc.OpticalFlowModule.getParentGeoFeatureGroup().Name,
            "optical_pitch_deg": float(doc.OpticalPitchStage.Pitch),
            "optical_pitch_pivot_cad_m": point(doc.OpticalPitchStage),
            "rail_length_m": float(doc.ContinuousRail.Shape.BoundBox.XLength) / 1000,
        },
        "simplified_geometry": approximation(points),
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
    }


def export(cad, output):
    import FreeCAD as App

    cad, output = Path(cad).resolve(), Path(output).resolve()
    report_path = cad.with_name(cad.stem + "_validation.json")
    if output.suffix.lower() != ".json" or output in (cad, report_path):
        raise ValueError(
            "Output must be a separate JSON snapshot, not CAD or its validation report."
        )
    digest = file_sha256(cad)
    fingerprint = source_fingerprint()
    report = json.loads(report_path.read_text())
    if (
        not report.get("passed")
        or report.get("source_fingerprint") != fingerprint
        or report.get("source_hashes_after", {}).get(cad.name) != digest
    ):
        raise ValueError(
            "Passing validation must match current source and exact saved CAD bytes."
        )
    doc = App.openDocument(str(cad))
    try:
        if doc.DesignRegistry.SourceFingerprint != fingerprint:
            raise ValueError("Saved CAD is stale relative to current geometry source.")
        result = {
            "schema_version": 1,
            "units": {
                "length": "m",
                "mass": "kg",
                "inertia": "kg*m^2",
                "angle": "rad except explicitly named *_deg fields",
            },
            "basis": {
                "cad_file": cad.name,
                "cad_sha256": digest,
                "source_fingerprint": fingerprint,
                "validation_sha256": file_sha256(report_path),
                "exporter_sha256": file_sha256(__file__),
            },
            **extract(doc),
        }
    finally:
        App.closeDocument(doc.Name)
    if file_sha256(cad) != digest or source_fingerprint() != fingerprint:
        raise RuntimeError(
            "CAD or source changed while extracting simulation parameters."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"Simulation parameter snapshot: {output}")


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
    from gondola.freecad_runtime import locate_appimage, mounted_appimage

    with mounted_appimage(locate_appimage()) as mount:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(mount / "usr/lib")))
        subprocess.run(
            [
                str(mount / "AppRun"),
                "python",
                __file__,
                "--native",
                "--cad",
                str(args.cad.resolve()),
                "--output",
                str(args.output.resolve()),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )


if __name__ == "__main__":
    main()
