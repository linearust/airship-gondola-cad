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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ay_geometry.FCStd"
BASELINE_SHA256 = "384fc879aabbea59b582514f370964c1284e4205bd58dc4febf1287d09af97f2"
ARTIFACT_SCHEMA_VERSION = 3
