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
        from gondola.contracts.design import MODULE_STATIONS
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
                row for row in MODULE_STATIONS if row.object_name == group.Name
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
        kit = optical_mount.build_optical_mount(doc)
        self.assertEqual(str(kit["group"].OpticalAttachmentMode), "rail")
        self.assertIsNone(kit["group"].getParentGeoFeatureGroup())
        self.assertNotIn("CarrierHostName", kit["group"].PropertiesList)
        self.assertNotIn("MountSide", kit["group"].PropertiesList)
        self.assertEqual(len(kit["hardware"]), 2)
        self.assertIsNone(doc.getObject("OpticalFootBolt1"))
        self.assertEqual(doc.OpticalMountBase.PrintSKU, "OpticalRailBase")
        self.assertEqual(tuple(kit["pitch_stage"].Placement.Base), (0, 0, 42))
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
                self.assertEqual(len(result["objects"]), 9)
                self.assertEqual(
                    doc.OpticalMountBase.PrintSKU,
                    "OpticalRailBase" if mode == "rail" else "OpticalCarrierBase",
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

    def test_each_base_preserves_literal_post_ear_and_buttress_stock(self):
        from gondola.parts import optical_mount

        for mode, bottom, pivot, depth in (
            ("carrier", 2, 23, 2),
            ("rail", 12.5, 42, 4),
        ):
            with self.subTest(mode=mode):
                shape = optical_mount.base_shape(mode)
                bore = Part.makeCylinder(
                    1.1, 3, App.Vector(0, -3, pivot), App.Vector(0, 1, 0)
                )
                post = Part.makeBox(
                    8, 3, pivot - bottom, App.Vector(-4, -3, bottom)
                ).cut(bore)
                ear = Part.makeCylinder(
                    4, 3, App.Vector(0, -3, pivot), App.Vector(0, 1, 0)
                ).cut(bore)
                points = [
                    App.Vector(-4, 0, bottom),
                    App.Vector(-4, depth, bottom),
                    App.Vector(-4, 0, bottom + 10),
                ]
                buttress = Part.Face(Part.makePolygon(points + points[:1])).extrude(
                    App.Vector(8, 0, 0)
                )
                for name, stock in (
                    ("post", post),
                    ("ear", ear),
                    ("buttress", buttress),
                ):
                    self.assertLess(abs(stock.cut(shape).Volume), 1e-5, name)
                self.assertLess(abs(shape.common(bore).Volume), 1e-5)
                self.assertEqual(len(shape.Solids), 1)

    def test_source_check_rejects_missing_post_and_swapped_attachment_base(self):
        from gondola.parts import optical_mount
        from gondola.validation.optical import _source_evidence

        doc, _ = self.make_document("rail")
        original = doc.OpticalMountBase.Shape.copy()
        defect = Part.makeBox(2, 3, 2, App.Vector(-1, -3, 30))
        self.assertAlmostEqual(original.common(defect).Volume, 12)
        for shape in (original.cut(defect), optical_mount.base_shape("carrier")):
            doc.OpticalMountBase.Shape = shape
            result = _source_evidence(doc)
            self.assertFalse(result["passed"])
            self.assertFalse(
                next(
                    row
                    for row in result["objects"]
                    if row["object"] == "OpticalMountBase"
                )["passed"]
            )

    def test_both_modes_keep_pitch_tool_and_continuous_bench_service(self):
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
                for pitch in (-20, 0, 20):
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
                self.assertAlmostEqual(result["paths"][0]["translation_mm"][1], 3.7)
                self.assertEqual(
                    len(result["previously_removed_attachment_fasteners"]), 2
                )

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
