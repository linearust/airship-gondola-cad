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
            "passed": True,
            "shared_rail_fasteners_removed_before_bench": [
                "MainPropulsionModuleRailMountNut",
                "MainPropulsionModuleRailMountScrew",
            ],
            "released_fasteners": [],
            "part_paths": [
                {
                    "waypoints_mm": [
                        [0, 0, 0],
                        [0, -2.7, 0],
                        [0, -2.7, 0.5],
                        [80, -2.7, 0.5],
                    ]
                }
            ],
            "output_gear_removal": [
                {
                    "part": "PortOutputGear",
                    "segments": [{"start_mm": [0, 0, 0], "end_mm": [0, -35, 0]}],
                },
                {
                    "part": "StarboardOutputGear",
                    "segments": [{"start_mm": [0, 0, 0], "end_mm": [0, 35, 0]}],
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

    def test_key_releases_before_lift_then_slide_without_hiding_drive_parts(self):
        names = ("ServoDriveBridge", "PortServo")
        for frame, x, y, z in (
            (108, 0, 0, 0),
            (109, 0, 0, 0),
            (120, 0, -2.7 * 11 / 23, 0),
            (132, 0, -2.7, 0),
            (133, 0, -2.7, 0),
            (134, 0, -2.7, 0.5 / 23),
            (156, 0, -2.7, 0.5),
            (157, 0, -2.7, 0.5),
            (158, 80 / 59, -2.7, 0.5),
            (215, 80 * 58 / 59, -2.7, 0.5),
            (216, 80, -2.7, 0.5),
            (241, 80, -2.7, 0.5),
        ):
            for name in names:
                with self.subTest(name=name, frame=frame):
                    self.assert_pose(name, frame, (x, y, z), drive_names=names)
        offsets, hidden = REVIEW_MOTION.removal_pose(241, names)
        self.assertEqual(hidden, {"PortOutputGear", "StarboardOutputGear"})
        self.assertEqual(set(offsets), set(names) | hidden)

    def test_bench_scene_excludes_shared_clamp_and_rejects_old_or_missing_pairs(self):
        pair = [
            "MainPropulsionModuleRailMountNut",
            "MainPropulsionModuleRailMountScrew",
        ]
        members = ["PropulsionFixedFrame", "ServoDriveBridge", "PortServo"]
        self.assertEqual(REVIEW_MOTION.bench_parts(members + pair), members)
        for invalid in (
            members,
            members + pair[:1],
            members + pair + ["ServoBridgePortBolt"],
        ):
            with (
                self.subTest(invalid=invalid),
                self.assertRaisesRegex(RuntimeError, "shared rail clamp"),
            ):
                REVIEW_MOTION.bench_parts(invalid)
        self.assertIn("not animated here", REVIEW_MOTION.removal_description())
        self.assertIn(
            "supporting frame and bridge together", REVIEW_MOTION.removal_description()
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
                (
                    1,
                    "Off-rail bench / shared clamp already removed / support both parts",
                ),
                (13, "Remove Port 16T"),
                (61, "Remove Starboard 16T"),
                (109, "Release key -Y 2.7 mm"),
                (133, "Lift module 0.5 mm"),
                (157, "Slide module +X 80 mm"),
                (217, "Module removed; output supports retained"),
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
            for endpoint in ("start_mm", "end_mm"):
                yield ("output_gear_removal", side, "segments", 0, endpoint)
        for step in (0, 1, 2, 3):
            yield ("part_paths", 0, "waypoints_mm", step)

    @staticmethod
    def parent_at(data, path):
        for key in path[:-1]:
            data = data[key]
        return data

    def test_matching_native_evidence_is_accepted(self):
        REVIEW_MOTION.check_basis(native_evidence())

    def test_changed_service_endpoints_and_key_release_are_rejected(self):
        for path in self.endpoint_paths():
            for axis in (0, 1, 2):
                with self.subTest(path=path, axis=axis):
                    evidence = native_evidence()
                    parent = self.parent_at(
                        evidence["saved_servo_module_service"], path
                    )
                    parent[path[-1]][axis] += 1
                    with self.assertRaisesRegex(RuntimeError, "removal paths"):
                        REVIEW_MOTION.check_basis(evidence)

    def test_failed_or_legacy_prerequisites_cannot_reuse_the_bench_scene(self):
        for key, value in (
            ("passed", False),
            ("shared_rail_fasteners_removed_before_bench", []),
            (
                "shared_rail_fasteners_removed_before_bench",
                ["MainPropulsionModuleRailMountScrew"],
            ),
            ("released_fasteners", ["ServoBridgePortBolt"]),
        ):
            with self.subTest(key=key, value=value):
                evidence = native_evidence()
                evidence["saved_servo_module_service"][key] = value
                with self.assertRaisesRegex(
                    RuntimeError, "off-rail bench prerequisites"
                ):
                    REVIEW_MOTION.check_basis(evidence)

    def test_empty_or_reordered_service_evidence_is_rejected(self):
        for key, value in (("part_paths", []), ("output_gear_removal", [])):
            evidence = native_evidence()
            evidence["saved_servo_module_service"][key] = value
            with self.assertRaisesRegex(RuntimeError, "removal paths"):
                REVIEW_MOTION.check_basis(evidence)
        evidence = native_evidence()
        evidence["saved_servo_module_service"]["output_gear_removal"].reverse()
        with self.assertRaisesRegex(RuntimeError, "gear removal paths"):
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
        for path in self.endpoint_paths():
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
