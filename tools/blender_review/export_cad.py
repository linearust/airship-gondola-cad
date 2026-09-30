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
from gondola.contracts import servo_horns
from gondola.parts import optical_mount
from gondola.provenance import file_sha256
from tools.blender_review.motion_plan import REVIEW_MOTION, curve
from tools.cad_snapshot import open_validated_cad

CATEGORIES = ("PrintedParts", "HardwareParts", "ReferenceParts", "TapeReferences")
REVIEW_HORN_PROFILE = "KST_X06_HALF_ARM_1"
REVIEW_HORN_SKU = "KST_X06_STOCK_HALF_ARM_1"
REVIEW_HORN_STEP_SHA256 = (
    "ea9ad94160411df4c32e495eda85f75a43bcfcb379a86b113ad6e03c8aa79c81"
)


def matrix(placement):
    value = placement.toMatrix()
    return [[value.A[row * 4 + col] for col in range(4)] for row in range(4)]


def color(obj, category, rail_names):
    if category == "PrintedParts":
        return [0.72, 0.78, 0.8, 1] if obj.Name in rail_names else [0.31, 0.66, 0.76, 1]
    if category == "HardwareParts":
        return [0.92, 0.64, 0.19, 1]
    if category == "TapeReferences":
        return [0.64, 0.4, 0.82, 0.6]
    if "Propeller" in obj.Name:
        return [0.23, 0.54, 0.91, 0.22]
    if any(key in obj.Name for key in ("FC", "Radio", "PAS")):
        return [0.18, 0.48, 0.29, 1]
    return [0.29, 0.34, 0.4, 1]


def representation(obj):
    """Describe the installed proxy without substituting manufacturing stock."""
    if getattr(obj, "HornProfile", "") in servo_horns.PROFILES:
        profile = servo_horns.profile(obj.HornProfile)
        return (
            profile.label
            + ". Manufacturer nominal STEP geometry with only the declared hole preparation. "
            + servo_horns.preparation_note(profile)
            + " Resin, mass, installed seating and root concentricity remain unmeasured."
        )
    if getattr(obj, "Name", "").endswith("HornGearAdapter"):
        return "Installed round-hole/slot adapter for the OEM half arm: near diameter 1.8 mm hole at 6.8 mm, far 1.8 x 2.4 mm slot at 13.2 mm, rear M1.4x8 screws and front M1.4 nuts. The open C-shaped locating seat and near hole limit assembly movement; they do not certify received-horn concentricity or assembled runout."
    return "Saved nominal installed CAD shape."


