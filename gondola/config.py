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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_au_geometry.FCStd"
BASELINE_SHA256 = "56fbdb3cf9f96d3deaccb28fdd13a579b16b685021508e832f21dfd84c036a27"
ARTIFACT_SCHEMA_VERSION = 3
