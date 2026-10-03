"""Direct tether retention, service and complete configuration regressions."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class DirectPowerTests(unittest.TestCase):
    def test_four_separated_contact_patches_reject_each_missing_land(self):
        from gondola.parts import equipment_mounts, power_mount
        from gondola.power_export import _internal_collisions

        physical, reserves = power_mount.local_shapes()
        self.assertEqual(set(physical), {"PowerModule0", "PowerModule1"})
        self.assertEqual(_internal_collisions(physical, reserves), [])
        carrier = equipment_mounts.mount_shape("battery").copy()
        carrier.translate(App.Vector(0, 0, -equipment_mounts.SUPPORT_FACE_Z))
        report = power_mount.direct_attachment_check(carrier, physical)
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["boards"]), 4)
        for row in report["boards"]:
            self.assertAlmostEqual(row["continuous_supported_area_mm2"], 48)
            self.assertAlmostEqual(row["body_overlap_mm2"], 48)
            self.assertAlmostEqual(row["insulation_allowance_mm"], 1)
        for board, regions in enumerate(power_mount.DIRECT_ADHESIVE_REGIONS):
            for patch, (centre, _) in enumerate(regions):
                with self.subTest(board=board, patch=patch):
                    cut = Part.makeBox(
                        1, 1, 2, App.Vector(centre[0] - 0.5, centre[1] - 0.5, -2)
                    )
                    changed = power_mount.direct_attachment_check(
                        carrier.cut(cut), physical
                    )
                    self.assertFalse(changed["passed"])
                    self.assertEqual(
                        [
                            (r["board"], r["patch"])
                            for r in changed["boards"]
                            if not r["passed"]
                        ],
                        [(f"PowerModule{board}", patch)],
                    )
        moved = {name: shape.copy() for name, shape in physical.items()}
        moved["PowerModule1"].translate(App.Vector(0, 0, 0.2))
        self.assertFalse(power_mount.direct_attachment_check(carrier, moved)["passed"])

    def test_direct_installation_rejects_battery_and_intermediate_removal_collision(
        self,
    ):
        from gondola.contracts.power_options import DIRECT_CARRIER
        from gondola.parts import equipment_mounts, power_mount
        from gondola.power_export import _configuration_conflicts

        with self.assertRaises(ValueError):
            power_mount.local_shapes("BATTERY_SVPDB")
        carrier = equipment_mounts.mount_shape("battery").copy()
        carrier.translate(App.Vector(0, 0, -equipment_mounts.SUPPORT_FACE_Z))
        context = {"BatteryMount": carrier}
        pose = App.Placement()
        self.assertEqual(
            _configuration_conflicts(
                "TETHER_BEC_SVPDB",
                pose,
                context,
                "BatteryEquipmentModule",
                packaging=DIRECT_CARRIER,
            ),
            [],
        )
        # Above the full 15 mm top-access reserve, below the end of a 32 mm lift:
        # both board endpoints clear, so an endpoint-only check would miss this.
        context["IntermediateObstacle"] = Part.makeBox(1, 1, 1, App.Vector(0, -14, 25))
        rejected = _configuration_conflicts(
            "TETHER_BEC_SVPDB",
            pose,
            context,
            "BatteryEquipmentModule",
            packaging=DIRECT_CARRIER,
        )
        self.assertTrue(
            any(
                r.get("phase") == "disconnected board removal"
                and r["second"] == "IntermediateObstacle"
                for r in rejected
            ),
            rejected,
        )

    def test_continuous_pitch_bounds_contain_both_sensor_and_connector_poses(self):
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import optical_sensor
        from gondola.validation.optical_envelopes import pitch_bound

        for profile in SENSOR_PROFILES.values():
            for factory in (
                optical_sensor.envelope_shape,
                optical_sensor.connector_reserve_shape,
            ):
                original = factory(profile)
                bound = pitch_bound(original, 20)
                for angle in range(-20, 21, 2):
                    moved = original.copy()
                    moved.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
                    self.assertLess(
                        moved.cut(bound).Volume,
                        1e-5,
                        (profile.key, factory.__name__, angle),
                    )

    def test_instrument_bound_refinement_keeps_real_and_unknown_obstructions(self):
        from gondola.cad import placed_shape, set_property
        from gondola.contracts.equipment_options import get_navigation_profile
        from gondola.parts import instrument_mount, optical_mount, wiring_reserves
        from gondola.power_export import _collisions, _instrument_motion_context

        doc = App.newDocument("PowerPitchRefinement")
        self.addCleanup(App.closeDocument, doc.Name)
        module = doc.addObject("App::Part", "ElectronicsEquipmentModule")
        module.Placement = App.Placement(
            App.Vector(-82, 0, 0), App.Rotation(App.Vector(0, 0, 1), 180)
        )
        kit = instrument_mount.build_mount(doc, module)
        optical = optical_mount.build_optical_mount(doc, kit["pitch_stage"])["group"]
        registry = doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        for category in (
            "PrintedParts",
            "HardwareParts",
            "ReferenceParts",
            "TapeReferences",
            "ClearanceVolumes",
        ):
            set_property(
                registry,
                category,
                kit["printed"] if category == "PrintedParts" else [],
                "App::PropertyLinkListGlobal",
            )
        doc.recompute()
        motion = _instrument_motion_context(doc, optical)
        bounds = motion["bounds"]
        nav = placed_shape(
            wiring_reserves.reserve_shapes(
                navigation_profile=get_navigation_profile("MGA01")
            )["PASConnectorReserve"],
            App.Placement(App.Vector(-140, 0, 0), App.Rotation()),
        )
        self.assertTrue(_collisions({"Navigation": nav}, bounds))
        self.assertEqual(
            _collisions({"Navigation": nav}, bounds, instrument_motion=motion), []
        )
        self.assertTrue(motion["proofs"])
        actual_hit = placed_shape(
            Part.makeSphere(0.5, App.Vector(29.5, 29.5, 30)),
            kit["pitch_stage"].getGlobalPlacement(),
        )
        self.assertTrue(
            _collisions({"ActualHit": actual_hit}, bounds, instrument_motion=motion)
        )
        changed = {
            **bounds,
            "Instrument/ElectronicsMount": bounds["Instrument/ElectronicsMount"].fuse(
                nav
            ),
        }
        self.assertTrue(
            _collisions({"Navigation": nav}, changed, instrument_motion=motion)
        )
        unknown = doc.addObject("Part::Feature", "UnknownOpticalStock")
        optical.addObject(unknown)
        unknown.Shape = Part.makeBox(1, 1, 1, App.Vector(60, 40, 8))
        registry.ReferenceParts = [unknown]
        doc.recompute()
        motion = _instrument_motion_context(doc, optical)
        self.assertIn("Instrument/UnknownOpticalStock", motion["bounds"])
        middle = placed_shape(
            unknown.Shape,
            module.getGlobalPlacement().multiply(instrument_mount.stage_placement(5)),
        )
        nominal = placed_shape(unknown.Shape, kit["pitch_stage"].getGlobalPlacement())
        self.assertLess(nominal.common(middle).Volume, 1e-6)
        self.assertTrue(
            _collisions(
                {"MidIntervalBlocker": middle},
                motion["bounds"],
                instrument_motion=motion,
            )
        )

    def test_composed_matrix_keeps_direct_tether_with_common_instrument_optics(self):
        from gondola.cad import set_property
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import (
            equipment_mounts,
            instrument_mount,
            optical_mount,
            optical_sensor,
        )
        from gondola.power_export import (
            _installation_context,
            _instrument_motion_bounds,
            screen_configurations,
        )

        doc = App.newDocument("DirectPowerMatrixFixture")
        try:
            mounts = []
            stations = {station.object_name: station for station in MODULE_STATIONS}
            for kind, name in equipment_mounts.MOUNT_NAMES.items():
                host = doc.addObject("App::Part", kind.capitalize() + "EquipmentModule")
                station = stations[host.Name]
                host.Placement = App.Placement(
                    App.Vector(station.x_mm, 0, 0),
                    App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
                )
                if kind == "electronics":
                    instrument = instrument_mount.build_mount(doc, host)
                    mounts.extend(instrument["printed"])
                else:
                    mount = equipment_mounts.build_mount(doc, host, kind)
                    mounts.append(mount)
            battery = doc.addObject("Part::Feature", "ModuleBatteryEnvelope")
            doc.BatteryEquipmentModule.addObject(battery)
            battery.Shape = Part.makeBox(16, 61, 15, App.Vector(-8, -30.5, 16.4))
            optical = optical_mount.build_optical_mount(doc, instrument["pitch_stage"])
            sensor_refs, sensor_reserves = optical_sensor.build_sensor(
                doc, optical["sensor_frame"]
            )
            registry = doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
            for category in (
                "PrintedParts",
                "HardwareParts",
                "ReferenceParts",
                "TapeReferences",
                "ClearanceVolumes",
            ):
                set_property(
                    registry,
                    category,
                    mounts + optical["printed"]
                    if category == "PrintedParts"
                    else optical["hardware"]
                    if category == "HardwareParts"
                    else [battery] + sensor_refs
                    if category == "ReferenceParts"
                    else sensor_reserves
                    if category == "ClearanceVolumes"
                    else [],
                    "App::PropertyLinkListGlobal",
                )
            doc.recompute()
            self.assertNotIn(
                battery.Name, _installation_context(doc, "TETHER_BEC_SVPDB")
            )
            self.assertIn(battery.Name, _installation_context(doc, "BATTERY_SVPDB"))
            bounds = _instrument_motion_bounds(doc, optical["group"])
            self.assertIn("Instrument/ElectronicsMount", bounds)
            from gondola.cad import world_shape

            for angle in (-20, -7, 0, 11, 20):
                instrument_mount.set_pitch(doc, angle)
                self.assertLess(
                    world_shape(doc.ElectronicsMount)
                    .cut(bounds["Instrument/ElectronicsMount"])
                    .Volume,
                    1e-5,
                )
            instrument_mount.set_pitch(doc, 0)
            screen = screen_configurations(doc)
            self.assertTrue(screen["passed"], screen)
            self.assertTrue(screen["default_configuration_clear"], screen)
            self.assertEqual(len(screen["configurations"]), 8)
            self.assertEqual(len(screen["navigation_compatibility_probes"]), 32)
            blocked = [
                r
                for r in screen["navigation_compatibility_probes"]
                if r["navigation"] == "MGF10A"
                and r["antenna_installation"] == "direct_sma"
            ]
            self.assertEqual(len(blocked), 8)
            self.assertTrue(all(not r["permitted"] for r in blocked))
            # Both sensors' common-platform operating field
            # block the direct helix; the remote SMA alternative stays available.
            direct_tether_helix = next(
                row
                for row in blocked
                if row["packaging"] == "DIRECT_CARRIER"
                and row["host"] == "BatteryEquipmentModule"
                and row["plan"] == "TETHER_BEC_SVPDB"
            )
            for bound in (
                "MTF02PContinuousOpticalFieldBound",
                "MTF01PContinuousOpticalFieldBound",
            ):
                self.assertTrue(
                    any(
                        hit["first"] == "NavigationDirectAntennaReserve"
                        and hit["second"] == bound
                        and hit["intersection_mm3"] > 1e-5
                        for hit in direct_tether_helix["collisions"]
                    ),
                    (bound, direct_tether_helix),
                )
            direct = [
                r
                for r in screen["navigation_compatibility_probes"]
                if r["packaging"] == "DIRECT_CARRIER" and r["permitted"]
            ]
            self.assertEqual(
                {(r["navigation"], r["antenna_installation"]) for r in direct},
                {
                    ("PAS", "integrated"),
                    ("MGA01", "integrated"),
                    ("MGF10A", "remote_sma"),
                },
            )
        finally:
            App.closeDocument(doc.Name)


if __name__ == "__main__":
    unittest.main()
