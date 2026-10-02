"""Independent numeric checks of the fixed review poses, without CAD runtimes."""

import unittest
from copy import deepcopy

from tools.blender_review.motion_plan import REVIEW_MOTION


def native_evidence():
    """Literal passed stop evidence, independent of the presentation plan."""

    def moving(prefix, side):
        return [
            prefix + suffix
            for suffix in (
                "Motor",
                "Shaft",
                "PropellerDisk",
                "MotorCarrier",
                "OutputShaft" + side,
                "OutputClamp" + side + "Bolt",
                "OutputClamp" + side + "Nut",
            )
        ]

    services = []
    for prefix, other, sign, side, other_side in (
        ("Port", "Starboard", 1, "Negative", "Positive"),
        ("Starboard", "Port", -1, "Positive", "Negative"),
    ):
        parts = moving(prefix, side)
        retained = [
            "PropulsionFixedFrame",
            "PortInputBearing",
            "StarboardInputBearing",
            "PortBearingCapInputBolt",
            "PortBearingCapInputNut",
            "StarboardBearingCapInputBolt",
            "StarboardBearingCapInputNut",
            *[
                prefix + suffix
                for suffix in (
                    "BearingCap",
                    "OutputBearingInboard",
                    "OutputBearingOutboard",
                    "Servo",
                    "DriverGear",
                    "HornGearAdapter",
                )
            ],
            other + "OutputGear",
            *moving(other, other_side),
        ]

        def path(points, obstacles):
            return {
                "passed": True,
                "obstacles": obstacles,
                "segments": [
                    {
                        "start_mm": list(a),
                        "end_mm": list(b),
                        "passed": True,
                        "intersection_mm3": {name: 0.0 for name in obstacles},
                    }
                    for a, b in zip(points, points[1:])
                ],
            }

        services.append(
            {
                "pod": prefix,
                "moving_parts": parts,
                "removed_parts": parts + [prefix + "OutputGear"],
                "removed_output_gear": prefix + "OutputGear",
                "shaft_moves_with_carrier": prefix + "OutputShaft" + side,
                "retained_parts": retained,
                "output_gear_removal": path(
                    [
                        (0, 0, 0),
                        (0, -sign * 11, 0),
                        (0, -sign * 11, 20),
                        (30, -sign * 11, 20),
                    ],
                    retained + parts,
                ),
                "carrier_removal": [
                    {"part": name, **path([(0, 0, 0), (0, sign * 60, 0)], retained)}
                    for name in parts
                ],
                "passed": True,
            }
        )
    return {
        "local_checks": {"output_carrier_service": services},
        "saved_carrier_metal_clearances": [
            {
                "pod": prefix,
                "passed": True,
                "axial_travel": {
                    "negative_mm": 0.5,
                    "positive_mm": 0.5,
                    "passed": True,
                },
            }
            for prefix in ("Port", "Starboard")
        ],
    }


def input_service_evidence():
    rows = []
    fixed = ["PropulsionFixedFrame"] + [
        side + suffix
        for side in ("Port", "Starboard")
        for suffix in (
            "InputBearing",
            "BearingCap",
            "BearingCapInputBolt",
            "BearingCapInputNut",
        )
    ]
    for output in native_evidence()["local_checks"]["output_carrier_service"]:
        prefix = output["pod"]
        sign = 1 if prefix == "Port" else -1
        remaining = [
            prefix + suffix
            for suffix in (
                "Servo",
                "ServoHorn",
                "HornGearAdapter",
                "HornGearClampNearBolt",
                "HornGearClampFarBolt",
                "HornGearClampNearNut",
                "HornGearClampFarNut",
                "InputShaftClampBolt",
                "InputShaftClampNut",
            )
        ]
        rows.append(
            {
                "pod": prefix,
                "passed": True,
                "preparation_passed": True,
                "required_prior_check": "servo_service_preparation",
                "service_mode": "shaft_first_compact_frame",
                "output_rotor_parking": {
                    "passed": True,
                    "input_remains_neutral": True,
                    "angle_deg": 90,
                    "axis_origin_mm": [0, sign * 75, 50],
                    "axis_direction": [0, 1, 0],
                    "moving_parts": output["moving_parts"],
                    "retained_parts": fixed.copy(),
                },
                "input_stub_removal": {
                    "passed": True,
                    "waypoints_mm": [
                        (0, 0, 0),
                        (0, sign * 32, 0),
                        (sign * 60, sign * 32, 0),
                    ],
                },
                "driver_gear_removal": {
                    "passed": True,
                    "waypoints_mm": [(0, 0, 0), (sign * 60, 0, 0)],
                },
                "moving_parts": remaining,
                "retained_parts": fixed.copy(),
                "part_paths": [
                    {
                        "part": name,
                        "passed": True,
                        "waypoints_mm": [
                            (0, 0, 0),
                            (0, sign * 13, 0),
                            (sign * 60, sign * 13, 0),
                        ],
                    }
                    for name in remaining
                ],
            }
        )
    return {"local_checks": {"input_drive_service": rows}}


