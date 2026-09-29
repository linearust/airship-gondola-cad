"""Identical carriers with audited openings, contact pads and device axes."""

import json
import math
import unittest

try:
    import FreeCAD as App
    import Part

    from gondola.parts import mounting_plate
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class EquipmentMountShapeTests(unittest.TestCase):
    def test_all_carriers_clear_the_rail_in_both_clamped_lateral_poses(self):
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import rail
        from gondola.validation.geometry import intersection_volume

        stations = {station.object_name: station for station in MODULE_STATIONS}
        rail_shape = rail.rail_shape()
        for kind, name in (
            ("battery", "BatteryEquipmentModule"),
            ("electronics", "ElectronicsEquipmentModule"),
            ("accessory", "AccessoryEquipmentModule"),
        ):
            station = stations[name]
            for side in (-1, 1):
                pose = App.Placement(
                    App.Vector(station.x_mm, side * rail.CLAMP_SHIFT_Y, 0),
                    App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
                )
                body = mounts.mount_shape(kind).copy()
                body.Placement = pose.multiply(body.Placement)
                with self.subTest(kind=kind, clamped_side=side):
                    self.assertLess(intersection_volume(body, rail_shape), 1e-6)
        # The accessory plate is above the rail and supported by its integral shoe.
        local = mounts.mount_shape("accessory")
        plate = local.common(
            Part.makeBox(
                20,
                10,
                mounts.DECK_THICKNESS + 0.2,
                App.Vector(10, -5, mounts.DECK_BOTTOM_Z - 0.1),
            )
        )
        self.assertAlmostEqual(plate.BoundBox.ZMin, mounts.DECK_BOTTOM_Z)
        self.assertGreaterEqual(plate.BoundBox.ZMin - rail.HEAD_TOP, 1.8 - 1e-6)

    def test_every_carrier_is_the_same_single_solid_without_projecting_tabs(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.print_export import geometry_comparison

        reference = mounts.mount_shape("battery")
        for kind in mounts.MOUNT_NAMES:
            shape = mounts.mount_shape(kind)
            with self.subTest(kind=kind):
                self.assertTrue(shape.isValid())
                self.assertEqual(len(shape.Solids), 1)
                comparison = geometry_comparison(shape, reference)
                self.assertLess(comparison["difference_mm3"], 1e-6)
                self.assertLess(comparison["bounds_difference_mm"], 1e-6)
                self.assertEqual(
                    mounts.mount_contract(kind)["shared_print_sku"],
                    "UniversalEquipmentCarrier",
                )
                self.assertEqual(
                    mounts.mount_contract(kind)["stack_interface"][
                        "carrier_datum_xy_mm"
                    ],
                    (0.0, 0.0),
                )
                for centre, size in mounts.BATTERY_ADHESIVE_REGIONS:
                    contact = Part.makeBox(
                        *size,
                        mounts.DECK_THICKNESS,
                        App.Vector(
                            centre[0] - size[0] / 2,
                            centre[1] - size[1] / 2,
                            mounts.DECK_BOTTOM_Z,
                        ),
                    )
                    self.assertLess(abs(contact.cut(shape).Volume), 1e-6)
                self.assertAlmostEqual(shape.BoundBox.XMin, -32)
                self.assertAlmostEqual(shape.BoundBox.XMax, 32)
                self.assertAlmostEqual(shape.BoundBox.YMin, -32)
                self.assertAlmostEqual(shape.BoundBox.YMax, 32)

    def test_plate_outline_is_centred_rounded_and_half_turn_symmetric(self):
        from gondola.parts import equipment_mounts as mounts

        # Fill through openings to inspect the outline; a separate audit also
        # checks the complete pattern, including every physical opening.
        plate = mounting_plate.shape()
        for hole in mounting_plate.cutters(mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS):
            plate = plate.fuse(hole)
        bounds = plate.BoundBox
        self.assertAlmostEqual(bounds.XLength, 64)
        self.assertAlmostEqual(bounds.YLength, 64)
        self.assertAlmostEqual(bounds.Center.x, 0)
        self.assertAlmostEqual(bounds.Center.y, 0)
        rotated = plate.copy()
        rotated.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
        self.assertLess(abs(rotated.cut(plate).Volume), 1e-6)
        for x in (-1, 1):
            for y in (-1, 1):
                self.assertFalse(
                    plate.isInside(
                        App.Vector(x * 31.8, y * 31.8, mounts.DECK_BOTTOM_Z + 1),
                        1e-6,
                        True,
                    )
                )
                self.assertTrue(
                    plate.isInside(
                        App.Vector(x * 29, y * 31, mounts.DECK_BOTTOM_Z + 1),
                        1e-6,
                        True,
                    )
                )

    def test_round_support_has_a_full_section_between_unchanged_shoe_and_deck(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import rail

        # Literal design dimensions keep the witness independent of the builder
        # and reject a hollow, necked or incomplete support anywhere in its height.
        support = Part.makeCylinder(8.5, 2.6, App.Vector(0, 0, 10.8))
        support_band = Part.makeBox(64, 64, 2.6, App.Vector(-32, -32, 10.8))
        shoe_band = Part.makeBox(64, 64, 10.8, App.Vector(-32, -32, 0))
        for kind in mounts.MOUNT_NAMES:
            shape = mounts.mount_shape(kind)
            with self.subTest(kind=kind):
                actual = shape.common(support_band)
                self.assertLess(abs(support.cut(actual).Volume), 1e-6)
                self.assertLess(abs(actual.cut(support).Volume), 1e-6)
                shoe = shape.common(shoe_band)
                self.assertLess(abs(shoe.cut(rail.shoe_shape()).Volume), 1e-6)
                self.assertLess(abs(rail.shoe_shape().cut(shoe).Volume), 1e-6)
        contract = mounts.common_plate_contract()["central_support"]
        self.assertEqual(contract["profile"], "solid cylinder")
        self.assertEqual(contract["diameter_mm"], 17.0)
        self.assertAlmostEqual(contract["height_mm"], 2.6)
        self.assertEqual(contract["z_range_mm"], (10.8, 13.4))

    def test_carrier_keeps_continuous_nut_loading_and_clamp_release_open(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import rail
        from gondola.validation.geometry import translation_sweep

        carrier = mounts.mount_shape("battery")
        # Fill the nut bore for an exact planar sweep containing the whole nut.
        nut = rail.hex_along_y(
            rail.NUT_AF,
            rail.NUT_POCKET_Y + rail.NUT_POCKET_DEPTH - rail.NUT_THICKNESS,
            rail.NUT_THICKNESS,
        )
        for side in (-1, 1):
            transform = rail.half_turn if side < 0 else lambda shape: shape
            for hardware, travel in (
                (nut, (side * 24, 0, 0)),
                (rail.clamp_screw_shape(), (0, side * rail.RELEASE_TRAVEL, 0)),
            ):
                with self.subTest(side=side, travel=travel):
                    sweep, method = translation_sweep(transform(hardware), travel)
                    self.assertIn("face-prism", method)
                    self.assertLess(abs(sweep.common(carrier).Volume), 1e-6)

    def test_all_roles_keep_a_full_common_deck_and_all_shared_holes(self):
        from gondola.parts import equipment_mounts as mounts

        self.assertEqual(mounts.COMMON_DECK_SIZE, (64.0, 64.0))
        self.assertEqual(len(mounting_plate.cutters(0, 2)), 28)
        plate = mounting_plate.shape()
        for kind in mounts.MOUNT_NAMES:
            carrier_deck = mounts.mount_shape(kind).common(
                Part.makeBox(
                    66,
                    66,
                    mounts.DECK_THICKNESS,
                    App.Vector(-33, -33, mounts.DECK_BOTTOM_Z),
                )
            )
            self.assertLess(abs(plate.cut(carrier_deck).Volume), 1e-6)
            self.assertLess(abs(carrier_deck.cut(plate).Volume), 1e-6)
        self.assertEqual(mounts.mount_hole_centres("battery"), ())
        self.assertEqual(
            mounts.mount_hole_centres("electronics"), mounts.FC_HOLE_CENTRES
        )
        self.assertEqual(
            mounts.mount_hole_centres("accessory"), mounts.PAS_HOLE_CENTRES
        )

    def test_standard_slots_have_open_paths_and_full_continuous_lands(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import rail

        for kind in mounts.MOUNT_NAMES:
            shape = mounts.mount_shape(kind)
            slots = mounts.standard_slot_shapes(
                kind, mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS
            ) + mounts.expansion_slot_shapes(
                mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS
            )
            lands = mounts.standard_slot_shapes(
                kind, mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS, border=1.5
            ) + mounts.expansion_slot_shapes(
                mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS, border=1.5
            )
            for slot, outer in zip(slots, lands, strict=True):
                with self.subTest(kind=kind, centre=slot.BoundBox.Center):
                    self.assertLess(abs(slot.common(shape).Volume), 1e-6)
                    self.assertLess(abs(outer.cut(slot).cut(shape).Volume), 1e-6)
                    self.assertLess(abs(slot.common(rail.shoe_shape()).Volume), 1e-6)

    def test_battery_keeps_three_continuous_adhesive_regions(self):
        from gondola.parts import equipment_mounts as mounts

        for centre, size in mounts.BATTERY_ADHESIVE_REGIONS:
            patch = Part.makeBox(
                *size,
                mounts.DECK_THICKNESS,
                App.Vector(
                    centre[0] - size[0] / 2,
                    centre[1] - size[1] / 2,
                    mounts.DECK_BOTTOM_Z,
                ),
            )
            self.assertLess(abs(patch.cut(mounts.mount_shape("battery")).Volume), 1e-6)

    def test_slots_cover_only_the_declared_square_pitch_and_clocking_ranges(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import mounting_slots

        slot_contract = mounting_slots.contract()
        self.assertEqual(slot_contract["square_pitch_range_mm"], (16.0, 23.0))
        self.assertEqual(slot_contract["square_pitch_range_rotation_deg"], 0.0)
        self.assertEqual(
            slot_contract["outer_diagonal_square_pitch_range_mm"], (40.0, 45.0)
        )
        self.assertEqual(slot_contract["square30_5_pitch_mm"], 30.5)
        self.assertEqual(slot_contract["square30_5_rotation_range_deg"], (-15.0, 15.0))
        self.assertFalse(slot_contract["x500_drop_in_compatible"])
        shape = mounts.mount_shape("electronics")
        # Interior values accompany end positions. Exact continuous openings and
        # lands are audited separately; this is not a sampled full-range proof.
        patterns = [(pitch, 0, 2.6) for pitch in (16.0, 20.0, 21.37, 23.0)]
        patterns += [(pitch, 0, 2.6) for pitch in (40.0, 42.6, 45.0)]
        patterns += [(30.5, turn, 3.6) for turn in (-15.0, -4.7, 0.0, 15.0)]
        for pitch, turn, diameter in patterns:
            for index in range(4):
                angle = math.radians(45 + turn + index * 90)
                radius = pitch / math.sqrt(2)
                probe = Part.makeCylinder(
                    diameter / 2,
                    mounts.DECK_THICKNESS,
                    App.Vector(
                        radius * math.cos(angle),
                        radius * math.sin(angle),
                        mounts.DECK_BOTTOM_Z,
                    ),
                )
                with self.subTest(pitch=pitch, turn=turn, corner=index):
                    self.assertLess(probe.common(shape).Volume, 1e-6)
        for kind in mounts.MOUNT_NAMES:
            self.assertNotIn("generic_fastening", mounts.mount_contract(kind))
            contract = mounts.common_plate_contract()
            self.assertEqual(contract["fixed_bore_count"], 4)
            self.assertEqual(contract["slot_count"], 24)

    def test_m2_slot_screws_clear_shoe_and_rail_over_the_whole_straight_path(self):
        from gondola.contracts import fasteners
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import mounting_slots, purchased_hardware, rail

        stations = {row.object_name: row for row in MODULE_STATIONS}
        rail_shape = rail.rail_shape()
        for kind in mounts.MOUNT_NAMES:
            station = stations[kind.capitalize() + "EquipmentModule"]
            carrier = mounts.mount_shape(kind)
            # Exclude the intended head-to-deck bearing contact to measure
            # clearance from the actual shoe and its integral riser instead.
            underdeck = carrier.common(
                Part.makeBox(
                    100,
                    100,
                    mounts.DECK_BOTTOM_Z - 1e-5,
                    App.Vector(-50, -50, 0),
                )
            )
            for row in mounting_slots.rows():
                if row["fastener"] != "M2":
                    continue
                self.assertEqual(row["kind"], "straight")
                start = App.Vector(*row["start_xy_mm"], mounts.DECK_BOTTOM_Z)
                end = App.Vector(*row["end_xy_mm"], mounts.DECK_BOTTOM_Z)
                # The transverse sweep of each cylindrical portion is a
                # capsule. Keeping head and shank at their own Z intervals
                # avoids a whole-screw bounding box filling the narrow slot.
                head = mounting_slots.shape(
                    {**row, "width_mm": fasteners.SCREW_HEAD_DIAMETER},
                    mounts.DECK_BOTTOM_Z - fasteners.SCREW_HEAD_HEIGHT,
                    fasteners.SCREW_HEAD_HEIGHT,
                )
                shank = mounting_slots.shape(
                    {**row, "width_mm": fasteners.THREAD_DIAMETER},
                    mounts.DECK_BOTTOM_Z,
                    8,
                )
                sweep = head.fuse(shank)
                for point in (start, end):
                    screw = purchased_hardware.screw_shape(8).copy()
                    screw.translate(point)
                    self.assertLess(screw.cut(sweep).Volume, 1e-6)
                with self.subTest(kind=kind, slot=row["name"]):
                    self.assertLess(sweep.common(carrier).Volume, 1e-6)
                    self.assertGreaterEqual(head.distToShape(underdeck)[0], 0.4)
                for side in (-1, 1):
                    placed = sweep.copy()
                    placed.Placement = App.Placement(
                        App.Vector(station.x_mm, side * rail.CLAMP_SHIFT_Y, 0),
                        App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
                    ).multiply(placed.Placement)
                    with self.subTest(kind=kind, slot=row["name"], approach=side):
                        self.assertGreaterEqual(
                            placed.distToShape(rail_shape)[0], 1.0 - 1e-6
                        )

    def test_shared_adhesive_patches_are_intact_and_clear_pas_holes(self):
        from gondola.parts import equipment_mounts as mounts

        shape = mounts.mount_shape("accessory")
        for centre, size in (
            (mounts.NAVIGATION_CENTRE_XY, mounts.GPS_ADHESIVE_SIZE),
            *mounts.RADIO_ADHESIVE_REGIONS,
        ):
            pad = Part.makeBox(
                *size,
                mounts.DECK_THICKNESS,
                App.Vector(
                    centre[0] - size[0] / 2,
                    centre[1] - size[1] / 2,
                    mounts.DECK_BOTTOM_Z,
                ),
            )
            self.assertLess(abs(pad.cut(shape).Volume), 1e-6)

    def test_underside_radio_requires_the_correct_contact_face_and_adhesive_gap(self):
        from gondola.parts import equipment_envelopes as devices
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment_options import adhesive_support_check

        support = mounts.mount_shape("accessory")
        body = devices.radio_envelope_shape()

        def check(shape, centre, size, face="bottom"):
            return adhesive_support_check(
                support,
                shape,
                centre,
                size,
                face=face,
            )

        for centre, size in mounts.RADIO_ADHESIVE_REGIONS:
            report = check(body, centre, size)
            self.assertTrue(report["passed"], report)
            self.assertTrue(report["body_on_requested_side"])
            self.assertAlmostEqual(report["adhesive_allowance_mm"], 1.0)
            self.assertFalse(check(body, centre, size, "top")["passed"])
            self.assertFalse(check(body, centre, size, "top")["body_on_requested_side"])
            for shift in (0.5, 1.0, 2.0, -1.0):
                with self.subTest(patch=centre, vertical_shift=shift):
                    displaced = body.copy()
                    displaced.translate(App.Vector(0, 0, shift))
                    self.assertFalse(check(displaced, centre, size)["passed"])
        with self.assertRaises(ValueError):
            check(body, *mounts.RADIO_ADHESIVE_REGIONS[0], "underside_typo")

    def test_radio_removal_is_outward_from_the_contact_face(self):
        from gondola.parts import equipment_envelopes as devices
        from gondola.parts import equipment_layout, equipment_mounts
        from gondola.validation.geometry import translation_sweep

        body = devices.radio_envelope_shape()
        support = equipment_mounts.mount_shape("accessory").copy()
        local_travel = equipment_layout.device_removal_vector("ModuleRadioEnvelope")
        self.assertEqual(tuple(local_travel), (0.0, 0.0, -32.0))
        # Check the physical path after arbitrary parent tilt, not only a
        # coincident global Z direction. An upward path must hit the plate.
        placement = App.Placement(
            App.Vector(12, 30, 60), App.Rotation(App.Vector(1, 2, 3), 37)
        )
        for shape in (body, support):
            shape.Placement = placement.multiply(shape.Placement)
        travel = placement.Rotation.multVec(App.Vector(*local_travel))
        sweep, _ = translation_sweep(body, tuple(travel))
        self.assertLess(sweep.common(support).Volume, 1e-6)
        wrong_sweep, _ = translation_sweep(body, tuple(-travel))
        self.assertGreater(wrong_sweep.common(support).Volume, 100)

    def test_radio_keeps_both_rail_clamp_tool_approaches_open(self):
        from gondola.parts import equipment_envelopes as devices
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.rail_access import rail_key_service_check

        body = devices.radio_envelope_shape()
        self.assertEqual(mounts.RADIO_CENTRE_XY, (26.0, -11.0))
        for side in (-1, 1):
            with self.subTest(approach_side=side):
                correct = rail_key_service_check(
                    {"carrier": mounts.mount_shape("accessory"), "radio": body},
                    side=side,
                    inserted_leg="long",
                )
                self.assertTrue(correct["passed"], correct)
                # The earlier +/-Y location blocks whichever clamp approaches
                # from that side. Both ports must remain usable, not just the
                # default port in the saved assembly.
                blocked_body = body.copy()
                blocked_body.Placement = App.Placement(
                    App.Vector(
                        0, side * 26, mounts.DECK_BOTTOM_Z - mounts.ADHESIVE_ALLOWANCE
                    ),
                    App.Rotation(App.Vector(1, 0, 0), 180),
                )
                blocked = rail_key_service_check(
                    {"radio": blocked_body}, side=side, inserted_leg="long"
                )
                self.assertFalse(blocked["passed"])
                self.assertTrue(blocked["collisions"])

    def test_every_carrier_preserves_fc_and_published_pas_hole_patterns(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import mounting_pad_check

        for kind in mounts.MOUNT_NAMES:
            shape = mounts.mount_shape(kind)
            for centre in mounts.COMMON_DEVICE_HOLE_CENTRES:
                check = mounting_pad_check(
                    shape,
                    centre,
                    bottom=mounts.DECK_BOTTOM_Z,
                    thickness=mounts.DECK_THICKNESS,
                    hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
                    pad_diameter=mounts.MOUNT_PAD_DIAMETER,
                )
                self.assertTrue(check["passed"], check)
        for actual, expected in zip(
            mounts.PAS_HOLE_CENTRES, interfaces.PAS_HOLE_CENTRES
        ):
            self.assertAlmostEqual(
                actual[0] - mounts.NAVIGATION_CENTRE_XY[0], expected[0]
            )
            self.assertAlmostEqual(
                actual[1] - mounts.NAVIGATION_CENTRE_XY[1], expected[1]
            )

    def test_side_slots_keep_their_explicit_nonstandard_travel(self):
        from gondola.parts import equipment_mounts as mounts

        rows = mounts.expansion_slot_rows()
        self.assertEqual(len(rows), 12)
        expected = set()
        for axis in (0, 1):
            for side in (-1, 1):
                for interval in (-1, 1):
                    point = [0.0, 0.0]
                    point[axis] = side * 27.0
                    point[1 - axis] = interval * 13.0
                    end = point.copy()
                    end[1 - axis] = interval * 23.0
                    expected.add(tuple(sorted((tuple(point), tuple(end)))))
                point = [0.0, 0.0]
                point[axis] = side * 27.0
                point[1 - axis] = -5.0
                end = point.copy()
                end[1 - axis] = 5.0
                expected.add(tuple(sorted((tuple(point), tuple(end)))))
        actual = {
            tuple(
                sorted(
                    (
                        tuple(round(v, 8) for v in row["start_xy_mm"]),
                        tuple(round(v, 8) for v in row["end_xy_mm"]),
                    )
                )
            )
            for row in rows
        }
        self.assertEqual(actual, expected)
        self.assertTrue(
            all(
                row["kind"] == "straight"
                and row["width_mm"] == 2.6
                and row["fastener"] == "M2"
                for row in rows
            )
        )
        self.assertFalse(mounts.expansion_contract()["industry_standard_claimed"])

    def test_unused_fixed_device_bore_blockage_and_missing_annulus_fail_audit(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import carrier_opening_checks

        original = mounts.mount_shape("battery")
        report = carrier_opening_checks(original)
        self.assertTrue(report["passed"], report)
        self.assertEqual((report["fixed_bore_count"], report["slot_count"]), (4, 24))
        for centre in mounts.FC_HOLE_CENTRES:
            with self.subTest(centre=centre):
                obstruction = Part.makeCylinder(
                    1.5,
                    mounts.DECK_THICKNESS,
                    App.Vector(*centre, mounts.DECK_BOTTOM_Z),
                )
                blocked = carrier_opening_checks(original.fuse(obstruction))
                self.assertFalse(blocked["passed"])
                self.assertTrue(
                    any(
                        row["through_bore_obstruction_mm3"] > 0.1
                        for row in blocked["fixed_device_bores"]
                    )
                )
                notch = Part.makeCylinder(
                    0.2,
                    mounts.DECK_THICKNESS,
                    App.Vector(centre[0] + 2, centre[1], mounts.DECK_BOTTOM_Z),
                )
                missing = carrier_opening_checks(original.cut(notch))
                self.assertFalse(missing["passed"])
                self.assertTrue(
                    any(
                        row["missing_full_thickness_bearing_annulus_mm3"] > 0.01
                        for row in missing["fixed_device_bores"]
                    )
                )


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class FCInstallationTests(unittest.TestCase):
    def setUp(self):
        from gondola.cad import create_group
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts.equipment_envelopes import build_equipment
        from gondola.parts.equipment_mounts import build_mount

        self.doc = App.newDocument("FCInstallationRegression")
        self.addCleanup(App.closeDocument, self.doc.Name)
        groups = {}
        for station in MODULE_STATIONS:
            group = create_group(self.doc, station.object_name, station.object_name)
            group.Placement = App.Placement(
                App.Vector(station.x_mm, 0, 0),
                App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
            )
            groups[station.object_name] = group
        for kind in ("battery", "electronics", "accessory"):
            build_mount(self.doc, groups[kind.capitalize() + "EquipmentModule"], kind)
        build_equipment(
            self.doc,
            groups["BatteryEquipmentModule"],
            groups["ElectronicsEquipmentModule"],
            groups["AccessoryEquipmentModule"],
        )
        self.doc.recompute()

    def test_print_metadata_uses_one_sku_without_claiming_half_turn_symmetry(self):
        from gondola.parts import equipment_mounts as mounts

        for kind, name in mounts.MOUNT_NAMES.items():
            obj = self.doc.getObject(name)
            self.assertEqual(obj.PrintSKU, "UniversalEquipmentCarrier")
            self.assertEqual(obj.MountKind, kind)
            self.assertFalse(obj.HalfTurnSymmetric)
            contract = json.loads(obj.MountContract)
            self.assertEqual(len(contract["physical_device_hole_centres_xy_mm"]), 4)
            self.assertEqual(
                contract["mount_hole_centres_xy_mm"],
                [list(xy) for xy in mounts.mount_hole_centres(kind)],
            )

    def test_both_battery_references_follow_the_same_raised_deck_datum(self):
        from gondola.cad import world_shape
        from gondola.parts import equipment_layout, equipment_mounts

        for name in ("ModuleBatteryEnvelope", "MaximumBatteryEnvelope"):
            obj = self.doc.getObject(name)
            group = obj.getParentGeoFeatureGroup()
            expected = (
                group.getGlobalPlacement()
                .multVec(App.Vector(0, 0, equipment_layout.adhesive_bottom()))
                .z
            )
            self.assertAlmostEqual(world_shape(obj).BoundBox.ZMin, expected)
        self.assertAlmostEqual(
            self.doc.ModuleBatteryEnvelope.BottomZ.Value,
            equipment_mounts.SUPPORT_FACE_Z + equipment_mounts.ADHESIVE_ALLOWANCE,
        )

    def test_native_hole_axis_metadata_follows_shared_support(self):
        from gondola.parts import equipment_mounts as mounts

        centres = mounts.FC_HOLE_CENTRES
        self.assertEqual(
            [
                (point.x, point.y, point.z)
                for point in self.doc.ElectronicsMount.MountHoleCentres
            ],
            [(x, y, mounts.DECK_BOTTOM_Z) for x, y in centres],
        )
        for name, expected in (
            ("ModuleFCEnvelope", mounts.FC_HOLE_CENTRES),
            (
                "ModulePASEnvelope",
                mounts.PAS_HOLE_CENTRES,
            ),
        ):
            with self.subTest(device=name):
                obj = self.doc.getObject(name)
                self.assertEqual(
                    [(point.x, point.y, point.z) for point in obj.VerifiedHoleAxesXY],
                    [(x, y, 0) for x, y in expected],
                )

    def test_native_board_pose_preserves_heading_after_carrier_turn(self):
        from gondola.validation.equipment import fc_installation_check

        result = fc_installation_check(self.doc)
        self.assertTrue(result["passed"], result)

    def test_unchanged_board_shape_cannot_hide_stale_controller_identity(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.validation.baseline import procurement_and_scope_metadata
        from gondola.validation.equipment import fc_installation_check

        board = self.doc.ModuleFCEnvelope
        self.assertIn(interfaces.FC_MODEL, board.Label)
        original = board.Shape.copy()
        contract = json.loads(json.dumps(interfaces.flight_controller_contract()))
        self.assertIn("FlightControllerContract", procurement_and_scope_metadata(board))
        contract["model"] = "MicoAir743v2-AIO-35A"
        board.FlightControllerContract = json.dumps(contract)
        result = fc_installation_check(self.doc)
        self.assertFalse(result["native_flight_controller_contract_matches"])
        self.assertFalse(result["passed"])
        self.assertLess(abs(board.Shape.cut(original).Volume), 1e-6)
        self.assertLess(abs(original.cut(board.Shape).Volume), 1e-6)

    def test_missing_or_malformed_controller_contract_is_rejected(self):
        from gondola.validation.equipment import fc_installation_check

        board = self.doc.ModuleFCEnvelope
        for value in ("{", "null", "[]"):
            with self.subTest(value=value):
                board.FlightControllerContract = value
                self.assertFalse(fc_installation_check(self.doc)["passed"])
        board.removeProperty("FlightControllerContract")
        self.assertFalse(fc_installation_check(self.doc)["passed"])

    def test_controller_firmware_or_input_evidence_cannot_silently_change(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.validation.equipment import fc_installation_check

        for mutation in ("firmware", "input_claim", "compatibility"):
            with self.subTest(mutation=mutation):
                contract = json.loads(
                    json.dumps(interfaces.flight_controller_contract())
                )
                electrical = contract["electrical"]
                if mutation == "firmware":
                    electrical["esc_firmware"] = "Bluejay"
                elif mutation == "input_claim":
                    electrical["input_claims"]["manual_text"]["cells"] = [2, 6]
                else:
                    electrical["compatibility_status"] = "verified"
                self.doc.ModuleFCEnvelope.FlightControllerContract = json.dumps(
                    contract
                )
                result = fc_installation_check(self.doc)
                self.assertFalse(result["native_flight_controller_contract_matches"])
                self.assertFalse(result["passed"])

    def test_symmetric_board_solid_cannot_hide_reversed_installation(self):
        from gondola.cad import world_shape
        from gondola.print_export import geometry_comparison
        from gondola.validation.equipment import fc_installation_check

        board = self.doc.ModuleFCEnvelope
        original = world_shape(board)
        board.Placement.Rotation = App.Rotation(App.Vector(0, 0, 1), -45)
        self.doc.recompute()
        self.assertLess(
            geometry_comparison(world_shape(board), original)["difference_mm3"],
            1e-6,
        )
        result = fc_installation_check(self.doc)
        self.assertFalse(result["native_board_placement_matches"])
        self.assertFalse(result["passed"])

    def test_wrong_parent_turn_or_native_orientation_marker_is_rejected(self):
        from gondola.validation.equipment import fc_installation_check

        self.doc.ModuleFCEnvelope.InstallationYawInCarrier = 0
        self.assertFalse(fc_installation_check(self.doc)["passed"])
        self.doc.ModuleFCEnvelope.InstallationYawInCarrier = 180
        self.doc.ElectronicsEquipmentModule.Placement.Rotation = App.Rotation()
        self.assertFalse(fc_installation_check(self.doc)["passed"])


if __name__ == "__main__":
    unittest.main()
