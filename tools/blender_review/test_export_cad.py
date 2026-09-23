"""Bounded export-contract checks; run with native FreeCAD's Python runtime."""

import unittest
from types import SimpleNamespace

from tools.blender_review.export_cad import (
    check_review_basis,
    representation,
    review_objects,
)


class ExportContractTests(unittest.TestCase):
    @staticmethod
    def basis():
        objects = {}
        for prefix in ("Port", "Starboard"):
            objects[prefix + "Pod"] = SimpleNamespace(MinimumTilt=-180, MaximumTilt=180)
            objects[prefix + "ServoHorn"] = SimpleNamespace(SuppliedHornMeasured=False)
            objects[prefix + "HornGearAdapter"] = SimpleNamespace(
                PrintBlankShape=object()
            )
            for position in ("Near", "Far"):
                for kind in ("Bolt", "Nut"):
                    objects[prefix + "HornGearClamp" + position + kind] = object()
        service = {
            "part_paths": [{"waypoints_mm": [[0, 0, 0], [0, 0, 0.5], [80, 0, 0.5]]}],
            "output_gear_removal": [
                {"segments": [{"end_mm": [0, -sign * 35, 0]}]} for sign in (1, -1)
            ],
            "mount_fastener_release": [
                {
                    "bolt_axial_withdrawal": {"segments": [{"end_mm": [0, 0, 8.2]}]},
                    "nut_axial_removal": {
                        "segments": [
                            {"end_mm": [0, 0, -0.2]},
                            {"end_mm": [sign * 25, 0, -0.2]},
                        ]
                    },
                }
                for sign in (1, -1)
            ],
        }
        report = {
            "gear_configuration": "48_16",
            "local_propulsion_evidence": {
                "saved_servo_module_service": service,
                "saved_carrier_metal_clearances": [
                    {"axial_travel": {"negative_mm": 0.5, "positive_mm": 0.5}}
                ],
            },
        }
        return SimpleNamespace(getObject=objects.get), objects, report

    def test_current_two_pair_examples_are_supported(self):
        doc, objects, report = self.basis()
        check_review_basis(doc, report)
        self.assertIn("Unmeasured", representation(objects["PortServoHorn"]))
        self.assertIn(
            "Prepared assembly example", representation(objects["PortHornGearAdapter"])
        )
        self.assertIn("undrilled blank", representation(objects["PortHornGearAdapter"]))

    def test_missing_pair_or_changed_horn_evidence_cannot_reuse_captions(self):
        doc, objects, report = self.basis()
        del objects["PortHornGearClampNearBolt"]
        with self.assertRaisesRegex(RuntimeError, "both prepared-example"):
            check_review_basis(doc, report)
        doc, objects, report = self.basis()
        objects["PortServoHorn"].SuppliedHornMeasured = True
        with self.assertRaisesRegex(RuntimeError, "horn/preparation"):
            check_review_basis(doc, report)
        doc, objects, report = self.basis()
        del objects["PortHornGearAdapter"].PrintBlankShape
        with self.assertRaisesRegex(RuntimeError, "horn/preparation"):
            check_review_basis(doc, report)

    def test_changed_motion_cannot_reuse_presentation_poses(self):
        doc, _, report = self.basis()
        report["local_propulsion_evidence"]["saved_servo_module_service"]["part_paths"][
            0
        ]["waypoints_mm"][2][0] = 90
        with self.assertRaisesRegex(RuntimeError, "removal paths"):
            check_review_basis(doc, report)

    def test_bench_jig_and_clearance_proxies_cannot_enter_installed_review(self):
        body, jig, reserve = [
            SimpleNamespace(Name=name)
            for name in ("PortHornGearAdapter", "HornCenteringJig", "WireReserve")
        ]
        registry = SimpleNamespace(
            PrintedParts=[body],
            HardwareParts=[],
            ReferenceParts=[],
            TapeReferences=[],
            FitCoupons=[jig],
            ClearanceVolumes=[reserve],
        )
        self.assertEqual(review_objects(registry), [body])
        for leaked in (jig, reserve):
            registry.ReferenceParts = [leaked]
            with self.assertRaisesRegex(RuntimeError, "bench fit sample or clearance"):
                review_objects(registry)

    def test_returned_spacer_requires_an_explicit_caption_revision(self):
        old = SimpleNamespace(Name="PortOutputBearingSpacerNegative")
        registry = SimpleNamespace(
            PrintedParts=[],
            HardwareParts=[old],
            ReferenceParts=[],
            TapeReferences=[],
            FitCoupons=[],
            ClearanceVolumes=[],
        )
        with self.assertRaisesRegex(RuntimeError, "axial-travel caption"):
            review_objects(registry)


if __name__ == "__main__":
    unittest.main()
