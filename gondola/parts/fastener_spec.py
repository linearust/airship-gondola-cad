"""Shared M2 purchased-hardware dimensions, independent of FreeCAD and parts.

Dimensions are nominal millimetres. They describe purchasing interfaces rather
than proven load capacity, thread retention or an approved supplier lot.
"""

THREAD_DIAMETER = 2.0
THREAD_PITCH = 0.4
SCREW_HEAD_DIAMETER = 3.8
SCREW_HEAD_HEIGHT = 2.0
SOCKET_KEY = 1.5
SOCKET_DEPTH = 1.0
JOURNAL_SCREW_LENGTH = 14.0
SET_SCREW_LENGTH = 6.0
SET_SCREW_KEY = 0.9
NUT_AF = 4.0
NUT_HEIGHT = 1.6
SQUARE_NUT_AF = 4.0
# Accu permits 4 - 0.4 mm; PTS lists the narrower range 4.0 - 3.7 mm.
SQUARE_NUT_MIN_AF = 3.6
SQUARE_NUT_HEIGHT = 1.2
SQUARE_NUT_MIN_HEIGHT = 0.8
WASHER_ID = 2.2
WASHER_OD = 5.0
WASHER_THICKNESS = 0.3
WASHER_MAX_ID = 2.34
WASHER_MIN_OD = 4.70
WASHER_MIN_THICKNESS = 0.25
WASHER_MAX_THICKNESS = 0.35
NUT_MIN_BEARING_DIAMETER = 3.2
# ISO 7093-1 / DIN 9021 M3 clearance washer used as an M2 journal retainer.
# Its large outer diameter catches the carrier's D-flat; it is not an M3 thread.
JOURNAL_RETAINING_WASHER_ID = 3.2
JOURNAL_RETAINING_WASHER_OD = 9.0
JOURNAL_RETAINING_WASHER_THICKNESS = 0.8
JOURNAL_RETAINING_WASHER_MAX_ID = 3.38
JOURNAL_RETAINING_WASHER_MIN_OD = 8.64
JOURNAL_RETAINING_WASHER_MIN_THICKNESS = 0.7
JOURNAL_RETAINING_WASHER_MAX_THICKNESS = 0.9
