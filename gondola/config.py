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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_bi_geometry.FCStd"
BASELINE_SHA256 = "d9fa5c2c006f33fedf3eaa0cee68224deeb324bc6e160d0465485cbb725faf24"
ARTIFACT_SCHEMA_VERSION = 3
