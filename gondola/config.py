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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ar_geometry.FCStd"
BASELINE_SHA256 = "342a6f551200c81954eca714570243aa54fc2472a696a516561946a4472f0a6f"
ARTIFACT_SCHEMA_VERSION = 3
