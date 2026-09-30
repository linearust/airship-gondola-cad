#!/usr/bin/env python3
"""Export an optional three-piece paired rail/frame/saddle fit coupon.

Run with normal Python after validating the saved CAD. The destination must be
new; no installed CAD, standard print manifest or source file is overwritten.
"""

import argparse
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gondola.provenance import file_sha256  # noqa: E402
from tools.cad_snapshot import open_validated_cad, write_json_atomic  # noqa: E402

PARTS = {
    "RailPairCoupon": ("ContinuousRail", (62, 28, 12.5)),
    "FrameJointCoupon": ("PropulsionFixedFrame", (62, 28, 12.5)),
    "SaddleJointCoupon": ("ServoDriveBridge", (62, 28, 14.5)),
}
TOL = 1e-6


def dimensions(shape):
    bounds = shape.optimalBoundingBox(False, False)
    return [bounds.XLength, bounds.YLength, bounds.ZLength]


def extract(doc):
    """Crop saved geometry in the propulsion frame; never call part builders."""
    import FreeCAD as App
    import Part

    from gondola.cad import world_shape
    from gondola.print_export import is_single_closed_solid

    inverse = doc.MainPropulsionModule.getGlobalPlacement().inverse()
    result = {}
    for name, (source_name, size) in PARTS.items():
        source = doc.getObject(source_name)
        if source is None or not hasattr(source, "PrintRotation"):
            raise ValueError("Missing source print: " + source_name)
        shape = world_shape(source)
        shape.Placement = inverse.multiply(shape.Placement)
        # PrintRotation refers to the source part's axes. Translation is safe;
        # rotating the crop frame would require explicitly composing rotations.
        if abs(shape.Placement.Rotation.Angle) > TOL:
            raise ValueError("Source part axes changed: " + source_name)
        crop = Part.makeBox(*size, App.Vector(-31, -14, 0))
        cropped = shape.common(crop).removeSplitter()
        if not is_single_closed_solid(cropped):
            raise ValueError("Crop is not one closed solid: " + source_name)
        result[name] = (source, cropped)
    return result


def joint_checks(shapes):
    """Literal contact areas and clear bores, independent of coupon construction."""
    import FreeCAD as App
    import Part

    from gondola.validation.servo_module import (
        _plane_contact_area,
        bridge_wrap_check,
    )

    rail, frame, saddle = (shapes[name] for name in PARTS)
    wrap = bridge_wrap_check(frame, saddle)
    contacts = []
    for first, second, axis, station, area, region in (
        (frame, saddle, 2, 12.5, 396, (-9, -11, 0, 18, 22, 20)),
        (frame, saddle, 1, -5.25, 206 - math.pi * 1.7**2, None),
        (frame, saddle, 1, 5.25, 206 - math.pi * 1.7**2, None),
        (rail, frame, 2, 10.5, 60, (5, -14, 0, 24, 28, 20)),
        (rail, frame, 2, 10.5, 60, (-29, -14, 0, 24, 28, 20)),
    ):
        if region is not None:
            x, y, z, *size = region
            tool = Part.makeBox(*size, App.Vector(x, y, z))
            first, second = first.common(tool), second.common(tool)
        actual = _plane_contact_area(first, second, axis, station)
        contacts.append(
            {
                "axis": axis,
                "plane_mm": station,
                "area_mm2": actual,
                "required_mm2": area,
                "passed": actual >= area - TOL,
            }
        )
    bores = []
    for x in (-17, 17):
        tool = Part.makeCylinder(1.5, 28, App.Vector(x, -14, 7), App.Vector(0, 1, 0))
        volumes = {
            name: abs(shape.common(tool).Volume) for name, shape in shapes.items()
        }
        bores.append(
            {
                "axis_x_mm": x,
                "obstruction_mm3": volumes,
                "passed": all(value < TOL for value in volumes.values()),
            }
        )
    overlaps = [
        abs(a.common(b).Volume)
        for a, b in ((rail, frame), (frame, saddle), (rail, saddle))
    ]
    return {
        "wrap": wrap,
        "contacts": contacts,
        "M3_bores": bores,
        "pair_overlap_mm3": overlaps,
        "passed": wrap["passed"]
        and all(row["passed"] for row in contacts + bores)
        and all(value < TOL for value in overlaps),
    }


