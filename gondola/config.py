"""Portable paths; generated artifacts are separate from source and fixtures."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "gondola"
OUTPUT_DIR = (
    Path(os.environ.get("GONDOLA_OUTPUT_DIR", ROOT / "build")).expanduser().resolve()
)
BASELINE_FILE = ROOT / "tests" / "fixtures" / "rev_i_geometry.FCStd"
BASELINE_SHA256 = "f0dad60f28f6f353446e7d1bfa165ff99a5442e9b678ab8c6deb92d44f303ce9"
ARTIFACT_SCHEMA_VERSION = 1
