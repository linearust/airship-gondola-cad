"""Prevent factory-flat shaft selections from degrading to plain-rod orders."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class ShaftProcurementTests(unittest.TestCase):
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

    def test_impossible_factory_flat_orders_are_rejected(self):
        from gondola.parts import purchased_hardware

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
                purchased_hardware.procurement_spec(code)


if __name__ == "__main__":
    unittest.main()
