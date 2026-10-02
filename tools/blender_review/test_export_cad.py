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
    check_optical_carrier_basis,
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
    def optical_basis():
        host = SimpleNamespace(Name="BatteryEquipmentModule")
        optical = SimpleNamespace(
            CarrierHostName=host.Name,
            MountSide="PositiveX",
            PropertiesList=["CarrierHostName", "MountSide"],
            getParentGeoFeatureGroup=lambda: host,
        )
        objects = {host.Name: host, "OpticalFlowModule": optical}
        for prefix in ("OpticalFoot", "OpticalPitch"):
            for index in ("1",) if prefix == "OpticalFoot" else ("",):
                for kind, sku in (("Bolt", "M2X8_BUTTON_HEAD"), ("Nut", "M2_HEX_NUT")):
                    objects[prefix + kind + index] = SimpleNamespace(HardwareSKU=sku)
        return SimpleNamespace(getObject=objects.get), objects

    def test_native_carrier_optical_attachment_matches_review(self):
        import FreeCAD as App

        from gondola.parts import optical_mount

        doc = App.newDocument("BlenderOpticalCarrierReview")
        try:
            host = doc.addObject("App::Part", "BatteryEquipmentModule")
            optical_mount.build_optical_mount(doc, host)
            self.assertEqual(
                check_optical_carrier_basis(doc),
                {"host": "BatteryEquipmentModule", "side": "PositiveX"},
            )
            doc.OpticalFlowModule.MountSide = "NegativeX"
            doc.recompute()
            self.assertEqual(check_optical_carrier_basis(doc)["side"], "NegativeX")
        finally:
            App.closeDocument(doc.Name)

    def test_wrong_optical_binding_and_legacy_rail_control_are_rejected(self):
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
                    check_optical_carrier_basis(doc)

    def test_each_optical_foot_and_pitch_fastener_is_required(self):
        for name in (
            "OpticalFootBolt1",
            "OpticalPitchBolt",
            "OpticalFootNut1",
            "OpticalPitchNut",
        ):
            for missing in (False, True):
                with self.subTest(name=name, missing=missing):
                    doc, objects = self.optical_basis()
                    if missing:
                        del objects[name]
                    else:
                        objects[name].HardwareSKU = "WrongFastener"
                    with self.assertRaisesRegex(RuntimeError, "Expected two M2"):
                        check_optical_carrier_basis(doc)

    @staticmethod
    def basis():
        objects = {}
        for prefix in ("Port", "Starboard"):
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
