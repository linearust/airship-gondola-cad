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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_al_geometry.FCStd"
BASELINE_SHA256 = "a5e6bbb390218786e8e0c77d1098daceb603af4b1a3a73e4783c0a3822dfae2c"
ARTIFACT_SCHEMA_VERSION = 3
