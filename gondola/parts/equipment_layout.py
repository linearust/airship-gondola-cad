"""Shared local placement datums for interchangeable purchased equipment."""

import FreeCAD as App

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


def radio_placement():
    """Radio beside navigation on the accessible outer face of the shared deck."""
    return App.Placement(
        App.Vector(*mounts.RADIO_CENTRE_XY, adhesive_bottom()),
        App.Rotation(),
    )


def device_removal_vector(name, distance=32.0):
    """Bench removal in the carrier frame, after releasing adhesive/hardware."""
    return (0.0, 0.0, distance)
