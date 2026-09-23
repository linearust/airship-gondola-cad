"""Native regressions for loose rigid guides and independent positive latches."""

import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class StackInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import (
            equipment_envelopes,
            equipment_mounts,
            optical_mount,
            optical_sensor,
        )

        cls.doc = App.newDocument("StructuralStackRegression")
        cls.battery = cls.doc.addObject("App::Part", "BatteryEquipmentModule")
        cls.electronics = cls.doc.addObject("App::Part", "ElectronicsEquipmentModule")
        cls.battery.Placement.Base.x = -90
        cls.electronics.Placement.Base.x = 90
        for host, kind in ((cls.battery, "battery"), (cls.electronics, "electronics")):
            equipment_mounts.build_mount(cls.doc, host, kind)
        equipment_envelopes.build_equipment(cls.doc, cls.battery, cls.electronics)
        cls.kit = optical_mount.build_optical_mount(cls.doc, cls.battery)
        cls.refs, cls.reserves = optical_sensor.build_sensor(
            cls.doc, cls.kit["pitch_stage"]
        )
        cls.moving = cls.kit["printed"] + cls.kit["hardware"] + cls.refs
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def setUp(self):
        from gondola.parts import optical_mount, stack_interface

        stack_interface.attach_to_host(self.kit["group"], self.battery)
        optical_mount.set_angles(self.doc, 0, 0)

    def test_complete_tower_reparents_with_positive_capture_on_each_host(self):
        from gondola.parts import stack_interface
        from gondola.validation.optical import tower_attachment_check

        before = {obj.Name: obj.getGlobalPlacement().Base for obj in self.moving}
        for host, dx in ((self.electronics, 180), (self.battery, 0)):
            stack_interface.attach_to_host(self.kit["group"], host)
            self.assertEqual(self.kit["group"].StackHostName, host.Name)
            for obj in self.moving:
                self.assertLess(
                    (
                        obj.getGlobalPlacement().Base
                        - before[obj.Name]
                        - App.Vector(dx, 0, 0)
                    ).Length,
                    1e-7,
                )
            result = tower_attachment_check(self.doc, host)
            self.assertTrue(result["passed"], result)
            self.assertEqual(len(result["positive_latch_seats"]), 2)
            self.assertGreater(
                result["dimensional_and_strain_screen"][
                    "minimum_remaining_guide_engagement_mm"
                ],
                1.5,
            )

    def test_cut_away_hook_or_refilled_host_guide_is_rejected(self):
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import tower_attachment_check

        base, host = self.doc.OpticalMountBase, self.doc.BatteryMount
        old_base, old_host = base.Shape.copy(), host.Shape.copy()
        x, y = s.ANCHOR_CENTRES[1]
        radius, angle = math.hypot(x, y), math.degrees(math.atan2(y, x))
        try:
            cut = Part.makeBox(
                12, 12, 5, App.Vector(radius - 3, -6, s.HOOK_BOTTOM_Z - 1)
            )
            cut.rotate(App.Vector(), App.Vector(0, 0, 1), angle)
            base.Shape = old_base.cut(cut)
            self.assertFalse(tower_attachment_check(self.doc, self.battery)["passed"])
            base.Shape = old_base
            fill = Part.makeBox(
                3.4,
                7.4,
                2,
                App.Vector(
                    radius + s.FIXED_LEG_INNER - 0.7, -3.7, s.HOST_DECK_BOTTOM_Z
                ),
            )
            fill.rotate(App.Vector(), App.Vector(0, 0, 1), angle)
            host.Shape = old_host.fuse(fill)
            self.assertFalse(tower_attachment_check(self.doc, self.battery)["passed"])
        finally:
            base.Shape, host.Shape = old_base, old_host

    def test_no_foot_fasteners_or_retained_stack_parts(self):
        from gondola.parts.stack_interface import is_removable_head_part

        self.assertTrue(
            all(is_removable_head_part(obj, self.kit["group"]) for obj in self.moving)
        )
        self.assertFalse(
            is_removable_head_part(self.doc.BatteryMount, self.kit["group"])
        )
        self.assertEqual(len(self.kit["hardware"]), 4)
        self.assertFalse(any("Foot" in obj.Name for obj in self.kit["hardware"]))

    def test_coupon_has_the_production_contact_geometry_and_orientation(self):
        from gondola.parts import equipment_mounts
        from gondola.parts import stack_interface as s

        coupons = s.build_fit_coupons(self.doc)
        try:
            coupon = coupons["printed"][0]
            anchor = App.Rotation(App.Vector(0, 0, 1), 45)
            expected_rotation = equipment_mounts.PRINT_ROTATION.multiply(anchor)
            self.assertTrue(coupon.PrintRotation.isSame(expected_rotation, 1e-7))
            radius = math.hypot(*s.ANCHOR_CENTRES[1])
            transformed = coupon.Shape.copy()
            transformed.translate(App.Vector(radius, 0, s.HOST_DECK_BOTTOM_Z))
            transformed.rotate(App.Vector(), App.Vector(0, 0, 1), 45)
            crop = Part.makeBox(
                s.HOST_SEAT_OUTER - s.FOOT_INNER_OFFSET,
                s.HOST_SEAT_WIDTH,
                s.DECK_THICKNESS,
                App.Vector(
                    radius + s.FOOT_INNER_OFFSET,
                    -s.HOST_SEAT_WIDTH / 2,
                    s.HOST_DECK_BOTTOM_Z,
                ),
            )
            crop.rotate(App.Vector(), App.Vector(0, 0, 1), 45)
            for kind in ("battery", "electronics"):
                production = equipment_mounts.mount_shape(kind).common(crop)
                sample = transformed.common(crop)
                self.assertLess(
                    abs(production.cut(sample).Volume)
                    + abs(sample.cut(production).Volume),
                    1e-5,
                )
            self.assertTrue(coupons["printed"][1].PrintRotation.isSame(anchor, 1e-7))
        finally:
            for obj in coupons["printed"]:
                self.doc.removeObject(obj.Name)
            self.doc.removeObject(coupons["group"].Name)

    def test_release_and_lift_are_clear_on_both_hosts_and_reject_blockers(self):
        from gondola.cad import world_shape
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import (
            _tower_float_clearance_check,
            _tower_service_check,
        )

        for host in (self.battery, self.electronics):
            s.attach_to_host(self.kit["group"], host)
            fixed = {
                obj.Name: world_shape(obj)
                for obj in self.doc.Objects
                if obj.TypeId == "Part::Feature"
                and obj not in self.moving + self.reserves
            }
            result = _tower_service_check(self.doc, fixed, self.moving)
            self.assertTrue(result["passed"], result)
            floating = _tower_float_clearance_check(self.doc, host, fixed)
            self.assertTrue(floating["passed"], floating)
        s.attach_to_host(self.kit["group"], self.battery)
        fixed = {"BatteryMount": world_shape(self.doc.BatteryMount)}
        local = s.latch_press_reservations()[0][1]
        local.Placement = (
            self.kit["group"].getGlobalPlacement().multiply(local.Placement)
        )
        point = local.CenterOfMass
        result = _tower_service_check(
            self.doc,
            {**fixed, "PressBlocker": Part.makeSphere(0.2, point)},
            self.moving,
        )
        self.assertFalse(result["passed"])
        self.assertTrue(
            any(
                row["manual_access_collisions"]
                for row in result["manual_release_access"]
            )
        )

    def test_continuous_float_bounds_contain_coupled_translated_and_yawed_tower(self):
        from gondola.cad import union
        from gondola.parts import stack_interface as s

        bound = union([shape for _, shape in s.rigid_float_component_bounds()])
        tower = s.tower_shape()
        a, b = s.FIXED_LEG_THICKNESS / 2, s.LEG_WIDTH / 2
        radius = math.hypot(*s.ANCHOR_CENTRES[0]) + s.FIXED_LEG_INNER + a
        gap = s.MAX_RADIAL_FLOAT
        # A near-end yaw with almost zero remaining tangent translation.
        end_angle = math.asin(gap / (radius + a))
        for yaw in (-end_angle, 0, end_angle):
            c, sn = math.cos(yaw), abs(math.sin(yaw))
            tr = a + gap - a * c - b * sn - radius * (1 - c)
            tt = b + gap - a * sn - b * c - radius * sn
            self.assertGreaterEqual(min(tr, tt), 0)
            for radial, tangent in ((-tr, -tt), (-tr, tt), (tr, -tt), (tr, tt)):
                moved = tower.copy()
                moved.rotate(App.Vector(), App.Vector(0, 0, 1), math.degrees(yaw))
                moved.translate(
                    App.Vector(
                        (radial - tangent) / math.sqrt(2),
                        (radial + tangent) / math.sqrt(2),
                        gap,
                    )
                )
                self.assertLess(
                    abs(moved.cut(bound).Volume), 1e-5, (yaw, radial, tangent)
                )

    def test_unsupported_host_is_rejected_without_moving_kit(self):
        from gondola.parts import stack_interface

        unknown = self.doc.addObject("App::Part", "UnsupportedHost")
        try:
            with self.assertRaises(ValueError):
                stack_interface.attach_to_host(self.kit["group"], unknown)
            self.assertEqual(self.kit["group"].getParentGeoFeatureGroup(), self.battery)
        finally:
            self.doc.removeObject(unknown.Name)


if __name__ == "__main__":
    unittest.main()
