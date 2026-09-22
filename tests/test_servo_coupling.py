"""Physical fit and assembly paths for the direct stock-horn gear adapter."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class ServoCouplingTests(unittest.TestCase):
    @staticmethod
    def _servo_envelope():
        from gondola.cad import box

        case = box(20, 16.6, 7, (-5, -16.8, -3.5))
        ears = box(28, 1, 7, (-9, -4.9, -3.5))
        shape = case.fuse(ears)
        shape.rotate(App.Vector(), App.Vector(0, 1, 0), 90)
        return shape

    @staticmethod
    def _clamp_hardware():
        from gondola.parts import purchased_hardware as hardware
        from gondola.parts import servo_coupling as coupling

        anchors = coupling.fastener_positions()[0]
        rotation = App.Rotation(
            App.Vector(0, 0, 1), App.Vector(*coupling.BOLT_DIRECTION)
        )
        result = []
        for shape, anchor in (
            (hardware.screw_shape(), anchors["screw"]),
            (hardware.square_nut_shape(), anchors["nut"]),
        ):
            placed = shape.copy()
            placed.Placement = App.Placement(App.Vector(*anchor), rotation)
            result.append(placed)
        return result

    def test_stock_horn_gear_and_fasteners_fit_without_drilling_the_horn(self):
        from gondola.parts import servo_coupling as coupling

        main = coupling.adapter_shape()
        retainer = coupling.retainer_shape()
        horn = coupling.horn_shape()
        # This full tip-diameter cylinder conservatively contains the bought
        # driver's teeth; its hub and 7 mm bore are the catalog dimensions.
        axis = App.Vector(0, 1, 0)
        start = coupling.SPIGOT_START_Y
        gear = Part.makeCylinder(5, 5, App.Vector(0, start, 0), axis).fuse(
            Part.makeCylinder(15.5, 3, App.Vector(0, start + 5, 0), axis)
        )
        gear = gear.cut(
            Part.makeCylinder(3.5, 8.2, App.Vector(0, start - 0.1, 0), axis)
        )
        screw, nut = self._clamp_hardware()
        shapes = [main, retainer, horn, gear, screw, nut]
        for shape in shapes:
            self.assertTrue(shape.isValid())
            self.assertEqual(len(shape.Solids), 1)
        for index, first in enumerate(shapes):
            for second in shapes[index + 1 :]:
                self.assertLess(first.common(second).Volume, 1e-7)
        self.assertAlmostEqual(main.distToShape(gear)[0], 0, places=6)
        journal = Part.makeCylinder(3.45, 8, App.Vector(0, start, 0), axis).cut(
            Part.makeCylinder(1.5, 8, App.Vector(0, start, 0), axis)
        )
        self.assertLess(journal.cut(main).Volume, 1e-7)
        spigot = main.common(
            Part.makeCylinder(3.46, 7.9, App.Vector(0, start + 0.05, 0), axis)
        )
        self.assertAlmostEqual(spigot.distToShape(gear)[0], 0.05, places=6)
        self.assertAlmostEqual(main.distToShape(horn)[0], 0, places=6)
        self.assertAlmostEqual(retainer.distToShape(horn)[0], 0, places=6)

    def test_shallow_socket_centres_the_horn_and_clamps_before_the_parts_bottom(self):
        from gondola.parts import servo_coupling as coupling

        main = coupling.adapter_shape()
        retainer = coupling.retainer_shape()
        horn = coupling.horn_shape()
        registers = [
            face
            for face in main.Faces
            if type(face.Surface).__name__ == "Cylinder"
            and abs(face.Surface.Radius - 3.05) < 1e-7
        ]
        self.assertTrue(registers)
        for face in registers:
            self.assertAlmostEqual(face.BoundBox.YLength, 1.3, places=6)
            self.assertAlmostEqual(face.BoundBox.YMax, 3.5, places=6)
        self.assertAlmostEqual(main.distToShape(retainer)[0], 0.3, places=6)
        for direction, obstacle in ((1, main), (-1, retainer)):
            displaced = horn.copy()
            displaced.translate(App.Vector(0, direction * 0.01, 0))
            self.assertGreater(displaced.common(obstacle).Volume, 1e-5)

    def test_parts_install_around_an_already_retained_horn_at_neutral(self):
        from gondola.parts import servo_coupling as coupling

        main = coupling.adapter_shape()
        retainer = coupling.retainer_shape()
        horn = coupling.horn_shape()
        case = self._servo_envelope()
        for step in range(1, 51):
            distance = step * 0.5
            incoming = main.copy()
            incoming.translate(App.Vector(0, distance, 0))
            self.assertLess(incoming.common(horn).Volume, 1e-7)
            incoming = retainer.copy()
            incoming.translate(App.Vector(0, -distance, 0))
            for obstacle in (main, horn, case):
                self.assertLess(incoming.common(obstacle).Volume, 1e-7)

    def test_rear_clamp_head_clears_servo_through_full_input_travel(self):
        from gondola.parts import servo_coupling as coupling

        case = self._servo_envelope()
        moving = [
            coupling.adapter_shape(),
            coupling.retainer_shape(),
            *self._clamp_hardware(),
        ]
        for angle in range(-60, 61, 5):
            for shape in moving:
                rotated = shape.copy()
                rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
                self.assertLess(rotated.common(case).Volume, 1e-7)
                self.assertGreaterEqual(rotated.distToShape(case)[0], 0.6 - 1e-7)

    def test_functional_walls_and_powder_escape_remain_open(self):
        from gondola.parts import servo_coupling as coupling
        from gondola.validation.manufacturing import planar_wall_regions

        main = coupling.adapter_shape()
        for shape in (main, coupling.retainer_shape()):
            thin = [
                row
                for row in planar_wall_regions(shape)
                if row["material_thickness_mm"] < 1.5 - 1e-6
            ]
            self.assertEqual(thin, [])
        self.assertGreaterEqual(
            (coupling.SPIGOT_DIAMETER - coupling.SPIGOT_BORE_DIAMETER) / 2, 1.5
        )
        escape = Part.makeCylinder(1.5, 16, App.Vector(0, -0.1, 0), App.Vector(0, 1, 0))
        self.assertLess(main.common(escape).Volume, 1e-7)
        # Sample between the through-bore and OEM head cavity. The shortened
        # body must retain its 1.9 mm roof before the gear journal starts.
        for x, z in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            section = Part.makeLine(
                App.Vector(x, -0.1, z), App.Vector(x, coupling.SPIGOT_START_Y, z)
            )
            self.assertAlmostEqual(main.common(section).Length, 1.9, places=6)


if __name__ == "__main__":
    unittest.main()
