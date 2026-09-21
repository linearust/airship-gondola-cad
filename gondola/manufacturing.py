"""Export only unique printed solids; purchased hardware gets its own BOM.

The source FreeCAD assembly is authoritative. STL and STEP files are generated
from its local part geometry, never from equipment or hardware envelopes.
"""

import json
import math
import re
from pathlib import Path

import FreeCAD as App
import MeshPart

from .config import ARTIFACT_SCHEMA_VERSION
from .design_contract import (
    MANUFACTURING_DECISION,
    PUBLISHED_PROCESS_SIZE_MM,
    RAIL_LENGTH_MM,
    release_status,
)
from .provenance import file_sha256, source_fingerprint

MESH_PARAMETERS = {
    "linear_deflection_mm": 0.04,
    "angular_deflection_rad": 0.12,
    "relative": False,
}


def mesh_from_shape(shape):
    """Use one tessellation contract for export and independent validation."""
    return MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=MESH_PARAMETERS["linear_deflection_mm"],
        AngularDeflection=MESH_PARAMETERS["angular_deflection_rad"],
        Relative=MESH_PARAMETERS["relative"],
    )


def print_shape(obj):
    """Orient a local part for manufacture and put its exact minimum at zero."""
    shape = obj.Shape.copy()
    rotation = obj.PrintRotation
    shape.rotate(App.Vector(), rotation.Axis, math.degrees(rotation.Angle))
    # Legacy BoundBox may overestimate trimmed curves. Exact extrema keep the
    # export on Z=0 and are essential when comparing repeated printed parts.
    bounds = shape.optimalBoundingBox(False, False)
    shape.translate(App.Vector(-bounds.XMin, -bounds.YMin, -bounds.ZMin))
    return shape


def _boundary_signature(shape):
    """Typed trimmed boundaries provide a fallback for OCC empty-cut failures.

    Identical faceted solids can raise 'Null shape' on subtraction. Compare
    face and wire structure plus five points per edge at 1e-5 mm precision;
    callers also require valid solids, equal exact bounds and equal volume.
    """

    def point(vector):
        return tuple(round(component, 5) for component in vector)

    def edge_signature(edge):
        return (
            edge.Curve.__class__.__name__,
            tuple(sorted(point(p) for p in edge.discretize(Number=5))),
        )

    return sorted(
        (
            face.Surface.__class__.__name__,
            round(face.Area, 5),
            point(face.CenterOfMass),
            tuple(
                sorted(
                    tuple(sorted(edge_signature(edge) for edge in wire.Edges))
                    for wire in face.Wires
                )
            ),
        )
        for face in shape.Faces
    )


def geometry_comparison(first, second):
    """Compare solid geometry, accepting no nonempty symmetric difference."""
    first_bounds = first.optimalBoundingBox(False, False)
    second_bounds = second.optimalBoundingBox(False, False)
    bounds_delta = max(
        abs(getattr(first_bounds, name) - getattr(second_bounds, name))
        for name in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
    )
    volume_delta = abs(first.Volume - second.Volume)
    if (
        first.isValid()
        and second.isValid()
        and bounds_delta < 1e-6
        and volume_delta < 1e-6
    ):
        if _boundary_signature(first) == _boundary_signature(second):
            return {
                "difference_mm3": 0.0,
                "method": "equal typed face/wire/edge boundary signatures at1e-5mm with exact bounds and volume agreement",
                "bounds_difference_mm": bounds_delta,
                "volume_difference_mm3": volume_delta,
            }
    cuts = [first.cut(second), second.cut(first)]
    difference = sum(0.0 if shape.isNull() else abs(shape.Volume) for shape in cuts)
    return {
        "difference_mm3": difference,
        "method": "BRep symmetric difference",
        "bounds_difference_mm": bounds_delta,
        "volume_difference_mm3": volume_delta,
    }


