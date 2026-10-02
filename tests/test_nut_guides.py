"""Side-entry cap and rotor-jack nuts retain real walls, floors and release paths."""

import tempfile
import unittest
from pathlib import Path

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SideEntryNutGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import bearing_retention, propulsion

        cls.sites = [
            (
                bearing_retention.lower_housing_shape(),
                App.Placement(
                    App.Vector(5.5, 6.5, -2.5), App.Rotation(App.Vector(1, 0, 0), 180)
                ),
                1,
                2.5,
            ),
            (
                propulsion.moving_carrier_shape(sign=1),
                App.Placement(
                    App.Vector(8, -25.5, 0),
                    App.Rotation(App.Vector(0, 0, 1), App.Vector(-1, 0, 0)),
                ),
                1,
                3.0,
            ),
        ]

    def check(self, shape, pose, direction, floor):
        from gondola.validation.nut_guides import nut_guide_check

        return nut_guide_check(
            shape, pose, outward_sign=direction, floor_thickness=floor
        )

    def test_maximum_nuts_clear_and_minimum_nuts_restrain_rotation(self):
        for site in self.sites:
            with self.subTest(floor=site[-1]):
                report = self.check(*site)
                self.assertTrue(report["passed"], report)
                self.assertEqual(len(report["nut_fit_and_side_entry"]), 9)
                self.assertEqual(len(report["minimum_nut_rotation_stops"]), 18)

    def test_either_retaining_wall_is_required(self):
        for host, pose, direction, floor in self.sites:
            for side in (-1, 1):
                cutter = Part.makeBox(
                    1, 0.5, 1, App.Vector(-0.5, 2.2 if side > 0 else -2.7, 0.2)
                )
                cutter.Placement = pose.multiply(cutter.Placement)
                report = self.check(host.cut(cutter), pose, direction, floor)
                self.assertFalse(report["passed"], report)
                self.assertGreater(
                    sum(x["missing_wall_mm3"] for x in report["wall_witnesses"]), 0.4
                )

    def test_full_bearing_floor_cannot_be_replaced_by_a_thin_seat(self):
        for host, pose, direction, floor in self.sites:
            cutter = Part.makeBox(0.2, 0.2, 0.5, App.Vector(1.6, -0.1, -floor + 0.1))
            cutter.Placement = pose.multiply(cutter.Placement)
            report = self.check(host.cut(cutter), pose, direction, floor)
            self.assertFalse(report["passed"], report)
            self.assertGreater(
                report["nut_fit_and_side_entry"][0]["missing_bearing_floor_mm3"], 0.01
            )

    def test_off_axis_clearance_is_checked_when_centred_nut_still_fits(self):
        for host, pose, direction, floor in self.sites:
            wall = Part.makeBox(1, 0.075, 1, App.Vector(-0.5, 2.05, 0.2))
            wall.Placement = pose.multiply(wall.Placement)
            report = self.check(host.fuse(wall), pose, direction, floor)
            self.assertTrue(report["nut_fit_and_side_entry"][0]["passed"], report)
            self.assertFalse(report["passed"], report)

    def test_side_exit_midpath_obstacle_is_not_hidden_by_clear_endpoints(self):
        for host, pose, direction, floor in self.sites:
            blocker = Part.makeBox(0.2, 0.2, 0.2, App.Vector(12, -0.1, 0.5))
            blocker.Placement = pose.multiply(blocker.Placement)
            report = self.check(host.fuse(blocker), pose, direction, floor)
            self.assertFalse(report["passed"], report)
            self.assertGreater(
                report["nut_fit_and_side_entry"][0][
                    "maximum_nut_side_entry_overlap_mm3"
                ],
                0.001,
            )

    def test_an_oversize_slot_loses_minimum_nut_antirotation(self):
        for host, pose, direction, floor in self.sites:
            cutter = Part.makeBox(8, 8, 1.8, App.Vector(-4, -4, 0))
            cutter.Placement = pose.multiply(cutter.Placement)
            report = self.check(host.cut(cutter), pose, direction, floor)
            self.assertFalse(report["passed"], report)
            self.assertTrue(
                all(not x["passed"] for x in report["minimum_nut_rotation_stops"])
            )

    def test_six_actual_sites_survive_native_reopen_and_parent_motion(self):
        from gondola.parts.propulsion import build_propulsion_module
        from gondola.validation.nut_guides import installed_nut_guide_checks

        doc = App.newDocument("SideEntryNutNative")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nuts.FCStd"
            try:
                build_propulsion_module(doc)
                doc.MainPropulsionModule.Placement = App.Placement(
                    App.Vector(7, -8, 3), App.Rotation(App.Vector(1, 0, 0), 13)
                )
                doc.PortPod.Tilt, doc.StarboardPod.Tilt = 37, -149
                doc.recompute()
                doc.saveAs(str(path))
            finally:
                App.closeDocument(doc.Name)
            saved = App.openDocument(str(path), hidden=True)
            try:
                saved.recompute()
                rows = installed_nut_guide_checks(saved)
                self.assertEqual(len(rows), 6)
                self.assertTrue(all(x["passed"] for x in rows), rows)
                nut = saved.PortOutputClampNegativeNut
                original = nut.Placement
                nut.Placement.Base += App.Vector(0.1, 0, 0)
                saved.recompute()
                self.assertFalse(
                    all(x["passed"] for x in installed_nut_guide_checks(saved))
                )
                nut.Placement = original
                saved.removeObject("PortBearingCapNegativeNut")
                self.assertFalse(
                    all(x["passed"] for x in installed_nut_guide_checks(saved))
                )
            finally:
                App.closeDocument(saved.Name)

    def test_unknown_floor_or_route_cannot_silently_select_a_contract(self):
        host, pose, _, _ = self.sites[0]
        for direction, floor in ((0, 2.5), (1, 1.5)):
            with self.assertRaises(ValueError):
                self.check(host, pose, direction, floor)


if __name__ == "__main__":
    unittest.main()
