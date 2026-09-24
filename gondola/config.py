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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_aq_geometry.FCStd"
BASELINE_SHA256 = "d63ad6124cb7ba07d456d1c152642eaa85883609727237a09e81bceedb3efbb7"
ARTIFACT_SCHEMA_VERSION = 3
