"""Bounded export-contract checks; run with native FreeCAD's Python runtime."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.blender_review import export_cad
from tools.blender_review.export_cad import (
    check_mesh_placement,
    check_optical_attachment_basis,
    check_review_basis,
    representation,
    review_objects,
)
from tools.blender_review.test_motion_plan import native_evidence


class MeshPlacementTests(unittest.TestCase):
    def saved_rounded_mount(self):
        import FreeCAD as App
        import MeshPart

        from gondola.parts import equipment_mounts

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "rounded_mount.FCStd"
        doc = App.newDocument("RoundedMeshPlacement")
        try:
            root = doc.addObject("App::Part", "Root")
            carrier = doc.addObject("App::Part", "Carrier")
            root.addObject(carrier)
            obj = doc.addObject("Part::Feature", "RoundedMount")
            carrier.addObject(obj)
            obj.Shape = equipment_mounts.mount_shape("battery")
            obj.Placement.Base = App.Vector(13, -7, 5)
            doc.recompute()
            doc.saveAs(str(path))
        finally:
            App.closeDocument(doc.Name)
        doc = App.openDocument(str(path), hidden=True)
        self.addCleanup(App.closeDocument, doc.Name)
        shape = doc.RoundedMount.Shape.copy()
        shape.Placement = App.Placement()
        mesh = MeshPart.meshFromShape(
            Shape=shape,
            LinearDeflection=0.04,
            AngularDeflection=0.12,
            Relative=False,
        )
        return doc, mesh

    def test_rounded_saved_mesh_uses_trimmed_bounds_and_nested_placements(self):
        import FreeCAD as App

        from gondola.cad import world_shape

        doc, mesh = self.saved_rounded_mount()
        obj = doc.RoundedMount
        placed = mesh.copy()
        placed.transform(obj.getGlobalPlacement().toMatrix())
        loose = world_shape(obj).BoundBox
        loose_error = max(
            abs(getattr(placed.BoundBox, key) - getattr(loose, key))
            for key in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
        )
        self.assertGreater(loose_error, 0.08)
        self.assertLess(check_mesh_placement(obj, mesh), 0.01)
        doc.Root.Placement = App.Placement(
            App.Vector(71, -39, 26), App.Rotation(App.Vector(2, -3, 5), 37)
        )
        doc.Carrier.Placement = App.Placement(
            App.Vector(-11, 8, 17), App.Rotation(App.Vector(4, 1, -2), -23)
        )
        doc.recompute()
        self.assertLess(check_mesh_placement(obj, mesh), 0.08)

    def test_shifted_mesh_is_still_rejected_with_nested_parent_placement(self):
        import FreeCAD as App

        doc, mesh = self.saved_rounded_mount()
        doc.Root.Placement = App.Placement(
            App.Vector(71, -39, 26), App.Rotation(App.Vector(2, -3, 5), 37)
        )
        doc.Carrier.Placement.Base = App.Vector(-11, 8, 17)
        doc.recompute()
        self.assertLess(check_mesh_placement(doc.RoundedMount, mesh), 0.08)
        mesh.transform(App.Placement(App.Vector(0.25, 0, 0), App.Rotation()).toMatrix())
        with self.assertRaisesRegex(RuntimeError, "Mesh placement mismatch"):
            check_mesh_placement(doc.RoundedMount, mesh)


class ExportContractTests(unittest.TestCase):
    def test_export_rejects_input_paths_before_opening_the_document(self):
        with tempfile.TemporaryDirectory() as folder:
            cad = Path(folder) / "saved.FCStd"
            report = Path(folder) / "saved_validation.json"
            cad.write_bytes(b"native CAD sentinel")
            report.write_bytes(b"validation sentinel")
            originals = {path: path.read_bytes() for path in (cad, report)}
            with patch.object(export_cad.App, "openDocument") as open_document:
                for output in (cad, report):
                    with (
                        self.subTest(output=output),
                        self.assertRaisesRegex(ValueError, "separate JSON"),
                    ):
                        export_cad.export(cad, output)
                open_document.assert_not_called()
            for path, contents in originals.items():
                self.assertEqual(path.read_bytes(), contents)

    @staticmethod
    def optical_basis(mode="carrier"):
        import FreeCAD as App

        host = SimpleNamespace(Name="BatteryEquipmentModule")
        optical = SimpleNamespace(
            OpticalAttachmentMode=mode,
            OpticalMountContract=json.dumps(
                {
                    "attachment_mode": mode,
                    "fixed_ear_thickness_mm": 3.0,
                    "ear_thickness_mm": 2.0,
                    "bolt_tip_beyond_nut_mm": 1.9,
                }
            ),
            PropertiesList=["OpticalAttachmentMode"],
        )
        if mode == "carrier":
            optical.CarrierHostName = host.Name
            optical.MountSide = "PositiveX"
            optical.PropertiesList += ["CarrierHostName", "MountSide"]
            optical.getParentGeoFeatureGroup = lambda: host
            origin = App.Vector(27, 0, 19)
            hardware = {
                "OpticalFootBolt1": "M2X8_BUTTON_HEAD",
                "OpticalFootNut1": "M2_HEX_NUT",
            }
        else:
            optical.RailPositionX = 140
            optical.PropertiesList += ["RailPositionX"]
            optical.getParentGeoFeatureGroup = lambda: None
            origin = App.Vector(140, 0, 0)
            hardware = {
                "OpticalFlowModuleRailMountScrew": "M3X10_BUTTON_HEAD",
                "OpticalFlowModuleRailMountNut": "M3_HEX_NUT",
            }
        optical.getGlobalPlacement = lambda: App.Placement(origin, App.Rotation())
        stage = SimpleNamespace(
            getParentGeoFeatureGroup=lambda: optical,
            getGlobalPlacement=lambda: App.Placement(
                App.Vector(origin.x, 0, 42), App.Rotation()
            ),
        )
        objects = {
            host.Name: host,
            "OpticalFlowModule": optical,
            "OpticalPitchStage": stage,
        }
        for name, sku in {
            **hardware,
            "OpticalPitchBolt": "M2X8_BUTTON_HEAD",
            "OpticalPitchNut": "M2_HEX_NUT",
        }.items():
            objects[name] = SimpleNamespace(HardwareSKU=sku)
        return SimpleNamespace(getObject=objects.get), objects

    def test_native_optical_modes_and_saved_parent_match_review(self):
        import FreeCAD as App

        from gondola.parts import optical_mount, rail

        for mode in ("rail", "carrier"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "optical.FCStd"
                doc = App.newDocument("BlenderOpticalAttachmentReview")
                try:
                    if mode == "carrier":
                        host = doc.addObject("App::Part", "BatteryEquipmentModule")
                        host.Placement.Base.x = 84
                        optical_mount.build_optical_mount(doc, host)
                        doc.OpticalFlowModule.MountSide = "NegativeX"
                    else:
                        group = optical_mount.build_optical_mount(doc, mode="rail")[
                            "group"
                        ]
                        group.addProperty("App::PropertyLength", "RailPositionX")
                        group.RailPositionX = 140
                        group.setExpression("Placement.Base.x", "RailPositionX")
                        rail.build_attachment_hardware(doc, group, group.Name)
                    doc.recompute()
                    expected = check_optical_attachment_basis(doc)
                    self.assertEqual(expected["mode"], mode)
                    self.assertEqual(
                        expected["pitch_pivot_cad_mm"],
                        [140, 0, 42] if mode == "rail" else [57, 0, 42],
                    )
                    self.assertEqual(
                        expected["native_parent"],
                        None if mode == "rail" else "BatteryEquipmentModule",
                    )
                    self.assertEqual(
                        expected["rail_position_x_mm"], 140 if mode == "rail" else None
                    )
                    self.assertEqual(
                        expected["side"], None if mode == "rail" else "NegativeX"
                    )
                    doc.saveAs(str(path))
                finally:
                    App.closeDocument(doc.Name)
                doc = App.openDocument(str(path), hidden=True)
                try:
                    self.assertEqual(check_optical_attachment_basis(doc), expected)
                finally:
                    App.closeDocument(doc.Name)

    def test_wrong_carrier_binding_and_mixed_rail_control_are_rejected(self):
        for field, value in (
            ("CarrierHostName", "ElectronicsEquipmentModule"),
            ("MountSide", "InvalidSide"),
            ("getParentGeoFeatureGroup", lambda: None),
            ("PropertiesList", ["CarrierHostName", "MountSide", "RailPositionX"]),
        ):
            with self.subTest(field=field):
                doc, objects = self.optical_basis()
                setattr(objects["OpticalFlowModule"], field, value)
                with self.assertRaisesRegex(RuntimeError, "host binding"):
                    check_optical_attachment_basis(doc)

    def test_wrong_rail_parent_controls_and_station_are_rejected(self):
        for field, value in (
            (
                "getParentGeoFeatureGroup",
                lambda: SimpleNamespace(Name="BatteryEquipmentModule"),
            ),
            ("PropertiesList", ["OpticalAttachmentMode"]),
            ("PropertiesList", ["RailPositionX", "CarrierHostName"]),
            ("RailPositionX", 139),
        ):
            with self.subTest(field=field):
                doc, objects = self.optical_basis("rail")
                setattr(objects["OpticalFlowModule"], field, value)
                with self.assertRaisesRegex(
                    RuntimeError, "native binding|native placement"
                ):
                    check_optical_attachment_basis(doc)

    def test_each_mode_requires_its_attachment_and_pitch_fasteners(self):
        for mode, names in (
            ("carrier", ("OpticalFootBolt1", "OpticalFootNut1")),
            (
                "rail",
                ("OpticalFlowModuleRailMountScrew", "OpticalFlowModuleRailMountNut"),
            ),
        ):
            for name in (*names, "OpticalPitchBolt", "OpticalPitchNut"):
                for missing in (False, True):
                    with self.subTest(mode=mode, name=name, missing=missing):
                        doc, objects = self.optical_basis(mode)
                        if missing:
                            del objects[name]
                        else:
                            objects[name].HardwareSKU = "WrongFastener"
                        with self.assertRaisesRegex(
                            RuntimeError, "Expected optical fastener"
                        ):
                            check_optical_attachment_basis(doc)

    def test_mixed_hardware_or_stale_pitch_contract_is_rejected(self):
        for mode, wrong_name in (
            ("rail", "OpticalFootBolt1"),
            ("carrier", "OpticalFlowModuleRailMountScrew"),
        ):
            doc, objects = self.optical_basis(mode)
            objects[wrong_name] = SimpleNamespace(HardwareSKU="M2X8_BUTTON_HEAD")
            with (
                self.subTest(mode=mode),
                self.assertRaisesRegex(RuntimeError, "mixes rail and carrier"),
            ):
                check_optical_attachment_basis(doc)
        for field, value in (
            ("attachment_mode", "rail"),
            ("fixed_ear_thickness_mm", 2.0),
            ("ear_thickness_mm", 3.0),
            ("bolt_tip_beyond_nut_mm", 2.9),
        ):
            doc, objects = self.optical_basis("carrier")
            contract = json.loads(objects["OpticalFlowModule"].OpticalMountContract)
            contract[field] = value
            objects["OpticalFlowModule"].OpticalMountContract = json.dumps(contract)
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(RuntimeError, "ear/bolt contract"),
            ):
                check_optical_attachment_basis(doc)

    @staticmethod
    def basis():
        objects = {}
        for prefix in ("Port", "Starboard"):
            assembly = SimpleNamespace(Name=prefix + "Assembly")
            drive = SimpleNamespace(Name=prefix + "InputDrive")
            objects[assembly.Name] = assembly
            objects[drive.Name] = drive
            for suffix, sku in (
                ("InputBearing", "BEARING_3X6X2_5"),
                ("BearingCapInputBolt", "M2X10_BUTTON_HEAD"),
                ("BearingCapInputNut", "M2_HEX_NUT"),
            ):
                objects[prefix + suffix] = SimpleNamespace(
                    Name=prefix + suffix,
                    HardwareSKU=sku,
                    getParentGeoFeatureGroup=lambda parent=assembly: parent,
                )
            objects[prefix + "InputShaft"] = SimpleNamespace(
                Name=prefix + "InputShaft",
                HardwareSKU="SS304_CUT3_L35_FLAT16_A0",
                getParentGeoFeatureGroup=lambda parent=drive: parent,
            )
            objects[prefix + "Pod"] = SimpleNamespace(MinimumTilt=-180, MaximumTilt=180)
            objects[prefix + "ServoHorn"] = SimpleNamespace(
                HardwareSKU="KST_X06_STOCK_HALF_ARM_1",
                HornProfile="KST_X06_HALF_ARM_1",
                ManufacturerGeometryProvided=True,
                ManufacturerGeometrySHA256="ea9ad94160411df4c32e495eda85f75a43bcfcb379a86b113ad6e03c8aa79c81",
                HornPreparationRequired=False,
                FactoryThreadedHoles=False,
                PurchasedHornMeasured=False,
                AxialSeatingMeasured=False,
                HornInterfaceContract=json.dumps(
                    {
                        "profile": "KST_X06_HALF_ARM_1",
                        "manufacturer_geometry_sha256": "ea9ad94160411df4c32e495eda85f75a43bcfcb379a86b113ad6e03c8aa79c81",
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
                ),
            )
            objects[prefix + "HornGearAdapter"] = SimpleNamespace(
                Name=prefix + "HornGearAdapter"
            )
            for position in ("Near", "Far"):
                objects[prefix + "HornGearClamp" + position + "Bolt"] = SimpleNamespace(
                    HardwareSKU="M1X6_HEX_HEAD"
                )
                objects[prefix + "HornGearClamp" + position + "Nut"] = SimpleNamespace(
                    HardwareSKU="M1_HEX_NUT"
                )
        for name in (
            "PropulsionFixedFrame",
            "PortOutputBearingInboard",
            "PortOutputBearingOutboard",
            "StarboardOutputBearingInboard",
            "StarboardOutputBearingOutboard",
            "PortBearingCap",
            "StarboardBearingCap",
            "PortOutputShaftNegative",
            "StarboardOutputShaftPositive",
        ):
            objects[name] = SimpleNamespace(Name=name)
        report = {
            "gear_configuration": "48_16",
            "local_propulsion_evidence": native_evidence(),
        }
        return SimpleNamespace(getObject=objects.get), objects, report

    def test_current_oem_preparation_and_fastening_are_supported(self):
        doc, objects, report = self.basis()
        check_review_basis(doc, report)
        self.assertIn("plastic half arm 1", representation(objects["PortServoHorn"]))
        self.assertIn(
            "round-hole/slot adapter",
            representation(objects["PortHornGearAdapter"]),
        )
        self.assertIn("rear M1x6", representation(objects["PortHornGearAdapter"]))
        self.assertIn("front M1 nuts", representation(objects["PortHornGearAdapter"]))
        self.assertIn("diameter 1.2 mm", representation(objects["PortHornGearAdapter"]))
        self.assertIn("1.2 x 1.8 mm", representation(objects["PortHornGearAdapter"]))
        self.assertNotIn("undrilled", representation(objects["PortHornGearAdapter"]))

    def test_old_looser_horn_dimensions_cannot_reuse_the_review_basis(self):
        for prefix in ("Port", "Starboard"):
            doc, objects, report = self.basis()
            horn = objects[prefix + "ServoHorn"]
            contract = json.loads(horn.HornInterfaceContract)
            contract.update(
                adapter_round_hole_diameter_mm=1.8,
                adapter_slot_width_mm=1.8,
                adapter_slot_overall_length_mm=2.4,
            )
            horn.HornInterfaceContract = json.dumps(contract)
            with self.assertRaisesRegex(RuntimeError, "OEM horn dimensions"):
                check_review_basis(doc, report)

    def test_native_oem_module_metadata_matches_the_review_basis(self):
        import FreeCAD as App

        from gondola.parts import propulsion

        doc = App.newDocument("BlenderOEMReviewBasis")
        try:
            propulsion.build_propulsion_module(doc)
            doc.recompute()
            _, _, report = self.basis()
            check_review_basis(doc, report)
        finally:
            App.closeDocument(doc.Name)

    def test_missing_or_changed_rear_bolts_and_front_nuts_are_rejected(self):
        for prefix in ("Port", "Starboard"):
            for position in ("Near", "Far"):
                for kind, message in (("Bolt", "rear M1x6"), ("Nut", "front M1")):
                    for missing in (False, True):
                        with self.subTest(
                            side=prefix, joint=position, kind=kind, missing=missing
                        ):
                            doc, objects, report = self.basis()
                            name = prefix + "HornGearClamp" + position + kind
                            if missing:
                                del objects[name]
                            else:
                                objects[name].HardwareSKU = "UNSUPPORTED_FASTENER"
                            with self.assertRaisesRegex(RuntimeError, message):
                                check_review_basis(doc, report)

    def test_changed_horn_identity_or_manufacturing_blank_is_rejected(self):
        for prefix in ("Port", "Starboard"):
            for field, value in (
                ("HardwareSKU", "UNSUPPORTED_HORN_SKU"),
                ("HornProfile", "UNSUPPORTED_HORN_PROFILE"),
            ):
                with self.subTest(side=prefix, field=field):
                    doc, objects, report = self.basis()
                    setattr(objects[prefix + "ServoHorn"], field, value)
                    with self.assertRaisesRegex(RuntimeError, "purchased-horn"):
                        check_review_basis(doc, report)
            doc, objects, report = self.basis()
            objects[prefix + "HornGearAdapter"].PrintBlankShape = object()
            with self.assertRaisesRegex(RuntimeError, "purchased-horn"):
                check_review_basis(doc, report)

    def test_missing_or_changed_oem_provenance_and_measurement_claims_are_rejected(
        self,
    ):
        for prefix in ("Port", "Starboard"):
            for field, wrong in (
                ("ManufacturerGeometryProvided", False),
                ("ManufacturerGeometrySHA256", "0" * 64),
                ("HornPreparationRequired", True),
                ("FactoryThreadedHoles", True),
                ("PurchasedHornMeasured", True),
                ("AxialSeatingMeasured", True),
            ):
                for missing in (False, True):
                    with self.subTest(side=prefix, field=field, missing=missing):
                        doc, objects, report = self.basis()
                        horn = objects[prefix + "ServoHorn"]
                        if missing:
                            delattr(horn, field)
                        else:
                            setattr(horn, field, wrong)
                        with self.assertRaisesRegex(
                            RuntimeError, "OEM horn provenance"
                        ):
                            check_review_basis(doc, report)

    def test_missing_or_changed_horn_contract_cannot_reuse_captions(self):
        for prefix in ("Port", "Starboard"):
            doc, objects, report = self.basis()
            horn = objects[prefix + "ServoHorn"]
            contract = json.loads(horn.HornInterfaceContract)
            for key in contract:
                with self.subTest(side=prefix, key=key):
                    horn.HornInterfaceContract = json.dumps({**contract, key: None})
                    with self.assertRaisesRegex(RuntimeError, "OEM horn dimensions"):
                        check_review_basis(doc, report)
            for value in ("invalid json", "null", "[]", None):
                with self.subTest(side=prefix, value=value):
                    horn.HornInterfaceContract = value
                    with self.assertRaisesRegex(RuntimeError, "OEM horn"):
                        check_review_basis(doc, report)
            del horn.HornInterfaceContract
            with self.assertRaisesRegex(RuntimeError, "OEM horn"):
                check_review_basis(doc, report)

    def test_changed_motion_cannot_reuse_presentation_poses(self):
        doc, _, report = self.basis()
        report["local_propulsion_evidence"]["saved_carrier_metal_clearances"][0][
            "axial_travel"
        ]["positive_mm"] = 0.6
        with self.assertRaisesRegex(RuntimeError, "axial-travel poses"):
            check_review_basis(doc, report)

    def test_missing_new_supports_and_returned_saddle_or_idler_are_rejected(self):
        for name in (
            "PropulsionFixedFrame",
            "PortOutputBearingInboard",
            "PortInputBearing",
            "StarboardInputShaft",
            "PortBearingCapInputBolt",
            "StarboardOutputBearingOutboard",
            "PortBearingCap",
            "StarboardOutputShaftPositive",
        ):
            with self.subTest(missing=name):
                doc, objects, report = self.basis()
                del objects[name]
                with self.assertRaisesRegex(RuntimeError, "inboard support topology"):
                    check_review_basis(doc, report)

        for name in (
            "ServoDriveBridge",
            "PortOutputShaftPositive",
            "StarboardOutputShaftNegative",
        ):
            with self.subTest(obsolete=name):
                doc, objects, report = self.basis()
                objects[name] = SimpleNamespace(Name=name)
                with self.assertRaisesRegex(RuntimeError, "inboard support topology"):
                    check_review_basis(doc, report)

    def test_input_bearing_and_cap_wing_hardware_cannot_join_rotating_group(self):
        for suffix in ("InputBearing", "BearingCapInputBolt", "BearingCapInputNut"):
            with self.subTest(part=suffix):
                doc, objects, report = self.basis()
                objects["Port" + suffix].getParentGeoFeatureGroup = lambda: objects[
                    "PortInputDrive"
                ]
                with self.assertRaisesRegex(RuntimeError, "must remain fixed"):
                    check_review_basis(doc, report)

    def test_fit_samples_and_clearance_proxies_cannot_enter_installed_review(self):
        body, coupon, reserve = [
            SimpleNamespace(Name=name)
            for name in ("PortHornGearAdapter", "BearingCupCoupon", "WireReserve")
        ]
        registry = SimpleNamespace(
            PrintedParts=[body],
            HardwareParts=[],
            ReferenceParts=[],
            TapeReferences=[],
            FitCoupons=[coupon],
            ClearanceVolumes=[reserve],
        )
        self.assertEqual(review_objects(registry), [body])
        for leaked in (coupon, reserve):
            registry.ReferenceParts = [leaked]
            with self.assertRaisesRegex(RuntimeError, "bench fit sample or clearance"):
                review_objects(registry)

    def test_returned_spacer_requires_an_explicit_caption_revision(self):
        old = SimpleNamespace(Name="PortOutputBearingSpacerNegative")
        registry = SimpleNamespace(
            PrintedParts=[],
            HardwareParts=[old],
            ReferenceParts=[],
            TapeReferences=[],
            FitCoupons=[],
            ClearanceVolumes=[],
        )
        with self.assertRaisesRegex(RuntimeError, "axial-travel caption"):
            review_objects(registry)


if __name__ == "__main__":
    unittest.main()
