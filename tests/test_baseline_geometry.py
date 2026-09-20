"""Independent approved-change checks; run inside the FreeCAD Python runtime."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(
    App is None, "Requires FreeCAD; exercised by the CAD validation workflow"
)
class ApprovedRailBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.config import BASELINE_FILE, BASELINE_SHA256
        from gondola.provenance import file_sha256
        from gondola.validation.baseline import approved_rail_shape
        from gondola.validation.geometry import local_shape

        if file_sha256(BASELINE_FILE) != BASELINE_SHA256:
            raise AssertionError("Frozen Rev I fixture hash changed")
        document = App.openDocument(str(BASELINE_FILE), hidden=True)
        try:
            cls.original = local_shape(document.ContinuousRail)
        finally:
            App.closeDocument(document.Name)
        cls.approved = approved_rail_shape(cls.original)

    def compare(self, first, second):
        from gondola.manufacturing import geometry_comparison

        return geometry_comparison(first, second)

    def test_requested_rail_matches_independently_transplanted_frozen_ends(self):
        from gondola.parts.rail import rail_shape

        comparison = self.compare(rail_shape(340), self.approved)
        self.assertLess(comparison["difference_mm3"], 1e-5)
        self.assertLess(comparison["volume_difference_mm3"], 1e-5)
        self.assertLess(comparison["bounds_difference_mm"], 1e-5)
        bounds = self.approved.optimalBoundingBox(False, False)
        self.assertAlmostEqual(bounds.XMin, -170)
        self.assertAlmostEqual(bounds.XMax, 170)

    def test_center_and_complete_tape_pads_preserve_frozen_geometry(self):
        center = Part.makeBox(338, 40, 10, App.Vector(-169, -20, -1))
        comparison = self.compare(
            self.original.common(center), self.approved.common(center)
        )
        self.assertLess(comparison["difference_mm3"], 1e-5)

    def test_simple_crop_is_rejected_due_to_wrong_terminal_profiles(self):
        cropped = self.original.common(
            Part.makeBox(340, 40, 10, App.Vector(-170, -20, -1))
        )
        self.assertGreater(self.compare(cropped, self.approved)["difference_mm3"], 1e-5)

    def test_unapproved_length_and_interior_damage_are_rejected(self):
        self.assertGreater(
            self.compare(self.original, self.approved)["difference_mm3"], 1e-5
        )
        damaged = self.approved.cut(Part.makeBox(1, 1, 1, App.Vector(-0.5, -0.5, 6)))
        self.assertGreater(self.compare(damaged, self.approved)["difference_mm3"], 0.9)


if __name__ == "__main__":
    unittest.main()
