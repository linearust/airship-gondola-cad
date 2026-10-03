"""Native independent interface, control and defect checks for the setup platform."""

import json
import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class InstrumentMountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import instrument_mount
        from gondola.validation.instrument import instrument_check

        cls.doc = App.newDocument("InstrumentMountRegression")
        cls.root = cls.doc.addObject("App::Part", "ElectronicsEquipmentModule")
        cls.kit = instrument_mount.build_mount(cls.doc, cls.root)
        cls.positive = instrument_check(cls.doc, include_installed=False)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def setUp(self):
        self.root.Placement = App.Placement()
        self.kit["pitch_stage"].Pitch = 0
        self.doc.recompute()

    def test_two_prints_two_M3_pairs_and_continuous_positive(self):
        self.assertTrue(self.positive["passed"], self.positive)
        self.assertEqual(len(self.kit["printed"]), 2)
        self.assertEqual(len(self.kit["hardware"]), 4)
        self.assertEqual(
            {o.PrintSKU for o in self.kit["printed"]},
            {"InstrumentMountBase", "InstrumentCarrier"},
        )
        self.assertEqual(
            sorted(o.HardwareSKU for o in self.kit["hardware"]),
            ["M3X16_BUTTON_HEAD"] * 2 + ["M3_HEX_NUT"] * 2,
        )
        for obj in self.kit["printed"] + self.kit["hardware"]:
            self.assertTrue(obj.Shape.isValid())
            self.assertEqual(len(obj.Shape.Solids), 1)
        self.assertTrue(all(row["passed"] for row in self.positive["pitch_pairs"]))
        self.assertEqual(len(self.positive["service_paths"]), 8)
        self.assertTrue(self.positive["driver_access_at_every_setup_angle"])
        self.assertEqual(
            {
                r["fixed"]
                for r in self.positive["pitch_pairs"]
                if r["fixed"].endswith("Driver")
            },
            {"InstrumentPivotDriver", "InstrumentLockDriver"},
        )

    def test_actual_standard_shoe_service_regions_keep_channel_and_all_stock(self):
        from gondola.cad import placed_shape
        from gondola.parts import instrument_mount, rail
        from gondola.validation.rail_access import _lift_path

        rail_shape = rail.rail_shape()
        for obj in self.kit["printed"]:
            shape = (
                obj.Shape
                if obj.Name == "InstrumentMountBase"
                else placed_shape(obj.Shape, instrument_mount.stage_placement(0))
            )
            report = _lift_path(
                obj.Name,
                shape,
                {"Rail": rail_shape},
                0,
                waypoints=[(-3, 0, 0), (3, 0, 0)],
            )
            self.assertTrue(report["passed"], report)
        blocker = Part.makeBox(2, 2, 2, App.Vector(0, 5, 18))
        negative = _lift_path(
            "InstrumentMountBase",
            self.kit["lower"].Shape,
            {"Rail": rail_shape, "Blocker": blocker},
            0,
            waypoints=[(-3, 0, 0), (3, 0, 0)],
        )
        self.assertFalse(negative["passed"], negative)

    def test_upper_service_partition_retains_blends_without_widening_lower_lug(self):
        from gondola.cad import union
        from gondola.validation.instrument import _split, _upper_regions

        upper = self.kit["upper"].Shape
        regions = _upper_regions(upper)
        self.assertEqual(len(regions), 2)
        restored = union(regions)
        self.assertLess(upper.cut(restored).Volume, 1e-6)
        self.assertLess(restored.cut(upper).Volume, 1e-6)
        self.assertAlmostEqual(regions[0].BoundBox.ZMax, 16.5)
        self.assertLessEqual(regions[0].BoundBox.YLength, 8 + 1e-6)
        # A literal R0.5 Y-root witness belongs entirely to the raised region.
        root = Part.makeBox(2, 0.5, 0.5, App.Vector(4, 4, 16.5)).cut(
            Part.makeCylinder(0.5, 2, App.Vector(4, 4.5, 16.5), App.Vector(1, 0, 0))
        )
        self.assertLess(root.cut(regions[1]).Volume, 1e-6)
        self.assertLess(root.common(regions[0]).Volume, 1e-6)
        # Deliberately dropping a0.02mm layer of actual support stock must fail.
        with self.assertRaisesRegex(ValueError, "exceeds its decomposition"):
            _split(
                upper,
                [
                    Part.makeBox(200, 200, 100, App.Vector(-100, -100, -83.51)),
                    Part.makeBox(200, 200, 100, App.Vector(-100, -100, 16.51)),
                ],
            )

    def test_standard_shoe_and_plate_are_exact_at_their_interface_datums(self):
        from gondola.parts import mounting_plate, rail

        lower = self.kit["lower"].Shape
        shoe = lower.common(Part.makeBox(80, 80, 12.5, App.Vector(-40, -40, 0)))
        expected = rail.mount_base_shape()
        self.assertLess(abs(shoe.cut(expected).Volume), 1e-5)
        self.assertLess(abs(expected.cut(shoe).Volume), 1e-5)
        upper = self.kit["upper"].Shape
        plate = upper.common(Part.makeBox(80, 80, 2, App.Vector(-40, -40, 17)))
        expected = mounting_plate.shape()
        self.assertLess(abs(plate.cut(expected).Volume), 1e-5)
        self.assertLess(abs(expected.cut(plate).Volume), 1e-5)

    def test_integral_bridge_keeps_fc_head_columns_and_wiring_clear(self):
        from gondola.validation.instrument import fc_bridge_access_check

        shape = self.kit["upper"].Shape
        report = fc_bridge_access_check(shape)
        self.assertTrue(report["passed"], report)
        for x, y in ((25.5 / math.sqrt(2), 0), (0, -25.5 / math.sqrt(2))):
            obstruction = Part.makeBox(1, 1, 8, App.Vector(x - 0.5, y - 0.5, 34))
            # A joined roof tongue blocks a real head column and must be rejected.
            blocked = shape.fuse(obstruction).fuse(
                Part.makeBox(
                    abs(x) + 1,
                    abs(y) + 1,
                    1,
                    App.Vector(min(0, x) - 0.5, min(0, y) - 0.5, 42),
                )
            )
            self.assertTrue(blocked.isValid())
            self.assertEqual(len(blocked.Solids), 1)
            self.assertFalse(fc_bridge_access_check(blocked)["passed"])

    def test_native_pitch_keeps_literal_axis_fixed_under_parent_pose(self):
        self.root.Placement = App.Placement(
            App.Vector(-56, 0, 0), App.Rotation(App.Vector(0, 0, 1), 180)
        )
        stage = self.kit["pitch_stage"]
        for request in (-999, -20, -9, 0, 7, 20, 999):
            with self.subTest(request=request):
                stage.Pitch = request
                self.doc.recompute()
                actual = max(-20, min(20, request))
                local_pivot = stage.Placement.multVec(App.Vector(0, 0, 8))
                self.assertLess((local_pivot - App.Vector(0, 0, 27.5)).Length, 1e-7)
                local_normal = stage.Placement.Rotation.multVec(App.Vector(0, 0, 1))
                self.assertAlmostEqual(local_normal.x, math.sin(math.radians(actual)))
                self.assertAlmostEqual(local_normal.z, math.cos(math.radians(actual)))
                world_pivot = stage.getGlobalPlacement().multVec(App.Vector(0, 0, 8))
                self.assertLess((world_pivot - App.Vector(-56, 0, 27.5)).Length, 1e-7)
        self.assertEqual(stage.getEditorMode("MinimumAngle"), ["ReadOnly"])
        self.assertEqual(stage.getEditorMode("MaximumAngle"), ["ReadOnly"])

    def test_centre_access_is_four_mm_and_missing_or_filled_stock_fails(self):
        from gondola.validation.instrument import centre_accessory_check

        shape = self.kit["upper"].Shape
        report = centre_accessory_check(shape)
        self.assertTrue(report["passed"], report)
        self.assertAlmostEqual(report["available_head_clearance_mm"], 4)
        # Connected roof tab blocks the accessory head without closing its bore.
        defective = shape.fuse(Part.makeBox(4, 8, 2, App.Vector(-2, -4, 15)))
        self.assertFalse(centre_accessory_check(defective)["passed"])

    def test_saved_nut_floor_defect_cannot_hide_behind_contract_metadata(self):
        from gondola.validation.instrument import instrument_check

        obj = self.kit["lower"]
        original = obj.Shape.copy()
        try:
            obj.Shape = original.cut(Part.makeBox(1, 1.5, 1, App.Vector(2, 4.1, 27)))
            self.doc.recompute()
            result = instrument_check(self.doc, include_installed=False)
            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["saved_print_stock_matches_source"])
            self.assertFalse(result["checks"]["both_nut_floors_retain_1p5mm_stock"])
        finally:
            obj.Shape = original
            self.doc.recompute()

    def test_spare_slot_relief_retains_real_arc_ligament(self):
        from gondola.validation.instrument import instrument_check

        self.assertTrue(
            self.positive["checks"]["spare_slot_relief_retains_1p5mm_arc_web"]
        )
        self.assertGreater(self.positive["arc_web"]["actual_slot_to_relief_mm"], 1.8)
        obj = self.kit["upper"]
        original = obj.Shape.copy()
        try:
            obj.Shape = original.cut(
                Part.makeBox(0.4, 0.4, 0.4, App.Vector(8.8, -0.2, 13.4))
            )
            self.doc.recompute()
            report = instrument_check(self.doc, include_installed=False)
            self.assertFalse(report["passed"])
            self.assertFalse(
                report["checks"]["spare_slot_relief_retains_1p5mm_arc_web"]
            )
        finally:
            obj.Shape = original
            self.doc.recompute()

    def test_saved_arc_blockage_is_rejected(self):
        from gondola.validation.instrument import instrument_check

        obj = self.kit["upper"]
        original = obj.Shape.copy()
        try:
            obj.Shape = original.fuse(Part.makeBox(1, 8, 5, App.Vector(9.5, -4, 5.5)))
            self.doc.recompute()
            result = instrument_check(self.doc, include_installed=False)
            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["saved_print_stock_matches_source"])
        finally:
            obj.Shape = original
            self.doc.recompute()

    def test_wrong_native_compensation_is_rejected(self):
        from gondola.validation.instrument import instrument_check

        stage = self.kit["pitch_stage"]
        original = dict(stage.ExpressionEngine)[".Placement.Base.z"]
        try:
            stage.setExpression("Placement.Base.z", "19.5 mm")
            result = instrument_check(self.doc, include_installed=False)
            self.assertFalse(result["passed"])
            self.assertIn("axis compensation", result["error"])
        finally:
            stage.setExpression("Placement.Base.z", original)
            self.doc.recompute()

    def test_real_hardware_has_full_nut_engagement_and_external_capture(self):
        from gondola.validation.geometry import planar_contact_area

        lower = self.kit["lower"].Shape
        for joint in ("Pivot", "Lock"):
            bolt = self.doc.getObject("Instrument" + joint + "Bolt")
            nut = self.doc.getObject("Instrument" + joint + "Nut")
            self.assertAlmostEqual(bolt.Shape.BoundBox.YMin, -9.1)
            self.assertAlmostEqual(bolt.Shape.BoundBox.YMax, 8.9)
            self.assertAlmostEqual(nut.Shape.BoundBox.YMin, 5.6)
            self.assertAlmostEqual(nut.Shape.BoundBox.YMax, 8.0)
            self.assertGreater(planar_contact_area(lower, bolt.Shape), 15)
            self.assertGreater(planar_contact_area(lower, nut.Shape), 15)
            self.assertIn("M3 x 0.5", bolt.ThreadStandard)
            self.assertIn("16 mm", bolt.PurchaseRequirements)
            self.assertIn("M3 button head", bolt.ShapeModelNotes)
            self.assertIn("diameter 6.0 mm x height 2.0 mm", bolt.ShapeModelNotes)
            self.assertNotIn("diameter 4.5", bolt.ShapeModelNotes)
        contract = json.loads(self.root.InstrumentMountContract)
        self.assertFalse(contract["holding_torque_verified"])
        self.assertFalse(contract["physical_angle_stops_modeled"])
        self.assertFalse(contract["self_levelling"])

    def test_planar_wall_screen_retains_minimum_stock(self):
        from gondola.validation.manufacturing import (
            material_length_on_line,
            planar_wall_regions,
        )

        for obj in self.kit["printed"]:
            rows = planar_wall_regions(obj.Shape)
            if obj.Name == "InstrumentMountBase":
                self.assertEqual(len(rows), 2)  # Two actual 1.5mm nut floors.
            self.assertTrue(
                all(r["material_thickness_mm"] >= 1.5 - 1e-5 for r in rows), rows
            )
        upper = self.kit["upper"].Shape
        self.assertAlmostEqual(
            material_length_on_line(upper, (0, 20, 16.99), (0, 20, 19.01)), 2
        )
        self.assertAlmostEqual(
            material_length_on_line(upper, (-4, -4.01, 15), (-4, 4.01, 15)), 8
        )


