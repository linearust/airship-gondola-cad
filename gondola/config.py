"""Portable paths; generated artifacts are separate from source and fixtures."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "gondola"
OUTPUT_DIR = (
    Path(os.environ.get("GONDOLA_OUTPUT_DIR", ROOT / "build")).expanduser().resolve()
)
BASELINE_FILE = ROOT / "tests" / "fixtures" / "rev_m_geometry.FCStd"
BASELINE_SHA256 = "e29b6eb7e1f11d7fa7f345144f459ea23e6d4630534ec5be61a4ded0a34bc907"
ARTIFACT_SCHEMA_VERSION = 2
