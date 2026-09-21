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
class WiringClearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.cad import create_group, set_property
        from gondola.parts import (
            equipment_envelopes,
            equipment_mounts,
            wiring_clearance,
        )
        from gondola.validation import equipment

        cls.wiring = wiring_clearance
        cls.audit = equipment
        cls.expected = wiring_clearance.reserve_shapes()
        cls.doc = App.newDocument("WiringClearanceRegression")
        battery = create_group(cls.doc, "BatteryModule", "Battery")
        battery.Placement.Base.x = -180
        electronics = create_group(cls.doc, "ElectronicsEquipmentModule", "Electronics")
        carrier = equipment_mounts.build_mount(cls.doc, electronics, "electronics")
        refs, reserves = equipment_envelopes.build_equipment(
            cls.doc, battery, electronics
        )
        registry = cls.doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        for name, value in {
            "PrintedParts": [carrier],
            "HardwareParts": [],
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
        self.assertEqual(set(contracts), set(self.expected))
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
            0.4, 2, 2, App.Vector(bounds.Center.x - 0.2, bounds.Center.y - 1, 15)
        )
        for x in (bounds.XMin + 0.5, bounds.XMax - 0.5):
            endpoint = Part.makeSphere(0.4, App.Vector(x, bounds.Center.y, 16))
            self.assertLess(endpoint.common(blocker).Volume, 1e-6)
        result = self.audit.connector_reserve_geometry_check(
            lane, lane, {"UnmodeledPlugAcrossMiddle": blocker}
        )
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["continuous_reserved_space_collisions"]), 1)

    def test_disconnected_fc_exit_is_rejected(self):
        expected = self.expected["FCWiringClearanceReserve"]
        severed = expected.cut(Part.makeBox(1, 30, 4, App.Vector(-26, -1, 14.2)))
        self.assertGreater(len(severed.Solids), 1)
        result = self.audit.connector_reserve_geometry_check(severed, expected, {})
        self.assertFalse(result["one_connected_solid"])
        self.assertFalse(result["passed"])

    def test_optical_gap_requires_margin_beyond_zero_interference(self):
        fc = self.expected["FCWiringClearanceReserve"]
        optical = self.doc.MTF02POpticalClearanceReserve.Shape.copy()
        optical.translate(App.Vector(0, 1, 0))
        self.assertLess(fc.common(optical).Volume, 1e-6)
        self.assertLess(fc.distToShape(optical)[0], 1)
        others = {
            "MTF02POpticalClearanceReserve": optical,
            "ModuleLR900Envelope": self.doc.ModuleLR900Envelope.Shape,
            "ModulePASEnvelope": self.doc.ModulePASEnvelope.Shape,
            "XT30ServiceReserve": self.expected["XT30ServiceReserve"],
        }
        results = self.audit.connector_buffer_checks(fc, others)
        self.assertFalse(results[0]["passed"])
        self.assertTrue(all(row["passed"] for row in results[1:]))

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
