"""Verifier inventory and file binding without requiring the Blender Python API."""

import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# Independent reviewed inventory: do not import names from exporter or verifier.
SCENE_NAMES = (
    "01 Assembly",
    "02 Independent tilt",
    "03 Gear and horn",
    "04 Axial allowance",
    "05 Optical rail trim",
    "06 Servo module removal",
)


class SceneObject(dict):
    def __init__(self, scene):
        super().__init__(CADObjectName="Part", ReviewScene=scene)
        self.name = scene + " | Part"
        self.type = "MESH"
        self.animation_data = self.data = None
        self.material_slots = ()
        self.matrix_world = ((1, 0, 0, 0), (0, -1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1))
        self.hide_render = self.hide_viewport = False
        self.rotation_mode = "QUATERNION"
        self.rotation_quaternion = (0, 1, 0, 0)

    def as_pointer(self):
        return id(self)

    def evaluated_get(self, graph):
        return self

    def visible_get(self, *, view_layer):
        return True


class Scene(dict):
    def __init__(self, name, metadata):
        super().__init__(
            CADRevision=metadata["revision"],
            CADSHA256=metadata["cad_sha256"],
            SourceFingerprint=metadata["source_fingerprint"],
        )
        self.name = name
        self.objects = [SceneObject(name)]
        self.animation_data = self.world = None
        self.frame_start = self.frame_end = 1
        self.render = SimpleNamespace(fps=24, fps_base=1)

    def frame_set(self, frame):
        pass


class Scenes(dict):
    def __iter__(self):
        return iter(self.values())


class SceneVerifierTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "metadata": {
                "cad_sha256": "a" * 64,
                "source_fingerprint": "b" * 64,
                "revision": "BH",
                "part_count": 1,
                "fps": 24,
            },
            "parts": [{"name": "Part"}],
            "scenes": [
                {
                    "name": name,
                    "visible": ["Part"],
                    "frames": 1,
                    "samples": [
                        {
                            "frame": 1,
                            "poses": {
                                "Part": {
                                    "matrix": [
                                        [1, 0, 0, 0],
                                        [0, 1, 0, 0],
                                        [0, 0, 1, 0],
                                        [0, 0, 0, 1],
                                    ],
                                    "visible": True,
                                }
                            },
                        }
                    ],
                }
                for name in SCENE_NAMES
            ],
        }
        self.bpy = SimpleNamespace(
            data=SimpleNamespace(scenes=Scenes()),
            context=SimpleNamespace(
                window=SimpleNamespace(scene=None),
                view_layer=None,
                evaluated_depsgraph_get=lambda: SimpleNamespace(update=lambda: None),
            ),
            ops=SimpleNamespace(
                wm=SimpleNamespace(open_mainfile=lambda **kwargs: None)
            ),
        )
        spec = importlib.util.spec_from_file_location(
            "_scene_verifier_under_test", Path(__file__).with_name("verify_scene.py")
        )
        self.verifier = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"bpy": self.bpy}):
            spec.loader.exec_module(self.verifier)
        self.install_scenes(self.payload)

    def install_scenes(self, payload):
        self.bpy.data.scenes = Scenes(
            (row["name"], Scene(row["name"], payload["metadata"]))
            for row in payload["scenes"]
        )

    def verify(self, payload=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.verifier.verify(payload or self.payload, Path("review.blend"))

    def test_exact_six_scenes_pass_without_claiming_source_cad_freshness(self):
        report = self.verify()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["scene_count"], 6)
        self.assertEqual(report["matrix_checks"], 6)
        self.assertEqual(report["visibility_checks"], 6)
        # The orchestration/collector separately hashes actual CAD bytes. This
        # verifier only binds exported metadata to the saved Blender scenes.
        self.assertFalse(report["source_cad_hash_checked"])

    def test_source_inventory_rejects_missing_duplicate_extra_or_replaced_scene(self):
        for change in ("missing", "duplicate", "extra", "replaced"):
            with self.subTest(change=change):
                payload = copy.deepcopy(self.payload)
                scenes = payload["scenes"]
                if change == "missing":
                    scenes.pop()
                elif change == "duplicate":
                    scenes[-1] = copy.deepcopy(scenes[0])
                elif change == "extra":
                    scenes.append({**copy.deepcopy(scenes[-1]), "name": "07 Legacy"})
                else:
                    scenes[4]["name"] = "05 Legacy optical host"
                # Even a Blender file agreeing with a malformed export must
                # fail the verifier's independent expected scene inventory.
                self.install_scenes(payload)
                report = self.verify(payload)
                self.assertFalse(report["passed"])
                self.assertIn("source_scene_inventory", report["discrepancy_kinds"])

    def test_saved_blender_inventory_rejects_missing_or_extra_scene(self):
        for change in ("missing", "extra"):
            with self.subTest(change=change):
                self.install_scenes(self.payload)
                if change == "missing":
                    self.bpy.data.scenes.pop("05 Optical rail trim")
                else:
                    self.bpy.data.scenes["07 Legacy"] = Scene(
                        "07 Legacy", self.payload["metadata"]
                    )
                report = self.verify()
                self.assertFalse(report["passed"])
                self.assertIn("scene_inventory", report["discrepancy_kinds"])

    def test_saved_scene_metadata_must_match_exported_cad_and_source_hashes(self):
        for key in ("CADSHA256", "SourceFingerprint"):
            with self.subTest(property=key):
                self.install_scenes(self.payload)
                self.bpy.data.scenes["05 Optical rail trim"][key] = "c" * 64
                report = self.verify()
                self.assertFalse(report["passed"])
                self.assertIn("source_metadata", report["discrepancy_kinds"])

    def test_input_json_or_blend_changes_during_verification_are_rejected(self):
        for changed_name in ("input.json", "review.blend"):
            with (
                self.subTest(changed=changed_name),
                tempfile.TemporaryDirectory() as folder,
            ):
                directory = Path(folder)
                exported, blend, output = (
                    directory / name
                    for name in ("input.json", "review.blend", "report.json")
                )
                exported.write_text(json.dumps(self.payload))
                blend.write_bytes(b"saved Blender input")
                verify = self.verifier.verify

                def mutate_after_verification(payload, path):
                    report = verify(payload, path)
                    self.assertTrue(report["passed"])
                    (directory / changed_name).write_bytes(
                        b"changed during verification"
                    )
                    return report

                argv = [
                    "verify_scene.py",
                    "--",
                    "--input",
                    str(exported),
                    "--blend",
                    str(blend),
                    "--output",
                    str(output),
                ]
                with (
                    patch.object(sys, "argv", argv),
                    patch.object(
                        self.verifier, "verify", side_effect=mutate_after_verification
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                    self.assertRaises(RuntimeError),
                ):
                    self.verifier.main()
                report = json.loads(output.read_text())
                self.assertFalse(report["passed"])
                self.assertFalse(report["input_files_unchanged_during_verification"])


if __name__ == "__main__":
    unittest.main()
