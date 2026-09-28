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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_be_geometry.FCStd"
BASELINE_SHA256 = "824cba0ce9104f3668e3facd7291dab36630bbc10c905a2e438798a8d74c182b"
ARTIFACT_SCHEMA_VERSION = 3