class InputServiceSummaryTests(unittest.TestCase):
    def test_native_sequence_is_recorded_without_claiming_an_animation(self):
        summary = REVIEW_MOTION.input_service_summary(input_service_evidence())
        self.assertEqual(set(summary), {"Port", "Starboard"})
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            row = summary[prefix]
            self.assertFalse(row["animated"])
            self.assertTrue(row["input_remains_neutral"])
            self.assertEqual(row["output_rotor_parking_deg"], 90)
            self.assertEqual(
                row["input_shaft_waypoints_mm"][-1], (sign * 60, sign * 32, 0)
            )
            self.assertEqual(
                row["servo_horn_adapter_waypoints_mm"][-1], (sign * 60, sign * 13, 0)
            )
            self.assertIn(prefix + "InputBearing", row["fixed_support_parts"])

    def test_missing_failed_or_stale_input_service_cannot_be_recorded(self):
        for side in (0, 1):
            for change in (
                "missing",
                "failed",
                "parking",
                "coupled_input",
                "fixed_bearing",
                "shaft_path",
                "servo_path",
                "missing_part",
            ):
                evidence = input_service_evidence()
                row = evidence["local_checks"]["input_drive_service"][side]
                if change == "missing":
                    evidence["local_checks"]["input_drive_service"].pop()
                elif change == "failed":
                    row["passed"] = False
                elif change == "parking":
                    row["output_rotor_parking"]["angle_deg"] = 180
                elif change == "coupled_input":
                    row["output_rotor_parking"]["input_remains_neutral"] = False
                elif change == "fixed_bearing":
                    row["output_rotor_parking"]["retained_parts"].remove(
                        row["pod"] + "InputBearing"
                    )
                elif change == "shaft_path":
                    row["input_stub_removal"]["waypoints_mm"][1] = (0, 26, 0)
                elif change == "servo_path":
                    row["part_paths"][0]["waypoints_mm"][1] = (0, 14, 0)
                else:
                    row["part_paths"].pop()
                with (
                    self.subTest(side=side, change=change),
                    self.assertRaisesRegex(RuntimeError, "input-service"),
                ):
                    REVIEW_MOTION.input_service_summary(evidence)


class ReviewMotionBoundaries(unittest.TestCase):
    def test_axial_allowance_reverses_at_reviewed_stops(self):
        for frame, shift in (
            (1, 0),
            (25, 0.25),
            (48, 0.4895833333333333),
            (49, 0.5),
            (50, 0.4791666666666667),
            (73, 0),
            (96, -0.4791666666666667),
            (97, -0.5),
            (98, -0.4895833333333333),
            (121, -0.25),
            (145, 0),
            (169, 0.25),
            (193, 0.5),
            (217, 0.25),
            (241, 0),
        ):
            with self.subTest(frame=frame):
                self.assertAlmostEqual(
                    REVIEW_MOTION.axial_shift(frame), shift, places=10
                )

    def test_markers_keep_nominal_carrier_stops_separate_from_bearing_float(self):
        self.assertEqual(
            REVIEW_MOTION.axial_markers(),
            [
                (1, "Nominal"),
                (49, "+0.5 mm stop"),
                (97, "-0.5 mm stop"),
                (145, "Rotation with permitted travel"),
                (241, "Nominal"),
            ],
        )
        self.assertIn("NOT bearing internal play", REVIEW_MOTION.axial_description())
        self.assertFalse(hasattr(REVIEW_MOTION, "module_lift_mm"))
        self.assertFalse(hasattr(REVIEW_MOTION, "removal_pose"))


