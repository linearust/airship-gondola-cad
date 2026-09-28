"""Saved tape placement diagnostics must follow geometry, not source pad constants."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailSupportTests(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument("RailSupportDiagnostic")
        self.frame = self.doc.addObject("App::Part", "Frame")
        self.frame.Placement = App.Placement(
            App.Vector(12, -18, 7), App.Rotation(App.Vector(1, 2, 3), 37)
        )
        self.rail = self.doc.addObject("Part::Feature", "Rail")
        self.rail.Shape = Part.makeBox(340, 6, 1.2, App.Vector(-170, -3, 0))
        self.frame.addObject(self.rail)
        self.module = self.doc.addObject("App::Part", "Carrier")
        self.frame.addObject(self.module)
        self.module.Placement.Base = App.Vector(90, -0.1, 0)
        self.tapes = []
        for label, y in (("Left", -36), ("Right", 6)):
            tape = self.doc.addObject("Part::Feature", label)
            self.frame.addObject(tape)
            tape.Shape = Part.makeBox(12, 30, 0.15, App.Vector(84, y, 1.2))
            self.tapes.append(tape)
        self.doc.recompute()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def report(self, tapes=None):
        from gondola.cad import world_shape
        from gondola.validation.assembly import tape_station_alignment

        tapes = self.tapes if tapes is None else tapes
        return tape_station_alignment(
            self.rail,
            [self.module],
            tapes,
            {obj.Name: world_shape(obj) for obj in tapes},
        )

    def test_common_rigid_transform_keeps_actual_station_and_both_tapes_aligned(self):
        report = self.report()
        row = report["modules"][0]
        self.assertAlmostEqual(row["station_x_mm"], 90)
        for tape in row["nearest_tapes"].values():
            self.assertAlmostEqual(tape["centre_distance_mm"], 0)
            self.assertTrue(tape["station_within_tape_width"])
            self.assertTrue(tape["same_head_land"])
        self.assertNotIn("passed", report)

    def test_moving_saved_tapes_is_visible_without_changing_source_pad_layout(self):
        for tape in self.tapes:
            tape.Placement.Base = App.Vector(18, 0, 0)
        self.doc.recompute()
        for tape in self.report()["modules"][0]["nearest_tapes"].values():
            self.assertAlmostEqual(tape["centre_distance_mm"], 18)
            self.assertFalse(tape["station_within_tape_width"])
            self.assertFalse(tape["same_head_land"])

    def test_missing_tape_side_and_gap_station_are_not_reported_as_directly_aligned(
        self,
    ):
        row = self.report(self.tapes[:1])["modules"][0]
        self.assertIsNone(row["nearest_tapes"]["positive_y"])
        self.module.Placement.Base = App.Vector(99, -0.1, 0)
        self.doc.recompute()
        for tape in self.report()["modules"][0]["nearest_tapes"].values():
            self.assertFalse(tape["same_head_land"])


if __name__ == "__main__":
    unittest.main()
