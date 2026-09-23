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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ae_geometry.FCStd"
BASELINE_SHA256 = "9879103a59dd699c332fc104f87fefa8eb66e9874472d650c6036c0fbccfcfa5"
ARTIFACT_SCHEMA_VERSION = 3
