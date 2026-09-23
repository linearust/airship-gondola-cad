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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ai_geometry.FCStd"
BASELINE_SHA256 = "994dc284ca93d16f63f7b539d33b53b1ab8c4ad9a54c1522647a69b1d8a754f6"
ARTIFACT_SCHEMA_VERSION = 3
