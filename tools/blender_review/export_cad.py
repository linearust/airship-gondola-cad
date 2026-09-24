"""Read saved FreeCAD geometry and sample review poses without saving the document.

Run with FreeCAD's Python runtime (normally through sibling run.py). Blender is
only a visual review derivative; the native B-rep and validation remain authority.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import FreeCAD as App
import MeshPart

from gondola.cad import belongs_to_group, world_shape
from gondola.parts import optical_mount, stack_interface
from gondola.provenance import file_sha256, source_fingerprint

CATEGORIES = ("PrintedParts", "HardwareParts", "ReferenceParts", "TapeReferences")


def matrix(placement):
    value = placement.toMatrix()
    return [[value.A[row * 4 + col] for col in range(4)] for row in range(4)]


def ramp(frame, start, end):
    return max(0.0, min(1.0, (frame - start) / (end - start)))


def curve(frame, points):
    for (start, a), (end, b) in zip(points, points[1:]):
        if frame <= end:
            return a + (b - a) * ramp(frame, start, end)
    return points[-1][1]


def color(obj, category, rail_names):
    if category == "PrintedParts":
        return [0.72, 0.78, 0.8, 1] if obj.Name in rail_names else [0.31, 0.66, 0.76, 1]
    if category == "HardwareParts":
        return [0.92, 0.64, 0.19, 1]
    if category == "TapeReferences":
        return [0.64, 0.4, 0.82, 0.6]
    if "Propeller" in obj.Name:
        return [0.23, 0.54, 0.91, 0.22]
    if any(key in obj.Name for key in ("FC", "LR900", "PAS")):
        return [0.18, 0.48, 0.29, 1]
    return [0.29, 0.34, 0.4, 1]


def representation(obj):
    """Describe the installed proxy without substituting manufacturing stock."""
    if hasattr(obj, "SuppliedHornMeasured") and not obj.SuppliedHornMeasured:
        return "Unmeasured supplied X06 horn; locally prepared example, not purchased dimensions or verified material."
    if hasattr(obj, "PrintBlankShape"):
        return "Prepared assembly example only; the manufacturing print uses a separate undrilled blank."
    return "Saved nominal installed CAD shape."


def review_objects(registry):
    """Installed leaves only: no fit samples, centring jig or clearance solids."""
    objects = [obj for category in CATEGORIES for obj in getattr(registry, category)]
    names = [obj.Name for obj in objects]
    if len(set(names)) != len(names):
        raise RuntimeError("Registry contains duplicate review parts.")
    excluded = {
        obj.Name
        for field in ("FitCoupons", "ClearanceVolumes")
        for obj in getattr(registry, field)
    }
    if excluded.intersection(names):
        raise RuntimeError(
            "A bench fit sample or clearance volume leaked into installed review parts."
        )
    if any("OutputBearingSpacer" in name for name in names):
        raise RuntimeError("Update the axial-travel caption for an installed spacer.")
    return objects


def check_review_basis(doc, report):
    """Reject stale presentation assumptions after a mechanical redesign."""
    evidence = report["local_propulsion_evidence"]
    service = evidence["saved_servo_module_service"]
    if report["gear_configuration"] != "48_16":
        raise RuntimeError(
            "Update review angles and captions for the selected gearing."
        )
    for prefix in ("Port", "Starboard"):
        horn = doc.getObject(prefix + "ServoHorn")
        adapter = doc.getObject(prefix + "HornGearAdapter")
        if (
            horn is None
            or getattr(horn, "SuppliedHornMeasured", True)
            or adapter is None
            or not hasattr(adapter, "PrintBlankShape")
        ):
            raise RuntimeError(
                "Update review captions for changed horn/preparation evidence."
            )
        for position in ("Near", "Far"):
            for kind in ("Bolt", "Nut"):
                if doc.getObject(prefix + "HornGearClamp" + position + kind) is None:
                    raise RuntimeError(
                        "Expected both prepared-example horn fastening pairs."
                    )
        pod = doc.getObject(prefix + "Pod")
        if float(pod.MinimumTilt) != -180 or float(pod.MaximumTilt) != 180:
            raise RuntimeError("Update the review for changed native tilt limits.")
    for row in evidence["saved_carrier_metal_clearances"]:
        if any(
            abs(row["axial_travel"][key] - 0.5) > 1e-8
            for key in ("negative_mm", "positive_mm")
        ):
            raise RuntimeError(
                "Update axial-travel poses and captions for the new stops."
            )
    for row in service["part_paths"]:
        if row["waypoints_mm"] != [[0, 0, 0], [0, 0, 0.5], [80, 0, 0.5]]:
            raise RuntimeError(
                "Update the review for changed servo-module removal paths."
            )
    for index, sign in enumerate((1, -1)):
        gear = service["output_gear_removal"][index]
        pair = service["mount_fastener_release"][index]
        expected = (
            (gear["segments"][-1]["end_mm"], [0, -sign * 35, 0]),
            (pair["bolt_axial_withdrawal"]["segments"][-1]["end_mm"], [0, 0, 8.2]),
            (pair["nut_axial_removal"]["segments"][0]["end_mm"], [0, 0, -0.2]),
            (pair["nut_axial_removal"]["segments"][-1]["end_mm"], [sign * 25, 0, -0.2]),
        )
        if any(
            any(abs(a - b) > 1e-8 for a, b in zip(actual, target))
            for actual, target in expected
        ):
            raise RuntimeError(
                "Update the review for changed gear/fastener removal paths."
            )


def export(cad_path, output):
    original_hash = file_sha256(cad_path)
    fingerprint = source_fingerprint()
    doc = App.openDocument(str(cad_path))
    try:
        registry = doc.DesignRegistry
        if registry.SourceFingerprint != fingerprint:
            raise RuntimeError(
                "Saved CAD does not match current source; rebuild and validate it first."
            )
        report_path = cad_path.with_name(cad_path.stem + "_validation.json")
        report = json.loads(report_path.read_text())
        if not report.get("passed") or report["source_fingerprint"] != fingerprint:
            raise RuntimeError(
                "A passing validation report for this source is required."
            )
        hashes = report["source_hashes_after"]
        if hashes.get(cad_path.name) != original_hash:
            raise RuntimeError(
                "Validation report does not identify these exact saved CAD bytes."
            )
        check_review_basis(doc, report)
        objects = review_objects(registry)
        rail_names = {obj.Name for obj in registry.RailSegments}
        parts = []
        max_bound_error = 0.0
        for category in CATEGORIES:
            for obj in getattr(registry, category):
                if not obj.isDerivedFrom("Part::Feature"):
                    raise RuntimeError(f"Non-leaf registry item: {obj.Name}")
                shape = obj.Shape.copy()
                shape.Placement = App.Placement()
                mesh = MeshPart.meshFromShape(
                    Shape=shape,
                    LinearDeflection=0.04,
                    AngularDeflection=0.12,
                    Relative=False,
                )
                vertices, triangles = mesh.Topology
                placed = mesh.copy()
                placed.transform(obj.getGlobalPlacement().toMatrix())
                native_bounds = world_shape(obj).BoundBox
                error = max(
                    abs(getattr(placed.BoundBox, key) - getattr(native_bounds, key))
                    for key in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
                )
                max_bound_error = max(max_bound_error, error)
                if error > 0.08:
                    raise RuntimeError(
                        f"Mesh placement mismatch: {obj.Name}: {error} mm"
                    )
                parts.append(
                    {
                        "name": obj.Name,
                        "label": obj.Label,
                        "category": category,
                        "representation": representation(obj),
                        "color": color(obj, category, rail_names),
                        "vertices": [[v.x, v.y, v.z] for v in vertices],
                        "triangles": [list(triangle) for triangle in triangles],
                        "matrix": matrix(obj.getGlobalPlacement()),
                    }
                )

        all_names = [obj.Name for obj in objects]
        propulsion = [
            obj.Name
            for obj in objects
            if belongs_to_group(obj, doc.MainPropulsionModule)
        ]
        drive_names = [
            obj.Name for obj in objects if belongs_to_group(obj, doc.ServoDriveModule)
        ]
        pod_names = {
            prefix: {
                obj.Name
                for obj in objects
                if belongs_to_group(obj, doc.getObject(prefix + "Pod"))
            }
            for prefix in ("Port", "Starboard")
        }
        port_detail = [name for name in propulsion if not name.startswith("Starboard")]
        original_drive = App.Placement(doc.ServoDriveModule.Placement)
        scenes = []

        def reset(host="BatteryEquipmentModule"):
            doc.PortPod.Tilt = doc.StarboardPod.Tilt = 0
            doc.ServoDriveModule.Placement = original_drive
            stack_interface.attach_to_host(doc.OpticalFlowModule, doc.getObject(host))
            optical_mount.set_angles(doc, 0, 0)
            doc.recompute()

        def scene(
            name,
            title,
            description,
            frames,
            visible,
            focus,
            markers,
            pose,
            host="BatteryEquipmentModule",
        ):
            reset(host)
            samples = []
            # Every frame is sampled from native controls: interpolation never has
            # to infer a 360-degree path from equivalent endpoint quaternions.
            for frame in range(1, frames + 1):
                offsets, hidden = pose(frame)
                doc.recompute()
                sample = {}
                for name_ in visible:
                    obj = doc.getObject(name_)
                    placement = App.Placement(obj.getGlobalPlacement())
                    if name_ in offsets:
                        placement.Base += doc.MainPropulsionModule.getGlobalPlacement().Rotation.multVec(
                            App.Vector(*offsets[name_])
                        )
                    sample[name_] = {
                        "matrix": matrix(placement),
                        "visible": name_ not in hidden,
                    }
                samples.append({"frame": frame, "poses": sample})
            scenes.append(
                {
                    "name": name,
                    "title": title,
                    "description": description,
                    "frames": frames,
                    "visible": visible,
                    "focus": focus,
                    "markers": [{"frame": f, "label": label} for f, label in markers],
                    "samples": samples,
                }
            )

        scene(
            "01 Assembly",
            "COMPLETE ASSEMBLY",
            "Nominal CAD assembly; propeller disks are swept envelopes. Supplied horns and machined adapters are unmeasured preparation examples. Bench centring jig and print blanks are not installed parts.",
            120,
            all_names,
            [[-150, -115, -2], [150, 115, 90]],
            [(1, "Nominal assembled configuration")],
            lambda f: ({}, set()),
        )

        def independent(frame):
            doc.PortPod.Tilt = curve(
                frame,
                [
                    (1, 0),
                    (49, 180),
                    (97, 0),
                    (145, -180),
                    (193, 0),
                    (241, 180),
                    (289, 0),
                ],
            )
            doc.StarboardPod.Tilt = curve(
                frame,
                [
                    (1, 0),
                    (97, 0),
                    (145, 180),
                    (193, -180),
                    (241, 0),
                    (265, -90),
                    (289, 0),
                ],
            )
            return {}, set()

        scene(
            "02 Independent tilt",
            "INDEPENDENT THRUST VECTORING",
            "Native output +/-180 deg; input -output/3. Bounded motion returns through intermediate angles; no wraparound. Wires are not simulated.",
            289,
            all_names,
            [[-145, -112, -2], [145, 112, 90]],
            [
                (1, "Port only"),
                (97, "Both axes independent"),
                (193, "Different directions"),
                (289, "Neutral"),
            ],
            independent,
        )

        def geared(frame):
            doc.PortPod.Tilt = curve(
                frame, [(1, 0), (49, 180), (97, 0), (145, -180), (193, 0)]
            )
            return {}, set()

        scene(
            "03 Gear and horn",
            "GEAR / HORN / SHAFT REVIEW",
            "48T driver / 16T driven: input -60..+60 deg, output +180..-180 deg. Supplied horn and paired-drilled adapter are preparation examples, not measured purchased fits or print blanks. Reference teeth; no backlash/contact simulation.",
            193,
            port_detail,
            [[-28, -12, 14], [30, 103, 77]],
            [
                (1, "Neutral"),
                (49, "Output +180 / input -60"),
                (97, "Neutral"),
                (145, "Output -180 / input +60"),
                (193, "Neutral"),
            ],
            geared,
        )

        def endplay(frame):
            shift = curve(
                frame, [(1, 0), (49, 0.5), (97, -0.5), (145, 0), (193, 0.5), (241, 0)]
            )
            doc.PortPod.Tilt = curve(
                frame, [(1, 0), (97, 0), (145, 90), (193, -90), (241, 0)]
            )
            return {name: (0, shift, 0) for name in pod_names["Port"]}, set()

        scene(
            "04 Axial allowance",
            "AXIAL TRAVEL AT ACTUAL SCALE",
            "Carrier and shafts move +/-0.5 mm toward integral frame stops; NOT bearing internal play. Bearings stay fixed in this prescribed pose; no spacer is installed. No friction, bearing-capture deformation, retention or load simulation.",
            241,
            port_detail,
            [[-18, 83, 36], [18, 100, 61]],
            [
                (1, "Nominal"),
                (49, "+0.5 mm stop"),
                (97, "-0.5 mm stop"),
                (145, "Rotation with permitted travel"),
                (241, "Nominal"),
            ],
            endplay,
        )

        def optical(frame):
            roll = curve(
                frame,
                [
                    (1, 0),
                    (37, 20),
                    (73, -20),
                    (109, 0),
                    (181, 0),
                    (217, 20),
                    (253, -20),
                    (289, 0),
                ],
            )
            pitch = curve(
                frame,
                [
                    (1, 0),
                    (109, 0),
                    (145, 20),
                    (181, -20),
                    (217, 20),
                    (253, -20),
                    (289, 0),
                ],
            )
            optical_mount.set_angles(doc, roll, pitch)
            return {}, set()

        for number, host, label in (
            (5, "BatteryEquipmentModule", "Battery"),
            (6, "ElectronicsEquipmentModule", "FC"),
        ):
            origin = doc.getObject(host).getGlobalPlacement().Base
            scene(
                f"0{number} Optical on {label}",
                f"OPTICAL MANUAL TRIM / {label.upper()} HOST",
                "Manual roll and pitch +/-20 deg; loosen, align and retighten pivot joints. Not actuated or self-levelling. Alternate installed host, not a transfer path. Sensor local +Z is its viewing direction.",
                289,
                all_names,
                [
                    [origin.x - 42, origin.y - 40, origin.z + 7],
                    [origin.x + 42, origin.y + 40, origin.z + 97],
                ],
                [
                    (1, "Aligned"),
                    (37, "Roll +20"),
                    (73, "Roll -20"),
                    (145, "Pitch +20"),
                    (181, "Pitch -20"),
                    (217, "Combined trim"),
                    (289, "Aligned"),
                ],
                optical,
                host,
            )

        def removal(frame):
            offsets, hidden = {}, set()
            for prefix, sign, start in (("Port", 1, 13), ("Starboard", -1, 61)):
                name = prefix + "OutputGear"
                offsets[name] = (0, -sign * 35 * ramp(frame, start, start + 35), 0)
                if frame > start + 35:
                    hidden.add(name)
            for prefix, sign, start in (("Port", 1, 109), ("Starboard", -1, 181)):
                bolt, nut = (
                    "ServoBridge" + prefix + "Bolt",
                    "ServoBridge" + prefix + "Nut",
                )
                offsets[bolt] = (0, 0, 8.2 * ramp(frame, start, start + 23))
                offsets[nut] = (
                    sign * 25 * ramp(frame, start + 29, start + 59),
                    0,
                    -0.2 * ramp(frame, start + 23, start + 29),
                )
                if frame > start + 23:
                    hidden.add(bolt)
                if frame > start + 59:
                    hidden.add(nut)
            shift = (80 * ramp(frame, 277, 336), 0, 0.5 * ramp(frame, 253, 276))
            offsets.update({name: shift for name in drive_names})
            return offsets, hidden

        scene(
            "07 Servo module removal",
            "PAIRED SERVO MODULE / BENCH REMOVAL",
            "UNPOWERED BENCH ONLY: leads disconnected and gear set screws released first. Sequentially remove 16T gears and two M2 pairs; lift 0.5 mm, slide +X 80 mm. Nearby rail equipment excluded. Playback repeats by resetting the bench state, not by a verified reassembly operation.",
            361,
            propulsion,
            [[-50, -111, 0], [119, 111, 90]],
            [
                (1, "Disconnect leads / release gear set screws"),
                (13, "Remove Port 16T"),
                (61, "Remove Starboard 16T"),
                (109, "Remove Port mount bolt / nut"),
                (181, "Remove Starboard mount bolt / nut"),
                (253, "Lift module 0.5 mm"),
                (277, "Slide module +X 80 mm"),
                (337, "Module removed; output supports retained"),
            ],
            removal,
        )

        result = {
            "metadata": {
                "cad_path": str(cad_path),
                "cad_sha256": original_hash,
                "source_fingerprint": fingerprint,
                "revision": report["revision"],
                "units": "mm",
                "fps": 24,
                "part_count": len(parts),
                "excluded_fit_samples": sorted(obj.Name for obj in registry.FitCoupons),
                "installed_representation": "Prepared assembly examples are displayed; undrilled PrintBlankShape stock and the bench-only centring jig are excluded.",
                "mesh_max_bounds_error_mm": max_bound_error,
                "scope": "Visual derivative of saved CAD; prescribed rigid motion, not a physics or collision simulation.",
                "validation_report": str(report_path),
            },
            "parts": parts,
            "scenes": scenes,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, separators=(",", ":")) + "\n")
        print(
            json.dumps(
                {
                    "parts": len(parts),
                    "scenes": len(scenes),
                    "max_mesh_bound_error_mm": max_bound_error,
                    "output": str(output),
                }
            )
        )
    finally:
        App.closeDocument(doc.Name)
        if (
            file_sha256(cad_path) != original_hash
            or source_fingerprint() != fingerprint
        ):
            raise RuntimeError("CAD or design source changed during review export.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cad", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.cad.resolve(), args.output.resolve())
