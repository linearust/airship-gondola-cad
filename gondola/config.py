"""Portable paths; generated artifacts are separate from source and fixtures."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "gondola"
OUTPUT_DIR = (
    Path(os.environ.get("GONDOLA_OUTPUT_DIR", ROOT / "build")).expanduser().resolve()
)
BASELINE_FILE = ROOT / "tests" / "fixtures" / "rev_k_geometry.FCStd"
BASELINE_SHA256 = "5dcf9fcf2b411afca68acc8459dff7d6fcfc15abaee8e1012433b73ca89ba2a1"
ARTIFACT_SCHEMA_VERSION = 1
