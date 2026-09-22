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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_x_geometry.FCStd"
BASELINE_SHA256 = "0d780e251e971a40338d6154a611ea7087ca1ebcdb606d4693a67e7f94ae32e8"
ARTIFACT_SCHEMA_VERSION = 3
