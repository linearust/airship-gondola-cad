"""Bought-carbon identity, independent clamps and honest contact reservations."""

import json
import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


def build_fixture(name):
    from gondola.cad import create_group, set_property
    from gondola.contracts.design import MODULE_STATIONS
    from gondola.parts import equipment_envelopes, rail, stock_adapter

    doc = App.newDocument(name)
    groups = {}
    for station in MODULE_STATIONS:
        group = create_group(doc, station.object_name, station.object_name)
        group.Placement = App.Placement(
            App.Vector(station.x_mm, 0, station.z_mm),
            App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
        )
        groups[group.Name] = group
    hardware = []
    plates = []
    for kind in stock_adapter.MOUNT_KINDS:
        group = groups[kind.capitalize() + "EquipmentModule"]
        result = stock_adapter.build_stock_adapter(doc, group, kind)
        hardware.extend(result["hardware"])
        plates.extend(result["plates"])
    for row in stock_adapter.joint_specs():
        hardware.extend(
            rail.build_clamp_hardware(
                doc,
                groups[row["parent_name"]],
                row["clamp_prefix"],
                plate_thickness_mm=row["plate_thickness_mm"],
                centre_xy_mm=row["local_centre_xy"],
                parent_z_mm=row["parent_z_mm"],
            )
        )
    references, clearances = equipment_envelopes.build_equipment(
        doc,
        groups["BatteryEquipmentModule"],
        groups["ElectronicsEquipmentModule"],
        groups["AccessoryEquipmentModule"],
    )
    registry = doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
    for key, objects in (
        ("PrintedParts", []),
        ("HardwareParts", hardware),
        ("EquipmentMounts", plates),
        ("ReferenceParts", references),
        ("TapeReferences", []),
        ("ClearanceVolumes", clearances),
    ):
        set_property(registry, key, objects, "App::PropertyLinkListGlobal")
    doc.recompute()
    return doc


