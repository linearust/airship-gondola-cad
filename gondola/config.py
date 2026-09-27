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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_av_geometry.FCStd"
BASELINE_SHA256 = "f0ee355bcf028b0c4f1692756e2d5547445dc016019dcd1a3084d730bfac04c4"
ARTIFACT_SCHEMA_VERSION = 3
