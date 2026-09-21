"""Portable paths; generated artifacts are separate from source and fixtures."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "gondola"
OUTPUT_DIR = (
    Path(os.environ.get("GONDOLA_OUTPUT_DIR", ROOT / "build")).expanduser().resolve()
)
BASELINE_FILE = ROOT / "tests" / "fixtures" / "rev_o_geometry.FCStd"
BASELINE_SHA256 = "91c0af1a15aa425f46120f9ab17fdce82d9d63a2613535ea06c304c499b69838"
ARTIFACT_SCHEMA_VERSION = 2
