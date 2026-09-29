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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_bh_geometry.FCStd"
BASELINE_SHA256 = "765d6d505b75c7b740794775740a6b50d3ade9e199e560941eb6aee48f71d53b"
ARTIFACT_SCHEMA_VERSION = 3
