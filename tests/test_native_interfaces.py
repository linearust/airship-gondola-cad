"""Verify native mounting pads, printed-part flags and hardware thread metadata."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class NativeInterfaceTests(unittest.TestCase):
    def test_native_rail_clamps_declare_m2_thread_dimensions(self):
        from gondola.cad import create_group
        from gondola.parts import rail

        document = App.newDocument("RailThreadRegressionTest")
        self.addCleanup(App.closeDocument, document.Name)
        parent = create_group(document, "ClampGroup", "Clamp hardware")
        hardware = rail.build_clamp_hardware(document, parent, "Test", "0")
        self.assertEqual(len(hardware), 2)
        for part in hardware:
            self.assertEqual(part.NominalThreadDiameter.Value, 2)
            self.assertEqual(part.ThreadPitch.Value, 0.4)
            self.assertIn("M2", part.ThreadStandard)
            self.assertNotIn("unthreaded", part.ThreadStandard.lower())

    def test_shared_nut_and_clamp_screw_declare_m2_threads(self):
        from gondola.parts import purchased_hardware

        document = App.newDocument("HardwareThreadRegressionTest")
        self.addCleanup(App.closeDocument, document.Name)
        parts = (
            ("M2_SQUARE_NUT_DIN562", purchased_hardware.square_nut_shape()),
            ("M2X8_SOCKET_CAP", purchased_hardware.screw_shape(8)),
        )
        for index, (sku, shape) in enumerate(parts):
            with self.subTest(sku=sku):
                obj = purchased_hardware.add_hardware(
                    document, None, f"Hardware{index}", sku, shape, sku, "Test only"
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

    def test_saved_mount_has_complete_bearing_annuli_and_clear_bores(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import mounting_pad_check

        shape = mounts.mount_shape("electronics").copy()
        for centre in mounts.FC_HOLE_CENTRES + mounts.PAS_HOLE_CENTRES:
            result = mounting_pad_check(
                shape,
                centre,
                bottom=mounts.DECK_BOTTOM_Z,
                thickness=mounts.DECK_THICKNESS,
                hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
                pad_diameter=mounts.MOUNT_PAD_DIAMETER,
            )
            self.assertTrue(result["passed"], result)

    def test_partial_bearing_or_filled_bore_is_rejected(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import mounting_pad_check

        shape = mounts.mount_shape("electronics").copy()
        centre = mounts.FC_HOLE_CENTRES[0]
        x, y = centre
        bottom, thickness = mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS
        missing_edge = shape.cut(
            Part.makeBox(1, 1, thickness + 2, App.Vector(x - 3.3, y - 0.5, bottom - 1))
        )
        blocked_bore = shape.fuse(
            Part.makeCylinder(0.4, thickness, App.Vector(x, y, bottom))
        )
        for changed in (missing_edge, blocked_bore):
            result = mounting_pad_check(
                changed,
                centre,
                bottom=bottom,
                thickness=thickness,
                hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
                pad_diameter=mounts.MOUNT_PAD_DIAMETER,
            )
            self.assertFalse(result["passed"], result)


if __name__ == "__main__":
    unittest.main()
