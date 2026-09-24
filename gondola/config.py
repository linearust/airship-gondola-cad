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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_an_geometry.FCStd"
BASELINE_SHA256 = "ecb4b5c20c7a0414dd97756ef81bb18abcc4ece925a443d475ad3395dd3522ea"
ARTIFACT_SCHEMA_VERSION = 3
