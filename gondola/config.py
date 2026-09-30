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
BASELINE_SHA256 = "890ff9b4830058df96bfb554cf59d1432d77297c35ee551835a83205a3a89508"
ARTIFACT_SCHEMA_VERSION = 3
