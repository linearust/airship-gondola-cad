"""Unmodified manufacturer X06 half-arm geometry in the assembly horn frame."""

import functools

import FreeCAD as App
import Part

from gondola.config import REPO_ROOT
from gondola.provenance import file_sha256

STEP_PATH = REPO_ROOT / "gondola" / "data" / "kst_x06_half_arm_1.step"
STEP_SHA256 = "ea9ad94160411df4c32e495eda85f75a43bcfcb379a86b113ad6e03c8aa79c81"


def _check_asset():
    if file_sha256(STEP_PATH) != STEP_SHA256:
        raise ValueError("Manufacturer X06 half-arm STEP checksum does not match")


@functools.lru_cache(maxsize=1)
def _raw_shape():
    shape = Part.read(str(STEP_PATH))
    # Recheck after native import as well as before every public cache lookup.
    _check_asset()
    if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1:
        raise ValueError("Manufacturer X06 half-arm STEP is not one valid solid")
    return shape


def normalized_shape():
    """Return a private copy: (x,y,z) -> (x,z+1.5,-y), without hole preparation.

    The spline rear opening is Y=0, the arm is Y=1.5..3.5 and its long axis
    remains +X. Only a rigid transform is applied; the supplied spline and all
    four factory holes remain intact. Callers may modify their returned copy.
    """
    _check_asset()
    shape = _raw_shape().copy()
    shape.rotate(App.Vector(), App.Vector(1, 0, 0), -90)
    shape.translate(App.Vector(0, 1.5, 0))
    return shape
