"""Both optical attachment choices bind real stock, controls and ordered service."""

import json
import unittest
from dataclasses import asdict

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class OpticalAttachmentModeTests(unittest.TestCase):
    def make_document(self, mode):
        from gondola.cad import set_property
        from gondola.contracts.design import module_stations
        from gondola.parts import optical_mount, optical_sensor, rail

        doc = App.newDocument("OpticalAttachmentMode")
        self.addCleanup(App.closeDocument, doc.Name)
        host = (
            doc.addObject("App::Part", "BatteryEquipmentModule")
            if mode == "carrier"
            else None
        )
        kit = optical_mount.build_optical_mount(doc, host, mode=mode)
        group = kit["group"]
        hardware = list(kit["hardware"])
        locks = []
        if mode == "rail":
            station = next(
                row for row in module_stations(mode) if row.object_name == group.Name
            )
            for name, value, kind in (
                ("RailPositionX", station.x_mm, "App::PropertyDistance"),
                ("RailAttachmentOffsetX", 0, "App::PropertyDistance"),
                ("RailAttachmentOffsetsX", [0], "App::PropertyFloatList"),
                ("RailContactLength", 16, "App::PropertyLength"),
            ):
                set_property(group, name, value, kind)
            set_property(group, "ModulePlacementContract", json.dumps(asdict(station)))
            set_property(
                group, "RailAttachmentContract", json.dumps(rail.attachment_contract())
            )
            group.Placement.Rotation = App.Rotation(
                App.Vector(0, 0, 1), station.yaw_deg
            )
            group.setExpression("Placement.Base.x", "RailPositionX")
            locks = rail.build_attachment_hardware(doc, group, group.Name)
            hardware += locks
        refs, reserves = optical_sensor.build_sensor(doc, kit["pitch_stage"])
        registry = doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        for name, objects in (
            ("PrintedParts", kit["printed"]),
            ("HardwareParts", hardware),
            ("ReferenceParts", refs),
            ("ClearanceVolumes", reserves),
            ("FitCoupons", []),
            ("EquipmentMounts", []),
            ("OpticalMountParts", kit["printed"]),
            ("TapeReferences", []),
            ("RailLocks", locks),
            ("Modules", [host] if mode == "carrier" else [group]),
        ):
            registry.addProperty("App::PropertyLinkListGlobal", name)
            setattr(registry, name, objects)
        doc.recompute()
        return doc, kit["printed"] + hardware + refs

    def test_attachment_inference_and_wrong_host_are_explicit(self):
        from gondola.parts import optical_mount

        doc = App.newDocument("OpticalModeInference")
        self.addCleanup(App.closeDocument, doc.Name)
        with self.assertRaises(ValueError):
            optical_mount.build_optical_mount(doc)
        kit = optical_mount.build_optical_mount(doc, mode="rail")
        self.assertEqual(str(kit["group"].OpticalAttachmentMode), "rail")
        self.assertIsNone(kit["group"].getParentGeoFeatureGroup())
        self.assertNotIn("CarrierHostName", kit["group"].PropertiesList)
        self.assertNotIn("MountSide", kit["group"].PropertiesList)
        self.assertEqual(len(kit["hardware"]), 0)
        self.assertIsNone(doc.getObject("OpticalFootBolt1"))
        self.assertIsNone(doc.getObject("OpticalMountBase"))
        self.assertEqual(doc.OpticalSensorTray.PrintSKU, "OpticalSensorTray")
        self.assertEqual(tuple(kit["pitch_stage"].Placement.Base), (-12, 1.25, 6.5))
        host = doc.addObject("App::Part", "BatteryEquipmentModule")
        for host_arg, mode in ((host, "rail"), (None, "carrier"), (None, "unknown")):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                optical_mount.build_optical_mount(doc, host_arg, mode=mode)

    def test_both_native_attachments_match_source_and_bind_their_inventory(self):
        from gondola.validation.optical import _source_evidence

        for mode in ("carrier", "rail"):
            doc, _ = self.make_document(mode)
            with self.subTest(mode=mode):
                result = _source_evidence(doc)
                self.assertTrue(result["passed"], result)
                self.assertEqual(result["attachment_controls"]["mode"], mode)
                self.assertEqual(len(result["objects"]), 9 if mode == "carrier" else 6)
                self.assertEqual(doc.OpticalSensorTray.PrintSKU, "OpticalSensorTray")
                self.assertEqual(
                    doc.getObject("OpticalMountBase") is None, mode == "rail"
                )

    def test_missing_or_conflicting_mode_and_controls_fail_closed(self):
        from gondola.validation.optical import _source_evidence

        doc, _ = self.make_document("rail")
        self.assertTrue(_source_evidence(doc)["passed"])
        group = doc.OpticalFlowModule
        group.addProperty("App::PropertyString", "CarrierHostName")
        group.CarrierHostName = "BatteryEquipmentModule"
        self.assertFalse(_source_evidence(doc)["passed"])
        group.removeProperty("CarrierHostName")
        group.setExpression("Placement.Base.x", None)
        self.assertFalse(_source_evidence(doc)["passed"])
        group.setExpression("Placement.Base.x", "RailPositionX")
        locks = list(doc.DesignRegistry.RailLocks)
        doc.DesignRegistry.RailLocks = locks[:-1]
        self.assertFalse(_source_evidence(doc)["passed"])
        doc.DesignRegistry.RailLocks = locks
        group.removeProperty("OpticalAttachmentMode")
        self.assertFalse(_source_evidence(doc)["passed"])

    def test_original_lower_pedestal_and_dual_interface_upper_stock(self):
        from gondola.parts import optical_mount, rail

        shape = optical_mount.base_shape("carrier")
        bore = Part.makeCylinder(1.1, 2, App.Vector(0, -2, 19), App.Vector(0, 1, 0))
        post = Part.makeBox(8, 2, 17, App.Vector(-4, -2, 2)).cut(bore)
        ear = Part.makeCylinder(4, 2, App.Vector(0, -2, 19), App.Vector(0, 1, 0)).cut(
            bore
        )
        points = [App.Vector(-4, 0, 2), App.Vector(-4, 2, 2), App.Vector(-4, 0, 7)]
        buttress = Part.Face(Part.makePolygon(points + points[:1])).extrude(
            App.Vector(8, 0, 0)
        )
        for stock in (post, ear, buttress):
            self.assertLess(abs(stock.cut(shape).Volume), 1e-5)
        self.assertLess(abs(shape.common(bore).Volume), 1e-5)
        with self.assertRaises(ValueError):
            optical_mount.base_shape("rail")
        tray = optical_mount.sensor_tray_shape()
        shoe = rail.mount_base_shape()
        shoe.translate(App.Vector(12, -1.25, -6.5))
        bridge = Part.makeBox(10, 2, 4, App.Vector(-2, 0, 4.5))
        pad_core = Part.makeBox(16, 10, 2, App.Vector(-8, -5, 8.5))
        for stock in (shoe, bridge, pad_core):
            self.assertLess(abs(stock.cut(tray).Volume), 1e-5)
        self.assertEqual(len(tray.Solids), 1)

    def test_source_check_rejects_missing_upper_bridge_and_obsolete_lower_base(self):
        from gondola.parts import optical_mount
        from gondola.validation.optical import _source_evidence

        doc, _ = self.make_document("rail")
        original = doc.OpticalSensorTray.Shape.copy()
        defect = Part.makeBox(1, 1, 1, App.Vector(3, 0.5, 7))
        self.assertAlmostEqual(original.common(defect).Volume, 1)
        doc.OpticalSensorTray.Shape = original.cut(defect)
        self.assertFalse(_source_evidence(doc)["passed"])
        doc.OpticalSensorTray.Shape = original
        obsolete = doc.addObject("Part::Feature", "OpticalMountBase")
        obsolete.Shape = optical_mount.base_shape()
        doc.OpticalFlowModule.addObject(obsolete)
        self.assertFalse(_source_evidence(doc)["passed"])

    def test_fixed_rail_pitch_cannot_be_changed_or_silently_reintroduced(self):
        from gondola.parts import optical_mount
        from gondola.validation.optical import _source_evidence
        from gondola.validation.optical_envelopes import motion_bounds
        from gondola.validation.optical_service import pitch_tool_shape

        doc, _ = self.make_document("rail")
        self.assertTrue(_source_evidence(doc)["passed"])
        self.assertNotIn(
            "OpticalPitchToolAccessBound", motion_bounds(doc.OpticalFlowModule)
        )
        with self.assertRaises(ValueError):
            optical_mount.set_pitch(doc, 1)
        with self.assertRaises(ValueError):
            pitch_tool_shape("rail")
        doc.OpticalPitchStage.Pitch = 1
        doc.recompute()
        self.assertFalse(_source_evidence(doc)["passed"])

    def test_only_carrier_has_pitch_tools_and_disassembly(self):
        from gondola.cad import world_shape
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import optical_mount, optical_sensor
        from gondola.validation.optical_service import (
            pitch_disassembly_check,
            pitch_tool_check,
        )

        for mode in ("carrier", "rail"):
            doc, kit = self.make_document(mode)
            for profile in SENSOR_PROFILES.values():
                optical_sensor.apply_profile(doc, profile)
                for pitch in (-20, 0, 20) if mode == "carrier" else (0,):
                    optical_mount.set_pitch(doc, pitch)
                    result = pitch_tool_check(
                        doc.OpticalFlowModule,
                        {obj.Name: world_shape(obj) for obj in kit},
                    )
                    self.assertTrue(
                        result["passed"], (mode, profile.key, pitch, result)
                    )
                optical_mount.set_pitch(doc, 0)
                result = pitch_disassembly_check(doc, kit)
                self.assertTrue(result["passed"], (mode, profile.key, result))
                self.assertEqual(result["attachment_mode"], mode)
                if mode == "rail":
                    self.assertFalse(result["applicable"])
                    self.assertEqual(result["paths"], [])
                else:
                    self.assertAlmostEqual(result["paths"][0]["translation_mm"][1], 4.7)
                    self.assertEqual(
                        len(result["previously_removed_attachment_fasteners"]), 2
                    )
                    self.assertEqual(
                        next(
                            row
                            for row in result["paths"]
                            if row["part"] == "TrayAssembly/OpticalSensorTray"
                        )["translation_mm"],
                        (0.0, 16.0, 0.0),
                    )

    def test_shared_tray_motion_bound_contains_unused_shoe_at_every_carrier_angle(self):
        from gondola.cad import world_shape
        from gondola.parts import optical_mount
        from gondola.validation.optical_envelopes import motion_bounds

        for mode in ("carrier", "rail"):
            doc, _ = self.make_document(mode)
            bounds = motion_bounds(doc.OpticalFlowModule)
            for angle in range(-20, 21, 2) if mode == "carrier" else (0,):
                optical_mount.set_pitch(doc, angle)
                tray = world_shape(doc.OpticalSensorTray)
                self.assertLess(
                    abs(tray.cut(bounds["MTF02PContinuousTrayBound"]).Volume),
                    1e-5,
                    (mode, angle),
                )

    def test_component_motion_bounds_retain_registration_and_reject_unknown_stock(self):
        import math

        from gondola.cad import placed_shape
        from gondola.parts import optical_interface, optical_mount
        from gondola.validation.optical_envelopes import motion_bounds

        doc, _ = self.make_document("carrier")
        group = doc.OpticalFlowModule
        group.Placement.Base += App.Vector(13, -7, 2)
        bound = motion_bounds(group)["MTF02PContinuousTrayBound"]
        for pitch in (-20, 0, 20):
            for sign_x, sign_y in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                moved = optical_mount.sensor_tray_shape()
                moved.rotate(App.Vector(), App.Vector(0, 1, 0), pitch)
                moved.translate(App.Vector(0, 0, 19))
                moved.rotate(
                    App.Vector(),
                    App.Vector(0, 0, 1),
                    math.degrees(sign_x * optical_interface.MAX_REGISTRATION_YAW_RAD),
                )
                moved.translate(
                    App.Vector(
                        sign_x * optical_interface.MAX_REGISTRATION_X,
                        sign_y * optical_interface.MAX_REGISTRATION_Y,
                        0,
                    )
                )
                moved = placed_shape(moved, group.getGlobalPlacement())
                self.assertLess(
                    abs(moved.cut(bound).Volume), 1e-5, (pitch, sign_x, sign_y)
                )
        # A saved physical branch cannot silently fall outside the source
        # primitives used to refine the broad continuous envelope.
        tray = doc.OpticalSensorTray
        tray.Shape = tray.Shape.fuse(Part.makeBox(2, 1, 1, App.Vector(-10, 0, 9)))
        with self.assertRaisesRegex(ValueError, "tray stock"):
            motion_bounds(group)

    def test_motion_bounds_reject_missing_misparented_or_shifted_saved_tray(self):
        from gondola.validation.optical_envelopes import motion_bounds

        doc, _ = self.make_document("carrier")
        group, stage, tray = (
            doc.OpticalFlowModule,
            doc.OpticalPitchStage,
            doc.OpticalSensorTray,
        )
        before = stage.Placement.copy()
        stage.Placement.Base.x += 0.5
        with self.assertRaisesRegex(ValueError, "pitch domain"):
            motion_bounds(group)
        stage.Placement = before
        group.addObject(tray)
        with self.assertRaisesRegex(ValueError, "hierarchy"):
            motion_bounds(group)
        stage.addObject(tray)
        self.assertIn("MTF02PContinuousTrayBound", motion_bounds(group))
        doc.removeObject(tray.Name)
        with self.assertRaisesRegex(ValueError, "hierarchy"):
            motion_bounds(group)

    def test_unused_shoe_midpath_obstacle_rejects_carrier_tray_removal(self):
        from gondola.cad import world_shape
        from gondola.validation.optical_service import pitch_disassembly_check

        doc, kit = self.make_document("carrier")
        base = doc.OpticalMountBase
        original = base.Shape.copy()
        # Only the outboard unused shoe crosses this point during +Y16.
        # The pad ends at X9; its ear and neck are much farther inboard.
        blocker = Part.makeBox(0.3, 0.3, 0.3, App.Vector(15, 7, 21))
        moving = world_shape(doc.OpticalSensorTray)
        moving.Placement = (
            doc.OpticalFlowModule.getGlobalPlacement()
            .inverse()
            .multiply(moving.Placement)
        )
        self.assertLess(abs(moving.common(blocker).Volume), 1e-5)
        midway = moving.copy()
        midway.translate(App.Vector(0, 4, 0))
        self.assertGreater(abs(midway.common(blocker).Volume), 1e-5)
        moving.translate(App.Vector(0, 16, 0))
        self.assertLess(abs(moving.common(blocker).Volume), 1e-5)
        base.Shape = original.fuse(blocker)
        result = pitch_disassembly_check(doc, kit)
        tray_path = next(
            row
            for row in result["paths"]
            if row["part"] == "TrayAssembly/OpticalSensorTray"
        )
        self.assertFalse(tray_path["passed"], tray_path)
        self.assertIn(
            "OpticalMountBase", [row["object"] for row in tray_path["collisions"]]
        )

    def test_rail_equipment_screens_have_one_pose_and_no_phantom_pitch_tool(self):
        from gondola.validation.equipment_options import _optical_screens

        doc, _ = self.make_document("rail")
        screens = _optical_screens(doc)
        for screen in screens:
            self.assertEqual(len(screen["poses"]), 1)
            pose = screen["poses"][0]
            self.assertEqual(pose["pitch_deg"], 0)
            self.assertNotIn("pitch_tool", pose)
            self.assertNotIn("OpticalMountBase", pose["physical"])
            self.assertIn("OpticalSensorTray", pose["physical"])
            self.assertEqual(len(screen["saved_rail_hardware"]), 2)

    def test_carrier_mode_retains_ordered_foot_release_and_continuous_lift(self):
        from gondola.parts import mounting_plate
        from gondola.validation.optical import _foot_service_checks

        doc, kit = self.make_document("carrier")
        plate = doc.addObject("Part::Feature", "BatteryMount")
        plate.Shape = mounting_plate.shape()
        doc.BatteryEquipmentModule.addObject(plate)
        doc.recompute()
        result = _foot_service_checks(doc, kit + [plate], kit)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["paths"][0]["part"], "OpticalFootNut1")
        self.assertEqual(result["paths"][1]["part"], "OpticalFootBolt1")
        original = plate.Shape.copy()
        # A real shelf above one foot edge blocks lift after both clamps are out.
        from gondola.cad import world_shape

        block = Part.makeBox(1, 2, 1, App.Vector(3, 6, 4))
        block.Placement = doc.OpticalFlowModule.getGlobalPlacement()
        self.assertLess(
            abs(block.common(world_shape(doc.OpticalMountBase)).Volume), 1e-5
        )
        plate.Shape = original.fuse(block)
        blocked = _foot_service_checks(doc, kit + [plate], kit)
        self.assertFalse(blocked["passed"])
        self.assertFalse(
            next(
                row
                for row in blocked["paths"]
                if row["part"] == "CompleteOpticalMount/OpticalMountBase"
            )["passed"]
        )
