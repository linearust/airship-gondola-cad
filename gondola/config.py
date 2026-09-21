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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_q_geometry.FCStd"
BASELINE_SHA256 = "174bbb5d063c723456d6b6216d5196aa2709f23fdfd013e97e091cf53a1f312f"
ARTIFACT_SCHEMA_VERSION = 3
