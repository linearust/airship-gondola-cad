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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_bc_geometry.FCStd"
BASELINE_SHA256 = "3caa6d85c778f0b567a4a80c18340055a5354f49005b00d88a425c24621aab1b"
ARTIFACT_SCHEMA_VERSION = 3
