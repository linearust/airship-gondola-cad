"""Invalid numeric audit evidence must not silently pass."""

import unittest

from gondola.validation.evidence import overlap_failures
from gondola.validation.propulsion_evidence import (
    PROPULSION_EVIDENCE_COUNTS,
    propulsion_evidence_check,
)


class OverlapEvidenceTests(unittest.TestCase):
    def test_nested_overlaps_fail_in_either_sign(self):
        result = overlap_failures(
            {
                "samples": [
                    {"overlap_frame_mm3": 0.1},
                    {"nested": {"rail_shoe_overlap_mm3": -0.2}},
                ]
            },
            1e-5,
        )
        self.assertEqual(
            result,
            [
                {"field": "/samples/0/overlap_frame_mm3", "volume_mm3": 0.1},
                {
                    "field": "/samples/1/nested/rail_shoe_overlap_mm3",
                    "volume_mm3": -0.2,
                },
            ],
        )

    def test_nonfinite_overlaps_fail(self):
        for volume in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(volume=volume):
                result = overlap_failures({"overlap_mm3": volume}, 1e-5)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["field"], "/overlap_mm3")

    def test_tolerance_and_required_blocking_contacts_are_not_failures(self):
        self.assertEqual(
            overlap_failures(
                {
                    "rail_overlap_mm3": 1e-5,
                    "shoe_overlap_mm3": -1e-6,
                    "blocking_intersection_mm3": 1.0,
                    "bearing_contact_area_mm2": 2.0,
                    "overlap_scope": "Nominal solid envelopes",
                },
                1e-5,
            ),
            [],
        )


class PropulsionEvidenceTests(unittest.TestCase):
    def complete_report(self):
        report = {
            key: [{"passed": True} for _ in range(count)]
            for key, count in PROPULSION_EVIDENCE_COUNTS.items()
        }
        for row in report["geometry"]:
            row.update(
                valid_brep=True,
                solid_count=1,
                single_closed_solid=True,
                watertight_mesh=True,
                mesh_components=1,
            )
        report["passed"] = True
        report["expected_evidence_counts"] = dict(PROPULSION_EVIDENCE_COUNTS)
        return report

    def test_complete_evidence_passes_with_contract_counts(self):
        result = propulsion_evidence_check(self.complete_report())
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["inventory"]["continuous_nut_loading"]["expected"], 2)
        self.assertEqual(result["inventory"]["fastener_service"]["expected"], 14)
        self.assertEqual(result["inventory"]["geometry"]["expected"], 6)
        self.assertEqual(result["inventory"]["bridge_joint"]["expected"], 1)
        self.assertEqual(result["inventory"]["servo_module_service"]["expected"], 1)
        self.assertEqual(result["inventory"]["input_drive_service"]["expected"], 2)
        self.assertEqual(result["inventory"]["servo_case_service"]["expected"], 2)
        self.assertNotIn("spacer_service", result["inventory"])
        self.assertEqual(result["inventory"]["bearing_post_roots"]["expected"], 4)

    def test_missing_row_cannot_reduce_its_own_required_count(self):
        for key, count in PROPULSION_EVIDENCE_COUNTS.items():
            with self.subTest(key=key):
                report = self.complete_report()
                report[key].pop()
                report["expected_evidence_counts"][key] = count - 1
                result = propulsion_evidence_check(report)
                self.assertFalse(result["passed"], result)
                self.assertEqual(
                    result["inventory"][key],
                    {"expected": count, "actual": count - 1},
                )

    def test_extra_rows_are_rejected(self):
        report = self.complete_report()
        report["fastener_service"].append({"passed": True})
        self.assertFalse(propulsion_evidence_check(report)["passed"])

    def test_successful_parent_does_not_hide_failed_or_nonboolean_row(self):
        for flag in (False, None, 1, "true"):
            with self.subTest(flag=flag):
                report = self.complete_report()
                report["input_drive_service"][0]["passed"] = flag
                result = propulsion_evidence_check(report)
                self.assertFalse(result["passed"], result)
                self.assertEqual(
                    result["row_failures"][0]["field"], "/input_drive_service/0"
                )

    def test_absent_or_malformed_row_collection_fails_closed(self):
        for rows in (None, {}, "two rows", [{"passed": True}, None]):
            with self.subTest(rows=rows):
                report = self.complete_report()
                report["continuous_nut_loading"] = rows
                self.assertFalse(propulsion_evidence_check(report)["passed"])
        report = self.complete_report()
        del report["continuous_nut_loading"]
        self.assertFalse(propulsion_evidence_check(report)["passed"])

    def test_successful_geometry_row_does_not_hide_invalid_solid_or_mesh(self):
        for field, invalid in (
            ("valid_brep", False),
            ("solid_count", 0),
            ("solid_count", 2),
            ("single_closed_solid", False),
            ("watertight_mesh", False),
            ("mesh_components", 2),
        ):
            with self.subTest(field=field, invalid=invalid):
                report = self.complete_report()
                report["geometry"][0][field] = invalid
                result = propulsion_evidence_check(report)
                self.assertFalse(result["passed"], result)
                self.assertEqual(result["row_failures"][0]["field"], "/geometry/0")


if __name__ == "__main__":
    unittest.main()
