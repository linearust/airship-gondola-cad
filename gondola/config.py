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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_as_geometry.FCStd"
BASELINE_SHA256 = "6205f34231fcdb19167bacd7fa00eb01dd25b4a1c3eb67a4279f10e0d1100b8a"
ARTIFACT_SCHEMA_VERSION = 3
