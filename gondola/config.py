"""Portable paths; generated artifacts are separate from source and fixtures."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "gondola"
OUTPUT_DIR = (
    Path(os.environ.get("GONDOLA_OUTPUT_DIR", ROOT / "build")).expanduser().resolve()
)
BASELINE_FILE = ROOT / "tests" / "fixtures" / "rev_n_geometry.FCStd"
BASELINE_SHA256 = "a99b5b73c4bc27507350073c8c823583f49c8b412a5faf6982ce629661e954b1"
ARTIFACT_SCHEMA_VERSION = 2
