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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_at_geometry.FCStd"
BASELINE_SHA256 = "b1085eacdac63585351da26c2a890faaaed59acd6a6287580d113ea534262b22"
ARTIFACT_SCHEMA_VERSION = 3
