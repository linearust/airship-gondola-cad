"""Native geometry regressions for continuous, explicitly provisional access."""

import json
import unittest
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None


@unittest.skipIf(App is None, "requires FreeCAD's Python runtime")
class WiringReserveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.cad import create_group, set_property
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import (
            equipment_envelopes,
            equipment_mounts,
            optical_mount,
            optical_sensor,
            wiring_reserves,
        )
        from gondola.validation import wiring as wiring_validation

        cls.wiring = wiring_reserves
        cls.audit = wiring_validation
        cls.expected = wiring_reserves.reserve_shapes()
        cls.expected["MTF02PConnectorReserve"] = (
            optical_sensor.connector_reserve_shape()
        )
        cls.doc = App.newDocument("WiringClearanceRegression")
        battery = create_group(cls.doc, "BatteryEquipmentModule", "Battery")
        electronics = create_group(cls.doc, "ElectronicsEquipmentModule", "Electronics")
        accessory = create_group(cls.doc, "AccessoryEquipmentModule", "Accessories")
        for station in MODULE_STATIONS:
            group = cls.doc.getObject(station.object_name)
            if group is not None:
                group.Placement = App.Placement(
                    App.Vector(station.x_mm, 0, 0),
                    App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
                )
        carrier = equipment_mounts.build_mount(cls.doc, electronics, "electronics")
        accessory_carrier = equipment_mounts.build_mount(
            cls.doc, accessory, "accessory"
        )
        refs, reserves = equipment_envelopes.build_equipment(
            cls.doc, battery, electronics, accessory
        )
        optical = optical_mount.build_optical_mount(cls.doc, battery)
        sensor_refs, sensor_reserves = optical_sensor.build_sensor(
            cls.doc, optical["pitch_stage"]
        )
        refs += sensor_refs
        reserves += sensor_reserves
        registry = cls.doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        for name, value in {
            "PrintedParts": [carrier, accessory_carrier] + optical["printed"],
            "HardwareParts": optical["hardware"],
            "ReferenceParts": refs,
            "ClearanceVolumes": reserves,
            "TapeReferences": [],
        }.items():
            set_property(registry, name, value, "App::PropertyLinkListGlobal")
        cls.doc.recompute()
        cls.reserve_names = tuple(cls.expected) + (
            "MTF02POpticalClearanceReserve",
            "CapacitorServiceReserve",
        )

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def saved_reserve_results(self):
        from gondola.validation import propulsion_wiring

        # This fixture contains the equipment carriers. Keep the absent propulsion
        # subsystem outside this unit boundary; its real route geometry and
        # terminal overlap are covered by test_propulsion_wiring and the full
        # saved-assembly validation, without this mock or reduced inventory.
        self.assertIsNone(self.doc.getObject("MainPropulsionModule"))
        with (
            patch.object(self.audit, "RESERVES", self.reserve_names),
            patch.object(
                propulsion_wiring, "check", return_value={"routes": []}
            ) as routes,
        ):
            result = self.audit.reserve_checks(self.doc)
        routes.assert_called_once_with(self.doc)
        return result

    def test_nominal_reservations_are_connected_and_clear(self):
        checks, pairs = self.saved_reserve_results()
        self.assertEqual(len(checks), 8)
        self.assertTrue(all(row["passed"] for row in checks), checks)
        self.assertTrue(all(row["passed"] for row in pairs), pairs)
        contracts = json.loads(json.dumps(self.wiring.reserve_contracts()))
        self.assertEqual(
            set(contracts), set(self.expected) - {"MTF02PConnectorReserve"}
        )
        for contract in contracts.values():
            self.assertFalse(contract["installed_connector_fit_verified"])
            self.assertFalse(contract["wire_bend_radius_qualified"])
            self.assertFalse(contract["complete_connected_harness_modeled"])

    def test_navigation_and_radio_reservations_belong_to_accessory_carrier(self):
        accessory_names = (
            "PASConnectorReserve",
            "RadioNegativeXConnectorReserve",
            "RadioPositiveXConnectorReserve",
            "NavigationDirectAntennaReserve",
        )
        for name in accessory_names:
            self.assertEqual(self.wiring.parent_name(name), "AccessoryEquipmentModule")
        for name in self.wiring.reserve_shapes():
            parent = self.doc.getObject(self.wiring.parent_name(name))
            self.assertIn(self.doc.getObject(name), parent.Group)
        for name in (
            "FCWiringClearanceReserve",
            "XT30ServiceReserve",
            "CapacitorServiceReserve",
        ):
            self.assertEqual(
                self.wiring.parent_name(name), "ElectronicsEquipmentModule"
            )

    def test_unknown_reservation_cannot_silently_use_the_fc_frame(self):
        for name in (
            "FCWiringClearanceReserv",
            "LR900NegativeXConnectorReserve",
            "",
            None,
            [],
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.wiring.parent_name(name)

    def test_radio_body_and_connector_lanes_use_the_same_underside_face(self):
        from gondola.parts import equipment_envelopes, equipment_mounts

        body = equipment_envelopes.radio_envelope_shape()
        expected_top = (
            equipment_mounts.DECK_BOTTOM_Z - equipment_mounts.ADHESIVE_ALLOWANCE
        )
        self.assertAlmostEqual(body.BoundBox.ZMax, expected_top)
        self.assertAlmostEqual(
            body.BoundBox.YMin, equipment_mounts.RADIO_CENTRE_XY[1] - 24.0 / 2
        )
        self.assertAlmostEqual(
            body.BoundBox.YMax, equipment_mounts.RADIO_CENTRE_XY[1] + 24.0 / 2
        )
        for name in (
            "RadioNegativeXConnectorReserve",
            "RadioPositiveXConnectorReserve",
        ):
            lane = self.expected[name]
            with self.subTest(lane=name):
                self.assertAlmostEqual(lane.BoundBox.ZMax, expected_top)
                self.assertLess(lane.BoundBox.ZMin, body.BoundBox.ZMin)
                self.assertLess(lane.common(body).Volume, 1e-6)
                self.assertLess(
                    lane.common(equipment_mounts.mount_shape("accessory")).Volume,
                    1e-6,
                )

    def test_reparented_reserve_is_rejected_even_when_world_geometry_is_unchanged(self):
        from gondola.cad import world_shape
        from gondola.print_export import geometry_comparison

        for name in (
            "FCWiringClearanceReserve",
            "XT30ServiceReserve",
            "CapacitorServiceReserve",
            "RadioNegativeXConnectorReserve",
            "MTF02PConnectorReserve",
        ):
            obj = self.doc.getObject(name)
            original_parent = obj.getParentGeoFeatureGroup()
            original_placement = App.Placement(obj.Placement)
            global_placement = obj.getGlobalPlacement()
            original_shape = world_shape(obj)
            wrong_parent = (
                self.doc.AccessoryEquipmentModule
                if original_parent != self.doc.AccessoryEquipmentModule
                else self.doc.ElectronicsEquipmentModule
            )
            with self.subTest(reserve=name):
                try:
                    wrong_parent.addObject(obj)
                    obj.Placement = (
                        wrong_parent.getGlobalPlacement()
                        .inverse()
                        .multiply(global_placement)
                    )
                    self.doc.recompute()
                    comparison = geometry_comparison(world_shape(obj), original_shape)
                    self.assertLess(comparison["difference_mm3"], 1e-6)
                    self.assertLess(comparison["bounds_difference_mm"], 1e-6)
                    checks, _ = self.saved_reserve_results()
                    result = next(row for row in checks if row["object"] == name)
                    self.assertFalse(result["parent_matches"])
                    self.assertEqual(result["expected_parent"], original_parent.Name)
                    self.assertEqual(result["actual_parent"], wrong_parent.Name)
                    if name in self.expected:
                        self.assertTrue(result["connector_geometry"]["passed"])
                    self.assertFalse(result["passed"])
                finally:
                    original_parent.addObject(obj)
                    obj.Placement = original_placement
                    self.doc.recompute()

    def test_missing_and_shortened_lane_are_rejected(self):
        expected = self.expected["MTF02PConnectorReserve"]
        self.assertFalse(
            self.audit.connector_reserve_geometry_check(None, expected, {})["passed"]
        )
        bounds = expected.BoundBox
        shortened = expected.common(
            Part.makeBox(
                bounds.XLength / 2,
                bounds.YLength,
                bounds.ZLength,
                App.Vector(bounds.XMin, bounds.YMin, bounds.ZMin),
            )
        )
        self.assertTrue(shortened.isValid())
        result = self.audit.connector_reserve_geometry_check(shortened, expected, {})
        self.assertFalse(result["passed"])
        self.assertGreater(result["source_comparison"]["difference_mm3"], 100)

    def test_middle_obstruction_fails_even_when_both_endpoints_are_clear(self):
        lane = self.expected["MTF02PConnectorReserve"]
        bounds = lane.BoundBox
        blocker = Part.makeBox(
            0.4,
            2,
            2,
            App.Vector(bounds.Center.x - 0.2, bounds.Center.y - 1, bounds.Center.z - 1),
        )
        for x in (bounds.XMin + 0.5, bounds.XMax - 0.5):
            endpoint = Part.makeSphere(
                0.4, App.Vector(x, bounds.Center.y, bounds.Center.z)
            )
            self.assertLess(endpoint.common(blocker).Volume, 1e-6)
        result = self.audit.connector_reserve_geometry_check(
            lane, lane, {"UnmodeledPlugAcrossMiddle": blocker}
        )
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["continuous_reserved_space_collisions"]), 1)

    def test_disconnected_fc_reservation_is_rejected(self):
        expected = self.expected["FCWiringClearanceReserve"]
        bounds = expected.BoundBox
        severed = expected.cut(
            Part.makeBox(
                1,
                bounds.YLength + 2,
                bounds.ZLength + 2,
                App.Vector(-0.5, bounds.YMin - 1, bounds.ZMin - 1),
            )
        )
        self.assertGreater(len(severed.Solids), 1)
        result = self.audit.connector_reserve_geometry_check(severed, expected, {})
        self.assertFalse(result["one_connected_solid"])
        self.assertFalse(result["passed"])

    def test_named_gap_rejects_clear_but_cramped_geometry(self):
        source = Part.makeBox(2, 2, 2)
        requirements = {"FC": {"Optical": 1.5}}
        for gap, expected in ((0.5, False), (1.5, True), (2.0, True)):
            with self.subTest(gap=gap):
                other = Part.makeBox(2, 2, 2, App.Vector(2 + gap, 0, 0))
                self.assertLess(source.common(other).Volume, 1e-6)
                result = self.audit.named_gap_checks(
                    {"FC": source, "Optical": other}, requirements
                )[0]
                self.assertAlmostEqual(result["measured_gap_mm"], gap)
                self.assertEqual(result["passed"], expected)

    def test_missing_non_solid_or_nested_geometry_cannot_pass_clearance(self):
        source = Part.makeBox(4, 4, 4)
        validation_cache = {}
        invalid = (None, Part.Shape(), Part.makeLine(App.Vector(), App.Vector(1, 0, 0)))
        for other in invalid:
            with self.subTest(other=other):
                result = self.audit.named_gap_checks(
                    {"FC": source, "Cable": other},
                    {"FC": {"Cable": 1.5}},
                    validation_cache=validation_cache,
                )[0]
                self.assertFalse(result["passed"])
                self.assertIn("error", result)
        contained = Part.makeSphere(0.25, App.Vector(2, 2, 2))
        result = self.audit.measure_clearances(
            source, {"ContainedCable": contained}, validation_cache=validation_cache
        )[0]
        self.assertFalse(result["passed"])
        self.assertGreater(result["intersection_mm3"], 0.06)
        clear = Part.makeBox(1, 1, 1, App.Vector(6, 0, 0))
        self.assertTrue(
            self.audit.named_gap_checks(
                {"FC": source, "Cable": clear},
                {"FC": {"Cable": 1.5}},
                validation_cache=validation_cache,
            )[0]["passed"]
        )

    def test_required_reserve_removed_from_registry_is_rejected(self):
        registry = self.doc.DesignRegistry
        original = list(registry.ClearanceVolumes)
        try:
            registry.ClearanceVolumes = [
                obj for obj in original if obj.Name != "CapacitorServiceReserve"
            ]
            checks, pairs = self.saved_reserve_results()
            self.assertFalse(
                next(
                    row for row in checks if row["object"] == "CapacitorServiceReserve"
                )["passed"]
            )
            self.assertTrue(
                any(
                    not row["passed"]
                    for row in pairs
                    if "CapacitorServiceReserve" in (row["a"], row["b"])
                )
            )
        finally:
            registry.ClearanceVolumes = original

    def test_native_contract_and_unverified_fit_cannot_be_promoted(self):
        obj = self.doc.MTF02PConnectorReserve
        original_contract = obj.WiringContract
        try:
            contract = json.loads(original_contract)
            contract["installed_connector_fit_verified"] = True
            obj.WiringContract = json.dumps(contract)
            obj.InstalledConnectorFitVerified = True
            rows, _ = self.saved_reserve_results()
            result = next(row for row in rows if row["object"] == obj.Name)
            self.assertFalse(result["native_wiring_contract_matches"])
            self.assertFalse(result["installed_connector_fit_remains_unverified"])
            self.assertFalse(result["passed"])
        finally:
            obj.WiringContract = original_contract
            obj.InstalledConnectorFitVerified = False

    def test_fc_reserve_contains_complete_core_and_both_continuous_turns(self):
        fc = self.expected["FCWiringClearanceReserve"]
        self.assertLess(self.wiring.fc_underbody_reserve_shape().cut(fc).Volume, 1e-6)
        # Independently check endpoint and middle sections of both selected
        # turn paths; the generated whole union must remain one solid.
        # Probe halfway through the required 8 mm space below the actual FC
        # envelope, rather than retaining an obsolete absolute deck elevation.
        section_z = self.doc.ModuleFCEnvelope.Shape.BoundBox.ZMin - 4.0
        for side in (-1, 1):
            turn_y = 14 if side < 0 else 4
            section = Part.makeSphere(1.4, App.Vector(-side * 29, -turn_y, section_z))
            self.assertLess(section.cut(fc).Volume, 1e-6)
        self.assertEqual(len(fc.Solids), 1)

    def test_xt30_is_beside_fc_with_continuous_fore_aft_access(self):
        reserve = self.expected["XT30ServiceReserve"]
        bounds = reserve.BoundBox
        self.assertAlmostEqual(bounds.Center.x, 0)
        self.assertAlmostEqual(bounds.Center.y, -49)
        self.assertAlmostEqual(bounds.XLength, 42)
        self.assertAlmostEqual(bounds.YLength, 10)
        self.assertAlmostEqual(bounds.ZLength, 15)
        self.assertEqual(
            self.wiring.reserve_contracts()["XT30ServiceReserve"][
                "selected_mating_axis"
            ],
            "X",
        )


