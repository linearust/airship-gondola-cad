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
    def test_two_flat_output_rod_keeps_round_bearing_journals(self):
        row = procurement_spec("SS304_CUT3_L42_FLAT5_GRIP11_A0")
        self.assertIn("42 mm length", row["requirements"])
        self.assertIn("second0.5mm-deep flat over the final11mm", row["requirements"])
        self.assertIn("intervening bearing-journal interval round", row["requirements"])
        for bad in ("SS304_CUT3_L16_FLAT5_GRIP11_A0", "SS304_CUT3_L42_FLAT5_GRIP0_A0"):
            with self.subTest(sku=bad), self.assertRaises(ValueError):
                procurement_spec(bad)

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
                ("SS304_CUT3_L35_FLAT16_A0", "length 16 mm, starting 0 mm"),
                ("SS304_CUT3_L34_FLAT5_A0", "length 5 mm, starting 0 mm"),
                ("SS304_CUT3_L14", "Leave the rod round"),
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
                material="304 stainless steel (seller claim)",
                thread_diameter=None,
            )
            self.assertIn(code, obj.PurchaseRequirements)
            self.assertIn(detail, obj.PurchaseRequirements)


class HardwareSpecificationTests(unittest.TestCase):
    def test_selected_m3_rail_joints_share_one_spec_and_preserve_remaining_m2_inventory(
        self,
    ):
        from gondola.contracts.design import HARDWARE_MATERIALS
        from gondola.procurement import hardware_material_code

        expected = {
            "M3X10_BUTTON_HEAD": 5,
            "M3_HEX_NUT": 5,
            "M2X8_BUTTON_HEAD": 2,
            "M2X10_BUTTON_HEAD": 6,
            "M2X12_BUTTON_HEAD": 2,
            "M2X6_BUTTON_HEAD": 2,
            "M2_HEX_NUT": 12,
            "BEARING_3X6X2_5": 6,
            "SS304_CUT3_L35_FLAT16_A0": 2,
        }
        self.assertNotIn("M3X20_BUTTON_HEAD", PURCHASED_HARDWARE_QUANTITIES)
        for code, quantity in expected.items():
            self.assertEqual(PURCHASED_HARDWARE_QUANTITIES[code], quantity)
        for code in ("M3X10_BUTTON_HEAD", "M3_HEX_NUT"):
            spec = procurement_spec(code)
            self.assertEqual(spec["candidate_url"], "")
            self.assertIn("owned", spec["evidence_notes"])
            self.assertIn("design material selection", spec["requirements"])
            self.assertNotIn("10.9", spec["requirements"])
            self.assertEqual(hardware_material_code(HARDWARE_MATERIALS[code]), "A2")
        self.assertIn(
            "head diameter at most 6 mm",
            procurement_spec("M3X10_BUTTON_HEAD")["requirements"],
        )
        self.assertIn(
            "6.5 mm effective grip",
            procurement_spec("M3X10_BUTTON_HEAD")["requirements"],
        )
        self.assertIn(
            "1.1 mm tip projection",
            procurement_spec("M3X10_BUTTON_HEAD")["requirements"],
        )
        self.assertIn(
            "5.9 mm across-flats hex pocket",
            procurement_spec("M3_HEX_NUT")["requirements"],
        )

    def test_current_plastic_horn_selection_preserves_source_and_unknown_mass(self):
        from gondola.config import REPO_ROOT
        from gondola.contracts.design import HARDWARE_MATERIALS
        from gondola.contracts.equipment_interfaces import PROPULSION_EVIDENCE
        from gondola.mass_budget import DENSITIES_G_CM3
        from gondola.procurement import hardware_material_code
        from gondola.provenance import file_sha256

        sku = "KST_X06_STOCK_HALF_ARM_1"
        for code, quantity in (
            (sku, 2),
            ("M1X6_HEX_HEAD", 4),
            ("M1_HEX_NUT", 4),
        ):
            self.assertEqual(PURCHASED_HARDWARE_QUANTITIES[code], quantity)
        evidence = PROPULSION_EVIDENCE[sku]
        self.assertEqual(evidence["selected_attachment_radii_mm"], [6.8, 13.2])
        self.assertEqual(evidence["threaded_hole_count"], 0)
        self.assertFalse(evidence["horn_requires_drilling"])
        self.assertEqual(evidence["optional_attachment_radii_mm"], [10.0])
        self.assertEqual(
            file_sha256(REPO_ROOT / evidence["sources"][0]),
            evidence["geometry_sha256"],
        )
        self.assertEqual(procurement_spec(sku)["candidate_url"], evidence["sources"][0])
        material = hardware_material_code(HARDWARE_MATERIALS[sku])
        self.assertIsNone(DENSITIES_G_CM3[material])
        for obsolete in (
            "ALI_PTK_15T_4MM_HORN",
            "METAL_15T_4MM_HORN_6_98",
            "KST_0415_13_HORN",
            "M1_6X5_PAN_HEAD_KIT",
            "M1_4X6_PAN_HEAD_KIT",
        ):
            self.assertNotIn(obsolete, PURCHASED_HARDWARE_QUANTITIES)
            self.assertNotIn(obsolete, HARDWARE_MATERIALS)
            with self.assertRaises(KeyError):
                procurement_spec(obsolete)

    def test_selected_shaft_evidence_matches_preparation_and_materials(self):
        from gondola.contracts.design import HARDWARE_MATERIALS
        from gondola.contracts.equipment_interfaces import PROPULSION_EVIDENCE

        evidence = PROPULSION_EVIDENCE["selected_shaft_stock"]
        self.assertEqual(evidence["seller_material_claim"], "304 stainless steel")
        self.assertEqual(evidence["stock_lengths_mm"], [100.0, 200.0])
        self.assertEqual(evidence["nominal_diameter_mm"], 3.0)
        for sku in PURCHASED_HARDWARE_QUANTITIES:
            if not sku.startswith("SS304_CUT3_"):
                continue
            spec = procurement_spec(sku)
            self.assertEqual(spec["candidate_url"], evidence["sources"][0])
            self.assertIn(evidence["seller_material_claim"], HARDWARE_MATERIALS[sku])
            self.assertIn("304 stainless", spec["requirements"])
            self.assertIn("100/200 mm", spec["requirements"])

    def test_only_unknown_skus_can_be_explicitly_allowed(self):
        with self.assertRaises(KeyError):
            procurement_spec("UNREGISTERED_PART")
        self.assertIsNone(procurement_spec("UNREGISTERED_PART", allow_unknown=True))
        with self.assertRaises(ValueError):
            procurement_spec("SS304_CUT3_L14_FLAT15_A0", allow_unknown=True)

    def test_every_selected_hardware_sku_has_a_portable_purchase_specification(self):
        for code in PURCHASED_HARDWARE_QUANTITIES:
            with self.subTest(code=code):
                spec = procurement_spec(code)
                for field in ("search_query", "requirements", "search_url", "status"):
                    self.assertIsInstance(spec[field], str)
                    self.assertTrue(spec[field])

    def test_impossible_cut_lengths_and_flat_preparations_are_rejected(self):
        for code in (
            "SS304_CUT3_L0",
            "SS304_CUT3_L201",
            "SS304_CUT3_L14_FLAT15_A0",
            "SS304_CUT3_L24_FLAT0_A0",
            "SS304_CUT3_L24_FLAT5_A20",
            "SS304_CUT3_L24_BROKEN",
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

    def test_input_flat_preserves_distal_journal_and_old_stub_is_not_selected(
        self,
    ):
        stub = procurement_spec("SS304_CUT3_L35_FLAT16_A0")
        self.assertIn("nominal depth 0.5 mm", stub["requirements"])
        self.assertIn("to 35 mm length", stub["requirements"])
        self.assertIn("length 16 mm, starting 0 mm", stub["requirements"])
        self.assertIn(
            "Keep every input and output bearing journal round", stub["requirements"]
        )
        self.assertNotIn("SS304_CUT3_L20_FLAT20_A0", PURCHASED_HARDWARE_QUANTITIES)
        with self.assertRaises(KeyError):
            procurement_spec("PSFU3-24-FC5-A3")

    def test_six_bearing_requirement_preserves_four_bearing_purchase_history(self):
        from gondola.contracts.equipment_interfaces import PROPULSION_EVIDENCE

        self.assertEqual(PURCHASED_HARDWARE_QUANTITIES["BEARING_3X6X2_5"], 6)
        requirement = procurement_spec("BEARING_3X6X2_5")["requirements"]
        self.assertIn("four previously confirmed purchased", requirement)
        self.assertIn("two additional matching bearings or spares", requirement)
        self.assertIn("does not record a new purchase", requirement)
        self.assertIn(
            "previously confirmed four purchased",
            PROPULSION_EVIDENCE["selected_bearing"]["scope"],
        )


if __name__ == "__main__":
    unittest.main()
