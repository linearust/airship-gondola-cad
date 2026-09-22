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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_t_geometry.FCStd"
BASELINE_SHA256 = "3fb28659cbe747b923534060caa1ae48a17bdae34abbe629378441e06b4f99b0"
ARTIFACT_SCHEMA_VERSION = 3
