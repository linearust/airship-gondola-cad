"""Independent stock, fit and side-entry checks for four cap and two jack nuts."""

import math

import FreeCAD as App
import Part

from gondola.cad import world_shape

from .geometry import intersection_volume, translation_sweep

V = App.Vector
TOL = 1e-5


def _hex_face(across_flats):
    radius = across_flats / math.sqrt(3)
    points = [
        V(radius * math.cos(i * math.pi / 3), radius * math.sin(i * math.pi / 3), 0)
        for i in range(6)
    ]
    return Part.Face(Part.makePolygon(points + points[:1]))


def nut_guide_check(host_shape, placement, *, outward_sign, floor_thickness):
    """Check a side-entry pocket in a nut frame with bearing plane Z0.

    Positive Z enters the nut from its bearing plane; the slot opens along X.
    Literal stock witnesses and complete swept maximum nut envelopes are
    independent of the production pocket constructors.
    """
    if outward_sign not in (-1, 1) or floor_thickness not in (2.5, 3.0):
        raise ValueError("Expected a cap or jack side-entry nut datum")
    host = host_shape.copy()
    host.Placement = placement.inverse().multiply(host.Placement)
    walls = []
    for side in (-1, 1):
        witness = Part.makeBox(2, 1.5, 1.8, V(-1, 2.125 if side > 0 else -3.625, 0))
        missing = abs(witness.cut(host).Volume)
        walls.append(
            {"side": side, "missing_wall_mm3": missing, "passed": missing < TOL}
        )
    bearing_face = _hex_face(3.8).cut(Part.Face(Part.Wire(Part.makeCircle(1.2))))
    offsets = [(0.0, 0.0)] + [
        (0.1 * math.cos(i * math.pi / 4), 0.1 * math.sin(i * math.pi / 4))
        for i in range(8)
    ]
    maximum = _hex_face(4).extrude(V(0, 0, 1.6))
    minimum = _hex_face(3.8).extrude(V(0, 0, 1.35))
    fits, stops = [], []
    for dx, dy in offsets:
        nut = maximum.copy()
        nut.translate(V(dx, dy, 0))
        lift, lift_method = translation_sweep(nut, (0, 0, 0.2))
        nut.translate(V(0, 0, 0.2))
        lateral, lateral_method = translation_sweep(nut, (outward_sign * 25, 0, 0))
        collision = max(
            intersection_volume(host, lift), intersection_volume(host, lateral)
        )
        floor = bearing_face.extrude(V(0, 0, -floor_thickness))
        floor.translate(V(dx, dy, 0))
        missing_floor = abs(floor.cut(host).Volume)
        fits.append(
            {
                "axis_offset_xy_mm": [dx, dy],
                "maximum_nut_side_entry_overlap_mm3": collision,
                "missing_bearing_floor_mm3": missing_floor,
                "methods": [lift_method, lateral_method],
                "passed": collision < TOL and missing_floor < TOL,
            }
        )
        for angle in (-30, 30):
            nut = minimum.copy()
            nut.rotate(V(), V(0, 0, 1), angle)
            nut.translate(V(dx, dy, 0))
            penetration = intersection_volume(host, nut)
            stops.append(
                {
                    "axis_offset_xy_mm": [dx, dy],
                    "attempted_rotation_deg": angle,
                    "rotation_stop_penetration_mm3": penetration,
                    "passed": penetration > TOL,
                }
            )
    return {
        "wall_witnesses": walls,
        "nut_fit_and_side_entry": fits,
        "minimum_nut_rotation_stops": stops,
        "nominal_clear_gap_mm": 4.25,
        "slot_height_mm": 1.8,
        "minimum_bearing_floor_mm": floor_thickness,
        "maximum_nut_af_height_mm": [4, 1.6],
        "minimum_nut_af_height_mm": [3.8, 1.35],
        "nominal_axis_float_radius_mm": 0.1,
        "physical_fit_verified": False,
        "scope": "Actual pocket walls and the full bearing floor must contain literal stock. Maximum sharp hex nuts clear a continuous0.2mm release then25mm side exit at the fixed axis and eight0.1mm boundary offsets. Minimum nuts meet rotation stops at±30 degrees. Transverse float and nut rotation are sampled; actual chamfers, manufactured clearance, torque restraint and strength need physical checks. Cap screws must leave before their nuts; rotor jack service occurs on the removed rotor.",
        "passed": all(row["passed"] for row in walls + fits + stops),
    }


def installed_nut_guide_checks(doc):
    """Audit four cap side slots and the two sole rotor jack pockets."""
    rows = []
    module = doc.getObject("MainPropulsionModule")
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        sites = [
            (
                "bearing_cap",
                "PropulsionFixedFrame",
                prefix + "BearingCap" + suffix + "Nut",
                module,
                App.Placement(
                    V(sign * x, sign * y, 47.5), App.Rotation(V(1, 0, 0), 180)
                ),
                sign * (-1 if x < 0 else 1),
                2.5,
            )
            for x, y, suffix in ((-5.5, 33.0, "Negative"),)
        ]
        sites.append(
            (
                "input_bearing_cap",
                "PropulsionFixedFrame",
                prefix + "BearingCapInputNut",
                module,
                App.Placement(
                    V(sign * 23, sign * 33, 47.5), App.Rotation(V(1, 0, 0), 180)
                ),
                sign,
                2.5,
            )
        )
        sites.append(
            (
                "rotor_jack",
                prefix + "MotorCarrier",
                prefix
                + "OutputClamp"
                + ("Negative" if sign > 0 else "Positive")
                + "Nut",
                doc.getObject(prefix + "Pod"),
                App.Placement(
                    V(8, -sign * 25.5, 0), App.Rotation(V(0, 0, 1), V(-1, 0, 0))
                ),
                1,
                3.0,
            )
        )
        for kind, host_name, nut_name, parent, local, direction, floor in sites:
            host, nut = doc.getObject(host_name), doc.getObject(nut_name)
            if host is None or nut is None or parent is None:
                rows.append(
                    {
                        "nut": nut_name,
                        "error": "Missing guide host, nut or native parent",
                        "passed": False,
                    }
                )
                continue
            pose = parent.getGlobalPlacement().multiply(local)
            report = nut_guide_check(
                world_shape(host), pose, outward_sign=direction, floor_thickness=floor
            )
            expected = (
                _hex_face(4)
                .extrude(V(0, 0, 1.6))
                .cut(Part.makeCylinder(1, 1.8, V(0, 0, -0.1)))
            )
            expected.Placement = pose
            actual = world_shape(nut)
            difference = abs(expected.cut(actual).Volume) + abs(
                actual.cut(expected).Volume
            )
            rows.append(
                {
                    "site": kind,
                    "host": host_name,
                    "nut": nut_name,
                    "nominal_saved_nut_difference_mm3": difference,
                    **report,
                    "passed": report["passed"] and difference < TOL,
                }
            )
    return rows
