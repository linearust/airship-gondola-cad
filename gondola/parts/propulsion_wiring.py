"""Connected planning space from each rear motor-loop bay to the FC.

This is a clearance allocation, not a motor cable model. The moving segment
from the received motor to the bay and the actual attachment hardware are not
known. No geometry here establishes cable bend, fatigue or tension limits.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import create_reference, set_property, union
from gondola.contracts.design import FC_INSTALLATION_LOCAL_YAW_DEG

from . import equipment_mounts, propulsion

V = App.Vector
ROUTE_DIAMETER_MM = 3.0
PLANNING_TURN_RADIUS_MM = 4.0
WORKSPACE_RADIUS_MM = 10.0
WORKSPACE_DEPTH_MM = 6.0
WORKSPACE_X_MM = -38.0
PREFIX_SIGNS = (("Port", 1), ("Starboard", -1))
SOURCE_URL = "https://www.igus.com/contentData/wpck/pdf/US_en/7_guidelines_for_continuousflex_cables.pdf"


def _rounded_path(points, radius):
    """C1 continuous planning centreline; radius is a design allowance only."""
    vertices = [V(*point) for point in points]
    edges = []
    previous = vertices[0]
    for before, vertex, after in zip(vertices, vertices[1:], vertices[2:]):
        incoming = vertex - before
        outgoing = after - vertex
        incoming.normalize()
        outgoing.normalize()
        cosine = max(-1.0, min(1.0, incoming.dot(outgoing)))
        angle = math.acos(cosine)
        if angle < 1e-8:
            continue
        trim = radius * math.tan(angle / 2)
        if trim >= min((vertex - before).Length, (after - vertex).Length) / 2:
            raise ValueError("Route corners overlap; reroute after module adjustment")
        start, end = vertex - incoming * trim, vertex + outgoing * trim
        perpendicular = outgoing - incoming * cosine
        perpendicular.normalize()
        centre = start + perpendicular * radius
        bisector = start + end - centre * 2
        bisector.normalize()
        midpoint = centre + bisector * radius
        if (start - previous).Length > 1e-8:
            edges.append(Part.makeLine(previous, start))
        edges.append(Part.Arc(start, midpoint, end).toShape())
        previous = end
    edges.append(Part.makeLine(previous, vertices[-1]))
    return Part.Wire(edges)


def route_points(sign, propulsion_placement, electronics_placement):
    """Points in propulsion-local coordinates, tracking both stationary modules."""
    if sign not in (-1, 1):
        raise ValueError("Motor side must be -1 or +1")
    board_frame = electronics_placement.multiply(
        App.Placement(V(), App.Rotation(V(0, 0, 1), FC_INSTALLATION_LOCAL_YAW_DEG))
    )
    endpoint = propulsion_placement.inverse().multVec(
        board_frame.multVec(V(24, sign * 10, equipment_mounts.SUPPORT_FACE_Z + 12))
    )
    return [
        (WORKSPACE_X_MM, sign * propulsion.PIVOT_HALF_SPAN, propulsion.PIVOT_Z),
        # Come inward before entering the FC band, leaving the electronics-host
        # optical tower leg and its seated registration envelope clear.
        (-38.0, sign * 20.0, 34.0),
        (endpoint.x, endpoint.y, endpoint.z),
    ]


def route_geometry(sign, propulsion_placement, electronics_placement):
    """Return local reservation plus its layout-dependent geometric basis."""
    points = route_points(sign, propulsion_placement, electronics_placement)
    centreline = _rounded_path(points, PLANNING_TURN_RADIUS_MM)
    start, next_point = V(*points[0]), V(*points[1])
    profile = Part.Wire(
        Part.makeCircle(ROUTE_DIAMETER_MM / 2, start, next_point - start)
    )
    corridor = centreline.makePipeShell([profile], True, False)
    workspace = Part.makeCylinder(
        WORKSPACE_RADIUS_MM,
        WORKSPACE_DEPTH_MM,
        start - V(WORKSPACE_DEPTH_MM / 2, 0, 0),
        V(1, 0, 0),
    )
    shape = union([workspace, corridor])
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Motor lead planning space must be one valid solid")
    return {
        "shape": shape,
        "workspace": workspace,
        "corridor": corridor,
        "centreline": centreline,
        "points": points,
    }


def route_contract(sign, propulsion_placement, electronics_placement):
    prefix = "Port" if sign == 1 else "Starboard"
    return {
        "scope": "Connected rear free-loop workspace to fixed FC access space only. The motor-exit-to-workspace moving lead segment is not modeled.",
        "source_url": SOURCE_URL,
        "source_scope": "General strain-relief and free-movement principles only; no selected miniature motor cable is qualified by this reference.",
        "route_points_in_propulsion_frame_mm": route_points(
            sign, propulsion_placement, electronics_placement
        ),
        "planning_corridor_diameter_mm": ROUTE_DIAMETER_MM,
        "planning_centreline_turn_radius_mm": PLANNING_TURN_RADIUS_MM,
        "free_loop_workspace_radius_mm": WORKSPACE_RADIUS_MM,
        "free_loop_workspace_axial_depth_mm": WORKSPACE_DEPTH_MM,
        "moving_attachment_candidate": {
            "object": prefix + "MotorCarrier",
            "region": "Existing broad rear crossbar toward the shaft axis; avoid motor screws, split clamps and the propeller opening.",
            "qualification": "Tie, tie head, wire exit and full moving cable geometry are unmodeled. The crossbar is a candidate attachment member, not a verified tie location.",
        },
        "fixed_attachment_candidate": {
            "object": "ElectronicsMount",
            "region": "Existing open carrier arm before FC entry, leaving the eight-mm underbody corridor and board damping free.",
            "qualification": "This candidate fixes the FC end to the stationary electronics carrier. It does not claim a separate proven tie on the propulsion frame. Retain slack between independently sliding modules; actual tie fit and load path need a bench check.",
        },
        "servo_leads": "Servo bodies remain fixed. Retain rear case exit allowance and a service loop before the FC; disconnect their leads before removing the deliberately separate servo bridge. No connector or full servo cable route is modeled.",
        "bounded_output_range_deg": [-180, 180],
        "endpoint_wrap_permitted": False,
        "complete_connected_harness_modeled": False,
        "moving_wire_sweep_verified": False,
        "wire_bend_radius_qualified": False,
        "wire_cut_length_verified": False,
        "strain_relief_fit_verified": False,
        "service_prerequisite": "Disconnect leads before removing or sliding either module. Rail adjustment requires rerouting and regeneration of this layout-specific reservation, then clearance and actual slack checks.",
        "bench_check": "With the received motor wires and connectors, sweep each pod slowly through both bounded directions and opposite-pod combinations. Confirm no tension, rubbing, pinching or entry into gears/shafts/propellers; qualify actual bend radius and fastening. Equal solid poses at -180 and +180 do not imply equal wire winding states.",
    }


def build_reserves(doc, propulsion_group, electronics_group):
    """No added printed/bought parts; return two inspectable clearance objects."""
    doc.recompute()
    propulsion_placement = propulsion_group.getGlobalPlacement()
    electronics_placement = electronics_group.getGlobalPlacement()
    objects = []
    for prefix, sign in PREFIX_SIGNS:
        geometry = route_geometry(sign, propulsion_placement, electronics_placement)
        contract = route_contract(sign, propulsion_placement, electronics_placement)
        obj = create_reference(
            doc,
            propulsion_group,
            prefix + "PhaseLeadLoopReserve",
            prefix + " connected motor-lead planning space",
            geometry["shape"],
            contract["scope"] + " " + contract["service_prerequisite"],
            SOURCE_URL,
        )
        obj.Role = "Clearance"
        obj.Label = "RESERVE | " + prefix + " loop workspace to FC"
        set_property(obj, "WiringContract", json.dumps(contract, sort_keys=True))
        set_property(obj, "MovingWireSweepVerified", False, "App::PropertyBool")
        set_property(obj, "CompleteHarnessModeled", False, "App::PropertyBool")
        objects.append(obj)
    return objects
