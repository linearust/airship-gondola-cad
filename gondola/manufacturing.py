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
            and bounds.XLength <= 340
            and bounds.YLength <= 340
            and bounds.ZLength <= 280
        ):
            raise RuntimeError(
                "Invalid PA12 print part or outside shared SLS/MJF envelope "
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
        "process": "PA12 SLS/MJF; agree the process with supplier",
        "manufacturing_release_status": "FIT PROTOTYPE ONLY: narrow rail flexures need supplier acceptance; actual RS1102 mounting and DS-M005 horn torque connection remain unfinished.",
        "published_machine_envelope_mm": {
            "SLS": [340, 340, 600],
            "MJF": [380, 380, 280],
        },
        "thin_flexure_exception": "The1mm continuous narrow rail base needs supplier review; nominal0.8mm minimum is not blanket compliance with3mm long/broad SLS PA12 guidance.",
        "one_piece_acceptance": "Supplier must confirm the378mm rail as one piece; published guide is not a manufacturing acceptance.",
        "unique_stl_count": len(entries),
        "installed_printed_part_count": len(installed),
        "additional_coupon_printed_part_count": len(coupons),
        "instructions": "Each STL/STEP is one unique PRINTED design; print installed_quantity. Coupons are extra. Purchased hardware is excluded. Layout document is an overview, not a nested machine job.",
        "parts": entries,
    }
    (folder / "print_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    App.setActiveDocument(assembly.Name)
    return manifest


def export_hardware_bom(objects, out, stem):
    """Group bought instances by both metric specification and material."""
    buckets = {}
    for obj in objects:
        material = str(getattr(obj, "MaterialSelection", "Unspecified"))
        if "Nylon" in material or "nylon" in material:
            material_code = "PA66"
        elif "A2" in material:
            material_code = "A2"
        else:
            material_code = material
        buckets.setdefault((str(obj.HardwareSKU), material_code), []).append(obj)

    rows = []
    for (sku, material_code), instances in buckets.items():
        obj = instances[0]
        rows.append(
            {
                "sku": sku,
                "purchase_code": sku + "_" + material_code,
                "quantity": len(instances),
                "label": obj.Label,
                "thread_descriptions": sorted(
                    {str(getattr(part, "ThreadStandard", "")) for part in instances}
                ),
                "material": str(
                    getattr(obj, "MaterialSelection", "Stainless steel for rail clamp")
                ),
                "sources": sorted(
                    {str(getattr(part, "SourceURL", "")) for part in instances}
                ),
                "notes": str(getattr(obj, "Notes", "")),
                "purchase_search_query": str(getattr(obj, "PurchaseSearchQuery", "")),
                "purchase_search_url": str(getattr(obj, "PurchaseSearchURL", "")),
                "purchase_requirements": str(getattr(obj, "PurchaseRequirements", "")),
                "purchase_candidate_url": str(getattr(obj, "PurchaseCandidateURL", "")),
                "purchase_evidence_notes": str(
                    getattr(obj, "PurchaseEvidenceNotes", "")
                ),
                "purchasing_status": str(getattr(obj, "PurchasingStatus", "")),
                "instances": [part.Name for part in instances],
            }
        )
    result = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "source_fingerprint": source_fingerprint(),
        "purchased_hardware_quantity": len(objects),
        "unique_purchase_spec_count": len(rows),
        "all_threads": "M3 x0.5 ISO metric coarse for the new mechanical hardware. OEM motor/horn screws remain unverified.",
        "color": "Gold = purchased hardware; not a material or finish specification.",
        "purchasing_status": "Specifications and source drawings; no marketplace SKU or seller lot verified.",
        "items": rows,
    }
    Path(out, stem + "_hardware_bom.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    return result
