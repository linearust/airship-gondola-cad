"""Frozen-design regression gates; execute inside the FreeCAD Python runtime."""

import json
import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class ModuleControlMappingTests(unittest.TestCase):
    def setUp(self):
        from gondola.design_contract import ModuleStation

        self.stations = tuple(
            ModuleStation(name, x, name + "Clamp", "PositiveY")
            for name, x in (
                ("Battery", -90),
                ("Propulsion", 0),
                ("Electronics", 90),
                ("Optical", -144),
            )
        )
        self.modules = [
            SimpleNamespace(
                Name=station.object_name,
                Placement=App.Placement(App.Vector(station.x_mm, 0, 0), App.Rotation()),
            )
            for station in self.stations
        ]
        self.doc = SimpleNamespace(
            DesignRegistry=SimpleNamespace(Modules=list(reversed(self.modules))),
            AssemblySettings=SimpleNamespace(
                PropertiesList=[station.clamp_control for station in self.stations]
            ),
        )

    def test_fourth_control_is_bound_by_name_despite_reordered_registry(self):
        from gondola.validation import baseline

        with patch.object(baseline, "MODULE_STATIONS", self.stations):
            bindings = baseline.module_control_bindings(self.doc)
        self.assertEqual(
            [(station.object_name, module.Name) for station, module in bindings],
            [(station.object_name, station.object_name) for station in self.stations],
        )

    def test_missing_fourth_module_or_control_is_not_silently_zipped_away(self):
        from gondola.validation import baseline

        with patch.object(baseline, "MODULE_STATIONS", self.stations):
            original = self.doc.DesignRegistry.Modules
            self.doc.DesignRegistry.Modules = self.modules[:3]
            self.assertFalse(baseline.control_behavior(self.doc)["passed"])
            self.doc.DesignRegistry.Modules = original
            self.doc.AssemblySettings.PropertiesList.pop()
            self.assertFalse(baseline.control_behavior(self.doc)["passed"])

    def test_outer_modules_exit_first_independently_of_registry_order(self):
        from gondola.validation.assembly import module_removal_plan

        outer_positive = SimpleNamespace(
            Name="OuterPositive",
            Placement=App.Placement(App.Vector(144, 0, 0), App.Rotation()),
        )
        modules = self.modules + [outer_positive]
        for order in (modules, list(reversed(modules))):
            actual = module_removal_plan(order)
            self.assertEqual(
                [(module.Name, direction) for module, direction in actual],
                [
                    ("Optical", -1),
                    ("Battery", -1),
                    ("Propulsion", -1),
                    ("OuterPositive", 1),
                    ("Electronics", 1),
                ],
            )
        requested = {module.Name: 1 for module in modules}
        actual = module_removal_plan(modules, requested)
        self.assertEqual(
            [module.Name for module, _ in actual],
            ["OuterPositive", "Electronics", "Propulsion", "Battery", "Optical"],
        )
        requested.pop("Optical")
        with self.assertRaises(ValueError):
            module_removal_plan(modules, requested)

    def test_actual_manual_stages_are_bounded_and_independent(self):
        from gondola.cad import create_group, set_property
        from gondola.design_contract import MODULE_STATIONS
        from gondola.parts.optical_mount import build_optical_mount
        from gondola.validation.baseline import control_behavior

        doc = App.newDocument("ManualControlRegression")
        self.addCleanup(App.closeDocument, doc.Name)
        settings = doc.addObject("App::FeaturePython", "AssemblySettings")
        modules = []
        for station in MODULE_STATIONS:
            set_property(
                settings,
                station.clamp_control,
                ["PositiveY", "NegativeY"],
                "App::PropertyEnumeration",
            )
            module = create_group(doc, station.object_name, station.object_name)
            set_property(module, "RailPositionX", station.x_mm, "App::PropertyLength")
            module.setExpression("Placement.Base.x", "RailPositionX")
            module.setExpression(
                "Placement.Base.y",
                f"AssemblySettings.{station.clamp_control} == 0 ? 0.45mm : -0.45mm",
            )
            modules.append(module)
        pods = []
        for name in ("PortPod", "StarboardPod"):
            pod = create_group(doc, name, name)
            pod.Placement.Rotation = App.Rotation(App.Vector(0, 1, 0), 1)
            set_property(pod, "Tilt", 0, "App::PropertyAngle")
            pod.setExpression(
                "Placement.Rotation.Angle", "min(150deg; max(-150deg; Tilt))"
            )
            pods.append(pod)
        registry = doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        set_property(registry, "Modules", modules, "App::PropertyLinkListGlobal")
        set_property(registry, "TiltingPods", pods, "App::PropertyLinkListGlobal")
        build_optical_mount(doc, doc.BatteryEquipmentModule)
        doc.recompute()
        result = control_behavior(doc)
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["cases"]), 3 * len(MODULE_STATIONS) + 20)
        doc.OpticalRollStage.MaximumAngle = 30
        self.assertFalse(control_behavior(doc)["passed"])

    def test_shapeless_stack_group_metadata_is_frozen_too(self):
        from gondola.cad import create_group, set_property
        from gondola.validation.baseline import native_interface_metadata

        doc = App.newDocument("StackGroupMetadataRegression")
        self.addCleanup(App.closeDocument, doc.Name)
        group = create_group(doc, "OpticalFlowModule", "Optical head")
        set_property(group, "StackHostName", "BatteryEquipmentModule")
        set_property(group, "HoldingTorqueVerified", False, "App::PropertyBool")
        original = native_interface_metadata(doc)
        self.assertIn(group.Name, original)
        group.HoldingTorqueVerified = True
        self.assertNotEqual(original, native_interface_metadata(doc))
        group.HoldingTorqueVerified = False
        group.StackHostName = "ElectronicsEquipmentModule"
        self.assertNotEqual(original, native_interface_metadata(doc))


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
        from gondola.design_contract import (
            EXPECTED_INVENTORY,
            PURCHASED_HARDWARE_QUANTITIES,
        )
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
        self.assertEqual(
            {obj.Name for obj in getattr(registry, "OpticalMountParts", [])},
            {"OpticalMountBase", "OpticalRollBracket", "OpticalSensorTray"},
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
        self.assertEqual(hardware_skus, PURCHASED_HARDWARE_QUANTITIES)
        result = unresolved_scope(self.reference)
        self.assertTrue(result["passed"], result)

    def test_fixture_native_controls_remain_independent_and_bounded(self):
        from gondola.design_contract import MODULE_STATIONS
        from gondola.validation.baseline import control_behavior

        result = control_behavior(self.reference)
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["cases"]), 3 * len(MODULE_STATIONS) + 20)

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

    def test_optical_contract_cannot_change_under_an_identical_solid(self):
        from gondola.validation.baseline import compare_shape_objects

        shape = Part.makeBox(2, 2, 2)
        expected = self.feature("ExpectedOpticalBracket", shape)
        actual = self.feature("ActualOpticalBracket", shape)
        contract = {"angle_limit_deg": 20, "retention_physically_verified": False}
        for obj in (expected, actual):
            obj.addProperty("App::PropertyString", "OpticalMountContract")
            obj.OpticalMountContract = json.dumps(contract)
        self.assertTrue(compare_shape_objects(actual, expected)["passed"])
        contract["retention_physically_verified"] = True
        actual.OpticalMountContract = json.dumps(contract)
        self.assertFalse(compare_shape_objects(actual, expected)["passed"])


if __name__ == "__main__":
    unittest.main()
