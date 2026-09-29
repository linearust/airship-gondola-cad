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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_bj_geometry.FCStd"
BASELINE_SHA256 = "3fb50bda82e4bf78d4020d2f1de777f742868ab6ce1dd7714cabf6a78075ba08"
ARTIFACT_SCHEMA_VERSION = 3
