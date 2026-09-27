"""Optional power-platform fit, registration and unsupported installation guards."""

import json
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
    def test_integral_variants_support_both_board_contact_areas(self):
        from gondola.parts import equipment_mounts, stack_interface
        from gondola.parts import power_mount as p

        for host, part_name in stack_interface.MECHANICAL_HOSTS.items():
            with self.subTest(host=host):
                shape = p.platform_shape(host)
                self.assertTrue(shape.isValid())
                self.assertEqual(len(shape.Solids), 1)
                self.assertLess(p.deck_shape().cut(shape).Volume, 1e-6)
                kind = next(
                    k for k, v in equipment_mounts.MOUNT_NAMES.items() if v == part_name
                )
                lower = equipment_mounts.mount_shape(kind).copy()
                lower.translate(App.Vector(0, 0, -stack_interface.STACK_TOP_Z))
                self.assertLess(lower.cut(shape).Volume, 1e-6)
                self.assertGreater(shape.Volume, lower.Volume + p.deck_shape().Volume)
                self.assertEqual(p.platform_contract()["attachment_hardware_added"], 0)
                self.assertLessEqual(
                    max(
                        shape.BoundBox.XLength,
                        shape.BoundBox.YLength,
                        shape.BoundBox.ZLength,
                    ),
                    340,
                )

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
                    sum(name.startswith("PowerFoot") for name in physical), 0
                )
                self.assertNotIn("TetherDepartureReserve", reserves)
        with self.assertRaises(ValueError):
            p.local_shapes("BATTERY")

    def test_accessory_power_keeps_both_radio_connector_lanes_open(self):
        from gondola.parts import power_mount, stack_interface, wiring_reserves

        platform = power_mount.platform_shape("AccessoryEquipmentModule").copy()
        platform.translate(App.Vector(0, 0, stack_interface.STACK_TOP_Z))
        lanes = wiring_reserves.reserve_shapes()
        for name in (
            "RadioNegativeXConnectorReserve",
            "RadioPositiveXConnectorReserve",
        ):
            with self.subTest(connector=name):
                self.assertLess(platform.common(lanes[name]).Volume, 1e-6)
                self.assertGreater(platform.distToShape(lanes[name])[0], 0.9)

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
                    obj = equipment_mounts.build_mount(doc, host, kind)
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
            # A modified main carrier must be rejected before the alternate
            # host probe can replace it with a fresh, apparently valid shape.
            changed_main = App.openDocument(str(source))
            changed_main.AccessoryMount.Shape = Part.makeBox(100, 100, 100)
            changed_main.recompute()
            changed_path = out / "modified_main.FCStd"
            changed_main.saveAs(str(changed_path))
            App.closeDocument(changed_main.Name)
            changed_hash = file_sha256(changed_path)
            changed_carrier = audit_power_options(changed_path, out)
            self.assertFalse(changed_carrier["passed"])
            self.assertFalse(changed_carrier["main_carriers_match"])
            self.assertTrue(changed_carrier["read_only_artifacts"])
            self.assertEqual(changed_hash, file_sha256(changed_path))

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
