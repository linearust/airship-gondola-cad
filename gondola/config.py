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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "geometry.FCStd"
BASELINE_SHA256 = "13afa4689da8d6645d4db1dd6a1afc2860dd7f65a599d5043e89a650cdd7637f"
ARTIFACT_SCHEMA_VERSION = 3