def mesh_checks(shape, mesh):
    """Check mesh connectivity and preserve orientation diagnostics.

    Downward-face area is informational only for powder-bed PA12; it is not a
    support requirement or a replacement for the manufacturer's build setup.
    """
    base_area, overhang_area = 0.0, 0.0
    for facet in mesh.Facets:
        points = [App.Vector(*point) for point in facet.Points]
        normal = facet.Normal
        area = (points[1] - points[0]).cross(points[2] - points[0]).Length / 2
        if normal.z < -0.99 and max(point.z for point in points) < 1e-4:
            base_area += area
        if (
            normal.z < -math.sqrt(0.5) - 1e-5
            and max(point.z for point in points) > 0.201
        ):
            overhang_area += area
    return {
        "valid_brep": shape.isValid(),
        "solid_count": len(shape.Solids),
        "watertight_mesh": mesh.isSolid(),
        "mesh_components": mesh.countComponents(),
        "bed_contact_area_mm2": base_area,
        "steep_downward_face_area_above_first_layer_mm2": overhang_area,
        "overhang_check_is_slicer_replacement": False,
    }


def print_entry_inventory_check(entry, installed, coupons):
    """Bind each manifest quantity and SKU to the saved native registry roles."""
    installed_by_name = {obj.Name: obj for obj in installed}
    coupons_by_name = {obj.Name: obj for obj in coupons}
    native = {**installed_by_name, **coupons_by_name}
    names = entry["instances"]
    expected_installed = sum(name in installed_by_name for name in names)
    expected_coupons = sum(name in coupons_by_name for name in names)
    known = all(name in native for name in names)
    skus_match = known and all(
        str(getattr(native[name], "PrintSKU", native[name].Name)) == entry["sku"]
        for name in names
    )
    print_flags_match = known and all(
        bool(getattr(native[name], "PrintPart", False)) for name in names
    )
    quantities_match = (
        type(entry["quantity"]) is int
        and type(entry["installed_quantity"]) is int
        and type(entry["coupon_quantity"]) is int
        and entry["quantity"] == len(names)
        and entry["installed_quantity"] == expected_installed
        and entry["coupon_quantity"] == expected_coupons
    )
    disjoint_roles = not (set(installed_by_name) & set(coupons_by_name))
    return {
        "native_installed_quantity": expected_installed,
        "native_coupon_quantity": expected_coupons,
        "known_native_instances": known,
        "native_print_skus_match": skus_match,
        "native_print_flags_match": print_flags_match,
        "quantities_match_native_roles": quantities_match,
        "passed": bool(names)
        and len(set(names)) == len(names)
        and disjoint_roles
        and known
        and skus_match
        and print_flags_match
        and quantities_match,
    }


