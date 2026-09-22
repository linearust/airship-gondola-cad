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
from .contracts.design import (
    MANUFACTURING_DECISION,
    MAX_PRINT_PART_DIMENSION_MM,
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
SIZE_NUMERICAL_TOLERANCE_MM = 1e-5
PRINT_PROCESS_DESCRIPTION = "PA12 SLS/MJF; process agreement pending"


def _valid_dimensions(dimensions):
    return (
        isinstance(dimensions, (list, tuple))
        and len(dimensions) == 3
        and all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value > 0
            for value in dimensions
        )
    )


def print_size_check(local_dimensions_mm, export_dimensions_mm):
    """Screen numeric XYZ bounds before and after print rotation independently.

    The small tolerance covers numeric bounds arithmetic, not fabrication.
    Published envelopes do not establish one-piece supplier acceptance.
    """
    local_valid = _valid_dimensions(local_dimensions_mm)
    export_valid = _valid_dimensions(export_dimensions_mm)
    local_passed = local_valid and max(local_dimensions_mm) <= (
        MAX_PRINT_PART_DIMENSION_MM + SIZE_NUMERICAL_TOLERANCE_MM
    )
    export_passed = export_valid and max(export_dimensions_mm) <= (
        MAX_PRINT_PART_DIMENSION_MM + SIZE_NUMERICAL_TOLERANCE_MM
    )
    published = {
        process: export_valid
        and all(
            size <= limit + SIZE_NUMERICAL_TOLERANCE_MM
            for size, limit in zip(export_dimensions_mm, limits)
        )
        for process, limits in PUBLISHED_PROCESS_SIZE_MM.items()
    }
    return {
        "dimensions_valid": local_valid and export_valid,
        "local_part_within_limit": local_passed,
        "oriented_part_within_limit": export_passed,
        "within_published_fabrication_size": published,
        "passed": local_passed and export_passed and all(published.values()),
    }


def _size_summary(local_sizes_mm, export_sizes_mm):
    checks = [
        print_size_check(size, export_sizes_mm.get(name))
        for name, size in local_sizes_mm.items()
    ]
    return {
        "all_native_instances_within_limit": bool(checks)
        and all(row["local_part_within_limit"] for row in checks),
        "all_oriented_instances_within_limit": bool(checks)
        and all(row["oriented_part_within_limit"] for row in checks),
        "within_published_fabrication_size": {
            process: bool(checks)
            and all(row["within_published_fabrication_size"][process] for row in checks)
            for process in PUBLISHED_PROCESS_SIZE_MM
        },
        "passed": bool(checks) and all(row["passed"] for row in checks),
    }


def _dimensions_match(first, second):
    return (
        _valid_dimensions(first)
        and _valid_dimensions(second)
        and all(
            abs(a - b) <= SIZE_NUMERICAL_TOLERANCE_MM for a, b in zip(first, second)
        )
    )


def print_size_declaration_check(entry, local_sizes_mm, export_sizes_mm, stl_size_mm):
    """Compare manifest claims with recomputed native bounds and real STL bounds."""
    declared = entry.get("local_sizes_mm")
    local_match = (
        isinstance(declared, dict)
        and declared.keys() == local_sizes_mm.keys()
        and all(
            _dimensions_match(declared[name], size)
            for name, size in local_sizes_mm.items()
        )
    )
    native_checks = _size_summary(local_sizes_mm, export_sizes_mm)
    stl_checks = _size_summary(
        local_sizes_mm, {name: stl_size_mm for name in local_sizes_mm}
    )
    export_match = all(
        _dimensions_match(entry.get("size_mm"), size)
        for size in export_sizes_mm.values()
    ) and bool(export_sizes_mm)
    checks_match = entry.get("size_checks") == native_checks
    return {
        "actual_local_sizes_mm": local_sizes_mm,
        "actual_native_export_sizes_mm": export_sizes_mm,
        "local_sizes_match_manifest": local_match,
        "export_size_matches_manifest": export_match,
        "size_checks_match_manifest": checks_match,
        "native_size_checks": native_checks,
        "actual_stl_size_checks": stl_checks,
        "passed": local_match
        and export_match
        and checks_match
        and native_checks["passed"]
        and stl_checks["passed"],
    }


def local_part_dimensions(obj):
    """Measure native local axes with neither placement nor PrintRotation applied."""
    shape = obj.Shape.copy()
    shape.Placement = App.Placement()
    bounds = shape.optimalBoundingBox(False, False)
    return [bounds.XLength, bounds.YLength, bounds.ZLength]


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


