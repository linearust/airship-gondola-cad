"""Saved optional artifacts must preserve the native solid and declared dimensions."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import FreeCAD as App
    import Mesh

    from gondola.parts import mounting_plate
except ImportError:
    App = Mesh = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SavedPowerExportTests(unittest.TestCase):
    def test_registration_bound_includes_the_complete_common_plate(self):
        from gondola.parts import power_mount
        from gondola.power_export import _registration_bounds

        shape = mounting_plate.shape(power_mount.DECK_BOTTOM_Z)
        bound = _registration_bounds(power_mount.DEFAULT_PLAN)["PowerDeck"]
        # These samples check that the whole plate participates in the analytical
        # enclosure; they do not replace its continuous mathematical bound.
        for yaw, x, y in (
            (0, 0, 0),
            (-2.5, 0, 0),
            (-2, 0, 1.5),
            (-2, 0, -1.5),
        ):
            moved = shape.copy()
            moved.rotate(App.Vector(), App.Vector(0, 0, 1), yaw)
            moved.translate(App.Vector(x, y, 0))
            self.assertLess(moved.cut(bound).Volume, 1e-6)

    def test_saved_round_trip_accepts_surface_identity_but_rejects_artifact_changes(
        self,
    ):
        from gondola.cad import set_property
        from gondola.contracts.power_options import (
            POWER_PLATFORM_DOCUMENT_NAME,
            power_option_contract,
        )
        from gondola.parts import power_mount
        from gondola.power_export import (
            ARTIFACT_NAMES,
            audit_power_options,
            export_power_options,
        )

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("gondola.power_export.source_fingerprint", return_value="a" * 64),
            # This isolates serialization and artifact mutation from arrangement
            # screening, which has separate real-assembly native tests.
            patch(
                "gondola.power_export.screen_configurations",
                return_value={"passed": True, "default_configuration_clear": True},
            ),
        ):
            out = Path(directory)
            main = App.newDocument("PowerSerializationFixture")
            try:
                main.addObject("App::Part", power_mount.DEFAULT_HOST)
                main.addObject("App::Part", power_mount.DEFAULT_OPTICAL_HOST)
                from gondola.parts import optical_interface

                optical = main.addObject("App::Part", "OpticalFlowModule")
                optical_interface.attach_to_host(
                    optical, main.getObject(power_mount.DEFAULT_HOST)
                )
                registry = main.addObject("App::DocumentObjectGroup", "DesignRegistry")
                set_property(registry, "OptionalPowerDocument", ARTIFACT_NAMES[0])
                set_property(
                    registry,
                    "OptionalPowerContract",
                    json.dumps(power_option_contract(), sort_keys=True),
                )
                for category in (
                    "PrintedParts",
                    "HardwareParts",
                    "ReferenceParts",
                    "TapeReferences",
                    "ClearanceVolumes",
                ):
                    registry.addProperty("App::PropertyLinkListGlobal", category)
                    setattr(registry, category, [])
                main.recompute()
                source = out / "gondola.FCStd"
                main.saveAs(str(source))
                export_power_options(main, out)
            finally:
                App.closeDocument(main.Name)

            initial = audit_power_options(source, out)
            self.assertTrue(initial["passed"], initial)
            self.assertTrue(initial["manifest_matches"])
            self.assertTrue(initial["mesh_surface_comparison"]["passed"])
            self.assertTrue(initial["read_only_artifacts"])
            self.assertTrue(initial["manufacturing_source_matches"])
            self.assertTrue(initial["optional_print_inventory_matches"])
            manufacture = App.openDocument(str(out / POWER_PLATFORM_DOCUMENT_NAME))
            manufacture.PowerPrintSource.SourceFingerprint = "b" * 64
            manufacture.save()
            App.closeDocument(manufacture.Name)
            changed_manufacture = audit_power_options(source, out)
            self.assertFalse(changed_manufacture["passed"])
            self.assertFalse(changed_manufacture["manufacturing_source_matches"])
            self.assertTrue(changed_manufacture["manifest_matches"])
            manufacture = App.openDocument(str(out / POWER_PLATFORM_DOCUMENT_NAME))
            manufacture.PowerPrintSource.SourceFingerprint = "a" * 64
            manufacture.save()
            App.closeDocument(manufacture.Name)

            mesh_path = out / ARTIFACT_NAMES[1]
            original_mesh = mesh_path.read_bytes()
            mesh = Mesh.Mesh(str(mesh_path))
            # Preserve connectivity and every unmodified triangle while corrupting
            # one small patch. Whole-mesh translation adds no coverage and makes
            # the intentionally negative surface audit needlessly expensive.
            mesh.movePoint(0, App.Vector(0.2, 0, 0))
            mesh.write(str(mesh_path))
            shifted = audit_power_options(source, out)
            self.assertTrue(shifted["mesh_checks"]["watertight_mesh"])
            self.assertTrue(shifted["manifest_matches"])
            self.assertFalse(shifted["mesh_surface_comparison"]["passed"])
            self.assertFalse(shifted["passed"])

            mesh_path.write_bytes(original_mesh)
            manifest_path = out / ARTIFACT_NAMES[3]
            manifest = json.loads(manifest_path.read_text())
            manifest["size_mm"][0] += 0.1
            manifest_path.write_text(json.dumps(manifest))
            wrong_size = audit_power_options(source, out)
            self.assertTrue(wrong_size["mesh_surface_comparison"]["passed"])
            self.assertFalse(wrong_size["manifest_matches"])
            self.assertFalse(wrong_size["passed"])


if __name__ == "__main__":
    unittest.main()
