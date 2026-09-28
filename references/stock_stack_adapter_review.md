# Purchased carbon stack adapter

Authority: [pure part contract](../gondola/contracts/stack_adapter.py),
[retained seller evidence](stock_stack_adapter/product_evidence.json), and
[supplied dimension drawing](stock_stack_adapter/dimension_drawing.png).
The [saved product listing](https://ko.aliexpress.com/item/1005009117550746.html)
is evidence of nominal specifications, not a dimensional inspection.

The selected option is **5PCS**. The seller describes a **30 × 30 × 1 mm carbon
fiber plate**, with a reference mass of **0.72 g per board**. Use the seller mass
separately from any reconstructed solid volume. The general delivery text lists
one board, eight M2 nylon nuts, four M2×6 and four M2×8 screws; this conflicts
with the selected five-board package. Included fastener quantities remain
unconfirmed. Pack quantity does not set the installed quantity.

The drawing labels **25.5, 20 and 16 mm** hole pitches and **Ø2 mm** through-holes.
Their concentric square arrangement follows the illustrated symmetry; separate
vertical dimensions and manufacturing tolerances are absent. The central hole,
four internal cutouts, outer corner blends and web widths are not dimensioned.
Treat any contour tracing as illustrative. A filled 30 mm square is a conservative
external clearance envelope, but does not prove continuous material for a seat
or adhesive patch. Do not locate a mating part using the undimensioned cutouts.

The FC interface uses the **25.5 mm pattern rotated 45°**, placing
its four nominal axes at `(±25.5/√2, 0)` and `(0, ±25.5/√2)` mm about the plate
centre. In BA all four equipment plates clamp directly to twin rail tracks at
opposed **16 mm Y axes**. Two **25.5 mm X axes** carry the removable optical or
power portal; FC uses its existing studs at those axes. There is no printed
saddle or equipment deck. These are project choices, not further seller features.

Carbon retention is rigid and independent of FC damping. The FC board or dampers
must not provide the clamp stop. The complete FC damping/upper fastening stack
remains unverified. Neighboring holes and undimensioned cutouts may interrupt
nut, portal-foot, rail-contact or adhesive areas. Inspect actual contact before
assembly; the filled CAD envelope cannot qualify laminate support or strength.
Battery end overhang and strap retention on the central small plate also require
a physical check. Nominal 3 mm insulating pads for taped devices must retain
clearance above the actual screw heads after compression.

Four boards are installed in the default design. Optional power adds two upper
boards while keeping the four lower boards, requiring six in that configuration.
A five-piece pack does not cover that complete combination. Reusing an empty
battery board would require a deliberately revised configuration and fresh checks.

Three patterns do not mean all holes can be occupied simultaneously. The nearest
same-corner hole centres are 2.828 mm apart for 16/20 mm, 3.889 mm for 20/25.5 mm,
and 6.718 mm for 16/25.5 mm. Adjacent heads, nuts or standoffs can collide. Check
the selected hardware's occupied face and height; Ø2 mm is a nominal hole label,
not an M2 thread or a guaranteed free-running fit.

Carbon fiber is electrically conductive, as the seller also states. Keep exposed
conductors and the FC underside insulated from it. Material lay-up, stiffness,
strength, flatness, actual holes and support footprints remain unverified. This
evidence does not qualify the plate for propulsion loads or every future stack.
