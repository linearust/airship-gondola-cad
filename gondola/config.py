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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_af_geometry.FCStd"
BASELINE_SHA256 = "7e164d8fb3d003fd3b1de6acc9511ba8bab094dbe5e03f45dfa146ba617c9bbb"
ARTIFACT_SCHEMA_VERSION = 3
