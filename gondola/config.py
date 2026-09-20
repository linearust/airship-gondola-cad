"""Portable paths; generated artifacts are separate from source and fixtures."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "gondola"
OUTPUT_DIR = (
    Path(os.environ.get("GONDOLA_OUTPUT_DIR", ROOT / "build")).expanduser().resolve()
)
BASELINE_FILE = ROOT / "tests" / "fixtures" / "rev_l_geometry.FCStd"
BASELINE_SHA256 = "a1e5b81c66bc4f65a6cbaf27fcb52e1b6e6862519e9b9d6a2d6a44a279fdac67"
ARTIFACT_SCHEMA_VERSION = 1
