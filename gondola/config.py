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
BASELINE_SHA256 = "1b08a44f377e0b7b44955cd3cdaf4da1a6f6a54539f7a416f8f5a2ea9d980d8a"
ARTIFACT_SCHEMA_VERSION = 3