def export(cad, output_dir):
    import FreeCAD as App
    import Mesh
    import Part

    from gondola.cad import set_property
    from gondola.print_export import (
        mesh_checks,
        mesh_from_shape,
        print_shape,
        print_size_check,
        print_solid_comparison,
    )
    from gondola.print_materials import PRINT_METADATA, print_filename
    from gondola.validation.geometry import compare_mesh_surfaces

    cad, output_dir = Path(cad).resolve(), Path(output_dir).resolve()
    if output_dir.exists():
        raise ValueError("Use a new, separate coupon output directory.")
    tool_hashes = {
        Path(__file__): file_sha256(__file__),
        ROOT / "tools/cad_snapshot.py": file_sha256(ROOT / "tools/cad_snapshot.py"),
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".joint-coupon-", dir=output_dir.parent
    ) as tmp:
        folder = Path(tmp)
        with open_validated_cad(cad, output_dir / "manifest.json") as snapshot:
            crops = extract(snapshot.doc)
            checks = joint_checks({name: row[1] for name, row in crops.items()})
            if not checks["passed"]:
                raise ValueError(
                    "Paired joint no longer matches reviewed coupon: " + str(checks)
                )
            coupon = App.newDocument("PairedJointFitCoupon")
            rows = []
            try:
                for name, (source, shape) in crops.items():
                    obj = coupon.addObject("Part::Feature", name)
                    obj.Shape = shape
                    obj.Label = "OPTIONAL FIT COUPON | " + name
                    set_property(
                        obj,
                        "PrintRotation",
                        source.PrintRotation,
                        "App::PropertyRotation",
                    )
                    for key in PRINT_METADATA:
                        set_property(obj, key, str(getattr(source, key)))
                    set_property(obj, "SourceObject", source.Name)
                    oriented = print_shape(obj)
                    mesh = mesh_from_shape(oriented)
                    stl, step = (print_filename(name, ext) for ext in ("stl", "step"))
                    mesh.write(str(folder / stl))
                    oriented.exportStep(str(folder / step))
                    mesh_check = mesh_checks(oriented, Mesh.Mesh(str(folder / stl)))
                    surface = compare_mesh_surfaces(Mesh.Mesh(str(folder / stl)), mesh)
                    step_check = print_solid_comparison(
                        oriented, Part.read(str(folder / step)), TOL
                    )
                    sizes = print_size_check(dimensions(shape), dimensions(oriented))
                    if not (
                        all(mesh_check.values())
                        and mesh_check["solid_count"] == 1
                        and mesh_check["mesh_components"] == 1
                        and surface["passed"]
                        and step_check["passed"]
                        and sizes["passed"]
                    ):
                        raise ValueError("Export verification failed: " + name)
                    rows.append(
                        {
                            "name": name,
                            "source_object": source.Name,
                            "quantity": 1,
                            "installed_quantity": 0,
                            "print_rotation_quaternion": list(source.PrintRotation.Q),
                            "local_size_mm": dimensions(shape),
                            "export_size_mm": dimensions(oriented),
                            "size_checks": sizes,
                            "mesh_checks": mesh_check,
                            "stl_surface_comparison": surface,
                            "step_comparison": step_check,
                            "files": [stl, step],
                        }
                    )
                native = folder / "paired_joint_coupon.FCStd"
                coupon.recompute()
                coupon.saveAs(str(native))
            finally:
                App.closeDocument(coupon.Name)
            saved = App.openDocument(str(native))
            try:
                for row in rows:
                    name = row["name"]
                    check = print_solid_comparison(
                        saved.getObject(name).Shape, crops[name][1], TOL
                    )
                    row["saved_crop_comparison"] = check
                    if (
                        not check["passed"]
                        or list(saved.getObject(name).PrintRotation.Q)
                        != row["print_rotation_quaternion"]
                    ):
                        raise ValueError(
                            "Native crop or print rotation changed: " + name
                        )
            finally:
                App.closeDocument(saved.Name)
            manifest = {
                "schema_version": 1,
                "units": "mm",
                "optional_fit_coupon": True,
                "basis": {
                    **snapshot.provenance(),
                    "exporter_sha256": tool_hashes[Path(__file__)],
                    "snapshot_helper_sha256": tool_hashes[
                        ROOT / "tools/cad_snapshot.py"
                    ],
                },
                "coordinate_frame": "Saved MainPropulsionModule local frame; assembled coupon poses.",
                "hardware": "Reuse two intended M3x12 screws and two M3 nuts; no additional hardware purchase or installed parts.",
                "limits": "Cropped fit specimen only: simultaneous rail seating, U-guide fit, nut/head access and opposed closure. Match each source part's production print orientation, material, process and finish. Truncated stock does not reproduce whole-frame stiffness, rail curvature, adhesion, creep, fatigue or operating strength; no physical fit qualification is implied.",
                "source_crop_boxes": {
                    name: {"origin_mm": [-31, -14, 0], "size_mm": list(spec[1])}
                    for name, spec in PARTS.items()
                },
                "checks": checks,
                "parts": rows,
                "artifacts": {
                    path.name: file_sha256(path) for path in sorted(folder.iterdir())
                },
                "passed": True,
            }
        snapshot.assert_unchanged()
        if any(file_sha256(path) != digest for path, digest in tool_hashes.items()):
            raise RuntimeError("Coupon export tools changed during export.")
        write_json_atomic(folder / "manifest.json", manifest, indent=2)
        snapshot.assert_unchanged()
        folder.rename(output_dir)
    print("Optional paired joint coupon: " + str(output_dir))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cad", type=Path, default=ROOT / "build/gondola.FCStd")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "build/paired_joint_fit_coupon"
    )
    parser.add_argument("--native", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.native:
        export(args.cad, args.output_dir)
        return
    from gondola.freecad_runtime import locate_appimage, mounted_appimage

    with mounted_appimage(locate_appimage()) as mount:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(mount / "usr/lib")))
        subprocess.run(
            [
                str(mount / "AppRun"),
                "python",
                __file__,
                "--native",
                "--cad",
                str(args.cad.resolve()),
                "--output-dir",
                str(args.output_dir.resolve()),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )


if __name__ == "__main__":
    main()
