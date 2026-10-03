"""Two output bearings and one input bearing in a shared keyed split housing.

Coordinates are relative to the inboard bearing axis. All three nominal diameter-6
seats are finish-to-fit; hard cap lands, not bearing compression, take bolt load.
The two side keys locate the cap before tightening. Match the printed coupon to
received bearings; nominal geometry does not establish PA12 fit or load capacity.
"""

import FreeCAD as App
import Part

from gondola.cad import box, translated_shape, union

SEAT_RADIUS = 3.0
BEARING_WIDTH = 2.5
BEARING_CENTRES_Y = (0.0, 13.0)
INPUT_BEARING_X = 16.0
INPUT_BEARING_Y = 5.0
INPUT_BODY_FRONT_Y, INPUT_BODY_REAR_Y = 1.0, 9.0
INPUT_BODY_OUTER_X = 26.5
INPUT_WING_ROOT_RADIUS = 0.75
CAP_FASTENER_STATIONS = (
    ("Negative", -5.5, INPUT_BEARING_Y),
    ("Input", 23.0, INPUT_BEARING_Y),
)
SEAT_WIDTH = 3.0
BEARING_AXIAL_FLOAT = SEAT_WIDTH - BEARING_WIDTH
SHIELD_OPENING_DIAMETER = 5.6
BODY_HALF_WIDTH = 9.0
BODY_FRONT_Y, BODY_REAR_Y = -3.0, 16.0
BODY_BOTTOM_Z = -8.0
CAP_BOTTOM_Z, CAP_TOP_Z = 0.0, 4.5
CAP_SCREW_SEAT_Z = CAP_TOP_Z
CAP_NUT_SEAT_Z = -2.5
CAP_NUT_POCKET_AF = 4.25
CAP_NUT_POCKET_HEIGHT = 1.8
CAP_KEY_HEIGHT = 1.5
GEAR_STOP_Y = -4.0
GEAR_STOP_OUTER_RADIUS = 4.5


def _cylinder(radius, start_y, length):
    return Part.makeCylinder(
        radius, length, App.Vector(0, start_y, 0), App.Vector(0, 1, 0)
    )


def _checked(shape, label):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError(f"{label}: expected one valid solid")
    return shape


def seat_tools():
    return union(
        [
            _cylinder(
                SHIELD_OPENING_DIAMETER / 2,
                GEAR_STOP_Y - 0.1,
                BODY_REAR_Y - GEAR_STOP_Y + 0.2,
            ),
            translated_shape(
                _cylinder(
                    SHIELD_OPENING_DIAMETER / 2,
                    INPUT_BODY_FRONT_Y - 0.1,
                    INPUT_BODY_REAR_Y - INPUT_BODY_FRONT_Y + 0.2,
                ),
                x=INPUT_BEARING_X,
            ),
            translated_shape(
                _cylinder(SEAT_RADIUS, INPUT_BEARING_Y - SEAT_WIDTH / 2, SEAT_WIDTH),
                x=INPUT_BEARING_X,
            ),
            *[
                _cylinder(SEAT_RADIUS, y - SEAT_WIDTH / 2, SEAT_WIDTH)
                for y in BEARING_CENTRES_Y
            ],
        ]
    )


def cap_keys():
    """Opposed side keys locate X and Y without thinning either axial shoulder."""
    return union(
        [
            box(3, 3, CAP_KEY_HEIGHT, (x, 0, 0))
            for x in (-BODY_HALF_WIDTH, BODY_HALF_WIDTH - 3)
        ]
    )


def screw_tools():
    return union(
        [
            Part.makeCylinder(1.1, 20, App.Vector(x, y, -10))
            for _, x, y in CAP_FASTENER_STATIONS
        ]
    )


def nut_pocket_tools():
    """Side-entry straight flats retain ordinary nuts without a thin outer wall."""
    from .purchased_hardware import hex_prism

    cuts = []
    for label, x, y in CAP_FASTENER_STATIONS:
        cuts.append(
            translated_shape(
                hex_prism(
                    CAP_NUT_POCKET_AF,
                    CAP_NUT_POCKET_HEIGHT,
                    CAP_NUT_SEAT_Z - CAP_NUT_POCKET_HEIGHT,
                ),
                x=x,
                y=y,
            )
        )
        cuts.append(
            box(
                3.6,
                CAP_NUT_POCKET_AF,
                CAP_NUT_POCKET_HEIGHT,
                (
                    x if x > 0 else -9.1,
                    y - CAP_NUT_POCKET_AF / 2,
                    CAP_NUT_SEAT_Z - CAP_NUT_POCKET_HEIGHT,
                ),
            )
        )
    return union(cuts)


