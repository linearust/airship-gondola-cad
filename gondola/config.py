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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_bf_geometry.FCStd"
BASELINE_SHA256 = "8515376f24b6719633184620e8dfa9246e028e94166c3f14f44cc61c9e48eee9"
ARTIFACT_SCHEMA_VERSION = 3