@unittest.skipIf(App is None, "Requires FreeCAD")
class InstrumentMotionCertificateTests(unittest.TestCase):
    def test_mid_interval_blocker_is_rejected_when_endpoints_clear(self):
        from gondola.validation.instrument import certify_pitch_clearance

        moving = Part.makeSphere(0.1, App.Vector(15, 0, 8))
        angle = math.radians(7.3)
        blocker = Part.makeSphere(
            0.1, App.Vector(15 * math.cos(angle), 0, 27.5 - 15 * math.sin(angle))
        )
        for endpoint in (-20, 20):
            shape = moving.copy()
            shape.translate(App.Vector(0, 0, 19.5))
            shape.rotate(App.Vector(0, 0, 27.5), App.Vector(0, 1, 0), endpoint)
            self.assertEqual(shape.common(blocker).Volume, 0)
        report = certify_pitch_clearance(moving, blocker)
        self.assertFalse(report["passed"], report)
        self.assertGreater(report["overlap_mm3"], 0)

    def test_all_propulsion_input_members_get_complete_orbit_bounds(self):
        from gondola.cad import placed_shape
        from gondola.validation.instrument import _propulsion_orbits

        doc = App.newDocument("InstrumentOrbitInventory")
        try:
            module = doc.addObject("App::Part", "ElectronicsEquipmentModule")
            module.Placement = App.Placement(
                App.Vector(-82, 0, 0), App.Rotation(App.Vector(0, 0, 1), 180)
            )
            registry = doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
            for key in (
                "PrintedParts",
                "ReferenceParts",
                "HardwareParts",
                "TapeReferences",
            ):
                registry.addProperty("App::PropertyLinkListGlobal", key)
            objects = []
            suffixes = (
                "ServoHorn",
                "DriverGear",
                "HornGearAdapter",
                "HornGearClampNearBolt",
                "HornGearClampFarBolt",
                "InputShaft",
                "InputShaftClampBolt",
                "InputShaftClampNut",
                "HornGearClampNearNut",
                "HornGearClampFarNut",
            )
            for prefix, sign in (("Port", 1), ("Starboard", -1)):
                for group_suffix in ("InputDrive", "Pod"):
                    group = doc.addObject("App::Part", prefix + group_suffix)
                    group.Placement.Base = App.Vector(sign * 16, sign * 8, 50)
                    for suffix in (
                        suffixes if group_suffix == "InputDrive" else ("MotorCarrier",)
                    ):
                        part = doc.addObject("Part::Feature", prefix + suffix)
                        group.addObject(part)
                        part.Shape = Part.makeBox(2, 1, 2, App.Vector(2, -0.5, 1))
                        objects.append(part)
            registry.ReferenceParts = objects
            doc.recompute()
            envelopes, rows = _propulsion_orbits(doc, module, True)
            self.assertEqual(len(rows), 22)
            self.assertEqual({row["part"] for row in rows}, {o.Name for o in objects})
            obj = doc.PortHornGearClampFarBolt
            relative = (
                module.getGlobalPlacement()
                .inverse()
                .multiply(obj.getParentGeoFeatureGroup().getGlobalPlacement())
            )
            for angle in (-173, -60, 0, 31, 179):
                source = obj.Shape.copy()
                source.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
                source = placed_shape(source, relative)
                self.assertLess(
                    source.cut(envelopes[obj.Name + "AllAngles"]).Volume, 1e-6
                )
            registry.ReferenceParts = [o for o in objects if o != obj]
            with self.assertRaisesRegex(ValueError, "Incomplete registered"):
                _propulsion_orbits(doc, module, True)
        finally:
            App.closeDocument(doc.Name)

    def test_continuous_clear_path_and_budget_fail_closed(self):
        from gondola.validation.instrument import certify_pitch_clearance

        moving = Part.makeSphere(0.1, App.Vector(15, 0, 8))
        fixed = Part.makeSphere(0.1, App.Vector(10, 0, 27.5))
        self.assertTrue(certify_pitch_clearance(moving, fixed)["passed"])
        self.assertFalse(
            certify_pitch_clearance(moving, fixed, max_evaluations=0)["passed"]
        )
        with self.assertRaisesRegex(ValueError, "Finite"):
            certify_pitch_clearance(moving, fixed, low=float("nan"))
