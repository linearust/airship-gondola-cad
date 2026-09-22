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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_u_geometry.FCStd"
BASELINE_SHA256 = "22418af02f770b1dd877f55f72d38c07b62db1d0374e707f667126d64f321199"
ARTIFACT_SCHEMA_VERSION = 3
