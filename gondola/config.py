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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_bg_geometry.FCStd"
BASELINE_SHA256 = "713ecfe4069a487d53c82b04354308dfc1346a32f935bd149aacbf1c2819555a"
ARTIFACT_SCHEMA_VERSION = 3
