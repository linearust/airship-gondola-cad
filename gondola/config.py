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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_bd_geometry.FCStd"
BASELINE_SHA256 = "9eda6f8b7c0c13ae65d55ea8b3037998e42b46548a9bba1948bcbdf4a29d8d2f"
ARTIFACT_SCHEMA_VERSION = 3
