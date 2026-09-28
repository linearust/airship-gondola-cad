"""Independent numeric checks of the fixed review plan, without CAD runtimes."""

import unittest

from tools.blender_review.motion_plan import REVIEW_MOTION


def native_evidence():
    """Recorded native endpoints, deliberately independent of the motion plan."""
    return {
        "saved_carrier_metal_clearances": [
            {"axial_travel": {"negative_mm": 0.5, "positive_mm": 0.5}}
        ],
        "saved_servo_module_service": {
            "part_paths": [{"waypoints_mm": [[0, 0, 0], [0, 0, 0.5], [80, 0, 0.5]]}],
            "output_gear_removal": [
                {"segments": [{"end_mm": [0, -35, 0]}]},
                {"segments": [{"end_mm": [0, 35, 0]}]},
            ],
            "mount_fastener_release": [
                {
                    "bolt_axial_withdrawal": {"segments": [{"end_mm": [0, 0, 8.2]}]},
                    "nut_axial_removal": {
                        "segments": [
                            {"end_mm": [0, 0, -0.2]},
                            {"end_mm": [25, 0, -0.2]},
                        ]
                    },
                },
                {
                    "bolt_axial_withdrawal": {"segments": [{"end_mm": [0, 0, 8.2]}]},
                    "nut_axial_removal": {
                        "segments": [
                            {"end_mm": [0, 0, -0.2]},
                            {"end_mm": [-25, 0, -0.2]},
                        ]
                    },
                },
            ],
        },
    }


class ReviewMotionBoundaries(unittest.TestCase):
    def assert_pose(self, name, frame, expected, hidden=False, drive_names=()):
        offsets, invisible = REVIEW_MOTION.removal_pose(frame, drive_names)
        for actual, target in zip(offsets[name], expected, strict=True):
            self.assertAlmostEqual(actual, target, places=10)
        self.assertEqual(name in invisible, hidden)

    def test_both_output_gears_stay_visible_through_withdrawal_endpoint(self):
        for name, cases in (
            (
                "PortOutputGear",
                (
                    (12, 0, False),
                    (13, 0, False),
                    (47, -34, False),
                    (48, -35, False),
                    (49, -35, True),
                ),
            ),
            (
                "StarboardOutputGear",
                (
                    (60, 0, False),
                    (61, 0, False),
                    (95, 34, False),
                    (96, 35, False),
                    (97, 35, True),
                ),
            ),
        ):
            for frame, y, hidden in cases:
                with self.subTest(name=name, frame=frame):
                    self.assert_pose(name, frame, (0, y, 0), hidden)

    def test_both_mount_bolts_hide_only_after_axial_withdrawal(self):
        for name, cases in (
            (
                "ServoBridgePortBolt",
                (
                    (108, 0, False),
                    (109, 0, False),
                    (131, 7.843478260869565, False),
                    (132, 8.2, False),
                    (133, 8.2, True),
                ),
            ),
            (
                "ServoBridgeStarboardBolt",
                (
                    (180, 0, False),
                    (181, 0, False),
                    (203, 7.843478260869565, False),
                    (204, 8.2, False),
                    (205, 8.2, True),
                ),
            ),
        ):
            for frame, z, hidden in cases:
                with self.subTest(name=name, frame=frame):
                    self.assert_pose(name, frame, (0, 0, z), hidden)

    def test_both_nuts_drop_before_sliding_and_hide_after_the_final_endpoint(self):
        for name, cases in (
            (
                "ServoBridgePortNut",
                (
                    (131, 0, 0, False),
                    (132, 0, 0, False),
                    (133, 0, -0.03333333333333333, False),
                    (137, 0, -0.16666666666666667, False),
                    (138, 0, -0.2, False),
                    (139, 0.8333333333333333, -0.2, False),
                    (167, 24.166666666666668, -0.2, False),
                    (168, 25, -0.2, False),
                    (169, 25, -0.2, True),
                ),
            ),
            (
                "ServoBridgeStarboardNut",
                (
                    (203, 0, 0, False),
                    (204, 0, 0, False),
                    (205, 0, -0.03333333333333333, False),
                    (209, 0, -0.16666666666666667, False),
                    (210, 0, -0.2, False),
                    (211, -0.8333333333333333, -0.2, False),
                    (239, -24.166666666666668, -0.2, False),
                    (240, -25, -0.2, False),
                    (241, -25, -0.2, True),
                ),
            ),
        ):
            for frame, x, z, hidden in cases:
                with self.subTest(name=name, frame=frame):
                    self.assert_pose(name, frame, (x, 0, z), hidden)

    def test_module_lifts_before_sliding_and_remains_visible(self):
        names = ("ServoDriveBridge", "PortServo")
        for frame, x, z in (
            (252, 0, 0),
            (253, 0, 0),
            (254, 0, 0.021739130434782608),
            (275, 0, 0.4782608695652174),
            (276, 0, 0.5),
            (277, 0, 0.5),
            (278, 1.3559322033898304, 0.5),
            (335, 78.64406779661017, 0.5),
            (336, 80, 0.5),
            (337, 80, 0.5),
            (361, 80, 0.5),
        ):
            for name in names:
                with self.subTest(name=name, frame=frame):
                    self.assert_pose(name, frame, (x, 0, z), drive_names=names)
        _, hidden = REVIEW_MOTION.removal_pose(361, names)
        self.assertEqual(
            hidden,
            {
                "PortOutputGear",
                "StarboardOutputGear",
                "ServoBridgePortBolt",
                "ServoBridgePortNut",
                "ServoBridgeStarboardBolt",
                "ServoBridgeStarboardNut",
            },
        )

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

    def test_markers_preserve_reviewed_timing_and_labels(self):
        self.assertEqual(
            REVIEW_MOTION.removal_markers(),
            [
                (1, "Disconnect leads / release gear set screws"),
                (13, "Remove Port 16T"),
                (61, "Remove Starboard 16T"),
                (109, "Remove Port mount bolt / nut"),
                (181, "Remove Starboard mount bolt / nut"),
                (253, "Lift module 0.5 mm"),
                (277, "Slide module +X 80 mm"),
                (337, "Module removed; output supports retained"),
            ],
        )
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


