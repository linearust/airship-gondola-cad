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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ac_geometry.FCStd"
BASELINE_SHA256 = "2a488193785ce17e75426d23e3b23f7f5f2a72a242f9223492e0cbdddd1ea7af"
ARTIFACT_SCHEMA_VERSION = 3
