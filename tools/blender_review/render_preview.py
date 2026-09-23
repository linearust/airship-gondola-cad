"""Render an existing review scene to MP4 without saving or changing the blend.

Use Blender's Python runtime after ``--``. All frames are rendered at the saved
24 fps, so the review's duration and removal visibility sequence are preserved.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import bpy


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scene", default="02 Independent tilt")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument(
        "--start", type=int, help="Optional first frame for a short preview"
    )
    parser.add_argument(
        "--end", type=int, help="Optional last frame for a short preview"
    )
    return parser.parse_args(argv)


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def mp4_duration(path):
    """Read the movie duration from the standard MP4 moov/mvhd header."""
    data = path.read_bytes()

    def boxes(start, stop):
        offset = start
        while offset + 8 <= stop:
            size, kind = struct.unpack_from(">I4s", data, offset)
            header = 8
            if size == 1:
                size = struct.unpack_from(">Q", data, offset + 8)[0]
                header = 16
            elif size == 0:
                size = stop - offset
            if size < header or offset + size > stop:
                raise ValueError("Malformed MP4 box")
            yield kind, offset + header, offset + size
            offset += size

    for kind, start, stop in boxes(0, len(data)):
        if kind != b"moov":
            continue
        for child, body, _ in boxes(start, stop):
            if child != b"mvhd":
                continue
            version = data[body]
            if version == 0:
                timescale, duration = struct.unpack_from(">II", data, body + 12)
            elif version == 1:
                timescale, duration = struct.unpack_from(">IQ", data, body + 20)
            else:
                raise ValueError("Unsupported MP4 movie-header version")
            if timescale == 0:
                raise ValueError("Invalid MP4 movie timescale")
            return duration / timescale
    raise ValueError("MP4 movie header is missing")


def main():
    args = arguments()
    blend, output = (
        args.blend.expanduser().resolve(),
        args.output.expanduser().resolve(),
    )
    if not blend.is_file():
        raise FileNotFoundError(blend)
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must have an .mp4 extension")
    if any(value < 2 or value % 2 for value in (args.width, args.height)):
        raise ValueError("H.264 preview dimensions must be positive even integers")
    if args.samples < 1:
        raise ValueError("Render samples must be positive")
    before = file_hash(blend)
    try:
        bpy.ops.wm.open_mainfile(filepath=str(blend))
        scene = bpy.data.scenes.get(args.scene)
        if scene is None:
            raise ValueError(f"Unknown review scene: {args.scene}")
        if scene.camera is None:
            raise ValueError("The selected scene has no review camera")
        fps = scene.render.fps / scene.render.fps_base
        if abs(fps - 24) > 1e-8:
            raise ValueError(
                "Expected a saved 24 fps review; refusing to change its timing"
            )
        start = scene.frame_start if args.start is None else args.start
        end = scene.frame_end if args.end is None else args.end
        if not scene.frame_start <= start <= end <= scene.frame_end:
            raise ValueError("Preview frame range must stay inside the saved scene")
        scene.frame_start, scene.frame_end, scene.frame_step = start, end, 1
        scene.render.engine = "BLENDER_EEVEE"
        scene.render.resolution_x, scene.render.resolution_y = args.width, args.height
        scene.render.resolution_percentage = 100
        if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = args.samples
        if hasattr(scene.render.image_settings, "media_type"):
            scene.render.image_settings.media_type = "VIDEO"
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.ffmpeg_preset = "GOOD"
        scene.render.ffmpeg.audio_codec = "NONE"
        scene.render.use_file_extension = True
        scene.render.filepath = str(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        bpy.context.window.scene = scene
        scene.frame_set(start)
        bpy.context.view_layer.update()
        bpy.ops.render.render(animation=True, scene=scene.name)
        duration = mp4_duration(output)
        expected = (end - start + 1) / fps
        if abs(duration - expected) > 1 / fps:
            raise RuntimeError(
                f"Unexpected video duration: {duration} versus {expected} s"
            )
        print(
            json.dumps(
                {
                    "output": str(output),
                    "scene": scene.name,
                    "frames": [start, end],
                    "fps": fps,
                    "duration_seconds": duration,
                    "expected_duration_seconds": expected,
                    "source_blend_sha256": before,
                    "scope": "Rendered prescribed CAD poses; no physics simulation or model changes.",
                },
                indent=2,
            )
        )
    finally:
        if file_hash(blend) != before:
            raise RuntimeError("Source blend changed during preview rendering")


if __name__ == "__main__":
    main()
