"""Interchangeable devices share supports without inheriting incompatible holes."""

import json
import unittest
from unittest.mock import patch

from gondola.contracts import equipment_options as options

try:
    import FreeCAD as App
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class EquipmentOptionShapeTests(unittest.TestCase):
    def test_gps_is_supported_over_adhesive_pad_not_offset_pas_hole_row(self):
        from gondola.parts import equipment_envelopes as envelopes
        from gondola.parts import equipment_layout as layout
        from gondola.parts import equipment_mounts as mounts

        pas = options.get_navigation_profile("PAS")
        self.assertEqual(layout.navigation_hole_centres(pas), mounts.PAS_HOLE_CENTRES)
        for key in ("MGA01", "MGF10A"):
            profile = options.get_navigation_profile(key)
            body = envelopes.navigation_envelope_shape(profile)
            self.assertTrue(body.isValid())
            self.assertEqual(len(body.Solids), 1)
            bounds = body.BoundBox
            self.assertAlmostEqual(bounds.Center.x, mounts.GPS_CENTRE_XY[0])
            self.assertAlmostEqual(bounds.Center.y, mounts.GPS_CENTRE_XY[1])
            self.assertEqual(bounds.Center.y, mounts.PAS_CENTRE_XY[1])
            self.assertAlmostEqual(
                bounds.ZMin - mounts.SUPPORT_FACE_Z, mounts.ADHESIVE_ALLOWANCE
            )
            self.assertAlmostEqual(
                body.Volume,
                profile.size_mm[0] * profile.size_mm[1] * profile.size_mm[2],
            )
            self.assertEqual(layout.navigation_hole_centres(profile), ())

    def test_radio_lanes_start_at_selected_body_ends_without_entering_body(self):
        from gondola.parts import equipment_envelopes as envelopes
        from gondola.parts import wiring_reserves as wiring

        for profile in options.RADIO_PROFILES.values():
            with self.subTest(model=profile.key):
                body = envelopes.radio_envelope_shape(profile)
                reserves = wiring.reserve_shapes(radio_profile=profile)
                negative = reserves["RadioNegativeXConnectorReserve"]
                positive = reserves["RadioPositiveXConnectorReserve"]
                for lane in (negative, positive):
                    self.assertLess(abs(lane.common(body).Volume), 1e-7)
                    self.assertAlmostEqual(lane.distToShape(body)[0], 0)
                    self.assertAlmostEqual(
                        lane.BoundBox.YLength,
                        body.BoundBox.YLength + 2 * wiring.CONNECTOR_SIDE_MARGIN_MM,
                    )
                self.assertAlmostEqual(negative.BoundBox.XMax, body.BoundBox.XMin)
                self.assertAlmostEqual(positive.BoundBox.XMin, body.BoundBox.XMax)

    def test_gps_connector_lane_covers_short_edge_and_follows_device_height(self):
        from gondola.parts import equipment_envelopes as envelopes
        from gondola.parts import wiring_reserves as wiring

        for key in ("MGA01", "MGF10A"):
            with self.subTest(model=key):
                profile = options.get_navigation_profile(key)
                body = envelopes.navigation_envelope_shape(profile)
                lane = wiring.reserve_shapes(profile)["PASConnectorReserve"]
                self.assertLess(abs(lane.common(body).Volume), 1e-7)
                self.assertAlmostEqual(lane.BoundBox.YMax, body.BoundBox.YMin)
                self.assertAlmostEqual(lane.BoundBox.ZMin, body.BoundBox.ZMin)
                self.assertAlmostEqual(
                    lane.BoundBox.XLength,
                    body.BoundBox.XLength + 2 * wiring.CONNECTOR_SIDE_MARGIN_MM,
                )

    def test_direct_helix_bounds_all_body_positions_without_adding_another_device(self):
        from gondola.parts import equipment_envelopes as envelopes
        from gondola.parts import wiring_reserves as wiring

        self.assertIsNone(
            wiring.direct_antenna_reserve_shape(options.get_navigation_profile("PAS"))
        )
        profile = options.get_navigation_profile("MGF10A")
        body = envelopes.navigation_envelope_shape(profile)
        antenna = wiring.direct_antenna_reserve_shape(profile)
        self.assertTrue(antenna.isValid())
        self.assertAlmostEqual(antenna.BoundBox.ZMin, body.BoundBox.ZMin)
        self.assertAlmostEqual(antenna.BoundBox.ZLength, body.BoundBox.ZLength + 59.3)
        self.assertLess(abs(body.cut(antenna).Volume), 1e-7)
        for axis in ("X", "Y"):
            self.assertAlmostEqual(
                getattr(antenna.BoundBox, axis + "Length"),
                getattr(body.BoundBox, axis + "Length") + 28,
            )
        self.assertIn("NavigationDirectAntennaReserve", wiring.reserve_shapes(profile))
        self.assertNotIn("NavigationDirectAntennaReserve", wiring.reserve_shapes())

    def test_source_selected_build_changes_slot_identity_without_duplicate_devices(
        self,
    ):
        from gondola.cad import create_group
        from gondola.parts import equipment_envelopes as envelopes

        with (
            patch.object(options, "SELECTED_NAVIGATION_KEY", "MGF10A"),
            patch.object(options, "SELECTED_RADIO_KEY", "LR24FMINI"),
        ):
            doc = App.newDocument("AlternativeEquipmentSlots")
            try:
                battery = create_group(doc, "BatteryEquipmentModule", "Battery")
                electronics = create_group(
                    doc, "ElectronicsEquipmentModule", "Electronics"
                )
                accessory = create_group(doc, "AccessoryEquipmentModule", "Accessory")
                refs, reserves = envelopes.build_equipment(
                    doc, battery, electronics, accessory
                )
                doc.recompute()
                self.assertEqual(len(refs), 4)
                self.assertEqual(doc.ModulePASEnvelope.NavigationModel, "MGF10A")
                self.assertEqual(doc.ModuleRadioEnvelope.RadioModel, "LR24FMINI")
                self.assertEqual(
                    json.loads(doc.ModulePASEnvelope.NavigationProfile)["key"],
                    "MGF10A",
                )
                self.assertEqual(
                    json.loads(doc.ModuleRadioEnvelope.RadioProfile)["key"],
                    "LR24FMINI",
                )
                self.assertNotIn(
                    "PublishedMountHolePitch", doc.ModulePASEnvelope.PropertiesList
                )
                self.assertIn(doc.NavigationDirectAntennaReserve, reserves)
                self.assertNotIn(doc.NavigationDirectAntennaReserve, refs)
                self.assertEqual(
                    doc.ModulePASEnvelope.getParentGeoFeatureGroup(), accessory
                )
                self.assertEqual(
                    doc.ModuleRadioEnvelope.getParentGeoFeatureGroup(), accessory
                )
                self.assertEqual(
                    doc.FCWiringClearanceReserve.getParentGeoFeatureGroup(), electronics
                )
                self.assertEqual(
                    doc.RadioNegativeXConnectorReserve.getParentGeoFeatureGroup(),
                    accessory,
                )
            finally:
                App.closeDocument(doc.Name)
        self.assertEqual(options.get_navigation_profile().key, "PAS")
        self.assertEqual(options.get_radio_profile().key, "LR24FMINI")
