"""Frozen-design regression gates; execute inside the FreeCAD Python runtime."""

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


if __name__ == "__main__":
    unittest.main()