class ReviewMotionEvidence(unittest.TestCase):
    @staticmethod
    def endpoint_paths():
        for side in (0, 1):
            yield ("output_gear_removal", side, "segments", -1, "end_mm")
            yield (
                "mount_fastener_release",
                side,
                "bolt_axial_withdrawal",
                "segments",
                -1,
                "end_mm",
            )
            for step in (0, 1):
                yield (
                    "mount_fastener_release",
                    side,
                    "nut_axial_removal",
                    "segments",
                    step,
                    "end_mm",
                )

    @staticmethod
    def parent_at(data, path):
        for key in path[:-1]:
            data = data[key]
        return data

    def test_matching_native_evidence_is_accepted(self):
        REVIEW_MOTION.check_basis(native_evidence())

    def test_changed_gear_bolt_and_nut_endpoints_are_rejected_on_both_sides(self):
        for path in self.endpoint_paths():
            with self.subTest(path=path):
                evidence = native_evidence()
                parent = self.parent_at(evidence["saved_servo_module_service"], path)
                parent[path[-1]][0] += 1
                with self.assertRaisesRegex(
                    RuntimeError, "gear/fastener removal paths"
                ):
                    REVIEW_MOTION.check_basis(evidence)

    def test_changed_module_lift_slide_or_seated_height_is_rejected(self):
        for waypoint, axis, value in ((1, 2, 0.6), (2, 0, 81), (2, 2, 0.6)):
            with self.subTest(waypoint=waypoint, axis=axis):
                evidence = native_evidence()
                evidence["saved_servo_module_service"]["part_paths"][0]["waypoints_mm"][
                    waypoint
                ][axis] = value
                with self.assertRaisesRegex(RuntimeError, "servo-module removal paths"):
                    REVIEW_MOTION.check_basis(evidence)

    def test_changed_or_nonfinite_axial_allowance_is_rejected_in_both_directions(self):
        for direction in ("negative_mm", "positive_mm"):
            for value in (0.6, float("nan"), float("inf"), -float("inf"), None, "0.5"):
                with self.subTest(direction=direction, value=value):
                    evidence = native_evidence()
                    evidence["saved_carrier_metal_clearances"][0]["axial_travel"][
                        direction
                    ] = value
                    with self.assertRaisesRegex(RuntimeError, "axial-travel poses"):
                        REVIEW_MOTION.check_basis(evidence)

    def test_malformed_service_vectors_are_rejected(self):
        paths = list(self.endpoint_paths()) + [
            ("part_paths", 0, "waypoints_mm", step) for step in (0, 1, 2)
        ]
        for path in paths:
            original = self.parent_at(
                native_evidence()["saved_servo_module_service"], path
            )[path[-1]]
            for malformed in (
                [],
                original[:-1],
                original + [0],
                [float("nan"), *original[1:]],
                [float("inf"), *original[1:]],
                [-float("inf"), *original[1:]],
                ["invalid", *original[1:]],
                None,
            ):
                with self.subTest(path=path, malformed=malformed):
                    evidence = native_evidence()
                    parent = self.parent_at(
                        evidence["saved_servo_module_service"], path
                    )
                    parent[path[-1]] = malformed
                    with self.assertRaisesRegex(RuntimeError, "removal paths"):
                        REVIEW_MOTION.check_basis(evidence)


if __name__ == "__main__":
    unittest.main()
