"""The optical sensor is rigidly attached to the shared instrument platform."""

SELECTED_MOUNT = "instrument"
MOUNT_MODES = ("instrument",)
DEFAULT_HOST = "InstrumentPitchStage"
SENSOR_FRAME_ORIGIN_IN_STAGE = (0.0, 0.0, 0.0)


def resolve_mount_mode(mode=None):
    mode = SELECTED_MOUNT if mode is None else mode
    if not isinstance(mode, str) or mode not in MOUNT_MODES:
        raise ValueError(f"Unsupported optical attachment mode: {mode!r}")
    return mode
