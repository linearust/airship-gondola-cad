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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_s_geometry.FCStd"
BASELINE_SHA256 = "5c673a24c535b0ad6c7f54e5e1b1582305d4c2976fdaf1837702a906480ff092"
ARTIFACT_SCHEMA_VERSION = 3
