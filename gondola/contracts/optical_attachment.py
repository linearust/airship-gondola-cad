"""Selected optical base; changing attachment mode requires a complete rebuild."""

SELECTED_MOUNT = "rail"
MOUNT_MODES = ("rail", "carrier")
CARRIER_PIVOT_Z = 23.0
RAIL_PIVOT_Z = 42.0
DEFAULT_RAIL_X = 140.0
DEFAULT_CARRIER_HOST = "BatteryEquipmentModule"
DEFAULT_CARRIER_SIDE = "PositiveX"


def resolve_mount_mode(mode=None):
    mode = SELECTED_MOUNT if mode is None else mode
    if not isinstance(mode, str) or mode not in MOUNT_MODES:
        raise ValueError(f"Unsupported optical attachment mode: {mode!r}")
    return mode


def pivot_z(mode=None):
    """Pitch origin in the selected fixed base's own coordinate system."""
    return RAIL_PIVOT_Z if resolve_mount_mode(mode) == "rail" else CARRIER_PIVOT_Z
