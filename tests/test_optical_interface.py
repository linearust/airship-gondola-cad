"""Compact foot reuses the common carrier slot and follows its native parent."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class OpticalCarrierInterfaceTests(unittest.TestCase):
    def new_carrier_mount(self, side="PositiveX"):
        from gondola.parts import mounting_plate, optical_mount

        doc = App.newDocument("OpticalLocatorInterface")
        self.addCleanup(App.closeDocument, doc.Name)
        host = doc.addObject("App::Part", "BatteryEquipmentModule")
        plate = doc.addObject("Part::Feature", "BatteryMount")
        plate.Shape = mounting_plate.shape()
        host.addObject(plate)
        optical_mount.build_optical_mount(doc, host, side)
        doc.recompute()
        return doc

    def test_component_proxies_enclose_compact_base(self):
        from gondola.parts import optical_interface, optical_mount

        shape = optical_mount.base_shape()
        proxies = Part.makeCompound(
            [s for _, s in optical_interface.base_component_proxies()]
        )
        self.assertLess(abs(shape.cut(proxies).Volume), 1e-5)
        self.assertEqual(len(optical_interface.base_component_proxies()), 3)
        self.assertEqual((shape.BoundBox.XLength, shape.BoundBox.YLength), (8, 18))

    def test_both_sides_reuse_existing_slot_without_intersecting_plate(self):
        from gondola.parts import mounting_plate, optical_interface, optical_mount

        plate = mounting_plate.shape()
        for side in optical_interface.SIDES:
            pose = optical_interface.placement(side)
            base = optical_mount.base_shape()
            base.Placement = pose
            self.assertLess(abs(base.common(plate).Volume), 1e-5)
            self.assertAlmostEqual(abs(pose.Base.x), 27)
            self.assertAlmostEqual(pose.Base.y, 0)
            for x, y in optical_interface.CLAMP_CENTRES.values():
                drill = Part.makeCylinder(1.25, 4, App.Vector(x, y, -3))
                drill.Placement = pose
                self.assertLess(abs(drill.common(plate).Volume), 1e-5)

    def test_located_foot_seats_fully_and_reuses_positive_end_fastener(self):
        from gondola.validation.optical import _carrier_interface_checks

        for side in ("PositiveX", "NegativeX"):
            with self.subTest(side=side):
                doc = self.new_carrier_mount(side)
                result = _carrier_interface_checks(doc)
                self.assertTrue(result["passed"], result)
                self.assertIsNone(doc.getObject("OpticalFootBolt0"))
                self.assertIsNone(doc.getObject("OpticalFootNut0"))
                bolt = doc.OpticalFootBolt1
                self.assertEqual(bolt.HardwareSKU, "M2X8_BUTTON_HEAD")
                self.assertAlmostEqual(bolt.Shape.BoundBox.Center.y, 5.0)
                self.assertEqual(doc.OpticalFootNut1.HardwareSKU, "M2_HEX_NUT")

    def test_material_witness_rejects_missing_rotated_or_thin_locator(self):
        from gondola.parts import optical_interface
        from gondola.validation.optical import _carrier_interface_checks

        doc = self.new_carrier_mount()
        foot = doc.OpticalMountBase
        original = foot.Shape.copy()
        above = original.cut(Part.makeBox(10, 18, 3, App.Vector(-5, -9, -3)))
        rotated = optical_interface.locator_shape()
        rotated.rotate(App.Vector(0, -2, 0), App.Vector(0, 0, 1), 90)
        thin = optical_interface.locator_shape().common(
            Part.makeBox(1.0, 18, 3, App.Vector(-0.5, -9, -3))
        )
        for name, replacement in (
            ("missing", None),
            ("rotated", rotated),
            ("thin", thin),
        ):
            with self.subTest(locator=name):
                foot.Shape = above if replacement is None else above.fuse(replacement)
                result = _carrier_interface_checks(doc)
                self.assertFalse(result["passed"], result)
                core = next(
                    row
                    for row in result["witnesses"]
                    if row["kind"] == "rigid_locator_full_length_and_section"
                )
                self.assertFalse(core["passed"])
        foot.Shape = original
        self.assertTrue(_carrier_interface_checks(doc)["passed"])

    def test_under_slot_blockage_and_incomplete_seating_are_rejected(self):
        from gondola.cad import world_shape
        from gondola.validation.optical import _carrier_interface_checks

        doc = self.new_carrier_mount()
        plate = doc.BatteryMount
        original = plate.Shape.copy()
        # A shallow artificial ledge prevents the tongue from reaching the
        # flat support plane, despite clear entry at the top of the slot.
        ledge = Part.makeBox(3, 3, 0.4, App.Vector(-1.5, -4, -1.3))
        ledge.Placement = doc.OpticalFlowModule.getGlobalPlacement().multiply(
            ledge.Placement
        )
        self.assertGreater(ledge.common(world_shape(doc.OpticalMountBase)).Volume, 0)
        plate.Shape = original.fuse(ledge)
        result = _carrier_interface_checks(doc)
        self.assertFalse(result["passed"], result)
        insertion = next(
            row
            for row in result["witnesses"]
            if row["kind"] == "continuous_full_seating_insertion"
        )
        self.assertGreater(insertion["obstruction_mm3"], 0)
        plate.Shape = original
        foot = doc.OpticalMountBase
        foot.Placement.Base.z += 0.1
        result = _carrier_interface_checks(doc)
        self.assertFalse(result["passed"], result)
        self.assertTrue(
            any(
                row["kind"] == "foot_support_strip"
                and row.get("surface") == "foot"
                and not row["passed"]
                for row in result["witnesses"]
            )
        )

    def test_long_or_protruding_locator_cannot_pass_nominal_fit_screen(self):
        from gondola.validation.optical import _carrier_interface_checks

        doc = self.new_carrier_mount()
        foot = doc.OpticalMountBase
        original = foot.Shape.copy()
        for name, protrusion in (
            ("blocked slot end", Part.makeBox(2, 2, 1, App.Vector(-1, -7, -1))),
            (
                "underside intrusion",
                Part.makeBox(1, 2, 2.5, App.Vector(-0.5, -3, -2.5)),
            ),
        ):
            with self.subTest(defect=name):
                foot.Shape = original.fuse(protrusion)
                self.assertFalse(_carrier_interface_checks(doc)["passed"])

    def test_dimensional_screen_preserves_underside_space_and_registration_bound(self):
        import math

        from gondola.parts import optical_interface

        self.assertGreaterEqual(2.0 - 0.3 - (1.2 + 0.3), 0.19)
        self.assertLess(
            math.asin((2.9 - 1.7) / 5.7),
            optical_interface.MAX_REGISTRATION_YAW_RAD,
        )
        self.assertAlmostEqual(optical_interface.LOCATOR_DEPTH, 1.2)
        self.assertAlmostEqual(optical_interface.LOCATOR_WIDTH, 2.0)

    def test_registration_bound_encloses_rotated_and_shifted_sensor(self):
        import math

        from gondola.contracts.optical_sensors import get_sensor_profile
        from gondola.parts import optical_interface, optical_sensor

        shape = optical_sensor.envelope_shape(get_sensor_profile("MTF01P"))
        bound = optical_interface.registration_bound(shape)
        for fraction in (-1, -0.5, 0, 0.5, 1):
            for sign in (-1, 1):
                actual = shape.copy()
                actual.rotate(
                    App.Vector(),
                    App.Vector(0, 0, 1),
                    math.degrees(fraction * optical_interface.MAX_REGISTRATION_YAW_RAD),
                )
                actual.translate(
                    App.Vector(
                        sign * optical_interface.MAX_REGISTRATION_X,
                        -sign * optical_interface.MAX_REGISTRATION_Y,
                        0,
                    )
                )
                self.assertLess(abs(actual.cut(bound).Volume), 1e-5)

    def test_native_side_changes_and_reparenting_move_entire_mount(self):
        from gondola.parts import optical_interface, optical_mount

        doc = App.newDocument("OpticalCarrierInterface")
        try:
            hosts = [
                doc.addObject("App::Part", name)
                for name in optical_interface.SUPPORTED_HOSTS
            ]
            hosts[1].Placement.Base = App.Vector(-54, -0.1, 0)
            kit = optical_mount.build_optical_mount(doc, hosts[0])
            optical_interface.attach_to_host(kit["group"], hosts[1], "NegativeX")
            self.assertEqual(kit["group"].getParentGeoFeatureGroup(), hosts[1])
            self.assertEqual(kit["group"].CarrierHostName, hosts[1].Name)
            self.assertEqual(
                tuple(kit["pitch_stage"].getGlobalPlacement().Base), (-81, -0.1, 38)
            )
            self.assertNotIn("RailPositionX", kit["group"].PropertiesList)
            kit["group"].MountSide = "PositiveX"
            doc.recompute()
            self.assertAlmostEqual(kit["pitch_stage"].getGlobalPlacement().Base.x, -27)
            with self.assertRaises(ValueError):
                optical_interface.placement("Unknown")
            other = doc.addObject("App::Part", "NotACarrier")
            with self.assertRaises(ValueError):
                optical_interface.attach_to_host(kit["group"], other)
        finally:
            App.closeDocument(doc.Name)
