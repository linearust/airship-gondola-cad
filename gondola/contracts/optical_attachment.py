"""The optical sensor is rigidly attached to the shared instrument platform."""

SELECTED_MOUNT = "instrument"
MOUNT_MODES = ("instrument",)
DEFAULT_HOST = "InstrumentPitchStage"
SENSOR_FRAME_ORIGIN_IN_STAGE = (0.0, 0.0, 0.0)
PAD_SIZE_MM = (18.0, 12.0)
PAD_BOTTOM_Z_MM = 42.0
PAD_THICKNESS_MM = 2.0
PAD_TOP_Z_MM = PAD_BOTTOM_Z_MM + PAD_THICKNESS_MM
ADHESIVE_THICKNESS_MM = 1.0


def resolve_mount_mode(mode=None):
    mode = SELECTED_MOUNT if mode is None else mode
    if not isinstance(mode, str) or mode not in MOUNT_MODES:
        raise ValueError(f"Unsupported optical attachment mode: {mode!r}")
    return mode
