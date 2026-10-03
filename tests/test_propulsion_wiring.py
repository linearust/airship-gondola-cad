"""Reject disconnected, stale, blocked or falsely qualified lead planning space."""

import json
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None


@unittest.skipIf(App is None, "requires FreeCAD's Python runtime")
class PropulsionWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.cad import create_group, create_reference, set_property
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import (
            equipment_envelopes,
            instrument_mount,
            propulsion_wiring,
            wiring_reserves,
        )
        from gondola.validation import propulsion_wiring as audit

        cls.wiring, cls.audit = propulsion_wiring, audit
        cls.doc = App.newDocument("PropulsionWiringRegression")
        cls.propulsion = create_group(cls.doc, "MainPropulsionModule", "Propulsion")
        cls.electronics = create_group(
            cls.doc, "ElectronicsEquipmentModule", "Electronics"
        )
        for group in (cls.propulsion, cls.electronics):
            station = next(
                item for item in MODULE_STATIONS if item.object_name == group.Name
            )
            group.Placement = App.Placement(
                App.Vector(station.x_mm, 0, 0),
                App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
            )
        instrument = instrument_mount.build_mount(cls.doc, cls.electronics)
        cls.stage = instrument["pitch_stage"]
        fc = create_reference(
            cls.doc,
            cls.stage,
            "ModuleFCEnvelope",
            "FC",
            equipment_envelopes.fc_envelope_shape(),
            "Reference",
        )
        cls.fc_reserve = create_reference(
            cls.doc,
            cls.stage,
            "FCWiringClearanceReserve",
            "FC space",
            wiring_reserves.reserve_shapes()["FCWiringClearanceReserve"],
            "Planning only",
        )
        cls.fc_reserve.Role = "Clearance"
        cls.routes = propulsion_wiring.build_reserves(
            cls.doc, cls.propulsion, cls.stage
        )
        registry = cls.doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        for name, items in {
            "PrintedParts": instrument["printed"],
            "HardwareParts": instrument["hardware"],
            "ReferenceParts": [fc],
            "TapeReferences": [],
            "ClearanceVolumes": [cls.fc_reserve] + cls.routes,
        }.items():
            set_property(registry, name, items, "App::PropertyLinkListGlobal")
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def test_connected_both_sides_remain_explicitly_unqualified(self):
        result = self.audit.check(self.doc)
        self.assertTrue(result["passed"], result)
        self.assertFalse(result["moving_wire_sweep_verified"])
        self.assertFalse(result["strain_relief_fit_verified"])
        for row in result["routes"]:
            self.assertGreater(row["fc_terminal_connection"]["connected_volume_mm3"], 1)
            self.assertLess(
                row["fc_terminal_connection"]["overlap_outside_terminal_region_mm3"],
                1e-9,
            )

    def test_route_endpoint_follows_actual_shared_stage_pitch(self):
        from gondola.parts.instrument_mount import set_pitch

        prop = self.propulsion.getGlobalPlacement()
        try:
            for angle in (-20, 0, 20):
                set_pitch(self.doc, angle)
                stage = self.stage.getGlobalPlacement()
                fc_frame = stage.multiply(
                    App.Placement(App.Vector(), App.Rotation(App.Vector(0, 0, 1), 180))
                )
                for sign in (-1, 1):
                    points = self.wiring.route_points(sign, prop, stage)
                    actual = prop.multVec(App.Vector(*points[-1]))
                    expected = fc_frame.multVec(App.Vector(24, sign * 10, 31))
                    self.assertLess((actual - expected).Length, 1e-7)
                    self.assertAlmostEqual(points[1][0] - points[-1][0], 11.0)
                    self.assertAlmostEqual(points[1][2] - points[-1][2], 14.0)
        finally:
            set_pitch(self.doc, 0)

    def test_pitch_change_rejects_saved_route_until_geometry_and_contract_regenerated(
        self,
    ):
        from gondola.parts.instrument_mount import set_pitch

        originals = [(obj, obj.Shape.copy(), obj.WiringContract) for obj in self.routes]
        try:
            set_pitch(self.doc, 20)
            result = self.audit.check(self.doc)
            self.assertFalse(result["passed"])
            self.assertTrue(
                all(not row["layout_geometry_matches"] for row in result["routes"])
            )
            prop = self.propulsion.getGlobalPlacement()
            stage = self.stage.getGlobalPlacement()
            for obj, sign in zip(self.routes, (1, -1)):
                obj.Shape = self.wiring.route_geometry(sign, prop, stage)["shape"]
                obj.WiringContract = json.dumps(
                    self.wiring.route_contract(sign, prop, stage), sort_keys=True
                )
            self.doc.recompute()
            result = self.audit.check(self.doc)
            self.assertTrue(result["passed"], result)
        finally:
            set_pitch(self.doc, 0)
            for obj, shape, contract in originals:
                obj.Shape = shape
                obj.WiringContract = contract
            self.doc.recompute()

    def test_disconnected_route_fails(self):
        route = self.routes[0]
        original = route.Shape
        try:
            points = self.wiring.route_points(
                1,
                self.propulsion.getGlobalPlacement(),
                self.stage.getGlobalPlacement(),
            )
            middle_y = (points[0][1] + points[1][1]) / 2
            route.Shape = original.cut(
                Part.makeBox(100, 1, 100, App.Vector(-80, middle_y - 0.5, 0))
            )
            self.assertGreater(len(route.Shape.Solids), 1)
            self.assertFalse(self.audit.check(self.doc)["passed"])
        finally:
            route.Shape = original

    def test_obstacle_in_middle_is_detected(self):
        from gondola.cad import create_reference

        points = self.wiring.route_points(
            1,
            self.propulsion.getGlobalPlacement(),
            self.stage.getGlobalPlacement(),
        )
        middle = (App.Vector(*points[0]) + App.Vector(*points[1])) / 2
        blocker = create_reference(
            self.doc,
            self.propulsion,
            "TestRouteBlocker",
            "Unmodeled wire obstruction",
            Part.makeBox(2, 4, 4, middle - App.Vector(1, 2, 2)),
            "Test",
        )
        registry = self.doc.DesignRegistry
        original = list(registry.ReferenceParts)
        try:
            registry.ReferenceParts = original + [blocker]
            result = self.audit.check(self.doc)
            self.assertFalse(result["passed"])
            self.assertTrue(
                any(
                    hit["object"] == blocker.Name
                    for row in result["routes"]
                    for hit in row.get("continuous_reserved_space_collisions", [])
                )
            )
        finally:
            registry.ReferenceParts = original
            self.doc.removeObject(blocker.Name)

    def test_electronics_relocation_rejects_stale_route(self):
        original = self.electronics.Placement
        try:
            changed = App.Placement(original)
            changed.Base.x -= 20
            self.electronics.Placement = changed
            self.doc.recompute()
            result = self.audit.check(self.doc)
            self.assertFalse(result["passed"])
            self.assertTrue(
                any(
                    not row.get("layout_geometry_matches", False)
                    for row in result["routes"]
                )
            )
        finally:
            self.electronics.Placement = original
            self.doc.recompute()

    def test_missing_fc_reserve_registry_is_rejected(self):
        registry = self.doc.DesignRegistry
        original = list(registry.ClearanceVolumes)
        try:
            registry.ClearanceVolumes = self.routes
            self.assertFalse(self.audit.check(self.doc)["passed"])
        finally:
            registry.ClearanceVolumes = original

    def test_unverified_dynamic_model_cannot_be_promoted(self):
        route = self.routes[0]
        try:
            route.MovingWireSweepVerified = True
            self.assertFalse(self.audit.check(self.doc)["passed"])
        finally:
            route.MovingWireSweepVerified = False

    def test_common_optical_bracket_and_both_sensor_fields_clear_regenerated_routes(
        self,
    ):
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import optical_interface, optical_mount, optical_sensor
        from gondola.parts.instrument_mount import set_pitch

        prop = self.propulsion.getGlobalPlacement()
        try:
            for angle in (-20, 0, 20):
                set_pitch(self.doc, angle)
                stage = self.stage.getGlobalPlacement()
                pose = stage.multiply(optical_interface.placement())
                obstacles = {"OpticalSensorTray": optical_mount.sensor_tray_shape()}
                for key, profile in SENSOR_PROFILES.items():
                    obstacles[key + "Body"] = optical_sensor.envelope_shape(profile)
                    obstacles[key + "Field"] = optical_sensor.optical_reserve_shape(
                        profile
                    )
                    obstacles[key + "Connector"] = (
                        optical_sensor.connector_reserve_shape(profile)
                    )
                for shape in obstacles.values():
                    shape.Placement = pose.multiply(shape.Placement)
                for sign in (-1, 1):
                    route = self.wiring.route_geometry(sign, prop, stage)["shape"]
                    route.Placement = prop.multiply(route.Placement)
                    for name, obstacle in obstacles.items():
                        with self.subTest(angle=angle, sign=sign, obstacle=name):
                            self.assertLess(abs(route.common(obstacle).Volume), 1e-6)
        finally:
            set_pitch(self.doc, 0)

    def test_remote_fc_crossing_is_not_a_permitted_connection(self):
        a = Part.makeBox(1, 1, 1)
        b = Part.makeBox(1, 1, 1, App.Vector(20, 0, 0))
        route = Part.makeCompound([a, b])
        result = self.audit.connection_check(route, route, (0, 0, 0))
        self.assertFalse(result["passed"])
        self.assertGreater(result["overlap_outside_terminal_region_mm3"], 0.9)


if __name__ == "__main__":
    unittest.main()
