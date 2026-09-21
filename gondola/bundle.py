"""Publish a prototype ZIP only from the exact files that passed validation.

No directory is copied recursively: old exports, private source snapshots and
human instructions can never leak into a new bundle through leftover files.
This module deliberately has no FreeCAD dependency so stale-file gates are
testable without the CAD runtime.
"""

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

from .config import (
    ARTIFACT_SCHEMA_VERSION,
    ARTIFACT_STEM,
    BASELINE_FILE,
    BASELINE_SHA256,
    OUTPUT_DIR,
    REPO_ROOT,
)
from .contracts.design import (
    EXPECTED_INVENTORY,
    HARDWARE_MATERIALS,
    PURCHASED_HARDWARE_QUANTITIES,
    hardware_bom_scope,
    release_status,
)
from .procurement import purchase_code
from .provenance import file_sha256, source_fingerprint


def _snapshot(path, inputs):
    """Read each input once so validation and publication use identical bytes."""
    path = Path(path)
    if path not in inputs:
        inputs[path] = path.read_bytes()
    return inputs[path]


def _read_json(path, inputs):
    try:
        result = json.loads(_snapshot(path, inputs))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Missing or malformed artifact: {path}") from error
    if not isinstance(result, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return result


def _filename(value, suffix):
    if (
        not isinstance(value, str)
        or Path(value).name != value
        or "/" in value
        or "\\" in value
        or not value.endswith(suffix)
    ):
        raise RuntimeError(f"Unsafe or malformed artifact filename: {value!r}")
    return value


def _quantity(value):
    if type(value) is not int or value < 0:
        raise RuntimeError(f"Invalid artifact quantity: {value!r}")
    return value


def print_artifact_paths(output, stem, manifest):
    """Return the exact validation inventory, with paths relative to output."""
    output = Path(output)
    folder = stem + "_print_parts"
    parts = manifest.get("parts")
    if (
        not isinstance(parts, list)
        or len(parts) != EXPECTED_INVENTORY["unique_print_files"]
    ):
        raise RuntimeError("Malformed print manifest: unexpected part inventory.")
    paths = {
        folder + "/print_manifest.json": output / folder / "print_manifest.json",
        stem + "_hardware_bom.json": output / (stem + "_hardware_bom.json"),
    }
    skus, instances = set(), set()
    installed = coupons = 0
    for part in parts:
        if not isinstance(part, dict) or not isinstance(part.get("sku"), str):
            raise RuntimeError("Malformed print manifest part.")
        if not part["sku"] or part["sku"] in skus:
            raise RuntimeError("Duplicate or empty print SKU.")
        skus.add(part["sku"])
        total = _quantity(part.get("quantity"))
        installed_count = _quantity(part.get("installed_quantity"))
        coupon_count = _quantity(part.get("coupon_quantity"))
        names = part.get("instances")
        if (
            not isinstance(names, list)
            or not all(isinstance(name, str) and name for name in names)
            or total != installed_count + coupon_count
            or total != len(names)
            or total == 0
            or len(set(names)) != len(names)
            or instances.intersection(names)
        ):
            raise RuntimeError("Print manifest quantities or instances disagree.")
        instances.update(names)
        installed += installed_count
        coupons += coupon_count
        for field, extension in (("file", ".stl"), ("step_file", ".step")):
            name = folder + "/" + _filename(part.get(field), extension)
            if name in paths:
                raise RuntimeError("Duplicate print artifact filename.")
            paths[name] = output / name
    if (
        installed != EXPECTED_INVENTORY["installed_prints"]
        or coupons != EXPECTED_INVENTORY["fit_coupons"]
        or manifest.get("unique_stl_count") != len(parts)
        or manifest.get("installed_printed_part_count") != installed
        or manifest.get("additional_coupon_printed_part_count") != coupons
    ):
        raise RuntimeError("Print manifest totals disagree with the design contract.")
    return paths


def _validate_bom(bom):
    items = bom.get("items")
    if (
        not isinstance(items, list)
        or len(items) != EXPECTED_INVENTORY["purchased_hardware_types"]
    ):
        raise RuntimeError("Malformed hardware BOM inventory.")
    codes, names = set(), set()
    quantity = 0
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("Malformed hardware BOM item.")
        code = item.get("purchase_code")
        sku = item.get("sku")
        if (
            not isinstance(sku, str)
            or sku not in PURCHASED_HARDWARE_QUANTITIES
            or item.get("material") != HARDWARE_MATERIALS[sku]
            or code != purchase_code(sku, HARDWARE_MATERIALS[sku])
            or item.get("quantity") != PURCHASED_HARDWARE_QUANTITIES[sku]
        ):
            raise RuntimeError(
                "Hardware BOM specifications disagree with the design contract."
            )
        instances = item.get("instances")
        count = _quantity(item.get("quantity"))
        if (
            not isinstance(code, str)
            or not code
            or code in codes
            or not isinstance(instances, list)
            or not all(isinstance(name, str) and name for name in instances)
            or len(instances) != count
            or count == 0
            or len(set(instances)) != len(instances)
            or names.intersection(instances)
        ):
            raise RuntimeError("Hardware BOM quantities or instances disagree.")
        codes.add(code)
        names.update(instances)
        quantity += count
    if (
        quantity != EXPECTED_INVENTORY["purchased_hardware"]
        or bom.get("purchased_hardware_quantity") != quantity
        or bom.get("unique_purchase_spec_count") != len(items)
    ):
        raise RuntimeError("Hardware BOM totals disagree with the design contract.")


def _same_source(artifact, fingerprint, label):
    if artifact.get("source_fingerprint") != fingerprint:
        raise RuntimeError(
            f"Stale source inputs in {label}; rebuild, preview, validate and compare."
        )


def _json_bytes(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def build_bundle():
    """Verify saved-CAD/source/export identities, then atomically replace ZIP."""
    output = Path(OUTPUT_DIR)
    cad = output / (ARTIFACT_STEM + ".FCStd")
    inputs = {}
    try:
        cad_sha = file_sha256(cad)
        fingerprint = source_fingerprint()
        audit_path = output / (ARTIFACT_STEM + "_validation.json")
        equipment_path = output / (ARTIFACT_STEM + "_equipment_validation.json")
        audit = _read_json(audit_path, inputs)
        equipment = _read_json(equipment_path, inputs)
        if not (
            audit.get("passed") is True
            and audit.get("source_hashes_before") == {cad.name: cad_sha}
            and audit.get("source_hashes_after") == {cad.name: cad_sha}
            and equipment.get("passed") is True
            and equipment.get("source_sha256") == cad_sha
            and equipment.get("source_sha256_after") == cad_sha
        ):
            raise RuntimeError(
                "Missing, failed or stale checks. Run validate after the last build/preview."
            )
        _same_source(audit, fingerprint, "validation")
        _same_source(equipment, fingerprint, "equipment validation")
        baseline_path = output / (ARTIFACT_STEM + "_baseline_validation.json")
        baseline = _read_json(baseline_path, inputs)
        _same_source(baseline, fingerprint, "baseline comparison")
        baseline_hashes = {
            os.path.relpath(cad, REPO_ROOT): cad_sha,
            os.path.relpath(BASELINE_FILE, REPO_ROOT): BASELINE_SHA256,
        }
        if not (
            baseline.get("passed") is True
            and baseline.get("source_sha256") == cad_sha
            and baseline.get("baseline_sha256") == BASELINE_SHA256
            and baseline.get("file_hashes_before") == baseline_hashes
            and baseline.get("file_hashes_after") == baseline_hashes
            and file_sha256(BASELINE_FILE) == BASELINE_SHA256
        ):
            raise RuntimeError(
                "Missing, failed or stale baseline comparison. "
                "Run compare against the frozen baseline after the last build/preview."
            )
        folder = output / (ARTIFACT_STEM + "_print_parts")
        manifest_path = folder / "print_manifest.json"
        bom_path = output / (ARTIFACT_STEM + "_hardware_bom.json")
        manifest = _read_json(manifest_path, inputs)
        bom = _read_json(bom_path, inputs)
        for label, artifact in (("manifest", manifest), ("BOM", bom)):
            if artifact.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
                raise RuntimeError(f"Unsupported {label} schema.")
            _same_source(artifact, fingerprint, label)
        if manifest.get("release_status") != release_status():
            raise RuntimeError(
                "Print manifest release status disagrees with the current design contract."
            )
        if bom.get("purchase_scope") != hardware_bom_scope():
            raise RuntimeError(
                "Hardware BOM purchase scope disagrees with the current design contract."
            )
        _validate_bom(bom)
        paths = print_artifact_paths(output, ARTIFACT_STEM, manifest)
        # Snapshot bytes once. The published files are exactly those hashed here,
        # even if another process rewrites an export during ZIP creation.
        snapshots = {name: _snapshot(path, inputs) for name, path in paths.items()}
        hashes = {
            name: hashlib.sha256(data).hexdigest() for name, data in snapshots.items()
        }
        if (
            audit.get("artifact_hashes_before") != hashes
            or audit.get("artifact_hashes") != hashes
        ):
            raise RuntimeError(
                "Stale or altered print files, manifest or BOM; run validate again."
            )
        bom_sha = hashes[ARTIFACT_STEM + "_hardware_bom.json"]
        if (
            equipment.get("hardware_bom_sha256_before") != bom_sha
            or equipment.get("hardware_bom_sha256_after") != bom_sha
        ):
            raise RuntimeError(
                "Stale equipment BOM validation; run validate against the current BOM."
            )
        for part in manifest["parts"]:
            for name_key, hash_key in (
                ("file", "file_sha256"),
                ("step_file", "step_sha256"),
            ):
                key = ARTIFACT_STEM + "_print_parts/" + part[name_key]
                if part.get(hash_key) != hashes[key]:
                    raise RuntimeError("Export checksum disagrees with print manifest.")
        state_path = output / "preview_state.json"
        state = _read_json(state_path, inputs)
        if state.get("passed") is not True or state.get("source_sha256") != cad_sha:
            raise RuntimeError("Preview is missing/stale. Run preview, then validate.")
        _same_source(state, fingerprint, "preview")
        images = state.get("images")
        image_hashes = state.get("image_sha256")
        if (
            not isinstance(images, list)
            or not images
            or len(images) != len(set(images))
            or not isinstance(image_hashes, dict)
            or set(images) != set(image_hashes)
        ):
            raise RuntimeError("Malformed preview image inventory.")
        files = {
            "print_manifest.json": snapshots.pop(
                ARTIFACT_STEM + "_print_parts/print_manifest.json"
            ),
            "hardware_bom.json": snapshots.pop(ARTIFACT_STEM + "_hardware_bom.json"),
            "validation/assembly.json": inputs[audit_path],
            "validation/equipment.json": inputs[equipment_path],
            "validation/baseline.json": inputs[baseline_path],
            "validation/preview.json": inputs[state_path],
        }
        for name, data in snapshots.items():
            files[Path(name).name] = data
        for filename in images:
            _filename(filename, ".png")
            data = _snapshot(output / filename, inputs)
            if hashlib.sha256(data).hexdigest() != image_hashes[filename]:
                raise RuntimeError("Preview image changed after rendering.")
            files["previews/" + filename] = data
        release = release_status()
        files["release_status.json"] = _json_bytes(release)
        files["package_hashes.json"] = _json_bytes(
            {
                "schema_version": ARTIFACT_SCHEMA_VERSION,
                "native_assembly_sha256": cad_sha,
                "source_fingerprint": fingerprint,
                "files": {
                    name: hashlib.sha256(data).hexdigest()
                    for name, data in sorted(files.items())
                },
            }
        )
        archive = output / (ARTIFACT_STEM + "_print_parts.zip")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=".gondola-bundle-", suffix=".zip", dir=output, delete=False
            ) as pending:
                temporary = Path(pending.name)
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as zipped:
                for name, data in sorted(files.items()):
                    zipped.writestr(name, data)
            with zipfile.ZipFile(temporary) as zipped:
                if zipped.testzip() is not None or set(zipped.namelist()) != set(files):
                    raise RuntimeError("ZIP integrity or inventory check failed.")
            # A simultaneous rebuild must not publish an archive described as
            # current while its governing source or exported files changed.
            if source_fingerprint() != fingerprint or file_sha256(cad) != cad_sha:
                raise RuntimeError("Source or native CAD changed while packaging.")
            if file_sha256(BASELINE_FILE) != BASELINE_SHA256:
                raise RuntimeError("Frozen baseline changed while packaging.")
            for path, data in inputs.items():
                if file_sha256(path) != hashlib.sha256(data).hexdigest():
                    raise RuntimeError(
                        f"Bundle input changed while packaging: {path.name}"
                    )
            temporary.replace(archive)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"Missing or malformed bundle input: {error}") from error
    print(
        json.dumps(
            {
                "archive": str(archive),
                "bytes": archive.stat().st_size,
                "native_assembly_sha256": cad_sha,
                "source_fingerprint": fingerprint,
                "stage": release["stage"],
            },
            indent=2,
        )
    )
    return archive
