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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_z_geometry.FCStd"
BASELINE_SHA256 = "4489ecc80bde62fcb34211a63b55a3c820bc7b17eac0218091ae8d2d4fdde78a"
ARTIFACT_SCHEMA_VERSION = 3
