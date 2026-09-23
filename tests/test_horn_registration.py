"""Saved machining examples cannot masquerade as measured supplied-horn fits."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_saved_examples_follow_both_drives_without_claiming_physical_fit(self):
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
                            result["supplied_horn_measurement_explicitly_unknown"]
                        )
                        self.assertEqual(len(result["joints"]), 2)
                        self.assertEqual(len(result["jig_working_range"]), 3)
                finally:
                    pod.Tilt = original
        finally:
            module.Placement = placement
            self.doc.recompute()

    def test_prepared_holes_cannot_silently_become_the_print_blank(self):
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortHornGearAdapter
        original = obj.PrintBlankShape.copy()
        try:
            obj.PrintBlankShape = obj.Shape.copy()
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["print_blank_difference_mm3"], 100)
            self.assertLess(result["material_removed_by_preparation_mm3"], 1e-7)
        finally:
            obj.PrintBlankShape = original

    def test_shifted_prepared_axis_is_rejected(self):
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortHornGearAdapter
        original = obj.Placement.copy()
        try:
            obj.Placement.Base += App.Vector(0.1, 0, 0)
            self.doc.recompute()
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["prepared_example_difference_mm3"], 1)
        finally:
            obj.Placement = original
            self.doc.recompute()

    def test_a_missing_second_installed_joint_does_not_pass(self):
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortHornGearClampFarBolt
        original = obj.Shape.copy()
        try:
            obj.Shape = self.doc.PortHornGearClampNearBolt.Shape.copy()
            self.doc.recompute()
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            # Exact second-hole geometry alone cannot stand in for its bolt.
            far = result["joints"][1]
            self.assertTrue(far["prepared_passage_blockage_mm3"] < 1e-7)
        finally:
            obj.Shape = original
            self.doc.recompute()

    def test_jig_nose_offset_is_rejected_in_saved_geometry(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.HornCenteringJig
        original = obj.Shape.copy()
        try:
            cutter = Part.makeBox(10, c.JIG_GUIDE_START_Y, 10, App.Vector(-5, 0, -5))
            nose = original.common(cutter)
            body = original.cut(cutter)
            nose.translate(App.Vector(0.2, 0, 0))
            obj.Shape = body.fuse(nose).removeSplitter()
            self.assertTrue(obj.Shape.isValid())
            self.assertEqual(len(obj.Shape.Solids), 1)
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["jig_difference_mm3"], 0.1)
            self.assertTrue(
                any(not row["passed"] for row in result["jig_working_range"])
            )
        finally:
            obj.Shape = original

    def test_jig_checks_follow_declared_working_range_and_reject_an_oversize_entry(
        self,
    ):
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import horn_registration_check

        for limits, expected, passed in (
            ((0.9, 1.5), (0.9, 1.2, 1.5), True),
            ((0.8, 2.0), (0.8, 1.4, 2.0), False),
        ):
            with (
                self.subTest(limits=limits),
                patch.object(c, "JIG_ACCEPTED_ENTRY_DIAMETERS", limits),
            ):
                result = horn_registration_check(self.doc, "Port")
                self.assertEqual(result["passed"], passed, result)
                for row, diameter in zip(result["jig_working_range"], expected):
                    self.assertAlmostEqual(row["synthetic_entry_diameter_mm"], diameter)
                if not passed:
                    self.assertFalse(result["jig_working_range"][-1]["passed"])

    def test_filled_guide_passage_is_rejected(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortHornGearAdapter
        original = obj.Shape.copy()
        try:
            plug = Part.makeCylinder(
                1.3,
                1.5,
                App.Vector(0, c.HORN_BOTTOM_Y + c.OEM_HEAD_CAVITY_TOP_Y, 0),
                App.Vector(0, 1, 0),
            )
            obj.Shape = original.fuse(plug).removeSplitter()
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["material_added_by_preparation_mm3"], 1)
            self.assertTrue(
                any(
                    row["adapter_overlap_mm3"] > 0.1
                    for row in result["jig_working_range"]
                )
            )
        finally:
            obj.Shape = original

    def test_source_example_cannot_be_marked_as_measured_purchased_horn(self):
        from gondola.validation.horn_coupling import horn_registration_check

        obj = self.doc.PortServoHorn
        original = obj.SuppliedHornMeasured
        try:
            obj.SuppliedHornMeasured = True
            result = horn_registration_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertFalse(result["physical_concentricity_verified"])
        finally:
            obj.SuppliedHornMeasured = original


if __name__ == "__main__":
    unittest.main()
