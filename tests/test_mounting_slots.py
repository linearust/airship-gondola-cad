"""Exact slot geometry and saved-material mutation checks for universal plates."""

import math
import unittest

try:
    import FreeCAD as App
    import Part

    from gondola.parts import mounting_plate
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class MountingSlotTests(unittest.TestCase):
    def test_saved_deck_openings_have_quarter_turn_and_both_mirror_symmetries(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import carrier_opening_checks

        original = mounting_plate.shape()
        report = carrier_opening_checks(original, centre_hole_diameter=2.6)
        self.assertTrue(report["deck_symmetry"]["passed"], report)
        self.assertTrue(report["passed"], report)
        # A new hole away from existing openings retains every specified rim.
        # Symmetry must reject the changed saved material independently.
        notch = Part.makeCylinder(
            0.3,
            mounts.DECK_THICKNESS,
            App.Vector(12, 2, mounts.DECK_BOTTOM_Z),
        )
        changed = original.cut(notch)
        single = carrier_opening_checks(changed, centre_hole_diameter=2.6)
        self.assertTrue(all(row["passed"] for row in single["mounting_slots"]))
        self.assertTrue(all(row["passed"] for row in single["fixed_device_bores"]))
        self.assertFalse(single["deck_symmetry"]["passed"])
        self.assertFalse(single["passed"])
        # Four identical notches preserve rotation but create a chiral array.
        # A rotation-only symmetry check would incorrectly accept this shape.
        for angle in (90, 180, 270):
            rotated = notch.copy()
            rotated.rotate(App.Vector(), App.Vector(0, 0, 1), angle)
            changed = changed.cut(rotated)
        chiral = carrier_opening_checks(changed, centre_hole_diameter=2.6)[
            "deck_symmetry"
        ]
        self.assertLess(chiral["quarter_turn_difference_mm3"], 1e-6)
        self.assertGreater(chiral["mirror_x_difference_mm3"], 0.1)
        self.assertGreater(chiral["mirror_y_difference_mm3"], 0.1)
        self.assertFalse(chiral["passed"])

    def test_pas_slot_axes_keep_bearing_sides_without_requiring_a_round_annulus(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import (
            mounting_pad_check,
            slot_mounting_pad_check,
        )

        original = mounting_plate.shape()
        for centre in mounts.PAS_HOLE_CENTRES:
            arguments = dict(
                bottom=mounts.DECK_BOTTOM_Z,
                thickness=mounts.DECK_THICKNESS,
                hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
                pad_diameter=mounts.MOUNT_PAD_DIAMETER,
            )
            with self.subTest(centre=centre):
                self.assertTrue(
                    slot_mounting_pad_check(original, centre, **arguments)["passed"]
                )
                self.assertFalse(
                    mounting_pad_check(original, centre, **arguments)["passed"]
                )
                origin = App.Vector(*centre, mounts.DECK_BOTTOM_Z)
                normal = App.Vector(-centre[1], centre[0], 0)
                normal.normalize()
                for sign in (-1, 1):
                    cut = Part.makeCylinder(
                        0.2, mounts.DECK_THICKNESS, origin + normal * (sign * 2.0)
                    )
                    row = slot_mounting_pad_check(
                        original.cut(cut), centre, **arguments
                    )
                    self.assertFalse(row["passed"])
                    self.assertGreater(
                        row["missing_full_thickness_slot_bearing_mm3"], 0.01
                    )
                fill = Part.makeCylinder(0.3, mounts.DECK_THICKNESS, origin)
                self.assertFalse(
                    slot_mounting_pad_check(original.fuse(fill), centre, **arguments)[
                        "passed"
                    ]
                )
                # Published axes cannot drift sideways out of their actual slot.
                shifted = (centre[0] + normal.x, centre[1] + normal.y)
                self.assertFalse(
                    slot_mounting_pad_check(original, shifted, **arguments)["passed"]
                )

    def test_all_nominal_contact_patches_reject_missing_interior_material(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import carrier_contact_patch_checks

        original = mounting_plate.shape()
        arguments = dict(bottom=mounts.DECK_BOTTOM_Z, thickness=mounts.DECK_THICKNESS)
        report = carrier_contact_patch_checks(original, **arguments)
        self.assertEqual(
            len(report["patches"]),
            len(mounts.BATTERY_ADHESIVE_REGIONS)
            + len(mounts.RADIO_ADHESIVE_REGIONS)
            + len(mounts.GPS_ADHESIVE_REGIONS),
        )
        self.assertTrue(report["passed"])
        for row in report["patches"]:
            with self.subTest(allocation=row["allocation"]):
                defect = Part.makeCylinder(
                    0.2,
                    mounts.DECK_THICKNESS,
                    App.Vector(*row["centre_xy_mm"], mounts.DECK_BOTTOM_Z),
                )
                changed = carrier_contact_patch_checks(
                    original.cut(defect), **arguments
                )
                selected = next(
                    x
                    for x in changed["patches"]
                    if x["allocation"] == row["allocation"]
                )
                self.assertFalse(selected["passed"])
                self.assertGreater(
                    selected["missing_full_thickness_material_mm3"], 0.01
                )
                self.assertFalse(changed["passed"])

    def test_slot_volumes_match_capsule_and_rounded_arc_formulae(self):
        from gondola.parts import mounting_slots

        rows = mounting_slots.rows()
        self.assertEqual(len(rows), 24)
        self.assertEqual(len({row["name"] for row in rows}), len(rows))
        self.assertEqual(sum(row["kind"] == "straight" for row in rows), 20)
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

        original = mounting_plate.shape()
        self.assertTrue(original.isValid())
        self.assertEqual(len(original.Solids), 1)
        self.assertTrue(
            carrier_opening_checks(original, centre_hole_diameter=2.6)["passed"]
        )
        specs = [
            next(row for row in mounting_slots.rows() if row["family"] == family)
            for family in ("square16_23", "square40_45", "square30_5", "side")
        ]
        specs.append(
            next(row for row in mounting_slots.rows() if row["name"] == "side_0_middle")
        )
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
            report = carrier_opening_checks(blocked, centre_hole_diameter=2.6)
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
            report = carrier_opening_checks(damaged, centre_hole_diameter=2.6)
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
            sum(size[0] * size[1] for _, size in mounts.BATTERY_ADHESIVE_REGIONS), 328
        )
        support = mounts.mount_shape("accessory")
        body = equipment_envelopes.radio_envelope_shape()
        self.assertEqual(
            sum(size[0] * size[1] for _, size in mounts.RADIO_ADHESIVE_REGIONS), 120
        )
        for centre, size in mounts.RADIO_ADHESIVE_REGIONS:
            with self.subTest(patch=centre):
                notch = Part.makeCylinder(
                    0.2,
                    mounts.DECK_THICKNESS,
                    App.Vector(*centre, mounts.DECK_BOTTOM_Z),
                )
                damaged = support.cut(notch)
                report = adhesive_support_check(
                    damaged, body, centre, size, face="bottom"
                )
                self.assertFalse(report["passed"])

    def test_both_gps_strips_preserve_area_and_full_backing_under_each_alternative(
        self,
    ):
        from gondola.contracts.equipment_options import NAVIGATION_PROFILES
        from gondola.parts import equipment_envelopes
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment_options import adhesive_support_check

        self.assertEqual(
            mounts.GPS_ADHESIVE_REGIONS,
            (((0.0, -6.5), (12.0, 5.0)), ((0.0, 6.5), (12.0, 5.0))),
        )
        self.assertEqual(
            sum(size[0] * size[1] for _, size in mounts.GPS_ADHESIVE_REGIONS), 120
        )
        support = mounts.mount_shape("accessory")
        for key in ("MGA01", "MGF10A"):
            body = equipment_envelopes.navigation_envelope_shape(
                NAVIGATION_PROFILES[key]
            )
            for centre, size in mounts.GPS_ADHESIVE_REGIONS:
                with self.subTest(profile=key, patch=centre):
                    self.assertTrue(
                        adhesive_support_check(support, body, centre, size)["passed"]
                    )
                    defect = Part.makeCylinder(
                        0.2, 2, App.Vector(*centre, mounts.DECK_BOTTOM_Z)
                    )
                    self.assertFalse(
                        adhesive_support_check(support.cut(defect), body, centre, size)[
                            "passed"
                        ]
                    )

    def test_void_probe_cannot_omit_part_of_declared_deck_thickness(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import carrier_opening_checks

        shape = mounting_plate.shape()
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
