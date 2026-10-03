"""Read saved FreeCAD geometry and sample review poses without saving the document.

Run with FreeCAD's Python runtime (normally through sibling run.py). Blender is
only a visual review derivative; the native B-rep and validation remain authority.
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import FreeCAD as App
import MeshPart

from gondola.cad import belongs_to_group, world_shape
from gondola.contracts import servo_horns
from gondola.parts import optical_mount
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


def check_mesh_placement(obj, mesh):
    """Compare the placed local mesh to trimmed world-space BRep extrema."""
    placed = mesh.copy()
    placed.transform(obj.getGlobalPlacement().toMatrix())
    # Loose OCC bounds can extend to the underlying surface beyond rounded
    # trimmed faces. Keep the existing tessellation limit, but measure the BRep.
    native_bounds = world_shape(obj).optimalBoundingBox(False, False)
    error = max(
        abs(getattr(placed.BoundBox, key) - getattr(native_bounds, key))
        for key in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
    )
    if error > 0.08:
        raise RuntimeError(f"Mesh placement mismatch: {obj.Name}: {error} mm")
    return error


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
    if getattr(obj, "Name", "") == "PropulsionFixedFrame":
        return "Integrated fixed support with two inboard bearings per rotor, one external input-shaft bearing per side, shared three-bearing caps and compact closed servo frames on the raised central plinth. Nominal CAD does not establish alignment, load sharing, overhang stiffness or loaded retention."
    if getattr(obj, "HornProfile", "") in servo_horns.PROFILES:
        profile = servo_horns.profile(obj.HornProfile)
        return (
            profile.label
            + ". Unmodified manufacturer nominal STEP geometry. "
            + servo_horns.preparation_note(profile)
            + " Resin, mass, installed seating and root concentricity remain unmeasured."
        )
    if getattr(obj, "Name", "").endswith("HornGearAdapter"):
        return "Installed round-hole/slot adapter for the OEM half arm: near diameter 1.2 mm hole at 6.8 mm, optional middle 1.2 x 1.6 mm slot at 10 mm and far 1.2 x 1.8 mm slot at 13.2 mm, rear M1x6 hex bolts and front M1 nuts. The open C-shaped locating seat and near hole limit assembly movement; they do not certify received-horn concentricity or assembled runout."
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
            or getattr(horn, "HornPreparationRequired", True) is not False
            or getattr(horn, "FactoryThreadedHoles", True) is not False
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
            "adapter_round_hole_diameter_mm": 1.2,
            "adapter_slot_width_mm": 1.2,
            "adapter_slot_centres_x_mm": [10.0, 13.2],
            "adapter_slot_centre_allowances_mm": [0.2, 0.3],
            "adapter_slot_overall_lengths_mm": [1.6, 1.8],
            "optional_middle_fastener_installed": False,
            "horn_requires_drilling": False,
            "adapter_slot_centre_allowance_mm": 0.3,
            "adapter_slot_overall_length_mm": 1.8,
            "nominal_arm_thickness_mm": 2.0,
            "screw_length_mm": 6.0,
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
            if bolt is None or getattr(bolt, "HardwareSKU", "") != "M1X6_HEX_HEAD":
                raise RuntimeError("Expected both rear M1x6 horn attachment screws.")
            if nut is None or getattr(nut, "HardwareSKU", "") != "M1_HEX_NUT":
                raise RuntimeError(
                    "Expected both front M1 horn nuts for the reviewed OEM profile."
                )
        pod = doc.getObject(prefix + "Pod")
        if float(pod.MinimumTilt) != -180 or float(pod.MaximumTilt) != 180:
            raise RuntimeError("Update the review for changed native tilt limits.")
    required = {"PropulsionFixedFrame"}
    obsolete = {"ServoDriveBridge"}
    for prefix, driven, idler in (
        ("Port", "Negative", "Positive"),
        ("Starboard", "Positive", "Negative"),
    ):
        required.update(
            prefix + suffix
            for suffix in (
                "OutputBearingInboard",
                "OutputBearingOutboard",
                "InputBearing",
                "InputShaft",
                "BearingCap",
                "BearingCapInputBolt",
                "BearingCapInputNut",
                "OutputShaft" + driven,
            )
        )
        obsolete.add(prefix + "OutputShaft" + idler)
    if any(doc.getObject(name) is None for name in required) or any(
        doc.getObject(name) is not None for name in obsolete
    ):
        raise RuntimeError(
            "Update the review for changed integrated inboard support topology."
        )
    for prefix in ("Port", "Starboard"):
        assembly = doc.getObject(prefix + "Assembly")
        drive = doc.getObject(prefix + "InputDrive")
        if assembly is None or drive is None:
            raise RuntimeError("Missing fixed input-bearing review hierarchy.")
        for suffix, sku in (
            ("InputBearing", "BEARING_3X6X2_5"),
            ("BearingCapInputBolt", "M2X10_BUTTON_HEAD"),
            ("BearingCapInputNut", "M2_HEX_NUT"),
        ):
            obj = doc.getObject(prefix + suffix)
            if (
                obj.getParentGeoFeatureGroup() != assembly
                or getattr(obj, "HardwareSKU", "") != sku
            ):
                raise RuntimeError(
                    "Input bearing and cap-wing hardware must remain fixed."
                )
        shaft = doc.getObject(prefix + "InputShaft")
        if (
            shaft.getParentGeoFeatureGroup() != drive
            or getattr(shaft, "HardwareSKU", "") != "SS304_CUT3_L35_FLAT16_A0"
        ):
            raise RuntimeError(
                "Update review for changed bearing-supported input shaft."
            )
    REVIEW_MOTION.check_basis(evidence)
    REVIEW_MOTION.check_rotor_service_basis(evidence)


def check_optical_attachment_basis(doc):
    """Bind the optical caption to the selected native attachment and hardware."""
    optical = doc.getObject("OpticalFlowModule")
    stage = doc.getObject("OpticalPitchStage")
    mode = str(getattr(optical, "OpticalAttachmentMode", ""))
    if (
        optical is None
        or stage is None
        or stage.getParentGeoFeatureGroup() != optical
        or mode not in ("rail", "carrier")
    ):
        raise RuntimeError("Update optical review for changed attachment mode.")
    parent = optical.getParentGeoFeatureGroup()
    host_name = side = station = None
    if mode == "rail":
        if (
            parent is not None
            or "RailPositionX" not in optical.PropertiesList
            or any(
                name in optical.PropertiesList
                for name in ("CarrierHostName", "MountSide")
            )
        ):
            raise RuntimeError("Update optical rail review for changed native binding.")
        station = float(optical.RailPositionX)
        if (
            not math.isfinite(station)
            or abs(optical.getGlobalPlacement().Base.x - station) > 1e-7
        ):
            raise RuntimeError("Optical rail position disagrees with native placement.")
        attachment_hardware = {
            "OpticalFlowModuleRailMountScrew": "M3X10_BUTTON_HEAD",
            "OpticalFlowModuleRailMountNut": "M3_HEX_NUT",
        }
        unexpected = (
            "OpticalFootBolt1",
            "OpticalFootNut1",
            "OpticalPitchBolt",
            "OpticalPitchNut",
        )
    else:
        host_name = str(getattr(optical, "CarrierHostName", ""))
        side = str(getattr(optical, "MountSide", ""))
        host = doc.getObject(host_name)
        if (
            host_name
            not in (
                "BatteryEquipmentModule",
                "ElectronicsEquipmentModule",
                "AccessoryEquipmentModule",
            )
            or host is None
            or parent != host
            or side not in ("PositiveX", "NegativeX")
            or "RailPositionX" in optical.PropertiesList
        ):
            raise RuntimeError(
                "Update optical carrier review for changed host binding."
            )
        attachment_hardware = {
            "OpticalFootBolt1": "M2X8_BUTTON_HEAD",
            "OpticalFootNut1": "M2_HEX_NUT",
            "OpticalPitchBolt": "M2X8_BUTTON_HEAD",
            "OpticalPitchNut": "M2_HEX_NUT",
        }
        unexpected = (
            "OpticalFlowModuleRailMountScrew",
            "OpticalFlowModuleRailMountNut",
        )
    if any(doc.getObject(name) is not None for name in unexpected):
        raise RuntimeError("Optical attachment hardware mixes rail and carrier modes.")
    for name, sku in attachment_hardware.items():
        obj = doc.getObject(name)
        if obj is None or getattr(obj, "HardwareSKU", "") != sku:
            raise RuntimeError(f"Expected optical fastener {name}: {sku}.")
    contract = json.loads(optical.OpticalMountContract)
    if (
        contract.get("attachment_mode") != mode
        or contract.get("fixed_ear_thickness_mm") != 2.0
        or contract.get("ear_thickness_mm") != 2.0
        or contract.get("adjustment_degrees_of_freedom")
        != (1 if mode == "carrier" else 0)
        or contract.get("bolt_tip_beyond_nut_mm")
        != (2.9 if mode == "carrier" else None)
    ):
        raise RuntimeError("Update optical pitch review for changed ear/bolt contract.")
    expected_origin = (0, 0, 19) if mode == "carrier" else (-12, 1.25, 6.5)
    limit = 20 if mode == "carrier" else 0
    if (
        doc.getObject("OpticalSensorTray") is None
        or (doc.getObject("OpticalMountBase") is not None) != (mode == "carrier")
        or abs(float(stage.MinimumAngle) + limit) > 1e-8
        or abs(float(stage.MaximumAngle) - limit) > 1e-8
        or any(
            abs(a - b) > 1e-8
            for a, b in zip(stage.Placement.Base, expected_origin, strict=True)
        )
        or (
            mode == "rail"
            and (
                abs(float(stage.Pitch)) > 1e-8
                or not stage.Placement.Rotation.isSame(App.Rotation(), 1e-8)
            )
        )
    ):
        raise RuntimeError("Optical attachment geometry or degrees of freedom changed.")
    return {
        "mode": mode,
        "native_parent": parent.Name if parent is not None else None,
        "host": host_name,
        "side": side,
        "rail_position_x_mm": station,
        "module_origin_cad_mm": list(optical.getGlobalPlacement().Base),
        "adjustment_degrees_of_freedom": 1 if mode == "carrier" else 0,
        "tray_origin_cad_mm": list(stage.getGlobalPlacement().Base),
        "pitch_pivot_cad_mm": list(stage.getGlobalPlacement().Base)
        if mode == "carrier"
        else None,
    }


def optical_review_plan(attachment):
    """Describe manual pitch only when the original pedestal is installed."""
    if attachment["mode"] == "rail":
        return {
            "title": "OPTICAL FIXED TRAY / DIRECT RAIL SHOE",
            "description": "The same upper tray mounts directly with one M3x10 pair at native rail station "
            + f"{attachment['rail_position_x_mm']:g} mm. "
            "The lower pedestal and M2 pitch hardware are absent. This attachment has zero pitch adjustment; its pose stays fixed. Rail trim is not animated. Use the stacked carrier arrangement for manual pitch alignment. Sensor local +Z is the viewing direction.",
            "pitch_points": [(1, 0), (145, 0)],
            "markers": [(1, "Fixed rail tray"), (145, "Fixed rail tray")],
        }
    return {
        "title": "OPTICAL MANUAL PITCH / ORIGINAL CARRIER PEDESTAL",
        "description": "One manual pitch axis +/-20 deg. A shallow tongue and one M2x8 pair fix the original lower pedestal to "
        + attachment["host"]
        + " ("
        + attachment["side"]
        + "); host and side stay fixed. "
        "The extended upper tray retains its unused rail shoe. One M2x8 pair clamps two 2 mm ears, with 2.9 mm nominal tip beyond the nut. Loosen, align and retighten; no roll correction, actuation or self-levelling. Relocation requires renewed populated-device, service and field checks. Sensor local +Z is the viewing direction.",
        "pitch_points": [(1, 0), (37, 20), (73, -20), (109, 20), (145, 0)],
        "markers": [
            (1, "Aligned"),
            (37, "Pitch +20"),
            (73, "Pitch -20"),
            (109, "Pitch +20"),
            (145, "Aligned"),
        ],
    }


def export(cad_path, output):
    with open_validated_cad(
        cad_path,
        output,
        tool_inputs={
            "exporter_sha256": __file__,
            "snapshot_helper_sha256": Path(__file__).resolve().parents[1]
            / "cad_snapshot.py",
            "motion_plan_sha256": Path(__file__).with_name("motion_plan.py"),
        },
    ) as snapshot:
        doc = snapshot.doc
        registry = doc.DesignRegistry
        report = snapshot.report
        check_review_basis(doc, report)
        optical_attachment = check_optical_attachment_basis(doc)
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
                error = check_mesh_placement(obj, mesh)
                max_bound_error = max(max_bound_error, error)
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
        pod_names = {
            prefix: {
                obj.Name
                for obj in objects
                if belongs_to_group(obj, doc.getObject(prefix + "Pod"))
            }
            for prefix in ("Port", "Starboard")
        }
        REVIEW_MOTION.check_rotor_members(pod_names)
        port_detail = [name for name in propulsion if not name.startswith("Starboard")]
        scenes = []

        def reset():
            doc.PortPod.Tilt = doc.StarboardPod.Tilt = 0
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
            "Nominal CAD assembly; propeller disks are swept envelopes. Both servos use the manufacturer stock plastic half arm 1, with unmodified factory holes and rear M1x6 hex bolts/front M1 nuts. The adapter has one near round hole and two radial slots; only the end bolts are installed. Resin, mass, installed seating and assembled runout remain unmeasured.",
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
            "48T driver / 16T driven: input -60..+60 deg, output +180..-180 deg. Each35mm input shaft has a16mm proximal flat and a round journal through its fixed external bearing. One common cap retains that bearing and the two output bearings; three screws seat the cap on hard lands. Manufacturer stock plastic half arm 1 retains its unmodified source geometry; rear M1x6 hex bolts and front nuts clamp the round-hole/slot adapter after alignment. Installed fit and bearing load sharing remain unverified. Gear teeth are reference geometry; no backlash/contact simulation.",
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
            [[-8, 18, 35], [38, 57, 62]],
            REVIEW_MOTION.axial_markers(),
            endplay,
        )

        optical_plan = optical_review_plan(optical_attachment)

        def optical(frame):
            pitch = curve(frame, optical_plan["pitch_points"])
            optical_mount.set_pitch(doc, pitch)
            return {}, set()

        origin = doc.OpticalFlowModule.getGlobalPlacement().Base
        scene(
            "05 Optical attachment",
            optical_plan["title"],
            optical_plan["description"],
            145,
            all_names,
            [[origin.x - 35, origin.y - 30, 0], [origin.x + 35, origin.y + 30, 80]],
            optical_plan["markers"],
            optical,
        )

        scene(
            "06 Rotor removal",
            "OPEN OUTER ROTOR / SHAFT WITHDRAWAL",
            REVIEW_MOTION.rotor_service_description(),
            REVIEW_MOTION.rotor_service_frames,
            propulsion,
            [[-25, -101, 0], [65, 160, 100]],
            REVIEW_MOTION.rotor_service_markers(),
            REVIEW_MOTION.rotor_service_pose,
        )

        result = {
            "metadata": {
                "cad_path": str(snapshot.cad_path),
                **snapshot.provenance(),
                **snapshot.tool_hashes,
                "revision": report["revision"],
                "units": "mm",
                "fps": 24,
                "part_count": len(parts),
                "excluded_fit_samples": sorted(obj.Name for obj in registry.FitCoupons),
                "installed_representation": "Installed round-hole/slot adapters and manufacturer stock plastic half-arm geometry without hole enlargement are displayed, including rear M1x6 hex bolts and front M1 nuts. Fit samples and clearance reservations are excluded. Nominal source geometry does not establish resin, mass, delivered fit or installed seating.",
                "mesh_max_bounds_error_mm": max_bound_error,
                "service_animation_included": True,
                "animated_service_scope": "Output rotor and its locked output shaft only; input-shaft and servo service are not animated.",
                "input_service_animation_included": False,
                "optical_attachment": optical_attachment,
                "optical_rail_trim_animation_included": False,
                "checked_input_service": REVIEW_MOTION.input_service_summary(
                    report["local_propulsion_evidence"]
                ),
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
