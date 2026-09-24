"""Reject disconnected, stale, blocked or falsely qualified lead planning space."""

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
        from gondola.parts import (
            equipment_envelopes,
            propulsion_wiring,
            wiring_reserves,
        )
        from gondola.validation import propulsion_wiring as audit

        cls.wiring, cls.audit = propulsion_wiring, audit
        cls.doc = App.newDocument("PropulsionWiringRegression")
        cls.propulsion = create_group(cls.doc, "MainPropulsionModule", "Propulsion")
        cls.propulsion.Placement.Base.y = 0.1
        cls.electronics = create_group(
            cls.doc, "ElectronicsEquipmentModule", "Electronics"
        )
        cls.electronics.Placement = App.Placement(
            App.Vector(-72, -0.1, 0), App.Rotation(App.Vector(0, 0, 1), 180)
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

    def test_disconnected_route_fails(self):
        route = self.routes[0]
        original = route.Shape
        try:
            route.Shape = original.cut(
                Part.makeBox(1, 200, 100, App.Vector(-43, -100, 0))
            )
            self.assertGreater(len(route.Shape.Solids), 1)
            self.assertFalse(self.audit.check(self.doc)["passed"])
        finally:
            route.Shape = original

    def test_obstacle_in_middle_is_detected(self):
        from gondola.cad import create_reference

        blocker = create_reference(
            self.doc,
            self.propulsion,
            "TestRouteBlocker",
            "Unmodeled wire obstruction",
            Part.makeBox(2, 4, 4, App.Vector(-39, 43, 40)),
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

    def test_electronics_slide_rejects_stale_route(self):
        original = self.electronics.Placement
        try:
            changed = App.Placement(original)
            changed.Base.x -= 9
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

    def _optical_host_obstacles(self, host_placement):
        from gondola.parts import optical_mount, stack_interface

        tower_placement = host_placement.multiply(
            App.Placement(App.Vector(0, 0, stack_interface.STACK_TOP_Z), App.Rotation())
        )
        obstacles = {"OpticalMountBase": optical_mount.base_shape()}
        obstacles.update(dict(stack_interface.rigid_float_component_bounds()))
        for shape in obstacles.values():
            shape.Placement = tower_placement.multiply(shape.Placement)
        return obstacles

    def test_both_optical_hosts_leave_registration_margin(self):
        from gondola.cad import world_shape

        hosts = {
            "Battery": App.Placement(App.Vector(90, -0.1, 0), App.Rotation()),
            "Electronics": self.electronics.getGlobalPlacement(),
        }
        for host, placement in hosts.items():
            obstacles = self._optical_host_obstacles(placement)
            for route in self.routes:
                shape = world_shape(route)
                for name, obstacle in obstacles.items():
                    with self.subTest(host=host, route=route.Name, obstacle=name):
                        self.assertLess(shape.common(obstacle).Volume, 1e-6)
                        self.assertGreaterEqual(shape.distToShape(obstacle)[0], 1.5)

    def test_old_diagonal_route_hits_electronics_stack_leg(self):
        old_points = [
            (-38, 65.5, 48.2),
            (-46, 65.5, 48.2),
            (-54, 45, 34),
            (-50, 14.8, 24.2),
        ]
        prop = self.propulsion.getGlobalPlacement()
        electronics = self.electronics.getGlobalPlacement()
        with patch.object(self.wiring, "route_points", return_value=old_points):
            shape = self.wiring.route_geometry(1, prop, electronics)["shape"]
        shape.Placement = prop.multiply(shape.Placement)
        obstacles = self._optical_host_obstacles(electronics)
        self.assertGreater(shape.common(obstacles["OpticalMountBase"]).Volume, 8)
        self.assertGreater(shape.common(obstacles["load_leg_0"]).Volume, 30)

    def test_remote_fc_crossing_is_not_a_permitted_connection(self):
        a = Part.makeBox(1, 1, 1)
        b = Part.makeBox(1, 1, 1, App.Vector(20, 0, 0))
        route = Part.makeCompound([a, b])
        result = self.audit.connection_check(route, route, (0, 0, 0))
        self.assertFalse(result["passed"])
        self.assertGreater(result["overlap_outside_terminal_region_mm3"], 0.9)


if __name__ == "__main__":
    unittest.main()
