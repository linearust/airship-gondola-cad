"""Native seating, clearance and removal checks for the shared-slot pedestal."""

import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class OpticalInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import (
            equipment_mounts,
            optical_interface,
            optical_mount,
            optical_sensor,
        )

        cls.doc = App.newDocument("CompactOpticalInterface")
        cls.hosts = {}
        cls.carriers = []
        for index, (name, kind) in enumerate(
            (
                ("BatteryEquipmentModule", "battery"),
                ("ElectronicsEquipmentModule", "electronics"),
            )
        ):
            host = cls.doc.addObject("App::Part", name)
            host.Placement = App.Placement(
                App.Vector(index * 100, 0, 0),
                App.Rotation(App.Vector(0, 0, 1), 180 * index),
            )
            cls.hosts[name] = host
            cls.carriers.append(equipment_mounts.build_mount(cls.doc, host, kind))
        cls.kit = optical_mount.build_optical_mount(
            cls.doc, cls.hosts["BatteryEquipmentModule"]
        )
        optical_interface.attach_to_host(
            cls.kit["group"], cls.hosts["BatteryEquipmentModule"]
        )
        cls.refs, cls.reserves = optical_sensor.build_sensor(
            cls.doc, cls.kit["pitch_stage"]
        )
        cls.moving = cls.kit["printed"] + cls.kit["hardware"] + cls.refs
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def setUp(self):
        from gondola.parts import optical_interface, optical_mount

        optical_interface.attach_to_host(
            self.kit["group"], self.hosts["BatteryEquipmentModule"]
        )
        optical_mount.set_pitch(self.doc, 0)

    def test_foot_fasteners_share_one_standard_slot_and_seat_on_both_carriers(self):
        from gondola.parts import mounting_slots
        from gondola.parts import optical_interface as interface
        from gondola.validation.optical import pedestal_attachment_check

        axes = [
            (x + interface.HOST_ORIGIN_XY[0], y + interface.HOST_ORIGIN_XY[1])
            for x, y in interface.CLAMP_CENTRES
        ]
        endpoints = [
            tuple(row[key])
            for row in mounting_slots.rows()
            if row["kind"] == "straight"
            for key in ("start_xy_mm", "end_xy_mm")
        ]
        for axis in axes:
            self.assertIn(axis, endpoints)
        for host in self.hosts.values():
            interface.attach_to_host(self.kit["group"], host)
            report = pedestal_attachment_check(self.doc, host)
            self.assertTrue(report["passed"], report)
            self.assertGreater(report["nominal_seat_contact_area_mm2"], 80)
            self.assertEqual(len(report["clamps"]), 2)

    def test_missing_contact_or_shortened_screw_fails(self):
        from gondola.validation.optical import pedestal_attachment_check

        host = self.hosts["BatteryEquipmentModule"]
        group = self.kit["group"]
        original = group.Placement.copy()
        try:
            group.Placement.Base.z += 0.1
            self.doc.recompute()
            self.assertFalse(pedestal_attachment_check(self.doc, host)["passed"])
        finally:
            group.Placement = original
        bolt = self.doc.OpticalFootBolt0
        original_shape = bolt.Shape.copy()
        try:
            cut = Part.makeBox(20, 20, 20, App.Vector(-10, -15, 3))
            bolt.Shape = original_shape.cut(cut)
            self.assertFalse(pedestal_attachment_check(self.doc, host)["passed"])
        finally:
            bolt.Shape = original_shape

    def test_carrier_removal_uses_outboard_slide_before_lift(self):
        from gondola.cad import world_shape
        from gondola.validation.optical import _pedestal_service_check

        fixed = {obj.Name: world_shape(obj) for obj in self.carriers}
        result = _pedestal_service_check(self.doc, fixed, self.moving)
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["clamp_hardware_removal"]), 4)
        for row in result["whole_pedestal_slide_then_lift"]:
            self.assertEqual(row["outboard_travel_mm"], 20)
            self.assertEqual(row["lift_after_slide_mm"], 40)

    def test_unknown_obstacle_in_outboard_slide_is_not_filtered_away(self):
        from gondola.cad import world_shape
        from gondola.validation.optical import _pedestal_service_check

        group = self.kit["group"]
        obstacle = Part.makeBox(1, 1, 1, App.Vector(12, 0, 1))
        obstacle.Placement = group.getGlobalPlacement()
        fixed = {obj.Name: world_shape(obj) for obj in self.carriers}
        fixed["UnknownServiceObstacle"] = obstacle
        report = _pedestal_service_check(self.doc, fixed, self.moving)
        self.assertFalse(report["passed"])
        self.assertIn(
            "UnknownServiceObstacle",
            report["bench_service_frame"]["retained_obstacles"],
        )
        hits = [
            hit["object"]
            for row in report["whole_pedestal_slide_then_lift"]
            for hit in row["collisions"]
        ]
        self.assertIn("UnknownServiceObstacle", hits)

    def test_registration_bounds_contain_continuous_cell_edge_poses(self):
        from gondola.parts import optical_interface as interface
        from gondola.parts import optical_mount

        bound = Part.makeCompound(
            [shape for _, shape in interface.rigid_float_component_bounds()]
        )
        for fraction in (-1, -0.5, 0, 0.5, 1):
            for sx, sy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                shape = optical_mount.base_shape()
                angle = fraction * interface.MAX_REGISTRATION_YAW_RAD
                shape.rotate(App.Vector(), App.Vector(0, 0, 1), math.degrees(angle))
                shape.translate(
                    App.Vector(
                        sx * interface.MAX_REGISTRATION_X,
                        sy * interface.MAX_REGISTRATION_Y,
                        0,
                    )
                )
                self.assertLess(abs(shape.cut(bound).Volume), 1e-5, (fraction, sx, sy))

    def test_reject_unsupported_host_without_mutating_parent(self):
        from gondola.parts import optical_interface

        original = self.kit["group"].getParentGeoFeatureGroup()
        wrong = self.doc.addObject("App::Part", "WrongOpticalHost")
        try:
            with self.assertRaises(ValueError):
                optical_interface.attach_to_host(self.kit["group"], wrong)
            self.assertIs(self.kit["group"].getParentGeoFeatureGroup(), original)
        finally:
            self.doc.removeObject(wrong.Name)


if __name__ == "__main__":
    unittest.main()
