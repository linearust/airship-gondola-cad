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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_aw_geometry.FCStd"
BASELINE_SHA256 = "ff5a729761bc9a071630966132ea7584c62321a3dc40766880d6f7ab3fd63ace"
ARTIFACT_SCHEMA_VERSION = 3
