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
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "rev_ak_geometry.FCStd"
BASELINE_SHA256 = "3f69926d05aad2429f40f281afd0529b333a66eb509b2d7b4e79efb53ba73665"
ARTIFACT_SCHEMA_VERSION = 3
