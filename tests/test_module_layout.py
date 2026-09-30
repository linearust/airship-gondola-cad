"""Four rail modules; optics attach to an existing universal carrier."""

import unittest
from dataclasses import asdict

from gondola.contracts.design import (
    FC_INSTALLATION_LOCAL_YAW_DEG,
    MODULE_STATIONS,
    ModuleStation,
)
from gondola.contracts.rail_attachments import attachment_pattern


class ModuleLayoutTests(unittest.TestCase):
    def test_battery_and_electronics_flank_neutral_propulsion(self):
        stations = {item.object_name: item for item in MODULE_STATIONS}
        self.assertEqual(len(stations), 4)
        self.assertEqual(stations["MainPropulsionModule"].x_mm, -17.0)
        self.assertEqual(stations["BatteryEquipmentModule"].x_mm, 100)
        self.assertEqual(stations["ElectronicsEquipmentModule"].x_mm, -70)
        self.assertEqual(stations["ElectronicsEquipmentModule"].yaw_deg, 180)
        self.assertEqual(stations["AccessoryEquipmentModule"].x_mm, -140)
        self.assertEqual(stations["AccessoryEquipmentModule"].yaw_deg, 180)
        propulsion = stations["MainPropulsionModule"]
        self.assertEqual(propulsion.contact_length_mm, 24)
        self.assertEqual(propulsion.x_mm + propulsion.attachment_offset_x_mm, 0)
        self.assertNotIn("OpticalFlowModule", stations)

    def test_compact_rail_preserves_base_end_margin_and_manufacturing_limit(self):
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
        self.assertEqual(RAIL_LENGTH_MM / 2 - abs(accessory.x_mm) - 8, 2)
        self.assertEqual(
            next(
                s for s in MODULE_STATIONS if s.object_name == "MainPropulsionModule"
            ).attachment_offset_x_mm,
            17.0,
        )

    def test_modules_allow_only_fixed_forward_or_reverse_orientation(self):
        forward = ModuleStation("Forward", 0)
        reversed_station = ModuleStation("Reverse", 0, 180)
        self.assertEqual(forward.yaw_deg, 0)
        self.assertEqual(reversed_station.yaw_deg, 180)
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

    def test_paired_clamps_preserve_serialized_station_and_opposed_hardware(self):
        station = next(
            item
            for item in MODULE_STATIONS
            if item.object_name == "MainPropulsionModule"
        )
        self.assertEqual(
            asdict(station),
            {
                "object_name": "MainPropulsionModule",
                "x_mm": -17.0,
                "yaw_deg": 0,
                "attachment_offset_x_mm": 17.0,
                "contact_length_mm": 24.0,
            },
        )
        pattern = station.attachment_pattern
        self.assertEqual(station.attachment_offsets_x_mm, (17.0, -17.0))
        self.assertEqual(
            pattern.sites(17),
            (
                {"prefix": "", "x_offset": 17, "side": 1},
                {"prefix": "Opposite", "x_offset": -17, "side": -1},
            ),
        )
        self.assertEqual(
            (pattern.count, pattern.spacing_mm, pattern.screw_length_mm),
            (2, 34.0, 12.0),
        )
        self.assertEqual(pattern.head_bearing_y(-5.25, 2.0), -7.75)
        ordinary = attachment_pattern(False)
        self.assertEqual(
            (ordinary.count, ordinary.spacing_mm, ordinary.screw_length_mm),
            (1, None, 8.0),
        )
        self.assertEqual(ordinary.head_bearing_y(-5.25, 2.0), -3.25)

    def test_invalid_clamp_configuration_fails_before_geometry(self):
        for invalid in (None, True, "0", float("nan"), float("inf")):
            for field in ("x_mm", "attachment_offset_x_mm", "contact_length_mm"):
                with (
                    self.subTest(field=field, value=invalid),
                    self.assertRaises(ValueError),
                ):
                    ModuleStation(
                        **{"object_name": "Carrier", "x_mm": 0, field: invalid}
                    )
            with self.subTest(offset=invalid), self.assertRaises(ValueError):
                attachment_pattern(False).sites(invalid)
        for invalid in (0, 1, None, "true"):
            with self.subTest(shared_drive=invalid), self.assertRaises(ValueError):
                attachment_pattern(invalid)
        for invalid in (0, -17, 16.9):
            with self.subTest(paired_offset=invalid), self.assertRaises(ValueError):
                ModuleStation(
                    "MainPropulsionModule", -17, attachment_offset_x_mm=invalid
                )


if __name__ == "__main__":
    unittest.main()
