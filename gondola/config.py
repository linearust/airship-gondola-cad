"""Portable paths; generated artifacts are separate from source and fixtures."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_STEM = "gondola"
OUTPUT_DIR = (
    Path(os.environ.get("GONDOLA_OUTPUT_DIR", REPO_ROOT / "build"))
    .expanduser()
    .resolve()
)
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ah_geometry.FCStd"
BASELINE_SHA256 = "9637e2bca7767c0bb6e3093bc32c37410d233c54d7c1dde5a4fe76d626313b82"
ARTIFACT_SCHEMA_VERSION = 3
