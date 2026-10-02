"""Saved-model aggregation must retain the complete eight-site nut evidence."""

import copy
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

try:
    import FreeCAD as App
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SavedPropulsionEvidenceTests(unittest.TestCase):
    def test_saved_aggregation_accepts_eight_guides_and_rejects_bad_inventories(self):
        from gondola.config import BASELINE_FILE
        from gondola.contracts.drive import drive_for_document
        from gondola.validation.assembly import detailed_propulsion_evidence
        from gondola.validation.nut_guides import installed_nut_guide_checks
        from gondola.validation.propulsion_evidence import PROPULSION_EVIDENCE_COUNTS

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "saved_evidence.FCStd"
            doc = App.openDocument(str(BASELINE_FILE), hidden=True)
            try:
                doc.saveAs(str(source))
            finally:
                App.closeDocument(doc.Name)
            saved = App.openDocument(str(source), hidden=True)
            try:
                saved.recompute()
                guides = installed_nut_guide_checks(saved)
                self.assertEqual(
                    {row["nut"] for row in guides},
                    {
                        "PortBearingCapNegativeNut",
                        "PortBearingCapPositiveNut",
                        "PortBearingCapInputNut",
                        "PortOutputClampNegativeNut",
                        "StarboardBearingCapNegativeNut",
                        "StarboardBearingCapPositiveNut",
                        "StarboardBearingCapInputNut",
                        "StarboardOutputClampPositiveNut",
                    },
                )
                self.assertEqual(len(guides), 8)
                self.assertTrue(all(row["passed"] for row in guides), guides)

                # Isolate final aggregation from unrelated expensive motion
                # checks. Native nut checks, reopened source-shape comparisons,
                # report parsing and the final assembly gate remain exercised.
                local = {
                    key: [{"passed": True} for _ in range(count)]
                    for key, count in PROPULSION_EVIDENCE_COUNTS.items()
                }
                for row in local["geometry"]:
                    row.update(
                        valid_brep=True,
                        solid_count=1,
                        single_closed_solid=True,
                        watertight_mesh=True,
                        mesh_components=1,
                    )
                local.update(
                    passed=True,
                    gear_configuration=drive_for_document(saved).key,
                    all_bought_parts_excluded_from_prints=True,
                )
                source.with_name(
                    source.stem + "_propulsion_validation.json"
                ).write_text(json.dumps(local))

                checks = {
                    "propulsion.fixed_servo_datum_check": {"passed": True},
                    "propulsion.servo_mount_check": {"passed": True},
                    "propulsion.bearing_post_roots_check": [{"passed": True}] * 2,
                    "propulsion.gear_engagement_check": {"passed": True},
                    "servo_module.integrated_frame_check": {"passed": True},
                    "servo_module.servo_service_preparation_check": {"passed": True},
                    "motion_clearance.carrier_metal_clearance_check": {"passed": True},
                    "relative_motion.relative_motion_check": {"passed": True},
                }
                failed = copy.deepcopy(guides)
                failed[-1]["passed"] = False
                cases = (
                    ("complete eight sites", guides, True),
                    ("missing site", guides[:-1], False),
                    ("extra site", guides + guides[-1:], False),
                    ("legacy six rows", guides[:-2], False),
                    ("failed site", failed, False),
                )
                with ExitStack() as stack:
                    for name, result in checks.items():
                        stack.enter_context(
                            patch("gondola.validation." + name, return_value=result)
                        )
                    nut_check = stack.enter_context(
                        patch(
                            "gondola.validation.nut_guides.installed_nut_guide_checks"
                        )
                    )
                    for label, rows, expected in cases:
                        with self.subTest(inventory=label):
                            nut_check.return_value = rows
                            result = detailed_propulsion_evidence(saved, source)
                            self.assertEqual(result["saved_nut_guides"], rows)
                            self.assertTrue(result["local_checks"]["passed"])
                            self.assertFalse(result["local_evidence_row_failures"])
                            self.assertTrue(
                                all(
                                    row["passed"]
                                    for row in result["saved_shape_source_comparisons"]
                                )
                            )
                            self.assertIs(result["passed"], expected, label)
            finally:
                App.closeDocument(saved.Name)


if __name__ == "__main__":
    unittest.main()