def export_print_parts(assembly, installed, coupons, out, stem):
    """Export one STL/STEP per verified print SKU and record all quantities."""
    out = Path(out)
    folder = out / (stem + "_print_parts")
    folder.mkdir(exist_ok=True)
    for extension in ("*.stl", "*.step"):
        for path in folder.glob(extension):
            path.unlink()

    buckets = {}
    for obj in list(installed) + list(coupons):
        if "Purchased" in str(getattr(obj, "Role", "")):
            raise RuntimeError("Purchased part in print list: " + obj.Name)
        buckets.setdefault(str(getattr(obj, "PrintSKU", obj.Name)), []).append(obj)

    layout = App.newDocument("GondolaPrintParts")
    layout.Label = "PA12 SLS/MJF individual print files and quantities"
    entries = []
    x = y = row_depth = 0
    for sku, instances in buckets.items():
        obj = instances[0]
        shape = print_shape(obj)
        bounds = shape.optimalBoundingBox(False, False)
        duplicate_checks = []
        for other in instances[1:]:
            check = geometry_comparison(shape, print_shape(other))
            duplicate_checks.append({"instance": other.Name, **check})
            if check["difference_mm3"] > 1e-6:
                raise RuntimeError("Different parts share SKU " + sku)

        mesh = mesh_from_shape(shape)
        checks = mesh_checks(shape, mesh)
        if not (
            checks["valid_brep"]
            and checks["solid_count"] == 1
            and checks["watertight_mesh"]
            and checks["mesh_components"] == 1
            and all(
                size
                <= min(limits[axis] for limits in PUBLISHED_PROCESS_SIZE_MM.values())
                for axis, size in enumerate(
                    (bounds.XLength, bounds.YLength, bounds.ZLength)
                )
            )
        ):
            raise RuntimeError(
                "Invalid PA12 print part or outside shared SLS/MJF size screen "
                + sku
                + str(checks)
            )

        file_stem = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", sku).lower()
        filename = file_stem + ".stl"
        step_filename = file_stem + ".step"
        mesh.write(str(folder / filename))
        shape.exportStep(str(folder / step_filename))
        # The native overview is for inspection, not a nested machine job.
        if x and x + bounds.XLength > 380:
            x, y, row_depth = 0, y + row_depth + 15, 0
        view_shape = shape.copy()
        view_shape.translate(App.Vector(x, y, 0))
        item = layout.addObject("Part::Feature", sku)
        item.Shape = view_shape
        installed_quantity = sum(part in installed for part in instances)
        coupon_quantity = sum(part in coupons for part in instances)
        item.Label = (
            f"{sku} | installed {installed_quantity} + sample {coupon_quantity}"
        )
        for key, value in [
            ("Quantity", len(instances)),
            ("InstalledQuantity", installed_quantity),
        ]:
            item.addProperty("App::PropertyInteger", key, "Manufacturing")
            setattr(item, key, value)
        if App.GuiUp:
            item.ViewObject.ShapeColor = (0.32, 0.67, 0.77)
            item.ViewObject.DisplayMode = "Flat Lines"

        entries.append(
            {
                "sku": sku,
                "file": filename,
                "file_sha256": file_sha256(folder / filename),
                "step_file": step_filename,
                "step_sha256": file_sha256(folder / step_filename),
                "quantity": len(instances),
                "installed_quantity": installed_quantity,
                "coupon_quantity": coupon_quantity,
                "instances": [part.Name for part in instances],
                "size_mm": [bounds.XLength, bounds.YLength, bounds.ZLength],
                "single_part_volume_cm3": shape.Volume / 1000,
                "duplicate_geometry_verification": duplicate_checks,
                "process": "PA12 SLS/MJF powder-bed process",
                "supports_required": False,
                "support_notes": "Powder supports the part. FDM overhang diagnostics do not apply to SLS/MJF.",
                "print_notes": str(getattr(obj, "PrintNotes", "")),
                "checks": checks,
            }
        )
        x += bounds.XLength + 15
        row_depth = max(row_depth, bounds.YLength)

    layout.recompute()
    layout.saveAs(str(out / (stem + "_print_parts.FCStd")))
    manifest = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "source_fingerprint": source_fingerprint(),
        "mesh_parameters": MESH_PARAMETERS,
        "units": "mm",
        "process": "PA12 SLS preferred; MJF alternative; agree the process with Creallo",
        "manufacturing_decision": MANUFACTURING_DECISION,
        "manufacturing_release_status": "CAD checks do not qualify manufacture or physical interfaces; see release_status for every unresolved interface.",
        "release_status": release_status(),
        "published_fabrication_size_mm": PUBLISHED_PROCESS_SIZE_MM,
        "size_screen_is_one_piece_acceptance": False,
        "thin_flexure_exception": "The1.2mm continuous narrow rail base needs supplier review; nominal0.8mm minimum is not blanket compliance with3mm long/broad PA12 guidance for SLS/MJF.",
        "one_piece_acceptance": f"Supplier must confirm the {RAIL_LENGTH_MM:g}mm rail as one piece; published guide includes split-and-join fabrication and is not a manufacturing acceptance.",
        "unique_stl_count": len(entries),
        "installed_printed_part_count": len(installed),
        "additional_coupon_printed_part_count": len(coupons),
        "instructions": "Each STL/STEP is one unique PRINTED design; print installed_quantity. Coupons are extra. Purchased hardware is excluded. Layout document is an overview, not a nested machine job.",
        "parts": entries,
    }
    (folder / "print_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    App.setActiveDocument(assembly.Name)
    return manifest
