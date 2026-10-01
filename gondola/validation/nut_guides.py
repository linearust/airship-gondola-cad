"""Independent saved-geometry witnesses for the eight shallow M2 nut guides."""

import math

import FreeCAD as App
import Part

from gondola.cad import world_shape

from .geometry import intersection_volume, translation_sweep

V = App.Vector
TOL = 1e-5


def is_guided_nut_bolt(name):
    return name in {
        prefix + joint + side + "Bolt"
        for prefix in ("Port", "Starboard")
        for joint in ("OutputClamp", "OutputBearingKeeper")
        for side in ("Negative", "Positive")
    }


def guided_nut_service_direction(doc, bolt_name):
    """Open-side lateral route after the nut clears the one-millimetre rails."""
    if not is_guided_nut_bolt(bolt_name):
        return None
    prefix = "Port" if bolt_name.startswith("Port") else "Starboard"
    if "OutputClamp" in bolt_name:
        parent, direction = doc.getObject(prefix + "Pod"), V(-1, 0, 0)
    else:
        parent, direction = doc.getObject("MainPropulsionModule"), V(1, 0, 0)
    return tuple(parent.getGlobalPlacement().Rotation.multVec(direction))


def _hex_face(across_flats):
    radius = across_flats / math.sqrt(3)
    points = [
        V(radius * math.cos(i * math.pi / 3), radius * math.sin(i * math.pi / 3), 0)
        for i in range(6)
    ]
    return Part.Face(Part.makePolygon(points + points[:1]))


def nut_guide_check(host_shape, placement, rail_length):
    """Check actual host stock in a frame whose unchanged nut seat is Z0.

    Literal dimensions below deliberately do not import the production guide
    builder. The small-nut rotation probes describe ideal sharp hex flanks;
    received chamfers and physical torque capacity remain unqualified.
    """
    host = host_shape.copy()
    host.Placement = placement.inverse().multiply(host.Placement)
    rails = []
    for side in (-1, 1):
        witness = Part.makeBox(
            rail_length,
            1.5,
            1.0,
            V(-rail_length / 2, side * 2.125 - (1.5 if side < 0 else 0), 0),
        )
        missing = abs(witness.cut(host).Volume)
        rails.append(
            {"side": side, "missing_rail_mm3": missing, "passed": missing < TOL}
        )

    # The disk swept by a nominal M2 shank in its unchanged diameter2.2 hole.
    offsets = [(0.0, 0.0)] + [
        (0.1 * math.cos(i * math.pi / 4), 0.1 * math.sin(i * math.pi / 4))
        for i in range(8)
    ]
    maximum = _hex_face(4.0).extrude(V(0, 0, 1.6))
    minimum = _hex_face(3.8).extrude(V(0, 0, 1.35))
    # Exclude the entire bore plus the declared axis float from the floor probe.
    bearing_face = _hex_face(3.8).cut(Part.Face(Part.Wire(Part.makeCircle(1.2))))
    fits, stops = [], []
    for dx, dy in offsets:
        nut = maximum.copy()
        nut.translate(V(dx, dy, 0))
        swept, method = translation_sweep(nut, (0, 0, 3))
        collision = intersection_volume(host, swept)
        foot = bearing_face.copy()
        foot.translate(V(dx, dy, 0))
        missing_support = foot.cut(host).Area
        fits.append(
            {
                "axis_offset_xy_mm": [dx, dy],
                "maximum_nut_insertion_removal_overlap_mm3": collision,
                "missing_flat_nut_seat_mm2": missing_support,
                "method": method,
                "passed": collision < TOL and missing_support < TOL,
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
        "rail_witnesses": rails,
        "nut_fit_and_axial_service": fits,
        "minimum_nut_rotation_stops": stops,
        "nominal_clear_gap_mm": 4.25,
        "guide_height_mm": 1.0,
        "finished_gap_acceptance_mm": [4.2, 4.3],
        "maximum_nut_af_height_mm": [4.0, 1.6],
        "minimum_nut_af_height_mm": [3.8, 1.35],
        "nominal_axis_float_radius_mm": 0.1,
        "physical_fit_verified": False,
        "scope": "Nominal sharp-hex geometry at the fixed axis and eight boundary directions of its 0.1 mm circular clearance. Axial insertion/removal is continuous for each tested offset; transverse float and nut rotation are sampled. Both literal rails and complete flat bearing lands must remain. Coupon-check the finished 4.2–4.3 mm gap, actual chamfers, full seating, engagement and torque restraint. This is not a strength, preload, as-printed tolerance or full nut-rotation/service proof; installed drive motion and ordered service remain separate checks.",
        "passed": all(row["passed"] for row in rails + fits + stops),
    }


def installed_nut_guide_checks(doc):
    """Enumerate all four carrier and four keeper seats from native parents."""
    rows = []
    module = doc.getObject("MainPropulsionModule")
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        pod = doc.getObject(prefix + "Pod")
        for side, suffix in ((-1, "Negative"), (1, "Positive")):
            for kind, host_name, nut_name, parent, local, length in (
                (
                    "rotor_clamp",
                    prefix + "MotorCarrier",
                    prefix + "OutputClamp" + suffix + "Nut",
                    pod,
                    App.Placement(V(4.2, side * 26.25, 2.5), App.Rotation()),
                    5.8,
                ),
                (
                    "bearing_keeper",
                    "PropulsionFixedFrame",
                    prefix + "OutputBearingKeeper" + suffix + "Nut",
                    module,
                    App.Placement(
                        V(0, sign * 75 + side * 37.75, 32),
                        App.Rotation(V(0, 0, 1), V(0, side, 0)),
                    ),
                    6.0,
                ),
            ):
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
                report = nut_guide_check(world_shape(host), pose, length)
                expected_nut = (
                    _hex_face(4)
                    .extrude(V(0, 0, 1.6))
                    .cut(Part.makeCylinder(1, 1.8, V(0, 0, -0.1)))
                )
                expected_nut.Placement = pose
                actual_nut = world_shape(nut)
                difference = abs(expected_nut.cut(actual_nut).Volume) + abs(
                    actual_nut.cut(expected_nut).Volume
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
