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
    def test_one_piece_deck_has_complete_slot_lands_and_true_beam_through_openings(
        self,
    ):
        from gondola.parts import equipment_mounts
        from gondola.parts import power_mount as p
        from gondola.validation.equipment import carrier_opening_checks

        shape = p.platform_shape()
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids), 1)
        self.assertEqual(p.DECK_SIZE_MM, equipment_mounts.COMMON_DECK_SIZE)
        self.assertEqual(
            p.platform_contract()["common_plate"],
            equipment_mounts.common_plate_contract(),
        )
        self.assertEqual(
            p.standard_slot_rows(), equipment_mounts.standard_slot_rows("electronics")
        )
        report = carrier_opening_checks(
            shape,
            bottom=p.DECK_BOTTOM_Z,
            thickness=p.DECK_THICKNESS_MM,
            through_bottom=0,
            through_depth=p.SUPPORT_Z,
        )
        self.assertTrue(report["passed"], report)
        self.assertEqual((report["fixed_bore_count"], report["slot_count"]), (4, 16))
        # Central board support and both broad end regions are continuous. No
        # dedicated cable-tie slots are required for straps around the outline.
        for x, y in ((0, 0), (0, -23), (0, 23), (0, -29), (0, 29)):
            region = Part.makeCylinder(0.5, 2, App.Vector(x, y, p.DECK_BOTTOM_Z))
            self.assertLess(region.cut(shape).Volume, 1e-6)
        bounds = shape.BoundBox
        self.assertLessEqual(max(bounds.XLength, bounds.YLength, bounds.ZLength), 340)

    def test_slot_floor_in_underlying_beam_cannot_pass_a_deck_only_probe(self):
        from gondola.parts import mounting_slots, stack_interface
        from gondola.parts import power_mount as p
        from gondola.validation.equipment import carrier_opening_checks

        original = p.platform_shape()
        # The diagonal beam crosses this arc. Reintroduce only material below
        # the deck, leaving the entire declared two-mm deck opening intact.
        row = next(row for row in mounting_slots.rows() if row["kind"] == "arc")
        floor = mounting_slots.shape(row, 0, 0.5).common(stack_interface.tower_shape())
        self.assertGreater(floor.Volume, 0.1)
        changed = original.fuse(floor).removeSplitter()
        self.assertTrue(changed.isValid())
        self.assertEqual(len(changed.Solids), 1)
        deck_only = carrier_opening_checks(
            changed, bottom=p.DECK_BOTTOM_Z, thickness=p.DECK_THICKNESS_MM
        )
        self.assertTrue(deck_only["passed"], deck_only)
        full = carrier_opening_checks(
            changed,
            bottom=p.DECK_BOTTOM_Z,
            thickness=p.DECK_THICKNESS_MM,
            through_bottom=0,
            through_depth=p.SUPPORT_Z,
        )
        self.assertFalse(full["passed"])
        rejected = next(
            item for item in full["mounting_slots"] if item["name"] == row["name"]
        )
        self.assertGreater(rejected["through_slot_obstruction_mm3"], 0.1)
        self.assertLess(rejected["missing_continuous_full_thickness_land_mm3"], 1e-6)

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

    def test_slot_registration_bound_contains_coupled_extreme_poses(self):
        from gondola.parts import power_mount, stack_interface
        from gondola.power_export import _xy_registration_bound

        board = power_mount.local_shapes()[0]["PowerModule0"]
        bound = _xy_registration_bound(board)
        allowance = stack_interface.COMBINED_AXIS_CLEARANCE
        # Full slot travel permits coupled yaw/translation beyond the former
        # circular-hole displacement disk. Check genuine capsule-valid poses.
        beyond_round_hole = False
        for yaw, dx, dy in (
            (0, 1, 0),
            (0, 0, 1),
            (-2.5, 0, 0),
            (-2, 0, 1.5),
            (-2, 0, -1.5),
        ):
            pose = App.Placement(
                App.Vector(dx, dy, 0), App.Rotation(App.Vector(0, 0, 1), yaw)
            )
            for x, y in stack_interface.CLAMP_CENTRES:
                point = pose.multVec(App.Vector(x, y, 0))
                low, high = (13, 23) if y > 0 else (-23, -13)
                closest_y = max(low, min(high, point.y))
                self.assertLessEqual(
                    math.hypot(point.x - x, point.y - closest_y), allowance
                )
                beyond_round_hole |= math.hypot(point.x - x, point.y - y) > allowance
            moved = board.copy()
            moved.Placement = pose
            self.assertLess(moved.cut(bound).Volume, 1e-6)
        self.assertTrue(beyond_round_hole)

    def test_power_feet_use_common_slots_and_have_clear_nut_access(self):
        from gondola.parts import equipment_mounts
        from gondola.parts import stack_interface as s

        tower = s.tower_shape()
        carrier = equipment_mounts.mount_shape("battery")
        for name, tool in s.clamp_tool_reservations():
            self.assertLess(tool.common(tower).Volume, 1e-6, name)
        for index, (x, y) in enumerate(s.CLAMP_CENTRES):
            bore = Part.makeCylinder(
                s.CLAMP_HOLE_DIAMETER / 2,
                s.DECK_THICKNESS,
                App.Vector(x, y, s.HOST_DECK_BOTTOM_Z),
            )
            self.assertLess(bore.common(carrier).Volume, 1e-6)
            foot = s.foot_shape(index, bottom=s.HOST_DECK_BOTTOM_Z)
            contact = foot.common(carrier).Volume / s.DECK_THICKNESS
            self.assertGreater(contact, 50)
            self.assertLessEqual(
                max(
                    abs(foot.BoundBox.XMin),
                    abs(foot.BoundBox.XMax),
                    abs(foot.BoundBox.YMin),
                    abs(foot.BoundBox.YMax),
                ),
                32,
            )

    def test_power_attachment_rejects_missing_host_seat_and_blocked_slot(self):
        from gondola.parts import equipment_mounts, power_mount
        from gondola.parts import stack_interface as s

        carrier = equipment_mounts.mount_shape("accessory").copy()
        carrier.translate(App.Vector(0, 0, -s.STACK_TOP_Z))
        self.assertTrue(power_mount.attachment_check(carrier)["passed"])
        changed = carrier.cut(
            Part.makeBox(
                3, 3, 2, App.Vector(28, 24, -s.TOWER_HEIGHT - s.DECK_THICKNESS)
            )
        )
        self.assertFalse(power_mount.attachment_check(changed)["passed"])
        changed = carrier.fuse(
            Part.makeCylinder(
                0.6,
                s.DECK_THICKNESS,
                App.Vector(27, 23, -s.TOWER_HEIGHT - s.DECK_THICKNESS),
            )
        )
        self.assertFalse(power_mount.attachment_check(changed)["passed"])

    def test_saved_audit_rejects_body_alternative_host_and_source_changes(self):
        from gondola.cad import set_property
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.contracts.power_options import power_option_contract
        from gondola.parts import equipment_mounts, optical_interface
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
                optical_interface.attach_to_host(optical, doc.BatteryEquipmentModule)
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
                side_effect=(
                    {"passed": True, "default_configuration_clear": True},
                    {"passed": False},
                ),
            ):
                rejected_alternate = audit_power_options(source, out)
            self.assertFalse(rejected_alternate["passed"])
            self.assertFalse(rejected_alternate["alternate_optical_hosts_passed"])
            self.assertTrue(rejected_alternate["configuration_screen"]["passed"])
            self.assertTrue(rejected_alternate["read_only_artifacts"])

            with patch(
                "gondola.power_export.screen_configurations",
                return_value={"passed": True, "default_configuration_clear": False},
            ):
                blocked_illustrated = audit_power_options(source, out)
            self.assertFalse(blocked_illustrated["passed"])
            self.assertFalse(blocked_illustrated["illustrated_configuration_clear"])
            self.assertTrue(blocked_illustrated["alternate_optical_hosts_passed"])

            source_changed = False

            def screen_while_source_changes(_doc):
                nonlocal source_changed
                source_changed = True
                return {"passed": True, "default_configuration_clear": True}

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
