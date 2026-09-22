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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_y_geometry.FCStd"
BASELINE_SHA256 = "7fdb555b017a93309ff5f5cf184ee3b7321e6bbb4b67cd5d587357bb518eef57"
ARTIFACT_SCHEMA_VERSION = 3