@unittest.skipIf(App is None, "Requires FreeCAD")
class EquipmentMountShapeTests(unittest.TestCase):
    def test_four_equal_bought_plates_preserve_twelve_nominal_bores(self):
        from gondola.contracts import stack_adapter as spec
        from gondola.parts import stock_adapter as stock

        for row in stock.joint_specs():
            shape = stock.plate_shape(centre_xy_mm=row["local_centre_xy"])
            self.assertTrue(shape.isValid())
            self.assertEqual(len(shape.Solids), 1)
            cx, cy = row["local_centre_xy"]
            for pitch in (16, 20, 25.5):
                for x, y in spec.hole_centres(pitch, 45):
                    bore = Part.makeCylinder(1, 1, App.Vector(cx + x, cy + y, 7))
                    self.assertLess(abs(shape.common(bore).Volume), 1e-7)
        self.assertEqual(len(stock.joint_specs()), 4)

    def test_only_opposed16_y_axes_join_rail_and_do_not_match_pas23(self):
        from gondola.contracts import stack_adapter as spec
        from gondola.parts import equipment_mounts as mounts

        self.assertEqual(len(spec.RAIL_FIX_CENTRES), 2)
        self.assertTrue(all(abs(x) < 1e-9 for x, y in spec.RAIL_FIX_CENTRES))
        self.assertAlmostEqual(spec.RAIL_TRACK_SPACING_MM, 16 * math.sqrt(2))
        self.assertNotAlmostEqual(spec.RAIL_TRACK_SPACING_MM, 23, places=2)
        self.assertEqual(mounts.mount_hole_centres("accessory"), ())
        self.assertEqual(
            mounts.mount_contract("accessory")["device_fastening_axes_xy_mm"], ()
        )

    def test_pad_reservation_cannot_certify_material_and_rejects_shifted_body(self):
        from gondola.parts import (
            equipment_envelopes as devices,
        )
        from gondola.parts import (
            equipment_mounts as mounts,
        )
        from gondola.parts import (
            stock_adapter,
        )
        from gondola.validation.equipment_options import adhesive_support_check

        support = stock_adapter.plate_shape(centre_xy_mm=mounts.RADIO_CENTRE_XY)
        body = devices.radio_envelope_shape()

        def check(part, face="top"):
            return adhesive_support_check(
                support,
                part,
                mounts.RADIO_CENTRE_XY,
                mounts.RADIO_ADHESIVE_SIZE,
                face=face,
            )

        report = check(body)
        self.assertTrue(report["passed"], report)
        self.assertFalse(report["continuous_support_area_verified"])
        self.assertIsNone(report["received_contact_area_mm2"])
        self.assertFalse(report["physical_contact_qualified"])
        self.assertAlmostEqual(report["adhesive_allowance_mm"], 3)
        self.assertFalse(check(body, "bottom")["passed"])
        for delta in ((8, 0, 0), (0, 0, -1), (0, 0, 1)):
            changed = body.copy()
            changed.translate(App.Vector(*delta))
            self.assertFalse(check(changed)["passed"])

    def test_saved_plate_damage_rejected_without_inventing_adhesive_contact(self):
        from gondola.parts import (
            equipment_envelopes as devices,
        )
        from gondola.parts import (
            equipment_mounts as mounts,
        )
        from gondola.parts import (
            stock_adapter,
        )
        from gondola.validation.equipment_options import adhesive_support_check

        shape = stock_adapter.plate_shape(centre_xy_mm=mounts.RADIO_CENTRE_XY)
        changed = shape.cut(Part.makeBox(2, 2, 2, App.Vector(-25, -1, 6.5)))
        report = adhesive_support_check(
            changed,
            devices.radio_envelope_shape(),
            mounts.RADIO_CENTRE_XY,
            mounts.RADIO_ADHESIVE_SIZE,
        )
        self.assertFalse(report["passed"])
        self.assertFalse(report["physical_contact_qualified"])

    def test_diagonal_underbody_strip_clears_actual_clamp_heads(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import rail

        strip = mounts.fc_wiring_reserve_shape()
        self.assertAlmostEqual(strip.BoundBox.ZLength, 8)
        for row in rail.clamp_rows():
            self.assertLess(abs(strip.common(row["shape"]).Volume), 1e-7)
            self.assertGreaterEqual(strip.distToShape(row["shape"])[0], 1.5)


@unittest.skipIf(App is None, "Requires FreeCAD")
class FCInstallationTests(unittest.TestCase):
    def setUp(self):
        self.doc = build_fixture("FCIdentityOnBoughtCarbon")
        self.addCleanup(App.closeDocument, self.doc.Name)

    def test_native_board_pose_preserves_heading_after_carrier_turn(self):
        from gondola.validation.equipment import fc_installation_check

        result = fc_installation_check(self.doc)
        self.assertTrue(result["passed"], result)

    def test_unchanged_board_shape_cannot_hide_stale_controller_identity(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.validation.baseline import procurement_and_scope_metadata
        from gondola.validation.equipment import fc_installation_check

        board = self.doc.ModuleFCEnvelope
        self.assertIn(interfaces.FC_MODEL, board.Label)
        original = board.Shape.copy()
        contract = json.loads(json.dumps(interfaces.flight_controller_contract()))
        self.assertIn("FlightControllerContract", procurement_and_scope_metadata(board))
        contract["model"] = "MicoAir743v2-AIO-35A"
        board.FlightControllerContract = json.dumps(contract)
        result = fc_installation_check(self.doc)
        self.assertFalse(result["native_flight_controller_contract_matches"])
        self.assertFalse(result["passed"])
        self.assertLess(abs(board.Shape.cut(original).Volume), 1e-6)
        self.assertLess(abs(original.cut(board.Shape).Volume), 1e-6)

    def test_missing_or_malformed_controller_contract_is_rejected(self):
        from gondola.validation.equipment import fc_installation_check

        board = self.doc.ModuleFCEnvelope
        for value in ("{", "null", "[]"):
            with self.subTest(value=value):
                board.FlightControllerContract = value
                self.assertFalse(fc_installation_check(self.doc)["passed"])
        board.removeProperty("FlightControllerContract")
        self.assertFalse(fc_installation_check(self.doc)["passed"])

    def test_controller_firmware_or_input_evidence_cannot_silently_change(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.validation.equipment import fc_installation_check

        for mutation in ("firmware", "input_claim", "compatibility"):
            with self.subTest(mutation=mutation):
                contract = json.loads(
                    json.dumps(interfaces.flight_controller_contract())
                )
                electrical = contract["electrical"]
                if mutation == "firmware":
                    electrical["esc_firmware"] = "Bluejay"
                elif mutation == "input_claim":
                    electrical["input_claims"]["manual_text"]["cells"] = [2, 6]
                else:
                    electrical["compatibility_status"] = "verified"
                self.doc.ModuleFCEnvelope.FlightControllerContract = json.dumps(
                    contract
                )
                result = fc_installation_check(self.doc)
                self.assertFalse(result["native_flight_controller_contract_matches"])
                self.assertFalse(result["passed"])

    def test_symmetric_board_solid_cannot_hide_reversed_installation(self):
        from gondola.cad import world_shape
        from gondola.print_export import geometry_comparison
        from gondola.validation.equipment import fc_installation_check

        board = self.doc.ModuleFCEnvelope
        original = world_shape(board)
        board.Placement.Rotation = App.Rotation(App.Vector(0, 0, 1), -45)
        self.doc.recompute()
        self.assertLess(
            geometry_comparison(world_shape(board), original)["difference_mm3"],
            1e-6,
        )
        result = fc_installation_check(self.doc)
        self.assertFalse(result["native_board_placement_matches"])
        self.assertFalse(result["passed"])

    def test_wrong_parent_turn_or_native_orientation_marker_is_rejected(self):
        from gondola.validation.equipment import fc_installation_check

        self.doc.ModuleFCEnvelope.InstallationYawInCarrier = 0
        self.assertFalse(fc_installation_check(self.doc)["passed"])
        self.doc.ModuleFCEnvelope.InstallationYawInCarrier = 180
        self.doc.ElectronicsEquipmentModule.Placement.Rotation = App.Rotation()
        self.assertFalse(fc_installation_check(self.doc)["passed"])


@unittest.skipIf(App is None, "Requires FreeCAD")
class StockAdapterInstallationTests(unittest.TestCase):
    def setUp(self):
        self.doc = build_fixture("BoughtCarbonInstallation")
        self.addCleanup(App.closeDocument, self.doc.Name)

    def test_all_four_bought_parts_and_clamps_keep_contact_unqualified(self):
        from gondola.validation.equipment import stock_adapter_check

        report = stock_adapter_check(self.doc)
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["purchased_parts"]), 28)
        self.assertEqual(len(report["nominal_purchased_bores"]), 48)
        self.assertFalse(report["exact_carbon_contact_qualified"])
        self.assertEqual(len(self.doc.DesignRegistry.PrintedParts), 0)
        self.assertEqual(len(self.doc.DesignRegistry.EquipmentMounts), 4)

    def test_shifted_clamp_or_missing_bought_registry_fails(self):
        from gondola.validation.equipment import stock_adapter_check

        obj = self.doc.StockRadioAdapterRailClampPositiveYNut
        old = App.Placement(obj.Placement)
        try:
            obj.Placement.Base.z += 0.3
            self.assertFalse(stock_adapter_check(self.doc)["passed"])
        finally:
            obj.Placement = old
        self.doc.DesignRegistry.HardwareParts = [
            o
            for o in self.doc.DesignRegistry.HardwareParts
            if o != self.doc.StockRadioAdapter
        ]
        self.assertFalse(stock_adapter_check(self.doc)["passed"])

    def test_wrong_mass_or_false_physical_fit_claim_fails(self):
        from gondola.validation.equipment import stock_adapter_check

        for name in (
            "StockFCAdapter",
            "StockBatteryAdapter",
            "StockNavigationAdapter",
            "StockRadioAdapter",
        ):
            obj = self.doc.getObject(name)
            for field, value in (
                ("ReferenceMassGrams", 0.5),
                ("PhysicalFitVerified", True),
                ("ExactContourModeled", True),
            ):
                old = getattr(obj, field)
                try:
                    setattr(obj, field, value)
                    self.assertFalse(stock_adapter_check(self.doc)["passed"])
                finally:
                    setattr(obj, field, old)

    def test_portal_changes_only_fc_x_nuts_without_duplicating_objects(self):
        from gondola.contracts.stack_adapter import COMMON_HOLE_CENTRES
        from gondola.parts import stock_adapter

        n = len(self.doc.Objects)
        stock_adapter.set_fc_portal(self.doc, True)
        for i, (x, y) in enumerate(COMMON_HOLE_CENTRES):
            self.assertAlmostEqual(
                self.doc.getObject(
                    stock_adapter.NUT_OBJECT_NAMES[i]
                ).Shape.BoundBox.ZMin,
                10 if abs(x) > 1 else 8,
            )
        stock_adapter.set_fc_portal(self.doc, False)
        self.assertEqual(len(self.doc.Objects), n)
        self.assertTrue(
            all(
                abs(self.doc.getObject(name).Shape.BoundBox.ZMin - 8) < 1e-7
                for name in stock_adapter.NUT_OBJECT_NAMES
            )
        )

    def test_service_does_not_exclude_other_installed_modules(self):
        from gondola.cad import world_shape
        from gondola.validation.equipment import device_service_check

        body = self.doc.ModuleFCEnvelope
        blocker = self.doc.addObject("Part::Feature", "OffCarrierServiceBlocker")
        self.doc.AccessoryEquipmentModule.addObject(blocker)
        target = world_shape(body).BoundBox.Center + App.Vector(0, 0, 9)
        blocker.Shape = Part.makeBox(2, 2, 2, target - App.Vector(1, 1, 1))
        # Express the deliberately foreign obstacle back in its own parent frame.
        blocker.Placement = (
            self.doc.AccessoryEquipmentModule.getGlobalPlacement()
            .inverse()
            .multiply(blocker.Placement)
        )
        objects = [body, *self.doc.DesignRegistry.HardwareParts, blocker]
        result = device_service_check(
            self.doc, body.Name, objects, {o.Name: world_shape(o) for o in objects}
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["bench_access_required"])
        self.assertEqual(result["off_carrier_parts_excluded_for_bench_service"], [])
        self.assertIn(blocker.Name, result["collisions"])


if __name__ == "__main__":
    unittest.main()