@unittest.skipIf(App is None, "requires FreeCAD's Python runtime")
class RailOpticalWiringGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.cad import set_property
        from gondola.contracts import optical_attachment
        from gondola.parts import (
            equipment_envelopes,
            equipment_mounts,
            optical_mount,
            optical_sensor,
            rail,
            wiring_reserves,
        )

        cls.doc = App.newDocument("RailOpticalWiringGapRegression")
        parents = []
        for name, x, yaw in (
            ("BatteryEquipmentModule", 84, 0),
            ("ElectronicsEquipmentModule", -56, 180),
            ("AccessoryEquipmentModule", -140, 180),
        ):
            group = cls.doc.addObject("App::Part", name)
            group.Placement = App.Placement(
                App.Vector(x, 0, 0), App.Rotation(App.Vector(0, 0, 1), yaw)
            )
            parents.append(group)
        printed = [
            equipment_mounts.build_mount(cls.doc, parent, kind)
            for parent, kind in zip(parents, ("battery", "electronics", "accessory"))
        ]
        # A rail-mode rebuild emits its native wiring contract from the selected
        # mode. The audit below must independently read that saved mode.
        with patch.object(optical_attachment, "SELECTED_MOUNT", "rail"):
            refs, reserves = equipment_envelopes.build_equipment(cls.doc, *parents)
        optical = optical_mount.build_optical_mount(cls.doc, mode="rail")
        optical["group"].Placement = App.Placement(
            App.Vector(140, 0, 0), App.Rotation(App.Vector(0, 0, 1), 180)
        )
        sensor_refs, sensor_reserves = optical_sensor.build_sensor(
            cls.doc, optical["pitch_stage"]
        )
        built_rail = rail.build_rail(cls.doc)
        locks = rail.build_attachment_hardware(
            cls.doc, optical["group"], "OpticalFlowModule"
        )
        registry = cls.doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        for name, values in {
            "PrintedParts": printed + optical["printed"] + built_rail["printed"],
            "HardwareParts": locks,
            "ReferenceParts": refs + sensor_refs,
            "ClearanceVolumes": reserves + sensor_reserves,
            "TapeReferences": built_rail["tapes"],
        }.items():
            set_property(registry, name, values, "App::PropertyLinkListGlobal")
        cls.reserve_names = tuple(wiring_reserves.reserve_shapes()) + (
            "MTF02PConnectorReserve",
            "MTF02POpticalClearanceReserve",
            "CapacitorServiceReserve",
        )
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def fc_result(self):
        from gondola.validation import propulsion_wiring, wiring

        self.assertIsNone(self.doc.getObject("MainPropulsionModule"))
        with (
            patch.object(wiring, "RESERVES", self.reserve_names),
            patch.object(propulsion_wiring, "check", return_value={"routes": []}),
        ):
            rows, _ = wiring.reserve_checks(self.doc)
        return next(row for row in rows if row["object"] == "FCWiringClearanceReserve")

    def test_saved_rail_contract_requires_actual_tray_with_unchanged_gap(self):
        from gondola.parts import wiring_reserves

        self.assertIsNone(self.doc.getObject("OpticalMountBase"))
        row = self.fc_result()
        self.assertTrue(row["passed"], row)
        self.assertTrue(row["native_wiring_contract_matches"])
        gaps = row["neighbour_clearance_buffers"]
        self.assertEqual(len(gaps), 6)
        self.assertIn("OpticalSensorTray", {item["object"] for item in gaps})
        self.assertNotIn("OpticalMountBase", {item["object"] for item in gaps})
        for mode, target, absent in (
            ("carrier", "OpticalMountBase", "OpticalSensorTray"),
            ("rail", "OpticalSensorTray", "OpticalMountBase"),
        ):
            expected = {
                "ModuleRadioEnvelope": 2.0,
                "ModulePASEnvelope": 2.0,
                "XT30ServiceReserve": 2.0,
                "MTF02POpticalClearanceReserve": 1.5,
                target: 1.5,
                "CapacitorServiceReserve": 1.5,
            }
            actual = wiring_reserves.neighbour_gap_pairs(mode)[
                "FCWiringClearanceReserve"
            ]
            self.assertEqual(actual, expected)
            self.assertNotIn(absent, actual)
            self.assertEqual(
                wiring_reserves.reserve_contracts(optical_mode=mode)[
                    "FCWiringClearanceReserve"
                ]["minimum_neighbour_gaps_mm"],
                expected,
            )

    def test_missing_rail_tray_cannot_pass_as_an_inapplicable_base(self):
        registry = self.doc.DesignRegistry
        original = list(registry.PrintedParts)
        try:
            registry.PrintedParts = [
                obj for obj in original if obj.Name != "OpticalSensorTray"
            ]
            row = self.fc_result()
            self.assertFalse(row["passed"])
            tray = next(
                item
                for item in row["neighbour_clearance_buffers"]
                if item["object"] == "OpticalSensorTray"
            )
            self.assertFalse(tray["passed"])
            self.assertEqual(tray["error"], "missing solid shape")
        finally:
            registry.PrintedParts = original

    def test_clear_but_cramped_rail_tray_and_stale_base_metadata_are_rejected(self):
        from gondola.parts import wiring_reserves
        from gondola.validation.wiring import named_gap_checks

        source = Part.makeBox(2, 2, 2)
        requirements = wiring_reserves.neighbour_gap_pairs("rail")
        shapes = {
            "FCWiringClearanceReserve": source,
            **{
                name: Part.makeBox(1, 1, 1, App.Vector(10, 0, 0))
                for name in requirements["FCWiringClearanceReserve"]
            },
        }
        for gap, passed in ((1.49, False), (1.5, True)):
            shapes["OpticalSensorTray"] = Part.makeBox(
                1, 1, 1, App.Vector(2 + gap, 0, 0)
            )
            row = next(
                item
                for item in named_gap_checks(shapes, requirements)
                if item["object"] == "OpticalSensorTray"
            )
            self.assertEqual(row["passed"], passed)
        obj = self.doc.FCWiringClearanceReserve
        original = obj.WiringContract
        try:
            obj.WiringContract = json.dumps(
                wiring_reserves.reserve_contracts(optical_mode="carrier")[obj.Name]
            )
            row = self.fc_result()
            self.assertFalse(row["native_wiring_contract_matches"])
            self.assertFalse(row["passed"])
        finally:
            obj.WiringContract = original


if __name__ == "__main__":
    unittest.main()
