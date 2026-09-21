"""Native geometry regressions for continuous, explicitly provisional access."""

import json
import unittest
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None


@unittest.skipIf(App is None, "requires FreeCAD's Python runtime")
class WiringReserveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.cad import create_group, set_property
        from gondola.parts import (
            equipment_envelopes,
            equipment_mounts,
            optical_mount,
            optical_sensor,
            stack_interface,
            wiring_reserves,
        )
        from gondola.validation import wiring as wiring_validation

        cls.wiring = wiring_reserves
        cls.audit = wiring_validation
        cls.expected = wiring_reserves.reserve_shapes()
        cls.expected["MTF02PConnectorReserve"] = (
            optical_sensor.connector_reserve_shape()
        )
        cls.doc = App.newDocument("WiringClearanceRegression")
        battery = create_group(cls.doc, "BatteryEquipmentModule", "Battery")
        battery.Placement.Base.x = -180
        electronics = create_group(cls.doc, "ElectronicsEquipmentModule", "Electronics")
        carrier = equipment_mounts.build_mount(cls.doc, electronics, "electronics")
        refs, reserves = equipment_envelopes.build_equipment(
            cls.doc, battery, electronics
        )
        optical = optical_mount.build_optical_mount(cls.doc, battery)
        stack_interface.attach_to_host(optical["group"], battery)
        optical["hardware"] += stack_interface.build_stack_hardware(
            cls.doc, optical["group"]
        )
        sensor_refs, sensor_reserves = optical_sensor.build_sensor(
            cls.doc, optical["pitch_stage"]
        )
        refs += sensor_refs
        reserves += sensor_reserves
        registry = cls.doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        for name, value in {
            "PrintedParts": [carrier] + optical["printed"],
            "HardwareParts": optical["hardware"],
            "ReferenceParts": refs,
            "ClearanceVolumes": reserves,
            "TapeReferences": [],
        }.items():
            set_property(registry, name, value, "App::PropertyLinkListGlobal")
        cls.doc.recompute()
        cls.reserve_names = tuple(cls.expected) + (
            "MTF02POpticalClearanceReserve",
            "CapacitorServiceReserve",
        )

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def saved_reserve_results(self):
        # This fixture isolates electronics; full assembly validation also tests
        # the rotor sweeps and the propulsion lead planning reservations.
        with patch.object(self.audit, "RESERVES", self.reserve_names):
            return self.audit.reserve_checks(self.doc)

    def test_nominal_reservations_are_connected_and_clear(self):
        checks, pairs = self.saved_reserve_results()
        self.assertEqual(len(checks), 8)
        self.assertTrue(all(row["passed"] for row in checks), checks)
        self.assertTrue(all(row["passed"] for row in pairs), pairs)
        contracts = json.loads(json.dumps(self.wiring.reserve_contracts()))
        self.assertEqual(
            set(contracts), set(self.expected) - {"MTF02PConnectorReserve"}
        )
        for contract in contracts.values():
            self.assertFalse(contract["installed_connector_fit_verified"])
            self.assertFalse(contract["wire_bend_radius_qualified"])
            self.assertFalse(contract["complete_connected_harness_modeled"])

    def test_missing_and_shortened_lane_are_rejected(self):
        expected = self.expected["MTF02PConnectorReserve"]
        self.assertFalse(
            self.audit.connector_reserve_geometry_check(None, expected, {})["passed"]
        )
        bounds = expected.BoundBox
        shortened = expected.common(
            Part.makeBox(
                bounds.XLength / 2,
                bounds.YLength,
                bounds.ZLength,
                App.Vector(bounds.XMin, bounds.YMin, bounds.ZMin),
            )
        )
        self.assertTrue(shortened.isValid())
        result = self.audit.connector_reserve_geometry_check(shortened, expected, {})
        self.assertFalse(result["passed"])
        self.assertGreater(result["source_comparison"]["difference_mm3"], 100)

    def test_middle_obstruction_fails_even_when_both_endpoints_are_clear(self):
        lane = self.expected["MTF02PConnectorReserve"]
        bounds = lane.BoundBox
        blocker = Part.makeBox(
            0.4,
            2,
            2,
            App.Vector(bounds.Center.x - 0.2, bounds.Center.y - 1, bounds.Center.z - 1),
        )
        for x in (bounds.XMin + 0.5, bounds.XMax - 0.5):
            endpoint = Part.makeSphere(
                0.4, App.Vector(x, bounds.Center.y, bounds.Center.z)
            )
            self.assertLess(endpoint.common(blocker).Volume, 1e-6)
        result = self.audit.connector_reserve_geometry_check(
            lane, lane, {"UnmodeledPlugAcrossMiddle": blocker}
        )
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["continuous_reserved_space_collisions"]), 1)

    def test_disconnected_fc_reservation_is_rejected(self):
        expected = self.expected["FCWiringClearanceReserve"]
        bounds = expected.BoundBox
        severed = expected.cut(
            Part.makeBox(
                1,
                bounds.YLength + 2,
                bounds.ZLength + 2,
                App.Vector(-0.5, bounds.YMin - 1, bounds.ZMin - 1),
            )
        )
        self.assertGreater(len(severed.Solids), 1)
        result = self.audit.connector_reserve_geometry_check(severed, expected, {})
        self.assertFalse(result["one_connected_solid"])
        self.assertFalse(result["passed"])

    def test_named_gap_rejects_clear_but_cramped_geometry(self):
        source = Part.makeBox(2, 2, 2)
        requirements = {"FC": {"Optical": 1.5}}
        for gap, expected in ((0.5, False), (1.5, True), (2.0, True)):
            with self.subTest(gap=gap):
                other = Part.makeBox(2, 2, 2, App.Vector(2 + gap, 0, 0))
                self.assertLess(source.common(other).Volume, 1e-6)
                result = self.audit.named_gap_checks(
                    {"FC": source, "Optical": other}, requirements
                )[0]
                self.assertAlmostEqual(result["measured_gap_mm"], gap)
                self.assertEqual(result["passed"], expected)

    def test_missing_non_solid_or_nested_geometry_cannot_pass_clearance(self):
        source = Part.makeBox(4, 4, 4)
        validation_cache = {}
        invalid = (None, Part.Shape(), Part.makeLine(App.Vector(), App.Vector(1, 0, 0)))
        for other in invalid:
            with self.subTest(other=other):
                result = self.audit.named_gap_checks(
                    {"FC": source, "Cable": other},
                    {"FC": {"Cable": 1.5}},
                    validation_cache=validation_cache,
                )[0]
                self.assertFalse(result["passed"])
                self.assertIn("error", result)
        contained = Part.makeSphere(0.25, App.Vector(2, 2, 2))
        result = self.audit.measure_clearances(
            source, {"ContainedCable": contained}, validation_cache=validation_cache
        )[0]
        self.assertFalse(result["passed"])
        self.assertGreater(result["intersection_mm3"], 0.06)
        clear = Part.makeBox(1, 1, 1, App.Vector(6, 0, 0))
        self.assertTrue(
            self.audit.named_gap_checks(
                {"FC": source, "Cable": clear},
                {"FC": {"Cable": 1.5}},
                validation_cache=validation_cache,
            )[0]["passed"]
        )

    def test_required_reserve_removed_from_registry_is_rejected(self):
        registry = self.doc.DesignRegistry
        original = list(registry.ClearanceVolumes)
        try:
            registry.ClearanceVolumes = [
                obj for obj in original if obj.Name != "CapacitorServiceReserve"
            ]
            checks, pairs = self.saved_reserve_results()
            self.assertFalse(
                next(
                    row for row in checks if row["object"] == "CapacitorServiceReserve"
                )["passed"]
            )
            self.assertTrue(
                any(
                    not row["passed"]
                    for row in pairs
                    if "CapacitorServiceReserve" in (row["a"], row["b"])
                )
            )
        finally:
            registry.ClearanceVolumes = original

    def test_native_contract_and_unverified_fit_cannot_be_promoted(self):
        obj = self.doc.MTF02PConnectorReserve
        original_contract = obj.WiringContract
        try:
            contract = json.loads(original_contract)
            contract["installed_connector_fit_verified"] = True
            obj.WiringContract = json.dumps(contract)
            obj.InstalledConnectorFitVerified = True
            rows, _ = self.saved_reserve_results()
            result = next(row for row in rows if row["object"] == obj.Name)
            self.assertFalse(result["native_wiring_contract_matches"])
            self.assertFalse(result["installed_connector_fit_remains_unverified"])
            self.assertFalse(result["passed"])
        finally:
            obj.WiringContract = original_contract
            obj.InstalledConnectorFitVerified = False

    def test_fc_reserve_contains_complete_core_and_both_continuous_turns(self):
        from gondola.parts import equipment_mounts as mounts

        fc = self.expected["FCWiringClearanceReserve"]
        self.assertLess(mounts.fc_wiring_reserve_shape().cut(fc).Volume, 1e-6)
        # Independently check endpoint and middle sections of both selected
        # turn paths; the generated whole union must remain one solid.
        for side in (-1, 1):
            turn_y = 14 if side < 0 else 4
            section = Part.makeSphere(1.4, App.Vector(side * 29, turn_y, 16.2))
            self.assertLess(section.cut(fc).Volume, 1e-6)
        self.assertEqual(len(fc.Solids), 1)


if __name__ == "__main__":
    unittest.main()
