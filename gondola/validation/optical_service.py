"""Access and ordered removal of the rigid, two-screw optical bracket."""

import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, placed_shape, union, world_shape
from gondola.contracts import fasteners

from .geometry import intersection_volume, translation_sweep
from .wiring import collision_hits

V = App.Vector
TOL = 1e-5
TOOL_APPROACH_LENGTH_MM = 15.0
CLAMP_CENTRES = {1: (-19.0, 0.0), 2: (19.0, 0.0)}


def tray_stock_enclosures(shape):
    """Contain the saved portal without filling the space under its pad.

    Independent literal regions include the half-mm load-root blends. Filled
    mounting holes are conservative after both fasteners have left. Unknown
    stock outside these regions fails closed.
    """
    epsilon = 1e-6
    boxes = (
        ((21, 8, 2), (-27, -4, 0)),
        ((21, 8, 2), (6, -4, 0)),
        ((12, 3, 2), (-6, 1, 0)),
        ((4, 8, 17), (-25.5, -4, 1.5)),
        ((4, 8, 17), (21.5, -4, 1.5)),
        ((50, 4, 2), (-25, -2, 18.5)),
        ((18, 12, 2), (-9, -6, 18.5)),
    )
    regions = []
    for size, origin in boxes:
        lower = [value - epsilon for value in origin]
        dimensions = [value + 2 * epsilon for value in size]
        # Keep the seated face exact: expansion below it creates a false plate
        # collision during vertical lift.
        if origin[2] == 0:
            lower[2], dimensions[2] = 0, size[2] + epsilon
        region = Part.makeBox(*dimensions, V(*lower))
        region.Placement = shape.Placement
        regions.append(region)
    return regions, abs(shape.cut(union(regions)).Volume)


def mount_tool_shapes():
    """Two straight M2 hex-key approaches in rigid bracket coordinates."""
    return {
        f"OpticalFootBolt{index}": Part.makeCylinder(
            fasteners.SOCKET_KEY / math.sqrt(3),
            TOOL_APPROACH_LENGTH_MM,
            V(x, y, -2 - fasteners.SCREW_HEAD_HEIGHT),
            V(0, 0, -1),
        )
        for index, (x, y) in CLAMP_CENTRES.items()
    }


def mount_tool_check(group, obstacles):
    """Retain every obstacle except the screw socket being accessed."""
    rows = []
    for target, local in mount_tool_shapes().items():
        tool = placed_shape(local, group.getGlobalPlacement())
        hits = collision_hits(
            tool,
            {name: shape for name, shape in obstacles.items() if name != target},
            tolerance=TOL,
        )
        rows.append({"target": target, "collisions": hits, "passed": not hits})
    return {
        "key_across_flats_mm": fasteners.SOCKET_KEY,
        "straight_approach_length_mm": TOOL_APPROACH_LENGTH_MM,
        "tools": rows,
        "passed": len(rows) == 2 and all(row["passed"] for row in rows),
        "scope": "Straight 1.5 mm hex-key legs below the two M2 mounting heads. Actual sockets, handles, hands, thread rotation and cable slack are not modeled. Disconnect leads and support the instruments before removing the rigid bracket.",
    }


def mounting_service_check(doc, physical, kit):
    """Remove both nuts and screws, then lift the supported bracket and sensor.

    All physical parts outside the bracket remain obstacles, including the FC,
    common plate, rail, instrument joint and unknown registered parts. The path
    uses the actual saved bracket frame, including oblique module placement.
    """
    group = doc.OpticalFlowModule
    inverse = group.getGlobalPlacement().inverse()

    def local(obj):
        shape = world_shape(obj)
        shape.Placement = inverse.multiply(shape.Placement)
        return shape

    remaining = {obj.Name: local(obj) for obj in kit}
    fixed = {
        obj.Name: local(obj) for obj in physical if not belongs_to_group(obj, group)
    }
    required = {"OpticalSensorTray", "ModuleMTF02PEnvelope"} | {
        f"OpticalFoot{kind}{index}"
        for kind in ("Nut", "Bolt")
        for index in CLAMP_CENTRES
    }
    missing = sorted(required - set(remaining))
    if missing:
        return {"missing_parts": missing, "paths": [], "passed": False}
    rows = []

    def path(name, shape, points, obstacles, *, tray=False):
        regions = [shape]
        enclosure = None
        if tray:
            regions, uncovered = tray_stock_enclosures(shape)
            enclosure = {
                "kind": "literal foot, two legs, crossbar and adhesive pad",
                "uncovered_saved_stock_mm3": uncovered,
                "passed": uncovered <= TOL,
            }
        segments = []
        for start, end in zip(points, points[1:]):
            hits, methods = [], set()
            for region in regions:
                moving = region.copy()
                moving.translate(V(*start))
                sweep, method = translation_sweep(
                    moving, tuple(b - a for a, b in zip(start, end))
                )
                methods.add(method)
                hits.extend(
                    {"object": other, "intersection_mm3": volume}
                    for other, target in obstacles.items()
                    if (volume := intersection_volume(sweep, target)) > TOL
                )
            segments.append(
                {
                    "start_mm": start,
                    "end_mm": end,
                    "methods": sorted(methods),
                    "collisions": hits,
                    "passed": not hits,
                }
            )
        rows.append(
            {
                "part": name,
                "conservative_enclosure": enclosure,
                "segments": segments,
                "passed": all(row["passed"] for row in segments)
                and (enclosure is None or enclosure["passed"]),
            }
        )

    for index, (x, _) in CLAMP_CENTRES.items():
        name = f"OpticalFootNut{index}"
        shape = remaining.pop(name)
        outward = -10.0 if x < 0 else 10.0
        path(
            name,
            shape,
            [(0, 0, 0), (0, 0, 4.7), (0, 8, 4.7), (outward, 8, 4.7), (outward, 8, 40)],
            {**fixed, **remaining},
        )
    for index in CLAMP_CENTRES:
        name = f"OpticalFootBolt{index}"
        shape = remaining.pop(name)
        path(name, shape, [(0, 0, 0), (0, 0, -8.2)], {**fixed, **remaining})
    for name, shape in remaining.items():
        path(
            "CompleteOpticalBracket/" + name,
            shape,
            [(0, 0, 0), (0, 10, 0), (0, 10, 40)],
            fixed,
            tray=name == "OpticalSensorTray",
        )
    return {
        "paths": rows,
        "retained_parts": sorted(fixed),
        "moving_parts": sorted(remaining),
        "passed": all(row["passed"] for row in rows),
        "scope": "Disconnect sensor leads and support the bracket. Unthread each pocket-held nut beyond its screw tip, move it +Y around its leg, outward in X, then lift. Withdraw both screws through the common plate, slide the bracket and sensor together 10 mm toward +Y to clear the FC, then lift 40 mm. All other installed physical solids remain obstacles. This continuous rigid-body reservation does not qualify hand access, thread engagement, retention or connected-cable service; the FC is serviced only after this bracket has been removed.",
    }
