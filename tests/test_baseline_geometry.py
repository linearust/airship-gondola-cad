"""Frozen-design regression gates; execute inside the FreeCAD Python runtime."""

import json
import unittest
from collections import Counter

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(
    App is None, "Requires FreeCAD; exercised by the CAD validation workflow"
)
class FrozenBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.config import BASELINE_FILE, BASELINE_SHA256
        from gondola.provenance import file_sha256

        if file_sha256(BASELINE_FILE) != BASELINE_SHA256:
            raise AssertionError("Frozen approved fixture hash changed")
        cls.reference = App.openDocument(str(BASELINE_FILE), hidden=True)
        cls.addClassCleanup(App.closeDocument, cls.reference.Name)

    def setUp(self):
        self.scratch = App.newDocument("BaselineRegressionTest")
        self.addCleanup(App.closeDocument, self.scratch.Name)

    def feature(self, name, shape):
        obj = self.scratch.addObject("Part::Feature", name)
        obj.Shape = shape.copy()
        return obj

    def test_fixture_inventory_and_unresolved_scope_match_approved_design(self):
        from gondola.design_contract import EXPECTED_INVENTORY
        from gondola.validation.baseline import unresolved_scope

        registry = self.reference.DesignRegistry
        self.assertEqual(
            len(registry.PrintedParts), EXPECTED_INVENTORY["installed_prints"]
        )
        self.assertEqual(len(registry.FitCoupons), EXPECTED_INVENTORY["fit_coupons"])
        for obj in list(registry.PrintedParts) + list(registry.FitCoupons):
            self.assertIn("PrintPart", obj.PropertiesList, obj.Name)
            self.assertTrue(obj.PrintPart, obj.Name)
        self.assertEqual(
            len(registry.HardwareParts), EXPECTED_INVENTORY["purchased_hardware"]
        )
        self.assertEqual(
            {obj.Name for obj in registry.EquipmentMounts},
            {"BatteryMount", "ElectronicsMount"},
        )
        self.assertEqual(
            len(registry.EquipmentMounts), EXPECTED_INVENTORY["equipment_mounts"]
        )
        self.assertTrue(
            {"StandardBoards", "StackPosts", "StackLocks", "StackWashers"}.isdisjoint(
                registry.PropertiesList
            )
        )
        hardware_skus = Counter(obj.HardwareSKU for obj in registry.HardwareParts)
        self.assertEqual(
            len(hardware_skus), EXPECTED_INVENTORY["purchased_hardware_types"]
        )
        self.assertEqual(hardware_skus["M2_HEX_NUT"], 4)
        self.assertEqual(hardware_skus["M2_SQUARE_NUT_DIN562"], 3)
        self.assertEqual(hardware_skus["M2_WASHER_2.2_5_0.3"], 8)
        self.assertEqual(hardware_skus["M3_WASHER_3.2_9_0.8"], 4)
        result = unresolved_scope(self.reference)
        self.assertTrue(result["passed"], result)

    def test_fixture_native_controls_remain_independent_and_bounded(self):
        from gondola.validation.baseline import control_behavior

        result = control_behavior(self.reference)
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["cases"]), 19)

    def test_rail_has_no_comparison_exception(self):
        from gondola.validation.baseline import compare_shape_objects
        from gondola.validation.geometry import local_shape

        shape = local_shape(self.reference.ContinuousRail)
        expected = self.feature("ExpectedRail", shape)
        actual = self.feature("ContinuousRail", shape)
        self.assertTrue(compare_shape_objects(actual, expected)["passed"])
        actual.Shape = shape.cut(Part.makeBox(1, 1, 1, App.Vector(-0.5, -0.5, 6)))
        result = compare_shape_objects(actual, expected)
        self.assertFalse(result["passed"])
        self.assertGreater(result["local_shape"]["difference_mm3"], 0.9)

    def test_symmetric_shape_cannot_hide_a_changed_placement(self):
        from gondola.validation.baseline import compare_shape_objects

        symmetric = Part.makeBox(2, 2, 2, App.Vector(-1, -1, -1))
        expected = self.feature("Expected", symmetric)
        actual = self.feature("Actual", symmetric)
        actual.Placement.Rotation = App.Rotation(App.Vector(0, 0, 1), 180)
        result = compare_shape_objects(actual, expected)
        self.assertLess(result["local_shape"]["difference_mm3"], 1e-5)
        self.assertLess(result["world_shape"]["difference_mm3"], 1e-5)
        self.assertFalse(result["world_placement_unchanged"])
        self.assertFalse(result["passed"])

    def test_unchanged_solid_cannot_hide_a_wrong_purchase_or_print_role(self):
        from gondola.validation.baseline import compare_shape_objects

        shape = Part.makeBox(2, 2, 2)
        expected = self.feature("ExpectedHardware", shape)
        actual = self.feature("ActualHardware", shape)
        for obj in (expected, actual):
            obj.addProperty("App::PropertyString", "HardwareSKU")
            obj.HardwareSKU = "M2X14_SOCKET_CAP"
            obj.addProperty("App::PropertyBool", "PrintPart")
            obj.PrintPart = False
            obj.addProperty("App::PropertyString", "PurchaseRequirements")
            obj.PurchaseRequirements = "A2 stainless steel, M2x14, DIN912"
        self.assertTrue(compare_shape_objects(actual, expected)["passed"])
        actual.HardwareSKU = "M2_HEX_NUT"
        self.assertFalse(compare_shape_objects(actual, expected)["passed"])
        actual.HardwareSKU = expected.HardwareSKU
        actual.PrintPart = True
        self.assertFalse(compare_shape_objects(actual, expected)["passed"])
        actual.PrintPart = False
        actual.PurchaseRequirements = "M2x10 substituted without geometric changes"
        self.assertFalse(compare_shape_objects(actual, expected)["passed"])

    def test_geometry_cannot_promote_an_unverified_assembly_to_production(self):
        from gondola.validation.baseline import unresolved_scope

        registry = self.reference.DesignRegistry
        original = registry.ReleaseStatus
        try:
            changed = json.loads(original)
            changed["production_released"] = True
            registry.ReleaseStatus = json.dumps(changed)
            result = unresolved_scope(self.reference)
            self.assertFalse(result["native_release_status_matches_contract"])
            self.assertFalse(result["passed"])
            registry.ReleaseStatus = "not valid JSON"
            self.assertFalse(unresolved_scope(self.reference)["passed"])
        finally:
            registry.ReleaseStatus = original


if __name__ == "__main__":
    unittest.main()
