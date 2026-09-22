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

        code = "M2X8_BUTTON_HEAD"
        incomplete = dict(PROCUREMENT_SPECS[code])
        del incomplete["search_query"]
        with patch.dict(PROCUREMENT_SPECS, {code: incomplete}):
            with self.assertRaises(KeyError):
                purchased_hardware.add_procurement_properties(
                    SimpleNamespace(HardwareSKU=code)
                )

    def test_cut_rod_preparation_keys_reach_native_metadata(self):
        from gondola.parts import purchased_hardware

        doc = App.newDocument("CutRodPurchaseTest")
        self.addCleanup(App.closeDocument, doc.Name)
        for index, (code, detail) in enumerate(
            (
                ("AL6061_CUT3_L16_FLAT16_A0", "length 16 mm, starting 0 mm"),
                ("AL6061_CUT3_L24_FLAT5_A0", "length 5 mm, starting 0 mm"),
                ("AL6061_CUT3_L14", "Leave the rod round"),
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
                material="Aluminium; 6061 seller claim",
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
            procurement_spec("AL6061_CUT3_L14_FLAT15_A0", allow_unknown=True)

    def test_every_selected_hardware_sku_has_a_portable_purchase_specification(self):
        for code in PURCHASED_HARDWARE_QUANTITIES:
            with self.subTest(code=code):
                spec = procurement_spec(code)
                for field in ("search_query", "requirements", "search_url", "status"):
                    self.assertIsInstance(spec[field], str)
                    self.assertTrue(spec[field])

    def test_impossible_cut_lengths_and_flat_preparations_are_rejected(self):
        for code in (
            "AL6061_CUT3_L0",
            "AL6061_CUT3_L331",
            "AL6061_CUT3_L14_FLAT15_A0",
            "AL6061_CUT3_L24_FLAT0_A0",
            "AL6061_CUT3_L24_FLAT5_A20",
            "AL6061_CUT3_L24_BROKEN",
        ):
            with self.subTest(code=code), self.assertRaises(ValueError):
                procurement_spec(code)

    def test_selected_material_and_supplier_uncertainties_are_preserved(self):
        bearing = procurement_spec("BEARING_3X6X2_5")
        self.assertIn("not NSK/ISC identity", bearing["evidence_notes"])
        for code in ("ALI_KAILASH_M05_48T_B3", "ALI_KAILASH_M05_16T_B3"):
            gear = procurement_spec(code)
            self.assertIn("Do not assume an included screw", gear["requirements"])
            self.assertNotIn("white POM", gear["requirements"])
        self.assertIn(
            "head diameter 4.5 mm", procurement_spec("M2X8_BUTTON_HEAD")["requirements"]
        )
        self.assertIn(
            "design allowances", procurement_spec("M2X8_BUTTON_HEAD")["evidence_notes"]
        )

    def test_full_length_input_flat_is_valid_and_old_finished_shaft_is_not_selected(
        self,
    ):
        stub = procurement_spec("AL6061_CUT3_L16_FLAT16_A0")
        self.assertIn("nominal depth 0.5 mm", stub["requirements"])
        self.assertIn("no bearing journal", stub["requirements"])
        with self.assertRaises(KeyError):
            procurement_spec("PSFU3-24-FC5-A3")


if __name__ == "__main__":
    unittest.main()
