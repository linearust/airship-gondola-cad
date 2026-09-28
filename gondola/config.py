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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ba_geometry.FCStd"
BASELINE_SHA256 = "41eff55eaacb911f88722a7223feb1e52e9c1eeaffb1c250049ca4b0f37b9d3b"
ARTIFACT_SCHEMA_VERSION = 3
