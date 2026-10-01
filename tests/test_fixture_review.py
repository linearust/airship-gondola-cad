"""Bind the frozen CAD to its retained independent transition approval."""

import gzip
import hashlib
import json
import unittest

from gondola.config import BASELINE_FILE, BASELINE_SHA256, REPO_ROOT
from gondola.provenance import file_sha256


class FixtureReviewTests(unittest.TestCase):
    def test_fixture_has_matching_retained_independent_approval(self):
        review = json.loads(BASELINE_FILE.with_name("review.json").read_text())
        self.assertEqual(file_sha256(BASELINE_FILE), BASELINE_SHA256)
        self.assertEqual(review["candidate_sha256"], BASELINE_SHA256)
        self.assertEqual(review["status"], "APPROVED_FOR_REGRESSION_FIXTURE_PROMOTION")
        evidence = review["evidence"]
        with gzip.open(REPO_ROOT / evidence["archive"], "rt") as stream:
            retained = json.load(stream)
        for key in evidence["record_path"]:
            retained = retained[key]
        encoded = json.dumps(
            retained, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
        self.assertEqual(
            hashlib.sha256(encoded).hexdigest(), evidence["canonical_json_sha256"]
        )
        self.assertEqual(retained["file_hashes_before"]["candidate"], BASELINE_SHA256)
        self.assertEqual(
            retained["file_hashes_before"]["old"], review["old_fixture_sha256"]
        )
        self.assertEqual(retained["file_hashes_before"], retained["file_hashes_after"])
        self.assertIs(retained["saved_files_unchanged"], True)
        self.assertIs(
            retained["review_conclusion"]["approved_for_fixture_transition"], True
        )
        self.assertTrue(retained["review_conclusion"]["checks"])
        self.assertTrue(
            all(
                value is True
                for value in retained["review_conclusion"]["checks"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
