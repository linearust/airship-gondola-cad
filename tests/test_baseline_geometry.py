"""Frozen-design regression gates; execute inside the FreeCAD Python runtime."""

import json
import tempfile
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
        from gondola.contracts.design import ModuleStation

        self.stations = tuple(
            ModuleStation(name, x)
            for name, x in (
                ("Battery", -100),
                ("Propulsion", 0),
                ("Electronics", 60),
                ("Optical", -140),
            )
        )
        self.modules = [
            SimpleNamespace(
                Name=station.object_name,
                PropertiesList=[
                    "RailAttachmentOffsetX",
                    "RailPositionX",
                    "RailContactLength",
                ],
                Placement=App.Placement(App.Vector(station.x_mm, 0, 0), App.Rotation()),
            )
            for station in self.stations
        ]
        self.doc = SimpleNamespace(
            DesignRegistry=SimpleNamespace(Modules=list(reversed(self.modules))),
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
            self.modules[-1].PropertiesList.pop()
            self.assertFalse(baseline.control_behavior(self.doc)["passed"])

    def test_duplicate_module_cannot_hide_a_missing_attachment_control(self):
        from gondola.validation import baseline

        self.doc.DesignRegistry.Modules = self.modules[:3] + [self.modules[0]]
        with patch.object(baseline, "MODULE_STATIONS", self.stations):
            self.assertFalse(baseline.control_behavior(self.doc)["passed"])

    def test_actual_manual_stages_are_bounded_and_independent(self):
        from gondola.cad import create_group, set_property
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts.optical_mount import build_optical_mount
        from gondola.validation.baseline import control_behavior

        doc = App.newDocument("ManualControlRegression")
        self.addCleanup(
            lambda name=doc.Name: (
                App.closeDocument(name) if name in App.listDocuments() else None
            )
        )
        modules = []
        for station in MODULE_STATIONS:
            module = create_group(doc, station.object_name, station.object_name)
            module.Placement.Rotation = App.Rotation(
                App.Vector(0, 0, 1), station.yaw_deg
            )
            set_property(
                module,
                "RailAttachmentOffsetX",
                station.attachment_offset_x_mm,
                "App::PropertyDistance",
            )
            set_property(module, "RailPositionX", station.x_mm, "App::PropertyDistance")
            set_property(
                module,
                "RailContactLength",
                station.contact_length_mm,
                "App::PropertyLength",
            )
            module.setExpression("Placement.Base.x", "RailPositionX")
            modules.append(module)
        build_optical_mount(doc, doc.BatteryEquipmentModule)
        pods = []
        for name in ("PortPod", "StarboardPod"):
            pod = create_group(doc, name, name)
            pod.Placement.Rotation = App.Rotation(App.Vector(0, 1, 0), 1)
            set_property(pod, "Tilt", 0, "App::PropertyAngle")
            pod.setExpression(
                "Placement.Rotation.Angle", "min(180deg; max(-180deg; Tilt))"
            )
            pods.append(pod)
        registry = doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        set_property(registry, "Modules", modules, "App::PropertyLinkListGlobal")
        set_property(registry, "TiltingPods", pods, "App::PropertyLinkListGlobal")
        doc.recompute()
        result = control_behavior(doc)
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["cases"]), result["expected_case_count"])
        self.assertEqual(
            sum(row["property"] == "RailPositionX" for row in result["cases"]), 8
        )
        doc.OpticalPitchStage.MaximumAngle = 30
        self.assertFalse(control_behavior(doc)["passed"])
        doc.OpticalPitchStage.MaximumAngle = 20
        # Saved manual positions remain editable; the validator rejects positions
        # outside the supported slot intervals without silently clamping them.
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/controls.FCStd"
            doc.saveAs(path)
            App.closeDocument(doc.Name)
            restored = App.openDocument(path)
            self.assertTrue(control_behavior(restored)["passed"])
            restored.BatteryEquipmentModule.RailPositionX = 999
            restored.recompute()
            self.assertFalse(control_behavior(restored)["passed"])
            self.assertEqual(float(restored.BatteryEquipmentModule.RailPositionX), 999)

    def test_continuous_carrier_rejects_unsupported_station_offset_or_rotation(self):
        from gondola.contracts.design import ModuleStation
        from gondola.validation.baseline import module_attachment_pose

        for yaw in (0, 180):
            station = ModuleStation("Test", -70, yaw)
            module = SimpleNamespace(
                RailAttachmentOffsetX=0,
                RailContactLength=16,
                RailPositionX=-70,
                Placement=App.Placement(
                    App.Vector(-70, 0, 0), App.Rotation(App.Vector(0, 0, 1), yaw)
                ),
            )
            self.assertTrue(module_attachment_pose(station, module)["passed"])
            for attribute, replacement in (
                ("RailAttachmentOffsetX", 20),
                ("RailContactLength", 32),
                ("RailPositionX", -80),
            ):
                original = getattr(module, attribute)
                setattr(module, attribute, replacement)
                self.assertFalse(module_attachment_pose(station, module)["passed"])
                setattr(module, attribute, original)
            original = module.Placement.copy()
            for vector, angle in (
                (App.Vector(-70, 0.1, 0), yaw),
                (App.Vector(-70, 0, 0.1), yaw),
                (App.Vector(-70, 0, 0), 180 - yaw),
            ):
                module.Placement = App.Placement(
                    vector, App.Rotation(App.Vector(0, 0, 1), angle)
                )
                self.assertFalse(module_attachment_pose(station, module)["passed"])
            module.Placement = original

    def test_shapeless_stack_and_rail_group_metadata_is_frozen_too(self):
        from gondola.cad import create_group, set_property
        from gondola.validation.baseline import native_interface_metadata

        doc = App.newDocument("StackGroupMetadataRegression")
        self.addCleanup(App.closeDocument, doc.Name)
        group = create_group(doc, "OpticalFlowModule", "Optical head")
        set_property(
            group,
            "OpticalInterfaceContract",
            '{"default_host":"BatteryEquipmentModule"}',
        )
        set_property(group, "HoldingTorqueVerified", False, "App::PropertyBool")
        original = native_interface_metadata(doc)
        self.assertIn(group.Name, original)
        group.HoldingTorqueVerified = True
        self.assertNotEqual(original, native_interface_metadata(doc))
        group.HoldingTorqueVerified = False
        group.OpticalInterfaceContract = '{"default_host":"ElectronicsEquipmentModule"}'
        self.assertNotEqual(original, native_interface_metadata(doc))
        carrier = create_group(doc, "BatteryEquipmentModule", "Rail carrier")
        set_property(
            carrier, "RailAttachmentContract", '{"physical_fit_verified": false}'
        )
        original = native_interface_metadata(doc)
        self.assertIn(carrier.Name, original)
        carrier.RailAttachmentContract = '{"physical_fit_verified": true}'
        self.assertNotEqual(original, native_interface_metadata(doc))
        mount = create_group(doc, "ElectronicsMount", "Equipment carrier")
        set_property(mount, "MountContract", '{"fc_wiring_clearance_mm": 8.0}')
        original = native_interface_metadata(doc)
        self.assertIn(mount.Name, original)
        mount.MountContract = '{"fc_wiring_clearance_mm": 4.0}'
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
        from gondola.contracts.design import (
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
            {"BatteryMount", "ElectronicsMount", "AccessoryMount"},
        )
        self.assertEqual(
            len(registry.EquipmentMounts), EXPECTED_INVENTORY["equipment_mounts"]
        )
        self.assertEqual(
            {obj.Name for obj in getattr(registry, "OpticalMountParts", [])},
            {"OpticalMountBase", "OpticalSensorTray"},
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
        from gondola.validation.baseline import control_behavior

        result = control_behavior(self.reference)
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["cases"]), result["expected_case_count"])
        self.assertEqual(
            sum(row["property"] == "RailPositionX" for row in result["cases"]), 8
        )

    def test_horn_clamp_cannot_silently_claim_qualified_manufacture(self):
        from gondola.validation.baseline import unresolved_scope

        clamp = self.reference.PortHornGearAdapter
        original = clamp.ManufacturingStatus
        try:
            clamp.ManufacturingStatus = "Production qualified"
            self.assertFalse(unresolved_scope(self.reference)["passed"])
        finally:
            clamp.ManufacturingStatus = original

    def test_rail_scope_rejects_missing_or_malformed_attachment_contract(self):
        from gondola.validation.baseline import unresolved_scope

        incomplete = SimpleNamespace(
            DesignRegistry=self.reference.DesignRegistry,
            ContinuousRail=SimpleNamespace(),
            getObject=self.reference.getObject,
        )
        self.assertFalse(unresolved_scope(incomplete)["passed"])
        rail = self.reference.ContinuousRail
        original = rail.RailAttachmentContract
        try:
            for malformed in ("not JSON", "null", "[]", "{}"):
                with self.subTest(contract=malformed):
                    rail.RailAttachmentContract = malformed
                    self.assertFalse(unresolved_scope(self.reference)["passed"])
        finally:
            rail.RailAttachmentContract = original

    def test_rail_scope_rejects_thinner_base_or_unearned_qualification(self):
        from gondola.validation.baseline import unresolved_scope

        rail = self.reference.ContinuousRail
        original = rail.RailAttachmentContract
        contract = json.loads(original)
        try:
            for field, value in (
                ("minimum_base_mm", 0.8),
                ("as_printed_fit_guaranteed", True),
                ("physical_fit_verified", True),
                ("holding_force_verified", True),
                ("physical_fit_verified", "false"),
            ):
                with self.subTest(field=field, value=value):
                    changed = dict(contract)
                    changed[field] = value
                    rail.RailAttachmentContract = json.dumps(changed)
                    result = unresolved_scope(self.reference)
                    self.assertFalse(
                        result["rail_attachment_qualification_remains_unverified"]
                    )
                    self.assertFalse(result["passed"])
        finally:
            rail.RailAttachmentContract = original

    def test_horn_sku_and_profile_must_match_each_selected_side(self):
        from gondola.contracts import servo_horns
        from gondola.validation.baseline import unresolved_scope

        for prefix in ("Port", "Starboard"):
            horn = self.reference.getObject(prefix + "ServoHorn")
            expected = servo_horns.profile(side=prefix)
            # Only one profile is supported; reject unknown identity without
            # requiring a second selectable horn just to exercise corruption.
            other = SimpleNamespace(sku="UNSUPPORTED_HORN_SKU", key="UNSUPPORTED_HORN")
            original = horn.HardwareSKU, horn.HornProfile
            try:
                for sku, profile in (
                    (other.sku, expected.key),
                    (expected.sku, other.key),
                    (other.sku, other.key),
                ):
                    with self.subTest(side=prefix, sku=sku, profile=profile):
                        horn.HardwareSKU, horn.HornProfile = sku, profile
                        self.assertFalse(unresolved_scope(self.reference)["passed"])
            finally:
                horn.HardwareSKU, horn.HornProfile = original

    def test_rail_has_no_comparison_exception(self):
        from gondola.validation.baseline import compare_shape_objects
        from gondola.validation.geometry import local_shape

        shape = local_shape(self.reference.ContinuousRail)
        expected = self.feature("ExpectedRail", shape)
        actual = self.feature("ContinuousRail", shape)
        self.assertTrue(compare_shape_objects(actual, expected)["passed"])
        # The old z=6 probe now falls inside the intentional side slot.
        # Remove material from the continuous 1.5 mm base instead.
        actual.Shape = shape.cut(Part.makeBox(1, 1, 1, App.Vector(-0.5, -0.5, 0.25)))
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
            obj.HardwareSKU = "M2X8_BUTTON_HEAD"
            obj.addProperty("App::PropertyBool", "PrintPart")
            obj.PrintPart = False
            obj.addProperty("App::PropertyString", "PurchaseRequirements")
            obj.PurchaseRequirements = "Kit steel M2x8; unmeasured button-head envelope"
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
        properties = (
            (
                "OpticalMountContract",
                "App::PropertyString",
                '{"angle_limit_deg":20}',
                "{}",
            ),
            (
                "OpticalInterfaceContract",
                "App::PropertyString",
                '{"default_station_x_mm":144}',
                "{}",
            ),
            ("OpticalFitVerified", "App::PropertyBool", False, True),
        )
        for name, kind, original, changed in properties:
            for obj in (expected, actual):
                obj.addProperty(kind, name)
                setattr(obj, name, original)
            with self.subTest(property=name):
                self.assertTrue(compare_shape_objects(actual, expected)["passed"])
                setattr(actual, name, changed)
                self.assertFalse(compare_shape_objects(actual, expected)["passed"])
                setattr(actual, name, original)


if __name__ == "__main__":
    unittest.main()
