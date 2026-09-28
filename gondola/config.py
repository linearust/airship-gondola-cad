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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ax_geometry.FCStd"
BASELINE_SHA256 = "613ea62f0f077afdc2df8865c4d657ba4a3b5e09f7d4446166a1e39ad7db938a"
ARTIFACT_SCHEMA_VERSION = 3
