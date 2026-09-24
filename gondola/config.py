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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ap_geometry.FCStd"
BASELINE_SHA256 = "b36eb0b454b7c57c285d2cc8c3fcd77874b18015b0348432147df159eeaafb74"
ARTIFACT_SCHEMA_VERSION = 3
