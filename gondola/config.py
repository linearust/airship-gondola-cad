"""Portable paths; generated artifacts are separate from source and fixtures."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "gondola"
OUTPUT_DIR = (
    Path(os.environ.get("GONDOLA_OUTPUT_DIR", ROOT / "build")).expanduser().resolve()
)
BASELINE_FILE = ROOT / "tests" / "fixtures" / "rev_p_geometry.FCStd"
BASELINE_SHA256 = "426de40f3ae9889c6b32427514a114a962f76c9c32ef849b3f29bcfe98fbde41"
ARTIFACT_SCHEMA_VERSION = 3