def review_objects(registry):
    """Installed leaves only: no fit samples or clearance solids."""
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
    if report["gear_configuration"] != "48_16":
        raise RuntimeError(
            "Update review angles and captions for the selected gearing."
        )
    for prefix in ("Port", "Starboard"):
        horn = doc.getObject(prefix + "ServoHorn")
        adapter = doc.getObject(prefix + "HornGearAdapter")
        if (
            horn is None
            or getattr(horn, "HornProfile", "") != REVIEW_HORN_PROFILE
            or servo_horns.profile(side=prefix).key != REVIEW_HORN_PROFILE
            or getattr(horn, "HardwareSKU", "") != REVIEW_HORN_SKU
            or adapter is None
            or hasattr(adapter, "PrintBlankShape")
        ):
            raise RuntimeError(
                "Update review captions for changed purchased-horn evidence."
            )
        if (
            getattr(horn, "ManufacturerGeometryProvided", False) is not True
            or getattr(horn, "ManufacturerGeometrySHA256", "")
            != REVIEW_HORN_STEP_SHA256
            or getattr(horn, "HornPreparationRequired", False) is not True
            or getattr(horn, "FactoryM1_6ThreadsConfirmed", True) is not False
            or getattr(horn, "PurchasedHornMeasured", True) is not False
            or getattr(horn, "AxialSeatingMeasured", True) is not False
        ):
            raise RuntimeError(
                "Update review captions for changed OEM horn provenance."
            )
        try:
            contract = json.loads(horn.HornInterfaceContract)
        except (AttributeError, TypeError, ValueError) as error:
            raise RuntimeError(
                "Missing reviewed OEM horn interface contract."
            ) from error
        expected_contract = {
            "profile": REVIEW_HORN_PROFILE,
            "manufacturer_geometry_sha256": REVIEW_HORN_STEP_SHA256,
            "attachment_radii_mm": [6.8, 13.2],
            "adapter_round_hole_x_mm": 6.8,
            "adapter_round_hole_diameter_mm": 1.8,
            "adapter_slot_width_mm": 1.8,
            "adapter_slot_centres_x_mm": [13.2],
            "adapter_slot_centre_allowance_mm": 0.3,
            "adapter_slot_overall_length_mm": 2.4,
            "nominal_arm_thickness_mm": 2.0,
            "screw_length_mm": 8.0,
            "nuts_per_side": 2,
        }
        if not isinstance(contract, dict) or any(
            contract.get(key) != value for key, value in expected_contract.items()
        ):
            raise RuntimeError(
                "Update review captions for changed OEM horn dimensions."
            )
        for position in ("Near", "Far"):
            bolt = doc.getObject(prefix + "HornGearClamp" + position + "Bolt")
            nut = doc.getObject(prefix + "HornGearClamp" + position + "Nut")
            if (
                bolt is None
                or getattr(bolt, "HardwareSKU", "") != "M1_4X8_PAN_HEAD_KIT"
            ):
                raise RuntimeError("Expected both rear M1.4x8 horn attachment screws.")
            if nut is None or getattr(nut, "HardwareSKU", "") != "M1_4_HEX_NUT_DIN934":
                raise RuntimeError(
                    "Expected both front M1.4 horn nuts for the reviewed OEM profile."
                )
        pod = doc.getObject(prefix + "Pod")
        if float(pod.MinimumTilt) != -180 or float(pod.MaximumTilt) != 180:
            raise RuntimeError("Update the review for changed native tilt limits.")
    REVIEW_MOTION.check_basis(evidence)


def check_optical_carrier_basis(doc):
    """Keep the optical caption bound to its actual carrier parent and hardware."""
    optical = doc.getObject("OpticalFlowModule")
    host_name = getattr(optical, "CarrierHostName", "")
    host = doc.getObject(host_name)
    side = str(getattr(optical, "MountSide", ""))
    if (
        optical is None
        or host_name
        not in (
            "BatteryEquipmentModule",
            "ElectronicsEquipmentModule",
            "AccessoryEquipmentModule",
        )
        or host is None
        or optical.getParentGeoFeatureGroup() != host
        or side not in ("PositiveX", "NegativeX")
        or "RailPositionX" in optical.PropertiesList
    ):
        raise RuntimeError("Update optical carrier review for changed host binding.")
    for name in ("OpticalFootBolt1", "OpticalPitchBolt"):
        obj = doc.getObject(name)
        if obj is None or getattr(obj, "HardwareSKU", "") != "M2X8_BUTTON_HEAD":
            raise RuntimeError("Expected two M2x8 optical foot/pitch screws.")
    for name in ("OpticalFootNut1", "OpticalPitchNut"):
        obj = doc.getObject(name)
        if obj is None or getattr(obj, "HardwareSKU", "") != "M2_HEX_NUT":
            raise RuntimeError("Expected two M2 optical foot/pitch nuts.")
    return {"host": host_name, "side": side}


