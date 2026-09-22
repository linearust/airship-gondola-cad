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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ab_geometry.FCStd"
BASELINE_SHA256 = "09e827f20d5fc3c36e29792cfbe4342ef7daa5f5c35c8d583f7d5823efe33735"
ARTIFACT_SCHEMA_VERSION = 3
