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
        accessory = cls.doc.addObject("App::Part", "AccessoryEquipmentModule")
        accessory.Placement.Base.x = 180
        equipment_envelopes.build_equipment(
            cls.doc, cls.battery, cls.electronics, accessory
        )
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

    def test_top_is_one_rectangular_beam_flush_with_the_leg_outer_faces(self):
        from gondola.parts import stack_interface as s

        tower = s.tower_shape()
        tower.rotate(App.Vector(), App.Vector(0, 0, 1), -45)
        half_span = (
            math.hypot(*s.ANCHOR_CENTRES[0]) + s.FIXED_LEG_INNER + s.FIXED_LEG_THICKNESS
        )
        expected = Part.makeBox(
            2 * half_span,
            s.LEG_WIDTH,
            s.TOP_BEAM_THICKNESS,
            App.Vector(-half_span, -s.LEG_WIDTH / 2, 0),
        )
        top = tower.common(Part.makeBox(200, 200, 10, App.Vector(-100, -100, 0)))
        self.assertLess(
            abs(top.cut(expected).Volume) + abs(expected.cut(top).Volume), 1e-5
        )
        self.assertEqual(len(top.Solids), 1)
        self.assertEqual(s.DECK_THICKNESS, 2.0)
        self.assertEqual(s.FOOT_THICKNESS, 2.0)
        self.assertEqual(s.TOP_BEAM_THICKNESS, 3.0)

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

    def test_complete_foot_and_host_seat_cannot_lose_an_outer_corner(self):
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import tower_attachment_check

        base, host = self.doc.OpticalMountBase, self.doc.BatteryMount
        before_base, before_host = base.Shape.copy(), host.Shape.copy()
        result = tower_attachment_check(self.doc, self.battery)
        self.assertTrue(result["passed"], result)
        for row in result["direct_clamped_seats"]:
            self.assertAlmostEqual(
                row["expected_complete_foot_contact_area_mm2"],
                8 * 13 - 5**2 / 2 - math.pi * 1.3**2,
                places=6,
            )
        # This tiny outer-corner loss leaves much more than the old 75 mm²
        # threshold. Inspecting the entire foot must still reject it.
        for target, bottom in ((base, -s.TOWER_HEIGHT), (host, s.HOST_DECK_BOTTOM_Z)):
            try:
                target.Shape = target.Shape.cut(
                    Part.makeBox(0.3, 0.3, 2, App.Vector(26.1, 31.1, bottom))
                )
                result = tower_attachment_check(self.doc, self.battery)
                self.assertFalse(result["passed"], result)
                row = result["direct_clamped_seats"][1]
                self.assertGreater(row["direct_seat_contact_area_mm2"], 75)
                self.assertGreater(
                    row["missing_complete_foot_material_mm3"]
                    if target == base
                    else row["missing_complete_carrier_seat_mm3"],
                    1e-5,
                )
            finally:
                base.Shape, host.Shape = before_base.copy(), before_host.copy()

    def test_inward_chamfer_retains_leg_support_and_is_required_during_removal(self):
        from unittest.mock import patch

        from gondola.cad import world_shape
        from gondola.parts import optical_mount
        from gondola.parts import stack_interface as s
        from gondola.validation.optical import _tower_service_check

        for index, (x, y) in enumerate(s.ANCHOR_CENTRES):
            leg = s._radial(s._fixed_leg_shape(math.hypot(x, y)), x, y)
            seat = leg.common(
                Part.makeBox(100, 100, 2, App.Vector(-50, -50, -s.TOWER_HEIGHT))
            )
            self.assertLess(abs(seat.cut(s.foot_shape(index)).Volume), 1e-5)
        s.attach_to_host(self.kit["group"], self.electronics)
        base = self.doc.OpticalMountBase
        original = base.Shape.copy()
        fixed = {
            obj.Name: world_shape(obj)
            for obj in self.doc.Objects
            if obj.TypeId == "Part::Feature" and obj not in self.moving + self.reserves
        }
        try:
            for chamfer in (0, 4):
                with patch.object(s, "FOOT_INBOARD_CHAMFER", chamfer):
                    base.Shape = optical_mount.base_shape()
                    result = _tower_service_check(self.doc, fixed, self.moving)
                    self.assertFalse(result["passed"], result)
                    self.assertTrue(
                        all(
                            row["fc_wiring_gap_mm"] < 1.5
                            for row in result["registered_foot_lift"]
                        ),
                        result,
                    )
        finally:
            base.Shape = original

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
            if host == self.electronics:
                self.assertTrue(
                    all(
                        row["fc_wiring_gap_mm"] >= 1.5
                        for row in result["registered_foot_lift"]
                    ),
                    result,
                )
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
        frame_angle = math.atan2(*reversed(s.CLAMP_CENTRES[1]))
        c, sn = math.cos(frame_angle), math.sin(frame_angle)
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
                pose = App.Placement(
                    App.Vector(
                        radial * c - tangent * sn,
                        radial * sn + tangent * c,
                        0,
                    ),
                    App.Rotation(App.Vector(0, 0, 1), math.degrees(yaw)),
                )
                for x, y in s.CLAMP_CENTRES:
                    axis = App.Vector(x, y, 0)
                    self.assertLessEqual((pose.multVec(axis) - axis).Length, gap + 1e-7)
                moved = tower.copy()
                moved.Placement = pose.multiply(moved.Placement)
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

    def test_accessory_shares_mechanical_pattern_without_claiming_optical_support(self):
        from gondola.parts import equipment_mounts
        from gondola.parts import stack_interface as s
        from gondola.validation.geometry import intersection_volume

        self.assertIn("AccessoryEquipmentModule", s.MECHANICAL_HOSTS)
        self.assertNotIn("AccessoryEquipmentModule", s.SUPPORTED_HOSTS)
        self.assertEqual(s.host_origin_xy("AccessoryMount"), (0.0, 0.0))
        self.assertEqual(
            s.host_placement("AccessoryEquipmentModule").Base,
            App.Vector(0, 0, s.HOST_SUPPORT_Z),
        )
        for host in s.MECHANICAL_HOSTS:
            self.assertEqual(s.host_origin_xy(host), (0.0, 0.0))
        support = equipment_mounts.mount_shape("accessory")
        datum = s.host_origin_xy("AccessoryMount")
        for index in range(2):
            seat = s.foot_shape(index, bottom=s.HOST_DECK_BOTTOM_Z)
            seat.translate(App.Vector(*datum, 0))
            self.assertLess(abs(seat.cut(support).Volume), 1e-6)
        plate = equipment_mounts.common_plate_shape()
        drilled = s.add_host_interface(plate, host)
        self.assertLess(abs(drilled.cut(plate).Volume), 1e-6)
        self.assertEqual((drilled.BoundBox.XMin, drilled.BoundBox.XMax), (-27.0, 27.0))
        for x, y in s.CLAMP_CENTRES:
            hole = Part.makeCylinder(
                s.CLAMP_HOLE_DIAMETER / 2,
                s.DECK_THICKNESS,
                App.Vector(x + datum[0], y + datum[1], s.HOST_DECK_BOTTOM_Z),
            )
            self.assertLess(intersection_volume(hole, support), 1e-6)
        with self.assertRaises(ValueError):
            s.attach_to_host(self.kit["group"], self.doc.AccessoryEquipmentModule)

    def test_round_hardware_bounds_contain_seated_translation_and_yaw(self):
        from gondola.parts import stack_interface as s

        bounds = dict(s.clamp_hardware_float_bounds())
        radius = math.hypot(*s.CLAMP_CENTRES[0])
        angle = math.degrees(2 * math.asin(s.MAX_RADIAL_FLOAT / (2 * radius)))
        poses = [
            App.Placement(App.Vector(dx, dy, 0), App.Rotation())
            for dx, dy in (
                (-s.MAX_RADIAL_FLOAT, 0),
                (s.MAX_RADIAL_FLOAT, 0),
                (0, -s.MAX_RADIAL_FLOAT),
                (0, s.MAX_RADIAL_FLOAT),
            )
        ] + [
            App.Placement(App.Vector(), App.Rotation(App.Vector(0, 0, 1), a))
            for a in (-angle, angle)
        ]
        anchor = App.Vector(*s.CLAMP_CENTRES[0], 0)
        for a in (-angle / 2, angle / 2):
            rotation = App.Rotation(App.Vector(0, 0, 1), a)
            displacement = rotation.multVec(anchor) - anchor
            shift = math.sqrt(s.MAX_RADIAL_FLOAT**2 - displacement.Length**2)
            tangent = App.Vector(-displacement.y, displacement.x, 0)
            tangent.normalize()
            for sign in (-1, 1):
                pose = App.Placement(tangent * (sign * shift), rotation)
                for x, y in s.CLAMP_CENTRES:
                    axis = App.Vector(x, y, 0)
                    self.assertLessEqual(
                        (pose.multVec(axis) - axis).Length, s.MAX_RADIAL_FLOAT + 1e-7
                    )
                poses.append(pose)
        for obj in self.kit["hardware"]:
            if not obj.Name.startswith("OpticalStackFoot"):
                continue
            key = obj.Name.removeprefix("OpticalStackFoot")
            for pose in poses:
                moved = obj.Shape.copy()
                moved.Placement = pose.multiply(moved.Placement)
                with self.subTest(object=obj.Name, pose=pose):
                    self.assertLess(abs(moved.cut(bounds[key]).Volume), 1e-5)

    def test_accessory_registration_clears_rail_and_mini_in_both_clamp_directions(self):
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import equipment_envelopes, rail, wiring_reserves
        from gondola.parts import stack_interface as s

        host = "AccessoryEquipmentModule"
        datum = s.host_placement(host, s.STACK_TOP_Z)
        obstacles = {"Mini": equipment_envelopes.radio_envelope_shape()}
        obstacles.update(
            (name, shape)
            for name, shape in wiring_reserves.reserve_shapes().items()
            if name.startswith("Radio")
        )
        station = next(item for item in MODULE_STATIONS if item.object_name == host)
        components = s.rigid_float_component_bounds() + s.clamp_hardware_float_bounds()
        for name, shape in components:
            placed = shape.copy()
            placed.Placement = datum.multiply(placed.Placement)
            for obstacle, target in obstacles.items():
                with self.subTest(component=name, obstacle=obstacle):
                    self.assertGreaterEqual(placed.distToShape(target)[0], 1.5 - 1e-5)
            for side in (-1, 1):
                pose = App.Placement(
                    App.Vector(station.x_mm, side * rail.CLAMP_SHIFT_Y, 0),
                    App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
                )
                world = placed.copy()
                world.Placement = pose.multiply(world.Placement)
                with self.subTest(component=name, clamp_side=side):
                    self.assertGreaterEqual(
                        world.distToShape(rail.rail_shape())[0], 1.5 - 1e-5
                    )


if __name__ == "__main__":
    unittest.main()
