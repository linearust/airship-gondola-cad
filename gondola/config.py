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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_aj_geometry.FCStd"
BASELINE_SHA256 = "8ce49e698661d106d9f4ea2b163d6d93ae51aaf2a0b3bf62bf49c9d5eac9201e"
ARTIFACT_SCHEMA_VERSION = 3