def export(cad_path, output):
    with open_validated_cad(cad_path, output) as snapshot:
        doc = snapshot.doc
        registry = doc.DesignRegistry
        report = snapshot.report
        check_review_basis(doc, report)
        optical_attachment = check_optical_carrier_basis(doc)
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

        def reset():
            doc.PortPod.Tilt = doc.StarboardPod.Tilt = 0
            doc.ServoDriveModule.Placement = original_drive
            optical_mount.set_pitch(doc, 0)
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
        ):
            reset()
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
            "Nominal CAD assembly; propeller disks are swept envelopes. Both servos use the manufacturer stock plastic half arm 1, with two prepared factory holes and rear M1.4x8 screws/front M1.4 nuts on an adapter with one near round hole and one far slot. Resin, mass, installed seating and assembled runout remain unmeasured.",
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
            "48T driver / 16T driven: input -60..+60 deg, output +180..-180 deg. Manufacturer stock plastic half arm 1 retains its source geometry except two prepared holes; rear M1.4x8 screws and front nuts clamp the round-hole/slot adapter after alignment. Installed fit remains unverified. Gear teeth are reference geometry; no backlash/contact simulation.",
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
            shift = REVIEW_MOTION.axial_shift(frame)
            doc.PortPod.Tilt = curve(
                frame, [(1, 0), (97, 0), (145, 90), (193, -90), (241, 0)]
            )
            return {name: (0, shift, 0) for name in pod_names["Port"]}, set()

        scene(
            "04 Axial allowance",
            "AXIAL TRAVEL AT ACTUAL SCALE",
            REVIEW_MOTION.axial_description(),
            REVIEW_MOTION.axial_steps[-1][0],
            port_detail,
            [[-18, 83, 36], [18, 100, 61]],
            REVIEW_MOTION.axial_markers(),
            endplay,
        )

        def optical(frame):
            pitch = curve(frame, [(1, 0), (37, 20), (73, -20), (109, 20), (145, 0)])
            optical_mount.set_pitch(doc, pitch)
            return {}, set()

        origin = doc.OpticalFlowModule.getGlobalPlacement().Base
        scene(
            "05 Optical carrier pitch",
            "OPTICAL MANUAL PITCH / CARRIER SIDE FOOT",
            "One manual pitch axis +/-20 deg. A rigid shallow tongue and one M2 pair fix the foot to "
            + optical_attachment["host"]
            + " ("
            + optical_attachment["side"]
            + "); a second pair locks pitch. Loosen, align and retighten the pivot; no roll correction, actuation or self-levelling. Host and side remain fixed during this review. Relocation requires renewed populated-device, service and field checks. Sensor local +Z is the viewing direction.",
            145,
            all_names,
            [[origin.x - 35, origin.y - 30, 0], [origin.x + 35, origin.y + 30, 60]],
            [
                (1, "Aligned"),
                (37, "Pitch +20"),
                (73, "Pitch -20"),
                (109, "Pitch +20"),
                (145, "Aligned"),
            ],
            optical,
        )

        scene(
            "06 Servo module removal",
            "PAIRED SERVO MODULE / BENCH REMOVAL",
            REVIEW_MOTION.removal_description()
            + " Horns, adapters and their rear screws/front nuts stay on the servos throughout this module-removal scene.",
            REVIEW_MOTION.removal_frames,
            propulsion,
            [[-50, -111, 0], [119, 111, 90]],
            REVIEW_MOTION.removal_markers(),
            lambda frame: REVIEW_MOTION.removal_pose(frame, drive_names),
        )

        result = {
            "metadata": {
                "cad_path": str(snapshot.cad_path),
                **snapshot.provenance(),
                "exporter_sha256": file_sha256(__file__),
                "snapshot_helper_sha256": file_sha256(
                    Path(__file__).resolve().parents[1] / "cad_snapshot.py"
                ),
                "motion_plan_sha256": file_sha256(
                    Path(__file__).with_name("motion_plan.py")
                ),
                "revision": report["revision"],
                "units": "mm",
                "fps": 24,
                "part_count": len(parts),
                "excluded_fit_samples": sorted(obj.Name for obj in registry.FitCoupons),
                "installed_representation": "Installed round-hole/slot adapters and manufacturer stock plastic half-arm geometry with two declared hole enlargements are displayed, including rear M1.4x8 screws and front M1.4 nuts. Fit samples and clearance reservations are excluded. Nominal source geometry does not establish resin, mass, delivered fit or installed seating.",
                "mesh_max_bounds_error_mm": max_bound_error,
                "scope": "Visual derivative of saved CAD; prescribed rigid motion, not a physics or collision simulation.",
                "validation_report": str(snapshot.report_path),
            },
            "parts": parts,
            "scenes": scenes,
        }
    snapshot.write_json(result, separators=(",", ":"))
    print(
        json.dumps(
            {
                "parts": len(parts),
                "scenes": len(scenes),
                "max_mesh_bound_error_mm": max_bound_error,
                "output": str(snapshot.output_path),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cad", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.cad.resolve(), args.output.resolve())
