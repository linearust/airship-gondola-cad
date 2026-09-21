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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_r_geometry.FCStd"
BASELINE_SHA256 = "f5b7362243d857a0255c2a45d2230874648bcfb75dd0aeef48affc867e2f977a"
ARTIFACT_SCHEMA_VERSION = 3
