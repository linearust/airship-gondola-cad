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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ad_geometry.FCStd"
BASELINE_SHA256 = "01ec30f2242ef8461a51c5e5d69fce9373ea8f0db068c79762027db3080f144d"
ARTIFACT_SCHEMA_VERSION = 3
