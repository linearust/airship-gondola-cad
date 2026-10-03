"""One dual-interface optical tray; the default retains its carrier pedestal."""

SELECTED_MOUNT = "carrier"
MOUNT_MODES = ("carrier", "rail")
CARRIER_PIVOT_Z = 19.0
# Canonical rail shoe translated into the tray's pitch frame.
TRAY_RAIL_SHOE_OFFSET = (12.0, -1.25, -6.5)
DEFAULT_RAIL_X = 140.0
DEFAULT_CARRIER_HOST = "BatteryEquipmentModule"
DEFAULT_CARRIER_SIDE = "PositiveX"


def resolve_mount_mode(mode=None):
    mode = SELECTED_MOUNT if mode is None else mode
    if not isinstance(mode, str) or mode not in MOUNT_MODES:
        raise ValueError(f"Unsupported optical attachment mode: {mode!r}")
    return mode


def pivot_z(mode=None):
    """Tray frame Z; only the carrier mode has a physical pitch joint."""
    return (
        -TRAY_RAIL_SHOE_OFFSET[2]
        if resolve_mount_mode(mode) == "rail"
        else CARRIER_PIVOT_Z
    )
