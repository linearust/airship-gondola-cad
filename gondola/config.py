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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_aa_geometry.FCStd"
BASELINE_SHA256 = "5924ef328526cabe9d3917a8c5771f5183091c9d9564da11723baddfd24785e9"
ARTIFACT_SCHEMA_VERSION = 3
