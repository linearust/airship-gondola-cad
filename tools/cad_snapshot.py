"""Read validated saved CAD and publish JSON derivatives without changing inputs."""

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from gondola.provenance import file_sha256, source_fingerprint


def json_output_path(output, protected_paths):
    """Reject input aliases before opening CAD or writing any output."""
    output = Path(output).expanduser().resolve()
    for protected in protected_paths:
        protected = Path(protected).expanduser().resolve()
        if output == protected or (
            output.exists() and protected.exists() and output.samefile(protected)
        ):
            raise ValueError("Output must be a separate JSON snapshot, not an input.")
    if output.suffix.lower() != ".json":
        raise ValueError("Output must be a separate JSON snapshot.")
    return output


def write_json_atomic(output, data, *, before_replace=None, **formatting):
    """Preserve the previous output if encoding, writing or final checks fail."""
    payload = json.dumps(data, allow_nan=False, **formatting) + "\n"
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        if before_replace is not None:
            before_replace()
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class CadSnapshot:
    doc: object
    cad_path: Path
    output_path: Path
    report_path: Path
    report: dict
    cad_sha256: str
    source_fingerprint: str
    validation_sha256: str

    def provenance(self):
        return {
            "cad_file": self.cad_path.name,
            "cad_sha256": self.cad_sha256,
            "source_fingerprint": self.source_fingerprint,
            "validation_sha256": self.validation_sha256,
        }

    def assert_unchanged(self):
        if (
            file_sha256(self.cad_path) != self.cad_sha256
            or source_fingerprint() != self.source_fingerprint
            or file_sha256(self.report_path) != self.validation_sha256
        ):
            raise RuntimeError(
                "CAD, source or validation report changed during export."
            )

    def write_json(self, data, **formatting):
        """Call after leaving open_validated_cad; publish only unchanged inputs."""

        def check_inputs():
            json_output_path(self.output_path, (self.cad_path, self.report_path))
            self.assert_unchanged()

        check_inputs()
        write_json_atomic(
            self.output_path, data, before_replace=check_inputs, **formatting
        )


@contextmanager
def open_validated_cad(cad_path, output_path):
    """Open one document for extraction, close it without saving, then recheck."""
    cad_path = Path(cad_path).expanduser().resolve()
    report_path = cad_path.with_name(cad_path.stem + "_validation.json")
    output_path = json_output_path(output_path, (cad_path, report_path))
    digest = file_sha256(cad_path)
    fingerprint = source_fingerprint()
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    hashes = report.get("source_hashes_after") if isinstance(report, dict) else None
    if (
        not isinstance(report, dict)
        or report.get("passed") is not True
        or report.get("source_fingerprint") != fingerprint
        or not isinstance(hashes, dict)
        or hashes.get(cad_path.name) != digest
    ):
        raise ValueError(
            "Passing validation must match current source and exact saved CAD bytes."
        )

    import FreeCAD as App

    doc = App.openDocument(str(cad_path))
    snapshot = CadSnapshot(
        doc,
        cad_path,
        output_path,
        report_path,
        report,
        digest,
        fingerprint,
        hashlib.sha256(report_bytes).hexdigest(),
    )
    try:
        if (
            getattr(getattr(doc, "DesignRegistry", None), "SourceFingerprint", None)
            != fingerprint
        ):
            raise ValueError("Saved CAD is stale relative to current geometry source.")
        yield snapshot
    finally:
        App.closeDocument(doc.Name)
    snapshot.assert_unchanged()
