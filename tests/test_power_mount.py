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

    from gondola.parts import mounting_plate
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
            centre_hole_diameter=mounting_plate.CENTRE_HOLE_DIAMETER_MM,
        )
        self.assertTrue(report["passed"], report)
        self.assertEqual((report["fixed_bore_count"], report["slot_count"]), (1, 40))
        # The new centre bore leaves surrounding board support intact. No
        # dedicated cable-tie slots are required for straps around the outline.
        for x, y in ((0, 3), (0, -23), (0, 23), (0, -29), (0, 29)):
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
        row = next(row for row in mounting_slots.rows() if row["kind"] == "polyline")
        floor = mounting_slots.shape(row, 0, 0.5).common(stack_interface.tower_shape())
        self.assertGreater(floor.Volume, 0.1)
        changed = original.fuse(floor).removeSplitter()
        self.assertTrue(changed.isValid())
        self.assertEqual(len(changed.Solids), 1)
        deck_only = carrier_opening_checks(
            changed,
            bottom=p.DECK_BOTTOM_Z,
            thickness=p.DECK_THICKNESS_MM,
            centre_hole_diameter=mounting_plate.CENTRE_HOLE_DIAMETER_MM,
        )
        self.assertTrue(deck_only["passed"], deck_only)
        full = carrier_opening_checks(
            changed,
            bottom=p.DECK_BOTTOM_Z,
            thickness=p.DECK_THICKNESS_MM,
            through_bottom=0,
            through_depth=p.SUPPORT_Z,
            centre_hole_diameter=mounting_plate.CENTRE_HOLE_DIAMETER_MM,
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
                physical, reserves = p.local_shapes(plan, packaging="PORTAL")
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
            p.local_shapes("BATTERY", packaging="PORTAL")

    def test_accessory_portal_registration_preserves_complete_radio_connector_lanes(
        self,
    ):
        from gondola.parts import equipment_envelopes, wiring_reserves
        from gondola.power_export import _registration_bounds

        # Independent carrier-frame witnesses:24x18.2x5.8mm radio below Z16,
        # rotated90deg at(26,-17). Preserve each complete15mm withdrawal lane
        # with2mm side/top allowance, rather than cutting a pocket around a bolt.
        expected = {
            "ModuleRadioEnvelope": Part.makeBox(
                18.2, 24, 5.8, App.Vector(16.9, -29, 10.2)
            ),
            "RadioNegativeXConnectorReserve": Part.makeBox(
                22.2, 15, 7.8, App.Vector(14.9, -44, 8.2)
            ),
            "RadioPositiveXConnectorReserve": Part.makeBox(
                22.2, 15, 7.8, App.Vector(14.9, -5, 8.2)
            ),
        }
        generated = {
            "ModuleRadioEnvelope": equipment_envelopes.radio_envelope_shape(),
            **{
                name: shape
                for name, shape in wiring_reserves.reserve_shapes().items()
                if name in expected
            },
        }
        self.assertEqual(set(generated), set(expected))
        for name, witness in expected.items():
            with self.subTest(part=name):
                self.assertLess(generated[name].cut(witness).Volume, 1e-6)
                self.assertLess(witness.cut(generated[name]).Volume, 1e-6)

        for plan in ("TETHER_BEC_SVPDB", "BATTERY_SVPDB"):
            bounds = _registration_bounds(plan)
            self.assertTrue({"PowerFootBolt0", "PowerFootBolt1"} <= set(bounds))
            placed = {}
            for name, bound in bounds.items():
                placed[name] = bound.copy()
                # Carrier top Z19 + integral32mm portal height.
                placed[name].translate(App.Vector(0, 0, 51))
            for name, bound in placed.items():
                for device, witness in expected.items():
                    with self.subTest(plan=plan, component=name, device=device):
                        self.assertLess(bound.common(witness).Volume, 1e-6)

            # The previousY=-11 layout leaves the whole positive-end connector
            # lane inside the conservative foot-bolt registration region. Keep
            # this rejected case so an empty or shortened bound cannot pass.
            old_lane = expected["RadioPositiveXConnectorReserve"].copy()
            old_lane.translate(App.Vector(0, 6, 0))
            old_overlap = sum(
                bound.common(old_lane).Volume
                for name, bound in placed.items()
                if name.startswith("PowerFootBolt")
            )
            with self.subTest(plan=plan, mutation="previous radio position"):
                self.assertGreater(old_overlap, 0.01)

    def test_optional_context_preserves_common_stage_parent_pose_and_control(self):
        from gondola.cad import world_shape
        from gondola.parts import (
            instrument_mount,
            optical_mount,
            power_mount,
            stack_interface,
        )

        doc = App.newDocument("PowerOpticalInstrument")
        option = None
        try:
            hosts = {
                name: doc.addObject("App::Part", name)
                for name in (
                    *stack_interface.MECHANICAL_HOSTS,
                    "ElectronicsEquipmentModule",
                )
            }
            hosts["BatteryEquipmentModule"].Placement.Base.x = -112
            hosts["AccessoryEquipmentModule"].Placement.Base.x = 84
            instrument = instrument_mount.build_mount(
                doc, hosts["ElectronicsEquipmentModule"]
            )
            optical = optical_mount.build_optical_mount(doc, instrument["pitch_stage"])[
                "group"
            ]
            for pitch in (-20, 0, 20):
                instrument_mount.set_pitch(doc, pitch)
                before_pose = optical.Placement.copy()
                before_world = world_shape(doc.ElectronicsMount)
                option = power_mount.create_option_document(doc)
                self.assertEqual(
                    json.loads(option.PowerOptionModule.OpticalAttachment),
                    {
                        "mode": "instrument",
                        "host": "InstrumentPitchStage",
                        "support_part": "ElectronicsMount",
                        "sensor_frame_origin_in_stage_mm": [0.0, 0.0, 0.0],
                    },
                )
                self.assertEqual(
                    optical.getParentGeoFeatureGroup(), instrument["pitch_stage"]
                )
                self.assertEqual(float(instrument["pitch_stage"].Pitch), pitch)
                self.assertTrue(optical.Placement.isSame(before_pose, 1e-7))
                after_world = world_shape(doc.ElectronicsMount)
                self.assertLess(abs(before_world.cut(after_world).Volume), 1e-6)
                self.assertLess(abs(after_world.cut(before_world).Volume), 1e-6)
                self.assertNotIn(
                    "OpticalCarrierHost", option.PowerOptionModule.PropertiesList
                )
                App.closeDocument(option.Name)
                option = None
            # An obsolete mode claim cannot be silently preserved in an export.
            optical.OpticalAttachmentMode = "carrier"
            with self.assertRaisesRegex(ValueError, "common instrument attachment"):
                power_mount.create_option_document(doc)
        finally:
            if option is not None:
                App.closeDocument(option.Name)
            for name in list(App.listDocuments()):
                if name.startswith("GondolaPowerOptions"):
                    App.closeDocument(name)
            App.closeDocument(doc.Name)

    def test_host_translation_and_attached_optical_module(self):
        from gondola.parts import instrument_mount, optical_mount
        from gondola.parts import power_mount as p
        from gondola.parts import stack_interface as s

        doc = App.newDocument("PowerStackHostTest")
        try:
            hosts = {
                name: doc.addObject("App::Part", name)
                for name in (*s.MECHANICAL_HOSTS, "ElectronicsEquipmentModule")
            }
            instrument = instrument_mount.build_mount(
                doc, hosts["ElectronicsEquipmentModule"]
            )
            optical = optical_mount.build_optical_mount(doc, instrument["pitch_stage"])[
                "group"
            ]
            self.assertEqual(
                optical.getParentGeoFeatureGroup(), instrument["pitch_stage"]
            )
            self.assertIsNotNone(
                p.host_placement(doc, "BatteryEquipmentModule", packaging="PORTAL")
            )
            with self.assertRaises(ValueError):
                p.host_placement(doc, "ElectronicsEquipmentModule", packaging="PORTAL")
            self.assertFalse(s.interface_contract("ElectronicsMount")["host_supported"])
            host = hosts["AccessoryEquipmentModule"]
            host.Placement = App.Placement(
                App.Vector(80, 20, 7), App.Rotation(App.Vector(0, 0, 1), 180)
            )
            expected = host.getGlobalPlacement().multVec(
                App.Vector(*s.host_origin_xy(host.Name), s.STACK_TOP_Z)
            )
            self.assertLess(
                (
                    p.host_placement(doc, host.Name, packaging="PORTAL").Base - expected
                ).Length,
                1e-6,
            )
            with self.assertRaises(ValueError):
                p.host_placement(doc, "PropulsionModule", packaging="PORTAL")
        finally:
            App.closeDocument(doc.Name)

    def test_slot_registration_bound_contains_coupled_extreme_poses(self):
        from gondola.parts import power_mount, stack_interface
        from gondola.power_export import _xy_registration_bound

        board = power_mount.local_shapes(packaging="PORTAL")[0]["PowerModule0"]
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
                low, high = (13, 19) if y > 0 else (-19, -13)
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
                33,
            )

    def test_repositioned_power_feet_support_complete_leg_roots(self):
        from gondola.parts import stack_interface as s

        self.assertEqual(s.ANCHOR_CENTRES, ((-20.0, -20.0), (20.0, 20.0)))
        self.assertEqual(s.CLAMP_CENTRES, ((-27.0, -19.0), (27.0, 19.0)))
        # Independent thin sections at the base of each2x8mm diagonal leg.
        for index, angle in enumerate((225, 45)):
            root = Part.makeBox(
                2, 8, 0.1, App.Vector(math.hypot(20, 20) - 1.4, -4, -32)
            )
            root.rotate(App.Vector(), App.Vector(0, 0, 1), angle)
            self.assertLess(root.cut(s.foot_shape(index)).Volume, 1e-6)

    def test_power_attachment_rejects_missing_host_seat_and_blocked_slot(self):
        from gondola.parts import equipment_mounts, power_mount
        from gondola.parts import stack_interface as s

        carrier = equipment_mounts.mount_shape("accessory").copy()
        carrier.translate(App.Vector(0, 0, -s.STACK_TOP_Z))
        self.assertTrue(power_mount.attachment_check(carrier)["passed"])
        changed = carrier.cut(
            Part.makeBox(
                3, 3, 2, App.Vector(28, 21, -s.TOWER_HEIGHT - s.DECK_THICKNESS)
            )
        )
        self.assertFalse(power_mount.attachment_check(changed)["passed"])
        changed = carrier.fuse(
            Part.makeCylinder(
                0.6,
                s.DECK_THICKNESS,
                App.Vector(27, 19, -s.TOWER_HEIGHT - s.DECK_THICKNESS),
            )
        )
        self.assertFalse(power_mount.attachment_check(changed)["passed"])

    def test_saved_audit_rejects_body_alternative_host_and_source_changes(self):
        from gondola.cad import set_property
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.contracts.power_options import power_option_contract
        from gondola.parts import (
            equipment_mounts,
            instrument_mount,
            optical_mount,
            optical_sensor,
        )
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
                instrument_hardware = []
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
                    if kind == "electronics":
                        instrument = instrument_mount.build_mount(doc, host)
                        mounts.extend(instrument["printed"])
                        instrument_hardware.extend(instrument["hardware"])
                        continue
                    obj = doc.addObject("Part::Feature", name)
                    obj.Shape = equipment_mounts.mount_shape(kind)
                    host.addObject(obj)
                    mounts.append(obj)
                # Configuration screening requires the actual saved integral carrier and
                # bounded native stage, not a metadata-only optical placeholder.
                optical = optical_mount.build_optical_mount(
                    doc, doc.InstrumentPitchStage
                )
                sensor_references, sensor_clearances = optical_sensor.build_sensor(
                    doc, doc.OpticalSensorFrame
                )
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
                        registry,
                        category,
                        mounts + optical["printed"]
                        if category == "PrintedParts"
                        else optical["hardware"] + instrument_hardware
                        if category == "HardwareParts"
                        else sensor_references
                        if category == "ReferenceParts"
                        else sensor_clearances
                        if category == "ClearanceVolumes"
                        else [],
                    )
                doc.recompute()
                source = out / "gondola.FCStd"
                doc.saveAs(str(source))
                export_power_options(doc, out)
            finally:
                App.closeDocument(doc.Name)
            report = audit_power_options(source, out)
            self.assertTrue(report["passed"], report)
            optional = App.openDocument(str(out / ARTIFACT_NAMES[0]))
            optional.Context_BatteryMount.SourceRole = "Clearance"
            optional.save()
            App.closeDocument(optional.Name)
            changed_role = audit_power_options(source, out)
            self.assertFalse(changed_role["passed"])
            self.assertFalse(changed_role["context_roles_match"])
            self.assertTrue(changed_role["context_shapes_match"])
            optional = App.openDocument(str(out / ARTIFACT_NAMES[0]))
            optional.Context_BatteryMount.SourceRole = "Printed"
            optional.save()
            App.closeDocument(optional.Name)
            with patch(
                "gondola.power_export.screen_configurations",
                return_value={"passed": True, "default_configuration_clear": False},
            ):
                blocked_illustrated = audit_power_options(source, out)
            self.assertFalse(blocked_illustrated["passed"])
            self.assertFalse(blocked_illustrated["illustrated_configuration_clear"])

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
