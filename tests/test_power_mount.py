"""Optional power-platform fit, registration and unsupported installation guards."""

import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class PowerMountTests(unittest.TestCase):
    def test_one_piece_flat_deck_and_true_through_holes(self):
        from gondola.parts import power_mount as p

        shape = p.platform_shape()
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids), 1)
        from gondola.parts import stack_interface

        for pattern in p.platform_contract()["standard_mounting"]["patterns"]:
            points = pattern["centres_xy_mm"]
            self.assertAlmostEqual(
                (App.Vector(*points[0], 0) - App.Vector(*points[1], 0)).Length,
                pattern["pitch_mm"],
            )
        for row, hole, outer in zip(
            p.standard_hole_rows(),
            stack_interface.board_hole_shapes(
                p.standard_hole_rows(), p.DECK_BOTTOM_Z, 2
            ),
            stack_interface.board_hole_shapes(
                p.standard_hole_rows(), p.DECK_BOTTOM_Z, 2, border=1.5
            ),
            strict=True,
        ):
            self.assertLess(shape.common(hole).Volume, 1e-6)
            self.assertLess(outer.cut(hole).cut(shape).Volume, 1e-6)
            self.assertEqual(
                row["diameter_mm"], 2.6 if row["fastener"] == "M2" else 3.6
            )
        from gondola.parts import equipment_mounts

        self.assertEqual(p.DECK_SIZE_MM, equipment_mounts.COMMON_DECK_SIZE)
        self.assertEqual(
            p.platform_contract()["common_plate"],
            equipment_mounts.common_plate_contract(),
        )
        holes = equipment_mounts.common_plate_hole_shapes(p.DECK_BOTTOM_Z, 2)
        self.assertEqual(len(holes), 20)
        for hole in holes:
            self.assertLess(shape.common(hole).Volume, 1e-6)
        # The symmetric plate ends and usable deck regions remain solid. There are
        # no cable-tie slots; straps wrap the existing outline.
        for x, y in (
            (-20, -14.5),
            (-20, 14.5),
            (20, -14.5),
            (20, 14.5),
            (25, -5),
            (25, 5),
            (0, -34),
            (0, 34),
        ):
            region = Part.makeCylinder(0.5, 2, App.Vector(x, y, p.DECK_BOTTOM_Z))
            self.assertLess(region.cut(shape).Volume, 1e-6)
        bounds = shape.BoundBox
        self.assertLessEqual(max(bounds.XLength, bounds.YLength, bounds.ZLength), 340)

    def test_regulator_bodies_and_connection_lanes_do_not_intersect_deck(self):
        from gondola.parts import power_mount as p
        from gondola.power_export import _internal_collisions

        for plan in ("TETHER_BEC_SVPDB", "BATTERY_SVPDB"):
            with self.subTest(plan=plan):
                physical, reserves = p.local_shapes(plan)
                self.assertEqual(_internal_collisions(physical, reserves), [])
                board_names = [
                    name for name in physical if name.startswith("PowerModule")
                ]
                for name in board_names:
                    self.assertLess(
                        physical[name].common(physical["PowerPlatform"]).Volume, 1e-6
                    )
                if len(board_names) == 2:
                    self.assertLess(
                        physical[board_names[0]]
                        .common(physical[board_names[1]])
                        .Volume,
                        1e-6,
                    )
                self.assertEqual(
                    sum(name.startswith("PowerFoot") for name in physical), 4
                )
                self.assertNotIn("TetherDepartureReserve", reserves)
        with self.assertRaises(ValueError):
            p.local_shapes("BATTERY")

    def test_host_translation_and_occupied_optical_rejection(self):
        from gondola.parts import power_mount as p
        from gondola.parts import stack_interface as s

        doc = App.newDocument("PowerStackHostTest")
        try:
            hosts = {
                name: doc.addObject("App::Part", name) for name in s.MECHANICAL_HOSTS
            }
            optical = doc.addObject("App::Part", "OpticalFlowModule")
            hosts["BatteryEquipmentModule"].addObject(optical)
            with self.assertRaises(ValueError):
                p.host_placement(doc, "BatteryEquipmentModule")
            host = hosts["AccessoryEquipmentModule"]
            host.Placement = App.Placement(
                App.Vector(80, 20, 7), App.Rotation(App.Vector(0, 0, 1), 180)
            )
            expected = host.getGlobalPlacement().multVec(
                App.Vector(*s.host_origin_xy(host.Name), s.STACK_TOP_Z)
            )
            self.assertLess(
                (p.host_placement(doc, host.Name).Base - expected).Length, 1e-6
            )
            with self.assertRaises(ValueError):
                p.host_placement(doc, "PropulsionModule")
        finally:
            App.closeDocument(doc.Name)

    def test_analytic_xy_bound_contains_extreme_translated_rotated_board(self):
        from gondola.parts import power_mount, stack_interface
        from gondola.power_export import _xy_registration_bound

        board = power_mount.local_shapes()[0]["PowerModule0"]
        bound = _xy_registration_bound(board)
        g = stack_interface.MAX_RADIAL_FLOAT
        radius = math.hypot(*stack_interface.CLAMP_CENTRES[0])
        angle = math.degrees(2 * math.asin(g / (2 * radius)))
        # Sanity-check the continuous analytic enclosure, not a sampled proof.
        for yaw in (-angle, 0, angle):
            for x, y in ((g, 0), (-g, 0), (0, g), (0, -g)):
                moved = board.copy()
                moved.rotate(App.Vector(), App.Vector(0, 0, 1), yaw)
                moved.translate(App.Vector(x, y, 0))
                self.assertLess(moved.cut(bound).Volume, 1e-6)

    def test_saved_audit_rejects_body_alternative_host_and_source_changes(self):
        from gondola.cad import set_property
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.contracts.power_options import power_option_contract
        from gondola.parts import equipment_mounts, stack_interface
        from gondola.power_export import (
            ARTIFACT_NAMES,
            audit_power_options,
            export_power_options,
        )
        from gondola.provenance import file_sha256

        # This case targets saved-artifact and audit gates. A stable identity keeps
        # unrelated parallel repository edits out of this isolated fixture test.
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch("gondola.power_export.source_fingerprint", return_value="a" * 64),
        ):
            out = Path(temporary)
            doc = App.newDocument("PowerExportFixture")
            try:
                mounts = []
                stations = {station.object_name: station for station in MODULE_STATIONS}
                for kind, name in equipment_mounts.MOUNT_NAMES.items():
                    host_name = kind.capitalize() + "EquipmentModule"
                    host = doc.addObject("App::Part", host_name)
                    # Use the actual carrier stations/orientations. The old
                    # all-zero-yaw fixture pointed the tether toward the other
                    # optical host and was correctly rejected by its field bound.
                    station = stations[host_name]
                    host.Placement = App.Placement(
                        App.Vector(station.x_mm, 0, 0),
                        App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
                    )
                    obj = doc.addObject("Part::Feature", name)
                    obj.Shape = equipment_mounts.mount_shape(kind)
                    host.addObject(obj)
                    mounts.append(obj)
                optical = doc.addObject("App::Part", "OpticalFlowModule")
                stack_interface.attach_to_host(optical, doc.BatteryEquipmentModule)
                registry = doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
                set_property(registry, "OptionalPowerDocument", ARTIFACT_NAMES[0])
                set_property(
                    registry,
                    "OptionalPowerContract",
                    json.dumps(power_option_contract(), sort_keys=True),
                )
                for category in (
                    "PrintedParts",
                    "HardwareParts",
                    "ReferenceParts",
                    "TapeReferences",
                    "ClearanceVolumes",
                ):
                    registry.addProperty("App::PropertyLinkListGlobal", category)
                    setattr(
                        registry, category, mounts if category == "PrintedParts" else []
                    )
                doc.recompute()
                source = out / "gondola.FCStd"
                doc.saveAs(str(source))
                export_power_options(doc, out)
            finally:
                App.closeDocument(doc.Name)
            report = audit_power_options(source, out)
            self.assertTrue(report["passed"], report)
            with patch(
                "gondola.power_export.screen_configurations",
                side_effect=({"passed": True}, {"passed": False}),
            ):
                rejected_alternate = audit_power_options(source, out)
            self.assertFalse(rejected_alternate["passed"])
            self.assertFalse(rejected_alternate["alternate_optical_hosts_passed"])
            self.assertTrue(rejected_alternate["configuration_screen"]["passed"])
            self.assertTrue(rejected_alternate["read_only_artifacts"])

            source_changed = False

            def screen_while_source_changes(_doc):
                nonlocal source_changed
                source_changed = True
                return {"passed": True}

            with (
                patch(
                    "gondola.power_export.screen_configurations",
                    side_effect=screen_while_source_changes,
                ),
                patch(
                    "gondola.power_export.source_fingerprint",
                    side_effect=lambda: ("b" if source_changed else "a") * 64,
                ),
            ):
                changed_source = audit_power_options(source, out)
            self.assertFalse(changed_source["passed"])
            self.assertFalse(changed_source["source_code_unchanged"])
            self.assertTrue(changed_source["alternate_optical_hosts_passed"])
            self.assertTrue(changed_source["read_only_artifacts"])
            optional = App.openDocument(str(out / ARTIFACT_NAMES[0]))
            original_plan = optional.PowerOptionModule.PowerPlanContract
            optional.PowerOptionModule.PowerPlanContract = "{}"
            optional.recompute()
            optional.save()
            App.closeDocument(optional.Name)
            rejected_plan = audit_power_options(source, out)
            self.assertFalse(rejected_plan["passed"])
            self.assertFalse(rejected_plan["power_plan_contract_matches"])
            self.assertTrue(all(rejected_plan["native_shape_checks"].values()))
            optional = App.openDocument(str(out / ARTIFACT_NAMES[0]))
            optional.PowerOptionModule.PowerPlanContract = original_plan
            optional.recompute()
            optional.save()
            App.closeDocument(optional.Name)
            optional = App.openDocument(str(out / ARTIFACT_NAMES[0]))
            optional.PowerModule0.Shape = Part.makeBox(100, 100, 100)
            optional.recompute()
            optional.save()
            App.closeDocument(optional.Name)
            before = file_sha256(out / ARTIFACT_NAMES[0])
            report = audit_power_options(source, out)
            self.assertFalse(report["passed"])
            self.assertFalse(report["native_shape_checks"]["PowerModule0"])
            self.assertTrue(report["read_only_artifacts"])
            self.assertEqual(before, file_sha256(out / ARTIFACT_NAMES[0]))


if __name__ == "__main__":
    unittest.main()
