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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_w_geometry.FCStd"
BASELINE_SHA256 = "d34879acea374abfd8b7ef95112279c7d22db79f15ac753e5a15d9bb1e46fd4f"
ARTIFACT_SCHEMA_VERSION = 3
