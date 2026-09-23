"""Verify every exported native pose against the saved Blender review animation."""

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy

TRANSLATION_TOLERANCE_M = 1e-7
ROTATION_TOLERANCE_RAD = 1e-5
MATRIX_TOLERANCE = 1e-5
MAX_DISCREPANCIES = 30


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def matrix_errors(actual, native):
    """Independently apply CAD mm to metres and the presentation X half-turn."""
    signs = (1, -1, -1)
    expected = [[signs[row] * native[row][col] for col in range(3)] for row in range(3)]
    translation = math.sqrt(
        sum(
            (actual[row][3] - signs[row] * native[row][3] * 0.001) ** 2
            for row in range(3)
        )
    )
    difference = max(
        abs(actual[row][col] - expected[row][col])
        for row in range(3)
        for col in range(3)
    )
    # atan2 avoids acos/float32 cancellation near an exactly matching rotation.
    relative = [
        [sum(expected[k][row] * actual[k][col] for k in range(3)) for col in range(3)]
        for row in range(3)
    ]
    sine = 0.5 * math.sqrt(
        (relative[2][1] - relative[1][2]) ** 2
        + (relative[0][2] - relative[2][0]) ** 2
        + (relative[1][0] - relative[0][1]) ** 2
    )
    cosine = 0.5 * (sum(relative[i][i] for i in range(3)) - 1)
    angle = math.atan2(sine, cosine)
    affine = max(abs(actual[3][i] - (1 if i == 3 else 0)) for i in range(4))
    return translation, angle, max(difference, affine)


def actions_for(data):
    animation = getattr(data, "animation_data", None)
    if animation is None:
        return
    if animation.action is not None:
        yield animation.action
    for track in animation.nla_tracks:
        for strip in track.strips:
            if strip.action is not None:
                yield strip.action


def scene_actions(scene):
    yield from actions_for(scene)
    if scene.world is not None:
        yield from actions_for(scene.world)
    for obj in scene.objects:
        yield from actions_for(obj)
        if obj.data is not None:
            yield from actions_for(obj.data)
            keys = getattr(obj.data, "shape_keys", None)
            if keys is not None:
                yield from actions_for(keys)
        for slot in obj.material_slots:
            if slot.material is not None:
                yield from actions_for(slot.material)
                if slot.material.node_tree is not None:
                    yield from actions_for(slot.material.node_tree)


