"""Off-rail portal service must not erase installed or carried obstacles."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class PowerBenchServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.config import BASELINE_FILE
        from gondola.parts import power_mount, stack_interface
        from gondola.power_export import _installation_context, _placed
        from gondola.provenance import file_sha256

        cls.source = BASELINE_FILE
        cls.before = file_sha256(cls.source)
        cls.doc = App.openDocument(str(cls.source), hidden=True)
        cls.host = "AccessoryEquipmentModule"
        cls.pose = power_mount.host_placement(
            cls.doc, cls.host, "TETHER_BEC_SVPDB", packaging="PORTAL"
        )
        cls.context = _installation_context(cls.doc, "TETHER_BEC_SVPDB")
        physical, _ = power_mount.local_shapes("TETHER_BEC_SVPDB", packaging="PORTAL")
        cls.physical = _placed(physical, cls.pose)
        cls.tools = _placed(dict(stack_interface.clamp_tool_reservations()), cls.pose)
        cls.off_rail = frozenset(
            obj.Name
            for category in ("RailSegments", "TapeReferences")
            for obj in getattr(cls.doc.DesignRegistry, category)
        )

    @classmethod
    def tearDownClass(cls):
        from gondola.provenance import file_sha256

        App.closeDocument(cls.doc.Name)
        if file_sha256(cls.source) != cls.before:
            raise AssertionError("Saved fixture changed during read-only bench audit")

    def test_off_rail_contract_excludes_only_the_absent_rail_and_tape(self):
        from gondola.power_export import _portal_foot_service_conflicts

        self.assertEqual(
            _portal_foot_service_conflicts(
                self.physical, self.pose, self.context, self.off_rail
            ),
            [],
        )
        # Force an overlap for every registered rail/tape obstacle instead of
        # relying on a particular wing pitch or carrier position to collide.
        self.assertTrue(self.off_rail)
        injection = self.tools["key_0"]
        for name in sorted(self.off_rail):
            with self.subTest(obstacle=name):
                self.assertIn(name, self.context)
                context = {
                    **self.context,
                    name: self.context[name].fuse(injection),
                }
                hits = _portal_foot_service_conflicts(
                    self.physical, self.pose, context, ()
                )
                self.assertTrue(any(row["second"] == name for row in hits), hits)
                self.assertEqual(
                    _portal_foot_service_conflicts(
                        self.physical, self.pose, context, self.off_rail
                    ),
                    [],
                )

    def test_host_attached_and_unknown_obstacles_remain_blocking(self):
        from gondola.power_export import _portal_foot_service_conflicts

        injection = self.tools["key_0"]
        for name in (
            "AccessoryMount",
            "UnknownAttachedPart",
            "PASConnectorReserve",
            "MTF01PContinuousBodyBound",
            "Instrument/ElectronicsMount",
            "MTF01PContinuousConnectorBound",
            "UnknownOpticalFieldBound",
        ):
            with self.subTest(obstacle=name):
                obstacle = (
                    self.context[name].fuse(injection)
                    if name in self.context
                    else injection
                )
                context = {**self.context, name: obstacle}
                hits = _portal_foot_service_conflicts(
                    self.physical, self.pose, context, self.off_rail
                )
                self.assertTrue(any(row["second"] == name for row in hits), hits)

    def test_inactive_optical_fields_do_not_block_disconnected_bench_tools(self):
        from gondola.power_export import _portal_foot_service_conflicts

        injection = self.tools["key_0"]
        for name in (
            "MTF02POpticalClearanceReserve",
            "MTF02PContinuousOpticalFieldBound",
            "MTF01PContinuousOpticalFieldBound",
        ):
            with self.subTest(field=name):
                self.assertGreater(injection.Volume, 1)
                self.assertEqual(
                    _portal_foot_service_conflicts(
                        self.physical,
                        self.pose,
                        {**self.context, name: injection},
                        self.off_rail,
                    ),
                    [],
                )

    def test_platform_boards_and_other_fasteners_remain_tool_obstacles(self):
        from gondola.power_export import _portal_foot_service_conflicts

        for name in ("PowerPlatform", "PowerModule0", "PowerFootBolt1"):
            with self.subTest(obstacle=name):
                physical = {
                    **self.physical,
                    name: self.physical[name].fuse(self.tools["key_0"]),
                }
                hits = _portal_foot_service_conflicts(
                    physical, self.pose, self.context, self.off_rail
                )
                self.assertTrue(any(row["second"] == name for row in hits), hits)

    def test_rail_and_tape_are_not_excluded_from_installed_checks(self):
        from gondola.power_export import _configuration_conflicts

        # The same name may be absent at the bench but remains a real installed
        # obstacle. Only the service branch receives the off-rail exception.
        context = {**self.context, "TapeWing1R": self.physical["PowerPlatform"]}
        hits = _configuration_conflicts(
            "TETHER_BEC_SVPDB",
            self.pose,
            context,
            self.host,
            packaging="PORTAL",
            off_rail_names=self.off_rail,
        )
        self.assertTrue(
            any(
                row["second"] == "TapeWing1R" and row["phase"] == "nominal"
                for row in hits
            ),
            hits,
        )


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class DirectBoardServicePhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import mounting_plate, power_mount
        from gondola.validation.geometry import translation_sweep

        cls.physical, cls.reserves = power_mount.local_shapes(
            "TETHER_BEC_SVPDB", packaging="DIRECT_CARRIER"
        )
        cls.context = {"BatteryMount": mounting_plate.shape(-2)}
        cls.board = cls.physical["PowerModule0"]
        cls.sweep, _ = translation_sweep(cls.board, (0, 0, 32))
        cls.end = cls.board.copy()
        cls.end.translate(App.Vector(0, 0, 32))
        # A bounded ray-field witness above the installed connection allowances
        # and below the extracted board: endpoints clear, midpoint obstructed.
        cls.midpoint = Part.makeSphere(0.3, App.Vector(0, -14, 31))
        cls.field_names = (
            "MTF02POpticalClearanceReserve",
            "MTF02PContinuousOpticalFieldBound",
            "MTF01PContinuousOpticalFieldBound",
        )

    def conflicts(self, extra):
        from gondola.power_export import _configuration_conflicts

        return _configuration_conflicts(
            "TETHER_BEC_SVPDB",
            App.Placement(),
            {**self.context, **extra},
            "BatteryEquipmentModule",
            packaging="DIRECT_CARRIER",
        )

    def test_temporary_field_crossing_is_allowed_only_after_disconnect(self):
        self.assertEqual(self.conflicts({}), [])
        self.assertGreater(self.sweep.common(self.midpoint).Volume, 0.11)
        for shape in [*self.physical.values(), *self.reserves.values(), self.end]:
            self.assertLess(abs(shape.common(self.midpoint).Volume), 1e-6)
        for name in self.field_names:
            with self.subTest(field=name):
                self.assertEqual(self.conflicts({name: self.midpoint}), [])

    def test_seated_optical_field_intersection_still_rejects_configuration(self):
        for name in self.field_names:
            with self.subTest(field=name):
                hits = self.conflicts({name: self.board})
                self.assertTrue(
                    any(
                        row["second"] == name
                        and row["phase"] == "nominal"
                        and row["intersection_mm3"] > 1
                        for row in hits
                    ),
                    hits,
                )

    def test_physical_and_access_reserves_still_block_midpath_removal(self):
        for name in (
            "ActualSensorBody",
            "MTF01PContinuousBodyBound",
            "Instrument/ElectronicsMount",
            "MTF01PContinuousConnectorBound",
            "UnknownOpticalFieldBound",
        ):
            with self.subTest(obstacle=name):
                hits = self.conflicts({name: self.midpoint})
                self.assertFalse(any(row["phase"] == "nominal" for row in hits), hits)
                self.assertTrue(
                    any(
                        row["first"] == "PowerModule0"
                        and row["second"] == name
                        and row["phase"] == "disconnected board removal"
                        and row["intersection_mm3"] > 0.11
                        for row in hits
                    ),
                    hits,
                )


if __name__ == "__main__":
    unittest.main()
