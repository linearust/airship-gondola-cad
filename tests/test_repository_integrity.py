"""Fast offline checks: python3 -m unittest discover -s tests -v.

Actual CAD geometry is exercised by python -m gondola validate / compare.
"""

import ast
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]


def imported_modules(path):
    """Include local imports and resolve their package-relative module names."""
    package = ".".join(path.parent.relative_to(REPO_ROOT).parts)
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = importlib.util.resolve_name("." * node.level + module, package)
            yield module
            yield from (f"{module}.{item.name}" for item in node.names)


class RepositoryIntegrityTests(unittest.TestCase):
    def test_leaf_validation_checks_do_not_import_the_propulsion_coordinator(self):
        # Shared checks must remain usable without importing their coordinator
        # back, including imports inside functions.
        coordinator = "gondola.validation.propulsion"
        for filename in (
            "horn_coupling.py",
            "propulsion_service.py",
            "servo_module.py",
            "shaft_retention.py",
            "fastener_seating.py",
            "geometry.py",
        ):
            path = REPO_ROOT / "gondola" / "validation" / filename
            self.assertNotIn(coordinator, set(imported_modules(path)), filename)

    def test_shared_optical_geometry_does_not_depend_on_report_coordinators(self):
        forbidden = {
            "gondola.validation.optical",
            "gondola.validation.equipment_options",
            "gondola.power_export",
        }
        path = REPO_ROOT / "gondola/validation/optical_envelopes.py"
        self.assertFalse(set(imported_modules(path)) & forbidden)
        for filename in ("power_export.py", "validation/equipment_options.py"):
            path = REPO_ROOT / "gondola" / filename
            self.assertNotIn("gondola.validation.optical", set(imported_modules(path)))

    def test_active_imports_do_not_require_revision_scripts_or_private_tools(self):
        allowed = set(sys.stdlib_module_names) | {
            "gondola",
            "FreeCAD",
            "FreeCADGui",
            "Part",
            "Mesh",
            "MeshPart",
            "PySide",
        }
        for path in (REPO_ROOT / "gondola").rglob("*.py"):
            source = path.read_text()
            self.assertNotIn("/home/h/", source, path)
            self.assertNotIn("/tmp/.mount_", source, path)
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Import):
                    imports = [item.name.split(".")[0] for item in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imports = [node.module.split(".")[0]]
                else:
                    continue
                self.assertTrue(set(imports) <= allowed, (path, imports))

    def test_status_works_after_copying_without_cad_or_archive(self):
        from gondola.contracts.design import EXPECTED_INVENTORY

        with tempfile.TemporaryDirectory(prefix="gondola-relocated-") as directory:
            copy = Path(directory) / "project"
            copy.mkdir()
            shutil.copytree(
                REPO_ROOT / "gondola",
                copy / "gondola",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            result = subprocess.run(
                [sys.executable, "-m", "gondola", "status"],
                cwd=copy,
                text=True,
                capture_output=True,
                check=True,
            )
            state = json.loads(result.stdout)
            self.assertEqual(state["scoped_listed_equipment_mass_g"], 35.532)
            self.assertEqual(state["inventory"], EXPECTED_INVENTORY)
            self.assertIn("yaw_motor", state["excluded_equipment"])
            self.assertFalse(state["production_released"])
            self.assertIn(
                "servo_drive",
                {entry["key"] for entry in state["unresolved_interfaces"]},
            )

    def test_frozen_reference_matches_the_reviewed_fixture_checksum(self):
        from gondola.config import BASELINE_FILE, BASELINE_SHA256

        baseline = BASELINE_FILE
        self.assertEqual(
            hashlib.sha256(baseline.read_bytes()).hexdigest(),
            BASELINE_SHA256,
        )

    def test_fingerprint_is_portable_and_sensitive_to_source_changes(self):
        from gondola import provenance

        with tempfile.TemporaryDirectory(prefix="gondola-fingerprint-") as directory:
            copy = Path(directory)
            shutil.copytree(
                REPO_ROOT / "gondola",
                copy / "gondola",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            for macro in REPO_ROOT.glob("*.FCMacro"):
                shutil.copy2(macro, copy / macro.name)
            original = provenance.source_fingerprint()
            with patch.object(provenance, "REPO_ROOT", copy):
                self.assertEqual(original, provenance.source_fingerprint())
                (copy / "build").mkdir()
                (copy / "build" / "irrelevant.py").write_text("generated artifact")
                self.assertEqual(original, provenance.source_fingerprint())
                asset = copy / "gondola" / "data" / "kst_x06_half_arm_1.step"
                contents = asset.read_bytes()
                asset.write_bytes(contents + b"\n")
                self.assertNotEqual(original, provenance.source_fingerprint())
                asset.write_bytes(contents)
                self.assertEqual(original, provenance.source_fingerprint())
                source = copy / "gondola" / "contracts" / "design.py"
                source.write_text(source.read_text() + "\n# changed design input\n")
                self.assertNotEqual(original, provenance.source_fingerprint())


if __name__ == "__main__":
    unittest.main()