def _housing_stock(bottom_z):
    body = box(
        2 * BODY_HALF_WIDTH,
        BODY_REAR_Y - BODY_FRONT_Y,
        CAP_TOP_Z - bottom_z,
        (-BODY_HALF_WIDTH, BODY_FRONT_Y, bottom_z),
    )
    body = body.fuse(
        box(
            INPUT_BODY_OUTER_X - BODY_HALF_WIDTH + 1,
            INPUT_BODY_REAR_Y - INPUT_BODY_FRONT_Y,
            CAP_TOP_Z - bottom_z,
            (BODY_HALF_WIDTH - 1, INPUT_BODY_FRONT_Y, bottom_z),
        )
    )
    from .edge_blends import fillet_selected, near

    # Concave plan-view roots join the T wing without extending into the
    # distal shaft/tool corridor. Both halves share this exact split outline.
    body = fillet_selected(
        body.removeSplitter(),
        INPUT_WING_ROOT_RADIUS,
        lambda edge, bounds: (
            near(bounds.XMin, BODY_HALF_WIDTH)
            and near(bounds.XLength, 0)
            and near(bounds.YLength, 0)
            and any(
                near(bounds.YMin, y) for y in (INPUT_BODY_FRONT_Y, INPUT_BODY_REAR_Y)
            )
            and near(bounds.ZLength, CAP_TOP_Z - bottom_z)
        ),
        2,
        "Shared bearing T-wing concave roots",
    )
    # This separate broad thrust land contacts the gear web, never a shield.
    return body.fuse(_cylinder(GEAR_STOP_OUTER_RADIUS, GEAR_STOP_Y, 1)).removeSplitter()


def lower_housing_shape(bottom_z=BODY_BOTTOM_Z):
    stock = _housing_stock(bottom_z).common(box(45, 30, -bottom_z, (-15, -8, bottom_z)))
    return _checked(
        stock.fuse(cap_keys())
        .cut(seat_tools())
        .cut(screw_tools())
        .cut(nut_pocket_tools()),
        "Integrated lower bearing housing",
    )


def cap_shape():
    stock = _housing_stock(BODY_BOTTOM_Z).common(box(45, 30, CAP_TOP_Z, (-15, -8, 0)))
    cap = _checked(
        stock.cut(cap_keys()).cut(seat_tools()).cut(screw_tools()), "Paired bearing cap"
    )
    from .edge_blends import fillet_selected, near

    # Round only the free upper perimeter. Keep the gear-stop front edge,
    # all screw bores, head-bearing lands and the complete split face unchanged.
    return fillet_selected(
        cap,
        0.3,
        lambda edge, bounds: (
            type(edge.Curve).__name__ == "Line"
            and near(bounds.ZMin, CAP_TOP_Z)
            and near(bounds.ZLength, 0)
            and not (near(bounds.YMin, BODY_FRONT_Y) and near(bounds.YLength, 0))
        ),
        7,
        "Bearing cap free upper perimeter",
    )


def cup_shape():
    """Production lower capture cropped to a coupon-height backing."""
    return lower_housing_shape()


def keeper_shape():
    """Compatibility entry point: the production shared bearing cap."""
    return cap_shape()


def coupon_shape():
    return _checked(
        cup_shape().fuse(box(39.5, 23, 3, (-11, -5, -11))),
        "Paired bearing housing coupon",
    )


def geometry_check(cup=None, keeper=None):
    """Builder smoke check; independent saved-solid witnesses live in validation."""
    lower = cup if cup is not None else cup_shape()
    cap = keeper if keeper is not None else cap_shape()
    complete = lower.fuse(cap)
    bearings = [
        _cylinder(3, y - 1.25, 2.5).cut(_cylinder(1.5, y - 1.3, 2.6))
        for y in BEARING_CENTRES_Y
    ] + [
        translated_shape(
            _cylinder(3, INPUT_BEARING_Y - 1.25, 2.5).cut(
                _cylinder(1.5, INPUT_BEARING_Y - 1.3, 2.6)
            ),
            x=INPUT_BEARING_X,
        )
    ]
    overlaps = [complete.common(b).Volume for b in bearings]
    seats = lower.common(cap).Volume
    result = {
        "valid_single_solid": lower.isValid() and len(lower.Solids) == 1,
        "valid_keeper_solid": cap.isValid() and len(cap.Solids) == 1,
        "bearing_count": 3,
        "input_bearing_axis_x_mm": INPUT_BEARING_X,
        "bearing_centres_y_mm": list(BEARING_CENTRES_Y),
        "bearing_solid_overlap_mm3": overlaps,
        "cap_body_overlap_mm3": seats,
        "nominal_axial_endplay_mm": BEARING_AXIAL_FLOAT,
        "nominal_diametral_clearance_mm": 0,
        "scope": "Nominal split seats with positive side-key registration and hard cap lands. Finish for snug bearing insertion and matching cap keys; bolts must not remove radial play or preload bearings. Shield lands, manufactured fit and loaded retention require physical checks.",
    }
    result["passed"] = (
        result["valid_single_solid"]
        and result["valid_keeper_solid"]
        and max([seats, *overlaps]) < 1e-7
    )
    return result
