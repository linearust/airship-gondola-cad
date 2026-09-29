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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_bi_geometry.FCStd"
BASELINE_SHA256 = "df7ec5412aa7133ed7b12178eb3198f0d0622c77627a6ad47b5de72ddbe248a8"
ARTIFACT_SCHEMA_VERSION = 3
