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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_am_geometry.FCStd"
BASELINE_SHA256 = "2c3c83d21350e1764031be9ac3c85f0db7fe811f68cd63dc85e756f1e91b695e"
ARTIFACT_SCHEMA_VERSION = 3
