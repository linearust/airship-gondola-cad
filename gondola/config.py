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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "geometry.FCStd"
BASELINE_SHA256 = "ba5f55cfe1b9f2bce67bd22c0aaeb1922d6e9bfa92a79f51b131509da9045287"
ARTIFACT_SCHEMA_VERSION = 3
