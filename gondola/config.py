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
BASELINE_SHA256 = "b5dc2f9a4d992f88ebd2d0358e86aba1de86c66b7adc584b58ade357012b3bd1"
ARTIFACT_SCHEMA_VERSION = 3
