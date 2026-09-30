"""Side service includes complete tools and their approach, with devices retained."""

import unittest
from types import SimpleNamespace

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailServiceTests(unittest.TestCase):
    def test_low_reference_part_does_not_acquire_a_phantom_clamp_bore_fill(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import _lift_path

        reference = Part.makeBox(2, 2, 2, App.Vector(20, 10, 3))
        report = _lift_path("Reference", reference, {"Rail": rail.rail_shape()}, 0)
        self.assertTrue(report["passed"], report)

    def test_carried_board_does_not_obstruct_side_access(self):
        from gondola.parts import equipment_mounts, rail
        from gondola.validation.rail_access import side_driver_clearance

        report = side_driver_clearance(
            rail.attachment_screw_shape(),
            {
                "Carrier": equipment_mounts.mount_shape("electronics"),
                "FC": Part.makeBox(30, 30, 5, App.Vector(-15, -15, 24)),
            },
        )
        self.assertTrue(report["passed"], report)

    def test_handle_approach_includes_intermediate_obstacles(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import side_driver_clearance

        report = side_driver_clearance(
            rail.attachment_screw_shape(),
            {
                "Block": Part.makeBox(1, 1, 1, App.Vector(4, -200, 6)),
            },
        )
        self.assertFalse(report["passed"])

    def test_through_hex_window_restrains_nut_without_an_external_wrench(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import nut_capture_check

        nut, mount = rail.nut_shape(), rail.mount_base_shape()
        report = nut_capture_check(0, nut, mount)
        self.assertTrue(report["passed"], report)
        self.assertFalse(report["external_holding_wrench_required"])
        self.assertAlmostEqual(report["nominal_nut_to_guard_overlap_mm3"], 0)
        self.assertTrue(
            all(row["rotation_block_mm3"] > 0.1 for row in report["rotation_limits"])
        )
        missing_guard = mount.cut(Part.makeBox(16, 3, 11, App.Vector(-8, 1.4, 2)))
        self.assertFalse(nut_capture_check(0, nut, missing_guard)["passed"])

    def test_recessed_nut_removal_rejects_an_obstacle_between_endpoints(self):
        from gondola.parts import rail
        from gondola.validation.propulsion_service import continuous_path

        nut = rail.nut_shape()
        obstacles = {"Rail": rail.rail_shape(), "Mount": rail.mount_base_shape()}
        path = [(0, 0, 0), (0, 4, 0)]
        self.assertTrue(continuous_path(nut, path, obstacles)["passed"])
        obstacles["Block"] = Part.makeBox(0.3, 0.1, 0.3, App.Vector(2, 5, 7))
        self.assertFalse(continuous_path(nut, path, obstacles)["passed"])

    def test_populated_u_saddle_lifts_over_the_rail_without_flexing(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import _lift_path

        result = _lift_path(
            "BatteryMount", rail.mount_base_shape(), {"Rail": rail.rail_shape()}, 0
        )
        self.assertTrue(result["passed"], result)

    def test_missing_neighbour_duplicate_or_lookalike_cannot_pass_inventory(self):
        from gondola.validation.rail_access import (
            _service_inventory,
            rail_attachment_service,
        )

        first, neighbour = (
            SimpleNamespace(Name="Carrier"),
            SimpleNamespace(Name="Neighbour"),
        )
        registry = SimpleNamespace(
            PrintedParts=[first],
            ReferenceParts=[neighbour],
            HardwareParts=[],
            TapeReferences=[],
        )
        doc = SimpleNamespace(
            getObject=lambda name: {"Carrier": first, "Neighbour": neighbour}.get(name)
        )
        self.assertTrue(_service_inventory(doc, registry, [first, neighbour])["passed"])
        for objects in (
            [first],
            [first, neighbour, neighbour],
            [first, SimpleNamespace(Name="Neighbour")],
        ):
            with self.subTest(objects=objects):
                report = rail_attachment_service(doc, registry, objects)
                self.assertFalse(report["passed"])
                self.assertFalse(report["obstacle_inventory"]["passed"])

    def test_saved_non_neutral_settings_are_reported_without_moving_stages(self):
        from gondola.validation.rail_access import _saved_stage_settings

        pod = SimpleNamespace(
            Tilt=999,
            Placement=App.Placement(
                App.Vector(), App.Rotation(App.Vector(0, 1, 0), 180)
            ),
        )
        stage = SimpleNamespace(
            Pitch=-12,
            Placement=App.Placement(
                App.Vector(), App.Rotation(App.Vector(0, 1, 0), -12)
            ),
        )
        objects = {"PortPod": pod, "OpticalPitchStage": stage}
        doc = SimpleNamespace(getObject=objects.get)
        report = _saved_stage_settings(doc)
        self.assertEqual(report["PortPod"]["commanded_angle_deg"], 999)
        self.assertEqual(
            report["PortPod"]["actual_local_rotation_quaternion_xyzw"],
            list(pod.Placement.Rotation.Q),
        )
        self.assertEqual(report["OpticalPitchStage"]["commanded_angle_deg"], -12)
        self.assertEqual(pod.Tilt, 999)
        self.assertEqual(stage.Pitch, -12)


if __name__ == "__main__":
    unittest.main()
