"""Side service includes complete tools and their approach, with devices retained."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

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

    def test_blind_hex_pocket_supports_and_restrains_nut_without_wrench(self):
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
        self.assertLess(result["shape_outside_service_envelope_mm3"], 1e-5)
        self.assertTrue(
            all(
                "face-prism" in segment["method"]
                for row in result["regions"]
                for segment in row["segments"]
            )
        )

    def test_both_shared_frame_legs_preserve_the_open_channel_during_service(self):
        from gondola.cad import translated_shape
        from gondola.parts import propulsion, rail
        from gondola.validation.rail_access import _lift_path

        result = _lift_path(
            "PropulsionFixedFrame",
            propulsion.fixed_frame_shape(),
            {"Rail": translated_shape(rail.rail_shape(), x=17)},
            17,
            waypoints=[(0, 0, 0), (10, 0, 0), (10, 0, 30)],
        )
        self.assertTrue(result["passed"], result)
        self.assertLess(result["shape_outside_service_envelope_mm3"], 1e-5)
        lower = next(
            row for row in result["regions"] if row["region"].endswith("Lower")
        )
        self.assertTrue(
            all("face-prism" in segment["method"] for segment in lower["segments"])
        )

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

    def source_propulsion_service(self):
        """Real two-foot geometry, isolated from unrelated equipment in this test."""
        from gondola.cad import set_property
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import propulsion, rail, servo_bridge
        from gondola.validation import baseline, rail_access

        station = next(
            row for row in MODULE_STATIONS if row.object_name == "MainPropulsionModule"
        )
        doc = App.newDocument("TwoPointRailService")
        self.addCleanup(lambda: App.closeDocument(doc.Name))
        module = doc.addObject("App::Part", station.object_name)
        module.Placement.Base = App.Vector(-17, 0, 0)
        for name, value, kind in (
            ("RailPositionX", -17, "App::PropertyDistance"),
            ("RailAttachmentOffsetX", 17, "App::PropertyDistance"),
            ("RailAttachmentOffsetsX", [17, -17], "App::PropertyFloatList"),
            ("RailContactLength", 24, "App::PropertyLength"),
        ):
            set_property(module, name, value, kind)
        printed = []
        for name, shape, parent in (
            ("ContinuousRail", rail.rail_shape(), None),
            ("PropulsionFixedFrame", propulsion.fixed_frame_shape(), module),
            ("ServoDriveBridge", servo_bridge.bridge_shape(), module),
        ):
            obj = doc.addObject("Part::Feature", name)
            obj.Shape = shape
            if parent:
                parent.addObject(obj)
            printed.append(obj)
        hardware = rail.build_attachment_hardware(
            doc, module, module.Name, x_offset=17, shared_drive=True
        )
        registry = doc.addObject("App::FeaturePython", "DesignRegistry")
        for name, objects in (
            ("Modules", [module]),
            ("PrintedParts", printed),
            ("ReferenceParts", []),
            ("HardwareParts", hardware),
            ("RailLocks", hardware),
            ("TapeReferences", []),
        ):
            set_property(registry, name, objects, "App::PropertyLinkList")
        doc.recompute()

        def report():
            objects = (
                list(registry.PrintedParts)
                + list(registry.ReferenceParts)
                + list(registry.HardwareParts)
            )
            stations = tuple(
                row
                for row in MODULE_STATIONS
                if row.object_name in {obj.Name for obj in registry.Modules}
            )
            with (
                patch.object(baseline, "MODULE_STATIONS", stations),
                patch.object(rail_access, "MODULE_STATIONS", stations),
            ):
                return rail_access.rail_attachment_service(doc, registry, objects)

        return doc, report

    def test_two_shared_clamps_release_in_order_then_both_feet_lift(self):
        _, check = self.source_propulsion_service()
        report = check()
        self.assertTrue(report["passed"], report)
        row = report["modules"][0]
        sites = row["attachment_services"]
        self.assertEqual(len(sites), 2)
        self.assertEqual([site["attachment_side"] for site in sites], [1, -1])
        self.assertEqual(sites[0]["previously_removed_attachment_hardware"], [])
        self.assertEqual(len(sites[0]["other_attachment_hardware_retained"]), 2)
        self.assertEqual(
            sites[1]["previously_removed_attachment_hardware"],
            sorted([sites[0]["screw"], sites[0]["nut"]]),
        )
        self.assertEqual(len(row["removed_attachment_hardware"]), 4)

    def test_deleted_saved_mounts_fail_before_constructing_service_shapes(self):
        from gondola.config import BASELINE_FILE
        from gondola.provenance import file_sha256
        from gondola.validation import rail_access

        before = file_sha256(BASELINE_FILE)
        doc = App.openDocument(str(BASELINE_FILE), hidden=True)
        try:
            for part, module in (
                ("BatteryMount", "BatteryEquipmentModule"),
                ("ElectronicsMount", "ElectronicsEquipmentModule"),
                ("AccessoryMount", "AccessoryEquipmentModule"),
                ("PropulsionFixedFrame", "MainPropulsionModule"),
            ):
                with self.subTest(part=part):
                    doc.removeObject(part)
                    doc.recompute()
                    registry = doc.DesignRegistry
                    objects = [
                        obj
                        for key in (
                            "PrintedParts",
                            "ReferenceParts",
                            "HardwareParts",
                            "TapeReferences",
                        )
                        for obj in getattr(registry, key)
                    ]
                    with patch.object(rail_access, "world_shape") as geometry:
                        report = rail_access.rail_attachment_service(
                            doc, registry, objects
                        )
                    geometry.assert_not_called()
                    self.assertFalse(report["passed"])
                    row = next(
                        row for row in report["modules"] if row["module"] == module
                    )
                    self.assertEqual(row["required_mount"]["object"], part)
                    self.assertFalse(row["required_mount"]["present"])
        finally:
            App.closeDocument(doc.Name)
            self.assertEqual(file_sha256(BASELINE_FILE), before)

    def test_required_mount_must_be_registered_valid_and_in_its_module(self):
        from gondola.validation import rail_access

        for defect in ("unregistered", "wrong_parent", "empty_shape"):
            with self.subTest(defect=defect):
                doc, check = self.source_propulsion_service()
                frame = doc.PropulsionFixedFrame
                if defect == "unregistered":
                    doc.DesignRegistry.PrintedParts = [
                        obj for obj in doc.DesignRegistry.PrintedParts if obj != frame
                    ]
                elif defect == "wrong_parent":
                    other = doc.addObject("App::Part", "WrongModule")
                    other.addObject(frame)
                else:
                    frame.Shape = Part.Shape()
                with patch.object(rail_access, "world_shape") as geometry:
                    report = check()
                geometry.assert_not_called()
                self.assertFalse(report["passed"])
                self.assertEqual(
                    report["modules"][0]["error"], "Invalid required rail mount"
                )

    def test_invalid_native_controls_stop_service_before_constructing_shapes(self):
        from gondola.validation import rail_access

        doc, check = self.source_propulsion_service()
        for value in (0, 8, float("nan")):
            with self.subTest(contact_length=value):
                doc.MainPropulsionModule.RailContactLength = value
                with patch.object(rail_access, "world_shape") as geometry:
                    report = check()
                geometry.assert_not_called()
                self.assertFalse(report["passed"])
                self.assertIn(
                    "RailContactLength",
                    report["modules"][0]["native_attachment_pose"]["invalid_controls"],
                )

    def test_shared_nut_support_must_exist_be_registered_and_belong_to_module(self):
        from gondola.validation import rail_access

        for defect in ("missing", "unregistered", "wrong_parent", "empty_shape"):
            with self.subTest(defect=defect):
                doc, check = self.source_propulsion_service()
                bridge = doc.ServoDriveBridge
                if defect == "missing":
                    doc.removeObject(bridge.Name)
                elif defect == "unregistered":
                    doc.DesignRegistry.PrintedParts = [
                        obj for obj in doc.DesignRegistry.PrintedParts if obj != bridge
                    ]
                elif defect == "wrong_parent":
                    # Detach the registry link while moving one print: FreeCAD
                    # otherwise reparents the registry's other linked prints.
                    printed = list(doc.DesignRegistry.PrintedParts)
                    doc.DesignRegistry.PrintedParts = [
                        obj for obj in printed if obj != bridge
                    ]
                    doc.addObject("App::Part", "WrongModule").addObject(bridge)
                    doc.DesignRegistry.PrintedParts = printed
                else:
                    bridge.Shape = Part.Shape()
                doc.recompute()
                with patch.object(rail_access, "world_shape") as geometry:
                    report = check()
                geometry.assert_not_called()
                self.assertFalse(report["passed"])
                row = report["modules"][0]
                self.assertEqual(row["error"], "Invalid required rail mount")
                self.assertEqual(row["required_mount"]["object"], "ServoDriveBridge")

    def test_populated_propulsion_slides_clear_of_fc_carrier_before_lifting(self):
        from gondola.cad import placed_shape, world_shape
        from gondola.parts import equipment_mounts
        from gondola.validation.rail_access import _lift_path

        doc, check = self.source_propulsion_service()
        neighbour = doc.addObject("Part::Feature", "ElectronicsMount")
        neighbour.Shape = equipment_mounts.mount_shape("electronics")
        neighbour.Placement = App.Placement(
            App.Vector(-70, 0, 0), App.Rotation(App.Vector(0, 0, 1), 180)
        )
        doc.DesignRegistry.PrintedParts = list(doc.DesignRegistry.PrintedParts) + [
            neighbour
        ]
        doc.recompute()
        inverse = doc.MainPropulsionModule.getGlobalPlacement().inverse()
        obstacles = {neighbour.Name: placed_shape(world_shape(neighbour), inverse)}
        direct = _lift_path(
            "ServoDriveBridge", doc.ServoDriveBridge.Shape, obstacles, 17
        )
        self.assertFalse(direct["passed"], direct)
        report = check()
        self.assertTrue(report["passed"], report)
        row = report["modules"][0]
        self.assertEqual(
            row["populated_module_removal_path_mm"],
            [(0, 0, 0), (10, 0, 0), (10, 0, 30)],
        )
        self.assertTrue(row["unclamped_propulsion_held_during_rail_slide"])
        bridge = next(
            part
            for part in row["populated_module_lift"]
            if part["part"] == "ServoDriveBridge"
        )
        self.assertLess(bridge["bridge_outside_stock_mm3"], 1e-5)
        self.assertEqual(len(bridge["regions"]), 8)

    def test_bridge_stock_sweeps_cannot_omit_an_unexpected_saved_protrusion(self):
        from gondola.parts import servo_bridge
        from gondola.validation.rail_access import _lift_path

        bridge = servo_bridge.bridge_shape().fuse(
            Part.makeBox(1, 1, 1, App.Vector(29.5, -1, 14))
        )
        report = _lift_path(
            "ServoDriveBridge",
            bridge,
            {},
            17,
            waypoints=[(0, 0, 0), (10, 0, 0), (10, 0, 30)],
        )
        self.assertFalse(report["passed"])
        self.assertGreater(report["bridge_outside_stock_mm3"], 0.7)

    def test_carrier_stock_sweeps_cannot_omit_an_unexpected_saved_protrusion(self):
        from gondola.parts import equipment_mounts
        from gondola.validation.rail_access import _lift_path

        carrier = equipment_mounts.mount_shape("electronics").fuse(
            Part.makeBox(1, 1, 1, App.Vector(20, 0, 16.4))
        )
        report = _lift_path(
            "ElectronicsMount",
            carrier,
            {},
            0,
            waypoints=[(0, 0, 0), (4, 0, 0), (4, 0, 30)],
        )
        self.assertFalse(report["passed"])
        self.assertGreater(report["shape_outside_service_envelope_mm3"], 0.5)

    def test_populated_fc_carrier_slides_away_from_retained_starboard_adapter(self):
        from gondola.cad import placed_shape, set_property, world_shape
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.parts import equipment_mounts, rail, servo_coupling
        from gondola.validation.rail_access import _lift_path

        doc, check = self.source_propulsion_service()
        module = doc.addObject("App::Part", "ElectronicsEquipmentModule")
        module.Placement = App.Placement(
            App.Vector(-70, 0, 0), App.Rotation(App.Vector(0, 0, 1), 180)
        )
        for name, value, kind in (
            ("RailPositionX", -70, "App::PropertyDistance"),
            ("RailAttachmentOffsetX", 0, "App::PropertyDistance"),
            ("RailAttachmentOffsetsX", [0], "App::PropertyFloatList"),
            ("RailContactLength", 16, "App::PropertyLength"),
        ):
            set_property(module, name, value, kind)
        carrier = doc.addObject("Part::Feature", "ElectronicsMount")
        module.addObject(carrier)
        carrier.Shape = equipment_mounts.mount_shape("electronics")
        adapter = doc.addObject("Part::Feature", "StarboardHornGearAdapter")
        doc.MainPropulsionModule.addObject(adapter)
        shape = servo_coupling.adapter_shape()
        shape.translate(App.Vector(0, servo_coupling.HORN_BOTTOM_Y, 0))
        shape.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
        shape.translate(
            App.Vector(-SELECTED_DRIVE.input_x_mm, 0, SELECTED_DRIVE.input_z_mm)
        )
        adapter.Shape = shape
        hardware = rail.build_attachment_hardware(doc, module, module.Name)
        registry = doc.DesignRegistry
        registry.Modules = list(registry.Modules) + [module]
        registry.PrintedParts = list(registry.PrintedParts) + [carrier, adapter]
        registry.HardwareParts = list(registry.HardwareParts) + hardware
        registry.RailLocks = list(registry.RailLocks) + hardware
        doc.recompute()
        inverse = module.getGlobalPlacement().inverse()
        retained = {adapter.Name: placed_shape(world_shape(adapter), inverse)}
        direct = _lift_path(carrier.Name, carrier.Shape, retained, 0)
        self.assertFalse(direct["passed"], direct)
        literal_at_twenty = carrier.Shape.copy()
        literal_at_twenty.translate(App.Vector(0, 0, 20))
        self.assertGreater(
            abs(literal_at_twenty.common(retained[adapter.Name]).Volume), 1
        )
        result = check()
        self.assertTrue(result["passed"], result)
        row = next(row for row in result["modules"] if row["module"] == module.Name)
        self.assertEqual(
            row["populated_module_removal_path_mm"], [(0, 0, 0), (4, 0, 0), (4, 0, 30)]
        )
        self.assertTrue(row["unclamped_module_held_during_rail_slide"])
        self.assertEqual(row["other_modules_removed"], [])

    def test_opposite_pair_must_be_registered_for_service(self):
        doc, check = self.source_propulsion_service()
        doc.DesignRegistry.RailLocks = [
            obj for obj in doc.DesignRegistry.RailLocks if "Opposite" not in obj.Name
        ]
        report = check()
        self.assertFalse(report["passed"])
        self.assertEqual(
            report["modules"][0]["error"], "Rail attachment inventory mismatch"
        )

    def test_opposite_side_driver_path_cannot_be_inferred_from_first_side(self):
        doc, check = self.source_propulsion_service()
        block = doc.addObject("Part::Feature", "OppositeDriverObstacle")
        block.Shape = Part.makeBox(1, 1, 1, App.Vector(-34.5, 20, 6.5))
        doc.DesignRegistry.ReferenceParts = [block]
        doc.recompute()
        report = check()
        self.assertFalse(report["passed"])
        sites = report["modules"][0]["attachment_services"]
        self.assertTrue(sites[0]["side_driver_access"]["passed"])
        self.assertFalse(sites[1]["side_driver_access"]["passed"])

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
