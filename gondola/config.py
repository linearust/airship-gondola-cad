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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_az_geometry.FCStd"
BASELINE_SHA256 = "4b4e5cb665fa2e001027a5ddd3e0d79b09876e66a7c6674088ec6098baa7e67c"
ARTIFACT_SCHEMA_VERSION = 3
