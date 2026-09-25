"""Shared local placement datums for interchangeable purchased equipment."""

from gondola.contracts.equipment_options import get_navigation_profile

from . import equipment_mounts as mounts


def navigation_centre():
    return mounts.NAVIGATION_CENTRE_XY


def navigation_bottom(profile=None):
    profile = profile or get_navigation_profile()
    clearance = (
        mounts.PAS_SERVICE_CLEARANCE
        if profile.key == "PAS"
        else mounts.ADHESIVE_ALLOWANCE
    )
    return mounts.SUPPORT_FACE_Z + clearance


def navigation_hole_centres(profile=None):
    profile = profile or get_navigation_profile()
    cx, cy = navigation_centre()
    return tuple((cx + x, cy + y) for x, y in profile.mounting_hole_centres_mm)


def adhesive_bottom():
    """Common nominal elevation for equipment with adhesive under its body."""
    return mounts.SUPPORT_FACE_Z + mounts.ADHESIVE_ALLOWANCE
