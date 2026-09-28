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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_bb_geometry.FCStd"
BASELINE_SHA256 = "ab35c4d780b660d4a9d520c4e478c38b5e0531089e0c0092dd4d4cff659521c2"
ARTIFACT_SCHEMA_VERSION = 3
