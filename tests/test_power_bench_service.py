"""Off-rail portal service must not erase installed or carried obstacles."""

import unittest

try:
    import FreeCAD as App
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
        from gondola.power_export import _collisions, _portal_foot_service_conflicts

        old_hits = _collisions(self.tools, self.context)
        self.assertTrue(any(row["second"] == "TapeWing1R" for row in old_hits))
        self.assertEqual(
            _portal_foot_service_conflicts(
                self.physical, self.pose, self.context, self.off_rail
            ),
            [],
        )
        # Omitting the explicit off-rail set must still expose the on-rail hit.
        self.assertTrue(
            _portal_foot_service_conflicts(self.physical, self.pose, self.context, ())
        )

    def test_host_attached_and_unknown_obstacles_remain_blocking(self):
        from gondola.power_export import _portal_foot_service_conflicts

        injection = self.tools["key_0"]
        for name in (
            "AccessoryMount",
            "UnknownAttachedPart",
            "PASConnectorReserve",
            "MTF02PContinuousOpticalFieldBound",
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


if __name__ == "__main__":
    unittest.main()