def verify(payload, blend):
    metadata = payload["metadata"]
    report = {
        "passed": False,
        "cad_sha256": metadata["cad_sha256"],
        "source_fingerprint": metadata["source_fingerprint"],
        "revision": metadata["revision"],
        "source_cad_hash_checked": False,
        "translation_tolerance_m": TRANSLATION_TOLERANCE_M,
        "rotation_tolerance_rad": ROTATION_TOLERANCE_RAD,
        "rotation_matrix_tolerance": MATRIX_TOLERANCE,
        "scope": "All exported integer-frame native samples, exact CAD-part inventories and visibility, and scene object/action isolation. CAD millimetres become metres with a global X half-turn. Quaternion sign continuity is checked between samples. No continuous-time interpolation, collision, physics, or source-CAD freshness certification is claimed.",
        "scene_count": len(bpy.data.scenes),
        "sampled_frames": 0,
        "matrix_checks": 0,
        "visibility_checks": 0,
        "maximum_translation_error_m": 0.0,
        "maximum_rotation_error_rad": 0.0,
        "maximum_matrix_error": 0.0,
        "discrepancy_count": 0,
        "discrepancy_kinds": {},
        "discrepancies": [],
        "scenes": [],
    }

    def fail(kind, **details):
        report["discrepancy_count"] += 1
        kinds = report["discrepancy_kinds"]
        kinds[kind] = kinds.get(kind, 0) + 1
        if len(report["discrepancies"]) < MAX_DISCREPANCIES:
            report["discrepancies"].append({"kind": kind, **details})

    definitions = payload["scenes"]
    expected_names = [definition["name"] for definition in definitions]
    if len(definitions) != 7 or len(set(expected_names)) != 7:
        fail("source_scene_inventory", names=expected_names)
    if set(bpy.data.scenes.keys()) != set(expected_names):
        fail(
            "scene_inventory",
            expected=expected_names,
            actual=list(bpy.data.scenes.keys()),
        )
    part_names = [part["name"] for part in payload["parts"]]
    if (
        len(part_names) != len(set(part_names))
        or len(part_names) != metadata["part_count"]
    ):
        fail("source_part_inventory")
    object_owners, action_owners = {}, {}
    for scene in bpy.data.scenes:
        for obj in scene.objects:
            previous = object_owners.setdefault(obj.as_pointer(), scene.name)
            if previous != scene.name:
                fail("shared_object", object=obj.name, scenes=[previous, scene.name])
        for action in set(scene_actions(scene)):
            previous = action_owners.setdefault(action.as_pointer(), scene.name)
            if previous != scene.name:
                fail("shared_action", action=action.name, scenes=[previous, scene.name])

    for definition in definitions:
        name = definition["name"]
        scene = bpy.data.scenes.get(name)
        if scene is None:
            continue
        initial_failures = report["discrepancy_count"]
        expected = definition["visible"]
        if len(expected) != len(set(expected)) or not set(expected).issubset(
            part_names
        ):
            fail("source_visible_inventory", scene=name)
        for key, value in (
            ("CADRevision", metadata["revision"]),
            ("CADSHA256", metadata["cad_sha256"]),
            ("SourceFingerprint", metadata["source_fingerprint"]),
        ):
            if scene.get(key) != value:
                fail("source_metadata", scene=name, property=key, actual=scene.get(key))
        objects = {}
        for obj in scene.objects:
            cad_name = obj.get("CADObjectName")
            if cad_name is None:
                if obj.type == "MESH":
                    fail("unidentified_mesh", scene=name, object=obj.name)
                continue
            if cad_name in objects:
                fail("duplicate_cad_object", scene=name, part=cad_name)
            objects[cad_name] = obj
            if obj.type != "MESH" or obj.get("ReviewScene") != name:
                fail("cad_object_identity", scene=name, part=cad_name)
        if set(objects) != set(expected):
            fail(
                "cad_object_inventory",
                scene=name,
                missing=sorted(set(expected) - objects.keys()),
                extra=sorted(objects.keys() - set(expected)),
            )
        frames = [sample["frame"] for sample in definition["samples"]]
        if frames != list(range(1, definition["frames"] + 1)):
            fail("source_sample_frames", scene=name)
        if scene.frame_start != 1 or scene.frame_end != definition["frames"]:
            fail(
                "scene_frame_range",
                scene=name,
                start=scene.frame_start,
                end=scene.frame_end,
            )
        if abs(scene.render.fps / scene.render.fps_base - metadata["fps"]) > 1e-7:
            fail("scene_fps", scene=name)
        bpy.context.window.scene = scene
        previous_quaternions = {}
        scene_translation = scene_rotation = scene_matrix = 0.0
        scene_checks = 0
        for sample in definition["samples"]:
            frame = sample["frame"]
            if set(sample["poses"]) != set(expected):
                fail("source_pose_inventory", scene=name, frame=frame)
            scene.frame_set(frame)
            graph = bpy.context.evaluated_depsgraph_get()
            graph.update()
            report["sampled_frames"] += 1
            for cad_name, pose in sample["poses"].items():
                obj = objects.get(cad_name)
                if obj is None:
                    continue
                evaluated = obj.evaluated_get(graph)
                errors = matrix_errors(evaluated.matrix_world, pose["matrix"])
                scene_translation = max(scene_translation, errors[0])
                scene_rotation = max(scene_rotation, errors[1])
                scene_matrix = max(scene_matrix, errors[2])
                report["matrix_checks"] += 1
                scene_checks += 1
                if not all(math.isfinite(value) for value in errors) or any(
                    value > limit
                    for value, limit in zip(
                        errors,
                        (
                            TRANSLATION_TOLERANCE_M,
                            ROTATION_TOLERANCE_RAD,
                            MATRIX_TOLERANCE,
                        ),
                    )
                ):
                    fail(
                        "matrix_mismatch",
                        scene=name,
                        frame=frame,
                        part=cad_name,
                        translation_error_m=errors[0],
                        rotation_error_rad=errors[1],
                        matrix_error=errors[2],
                    )
                visible = pose["visible"]
                report["visibility_checks"] += 1
                if (
                    evaluated.hide_render != (not visible)
                    or evaluated.hide_viewport != (not visible)
                    or (
                        visible
                        and not obj.visible_get(view_layer=bpy.context.view_layer)
                    )
                ):
                    fail(
                        "visibility_mismatch",
                        scene=name,
                        frame=frame,
                        part=cad_name,
                        expected=visible,
                        hide_render=bool(evaluated.hide_render),
                        hide_viewport=bool(evaluated.hide_viewport),
                    )
                if evaluated.rotation_mode != "QUATERNION":
                    fail("rotation_mode", scene=name, frame=frame, part=cad_name)
                else:
                    quaternion = tuple(evaluated.rotation_quaternion)
                    previous = previous_quaternions.get(cad_name)
                    if (
                        previous is not None
                        and sum(a * b for a, b in zip(previous, quaternion)) < -1e-7
                    ):
                        fail(
                            "quaternion_sign_discontinuity",
                            scene=name,
                            frame=frame,
                            part=cad_name,
                        )
                    previous_quaternions[cad_name] = quaternion
        report["maximum_translation_error_m"] = max(
            report["maximum_translation_error_m"], scene_translation
        )
        report["maximum_rotation_error_rad"] = max(
            report["maximum_rotation_error_rad"], scene_rotation
        )
        report["maximum_matrix_error"] = max(
            report["maximum_matrix_error"], scene_matrix
        )
        report["scenes"].append(
            {
                "name": name,
                "parts": len(objects),
                "frames": len(frames),
                "matrix_checks": scene_checks,
                "maximum_translation_error_m": scene_translation,
                "maximum_rotation_error_rad": scene_rotation,
                "maximum_matrix_error": scene_matrix,
                "passed": report["discrepancy_count"] == initial_failures,
            }
        )
        print(
            f"Verified {name}: {len(frames)} frames, {scene_checks} poses", flush=True
        )
    report["unique_object_count"] = len(object_owners)
    report["unique_action_count"] = len(action_owners)
    report["blend_path"] = str(blend)
    report["passed"] = report["discrepancy_count"] == 0 and report["matrix_checks"] > 0
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(
        sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    )
    started = time.monotonic()
    report = {"passed": False}
    try:
        source_hash = file_sha256(args.input)
        blend_hash = file_sha256(args.blend)
        payload = json.loads(args.input.read_text())
        bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()))
        report = verify(payload, args.blend.resolve())
        report.update(input_json_sha256=source_hash, blend_sha256=blend_hash)
        unchanged = source_hash == file_sha256(
            args.input
        ) and blend_hash == file_sha256(args.blend)
        report["input_files_unchanged_during_verification"] = unchanged
        report["passed"] = report["passed"] and unchanged
    except Exception as error:
        report.update(passed=False, error=f"{type(error).__name__}: {error}")
    report["elapsed_seconds"] = time.monotonic() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "report": str(args.output)}))
    if not report["passed"]:
        raise RuntimeError(f"Blender review verification failed; see {args.output}")


if __name__ == "__main__":
    main()
