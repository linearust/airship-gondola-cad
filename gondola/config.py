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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_v_geometry.FCStd"
BASELINE_SHA256 = "6195de36c1f058e1a9a809a451eefbcfc4d75f12dbd2c6c2d5950bbbc16a434e"
ARTIFACT_SCHEMA_VERSION = 3
