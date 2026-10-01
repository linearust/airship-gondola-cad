"""Nominal capture, bearing planes and release of recessed M2 nut seats."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ShallowNutGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import bearing_retention

        cls.cup = bearing_retention.cup_shape()
        cls.frames = (
            (
                cls.cup,
                App.Placement(
                    App.Vector(0, 3.5, -18),
                    App.Rotation(App.Vector(0, 0, 1), App.Vector(0, 1, 0)),
                ),
                6.0,
            ),
        )

    def test_shallow_keeper_pocket_fits_and_restrains_ordinary_nuts(self):
        from gondola.validation.nut_guides import nut_guide_check

        for host, pose, length in self.frames:
            with self.subTest(rail_length=length):
                self.assertTrue(host.isValid())
                self.assertEqual(len(host.Solids), 1)
                report = nut_guide_check(host, pose, length)
                self.assertTrue(report["passed"], report)
                self.assertEqual(len(report["minimum_nut_rotation_stops"]), 18)

    def test_complete_recess_wall_is_required(self):
        from gondola.validation.nut_guides import nut_guide_check

        for host, pose, length in self.frames:
            for side in (-1, 1):
                cutter = Part.makeBox(
                    2, 2, 0.5, App.Vector(-1, side * 2.125 - (2 if side < 0 else 0), 0)
                )
                cutter.Placement = pose.multiply(cutter.Placement)
                with self.subTest(rail_length=length, side=side):
                    report = nut_guide_check(host.cut(cutter), pose, length)
                    self.assertFalse(report["passed"], report)
                    self.assertGreater(
                        sum(
                            row["missing_rail_mm3"] for row in report["rail_witnesses"]
                        ),
                        0.1,
                    )

    def test_clearance_loss_cannot_be_hidden_by_a_fitting_centred_nut(self):
        from gondola.validation.nut_guides import nut_guide_check

        host, pose, length = self.frames[0]
        inward_wall = Part.makeBox(5.8, 0.075, 1, App.Vector(-2.9, 2.05, 0))
        inward_wall.Placement = pose.multiply(inward_wall.Placement)
        report = nut_guide_check(host.fuse(inward_wall), pose, length)
        self.assertTrue(report["nut_fit_and_axial_service"][0]["passed"])
        self.assertFalse(report["passed"], report)

    def test_actual_seat_material_and_midpath_release_obstacles_are_required(self):
        from gondola.validation.nut_guides import nut_guide_check

        host, pose, length = self.frames[0]
        void = Part.makeBox(0.2, 0.2, 0.4, App.Vector(1.6, 0, -0.2))
        void.Placement = pose.multiply(void.Placement)
        report = nut_guide_check(host.cut(void), pose, length)
        self.assertFalse(report["passed"], report)
        blocker = Part.makeBox(0.2, 0.2, 0.2, App.Vector(1.6, 0, 2.1))
        blocker.Placement = pose.multiply(blocker.Placement)
        report = nut_guide_check(host.fuse(blocker), pose, length)
        self.assertFalse(report["passed"], report)

    def test_all_eight_installed_sites_follow_their_actual_native_frames(self):
        from gondola.parts.propulsion import build_propulsion_module
        from gondola.validation.nut_guides import installed_nut_guide_checks

        doc = App.newDocument("NutGuideNativeTest")
        try:
            build_propulsion_module(doc)
            doc.MainPropulsionModule.Placement = App.Placement(
                App.Vector(7, -8, 3), App.Rotation(App.Vector(1, 0, 0), 13)
            )
            doc.PortPod.Tilt, doc.StarboardPod.Tilt = 37, -149
            doc.recompute()
            rows = installed_nut_guide_checks(doc)
            self.assertEqual(len(rows), 8)
            self.assertTrue(all(row["passed"] for row in rows), rows)
            doc.removeObject("PortOutputClampNegativeNut")
            self.assertFalse(
                all(row["passed"] for row in installed_nut_guide_checks(doc))
            )
        finally:
            App.closeDocument(doc.Name)


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RecessedClampNutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.host = propulsion._carrier_side_shape()
        cls.pose = App.Placement(App.Vector(4.2, 26.25, 2.5), App.Rotation())

    def test_flat_block_pocket_has_full_wall_floor_and_clearance(self):
        from gondola.validation.nut_guides import nut_guide_check

        report = nut_guide_check(self.host, self.pose, 5.8, recessed=True)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["guide_height_mm"], 1.5)
        box = Part.makeBox(18, 10, 8, App.Vector(-7, 21.25, -4))
        self.assertLess(self.host.cut(box).Volume, 1e-6)
        # A wide planar end replaces the separate raised circular stop flange.
        end = Part.makeBox(17.8, 0.1, 1, App.Vector(-6.9, 31.15, 2.9))
        self.assertLess(end.cut(self.host).Volume, 1e-6)

    def test_opened_hex_wall_and_missing_floor_are_rejected(self):
        from gondola.validation.nut_guides import nut_guide_check

        for cutter in (
            Part.makeBox(1, 2, 1.5, App.Vector(-0.5, 2, 0)),
            Part.makeBox(0.2, 0.2, 0.4, App.Vector(1.6, 0, -0.2)),
        ):
            cutter.Placement = self.pose.multiply(cutter.Placement)
            report = nut_guide_check(
                self.host.cut(cutter), self.pose, 5.8, recessed=True
            )
            self.assertFalse(report["passed"], report)

    def test_old_lift_is_insufficient_for_deeper_pocket(self):
        from gondola.parts import purchased_hardware
        from gondola.validation.propulsion_service import fastener_service_check

        bolt, nut = purchased_hardware.screw_shape(), purchased_hardware.hex_nut_shape()
        bolt.translate(App.Vector(4.2, 26.25, -2.5))
        nut.translate(App.Vector(4.2, 26.25, 2.5))
        options = dict(nut_lateral_direction=(-1, 0, 0), guided_nut=True)
        old = fastener_service_check(bolt, nut, {"carrier": self.host}, **options)
        new = fastener_service_check(
            bolt, nut, {"carrier": self.host}, capture_depth_mm=1.5, **options
        )
        self.assertFalse(old["passed"], old)
        self.assertTrue(new["passed"], new)


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class GuidedNutServiceTests(unittest.TestCase):
    def test_short_legacy_lateral_release_is_blocked_but_raised_release_is_clear(self):
        from gondola.parts import propulsion, purchased_hardware
        from gondola.validation.propulsion_service import fastener_service_check

        bolt, nut = purchased_hardware.screw_shape(), purchased_hardware.hex_nut_shape()
        bolt.translate(App.Vector(4.2, 26.25, -2.5))
        nut.translate(App.Vector(4.2, 26.25, 2.5))
        obstacles = {"carrier": propulsion._carrier_side_shape()}
        old = fastener_service_check(
            bolt, nut, obstacles, nut_lateral_direction=(0, 1, 0)
        )
        new = fastener_service_check(
            bolt,
            nut,
            obstacles,
            nut_lateral_direction=(0, 1, 0),
            guided_nut=True,
            capture_depth_mm=1.5,
        )
        self.assertFalse(old["passed"], old)
        self.assertTrue(new["passed"], new)
        self.assertEqual(new["minimum_nut_lift_before_lateral_mm"], 1.7)
        self.assertTrue(new["screw_first_with_nut_held_in_guides"])
        self.assertIn(
            "seated_guided_nut",
            new["bolt_axial_withdrawal"]["segments"][0]["intersection_mm3"],
        )
        with self.assertRaises(ValueError):
            fastener_service_check(
                bolt, nut, obstacles, retain_bolt=True, guided_nut=True
            )

    def test_all_eight_guided_nuts_release_in_the_complete_retained_scene(self):
        from gondola.cad import world_shape
        from gondola.parts.propulsion import build_propulsion_module
        from gondola.validation.nut_guides import guided_nut_service_direction
        from gondola.validation.propulsion_service import (
            fastener_service_check,
            module_service_shapes,
        )

        doc = App.newDocument("GuidedNutServiceTest")
        try:
            module = build_propulsion_module(doc)
            doc.MainPropulsionModule.Placement = App.Placement(
                App.Vector(7, -8, 3), App.Rotation(App.Vector(1, 0, 0), 13)
            )
            doc.recompute()
            shapes, missing = module_service_shapes(doc, module)
            self.assertFalse(missing)
            shapes = {name: world_shape(doc.getObject(name)) for name in shapes}
            for prefix in ("Port", "Starboard"):
                for side, suffix in ((-1, "Negative"), (1, "Positive")):
                    for joint in ("OutputClamp", "OutputBearingKeeper"):
                        name = prefix + joint + suffix
                        removed = {name + "Bolt", name + "Nut"}
                        if joint == "OutputBearingKeeper":
                            # The checked keeper service starts after its rotor,
                            # shafts and output gear have been removed.
                            removed.update(
                                obj.Name for obj in doc.getObject(prefix + "Pod").Group
                            )
                        retained = {
                            key: value
                            for key, value in shapes.items()
                            if key not in removed
                        }
                        # Rotor nuts leave toward the open motor-plate side;
                        # moving them along Y instead would meet the fixed cup.
                        lateral = guided_nut_service_direction(doc, name + "Bolt")
                        with self.subTest(joint=name):
                            report = fastener_service_check(
                                shapes[name + "Bolt"],
                                shapes[name + "Nut"],
                                retained,
                                nut_lateral_direction=lateral,
                                guided_nut=True,
                                capture_depth_mm=1.5 if joint == "OutputClamp" else 0.5,
                            )
                            self.assertTrue(report["passed"], report)
        finally:
            App.closeDocument(doc.Name)

    def test_only_the_eight_named_sites_acquire_screw_first_service(self):
        from gondola.parts import purchased_hardware
        from gondola.validation.nut_guides import is_guided_nut_bolt
        from gondola.validation.propulsion_service import fastener_service_check

        for name in (
            "PortServoEarLowerBolt",
            "StarboardInputShaftClampBolt",
            "OpticalPitchBolt",
            "PortHornGearClampNearBolt",
            "OtherOutputClampNegativeBolt",
        ):
            self.assertFalse(is_guided_nut_bolt(name), name)
        bolt, nut = (
            purchased_hardware.servo_screw_shape(),
            purchased_hardware.servo_nut_shape(),
        )
        nut.translate(App.Vector(0, 0, 6))
        report = fastener_service_check(
            bolt, nut, {}, thread_diameter=1.6, retain_bolt=True
        )
        self.assertTrue(report["passed"], report)
        self.assertFalse(report["screw_first_with_nut_held_in_guides"])
        self.assertTrue(report["bolt_retained_in_servo_unit"])


if __name__ == "__main__":
    unittest.main()
