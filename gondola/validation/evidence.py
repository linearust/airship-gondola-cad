"""Inspect numeric audit evidence without importing the CAD runtime."""

import math
from collections.abc import Mapping
from numbers import Real


def _finite_nonnegative(value):
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and value >= 0
        and math.isfinite(value)
    )


def comparison_passed(comparison, tolerance):
    """Require complete, finite, nonnegative differences below a valid limit."""
    if (
        not isinstance(comparison, Mapping)
        or not _finite_nonnegative(tolerance)
        or tolerance == 0
    ):
        return False
    return all(
        _finite_nonnegative(comparison.get(key)) and comparison[key] < tolerance
        for key in ("difference_mm3", "bounds_difference_mm", "volume_difference_mm3")
    )


def overlap_failures(value, tolerance, location=""):
    """Find nonzero or nonfinite overlap volumes in nested audit reports.

    Blocking intersections and contact areas are intentionally outside this
    check: those positive quantities can be required by retention tests.
    """
    failures = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = location + "/" + key
            if (
                "overlap" in key
                and key.endswith("mm3")
                and isinstance(child, (int, float))
                and (not math.isfinite(child) or abs(child) > tolerance)
            ):
                failures.append({"field": path, "volume_mm3": child})
            failures.extend(overlap_failures(child, tolerance, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            failures.extend(overlap_failures(child, tolerance, f"{location}/{index}"))
    return failures
