"""Exact slot geometry and saved-material mutation checks for universal plates."""

import math
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class MountingSlotTests(unittest.TestCase):
    def test_slot_volumes_match_capsule_and_rounded_arc_formulae(self):
        from gondola.parts import mounting_slots

        rows = mounting_slots.rows()
        self.assertEqual(len(rows), 10)
        self.assertEqual(len({row["name"] for row in rows}), 10)
        self.assertEqual(sum(row["kind"] == "straight" for row in rows), 6)
        self.assertEqual(sum(row["kind"] == "arc" for row in rows), 4)
        for row in rows:
            for border in (0.0, 1.5):
                radius = row["width_mm"] / 2 + border
                if row["kind"] == "straight":
                    length = math.dist(row["start_xy_mm"], row["end_xy_mm"])
                else:
                    length = row["radius_mm"] * math.radians(
                        row["end_angle_deg"] - row["start_angle_deg"]
                    )
                shape = mounting_slots.shape(row, 7.0, 2.0, border=border)
                with self.subTest(slot=row["name"], border=border):
                    self.assertTrue(shape.isValid())
                    self.assertEqual(len(shape.Solids), 1)
                    self.assertAlmostEqual(
                        shape.Volume,
                        2 * (2 * radius * length + math.pi * radius**2),
                        places=6,
                    )
                    self.assertAlmostEqual(shape.BoundBox.ZMin, 7)
                    self.assertAlmostEqual(shape.BoundBox.ZMax, 9)

    def test_invalid_closed_or_degenerate_slots_are_rejected(self):
        from gondola.parts import mounting_slots

        straight = next(
            row for row in mounting_slots.rows() if row["kind"] == "straight"
        )
        arc = next(row for row in mounting_slots.rows() if row["kind"] == "arc")
        for row in (
            {**straight, "end_xy_mm": straight["start_xy_mm"]},
            {**arc, "end_angle_deg": arc["start_angle_deg"]},
            {**arc, "end_angle_deg": arc["start_angle_deg"] + 360},
            {**arc, "radius_mm": 0.5},
            {**straight, "kind": "unknown"},
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                mounting_slots.shape(row, 0, 2)
        for depth, border in ((0, 0), (-1, 0), (2, -0.1)):
            with (
                self.subTest(depth=depth, border=border),
                self.assertRaises(ValueError),
            ):
                mounting_slots.shape(straight, 0, depth, border=border)

    def test_continuous_lands_detect_midpath_blockage_and_oblique_edge_notches(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import mounting_slots
        from gondola.validation.equipment import carrier_opening_checks

        original = mounts.common_plate_shape()
        self.assertTrue(original.isValid())
        self.assertEqual(len(original.Solids), 1)
        self.assertTrue(carrier_opening_checks(original)["passed"])
        specs = [
            next(row for row in mounting_slots.rows() if row["family"] == family)
            for family in ("square20_24", "square30_5", "side")
        ]
        for row in specs:
            fraction = 0.413
            if row["kind"] == "arc":
                angle = math.radians(
                    row["start_angle_deg"]
                    + fraction * (row["end_angle_deg"] - row["start_angle_deg"])
                )
                normal = App.Vector(math.cos(angle), math.sin(angle), 0)
                centre = normal * row["radius_mm"]
            else:
                start = App.Vector(*row["start_xy_mm"], 0)
                delta = App.Vector(*row["end_xy_mm"], 0) - start
                centre = start + delta * fraction
                normal = App.Vector(-delta.y, delta.x, 0) / delta.Length
            centre.z = mounts.DECK_BOTTOM_Z
            # A disk crossing both edges is joined to the existing plate: failure
            # must come from the obstructed slot, not disconnected-solid status.
            obstruction = Part.makeCylinder(
                row["width_mm"] / 2 + 0.15, mounts.DECK_THICKNESS, centre
            )
            blocked = original.fuse(obstruction).removeSplitter()
            self.assertEqual(len(blocked.Solids), 1)
            report = carrier_opening_checks(blocked)
            item = next(
                item for item in report["mounting_slots"] if item["name"] == row["name"]
            )
            with self.subTest(slot=row["name"], mutation="interior obstruction"):
                self.assertFalse(report["passed"])
                self.assertGreater(item["through_slot_obstruction_mm3"], 0.1)
            notch_centre = centre + normal * (row["width_mm"] / 2 + 0.7)
            notch = Part.makeCylinder(0.18, mounts.DECK_THICKNESS, notch_centre)
            damaged = original.cut(notch)
            self.assertEqual(len(damaged.Solids), 1)
            report = carrier_opening_checks(damaged)
            item = next(
                item for item in report["mounting_slots"] if item["name"] == row["name"]
            )
            with self.subTest(slot=row["name"], mutation="interior edge notch"):
                self.assertFalse(report["passed"])
                self.assertLess(item["through_slot_obstruction_mm3"], 1e-6)
                self.assertGreater(
                    item["missing_continuous_full_thickness_land_mm3"], 0.01
                )

    def test_declared_adhesive_area_is_retained_and_an_interior_break_is_rejected(self):
        from gondola.parts import equipment_envelopes
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment_options import adhesive_support_check

        self.assertEqual(
            sum(size[0] * size[1] for _, size in mounts.BATTERY_ADHESIVE_REGIONS), 512
        )
        support = mounts.mount_shape("accessory")
        body = equipment_envelopes.radio_envelope_shape()
        centre = mounts.RADIO_CENTRE_XY
        notch = Part.makeCylinder(
            0.2, mounts.DECK_THICKNESS, App.Vector(*centre, mounts.DECK_BOTTOM_Z)
        )
        damaged = support.cut(notch)
        report = adhesive_support_check(
            damaged, body, centre, mounts.RADIO_ADHESIVE_SIZE, face="bottom"
        )
        self.assertFalse(report["passed"])

    def test_void_probe_cannot_omit_part_of_declared_deck_thickness(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import carrier_opening_checks

        shape = mounts.common_plate_shape()
        for bottom, depth in (
            (mounts.DECK_BOTTOM_Z + 0.1, 2),
            (mounts.DECK_BOTTOM_Z, 1.9),
        ):
            with (
                self.subTest(bottom=bottom, depth=depth),
                self.assertRaises(ValueError),
            ):
                carrier_opening_checks(
                    shape, through_bottom=bottom, through_depth=depth
                )


if __name__ == "__main__":
    unittest.main()
