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
            App.Vector(4, 2, mounts.DECK_BOTTOM_Z),
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

    def test_straight_capsule_volumes_and_joined_path_solids(self):
        from gondola.parts import mounting_slots

        rows = mounting_slots.rows()
        self.assertEqual(len(rows), 36)
        self.assertEqual(len({row["name"] for row in rows}), len(rows))
        self.assertEqual(sum(row["kind"] == "straight" for row in rows), 32)
        self.assertEqual(sum(row["kind"] == "polyline" for row in rows), 4)
        for row in rows:
            for border in (0.0, 1.5):
                radius = row["width_mm"] / 2 + border
                if row["kind"] == "straight":
                    length = math.dist(row["start_xy_mm"], row["end_xy_mm"])
                else:
                    # Corner paths must be one solid; exact constituent capsule
                    # volumes are checked separately below for straight rows.
                    length = None
                shape = mounting_slots.shape(row, 7.0, 2.0, border=border)
                with self.subTest(slot=row["name"], border=border):
                    self.assertTrue(shape.isValid())
                    self.assertEqual(len(shape.Solids), 1)
                    if length is not None:
                        self.assertAlmostEqual(
                            shape.Volume,
                            2 * (2 * radius * length + math.pi * radius**2),
                            places=6,
                        )
                    else:
                        self.assertGreater(shape.Volume, 2 * math.pi * radius**2)
                    self.assertAlmostEqual(shape.BoundBox.ZMin, 7)
                    self.assertAlmostEqual(shape.BoundBox.ZMax, 9)

    def test_central_slots_retain_fastener_backing_and_bench_access(self):
        from gondola.contracts import fasteners
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import mounting_slots, power_mount

        specs = [
            row for row in mounting_slots.rows() if row["family"] == "central_axis"
        ]
        self.assertEqual(len(specs), 4)
        self.assertEqual(
            mounting_slots.contract()["central_axis_opposed_pitch_range_mm"],
            (23.0, 26.8),
        )
        for name, solid, bottom in (
            ("carrier", mounts.mount_shape("battery"), mounts.DECK_BOTTOM_Z),
            ("power", power_mount.platform_shape(), power_mount.DECK_BOTTOM_Z),
        ):
            for spec in specs:
                with self.subTest(part=name, slot=spec["name"]):
                    opening = mounting_slots.shape(spec, bottom, 2)
                    # Continuous full-travel backing of an acceptance head and
                    # a circumscribed nut is checked around the intentional slot.
                    for diameter in (
                        fasteners.SCREW_HEAD_DIAMETER,
                        fasteners.HEX_NUT_AF / math.cos(math.pi / 6),
                    ):
                        footprint = mounting_slots.shape(
                            {**spec, "width_mm": diameter}, bottom, 2
                        ).cut(opening)
                        self.assertLess(footprint.cut(solid).Volume, 1e-6)
                    # The carrier is removed from the rail for bench service;
                    # tools must clear its own feet and the optional portal.
                    for diameter, height, gap in (
                        (fasteners.SCREW_HEAD_DIAMETER, 2.0, 0.0),
                        (4.8, fasteners.HEX_NUT_HEIGHT, 0.0),
                        (6.0, 6.0, 2.0),
                    ):
                        sweep = mounting_slots.shape(
                            {**spec, "width_mm": diameter},
                            bottom - height - gap,
                            height,
                        )
                        self.assertLess(sweep.common(solid).Volume, 1e-6)

    def test_invalid_closed_or_degenerate_slots_are_rejected(self):
        from gondola.parts import mounting_slots

        straight = next(
            row for row in mounting_slots.rows() if row["kind"] == "straight"
        )
        path = next(row for row in mounting_slots.rows() if row["kind"] == "polyline")
        for row in (
            {**straight, "end_xy_mm": straight["start_xy_mm"]},
            {**path, "points_xy_mm": ()},
            {**path, "points_xy_mm": path["points_xy_mm"][:2]},
            {**path, "points_xy_mm": ((0, 0), (0, 0), (1, 0))},
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
            for family in (
                "square16_20",
                "square40_45",
                "rectangle25_30_square30_5",
                "central_axis",
                "side",
            )
        ]
        specs.append(
            next(row for row in mounting_slots.rows() if row["name"] == "side_0_middle")
        )
        for row in specs:
            fraction = 0.413
            points = (
                row["points_xy_mm"][:2]
                if row["kind"] == "polyline"
                else (row["start_xy_mm"], row["end_xy_mm"])
            )
            start = App.Vector(*points[0], 0)
            delta = App.Vector(*points[1], 0) - start
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
            sum(size[0] * size[1] for _, size in mounts.BATTERY_ADHESIVE_REGIONS), 304
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

    def test_optional_payload_axes_and_bearing_faces_use_published_rectangles(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import optional_payload_pattern_checks

        plate = mounting_plate.shape()
        report = optional_payload_pattern_checks(
            plate, bottom=mounts.DECK_BOTTOM_Z, thickness=2
        )
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["axes"]), 16)
        carrier = mounts.mount_shape("electronics")
        for row in report["axes"]:
            # A2mm-tall circular acceptance head under an unloaded rail carrier
            # clears its risers and shoe. This is not installed device clearance.
            head = Part.makeCylinder(
                row["bearing_diameter_mm"] / 2, 2, App.Vector(*row["centre_xy_mm"], 15)
            )
            self.assertLess(head.common(carrier).Volume, 1e-6)
        # Literal published patterns independently catch a mistaken square pitch.
        for px, py in ((58, 49), (49, 58), (25, 30), (30, 25)):
            for x in (-px / 2, px / 2):
                for y in (-py / 2, py / 2):
                    screw = Part.makeCylinder(1.25, 2, App.Vector(x, y, 17))
                    self.assertLess(screw.common(plate).Volume, 1e-6)
        # Filling a screw path and removing a real bearing land are distinct faults.
        plugged = plate.fuse(Part.makeCylinder(0.4, 2, App.Vector(29, 24.5, 17)))
        self.assertFalse(
            optional_payload_pattern_checks(plugged, bottom=17, thickness=2)["passed"]
        )
        notched = plate.cut(Part.makeCylinder(0.2, 2, App.Vector(31.2, 24.5, 17)))
        self.assertFalse(
            optional_payload_pattern_checks(notched, bottom=17, thickness=2)["passed"]
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
