"""Production rail-clamp patterns, independent of FreeCAD geometry builders.

Saved-geometry validators deliberately keep their own literal witnesses.
Dimensions are design selections in millimetres, not measured hardware fits.
"""

import math
from dataclasses import dataclass
from numbers import Real

from .fasteners import RAIL_SCREW_LENGTH


@dataclass(frozen=True)
class AttachmentPattern:
    """Shared mechanical datums consumed by the rail, frame and removable saddle."""

    half_spacing_mm: float
    extra_cheek_mm: float
    screw_length_mm: float
    nut_bearing_y_mm: float
    frame_half_width_mm: float = 0.0
    contact_length_mm: float = 16.0
    seat_z_mm: float = 12.5

    @property
    def shared_drive(self):
        return self.half_spacing_mm > 0

    @property
    def count(self):
        return 2 if self.shared_drive else 1

    @property
    def spacing_mm(self):
        return 2 * self.half_spacing_mm if self.shared_drive else None

    def sites(self, offset=0.0):
        if (
            isinstance(offset, bool)
            or not isinstance(offset, Real)
            or not math.isfinite(offset)
        ):
            raise ValueError("Rail attachment offset must be a finite number")
        if self.shared_drive and abs(offset - self.half_spacing_mm) > 1e-6:
            raise ValueError("Shared clamp offset must match the paired bridge")
        first = {"prefix": "", "x_offset": offset, "side": 1}
        if not self.shared_drive:
            return (first,)
        return (first, {"prefix": "Opposite", "x_offset": -offset, "side": -1})

    def head_bearing_y(self, mount_outer_y, recess_depth):
        outer_y = (
            -self.frame_half_width_mm - self.extra_cheek_mm
            if self.shared_drive
            else mount_outer_y
        )
        return outer_y + recess_depth


CARRIER_ATTACHMENT = AttachmentPattern(0.0, 0.0, RAIL_SCREW_LENGTH, 3.25)
PROPULSION_ATTACHMENT = AttachmentPattern(
    14.0, 5.0, 20.0, 8.0, 6.0, contact_length_mm=38.0
)


def attachment_pattern(shared_drive):
    if not isinstance(shared_drive, bool):
        raise ValueError("Shared drive attachment must be a boolean")
    return PROPULSION_ATTACHMENT if shared_drive else CARRIER_ATTACHMENT


def module_attachment_pattern(object_name):
    """Stable native module identities select the production interface once."""
    return attachment_pattern(object_name == "MainPropulsionModule")
