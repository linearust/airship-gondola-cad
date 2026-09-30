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
OPTICAL_PIVOT_SCREW_LENGTH = 8.0
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

# Selected micro-screw kit: explicit acceptance envelopes, not seller dimensions.
SERVO_SCREW_HEAD_DIAMETER = 3.5
SERVO_SCREW_HEAD_HEIGHT = 1.6
SERVO_SCREW_LENGTH = 8.0
SERVO_SCREW_MATERIAL = "304 stainless steel (seller claim)"

# Rail-only M3 interfaces. Do not propagate these dimensions to the M2 clamps.
# A procurement source has not been selected; these are acceptance envelopes.
RAIL_THREAD_DIAMETER = 3.0
RAIL_THREAD_PITCH = 0.5
RAIL_SCREW_HEAD_DIAMETER = 6.0
RAIL_SCREW_HEAD_HEIGHT = 2.0
RAIL_HEX_NUT_AF = 5.5
RAIL_HEX_NUT_HEIGHT = 2.4
RAIL_FASTENER_MATERIAL = "A2 stainless steel"
RAIL_FASTENER_SOURCE = ""
RAIL_HEAD_ENVELOPE_NOTE = (
    "M3 button head bounded by diameter 6.0 mm x height 2.0 mm; M3 nut bounded "
    "by 5.5 mm across flats x 2.4 mm high. These are design acceptance "
    "envelopes, not measured or published dimensions of a selected supplier. "
    "A2 stainless steel is a design selection; procurement is unverified. "
    "Check actual head, socket and nut dimensions before printing."
)
