"""Identify the exact code and GUI entry points behind generated CAD artifacts."""

import hashlib
from pathlib import Path

from .config import REPO_ROOT


def file_sha256(path):
    """Hash saved artifact bytes, independently of their location or mtime."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_fingerprint():
    paths = [
        *(REPO_ROOT / "gondola").rglob("*.py"),
        *REPO_ROOT.glob("*.FCMacro"),
    ]
    fingerprint = hashlib.sha256()
    for path in sorted(paths):
        name = path.relative_to(REPO_ROOT).as_posix().encode()
        content = path.read_bytes()
        fingerprint.update(len(name).to_bytes(8, "big"))
        fingerprint.update(name)
        fingerprint.update(len(content).to_bytes(8, "big"))
        fingerprint.update(content)
    return fingerprint.hexdigest()
