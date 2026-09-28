"""Verify native mounting pads, printed-part flags and hardware thread metadata."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class NativeInterfaceTests(unittest.TestCase):
    def test_complete_assembly_preserves_a_common_frame_and_removable_servo_module(
        self,
    ):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from gondola import assembly
        from gondola.cad import belongs_to_group
        from gondola.contracts.design import EXCLUDED_EQUIPMENT, EXPECTED_INVENTORY
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.validation.propulsion import (
            fixed_servo_datum_check,
            servo_mount_check,
        )

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(assembly, "OUTPUT_DIR", Path(directory)):
                doc = assembly.build_assembly()
            try:
                self.assertEqual(
                    doc.PropulsionFixedFrame.PrintSKU, SELECTED_DRIVE.frame_sku
                )
                self.assertEqual(
                    doc.ServoDriveBridge.PrintSKU, SELECTED_DRIVE.bridge_sku
                )
                self.assertEqual(
                    doc.ServoDriveModule.getParentGeoFeatureGroup(),
                    doc.MainPropulsionModule,
                )
                self.assertEqual(
                    doc.ServoDriveBridge.getParentGeoFeatureGroup(),
                    doc.ServoDriveModule,
                )
                self.assertFalse(
                    belongs_to_group(doc.PropulsionFixedFrame, doc.ServoDriveModule)
                )
                self.assertNotIn(doc.ServoDriveModule, doc.DesignRegistry.Modules)
                self.assertEqual(len(doc.DesignRegistry.Modules), 4)
                self.assertEqual(
                    len(doc.DesignRegistry.PrintedParts),
                    EXPECTED_INVENTORY["installed_prints"],
                )
                self.assertEqual(
                    len(doc.DesignRegistry.HardwareParts),
                    EXPECTED_INVENTORY["purchased_hardware"],
                )
                self.assertEqual(
                    doc.DesignRegistry.ScopeExclusions.split("; "),
                    list(EXCLUDED_EQUIPMENT),
                )
                self.assertEqual(
                    list(doc.DesignRegistry.PrintedParts).count(doc.ServoDriveBridge), 1
                )
                for prefix in ("Port", "Starboard"):
                    self.assertEqual(
                        doc.getObject(prefix + "ServoMount").getParentGeoFeatureGroup(),
                        doc.ServoDriveModule,
                    )
                    self.assertFalse(
                        belongs_to_group(
                            doc.getObject(prefix + "Pod"), doc.ServoDriveModule
                        )
                    )
                    self.assertIsNone(doc.getObject(prefix + "ServoHolder"))
                    for kind in ("Bolt", "Nut"):
                        self.assertIn(
                            doc.getObject("ServoBridge" + prefix + kind),
                            doc.DesignRegistry.HardwareParts,
                        )
                    for side in ("Negative", "Positive"):
                        for kind in ("Bolt", "Nut"):
                            self.assertIsNone(
                                doc.getObject(prefix + "HolderMount" + side + kind)
                            )
                    self.assertFalse(
                        belongs_to_group(
                            doc.PropulsionFixedFrame,
                            doc.getObject(prefix + "ServoMount"),
                        )
                    )
                    for check in (fixed_servo_datum_check, servo_mount_check):
                        result = check(doc, prefix)
                        self.assertTrue(result["passed"], result)
            finally:
                App.closeDocument(doc.Name)

    def test_native_rail_clamps_declare_m2_thread_dimensions(self):
        from gondola.cad import create_group
        from gondola.parts import rail

        document = App.newDocument("RailThreadRegressionTest")
        self.addCleanup(App.closeDocument, document.Name)
        parent = create_group(document, "ClampGroup", "Clamp hardware")
        hardware = rail.build_clamp_hardware(document, parent, "Test")
        self.assertEqual(len(hardware), 4)
        for part in hardware:
            self.assertEqual(part.NominalThreadDiameter.Value, 2)
            self.assertEqual(part.ThreadPitch.Value, 0.4)
            self.assertIn("M2", part.ThreadStandard)
            self.assertNotIn("unthreaded", part.ThreadStandard.lower())

    def test_shared_nut_and_clamp_screw_declare_m2_threads(self):
        from gondola.contracts import fasteners
        from gondola.parts import purchased_hardware

        document = App.newDocument("HardwareThreadRegressionTest")
        self.addCleanup(App.closeDocument, document.Name)
        parts = (
            ("M2_HEX_NUT", purchased_hardware.hex_nut_shape()),
            ("M2X8_BUTTON_HEAD", purchased_hardware.screw_shape(8)),
        )
        for index, (sku, shape) in enumerate(parts):
            with self.subTest(sku=sku):
                obj = purchased_hardware.add_hardware(
                    document,
                    None,
                    f"Hardware{index}",
                    sku,
                    shape,
                    sku,
                    "Test only",
                    material=fasteners.KIT_MATERIAL,
                )
                self.assertEqual(obj.NominalThreadDiameter.Value, 2)
                self.assertEqual(obj.ThreadPitch.Value, 0.4)
                self.assertNotIn("unthreaded", obj.ThreadStandard.lower())

    def test_native_print_factory_sets_explicit_print_flag(self):
        from gondola.cad import create_group, create_printed_part

        document = App.newDocument("PrintFactoryRegressionTest")
        self.addCleanup(App.closeDocument, document.Name)
        parent = create_group(document, "PrintGroup", "Printed test parts")
        part = create_printed_part(
            document,
            parent,
            "PrintedPart",
            "Printed factory test",
            Part.makeBox(2, 3, 4),
            App.Rotation(),
            "Test only",
        )
        self.assertIn("PrintPart", part.PropertiesList)
        self.assertTrue(part.PrintPart)
        self.assertEqual(part.getTypeIdOfProperty("PrintPart"), "App::PropertyBool")

    def test_bought_plate_identity_does_not_infer_unknown_lands(self):
        from gondola.contracts.stack_adapter import COMMON_HOLE_CENTRES
        from gondola.parts import stock_adapter

        shape = stock_adapter.plate_shape()
        self.assertTrue(shape.isValid())
        for x, y in COMMON_HOLE_CENTRES:
            bore = Part.makeCylinder(1, 1, App.Vector(x, y, 7))
            self.assertLess(abs(shape.common(bore).Volume), 1e-7)
        contract = stock_adapter.mounting_contract()
        self.assertFalse(contract["physical_fit_verified"])
        self.assertIn("not dimensioned", contract["purchased_plate"]["contour_scope"])

    def test_portal_toggles_existing_fc_nuts_only(self):
        from gondola.cad import create_group
        from gondola.parts import stock_adapter

        doc = App.newDocument("StockFCSeparatePortal")
        self.addCleanup(App.closeDocument, doc.Name)
        parent = create_group(doc, "ElectronicsEquipmentModule", "FC")
        result = stock_adapter.build_stock_adapter(doc, parent)
        before = {obj.Name: obj.Shape.copy() for obj in result["hardware"]}
        object_count = len(doc.Objects)
        stock_adapter.set_fc_portal(doc, True)
        self.assertEqual(len(result["hardware"]), 9)
        self.assertEqual(len(doc.Objects), object_count)
        for name in stock_adapter.BOLT_OBJECT_NAMES:
            self.assertLess(
                abs(doc.getObject(name).Shape.cut(before[name]).Volume), 1e-7
            )
        stock_adapter.set_fc_portal(doc, False)
        for name, shape in before.items():
            actual = doc.getObject(name).Shape
            self.assertLess(
                abs(actual.cut(shape).Volume) + abs(shape.cut(actual).Volume), 1e-7
            )


if __name__ == "__main__":
    unittest.main()
