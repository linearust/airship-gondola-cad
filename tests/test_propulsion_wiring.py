"""Reject disconnected, stale, blocked or falsely qualified lead planning space."""

import math
import unittest
from unittest.mock import patch

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
        fc = create_reference(
            cls.doc,
            cls.electronics,
            "ModuleFCEnvelope",
            "FC",
            equipment_envelopes.fc_envelope_shape(),
            "Reference",
        )
        cls.fc_reserve = create_reference(
            cls.doc,
            cls.electronics,
            "FCWiringClearanceReserve",
            "FC space",
            wiring_reserves.reserve_shapes()["FCWiringClearanceReserve"],
            "Planning only",
        )
        cls.fc_reserve.Role = "Clearance"
        cls.routes = propulsion_wiring.build_reserves(
            cls.doc, cls.propulsion, cls.electronics
        )
        registry = cls.doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        for name, items in {
            "PrintedParts": [],
            "HardwareParts": [],
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

    def test_thirteen_mm_rise_has_real_remote_overlap_at_actual_module_stations(
        self,
    ):
        from gondola.cad import placed_shape, world_shape

        propulsion = self.propulsion.getGlobalPlacement()
        electronics = self.electronics.getGlobalPlacement()
        self.assertEqual(propulsion.Base.x, -17)
        fc = world_shape(self.fc_reserve)
        for sign in (-1, 1):
            points = self.wiring.route_points(sign, propulsion, electronics)
            self.assertAlmostEqual(points[1][2] - points[-1][2], 14.0)
            # Retain the previous insufficient13 mm rise as the FC deck moves:
            # its old absolute Z42 becomes Z44 after raising the carrier2 mm.
            points[1] = (*points[1][:2], points[-1][2] + 13.0)
            with patch.object(self.wiring, "route_points", return_value=points):
                route = self.wiring.route_geometry(sign, propulsion, electronics)
            shape = placed_shape(route["shape"], propulsion)
            endpoint = propulsion.multVec(App.Vector(*points[-1]))
            result = self.audit.connection_check(shape, fc, tuple(endpoint))
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["overlap_outside_terminal_region_mm3"], 5e-5)

            # Independent cylinder/plane bound: at the top of the FC band,
            # the furthest point on the last straight Ø3 corridor lies beyond
            # the 8 mm sphere by 0.02623 mm. This is real geometry, not a
            # Boolean sliver to discard by widening the audit tolerance.
            approach = propulsion.multVec(App.Vector(*points[1])) - endpoint
            rise = approach.z
            horizontal = math.hypot(approach.x, approach.y)
            band_height = fc.BoundBox.ZMax - endpoint.z
            axial_distance = (band_height * approach.Length + 1.5 * horizontal) / rise
            maximum_radius = math.hypot(axial_distance, 1.5)
            self.assertGreater(maximum_radius, 8.02)
            self.assertLess(maximum_radius, 8.03)

    def test_fixed_z43_waypoint_cannot_follow_the_raised_fc_terminal(self):
        from gondola.cad import placed_shape, world_shape

        propulsion = self.propulsion.getGlobalPlacement()
        electronics = self.electronics.getGlobalPlacement()
        fc = world_shape(self.fc_reserve)
        for sign in (-1, 1):
            points = self.wiring.route_points(sign, propulsion, electronics)
            self.assertAlmostEqual(points[-1][2], 31.0)
            self.assertAlmostEqual(points[1][2], 45.0)
            # This was the actual regression: the terminal rose2 mm while
            # the intermediate waypoint remained at absolute Z43.
            points[1] = (*points[1][:2], 43.0)
            with patch.object(self.wiring, "route_points", return_value=points):
                route = self.wiring.route_geometry(sign, propulsion, electronics)
            shape = placed_shape(route["shape"], propulsion)
            endpoint = propulsion.multVec(App.Vector(*points[-1]))
            result = self.audit.connection_check(shape, fc, tuple(endpoint))
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["overlap_outside_terminal_region_mm3"], 0.07)

    def test_disconnected_route_fails(self):
        route = self.routes[0]
        original = route.Shape
        try:
            points = self.wiring.route_points(
                1,
                self.propulsion.getGlobalPlacement(),
                self.electronics.getGlobalPlacement(),
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
            self.electronics.getGlobalPlacement(),
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

    def _optical_carrier_obstacles(self, host_name, side):
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import optical_interface, optical_mount

        station = next(s for s in MODULE_STATIONS if s.object_name == host_name)
        host = App.Placement(
            App.Vector(station.x_mm, 0, 0),
            App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
        )
        tower_placement = host.multiply(optical_interface.placement(side))
        obstacles = {"OpticalMountBase": optical_mount.base_shape()}
        obstacles.update(dict(optical_interface.base_component_proxies()))
        for shape in obstacles.values():
            shape.Placement = tower_placement.multiply(shape.Placement)
        return obstacles

    def test_selected_optical_carrier_attachments_clear_motor_routes(self):
        from gondola.cad import world_shape
        from gondola.parts import power_mount

        for host, side in {
            ("BatteryEquipmentModule", "PositiveX"),
            (power_mount.DEFAULT_OPTICAL_HOST, power_mount.DEFAULT_OPTICAL_SIDE),
        }:
            obstacles = self._optical_carrier_obstacles(host, side)
            for route in self.routes:
                shape = world_shape(route)
                for name, obstacle in obstacles.items():
                    with self.subTest(
                        host=host, side=side, route=route.Name, obstacle=name
                    ):
                        self.assertLess(shape.common(obstacle).Volume, 1e-6)
                        self.assertGreaterEqual(shape.distToShape(obstacle)[0], 1.5)

    def test_low_waypoint_crosses_fc_band_before_terminal_entry(self):
        from gondola.cad import world_shape

        prop = self.propulsion.getGlobalPlacement()
        electronics = self.electronics.getGlobalPlacement()
        for sign in (-1, 1):
            points = self.wiring.route_points(sign, prop, electronics)
            # Preserve the deliberately bad waypoint 16 mm ahead of the FC
            # after moving that module onto the new 20 mm rail station grid.
            fc_local_x = prop.inverse().multVec(electronics.Base).x
            points[1] = (fc_local_x + 16.0, sign * 20.0, 34.0)
            with patch.object(self.wiring, "route_points", return_value=points):
                shape = self.wiring.route_geometry(sign, prop, electronics)["shape"]
            shape.Placement = prop.multiply(shape.Placement)
            endpoint = prop.multVec(App.Vector(*points[-1]))
            result = self.audit.connection_check(
                shape,
                world_shape(self.fc_reserve),
                (endpoint.x, endpoint.y, endpoint.z),
            )
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["overlap_outside_terminal_region_mm3"], 1)

    def test_remote_fc_crossing_is_not_a_permitted_connection(self):
        a = Part.makeBox(1, 1, 1)
        b = Part.makeBox(1, 1, 1, App.Vector(20, 0, 0))
        route = Part.makeCompound([a, b])
        result = self.audit.connection_check(route, route, (0, 0, 0))
        self.assertFalse(result["passed"])
        self.assertGreater(result["overlap_outside_terminal_region_mm3"], 0.9)


if __name__ == "__main__":
    unittest.main()
