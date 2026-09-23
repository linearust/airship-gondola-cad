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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ag_geometry.FCStd"
BASELINE_SHA256 = "4db17b3b07a56ba63e66c8b49707704635f0e008de1411fda4ec5858a2b91437"
ARTIFACT_SCHEMA_VERSION = 3
