"""Four bought plates on flat bays retain the three intended mass regions."""

import unittest

from gondola.contracts.design import (
    FC_INSTALLATION_LOCAL_YAW_DEG,
    MODULE_STATIONS,
    OPTICAL_STACK_HOST,
    RAIL_LENGTH_MM,
    ModuleStation,
)


class ModuleLayoutTests(unittest.TestCase):
    def test_battery_and_electronics_flank_neutral_propulsion(self):
        stations = {item.object_name: item for item in MODULE_STATIONS}
        self.assertEqual(len(stations), 4)
        self.assertEqual(stations["MainPropulsionModule"].x_mm, 3)
        self.assertEqual(stations["MainPropulsionModule"].z_mm, 4.8)
        self.assertEqual(stations["BatteryEquipmentModule"].x_mm, 96)
        self.assertEqual(stations["ElectronicsEquipmentModule"].x_mm, -51)
        self.assertEqual(stations["ElectronicsEquipmentModule"].yaw_deg, 180)
        self.assertEqual(stations["AccessoryEquipmentModule"].x_mm, -123)
        self.assertEqual(stations["AccessoryEquipmentModule"].yaw_deg, 180)
        self.assertEqual(OPTICAL_STACK_HOST, "BatteryEquipmentModule")

    def test_each_accessory_plate_uses_its_own_complete_rigid_bay(self):
        station = next(
            row
            for row in MODULE_STATIONS
            if row.object_name == "AccessoryEquipmentModule"
        )
        centres = sorted(station.x_mm - local for local in (-22, 24))
        self.assertEqual(centres, [-147, -101])
        for centre in centres:
            bay = 48 * round(centre / 48)
            self.assertLessEqual(abs(centre - bay), 6)
            self.assertGreaterEqual(RAIL_LENGTH_MM / 2 - abs(bay) - 42 / 2, 5)
        # The frame's midpoint is deliberately in a gap; no plate attaches there.
        self.assertNotEqual(station.x_mm % 48, 0)

    def test_fixed_half_turn_has_no_obsolete_side_clamp_selection(self):
        self.assertEqual(ModuleStation("Forward", 0).yaw_deg, 0)
        self.assertEqual(ModuleStation("Reverse", 0, 180).yaw_deg, 180)
        self.assertFalse(hasattr(ModuleStation("Forward", 0), "clamp_control"))
        for invalid in (-180, 45, 90, 360):
            with self.subTest(yaw=invalid), self.assertRaises(ValueError):
                ModuleStation("Invalid", 0, invalid)

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
