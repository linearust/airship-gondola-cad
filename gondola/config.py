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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ao_geometry.FCStd"
BASELINE_SHA256 = "bf3c09fb8deb869ea6d0e0a3d06a320ffa5ffa7552aab9132e2eb267e14dea51"
ARTIFACT_SCHEMA_VERSION = 3