class RotorServiceBoundaries(unittest.TestCase):
    def test_piecewise_gear_path_finishes_before_locked_rotor_withdrawal(self):
        for frame, gear, travel, hidden in (
            (1, (0, 0, 0), 0, False),
            (25, (0, 0, 0), 0, False),
            (37, (0, -5.5, 0), 0, False),
            (49, (0, -11, 0), 0, False),
            (61, (0, -11, 10), 0, False),
            (73, (0, -11, 20), 0, False),
            (85, (15, -11, 20), 0, False),
            (97, (30, -11, 20), 0, False),
            (98, (30, -11, 20), 0, True),
            (121, (30, -11, 20), 0, True),
            (145, (30, -11, 20), 30, True),
            (169, (30, -11, 20), 60, True),
            (193, (30, -11, 20), 60, True),
        ):
            with self.subTest(frame=frame):
                offsets, absent = REVIEW_MOTION.rotor_service_pose(frame)
                self.assertEqual(offsets.pop("PortOutputGear"), gear)
                self.assertEqual(
                    set(offsets),
                    {
                        "PortMotor",
                        "PortShaft",
                        "PortPropellerDisk",
                        "PortMotorCarrier",
                        "PortOutputShaftNegative",
                        "PortOutputClampNegativeBolt",
                        "PortOutputClampNegativeNut",
                    },
                )
                self.assertTrue(
                    all(value == (0, travel, 0) for value in offsets.values())
                )
                self.assertEqual(absent, {"PortOutputGear"} if hidden else set())
                self.assertNotIn("PropulsionFixedFrame", offsets)
                self.assertNotIn("PortBearingCap", offsets)
                self.assertNotIn("PortOutputBearingInboard", offsets)

    def test_complete_independent_service_evidence_matches_the_sequence(self):
        REVIEW_MOTION.check_rotor_service_basis(native_evidence())
        self.assertEqual(REVIEW_MOTION.rotor_service_frames, 193)
        self.assertEqual(REVIEW_MOTION.rotor_service_markers()[-1][0], 169)

    def test_saved_pod_membership_must_match_exact_removed_units(self):
        rows = native_evidence()["local_checks"]["output_carrier_service"]
        names = {row["pod"]: set(row["removed_parts"]) for row in rows}
        REVIEW_MOTION.check_rotor_members(names)
        for missing in (False, True):
            changed = deepcopy(names)
            if missing:
                changed["Port"].remove("PortOutputShaftNegative")
            else:
                changed["Port"].add("PortBearingCap")
            with (
                self.subTest(missing=missing),
                self.assertRaisesRegex(RuntimeError, "pod membership"),
            ):
                REVIEW_MOTION.check_rotor_members(changed)

    def test_changed_missing_or_failed_service_evidence_is_rejected(self):
        original = native_evidence()
        cases = []
        for prefix_index in (0, 1):
            for kind in (
                "waypoint",
                "nonfinite",
                "shaft",
                "missing_path",
                "failed_path",
                "missing_retained",
                "missing_swept_obstacle",
                "collision",
                "moving_cap",
            ):
                evidence = deepcopy(original)
                row = evidence["local_checks"]["output_carrier_service"][prefix_index]
                if kind == "waypoint":
                    row["output_gear_removal"]["segments"][0]["end_mm"][1] += 0.1
                elif kind == "nonfinite":
                    row["carrier_removal"][0]["segments"][0]["end_mm"][1] = float("nan")
                elif kind == "shaft":
                    row["shaft_moves_with_carrier"] = "SeparateLooseShaft"
                elif kind == "missing_path":
                    row["carrier_removal"].pop()
                elif kind == "failed_path":
                    row["carrier_removal"][0]["segments"][0]["passed"] = False
                elif kind == "missing_retained":
                    row["retained_parts"].remove("PropulsionFixedFrame")
                elif kind == "missing_swept_obstacle":
                    del row["carrier_removal"][0]["segments"][0]["intersection_mm3"][
                        "PropulsionFixedFrame"
                    ]
                elif kind == "collision":
                    row["output_gear_removal"]["segments"][1]["intersection_mm3"][
                        "PropulsionFixedFrame"
                    ] = 0.01
                else:
                    row["moving_parts"].append(row["pod"] + "BearingCap")
                cases.append((f"{prefix_index}:{kind}", evidence))
        for label, evidence in cases:
            with (
                self.subTest(case=label),
                self.assertRaisesRegex(RuntimeError, "rotor-removal"),
            ):
                REVIEW_MOTION.check_rotor_service_basis(evidence)
        for rows in ([], original["local_checks"]["output_carrier_service"][:1]):
            with self.assertRaisesRegex(RuntimeError, "rotor-removal"):
                REVIEW_MOTION.check_rotor_service_basis(
                    {"local_checks": {"output_carrier_service": rows}}
                )


