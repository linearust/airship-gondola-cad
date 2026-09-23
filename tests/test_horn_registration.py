"""A clamping bolt must not conceal missing gear-centering datums."""

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
        doc.recompute()
        doc.saveAs(str(path))
        App.closeDocument(doc.Name)
        cls.doc = App.openDocument(str(path), hidden=True)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)
        cls.directory.cleanup()

    def test_saved_datums_follow_both_drives_and_module_placement(self):
        from gondola.validation.propulsion import horn_registration_check

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
                finally:
                    pod.Tilt = original
        finally:
            module.Placement = placement
            self.doc.recompute()

    def test_removing_tip_datum_is_rejected_even_with_the_bolt_installed(self):
        from gondola.parts import servo_coupling as coupling
        from gondola.validation.propulsion import direct_adapter_fit_check

        adapter = self.doc.PortHornGearAdapter
        original = adapter.Shape.copy()
        try:
            # Remove only the rear locating lip. The clamped front face, bolt,
            # horn and shaft socket remain in place and still fit nominally.
            adapter.Shape = original.cut(
                Part.makeBox(
                    10,
                    coupling.HORN_HEIGHT - coupling.BODY_BACK_Y + 0.01,
                    20,
                    App.Vector(
                        coupling.HORN_TIP_CENTRE + coupling.HORN_TIP_RADIUS,
                        coupling.HORN_BOTTOM_Y + coupling.BODY_BACK_Y - 0.01,
                        -10,
                    ),
                )
            )
            self.doc.recompute()
            result = direct_adapter_fit_check(self.doc, "Port")
            self.assertTrue(result["input_shaft_retention_passed"])
            self.assertTrue(
                all(row["intersection_mm3"] < 1e-5 for row in result["internal_pairs"])
            )
            self.assertFalse(result["horn_registration"]["passed"], result)
            self.assertFalse(result["passed"], result)
        finally:
            adapter.Shape = original
            self.doc.recompute()


if __name__ == "__main__":
    unittest.main()
