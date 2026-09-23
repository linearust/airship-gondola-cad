"""Build an inspectable Blender review from sampled, native CAD geometry.

Run with Blender's Python runtime, after its ``--`` separator::

    blender --background --factory-startup --python build_scene.py -- \
        --input cad_review.json --output gondola_review.blend

This presentation does not modify the engineering model or certify its motion.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

MM_TO_M = 0.001
MODEL_ROTATION = Matrix.Rotation(math.pi, 4, "X")
LIMIT_NOTE = (
    "Rigid CAD review | propellers shown as disks | loads and cables unverified"
)


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--render-stills",
        type=Path,
        metavar="DIRECTORY",
        help="Render one representative frame from every scene into this directory.",
    )
    return parser.parse_args(argv)


def presentation_matrix(rows):
    """Keep the rigid basis; convert only translations for metre-sized meshes."""
    if len(rows) != 4 or any(len(row) != 4 for row in rows):
        raise ValueError("A CAD pose must contain a 4 by 4 matrix")
    if not all(math.isfinite(float(value)) for row in rows for value in row):
        raise ValueError("A CAD pose contains non-finite values")
    matrix = Matrix(rows)
    matrix.translation *= MM_TO_M
    return MODEL_ROTATION @ matrix


def material_for(part, cache):
    color = tuple(float(value) for value in part.get("color", [0.35, 0.58, 0.70, 1]))
    if len(color) == 3:
        color += (1.0,)
    if len(color) != 4:
        raise ValueError(f"Invalid RGBA color for {part['name']}")
    color = tuple(max(0.0, min(1.0, value)) for value in color)
    propeller_disk = "propellerdisk" in part["name"].lower()
    if propeller_disk:
        color = (*color[:3], min(color[3], 0.16))
    key = (part["category"], color)
    if key in cache:
        return cache[key]
    material = bpy.data.materials.new("CAD " + part["category"] + f" {len(cache):02d}")
    material.diffuse_color = color
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Alpha"].default_value = color[3]
    shader.inputs["Metallic"].default_value = (
        0.35 if part["category"] == "HardwareParts" else 0.0
    )
    shader.inputs["Roughness"].default_value = 0.48
    if color[3] < 1:
        material.surface_render_method = "DITHERED"
    cache[key] = material
    return material


def build_meshes(parts):
    meshes, materials = {}, {}
    for part in parts:
        name = part["name"]
        if name in meshes:
            raise ValueError(f"Duplicate CAD part: {name}")
        vertices = [
            tuple(float(value) * MM_TO_M for value in point)
            for point in part["vertices"]
        ]
        if any(
            len(point) != 3 or not all(math.isfinite(v) for v in point)
            for point in vertices
        ):
            raise ValueError(f"Invalid mesh vertices: {name}")
        faces = part["triangles"]
        if any(
            len(face) != 3 or any(index < 0 or index >= len(vertices) for index in face)
            for face in faces
        ):
            raise ValueError(f"Invalid mesh triangles: {name}")
        mesh = bpy.data.meshes.new("CAD mesh | " + name)
        mesh.from_pydata(vertices, [], faces)
        mesh.materials.append(material_for(part, materials))
        mesh.update()
        mesh["CADObjectName"] = name
        mesh["SourceUnits"] = "mm"
        meshes[name] = mesh
    return meshes


def set_interpolation(obj):
    """Blender 5.x stores keyframes in action layers and channel bags."""
    if not obj.animation_data or not obj.animation_data.action:
        return
    action = obj.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    mode = (
                        "CONSTANT"
                        if curve.data_path in {"hide_render", "hide_viewport"}
                        else "LINEAR"
                    )
                    for keyframe in curve.keyframe_points:
                        keyframe.interpolation = mode


def make_cad_objects(scene, specification, parts, meshes):
    collection = bpy.data.collections.new(scene.name + " | CAD parts")
    scene.collection.children.link(collection)
    objects = {}
    visible = specification["visible"]
    if len(visible) != len(set(visible)):
        raise ValueError(f"Duplicate visible parts in scene {scene.name}")
    for name in visible:
        if name not in parts:
            raise ValueError(f"Unknown CAD part in scene {scene.name}: {name}")
        part = parts[name]
        obj = bpy.data.objects.new(name, meshes[name])
        collection.objects.link(obj)
        obj.rotation_mode = "QUATERNION"
        obj.matrix_world = presentation_matrix(part["matrix"])
        obj["CADObjectName"] = name
        obj["CADLabel"] = part.get("label", name)
        obj["CADCategory"] = part["category"]
        obj["ReviewScene"] = scene.name
        if "propellerdisk" in name.lower():
            obj.display_type = "WIRE"
            obj["Representation"] = (
                "Swept propeller disk, not blade geometry or aerodynamic simulation"
            )
        objects[name] = obj
    samples = sorted(specification["samples"], key=lambda sample: sample["frame"])
    if not samples:
        raise ValueError(f"Scene {scene.name} has no samples")
    previous_quaternions = {}
    for sample in samples:
        frame = int(sample["frame"])
        if not scene.frame_start <= frame <= scene.frame_end:
            raise ValueError(f"Sample {frame} lies outside scene {scene.name}")
        if set(sample["poses"]) != set(objects):
            raise ValueError(
                f"Incomplete or extra sampled parts in {scene.name}, frame {frame}"
            )
        for name, pose in sample["poses"].items():
            obj = objects[name]
            location, rotation, scale = presentation_matrix(pose["matrix"]).decompose()
            if (
                name in previous_quaternions
                and rotation.dot(previous_quaternions[name]) < 0
            ):
                rotation.negate()
            previous_quaternions[name] = rotation.copy()
            obj.location = location
            obj.rotation_quaternion = rotation
            obj.scale = scale
            obj.hide_render = not bool(pose["visible"])
            obj.hide_viewport = not bool(pose["visible"])
            for path in (
                "location",
                "rotation_quaternion",
                "scale",
                "hide_render",
                "hide_viewport",
            ):
                obj.keyframe_insert(
                    data_path=path, frame=frame, group="Sampled CAD pose"
                )
    for obj in objects.values():
        set_interpolation(obj)
    return objects


def camera_and_lighting(scene, specification):
    low, high = specification["focus"]
    corners = [
        MODEL_ROTATION @ Vector((x * MM_TO_M, y * MM_TO_M, z * MM_TO_M))
        for x in (low[0], high[0])
        for y in (low[1], high[1])
        for z in (low[2], high[2])
    ]
    centre = sum(corners, Vector()) / len(corners)
    diagonal = max((corner - centre).length for corner in corners) * 2
    span = max(diagonal, 0.015)
    direction = Vector((1.35, -1.8, -1.25)).normalized()
    if scene.name.startswith("03 "):
        # The oblique underside view exposes the gear mesh and horn together.
        direction = Vector((1.4, -1.5, -1.3)).normalized()
    elif scene.name.startswith("04 "):
        # Preserve a large screen-space component of axial bearing travel.
        direction = Vector((1.5, -0.7, 0.55)).normalized()
    elif scene.name.startswith("05 "):
        # Approach from outside the battery end, not through the propulsion.
        direction = Vector((-1.5, -1.0, -0.9)).normalized()
    elif scene.name.startswith("06 "):
        direction = Vector((1.5, 1.0, -0.9)).normalized()
    camera_data = bpy.data.cameras.new(scene.name + " | Camera")
    camera = bpy.data.objects.new(scene.name + " | Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = centre + direction * (span * 3 + 0.1)
    camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.clip_start = 0.0001
    camera_data.clip_end = max(100, span * 10)
    scene.camera = camera
    inverse = camera.rotation_euler.to_matrix().transposed()
    projected = [inverse @ (point - centre) for point in corners]
    dx = max(p.x for p in projected) - min(p.x for p in projected)
    dy = max(p.y for p in projected) - min(p.y for p in projected)
    camera_data.ortho_scale = 1
    unit_frame = camera_data.view_frame(scene=scene)
    unit_width = max(p.x for p in unit_frame) - min(p.x for p in unit_frame)
    unit_height = max(p.y for p in unit_frame) - min(p.y for p in unit_frame)
    camera_data.ortho_scale = max(dx / unit_width, dy / unit_height, 0.01) * 1.38
    right = Vector((0, 0, 1)).cross(direction).normalized()
    up = direction.cross(right).normalized()
    # Camera-relative soft lights illuminate the inspected faces. Powers scale
    # with area because these CAD meshes use actual metre-sized dimensions.
    for name, offset, power, size in (
        ("Key", direction * 2 + up * 1.4 - right * 0.8, 26, 1.5),
        ("Fill", direction * 1.5 - up * 0.3 + right * 1.8, 14, 1.8),
        ("Rim", -direction + up * 1.5 - right * 0.4, 20, 1.0),
    ):
        light_data = bpy.data.lights.new(scene.name + " | " + name, "AREA")
        light_data.energy = power * span * span
        light_data.shape = "DISK"
        light_data.size = size * span
        light = bpy.data.objects.new(light_data.name, light_data)
        scene.collection.objects.link(light)
        light.location = centre + Vector(offset) * span
        light.rotation_euler = (
            (centre - light.location).to_track_quat("-Z", "Y").to_euler()
        )
    return camera


def text_material():
    material = bpy.data.materials.new("Review annotation")
    material.diffuse_color = (0.86, 0.92, 0.97, 1)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (0.86, 0.92, 0.97, 1)
    emission.inputs["Strength"].default_value = 1
    material.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
    return material


def add_overlays(scene, specification, camera, material):
    frame = camera.data.view_frame(scene=scene)
    left, right = min(p.x for p in frame), max(p.x for p in frame)
    bottom, top = min(p.y for p in frame), max(p.y for p in frame)
    width, height = right - left, top - bottom

    def add_text(name, body, x, y, size):
        data = bpy.data.curves.new(name, "FONT")
        data.body = body
        data.size = size
        data.align_y = "TOP"
        data.materials.append(material)
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.parent = camera
        obj.location = (x, y, -0.02)
        obj.rotation_euler = (0, 0, 0)
        return obj

    add_text(
        scene.name + " | Title",
        specification.get("title", scene.name),
        left + width * 0.04,
        top - height * 0.04,
        height * 0.034,
    )
    add_text(
        scene.name + " | Limits",
        LIMIT_NOTE,
        left + width * 0.04,
        bottom + height * 0.04,
        height * 0.018,
    )
    markers = sorted(
        specification.get("markers", []), key=lambda marker: marker["frame"]
    )
    for index, marker in enumerate(markers):
        start = int(marker["frame"])
        end = (
            int(markers[index + 1]["frame"])
            if index + 1 < len(markers)
            else scene.frame_end + 1
        )
        obj = add_text(
            scene.name + f" | Stage {index + 1:02d}",
            str(marker["label"]),
            left + width * 0.04,
            top - height * 0.088,
            height * 0.021,
        )
        for at, hidden in ((scene.frame_start - 1, True), (start, False), (end, True)):
            obj.hide_render = hidden
            obj.hide_viewport = hidden
            obj.keyframe_insert(data_path="hide_render", frame=at)
            obj.keyframe_insert(data_path="hide_viewport", frame=at)
        set_interpolation(obj)


def configure_scene(scene, specification, metadata):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.fps = int(metadata.get("fps", 24))
    scene.render.fps_base = 1.0
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 1.0
    frames = specification["frames"]
    if isinstance(frames, list):
        scene.frame_start, scene.frame_end = int(frames[0]), int(frames[-1])
    else:
        scene.frame_start, scene.frame_end = 1, int(frames)
    if scene.frame_end < scene.frame_start:
        raise ValueError(f"Invalid frame interval in {scene.name}")
    scene["ReviewDescription"] = specification.get("description", "")
    scene["CADRevision"] = str(metadata.get("revision", ""))
    scene["CADSHA256"] = str(metadata.get("cad_sha256", ""))
    scene["SourceFingerprint"] = str(metadata.get("source_fingerprint", ""))
    scene["PresentationTransform"] = (
        "Rx(180 degrees), mm to m; engineering coordinates unchanged in source CAD"
    )
    scene["ReviewLimitations"] = LIMIT_NOTE
    world = bpy.data.worlds.new(scene.name + " | Neutral background")
    world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs["Color"].default_value = (
        0.045,
        0.057,
        0.072,
        1,
    )
    world.node_tree.nodes.get("Background").inputs["Strength"].default_value = 0.65
    scene.world = world
    for marker in specification.get("markers", []):
        scene.timeline_markers.new(str(marker["label"]), frame=int(marker["frame"]))


def usage_text(data):
    metadata = data["metadata"]
    lines = [
        "곤돌라 CAD 동작 검토 — Blender",
        "",
        "상단 Scene 목록에서 검토 장면을 선택하고, 3D 화면에 마우스를 둔 뒤 Space로 재생/정지합니다.",
        "타임라인을 드래그하여 자세를 확인합니다. 숫자패드 0은 검토 카메라 보기입니다.",
        "휠/가운데 버튼으로 자유롭게 확대·회전할 수 있습니다. F12는 현재 장면을 렌더링합니다.",
        "기본 Solid 화면에서 프로펠러 회전 영역은 선으로 표시되고, 렌더에서는 반투명 원판입니다.",
        "",
        "이는 원본 FreeCAD의 실제 부품과 샘플 자세를 사용하는 시각 검토입니다.",
        "장면마다 별도 오브젝트와 애니메이션을 사용하며, 동일한 부품의 메시만 공유합니다.",
        "입력 샘플 사이의 동작은 선형 보간입니다. 충돌 계산, 구조 해석, 공차·하중·마찰·배선 검증이 아닙니다.",
        "분해 장면은 명시된 순서와 가정에 따른 시각화이며, 구매 부품의 실제 작업성을 보증하지 않습니다.",
        "프로펠러는 회전 영역 원판이며 실제 날개나 공력 시뮬레이션이 아닙니다.",
        "표시 방향만 전체 X축 기준 180도 뒤집어 옵티컬 센서의 +Z 방향이 화면에서 아래를 향하게 했습니다.",
        "원본 CAD를 수정하지 않습니다. 구매/제작 판단에는 CAD와 기존 검증 보고서를 사용하세요.",
        "",
        "장면:",
    ]
    for scene in data["scenes"]:
        lines.append(f"- {scene['name']}: {scene.get('description', '')}")
    lines.extend(["", "출처:", json.dumps(metadata, ensure_ascii=False, indent=2)])
    text = bpy.data.texts.new("READ ME — 사용법과 검토 범위")
    text.write("\n".join(lines))
    manifest = bpy.data.texts.new("CAD review manifest.json")
    manifest.write(
        json.dumps(
            {
                "metadata": metadata,
                "scenes": [
                    {key: value for key, value in scene.items() if key != "samples"}
                    for scene in data["scenes"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def configure_workspace(default_scene):
    if bpy.context.window:
        bpy.context.window.scene = default_scene
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            space.shading.type = "SOLID"
            space.shading.color_type = "MATERIAL"
            space.shading.show_shadows = True
            space.shading.show_cavity = True
            space.shading.cavity_type = "BOTH"
            space.shading.background_type = "WORLD"
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.overlay.show_extras = False
            space.clip_start = 0.0001
            space.clip_end = 100
            space.region_3d.view_perspective = "CAMERA"
            space.region_3d.view_camera_zoom = 0


def main():
    args = arguments()
    data = json.loads(args.input.read_text())
    if data["metadata"].get("units") != "mm":
        raise ValueError("Expected millimetre CAD coordinates")
    if not data["scenes"]:
        raise ValueError("No review scenes provided")
    # Start from a clean process, without touching the user's saved preferences.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    original_scenes = list(bpy.data.scenes)
    meshes = build_meshes(data["parts"])
    parts = {part["name"]: part for part in data["parts"]}
    annotation_material = text_material()
    scenes = []
    for specification in data["scenes"]:
        scene = bpy.data.scenes.new(specification["name"])
        configure_scene(scene, specification, data["metadata"])
        make_cad_objects(scene, specification, parts, meshes)
        camera = camera_and_lighting(scene, specification)
        add_overlays(scene, specification, camera, annotation_material)
        scene.frame_set(scene.frame_start)
        scenes.append(scene)
    default_scene = next(
        (scene for scene in scenes if scene.name == "02 Independent tilt"), scenes[0]
    )
    configure_workspace(default_scene)
    for scene in original_scenes:
        bpy.data.scenes.remove(scene)
    usage_text(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    print(f"BLENDER_REVIEW_SAVED {args.output.resolve()}")
    if args.render_stills:
        args.render_stills.mkdir(parents=True, exist_ok=True)
        for scene in scenes:
            if bpy.context.window:
                bpy.context.window.scene = scene
            frame = (scene.frame_start + scene.frame_end) // 2
            scene.frame_set(frame)
            filename = re.sub(r"[^A-Za-z0-9._-]+", "_", scene.name).strip("_")
            scene.render.filepath = str(
                (args.render_stills / (filename + ".png")).resolve()
            )
            bpy.ops.render.render(write_still=True, scene=scene.name)
            scene.frame_set(scene.frame_start)
            print(f"BLENDER_REVIEW_STILL {scene.render.filepath}")
        configure_workspace(default_scene)
        # Preserve the initial playback frame when the reviewed file is opened.
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))


if __name__ == "__main__":
    main()
