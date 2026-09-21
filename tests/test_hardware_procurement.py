"""Preserve purchase specifications and native hardware annotations."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gondola.contracts.design import PURCHASED_HARDWARE_QUANTITIES
from gondola.contracts.hardware import PROCUREMENT_SPECS, procurement_spec

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class NativeHardwareProcurementTests(unittest.TestCase):
    def test_incomplete_known_spec_is_not_silently_treated_as_unknown(self):
        from gondola.parts import purchased_hardware

        code = "M2X8_SOCKET_CAP"
        incomplete = dict(PROCUREMENT_SPECS[code])
        del incomplete["search_query"]
        with patch.dict(PROCUREMENT_SPECS, {code: incomplete}):
            with self.assertRaises(KeyError):
                purchased_hardware.add_procurement_properties(
                    SimpleNamespace(HardwareSKU=code)
                )

    def test_complete_factory_order_codes_reach_native_metadata(self):
        from gondola.parts import purchased_hardware

        doc = App.newDocument("FactoryFlatPurchaseTest")
        self.addCleanup(App.closeDocument, doc.Name)
        for index, (code, detail) in enumerate(
            (
                ("PSFU3-26-FC5-A18", "Factory FC5-A18 alteration"),
                ("PSFU3-24-FC5-A3", "Factory FC5-A3 alteration"),
                ("PSFU3-14", "No flat is included"),
            )
        ):
            obj = purchased_hardware.add_hardware(
                doc,
                None,
                f"Shaft{index}",
                code,
                Part.makeCylinder(1.5, 14),
                code,
                "Metadata-only regression envelope",
                material="SUJ2-equivalent hard-chrome steel",
                thread_diameter=None,
            )
            self.assertIn(code, obj.PurchaseRequirements)
            self.assertIn(detail, obj.PurchaseRequirements)


class HardwareSpecificationTests(unittest.TestCase):
    def test_only_unknown_skus_can_be_explicitly_allowed(self):
        with self.assertRaises(KeyError):
            procurement_spec("UNREGISTERED_PART")
        self.assertIsNone(procurement_spec("UNREGISTERED_PART", allow_unknown=True))
        with self.assertRaises(ValueError):
            procurement_spec("PSFU3-14-FC5-A3", allow_unknown=True)

    def test_every_selected_hardware_sku_has_a_portable_purchase_specification(self):
        for code in PURCHASED_HARDWARE_QUANTITIES:
            with self.subTest(code=code):
                spec = procurement_spec(code)
                for field in ("search_query", "requirements", "search_url", "status"):
                    self.assertIsInstance(spec[field], str)
                    self.assertTrue(spec[field])

    def test_impossible_factory_flat_orders_are_rejected(self):
        for code in (
            "PSFU3-9",
            "PSFU3-401",
            "PSFU3-14-FC5-A3",
            "PSFU3-26-FC0-A18",
            "PSFU3-26-FC16-A3",
            "PSFU3-26-FC5-A1",
            "PSFU3-26-FC5-A22",
        ):
            with self.subTest(code=code), self.assertRaises(ValueError):
                procurement_spec(code)


if __name__ == "__main__":
    unittest.main()
