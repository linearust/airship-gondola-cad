"""Native regressions for direct seating clamps and bounded assembly registration."""

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

    def test_complete_tower_reparents_with_direct_clamping_on_each_host(self):
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
            self.assertEqual(len(result["direct_clamped_seats"]), 2)
            self.assertEqual(result["clamp_fit"]["nominal_axial_seating_gap_mm"], 0)

    def test_cut_away_seat_or_refilled_clamp_hole_is_rejected(self):
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import tower_attachment_check

        base, host = self.doc.OpticalMountBase, self.doc.BatteryMount
        old_base, old_host = base.Shape.copy(), host.Shape.copy()
        x, y = s.ANCHOR_CENTRES[1]
        radius, angle = math.hypot(x, y), math.degrees(math.atan2(y, x))
        try:
            cut = Part.makeBox(12, 12, 1, App.Vector(radius - 4, -6, -s.TOWER_HEIGHT))
            cut.rotate(App.Vector(), App.Vector(0, 0, 1), angle)
            base.Shape = old_base.cut(cut)
            self.assertFalse(tower_attachment_check(self.doc, self.battery)["passed"])
            base.Shape = old_base
            cx, cy = s.CLAMP_CENTRES[1]
            host.Shape = old_host.fuse(
                Part.makeCylinder(1.3, 2, App.Vector(cx, cy, s.HOST_DECK_BOTTOM_Z))
            )
            self.assertFalse(tower_attachment_check(self.doc, self.battery)["passed"])
        finally:
            base.Shape, host.Shape = old_base, old_host

    def test_foot_hardware_is_in_removable_kit_and_uses_existing_sizes(self):
        from gondola.parts.stack_interface import is_removable_head_part

        self.assertTrue(
            all(is_removable_head_part(obj, self.kit["group"]) for obj in self.moving)
        )
        self.assertFalse(
            is_removable_head_part(self.doc.BatteryMount, self.kit["group"])
        )
        self.assertEqual(len(self.kit["hardware"]), 8)
        feet = [obj for obj in self.kit["hardware"] if "Foot" in obj.Name]
        self.assertEqual(len(feet), 4)
        self.assertEqual(
            {obj.HardwareSKU for obj in feet}, {"M2X8_BUTTON_HEAD", "M2_HEX_NUT"}
        )

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
        local = s.clamp_tool_reservations()[0][1]
        local.Placement = (
            self.kit["group"].getGlobalPlacement().multiply(local.Placement)
        )
        point = local.CenterOfMass
        result = _tower_service_check(
            self.doc,
            {**fixed, "KeyBlocker": Part.makeSphere(0.2, point)},
            self.moving,
        )
        self.assertFalse(result["passed"])
        self.assertTrue(
            any(row["access_collisions"] for row in result["clamp_tool_access"])
        )

    def test_bench_service_separates_tape_but_keeps_host_and_unknown_obstacles(self):
        from gondola.cad import world_shape
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import _tower_service_check

        s.attach_to_host(self.kit["group"], self.battery)
        tool = s.clamp_tool_reservations()[0][1]
        tool.Placement = self.kit["group"].getGlobalPlacement().multiply(tool.Placement)
        point = tool.CenterOfMass
        tape_group = self.doc.addObject("App::Part", "TapeAttachmentReference")
        blocker = self.doc.addObject("Part::Feature", "BenchServiceBlocker")
        tape_group.addObject(blocker)
        blocker.Shape = Part.makeSphere(0.2, point)
        try:
            fixed = {
                "BatteryMount": world_shape(self.doc.BatteryMount),
                blocker.Name: world_shape(blocker),
            }
            result = _tower_service_check(self.doc, fixed, self.moving)
            self.assertTrue(result["passed"], result)
            frame = result["bench_service_frame"]
            self.assertEqual(frame["host"], self.battery.Name)
            self.assertIn(
                {"object": blocker.Name, "separated_vehicle_group": tape_group.Name},
                frame["removed_nonhost_objects"],
            )
            self.assertIn("ModuleBatteryEnvelope", frame["retained_obstacles"])
            # Reclassifying the same physical obstruction as host-attached must
            # prevent its removal, even if the caller omits it from the mapping.
            tape_group.removeObject(blocker)
            self.battery.addObject(blocker)
            blocker.Shape = Part.makeSphere(
                0.2, self.battery.getGlobalPlacement().inverse().multVec(point)
            )
            result = _tower_service_check(
                self.doc,
                {"BatteryMount": world_shape(self.doc.BatteryMount)},
                self.moving,
            )
            self.assertFalse(result["passed"])
            self.assertIn(
                blocker.Name, result["bench_service_frame"]["retained_obstacles"]
            )
            self.assertTrue(
                any(
                    any(
                        hit["object"] == blocker.Name
                        for hit in row["access_collisions"]
                    )
                    for row in result["clamp_tool_access"]
                )
            )
            self.battery.removeObject(blocker)
            self.doc.removeObject(blocker.Name)
            result = _tower_service_check(
                self.doc,
                {"UnknownBenchBlocker": Part.makeSphere(0.2, point)},
                self.moving,
            )
            self.assertFalse(result["passed"])
            self.assertIn(
                "UnknownBenchBlocker",
                result["bench_service_frame"]["retained_obstacles"],
            )
        finally:
            if self.doc.getObject("BenchServiceBlocker") is not None:
                self.doc.removeObject("BenchServiceBlocker")
            self.doc.removeObject(tape_group.Name)

    def test_registration_requires_a_service_gap_even_without_a_collision(self):
        from gondola.cad import world_shape
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import _tower_float_clearance_check

        s.attach_to_host(self.kit["group"], self.electronics)
        capacitor = world_shape(self.doc.CapacitorServiceReserve)
        leg = dict(s.rigid_float_component_bounds())["load_leg_1"]
        leg.Placement = self.kit["group"].getGlobalPlacement().multiply(leg.Placement)
        gap, pairs, _ = leg.distToShape(capacitor)
        self.assertGreater(gap, 1.5)
        move = pairs[0][0] - pairs[0][1]
        move.normalize()
        capacitor.translate(move * (gap - 1.0))
        self.assertLess(abs(leg.common(capacitor).Volume), 1e-5)
        result = _tower_float_clearance_check(
            self.doc, self.electronics, {"CapacitorServiceReserve": capacitor}
        )
        self.assertFalse(result["passed"])
        row = next(
            item
            for item in result["component_bounds"]
            if item["component"] == "load_leg_1"
        )
        self.assertFalse(row["collisions"])
        self.assertAlmostEqual(row["capacitor_service_gap_mm"], 1.0, places=6)

    def test_continuous_float_bounds_contain_coupled_translated_and_yawed_tower(self):
        from gondola.cad import union
        from gondola.parts import stack_interface as s

        bound = union([shape for _, shape in s.rigid_float_component_bounds()])
        tower = s.tower_shape()
        radius = math.hypot(*s.CLAMP_CENTRES[0])
        gap = s.MAX_RADIAL_FLOAT
        limit = 2 * math.asin(gap / (2 * radius))
        for yaw in (-0.9 * limit, -0.5 * limit, 0, 0.5 * limit, 0.9 * limit):
            dr, dt = radius * (math.cos(yaw) - 1), radius * math.sin(yaw)
            d = math.hypot(dr, dt)
            t = math.sqrt(max(0, gap * gap - d * d))
            direction = (1, 0) if d < 1e-9 else (-dt / d, dr / d)
            for sign in (-1, 1):
                radial, tangent = (sign * t * v for v in direction)
                self.assertLessEqual(math.hypot(radial + dr, tangent + dt), gap + 1e-7)
                self.assertLessEqual(math.hypot(radial - dr, tangent - dt), gap + 1e-7)
                moved = tower.copy()
                moved.rotate(App.Vector(), App.Vector(0, 0, 1), math.degrees(yaw))
                moved.translate(
                    App.Vector(
                        (radial - tangent) / math.sqrt(2),
                        (radial + tangent) / math.sqrt(2),
                        0,
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