class ReviewMotionEvidence(unittest.TestCase):
    def test_matching_native_evidence_is_accepted(self):
        REVIEW_MOTION.check_basis(native_evidence())

    def test_both_complete_passed_carrier_proofs_are_required(self):
        for mode in ("missing", "duplicate", "failed_carrier", "failed_stops"):
            with self.subTest(mode=mode):
                evidence = native_evidence()
                rows = evidence["saved_carrier_metal_clearances"]
                if mode == "missing":
                    rows.pop()
                elif mode == "duplicate":
                    rows[1]["pod"] = "Port"
                elif mode == "failed_carrier":
                    rows[1]["passed"] = False
                else:
                    rows[1]["axial_travel"]["passed"] = False
                with self.assertRaisesRegex(RuntimeError, "axial-travel poses"):
                    REVIEW_MOTION.check_basis(evidence)

    def test_empty_axial_allowance_evidence_is_rejected(self):
        evidence = native_evidence()
        evidence["saved_carrier_metal_clearances"] = []
        with self.assertRaisesRegex(RuntimeError, "axial-travel poses"):
            REVIEW_MOTION.check_basis(evidence)

    def test_axial_bound_padding_does_not_change_nominal_reviewed_poses(self):
        for side in (0, 1):
            for direction in ("negative_mm", "positive_mm"):
                for padding in (-1e-7, 1e-7):
                    with self.subTest(side=side, direction=direction, padding=padding):
                        evidence = native_evidence()
                        evidence["saved_carrier_metal_clearances"][side][
                            "axial_travel"
                        ][direction] += padding
                        REVIEW_MOTION.check_basis(evidence)
                        self.assertEqual(REVIEW_MOTION.axial_allowance_mm, 0.5)
                        self.assertEqual(REVIEW_MOTION.axial_shift(49), 0.5)
                        self.assertEqual(REVIEW_MOTION.axial_shift(97), -0.5)

    def test_changed_or_nonfinite_axial_allowance_is_rejected_in_both_directions(self):
        for side in (0, 1):
            for direction in ("negative_mm", "positive_mm"):
                for value in (
                    0.5 - 2e-6,
                    0.5 + 2e-6,
                    0.6,
                    float("nan"),
                    float("inf"),
                    -float("inf"),
                    None,
                    "0.5",
                ):
                    with self.subTest(side=side, direction=direction, value=value):
                        evidence = native_evidence()
                        evidence["saved_carrier_metal_clearances"][side][
                            "axial_travel"
                        ][direction] = value
                        with self.assertRaisesRegex(RuntimeError, "axial-travel poses"):
                            REVIEW_MOTION.check_basis(evidence)


if __name__ == "__main__":
    unittest.main()
