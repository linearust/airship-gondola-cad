"""Saved factory-horn geometry must not masquerade as physically measured fit."""

import tempfile
import unittest
from pathlib import Path

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class HornRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.directory = tempfile.TemporaryDirectory()
        path = Path(cls.directory.name) / "horn_registration.FCStd"
        doc = App.newDocument("HornRegistrationSource")
        propulsion.build_propulsion_module(doc)
        propulsion.build_fit_coupons(doc)
        doc.recompute()
        doc.saveAs(str(path))
        App.closeDocument(doc.Name)
        cls.doc = App.openDocument(str(path), hidden=True)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)
        cls.directory.cleanup()

    def test_saved_factory_joints_follow_both_drives_without_claiming_physical_fit(
        self,
    ):
        from gondola.validation.horn_coupling import horn_registration_check

        module = self.doc.MainPropulsionModule
        placement = module.Placement.copy()
        try:
            module.Placement = App.Placement(
                App.Vector(31, -8, 4), App.Rotation(App.Vector(1, 2, 3), 23)
            )
            for prefix in ("Port", "Starboard"):
                pod = self.doc.getObject(prefix + "Pod")
                original = float(pod.Tilt)
                try:
                    for angle in (-180, 0, 105):
                        pod.Tilt = angle
                        self.doc.recompute()
                        result = horn_registration_check(self.doc, prefix)
                        self.assertTrue(result["passed"], result)
                        self.assertFalse(result["physical_concentricity_verified"])
                        self.assertTrue(
                            result["purchased_horn_measurement_explicitly_unknown"]
                        )
                        self.assertEqual(result["profile"], "KST_X06_HALF_ARM_1")
                        self.assertTrue(result["manufacturer_geometry_matches"])
                        self.assertTrue(result["axial_seating_explicitly_unmeasured"])
                        self.assertFalse(result["factory_m1_6_threads_confirmed"])
                        self.assertTrue(result["preparation_required"])
                        self.assertEqual(len(result["joints"]), 2)
                        self.assertTrue(
                            all(
                                joint["separate_nut_required"]
                                for joint in result["joints"]
                            )
                        )
                        self.assertEqual(len(result["register_directional_stops"]), 3)
                        self.assertFalse(result["obsolete_horn_parts"])
                finally:
                    pod.Tilt = original
        finally:
            module.Placement = placement
            self.doc.recompute()

    def test_changed_export_cannot_restore_an_undrilled_print_blank(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortHornGearAdapter
        self.assertFalse(hasattr(obj, "PrintBlankShape"))
        try:
            obj.addProperty(
                "Part::PropertyPartShape", "PrintBlankShape", "Manufacturing"
            )
            plug = Part.makeCylinder(
                1.1,
                2,
                App.Vector(6.8, c.HORN_BOTTOM_Y + c.HORN_HEIGHT, 0),
                App.Vector(0, 1, 0),
            )
            obj.PrintBlankShape = obj.Shape.fuse(plug)
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["print_export_difference_mm3"], 1)
        finally:
            obj.removeProperty("PrintBlankShape")

    def test_shifted_adapter_axis_is_rejected(self):
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortHornGearAdapter
        original = obj.Placement.copy()
        try:
            obj.Placement.Base += App.Vector(0.1, 0, 0)
            self.doc.recompute()
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["adapter_difference_mm3"], 1)
        finally:
            obj.Placement = original
            self.doc.recompute()

    def test_missing_second_installed_screw_does_not_pass(self):
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortHornGearClampFarBolt
        original = obj.Shape.copy()
        try:
            obj.Shape = self.doc.PortHornGearClampNearBolt.Shape.copy()
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(
                result["joints"][1]["nominal_fastener_difference_mm3"], 1
            )
        finally:
            obj.Shape = original

    def test_removed_root_register_is_detected(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortHornGearAdapter
        original = obj.Shape.copy()
        try:
            cutter = Part.makeBox(
                20,
                c.REGISTER_ENGAGEMENT + 0.1,
                20,
                App.Vector(-10, c.HORN_BOTTOM_Y + c.BODY_BACK_Y - 0.1, -10),
            )
            obj.Shape = original.cut(cutter).removeSplitter()
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertTrue(
                all(not row["passed"] for row in result["register_directional_stops"])
            )
        finally:
            obj.Shape = original

    def test_unmeasured_purchased_horn_cannot_be_marked_as_measured(self):
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortServoHorn
        original = obj.PurchasedHornMeasured
        try:
            obj.PurchasedHornMeasured = True
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertFalse(result["physical_concentricity_verified"])
        finally:
            obj.PurchasedHornMeasured = original

    def test_wrong_second_front_nut_is_detected(self):
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortHornGearClampFarNut
        original = obj.Shape.copy()
        try:
            obj.Shape = self.doc.PortHornGearClampNearNut.Shape.copy()
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(
                result["joints"][1]["nominal_fastener_difference_mm3"], 1
            )
        finally:
            obj.Shape = original

    def test_missing_or_wrong_manufacturer_geometry_provenance_is_rejected(self):
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortServoHorn
        self.assertTrue(obj.ManufacturerGeometryProvided)
        self.assertEqual(
            obj.ManufacturerGeometrySHA256,
            "ea9ad94160411df4c32e495eda85f75a43bcfcb379a86b113ad6e03c8aa79c81",
        )
        for name, wrong in (
            ("ManufacturerGeometryProvided", False),
            ("ManufacturerGeometrySHA256", "0" * 64),
        ):
            with self.subTest(property=name):
                original = getattr(obj, name)
                try:
                    setattr(obj, name, wrong)
                    result = horn_registration_check(self.doc, "Port")
                    self.assertFalse(result["passed"], result)
                    self.assertFalse(result["manufacturer_geometry_matches"])
                finally:
                    setattr(obj, name, original)


if __name__ == "__main__":
    unittest.main()
