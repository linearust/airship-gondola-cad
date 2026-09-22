"""M2 kit interfaces and explicit design envelopes, in millimetres.

The user's 482-piece kit supplies eight bolt lengths, hex nuts and 1.5 mm keys.
Its button-head dimensions have not been supplied. The cylindrical head bounds
below are design acceptance envelopes, NOT a manufacturer's dimensions or a
claim that the head is cylindrical. Measure the purchased lot before printing.
Nut dimensions likewise define the accepted interface, not a verified lot.
"""

THREAD_DIAMETER = 2.0
THREAD_PITCH = 0.4
SCREW_HEAD_DIAMETER = 4.5
SCREW_HEAD_HEIGHT = 2.0
SOCKET_KEY = 1.5
CLAMP_SCREW_LENGTH = 8.0
RAIL_SCREW_LENGTH = 8.0
STACK_SCREW_LENGTH = 5.0
OPTICAL_PIVOT_SCREW_LENGTH = 6.0
HEX_NUT_AF = 4.0
HEX_NUT_MIN_AF = 3.8
HEX_NUT_HEIGHT = 1.6
HEX_NUT_MIN_HEIGHT = 1.4
KIT_SOURCE = "https://www.aliexpress.com/item/1005005551208735.html"
KIT_MATERIAL = "Black steel; seller-stated screw class 10.9, nut grade unverified"
HEAD_ENVELOPE_NOTE = (
    "Unmeasured kit button head represented by a conservative design cylinder "
    "diameter 4.5 mm x height 2.0 mm. This is an acceptance envelope, not a "
    "published head dimension; socket depth and actual head mass are unknown."
)