def _topologically_empty(shape):
    """Empty compounds count as empty; zero-volume faces and wires do not."""
    return shape.isNull() or not any(
        getattr(shape, topology)
        for topology in ("Solids", "Shells", "Faces", "Wires", "Edges", "Vertexes")
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
                "closed_solid_identity_by_empty_cuts": False,
            }
    cuts = [first.cut(second), second.cut(first)]
    difference = sum(0.0 if shape.isNull() else abs(shape.Volume) for shape in cuts)
    # FreeCAD's Volume uses OCC's nonadaptive integral. STEP reparameterization
    # can change that scalar slightly despite identical solid boundaries. Only
    # actual empty topology in BOTH directions certifies this alternative;
    # retain the raw volume discrepancy for diagnosis.
    empty_cut_identity = all(
        shape.isValid() and len(shape.Solids) == 1 and shape.isClosed()
        for shape in (first, second)
    ) and all(_topologically_empty(shape) for shape in cuts)
    return {
        "difference_mm3": difference,
        "method": "BRep symmetric difference",
        "bounds_difference_mm": bounds_delta,
        "volume_difference_mm3": volume_delta,
        "closed_solid_identity_by_empty_cuts": empty_cut_identity,
    }


def is_single_closed_solid(shape):
    """Accept one closed solid, allowing container wrappers but no loose topology.

    A valid compound with one solid can still contain extra edges or vertices;
    neither its volume nor its solid count reveals those non-printable extras.
    """
    if shape.isNull() or not shape.isValid():
        return False
    while shape.ShapeType in ("Compound", "CompSolid"):
        children = shape.childShapes()
        if len(children) != 1:
            return False
        shape = children[0]
    return shape.ShapeType == "Solid" and shape.isClosed()


def print_solid_comparison(first, second, tolerance):
    """Apply one identity gate to repeated print instances and STEP round trips."""
    result = {
        "first_single_closed_solid": is_single_closed_solid(first),
        "second_single_closed_solid": is_single_closed_solid(second),
        "passed": False,
    }
    if not all(
        result[key]
        for key in ("first_single_closed_solid", "second_single_closed_solid")
    ):
        return result
    result.update(geometry_comparison(first, second))
    # STEP may reparameterize an identical curved boundary and change OCC's
    # scalar volume integral. The empty-cut proof bypasses only that scalar
    # discrepancy; geometric difference and bounds retain their strict limits.
    result["passed"] = (
        result["difference_mm3"] < tolerance
        and result["bounds_difference_mm"] < tolerance
        and (
            result["volume_difference_mm3"] < tolerance
            or result["closed_solid_identity_by_empty_cuts"]
        )
    )
    return result


def mesh_checks(shape, mesh):
    """Check solid validity, watertightness and connectivity for PA12 exports."""
    return {
        "valid_brep": shape.isValid(),
        "single_closed_solid": is_single_closed_solid(shape),
        "solid_count": len(shape.Solids),
        "watertight_mesh": mesh.isSolid(),
        "mesh_components": mesh.countComponents(),
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
        oriented_shapes = {part.Name: print_shape(part) for part in instances}
        local_sizes = {part.Name: local_part_dimensions(part) for part in instances}
        export_sizes = {}
        for name, oriented in oriented_shapes.items():
            oriented_bounds = oriented.optimalBoundingBox(False, False)
            export_sizes[name] = [
                oriented_bounds.XLength,
                oriented_bounds.YLength,
                oriented_bounds.ZLength,
            ]
        size_checks = _size_summary(local_sizes, export_sizes)
        shape = oriented_shapes[obj.Name]
        bounds = shape.optimalBoundingBox(False, False)
        duplicate_checks = []
        for other in instances[1:]:
            check = print_solid_comparison(shape, oriented_shapes[other.Name], 1e-6)
            duplicate_checks.append({"instance": other.Name, **check})
            if not check["passed"]:
                raise RuntimeError("Different parts share SKU " + sku)

        mesh = mesh_from_shape(shape)
        checks = mesh_checks(shape, mesh)
        if not (
            checks["valid_brep"]
            and checks["single_closed_solid"]
            and checks["solid_count"] == 1
            and checks["watertight_mesh"]
            and checks["mesh_components"] == 1
            and size_checks["passed"]
        ):
            raise RuntimeError(
                "Invalid PA12 print part or outside native/export dimension limits "
                + sku
                + str({"geometry": checks, "size": size_checks})
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
                "local_sizes_mm": local_sizes,
                "size_checks": size_checks,
                "single_part_volume_cm3": shape.Volume / 1000,
                "duplicate_geometry_verification": duplicate_checks,
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
        "process": PRINT_PROCESS_DESCRIPTION,
        "manufacturing_decision": MANUFACTURING_DECISION,
        "manufacturing_release_status": "CAD checks do not qualify manufacture or physical interfaces; see release_status for every unresolved interface.",
        "release_status": release_status(),
        "published_fabrication_size_mm": PUBLISHED_PROCESS_SIZE_MM,
        "maximum_print_part_dimension_mm": MAX_PRINT_PART_DIMENSION_MM,
        "size_numerical_tolerance_mm": SIZE_NUMERICAL_TOLERANCE_MM,
        "size_screen_is_one_piece_acceptance": False,
        "thin_flexure_exception": "The 1.2 mm continuous narrow rail base needs supplier review; the nominal 0.8 mm minimum is not blanket compliance with Creallo's 3 mm long/broad SLS PA12 recommendation.",
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
