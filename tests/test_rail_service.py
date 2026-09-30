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

    def test_wrench_can_grasp_nut_but_not_pass_through_an_obstruction(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import nut_wrench_clearance

        obstacles = {
            "Nut": rail.nut_shape(),
            "Rail": rail.rail_shape(),
            "Mount": rail.mount_base_shape(),
        }
        self.assertTrue(nut_wrench_clearance(0, obstacles)["passed"])
        obstacles["Block"] = Part.makeBox(1, 2, 1, App.Vector(15, 1.3, 6))
        self.assertFalse(nut_wrench_clearance(0, obstacles)["passed"])

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
