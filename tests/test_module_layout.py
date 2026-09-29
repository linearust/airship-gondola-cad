"""Four rail modules; optics attach to an existing universal carrier."""

import unittest

from gondola.contracts.design import (
    FC_INSTALLATION_LOCAL_YAW_DEG,
    MODULE_STATIONS,
    ModuleStation,
)


class ModuleLayoutTests(unittest.TestCase):
    def test_battery_and_electronics_flank_neutral_propulsion(self):
        stations = {item.object_name: item for item in MODULE_STATIONS}
        self.assertEqual(len(stations), 4)
        self.assertEqual(stations["MainPropulsionModule"].x_mm, 0)
        self.assertEqual(stations["BatteryEquipmentModule"].x_mm, 90)
        self.assertEqual(stations["ElectronicsEquipmentModule"].x_mm, -54)
        self.assertEqual(stations["ElectronicsEquipmentModule"].yaw_deg, 180)
        self.assertEqual(stations["AccessoryEquipmentModule"].x_mm, -140)
        self.assertEqual(stations["AccessoryEquipmentModule"].yaw_deg, 180)
        self.assertNotIn("OpticalFlowModule", stations)

    def test_compact_rail_preserves_shoe_end_margin_and_manufacturing_limit(self):
        from gondola.contracts.design import (
            MAX_PRINT_PART_DIMENSION_MM,
            RAIL_LENGTH_MM,
        )

        accessory = next(
            station
            for station in MODULE_STATIONS
            if station.object_name == "AccessoryEquipmentModule"
        )
        self.assertEqual(RAIL_LENGTH_MM, 300)
        self.assertEqual(MAX_PRINT_PART_DIMENSION_MM, 340)
        self.assertEqual(RAIL_LENGTH_MM / 2 - abs(accessory.x_mm) - 9, 1)
        self.assertEqual(abs(accessory.x_mm - (-144)), 4)
        self.assertEqual(abs(accessory.x_mm - (-135)), 5)

    def test_transverse_clamp_direction_tracks_fixed_half_turn(self):
        forward = ModuleStation("Forward", 0, "Clamp", "PositiveY")
        reversed_station = ModuleStation("Reverse", 0, "Clamp", "PositiveY", 180)
        self.assertEqual(forward.transverse_sign, 1)
        self.assertEqual(reversed_station.transverse_sign, -1)
        for invalid in (-180, 45, 90, 360):
            with self.subTest(yaw=invalid), self.assertRaises(ValueError):
                ModuleStation("Invalid", 0, "Clamp", "PositiveY", invalid)

    def test_fc_relative_half_turn_preserves_prior_world_heading_basis(self):
        electronics = next(
            item
            for item in MODULE_STATIONS
            if item.object_name == "ElectronicsEquipmentModule"
        )
        self.assertEqual(FC_INSTALLATION_LOCAL_YAW_DEG, 180)
        self.assertEqual((electronics.yaw_deg + FC_INSTALLATION_LOCAL_YAW_DEG) % 360, 0)


if __name__ == "__main__":
    unittest.main()
