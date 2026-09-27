"""Purchased KST clamp hardware keeps its real metric-thread identity."""

import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

try:
    import FreeCAD as App
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class KSTHardwareMetadataTests(unittest.TestCase):
    def test_m14_screws_and_nuts_pass_and_wrong_thread_data_fails(self):
        from gondola.contracts import servo_horns
        from gondola.parts import propulsion
        from gondola.procurement import export_hardware_bom
        from gondola.validation import assembly

        with (
            patch.dict(
                servo_horns.SELECTED_BY_SIDE,
                Port="KST_0415_13",
                Starboard="KST_0415_13",
            ),
            tempfile.TemporaryDirectory() as temporary,
        ):
            doc = App.newDocument("KSTHardwareMetadata")
            try:
                module = propulsion.build_propulsion_module(doc)
                hardware = [
                    obj
                    for obj in module["hardware"]
                    if obj.HardwareSKU.startswith("M1_4")
                ]
                quantities = Counter(str(obj.HardwareSKU) for obj in hardware)
                self.assertEqual(
                    quantities,
                    {"M1_4X6_PAN_HEAD_KIT": 4, "M1_4_HEX_NUT_DIN934": 4},
                )
                registry = doc.addObject("App::FeaturePython", "HardwareRegistry")
                for name in (
                    "HardwareParts",
                    "PrintedParts",
                    "FitCoupons",
                    "RailLocks",
                ):
                    registry.addProperty("App::PropertyLinkList", name)
                    setattr(registry, name, hardware if name == "HardwareParts" else [])
                doc.recompute()
                doc.saveAs(str(Path(temporary) / "hardware.FCStd"))
                export_hardware_bom(hardware, Path(temporary), "hardware")
                with patch.object(
                    assembly, "PURCHASED_HARDWARE_QUANTITIES", quantities
                ):
                    result = assembly.hardware_check(registry)
                    self.assertTrue(result["passed"], result)
                    for obj in (
                        doc.PortHornGearClampNearBolt,
                        doc.PortHornGearClampNearNut,
                    ):
                        for name, wrong in (
                            ("NominalThreadDiameter", 1.6),
                            ("ThreadPitch", 0.35),
                            ("ThreadStandard", "M1.6 x 0.35"),
                        ):
                            with self.subTest(part=obj.Name, property=name):
                                original = getattr(obj, name)
                                setattr(obj, name, wrong)
                                try:
                                    result = assembly.hardware_check(registry)
                                    self.assertFalse(result["passed"])
                                    row = next(
                                        row
                                        for row in result["parts"]
                                        if row["part"] == obj.Name
                                    )
                                    self.assertFalse(
                                        row["thread_metadata_matches_part"]
                                    )
                                finally:
                                    setattr(obj, name, original)
            finally:
                App.closeDocument(doc.Name)


if __name__ == "__main__":
    unittest.main()
