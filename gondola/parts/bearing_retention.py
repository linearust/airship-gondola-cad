"""Two purchased bearings in a rigid split housing and positively located cap.

Coordinates are relative to the inboard bearing axis. Both nominal diameter-6
seats are finish-to-fit; hard cap lands, not bearing compression, take bolt load.
The two side keys locate the cap before tightening. Match the printed coupon to
received bearings; nominal geometry does not establish PA12 fit or load capacity.
"""

import FreeCAD as App
import Part

from gondola.cad import box, translated_shape, union

BEARING_RADIUS = SEAT_RADIUS = 3.0
BEARING_WIDTH = 2.5
BEARING_CENTRES_Y = (0.0, 13.0)
SEAT_WIDTH = 3.0
BEARING_AXIAL_FLOAT = SEAT_WIDTH - BEARING_WIDTH
SHIELD_OPENING_DIAMETER = 5.6
BODY_HALF_WIDTH = 9.0
BODY_FRONT_Y, BODY_REAR_Y = -3.0, 16.0
BODY_BOTTOM_Z = -8.0
CAP_BOTTOM_Z, CAP_TOP_Z = 0.0, 4.5
CAP_BOLT_X = (-5.5, 5.5)
CAP_BOLT_Y = 6.5
CAP_SCREW_SEAT_Z = CAP_TOP_Z
CAP_NUT_SEAT_Z = -2.5
CAP_SCREW_LENGTH = 10.0
CAP_NUT_POCKET_AF = 4.25
CAP_NUT_POCKET_HEIGHT = 1.8
CAP_KEY_HEIGHT = 1.5
GEAR_STOP_Y = -4.0
GEAR_STOP_OUTER_RADIUS = 4.5
SHOULDER_THICKNESS = 1.5


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
        [Part.makeCylinder(1.1, 20, App.Vector(x, CAP_BOLT_Y, -10)) for x in CAP_BOLT_X]
    )


def nut_pocket_tools():
    """Side-entry straight flats retain ordinary nuts without a thin outer wall."""
    from .purchased_hardware import hex_prism

    cuts = []
    for x in CAP_BOLT_X:
        cuts.append(
            translated_shape(
                hex_prism(
                    CAP_NUT_POCKET_AF,
                    CAP_NUT_POCKET_HEIGHT,
                    CAP_NUT_SEAT_Z - CAP_NUT_POCKET_HEIGHT,
                ),
                x=x,
                y=CAP_BOLT_Y,
            )
        )
        cuts.append(
            box(
                3.6,
                CAP_NUT_POCKET_AF,
                CAP_NUT_POCKET_HEIGHT,
                (
                    x if x > 0 else -9.1,
                    CAP_BOLT_Y - CAP_NUT_POCKET_AF / 2,
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
    # This separate broad thrust land contacts the gear web, never a shield.
    return body.fuse(_cylinder(GEAR_STOP_OUTER_RADIUS, GEAR_STOP_Y, 1)).removeSplitter()


def lower_housing_shape(bottom_z=BODY_BOTTOM_Z):
    stock = _housing_stock(bottom_z).common(box(30, 30, -bottom_z, (-15, -8, bottom_z)))
    return _checked(
        stock.fuse(cap_keys())
        .cut(seat_tools())
        .cut(screw_tools())
        .cut(nut_pocket_tools()),
        "Integrated lower bearing housing",
    )


def cap_shape():
    stock = _housing_stock(BODY_BOTTOM_Z).common(box(30, 30, CAP_TOP_Z, (-15, -8, 0)))
    return _checked(
        stock.cut(cap_keys()).cut(seat_tools()).cut(screw_tools()), "Paired bearing cap"
    )


def cup_shape():
    """Production lower capture cropped to a coupon-height backing."""
    return lower_housing_shape()


def keeper_shape():
    """Compatibility entry point: the production shared bearing cap."""
    return cap_shape()


def coupon_shape():
    return _checked(
        cup_shape().fuse(box(22, 23, 3, (-11, -5, -11))),
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
    ]
    overlaps = [complete.common(b).Volume for b in bearings]
    seats = lower.common(cap).Volume
    result = {
        "valid_single_solid": lower.isValid() and len(lower.Solids) == 1,
        "valid_keeper_solid": cap.isValid() and len(cap.Solids) == 1,
        "bearing_count": 2,
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
