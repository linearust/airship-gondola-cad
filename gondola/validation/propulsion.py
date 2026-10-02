"""Recompute local propulsion fit and removal evidence from current geometry.

Rigid envelopes preserve explicit OEM fit, clamp grip and load limitations.
The checks cover supported gearing, separate shafts, positive bearing capture
and practical disassembly geometry without certifying physical operation.
"""

import json
import math
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

from gondola.cad import (
    translated_shape,
    world_shape,
)
from gondola.config import ARTIFACT_STEM, OUTPUT_DIR
from gondola.contracts.drive import (
    SELECTED_DRIVE,
    drive_for_document,
)
from gondola.parts import propulsion, rail, servo_bridge
from gondola.print_export import mesh_checks, print_shape

from .bearing_capture import split_bearing_stack_check, split_cap_seating_check
from .drive_kinematics import (
    drive_motion_check as drive_motion_check,
)
from .drive_kinematics import (
    fixed_servo_datum_check as fixed_servo_datum_check,
)
from .drive_kinematics import (
    gear_engagement_check as gear_engagement_check,
)
from .drive_kinematics import (
    gear_mesh_check as gear_mesh_check,
)
from .drive_kinematics import (
    gear_rotation_check as gear_rotation_check,
)
from .evidence import overlap_failures
from .fastener_seating import clamp_fastener_check as clamp_fastener_check
from .geometry import (
    belongs_to_group,
    intersection_volume,
)
from .horn_coupling import horn_registration_check as horn_registration_check
from .motion_clearance import carrier_axial_travel, carrier_metal_clearance_check
from .propulsion_evidence import PROPULSION_EVIDENCE_COUNTS, propulsion_evidence_check
from .propulsion_service import (
    contained_region_paths,
    continuous_path,
    driver_full_rotation_clearance_check,
    driver_service_segment_check,
    fastener_service_check,
    module_service_shapes,
    retained_obstacles,
    servo_bench_members,
    split_housing_vertical_service,
)
from .rail_contact import attachment_check
from .relative_motion import relative_motion_check
from .servo_interface import horn_spline_contact
from .servo_module import integrated_frame_check, servo_service_preparation_check
from .shaft_retention import (
    carrier_shaft_retention_check as carrier_shaft_retention_check,
)
from .shaft_retention import (
    direct_adapter_fit_check as direct_adapter_fit_check,
)
from .shaft_retention import (
    input_shaft_retention_check as input_shaft_retention_check,
)
from .shaft_retention import (
    output_shaft_name,
)
from .shaft_retention import (
    output_stub_check as output_stub_check,
)

TOL = 1e-5


def _positive_module_shapes(doc, prefix, objects):
    """Normalize actual placements to module coordinates, +Y toward this rotor."""
    inverse = doc.MainPropulsionModule.getGlobalPlacement().inverse()
    shapes = []
    for obj in objects:
        shape = world_shape(obj)
        shape.Placement = inverse.multiply(shape.Placement)
        if prefix == "Starboard":
            shape.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
        shapes.append(shape)
    return shapes


def output_bearing_stack_check(doc, prefix, suffix, axial_stops=None):
    """Check each real split-housing bearing and all three cap fasteners."""
    shaft_suffix = "Negative" if prefix == "Port" else "Positive"
    names = [
        prefix + "OutputBearing" + suffix,
        prefix + "OutputShaft" + shaft_suffix,
        "PropulsionFixedFrame",
        prefix + "BearingCap",
    ]
    fastener_names = [
        prefix + "BearingCap" + side + kind
        for side in ("Negative", "Positive", "Input")
        for kind in ("Bolt", "Nut")
    ]
    objects = [doc.getObject(name) for name in names]
    fasteners = [doc.getObject(name) for name in fastener_names]
    if suffix not in ("Inboard", "Outboard") or any(
        obj is None for obj in objects + fasteners
    ):
        return {"passed": False, "error": "Missing split bearing capture component"}
    stops = (
        axial_stops if axial_stops is not None else carrier_axial_travel(doc, prefix)
    )
    if not stops.get("passed"):
        return {
            "passed": False,
            "error": "Unproven carrier/frame axial stops",
            "axial_stops": stops,
        }
    shapes = _positive_module_shapes(doc, prefix, objects)
    capture = split_bearing_stack_check(
        *shapes,
        centre_y=28.0 if suffix == "Inboard" else 41.0,
        negative_travel=stops["negative_mm" if prefix == "Port" else "positive_mm"],
        positive_travel=stops["positive_mm" if prefix == "Port" else "negative_mm"],
    )
    seating = split_cap_seating_check(shapes[2], shapes[3])
    clamp = Part.makeCompound([world_shape(objects[2]), world_shape(objects[3])])
    seated = [
        {
            "bolt": fastener_names[index],
            **clamp_fastener_check(
                clamp, world_shape(fasteners[index]), world_shape(fasteners[index + 1])
            ),
        }
        for index in (0, 2, 4)
    ]
    return {
        "bearing": names[0],
        **capture,
        "cap_hard_seating": seating,
        "cap_fasteners": seated,
        "passed": capture["passed"]
        and seating["passed"]
        and all(row["passed"] for row in seated),
    }


def input_bearing_support_check(doc, prefix):
    """Literal saved-solid proof of the new far input support and third joint."""
    names = [
        prefix + "InputBearing",
        prefix + "InputShaft",
        "PropulsionFixedFrame",
        prefix + "BearingCap",
    ]
    fastener_names = [prefix + "BearingCapInput" + kind for kind in ("Bolt", "Nut")]
    objects = [doc.getObject(name) for name in names + fastener_names]
    if prefix not in ("Port", "Starboard") or any(obj is None for obj in objects):
        return {"passed": False, "error": "Missing input bearing support"}
    shapes = _positive_module_shapes(doc, prefix, objects)
    bearing, shaft, frame, cap, bolt, nut = shapes
    capture = split_bearing_stack_check(
        bearing,
        shaft,
        frame,
        cap,
        centre_x=16.0,
        centre_y=33.0,
        negative_travel=0.0,
        positive_travel=0.0,
    )
    # Broad stock must carry the new bearing into the existing bed. The cap
    # floor is backed by the lower housing; clamp force is not bearing preload.
    web = Part.makeBox(5, 8, 8, App.Vector(8, 29, 42))
    missing_web = abs(web.cut(frame).Volume)
    lands = Part.makeCompound(
        [
            Part.makeBox(4.5, 7, 0.1, App.Vector(8.5, 29.5, 49.9)),
            Part.makeBox(6.5, 7, 0.1, App.Vector(19.5, 29.5, 49.9)),
        ]
    ).cut(Part.makeCylinder(1.11, 0.4, App.Vector(23, 33, 49.8)))
    # The nominal nut prism cuts into the underside, not the hard Z50 lands.
    missing_lower = abs(lands.cut(frame).Volume)
    upper_lands = translated_shape(lands, z=0.1).cut(
        Part.makeBox(3, 3, 2, App.Vector(6, 28, 49.8))
    )
    missing_upper = abs(upper_lands.cut(cap).Volume)
    clamp = clamp_fastener_check(Part.makeCompound([frame, cap]), bolt, nut)
    from gondola.cad import belongs_to_group

    fixed_parent = doc.getObject(prefix + "Assembly")
    fixed_bearing = (
        fixed_parent is not None
        and belongs_to_group(objects[0], fixed_parent)
        and not belongs_to_group(objects[0], doc.getObject(prefix + "InputDrive"))
    )
    return {
        "bearing": names[0],
        "shaft": names[1],
        "capture": capture,
        "fixed_native_parent": fixed_bearing,
        "missing_connecting_web_mm3": missing_web,
        "missing_lower_hard_land_mm3": missing_lower,
        "missing_cap_hard_land_mm3": missing_upper,
        "outer_cap_joint": clamp,
        "scope": "One external bearing supports the far side of each servo-driven gear. Literal round journal, complete outer-ring capture, short connecting web, hard lands and third M2 cap joint are required. No servo axial preload is intended; the shaft may slide through the bearing during service. Align received servo/horn/stub to the fitted bearing before final fastening and verify the whole +/-60 degree range. Nominal geometry cannot establish horn runout, shaft straightness, bearing load capacity or printed stiffness.",
        "passed": capture["passed"]
        and fixed_bearing
        and missing_web < TOL
        and missing_lower < TOL
        and missing_upper < TOL
        and clamp["passed"],
    }


def _servo_rear_body_allowance(doc, prefix):
    """Measure the rear case separately from its lower mounting ear."""
    from gondola.parts import servo_envelope

    from .relative_motion import _certify_pair, _part

    mount = doc.getObject(prefix + "ServoMount")
    group = doc.getObject("MainPropulsionModule")
    if mount is None or group is None:
        return {"passed": False, "error": "Missing servo or propulsion module"}
    canonical = mount.getGlobalPlacement().multiply(
        App.Placement(
            App.Vector(),
            App.Rotation(App.Vector(0, 0, 1), 180 if prefix == "Starboard" else 0),
        )
    )
    inverse = canonical.inverse()
    shapes = {}
    for obj in doc.Objects:
        if (
            belongs_to_group(obj, group)
            and obj.isDerivedFrom("Part::Feature")
            and getattr(obj, "Role", "") != "Clearance"
        ):
            shape = world_shape(obj)
            if shape.isNull() or not shape.isValid() or not shape.Solids:
                return {
                    "passed": False,
                    "error": "Invalid physical obstacle: " + obj.Name,
                }
            shape.Placement = inverse.multiply(shape.Placement)
            shapes[obj.Name] = shape
    if any(name not in shapes for name in (prefix + "Servo", "PropulsionFixedFrame")):
        return {"passed": False, "error": "Missing servo case or connecting plate"}
    rear = servo_envelope.case_rear_y()
    # Read a rear-case strip that does not contain the forward mounting ears.
    # The lower ear reaches four millimetres below the actual body.
    strip_width = servo_envelope.CASE_WIDTH + 2
    strip = Part.makeBox(
        strip_width, 1, 40, App.Vector(-strip_width / 2, rear + 0.5, -30)
    )
    body = shapes[prefix + "Servo"].common(strip)
    under = shapes["PropulsionFixedFrame"].common(
        Part.makeBox(
            servo_envelope.CASE_WIDTH,
            1,
            40,
            App.Vector(-servo_envelope.CASE_WIDTH / 2, rear + 0.5, -40),
        )
    )
    if not body.Solids:
        return {"passed": False, "error": "Missing rear body strip"}
    body_bounds = body.optimalBoundingBox(False, False)
    plate_top = under.optimalBoundingBox(False, False).ZMax if under.Solids else None
    gap = None if plate_top is None else body_bounds.ZMin - plate_top
    # The raised transverse beam no longer lies directly beneath the rear case.
    # Require the actual five-millimetre air reserve whether or not a lower
    # surface exists; absence of a plate is not a measured zero gap.
    lower_reserve = Part.makeBox(
        servo_envelope.CASE_WIDTH,
        1,
        5,
        App.Vector(-servo_envelope.CASE_WIDTH / 2, rear + 0.5, body_bounds.ZMin - 5),
    )
    lower_intrusion = intersection_volume(lower_reserve, shapes["PropulsionFixedFrame"])
    lane_end = rear - 0.1
    lane_start = lane_end - 1.8
    lane = Part.makeBox(
        body_bounds.XLength + 13.9,
        1.8,
        body_bounds.ZLength,
        App.Vector(body_bounds.XMin, lane_start, body_bounds.ZMin),
    )
    collisions = [
        {"part": name, "intersection_mm3": volume}
        for name, obstacle in shapes.items()
        if (volume := intersection_volume(lane, obstacle)) > TOL
    ]
    # Keep the complete rear lead allowance clear of both independently moving
    # input drives. Normalize each actual part to neutral without changing the
    # document, then certify every point in its bounded +/-60 degree motion.
    stationary = _part(lane, prefix + "RearLeadAllowance")
    moving_rows = []
    spec = drive_for_document(doc)
    for side in ("Port", "Starboard"):
        drive = doc.getObject(side + "InputDrive")
        if drive is None:
            return {"passed": False, "error": "Missing input drive: " + side}
        placed = drive.getGlobalPlacement()
        parent = drive.getParentGeoFeatureGroup().getGlobalPlacement()
        neutral = parent.multiply(App.Placement(drive.Placement.Base, App.Rotation()))
        to_neutral = inverse.multiply(neutral).multiply(placed.inverse())
        axis = inverse.multiply(neutral).Base
        for obj in doc.Objects:
            if obj.Name not in shapes or not belongs_to_group(obj, drive):
                continue
            shape = world_shape(obj)
            shape.Placement = to_neutral.multiply(shape.Placement)
            if obj.Name == side + "DriverGear":
                moving_rows.append(
                    {
                        "parts": [stationary["name"], obj.Name],
                        **driver_full_rotation_clearance_check(
                            shape,
                            lane,
                            inverse.multiply(neutral),
                            1 if side == "Port" else -1,
                            spec,
                        ),
                    }
                )
                continue
            moving_rows.append(
                _certify_pair(
                    stationary,
                    _part(
                        shape,
                        obj.Name,
                        axis=tuple(axis),
                        rate=-1 / spec.ratio,
                        prefix=side,
                    ),
                )
            )
    return {
        "coordinate_frame": "servo axis, positive Y toward the horn",
        "rear_body_bottom_z_mm": body_bounds.ZMin,
        "servo_with_ears_bottom_z_mm": shapes[prefix + "Servo"].BoundBox.ZMin,
        "rear_body_section_mm": [body_bounds.XLength, body_bounds.ZLength],
        "plate_top_below_rear_body_z_mm": plate_top,
        "rear_strip_open_below": plate_top is None,
        "five_mm_rear_body_reserve_intrusion_mm3": lower_intrusion,
        "rear_body_to_plate_gap_mm": gap,
        "minimum_rear_body_allowance_mm": 5.0,
        "rear_then_outward_planning_volume_mm": [
            body_bounds.XLength + 13.9,
            1.8,
            body_bounds.ZLength,
        ],
        "rear_departure_mm": 1.8,
        "outward_reach_mm": 13.9,
        "inward_planning_y_range_mm": [lane_start, lane_end],
        "checked_physical_objects": sorted(shapes),
        "planning_volume_collisions": collisions,
        "continuous_input_drive_clearance": moving_rows,
        "scope": "Saved rear case strip excludes the lower mounting ear. A1.8mm rear departure joins a13.9mm outwardX reserve behind the closed mounting wall, retaining the complete20mm case-height envelope. It stops0.1mm before the case rear face and never claims under-ear/nut access. Every physical input-drive part on both sides is checked through its complete bounded motion. Received lead exit position, diameter, connector and bend radius are unspecified; this rigid design allowance is not a factory cable route or installed harness qualification.",
        "passed": abs(body_bounds.ZMin - servo_envelope.CASE_BOTTOM_Z) < TOL
        and abs(body_bounds.ZLength - servo_envelope.CASE_LENGTH) < TOL
        and abs(body_bounds.XLength - servo_envelope.CASE_WIDTH) < TOL
        and (gap is None or gap >= 5.0 - TOL)
        and lower_intrusion < TOL
        and not collisions
        and bool(moving_rows)
        and all(row["passed"] for row in moving_rows),
    }


def servo_mount_check(doc, prefix):
    """Require both stock ears to seat on the integrated frame without collision."""
    from .servo_ear_nuts import servo_ear_nut_check

    frame = world_shape(doc.PropulsionFixedFrame)
    servo = world_shape(doc.getObject(prefix + "Servo"))
    frame_overlap = intersection_volume(frame, servo)
    mount = doc.getObject(prefix + "ServoMount")
    canonical = mount.getGlobalPlacement().multiply(
        App.Placement(
            App.Vector(),
            App.Rotation(App.Vector(0, 0, 1), 180 if prefix == "Starboard" else 0),
        )
    )
    local_frame = frame.copy()
    local_frame.Placement = canonical.inverse().multiply(local_frame.Placement)
    # Literal closed frame: both3mm side walls and complete ear bars.
    # The7.4x20.4 window clears the nominal7x20 case by0.2mm per face.
    required = Part.makeBox(13.4, 5, 30.7, App.Vector(-6.7, -2.5, -20.5))
    window = Part.makeBox(7.4, 7, 20.4, App.Vector(-3.7, -3.5, -15.2))
    required = required.cut(window)
    for z, opening in ((-17, 1), (7, -1)):
        bore = Part.makeCylinder(1.1, 7, App.Vector(0, -3.5, z), App.Vector(0, 1, 0))
        slot = Part.makeBox(
            2.2, 7, 2.2, App.Vector(-1.1, -3.5, z if opening > 0 else z - 2.2)
        )
        radius = 3.4 / math.sqrt(3)
        points = [
            App.Vector(
                radius * math.cos(i * math.pi / 3),
                radius * math.sin(i * math.pi / 3),
                0,
            )
            for i in range(6)
        ]
        pocket = Part.Face(Part.makePolygon(points + points[:1])).extrude(
            App.Vector(0, 0, 0.6)
        )
        pocket.Placement = App.Placement(
            App.Vector(0, -2.6, z),
            App.Rotation(App.Vector(0, 0, 1), App.Vector(0, 1, 0)),
        )
        required = required.cut(bore).cut(slot).cut(pocket)
    missing_stock = abs(required.cut(local_frame).Volume)
    module_frame = frame.copy()
    module_frame.Placement = (
        doc.MainPropulsionModule.getGlobalPlacement()
        .inverse()
        .multiply(frame.Placement)
    )
    connections = {
        "direct_servo_plinth": Part.makeBox(45.4, 21, 9.5, App.Vector(-22.7, -10.5, 20))
    }
    connection_losses = {
        name: abs(stock.cut(module_frame).Volume) for name, stock in connections.items()
    }
    case_window = Part.makeBox(7.4, 5, 20.4, App.Vector(-3.7, -2.5, -15.2))
    window_intrusion = intersection_volume(case_window, local_frame)
    between_frames = Part.makeBox(18.6, 21, 30.7, App.Vector(-9.3, -10.5, 29.5))
    central_intrusion = intersection_volume(between_frames, module_frame)
    cradle = {
        "coordinate_frame": "canonical servo axis",
        "complete_inboard_web_thickness_mm": 3.0,
        "complete_outboard_web_thickness_mm": 3.0,
        "closed_service_window_mm": [7.4, 20.4],
        "nominal_case_clearance_per_face_mm": 0.2,
        "missing_complete_cradle_stock_mm3": missing_stock,
        "outward_case_window_intrusion_mm3": window_intrusion,
        "missing_connection_stock_mm3": connection_losses,
        "unrequested_central_upper_stock_mm3": central_intrusion,
        "scope": "Independent closed rectangular wall stock and7.4x20.4 case window, excluding literal ear slots opening into the window and shallow nut seats. Both3mm walls seat directly on the complete45.4x21x9.5 central plinth atZ20..29.5; no narrow projecting feet carry these frames. The space between the frames stays empty above that plinth. Nominal case clearance is0.2mm per face; finish tight prints and never force case compression. Installed ear joints locate and clamp the servo. Closed stock does not qualify torsional stiffness or strength.",
        "passed": missing_stock < TOL
        and window_intrusion < TOL
        and central_intrusion < TOL
        and all(volume < TOL for volume in connection_losses.values()),
    }
    clamps = Part.makeCompound([frame, servo])
    rear_allowance = _servo_rear_body_allowance(doc, prefix)
    nut_capture = servo_ear_nut_check(doc, prefix)
    rows = []
    for suffix in ("Lower", "Upper"):
        name = prefix + "ServoEar" + suffix
        rows.append(
            {
                "bolt": name + "Bolt",
                **clamp_fastener_check(
                    clamps,
                    world_shape(doc.getObject(name + "Bolt")),
                    world_shape(doc.getObject(name + "Nut")),
                    thread_diameter=1.6,
                    nut_height=1.3,
                ),
            }
        )
    return {
        "pod": prefix,
        "servo_frame_intersection_mm3": frame_overlap,
        "rear_body_and_inward_lead_allowance": rear_allowance,
        "cradle_stock_and_case_window": cradle,
        "shallow_nut_capture": nut_capture,
        "cases": rows,
        "scope": "The two published X06 ears bear directly on the integrated frame using M1.6 fasteners. Nominal rigid contact is not proof of clamp torque, stiffness or actual case fit.",
        "passed": frame_overlap < TOL
        and cradle["passed"]
        and rear_allowance["passed"]
        and nut_capture["passed"]
        and all(row["passed"] for row in rows),
    }


def tilt_clearance_check(doc, module, prefix):
    """Move both coupled groups and inspect live shapes against the fixed parts."""
    pod = doc.getObject(prefix + "Pod")
    drive = doc.getObject(prefix + "InputDrive")
    objects = module["printed"] + module["hardware"] + module["references"]
    moving = [
        obj
        for obj in objects
        if belongs_to_group(obj, pod) or belongs_to_group(obj, drive)
    ]
    output_moving = [obj for obj in moving if belongs_to_group(obj, pod)]
    input_moving = [obj for obj in moving if belongs_to_group(obj, drive)]
    fixed = [obj for obj in objects if obj not in moving]
    horn = doc.getObject(prefix + "ServoHorn")
    servo = doc.getObject(prefix + "Servo")
    mount = doc.getObject(prefix + "ServoMount")
    if (
        horn not in input_moving
        or servo not in fixed
        or mount is None
        or not belongs_to_group(servo, mount)
    ):
        return {
            "pod": prefix,
            "poses": [],
            "error": "Horn must move with its input drive and servo must remain in its fixed mount",
            "passed": False,
        }
    original_tilt = float(pod.Tilt)
    rows = []
    try:
        for index in range(49):
            angle = -180 + index * 7.5
            pod.Tilt = angle
            doc.recompute()
            fixed_shapes = {obj.Name: world_shape(obj) for obj in fixed}
            moving_shapes = {obj.Name: world_shape(obj) for obj in moving}
            collisions = []
            spline_contacts = []
            minimum_z = float("inf")
            for obj in moving:
                shape = moving_shapes[obj.Name]
                minimum_z = min(minimum_z, shape.optimalBoundingBox(False, False).ZMin)
                for name, obstacle in fixed_shapes.items():
                    volume = intersection_volume(shape, obstacle)
                    if obj.Name == prefix + "ServoHorn" and name == prefix + "Servo":
                        frame = drive.getGlobalPlacement()
                        contact = horn_spline_contact(
                            shape,
                            obstacle,
                            frame.Base,
                            frame.Rotation.multVec(App.Vector(0, 1, 0)),
                        )
                        spline_contacts.append(
                            {"moving": obj.Name, "fixed": name, **contact}
                        )
                        if contact["passed"]:
                            continue
                    if volume > TOL:
                        collisions.append(
                            {
                                "moving": obj.Name,
                                "fixed": name,
                                "intersection_mm3": volume,
                            }
                        )
            for output_object in output_moving:
                for input_object in input_moving:
                    volume = intersection_volume(
                        moving_shapes[output_object.Name],
                        moving_shapes[input_object.Name],
                    )
                    if volume > TOL:
                        collisions.append(
                            {
                                "moving": output_object.Name,
                                "other_moving": input_object.Name,
                                "intersection_mm3": volume,
                            }
                        )
            rows.append(
                {
                    "output_angle_deg": angle,
                    "minimum_z_mm": minimum_z,
                    "collisions": collisions,
                    "spline_contacts": spline_contacts,
                    "passed": not collisions
                    and minimum_z >= -TOL
                    and all(contact["passed"] for contact in spline_contacts),
                }
            )
    finally:
        pod.Tilt = original_tilt
        doc.recompute()
    return {
        "pod": prefix,
        "moving_objects": [obj.Name for obj in moving],
        "fixed_objects": [obj.Name for obj in fixed],
        "relative_motion_pairs_checked_per_pose": len(output_moving)
        * len(input_moving),
        "poses": rows,
        "scope": "49 sampled coupled-output/input positions at the fixed nominal center distance, including both bounded rotation endpoints. Checks live fixed obstacles and every output-pod/input-drive pair, including gear teeth; no gear-pair exclusion. Same-side OEM horn contact is permitted only inside the uniquely sourced servo spline cylinder measured at that pose; case and ear overlap remains forbidden. Not a continuous rigid-body or connected-wire sweep proof or a qualification of physical spline fit.",
        "passed": bool(moving) and all(row["passed"] for row in rows),
    }


def input_drive_service_check(doc, module, prefix, *, module_release=None):
    """Check the stock-horn servo unit's service from the integrated frame.

    Reuse module-removal evidence only within the same unchanged audit invocation.
    """
    from .horn_coupling import assembled_servo_service_check

    return assembled_servo_service_check(
        doc, module, prefix, module_release=module_release
    )


def servo_case_service_check(
    doc, module, prefix, *, prior_service=None, module_release=None
):
    """Reuse the stock-horn unit's checked withdrawal, including the servo case.

    Reuse prerequisite evidence only during one unchanged audit invocation.
    """
    if prior_service is None:
        prior_service = input_drive_service_check(
            doc, module, prefix, module_release=module_release
        )
    return {
        **prior_service,
        "required_prior_check": "input_drive_service",
        "prior_input_drive_service_passed": prior_service["passed"],
    }


def frame_rail_bore_filled(frame):
    """Fill both round side bores outside the fitted rail channel for exact sweeps."""
    additions = []
    for site in rail.attachment_sites(x_offset=14, shared_drive=True):
        for start_y in (-3.25, 1.25):
            plug = Part.makeCylinder(
                1.7, 2.0, App.Vector(0, start_y, 6), App.Vector(0, 1, 0)
            )
            additions.append(rail.attachment_site_shape(plug, site))
    return frame.fuse(additions).removeSplitter()


def vertical_frame_release_check(frame, rail_shape=None):
    """Lift the complete frame after extracting only its rail screw and nut."""
    from gondola.parts import servo_bridge

    rail_shape = (
        translated_shape(rail.rail_shape(), x=14) if rail_shape is None else rail_shape
    )
    bounds = frame.BoundBox
    split_z = servo_bridge.CONNECTOR_PLATE_BOTTOM_Z
    region = Part.makeBox(
        bounds.XLength + 2,
        bounds.YLength + 2,
        split_z - bounds.ZMin + 1,
        App.Vector(bounds.XMin - 1, bounds.YMin - 1, bounds.ZMin - 1),
    )
    conservative = frame_rail_bore_filled(frame)
    lower = conservative.common(region)
    upper = conservative.cut(region)
    from .rail_access import _mount_service_regions

    sections = [
        (label, part)
        for label, part in _mount_service_regions("PropulsionFixedFrame", frame, 14)
        if label != "PropulsionFixedFrameUpper"
    ]
    checked = contained_region_paths(
        lower, sections, [(0, 0, 0), (0, 0, 30)], {"Rail": rail_shape}
    )
    path = {
        "regions": checked["regions"],
        "lower_frame_outside_envelope_mm3": checked["uncovered_volume_mm3"],
        "passed": checked["passed"],
    }
    upper_gap = upper.BoundBox.ZMin - rail_shape.BoundBox.ZMax
    missing = abs(frame.cut(conservative).Volume)
    added = abs(conservative.cut(frame).Volume)
    plug_volume = 4 * math.pi * 1.7**2 * 2.0
    return {
        "lower_frame_path": path,
        "upper_geometry_initial_z_gap_mm": upper_gap,
        "original_shape_missing_from_envelope_mm3": missing,
        "side_bore_filled_volume_mm3": added,
        "maximum_side_bore_plug_volume_mm3": plug_volume,
        "scope": "Fill only the four side screw bores through the2mm bearing floors, then split atZ12.5. Sweep the two standard U-shoe stocks with their recesses conservatively filled and rail channels open. Complete lower-shape containment is required. Upper stock starts above the rail and moves upward. This local check does not certify adjacent equipment or a bent bonded rail.",
        "passed": path["passed"]
        and upper_gap > TOL
        and missing < TOL
        and added <= plug_volume + TOL,
    }


def rail_mount_clearance_check(doc, module):
    """Audit both shared rail pairs with the complete populated mechanism retained."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"missing_parts": missing, "passed": False}
    sites = rail.attachment_sites(x_offset=14, shared_drive=True)
    expected = {}
    for site in sites:
        for suffix, shape in (
            ("RailMountScrew", rail.attachment_screw_shape(10, head_face_y=-3.25)),
            ("RailMountNut", rail.attachment_nut_shape(shared_drive=True)),
        ):
            expected[module["group"].Name + site["prefix"] + suffix] = (
                rail.attachment_site_shape(shape, site)
            )
    present = sorted(set(expected) & shapes.keys())
    complete = not present or set(present) == set(expected)
    for name, shape in expected.items():
        shapes.setdefault(name, shape)
    shapes["LocalRailReference"] = translated_shape(rail.rail_shape(), x=14)
    rows = [
        _rail_site_clearance_check(doc, module, site, shapes, present) for site in sites
    ]
    return {
        "sites": rows,
        "installed_rail_fasteners_present": present,
        "expected_rail_fasteners": sorted(expected),
        "complete_saved_fastener_set": complete,
        "integrated_frame_rail_clamp": True,
        "clamp_spacing_mm": 28.0,
        "removed_before_access": [],
        "scope": "Both opposed pairs are checked with the other pair and the entire mechanism retained. Local rigid clearance only; fitted curvature, simultaneous seating, preload and loaded stiffness require physical validation.",
        "passed": complete and all(row["passed"] for row in rows),
    }


def _rail_site_clearance_check(doc, module, site, shapes, present_fasteners):
    """Service the side M3 joint with the entire servo/gear module installed."""
    from gondola.print_export import geometry_comparison

    from .rail_access import nut_capture_check, side_driver_clearance
    from .rail_mount import paired_spine_support_check

    # Put the selected site into the canonical +X / negative-head-Y frame.
    shapes = {
        name: (servo_bridge.opposite(shape) if site["side"] < 0 else shape.copy())
        for name, shape in shapes.items()
    }
    x, z = 14.0, 6.0
    screw_name, nut_name = (
        module["group"].Name + site["prefix"] + suffix
        for suffix in ("RailMountScrew", "RailMountNut")
    )
    screw, nut = shapes[screw_name], shapes[nut_name]
    expected_screw = translated_shape(
        rail.attachment_screw_shape(10, head_face_y=-3.25), x=x
    )
    hardware_geometry = []
    for name, expected, sku in (
        (screw_name, expected_screw, "M3X10_BUTTON_HEAD"),
        (
            nut_name,
            translated_shape(rail.attachment_nut_shape(shared_drive=True), x=x),
            "M3_HEX_NUT",
        ),
    ):
        comparison = geometry_comparison(shapes[name], expected)
        actual = doc.getObject(name)
        metadata_ok = name not in present_fasteners or (
            actual is not None
            and actual.HardwareSKU == sku
            and actual.getParentGeoFeatureGroup() == module["group"]
        )
        hardware_geometry.append(
            {
                "object": name,
                "comparison": comparison,
                "installed_metadata_matches": metadata_ok,
                "passed": metadata_ok
                and all(
                    comparison[key] < TOL
                    for key in (
                        "difference_mm3",
                        "bounds_difference_mm",
                        "volume_difference_mm3",
                    )
                ),
            }
        )
    crop = Part.makeBox(16, 10.5, 12.5, App.Vector(x - 8, -5.25, 0))
    contact = attachment_check(
        translated_shape(shapes["LocalRailReference"], x=-x),
        translated_shape(shapes["PropulsionFixedFrame"].common(crop), x=-x),
        contact_length=44,
        shared_drive=True,
        screw_length=10,
        head_face_y=-3.25,
        nut_bearing_y=3.25,
        nut_outer_y=5.25,
    )
    paired_support = paired_spine_support_check(
        shapes["LocalRailReference"], shapes["PropulsionFixedFrame"]
    )
    screw_obstacles = retained_obstacles(shapes, {screw_name})
    withdrawal = continuous_path(screw, [(0, 0, 0), (0, -25, 0)], screw_obstacles)
    # Remove the screw first; the unthreaded nut can move outward then sideways.
    nut_obstacles = retained_obstacles(shapes, {screw_name, nut_name})
    nut_path = continuous_path(nut, [(0, 0, 0), (0, 4, 0), (35, 4, 0)], nut_obstacles)
    driver = side_driver_clearance(screw, screw_obstacles)
    stem_hits = {
        name: max(
            segment["intersection_mm3"].get(name, 0) for segment in driver["segments"]
        )
        for name in screw_obstacles
    }
    capture = nut_capture_check(x, nut, shapes["PropulsionFixedFrame"], shared=True)
    lift = vertical_frame_release_check(
        shapes["PropulsionFixedFrame"], shapes["LocalRailReference"]
    )
    overlaps = {
        "screw_frame": intersection_volume(screw, shapes["PropulsionFixedFrame"]),
        "nut_frame": intersection_volume(nut, shapes["PropulsionFixedFrame"]),
        "rail_frame": intersection_volume(
            shapes["LocalRailReference"], shapes["PropulsionFixedFrame"]
        ),
    }
    return {
        "installed_rail_fasteners_present": present_fasteners,
        "local_reference_fasteners_added": sorted(
            {screw_name, nut_name} - set(present_fasteners)
        ),
        "site": site,
        "removed_before_access": [],
        "retained_during_access": sorted(shapes),
        "side_bolt_axis_mm": [x, z],
        "integrated_frame_rail_clamp": True,
        "shared_grip_contact_check": contact,
        "paired_spine_support": paired_support,
        "hardware_geometry": hardware_geometry,
        "screw_length_mm": servo_bridge.SHARED_SCREW_LENGTH,
        "driver_access": driver,
        "centred_load_zone_x_range_mm": [x - 5, x + 5],
        "physical_shoe_pair_x_range_mm": [-22, 22],
        "bolt_withdrawal": withdrawal,
        "nut_removal_after_bolt": nut_path,
        "driver_clearance_overlap_mm3": stem_hits,
        "nut_window_anti_rotation": capture,
        "frame_vertical_removal": lift,
        "seated_intersections_mm3": overlaps,
        "scope": "All local servo, gear, bearing and rotor hardware stays installed. The recessed M3x10 rail screw and nut are serviced; support the integrated propulsion assembly throughout release. The Ø4 driver stem is an external access envelope; the downward-open hex pocket with vertical flats limits nut rotation and retains a 2 mm nominal load-bearing floor. Actual socket engagement, nut insertion, finger access, harnesses, clamp force and bending remain bench checks. Complete populated-assembly service is audited separately.",
        "passed": contact["passed"]
        and paired_support["passed"]
        and all(row["passed"] for row in hardware_geometry)
        and withdrawal["passed"]
        and driver["passed"]
        and nut_path["passed"]
        and capture["passed"]
        and lift["passed"]
        and all(value < TOL for value in stem_hits.values())
        and all(value < TOL for value in overlaps.values()),
    }


def bearing_post_roots_check(doc):
    """Require two short housing webs with roots and the raised shared beam."""
    obj = doc.getObject("PropulsionFixedFrame")
    if obj is None:
        return [{"passed": False, "error": "Missing integrated output support"}]
    shape = obj.Shape.copy()
    shape.Placement = App.Placement()
    beam = Part.makeBox(18, 88, 5, App.Vector(-9, -44, 24.5))
    missing_beam = abs(beam.cut(shape).Volume)
    rows = []
    for sign in (-1, 1):
        y = 25 if sign > 0 else -44
        post = Part.makeBox(18, 19, 12.5, App.Vector(-9, y, 29.5))
        root = Part.makeBox(18, 1.5, 1.5, App.Vector(-9, 23.5, 29.5)).cut(
            Part.makeCylinder(1.5, 18, App.Vector(-9, 23.5, 31), App.Vector(1, 0, 0))
        )
        if sign < 0:
            root = root.mirror(App.Vector(), App.Vector(0, 1, 0))
        bed_y = 25 if sign > 0 else -44
        bed = Part.makeBox(18, 19, 3, App.Vector(-9, bed_y, 42))
        for x, y_bolt in ((-5.5, 34.5), (6.25, 39.5)):
            bed = bed.cut(
                Part.makeCylinder(1.1, 3, App.Vector(sign * x, sign * y_bolt, 42))
            )
        missing = abs(post.cut(shape).Volume)
        missing_blends = abs(root.cut(shape).Volume)
        missing_bed = abs(bed.cut(shape).Volume)
        rows.append(
            {
                "side": sign,
                "post_centres_y_mm": [sign * 34.5],
                "root_section_mm": [18, 19],
                "root_height_range_mm": [29.5, 42],
                "missing_root_material_mm3": missing,
                "root_blend_radius_mm": 1.5,
                "missing_root_blend_mm3": missing_blends,
                "missing_housing_bed_mm3": missing_bed,
                "shared_beam_z_range_mm": [24.5, 29.5],
                "missing_shared_beam_mm3": missing_beam,
                "scope": "One full18x19 web per side joins the88mm shared beam atZ29.5 to the equally wide paired-bearing bed atZ42. An independent quarter-circle stock witness proves the R1.5 lower inner-Y transition across the full18mm width. The18x19 bed retains3mm continuous stock below its nut slots, apart from its two explicit vertical screw bores. These are geometry and material-continuity witnesses, not load or stiffness qualification.",
                "passed": max(missing, missing_blends, missing_bed, missing_beam) < TOL,
            }
        )
    return rows


def _record_drive_motion_checks(report, doc, module, prefix):
    """Keep native motion, meshing and coupled service evidence together."""
    report["drive_motion"].append(drive_motion_check(doc, prefix))
    report["fixed_servo_datum"].append(fixed_servo_datum_check(doc, prefix))
    report["servo_mounts"].append(servo_mount_check(doc, prefix))
    report["direct_adapter_fit"].append(direct_adapter_fit_check(doc, prefix))
    report["input_shaft_retention"].append(input_shaft_retention_check(doc, prefix))
    report["carrier_shaft_retention"].append(carrier_shaft_retention_check(doc, prefix))
    report["gear_rotation"].append(gear_rotation_check(doc, prefix))
    carrier_clearance = carrier_metal_clearance_check(doc, prefix)
    report["carrier_metal_clearance"].append(carrier_clearance)
    axial_stops = carrier_clearance.get("axial_travel", {"passed": False})
    report["gear_mesh_alignment"].append(
        gear_engagement_check(doc, prefix, axial_stops)
    )
    report["tilt_clearance"].append(tilt_clearance_check(doc, module, prefix))
    report["replacement_rotor_space"].append(
        replacement_rotor_space_check(doc, module, prefix)
    )
    input_service = input_drive_service_check(
        doc, module, prefix, module_release=report["servo_service_preparation"][0]
    )
    report["input_drive_service"].append(input_service)
    report["servo_case_service"].append(
        servo_case_service_check(doc, module, prefix, prior_service=input_service)
    )


def _record_output_stub_checks(report, prefix, pod, physical, frame):
    """Check each shaft's motor separation and outward whole-rotor route."""
    shaft_name = output_shaft_name(prefix)
    sign = 1 if prefix == "Port" else -1
    report["output_stub_clearance"].append(
        {
            "shaft": shaft_name,
            **output_stub_check(
                physical[shaft_name],
                physical[prefix + "Motor"],
                pod.getGlobalPlacement().Base.y,
            ),
        }
    )
    moving = {
        name for name in physical if belongs_to_group(pod.Document.getObject(name), pod)
    }
    report["shaft_service"].append(
        {
            "shaft": shaft_name,
            "moving_with_rotor": sorted(moving - {prefix + "OutputGear"}),
            "excluded_physical_parts": sorted(moving),
            "scope": "Remove the output gear, retain the D-shaft jack setting, support the rotor and withdraw shaft/carrier together 60 mm outward through both fixed bearings. The opposite shaft remains installed. Shaft removal from the carrier is a subsequent bench operation.",
            **continuous_path(
                physical[shaft_name],
                [(0, 0, 0), (0, sign * 60, 0)],
                retained_obstacles(physical, moving),
            ),
        }
    )


def output_carrier_service_check(doc, module, prefix):
    """Withdraw rotor and clamped shaft together through both inboard bearings."""
    shapes, missing = module_service_shapes(doc, module)
    sign = 1 if prefix == "Port" else -1
    gear, shaft = prefix + "OutputGear", output_shaft_name(prefix)
    pod = doc.getObject(prefix + "Pod")
    if missing or pod is None or any(name not in shapes for name in (gear, shaft)):
        return {"pod": prefix, "missing_parts": missing, "passed": False}
    gear_path = continuous_path(
        shapes[gear],
        [(0, 0, 0), (0, -sign * 11, 0), (0, -sign * 11, 20), (30, -sign * 11, 20)],
        retained_obstacles(shapes, {gear}),
    )
    moving = {name for name in shapes if belongs_to_group(doc.getObject(name), pod)} - {
        gear
    }
    fixed = retained_obstacles(shapes, moving | {gear})
    waypoints = [(0, 0, 0), (0, sign * 60, 0)]
    paths = [
        {"part": name, **continuous_path(shapes[name], waypoints, fixed)}
        for name in sorted(moving)
    ]
    removed = moving | {gear}
    return {
        "pod": prefix,
        "moving_parts": sorted(moving),
        "removed_parts": sorted(removed),
        "removed_output_gear": gear,
        "output_gear_removal": gear_path,
        "carrier_removal": paths,
        "retained_parts": sorted(set(shapes) - removed),
        "shaft_moves_with_carrier": shaft,
        "scope": "Unpowered bench sequence with leads freed and rotor supported: remove the output gear inward, keep the D-shaft jack clamp assembled, then withdraw the complete motor/guard/carrier, shaft and jack fasteners 60 mm outward along Y. Both inboard bearings and the split cap remain installed. The opposite shaft remains installed. Any later shaft/carrier separation occurs on the bench after loosening the jack. Reverse for assembly and qualify physical fits, clamp grip and gear retention separately.",
        "passed": gear_path["passed"]
        and shaft in moving
        and bool(moving)
        and all(row["passed"] for row in paths),
    }


def replacement_rotor_space_check(doc, module, prefix):
    """Reserve replacement bulk through all tilt angles and both service paths.

    This does not fit a 50 mm propeller to the current guard. The replacement
    bulk is constrained to an independent radius34 / axial±29 cylinder; its
    separate shaft and clamp interfaces retain the currently checked stops.
    """
    from .servo_module import (
        driver_gear_service_waypoints,
        input_jack_backoff_vector,
        input_shaft_service_waypoints,
        servo_unit_service_waypoints,
    )

    shapes, missing = module_service_shapes(doc, module)
    pod = doc.getObject(prefix + "Pod")
    drive = doc.getObject("ServoDriveModule")
    if missing or pod is None or drive is None or "PropulsionFixedFrame" not in shapes:
        return {"pod": prefix, "missing_parts": missing, "passed": False}
    travel = carrier_axial_travel(doc, prefix)
    if not travel["passed"]:
        return {"pod": prefix, "axial_travel": travel, "passed": False}
    origin = (
        module["group"]
        .getGlobalPlacement()
        .inverse()
        .multVec(pod.getGlobalPlacement().Base)
    )
    nominal = Part.makeCylinder(
        34, 58, App.Vector(origin.x, origin.y - 29, origin.z), App.Vector(0, 1, 0)
    )
    moving = Part.makeCylinder(
        34,
        58 + travel["negative_mm"] + travel["positive_mm"],
        App.Vector(origin.x, origin.y - 29 - travel["negative_mm"], origin.z),
        App.Vector(0, 1, 0),
    )
    # Own rotor/clamps/shafts are the replacement interfaces, not obstacles.
    # The output gear remains an obstacle; the ordinary service check also
    # verifies removing that gear before the rotor or servo module is serviced.
    excluded = {
        name
        for name in shapes
        if belongs_to_group(doc.getObject(name), pod) and name != prefix + "OutputGear"
    }
    obstacles = retained_obstacles(shapes, excluded)
    distances = {
        name: moving.distToShape(shape)[0] for name, shape in obstacles.items()
    }
    gaps = []
    for stop in travel["stops"]:
        nominal_gap = abs(stop["frame_stop_y_mm"]) - 29
        remaining = nominal_gap - stop["travel_mm"]
        gaps.append(
            {
                "direction": stop["direction"],
                "nominal_post_face_gap_mm": nominal_gap,
                "gap_at_axial_stop_mm": remaining,
                "passed": remaining >= 1.25 - TOL,
            }
        )
    sign = 1 if prefix == "Port" else -1
    rotor_service = continuous_path(moving, [(0, 0, 0), (0, sign * 60, 0)], obstacles)
    servo_paths = []
    future_obstacle = {
        "removed_replacement_rotor_bulk": translated_shape(moving, y=sign * 60)
    }
    configuration = drive_for_document(doc)
    ear_paths = {}
    for name in sorted(servo_bench_members(doc, shapes)):
        side = "Port" if name.startswith("Port") else "Starboard"
        waypoints = servo_unit_service_waypoints(side)
        stage = "servo_horn_adapter_removal"
        if name == side + "InputShaft":
            waypoints = input_shaft_service_waypoints(side)
            stage = "input_shaft_removal"
        if name == side + "InputShaftClampBolt":
            backoff = input_jack_backoff_vector(side)
            waypoints = [(0, 0, 0)] + [
                tuple(a + b for a, b in zip(point, backoff)) for point in waypoints
            ]
            stage = "jack_backoff_and_servo_removal"
        if name == side + "DriverGear":
            waypoints = driver_gear_service_waypoints(side)
            stage = "loose_driver_removal"
            # Use the same containment-checked hub/tooth sweep as the installed
            # service proof; avoid tessellating hundreds of axial tooth prisms.
            segments = [
                driver_service_segment_check(
                    shapes[name],
                    start,
                    end,
                    future_obstacle,
                    configuration,
                    1 if side == "Port" else -1,
                )
                for start, end in zip(waypoints, waypoints[1:])
            ]
            path = {
                "obstacles": list(future_obstacle),
                "segments": segments,
                "passed": all(row["passed"] for row in segments),
            }
        elif "ServoEar" in name:
            pair = name.removesuffix("Bolt").removesuffix("Nut")
            if pair not in ear_paths:
                ear_paths[pair] = fastener_service_check(
                    shapes[pair + "Bolt"],
                    shapes[pair + "Nut"],
                    future_obstacle,
                    thread_diameter=1.6,
                    guided_nut=True,
                    capture_depth_mm=0.5,
                )
            check = ear_paths[pair]
            path = check[
                "bolt_axial_withdrawal"
                if name.endswith("Bolt")
                else "nut_axial_removal"
            ]
            path = {**path, "passed": path["passed"] and check["passed"]}
            waypoints = [path["segments"][0]["start_mm"]] + [
                row["end_mm"] for row in path["segments"]
            ]
            stage = "ear_fastener_release"
        else:
            path = continuous_path(shapes[name], waypoints, future_obstacle)
        servo_paths.append(
            {"part": name, "service_stage": stage, "waypoints_mm": waypoints, **path}
        )
    grip_tools = []
    for side, grip_sign in (("Port", 1), ("Starboard", -1)):
        jaws = Part.makeCompound(
            [
                Part.makeBox(15, 3.8, height, App.Vector(14.5, 37.7, z))
                for z, height in ((47, 1.5), (51.5, 1.5))
            ]
        )
        if grip_sign < 0:
            jaws.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
        points = [(grip_sign * 60, 0, 0), *input_shaft_service_waypoints(side)]
        grip_tools.append(
            {
                "pod": side,
                "waypoints_mm": points,
                "scope": "Literal side-entry jaw envelope from the checked shaft-first service route. Both jaws are tangent to the round distal journal; actual hand tools and grip are unqualified.",
                **continuous_path(jaws, points, future_obstacle),
            }
        )
    nominal_frame_gap = nominal.distToShape(shapes["PropulsionFixedFrame"])[0]
    return {
        "pod": prefix,
        "future_propeller_reference_diameter_mm": 50,
        "bulk_half_width_mm": 29,
        "full_rotation_radius_mm": 34,
        "axial_travel": travel,
        "post_face_gaps": gaps,
        "nominal_frame_gap_mm": nominal_frame_gap,
        "all_angle_gaps_with_axial_travel_mm": distances,
        "excluded_replacement_interface_parts": sorted(excluded),
        "rotor_bulk_removal": rotor_service,
        "servo_module_removal_past_future_bulk": servo_paths,
        "input_service_requires_future_rotor_removal": True,
        "input_grip_tools_past_future_bulk": grip_tools,
        "scope": "Continuous enclosing cylinder for a future replacement rotor bulk, including measured current axial stops. The inboard housing, every retained physical propulsion part, outward rotor Y60 and separate input-service stages are checked. The reserved generic future rotor bulk must first be removed along its verified outwardY60 route before input service. Each input shaft then moves32mm outward inY and60mm outward inX; its released driver moves60mm outward inX. After ear hardware release, the remaining servo/horn/adapter moves13mm outward inY then60mm outward inX. The future bulk is58mm wide; the separate shaft and root thrust interfaces lie outside this bulk. The present40mm guard and return arm do not accept a50mm propeller. Replacement shaft/clamp interfaces, assembly strength, future motor/propeller hardware and wiring still require design and tests; this is a space reservation only.",
        "passed": all(row["passed"] for row in gaps)
        and bool(distances)
        and min(distances.values()) >= 1.25 - TOL
        and nominal_frame_gap >= 1.75 - TOL
        and rotor_service["passed"]
        and bool(servo_paths)
        and all(row["passed"] for row in servo_paths + grip_tools),
    }


def _record_bearing_checks(report, doc, module, prefix, physical):
    """Release the hard-seated cap, then lift each bearing from its open seat."""
    carrier_service = output_carrier_service_check(doc, module, prefix)
    report["output_carrier_service"].append(carrier_service)
    shapes, missing = module_service_shapes(doc, module)
    if prefix == "Starboard":
        for shape in shapes.values():
            shape.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
    staged = retained_obstacles(shapes, set(carrier_service.get("removed_parts", [])))
    cap_name = prefix + "BearingCap"
    pairs = [
        (cap_name + side + "Bolt", cap_name + side + "Nut")
        for side in ("Negative", "Positive", "Input")
    ]
    required = [cap_name, *[name for pair in pairs for name in pair]]
    missing = sorted(set(missing) | (set(required) - set(staged)))
    release = []
    if not missing:
        for bolt, nut in pairs:
            path = fastener_service_check(
                staged[bolt],
                staged[nut],
                retained_obstacles(staged, {bolt, nut}),
                side_entry_nut=True,
                capture_depth_mm=1.8,
                nut_lateral_direction=(
                    -1 if "Negative" in bolt else 1,
                    0,
                    0,
                ),
            )
            release.append({"bolt": bolt, "nut": nut, **path})
            staged.pop(bolt)
            staged.pop(nut)
        cap_path = split_housing_vertical_service(
            staged[cap_name], retained_obstacles(staged, {cap_name})
        )
        staged.pop(cap_name)
    else:
        cap_path = {"passed": False, "missing_parts": missing}
    for suffix, centre in (("Inboard", 28.0), ("Outboard", 41.0)):
        name = prefix + "OutputBearing" + suffix
        stack = output_bearing_stack_check(doc, prefix, suffix)
        report["bearing_stacks"].append(stack)
        path = (
            split_housing_vertical_service(
                staged[name],
                retained_obstacles(staged, {name}),
                bearing_centre_y=centre,
            )
            if name in staged
            else {"passed": False, "error": "Missing bearing"}
        )
        report["bearing_service"].append(
            {
                "bearing": name,
                "cap": cap_name,
                "required_prior_check": "output_carrier_service",
                "fastener_release": release,
                "cap_removal": cap_path,
                "bearing_removal": path,
                "missing_parts": missing,
                "scope": "After the checked rotor/shaft/output-gear removal, hold each side nut and withdraw its cap bolt upward; remove the unthreaded nut through its side opening. Lift the cap Z30, then lift each bearing Z30 from the lower semicircular seat. All other physical module parts remain obstacles. No forced insertion or bearing preload is modeled.",
                "passed": carrier_service["passed"]
                and stack["passed"]
                and not missing
                and len(release) == 3
                and all(row["passed"] for row in release)
                and cap_path["passed"]
                and path["passed"],
            }
        )
        staged.pop(name, None)

    input_rows = [row for row in report["input_drive_service"] if row["pod"] == prefix]
    input_service = input_rows[0] if len(input_rows) == 1 else {"passed": False}
    name = prefix + "InputBearing"
    remaining = retained_obstacles(staged, set(input_service.get("removed_parts", [])))
    path = (
        split_housing_vertical_service(
            remaining[name],
            retained_obstacles(remaining, {name}),
            bearing_centre_x=16,
            bearing_centre_y=33,
        )
        if name in remaining
        else {"passed": False, "error": "Missing input bearing"}
    )
    report["input_bearing_service"].append(
        {
            "bearing": name,
            "required_prior_checks": ["input_drive_service", "output_carrier_service"],
            "input_removal_passed": input_service["passed"],
            "cap_removal": cap_path,
            "bearing_removal": path,
            "fastener_release": release,
            "scope": "For bearing replacement remove the input unit using the checked parked-rotor sequence, return the unmeshed rotor to neutral along the certified reverse parking arc, then remove the output rotor/shaft. Release all three cap pairs and lift the cap, output bearings, then input bearing+Z30. No shaft is forced through a bearing shoulder; all unremoved parts remain obstacles. This is a maintenance route, not an assembly-fit guarantee.",
            "passed": input_service["passed"]
            and carrier_service["passed"]
            and not missing
            and len(release) == 3
            and all(row["passed"] for row in release)
            and cap_path["passed"]
            and path["passed"],
        }
    )


def _record_drive_service_checks(report, doc, prefix, sign, physical):
    """Keep output unmeshing and shaft-first input service explicitly ordered."""
    gear = prefix + "OutputGear"
    report["gear_service"].append(
        {
            "gear": gear,
            "required_prior_check": None,
            "scope": "Release the purchased set screw, move the small output gear11mm inward to clear its shaft, lift20mm, then move30mm in+X. The opposite gear and shaft stay installed.",
            **continuous_path(
                physical[gear],
                [
                    (0, 0, 0),
                    (0, -sign * 11, 0),
                    (0, -sign * 11, 20),
                    (30, -sign * 11, 20),
                ],
                retained_obstacles(physical, {gear}),
            ),
        }
    )
    prior = [row for row in report["input_drive_service"] if row["pod"] == prefix]
    service = prior[0] if len(prior) == 1 else {"passed": False}
    driver = service.get("driver_gear_removal", {"passed": False})
    shaft = service.get("input_stub_removal", {"passed": False})
    report["gear_service"].append(
        {
            "gear": prefix + "DriverGear",
            "required_prior_check": "input_drive_service",
            "required_mechanical_stage": "input_stub_removal",
            "prior_input_shaft_removal_passed": shaft["passed"],
            "scope": "After output-gear unmeshing, loosen the input jack and bought driver set screw, support the driver and park the unmeshed rotor90deg, withdraw its shaft32mm axially then60mm outward inX. Only then remove the loose driver60mm outward inX. The servo/horn/adapter, fixed frame, bearings and rotors remain installed for this stage. Actual set-screw and handling access remain physical checks.",
            **driver,
            "passed": service["passed"] and shaft["passed"] and driver["passed"],
        }
    )
    for suffix in ("Motor", "PropellerDisk"):
        name = prefix + suffix
        excluded = {name, prefix + "Shaft"}
        moving = physical[name]
        if suffix == "Motor":
            moving = Part.makeCompound([moving, physical[prefix + "Shaft"]])
            excluded.add(prefix + "PropellerDisk")
        report["motor_and_prop_insertion"].append(
            {
                "part": name,
                "excluded_physical_parts": sorted(excluded),
                "scope": "Bare motor/shaft withdraw together with propeller removed; propeller disk proxy excludes its shaft because its hub bore is unmodeled. OEM motor fastening remains unresolved.",
                **continuous_path(
                    moving,
                    [(0, 0, 0), (30, 0, 0)],
                    retained_obstacles(physical, excluded),
                ),
            }
        )


def _record_drive_checks(report, doc, module, physical, frame, prefix, sign):
    """Collect direct input-drive and separately supported output evidence."""
    pod = doc.getObject(prefix + "Pod")
    report["input_bearing_support"].append(input_bearing_support_check(doc, prefix))
    _record_drive_motion_checks(report, doc, module, prefix)
    _record_output_stub_checks(report, prefix, pod, physical, frame)
    _record_bearing_checks(report, doc, module, prefix, physical)
    _record_drive_service_checks(report, doc, prefix, sign, physical)


def _record_fastener_checks(report, module, physical):
    """Verify installed fastener seats, engagement and ordered access routes."""
    clamp_parts = Part.makeCompound(
        [world_shape(obj) for obj in module["printed"]]
        + [
            physical[prefix + suffix]
            for prefix in ("Port", "Starboard")
            for suffix in ("Servo", "ServoHorn")
        ]
    )
    bolts = [
        obj
        for obj in module["hardware"]
        if obj.Name.endswith("Bolt")
        and ("ServoEar" in obj.Name or "BearingCap" in obj.Name)
    ]
    for bolt in bolts:
        nut_name = bolt.Name.removesuffix("Bolt") + "Nut"
        thread = float(bolt.NominalThreadDiameter.Value)
        report["fastener_stacks"].append(
            {
                "bolt": bolt.Name,
                "nut": nut_name,
                **clamp_fastener_check(
                    clamp_parts,
                    physical[bolt.Name],
                    physical[nut_name],
                    thread_diameter=thread,
                    nut_height=1.6 if thread == 2 else 1.3,
                ),
            }
        )
        prefix = "Port" if bolt.Name.startswith("Port") else "Starboard"
        if "ServoEar" in bolt.Name:
            prior = [
                row for row in report["input_drive_service"] if row["pod"] == prefix
            ]
            rows = prior[0].get("ear_fastener_release", []) if len(prior) == 1 else []
            dependency = "input_drive_service"
            prerequisite = "Remove both small output gears, park the selected output rotor90deg with input neutral, then remove the input shaft and loose driver by the checked routes. Withdraw the lower ear screw and release its shallow-pocket nut, then the upper pair. The remaining servo/horn/adapter and integrated frame stay installed until both pairs are free."
        else:
            prior = [
                row
                for row in report["bearing_service"]
                if row["bearing"] == prefix + "OutputBearingInboard"
            ]
            rows = prior[0].get("fastener_release", []) if len(prior) == 1 else []
            dependency = "bearing_service"
            prerequisite = "Remove the selected output gear and withdraw its rotor/shaft outward. Hold each side-entry cap nut, withdraw the cap bolt upward, then move the unthreaded nut0.2mm down and outward alongX. Release the negativeX pair, positiveX pair, then input-wing pair. Input-bearing replacement additionally requires the checked input-unit removal and return of the unmeshed output rotor to neutral before rotor withdrawal."
        matches = [row for row in rows if row["bolt"] == bolt.Name]
        service = (
            matches[0]
            if len(matches) == 1
            else {"passed": False, "error": "Missing ordered fastener service proof"}
        )
        obstacle_names = set(
            service.get("bolt_axial_withdrawal", {}).get("obstacles", [])
        )
        obstacle_names.update(service.get("nut_axial_removal", {}).get("obstacles", []))
        retained = obstacle_names & set(physical) - {bolt.Name, nut_name}
        prior_passed = len(prior) == 1 and prior[0]["passed"]
        report["fastener_service"].append(
            {
                **service,
                "bolt": bolt.Name,
                "nut": nut_name,
                "assembly_prerequisites": prerequisite,
                "service_group": module["group"].Name,
                "service_dependencies": [
                    {"check": dependency, "object": prefix, "passed": prior_passed}
                ],
                "retained_service_parts": sorted(retained),
                "removed_local_parts": sorted(set(physical) - retained),
                "passed": service["passed"] and prior_passed,
            }
        )

    doc = module["group"].Document
    for prefix, sign in (("Port", 1), ("Starboard", -1)):
        registration = horn_registration_check(doc, prefix)
        prior = [
            row
            for row in report["input_drive_service"]
            if row["pod"] == prefix and "adapter_clamp_release" in row
        ]
        service = (
            prior[0]
            if len(prior) == 1
            else input_drive_service_check(doc, module, prefix)
        )
        for joint in registration.get("joints", []):
            report["fastener_stacks"].append(
                {
                    "bolt": prefix + "HornGearClamp" + joint["joint"] + "Bolt",
                    "nut": prefix + "HornGearClamp" + joint["joint"] + "Nut"
                    if joint["separate_nut_required"]
                    else None,
                    **joint,
                }
            )
        for row in service.get("adapter_clamp_release", {}).get("fasteners", []):
            dependencies = [
                {
                    "check": "input_drive_service",
                    "object": prefix,
                    "passed": service["passed"],
                }
            ]
            if row["joint"] == "Near":
                dependencies.append(
                    {
                        "check": "fastener_service",
                        "object": prefix + "HornGearClampFarBolt",
                        "passed": service["adapter_clamp_release"]["fasteners"][0][
                            "passed"
                        ],
                    }
                )
            report["fastener_service"].append(
                {
                    **row,
                    "nut": row.get("nut"),
                    "assembly_prerequisites": service["scope"],
                    "service_group": module["group"].Name,
                    "service_dependencies": dependencies,
                    "retained_service_parts": row["retained_parts"],
                    "removed_local_parts": row["removed_prior_parts"]
                    + [row.get("removed_part", row["bolt"])],
                    "passed": row["passed"]
                    and all(item["passed"] for item in dependencies),
                }
            )


def _record_print_checks(report, module, physical):
    """Measure functional walls and check every printable solid and mesh."""
    wall_probes = propulsion.manufacturing_wall_probes(
        drive=drive_for_document(module["group"].Document)
    ) + [
        (
            "guard_radial",
            "PortMotorCarrier",
            (
                propulsion.GUARD_PLANE_X,
                propulsion.PIVOT_HALF_SPAN,
                propulsion.PIVOT_Z + 22.99,
            ),
            (
                propulsion.GUARD_PLANE_X,
                propulsion.PIVOT_HALF_SPAN,
                propulsion.PIVOT_Z + 26.01,
            ),
            3.0,
        ),
        ("guard_axial", "PortMotorCarrier", (7.99, 75, 74.5), (11.01, 75, 74.5), 3.0),
        ("guard_root_fan", "PortMotorCarrier", (7.99, 46, 55), (11.01, 46, 55), 3.0),
        (
            "guard_rear_bridge",
            "PortMotorCarrier",
            (-8.01, 91, 50),
            (-4.99, 91, 50),
            3.0,
        ),
        (
            "guard_outer_return",
            "PortMotorCarrier",
            (2, 97.99, 50),
            (2, 101.01, 50),
            3.0,
        ),
    ]
    from gondola.parts import servo_coupling as coupling

    spec = drive_for_document(module["group"].Document)
    x, z = spec.input_x_mm, spec.input_z_mm
    wall_probes.extend(
        [
            (
                "driver_shaft_stop_roof",
                "PortHornGearAdapter",
                (
                    x + 2,
                    coupling.HORN_BOTTOM_Y - 8 + coupling.OEM_HEAD_CAVITY_TOP_Y - 0.01,
                    z,
                ),
                (x + 2, coupling.HORN_BOTTOM_Y - 8 + coupling.SHAFT_START_Y, z),
                1.5,
            ),
            (
                "driver_shaft_nut_retaining_wall",
                "PortHornGearAdapter",
                tuple(
                    App.Vector(x, coupling.HORN_BOTTOM_Y - 8, z)
                    + coupling.shaft_frame_point(
                        coupling.SHAFT_NUT_SEAT_X + 0.01,
                        coupling.SHAFT_CLAMP_Y + 1.5,
                        0,
                    )
                ),
                tuple(
                    App.Vector(x, coupling.HORN_BOTTOM_Y - 8, z)
                    + coupling.shaft_frame_point(
                        coupling.SHAFT_BOSS_END_X - 0.01,
                        coupling.SHAFT_CLAMP_Y + 1.5,
                        0,
                    )
                ),
                abs(coupling.SHAFT_BOSS_END_X - coupling.SHAFT_NUT_SEAT_X),
            ),
        ]
    )
    for feature, name, start, end, expected in wall_probes:
        section = physical[name].common(
            Part.makeLine(App.Vector(*start), App.Vector(*end))
        )
        thickness = sum(edge.Length for edge in section.Edges)
        report["functional_wall_probes"].append(
            {
                "feature": feature,
                "part": name,
                "measured_wall_mm": thickness,
                "expected_wall_mm": expected,
                "passed": abs(thickness - expected) < TOL and thickness >= 1.5 - TOL,
            }
        )
    for obj in module["printed"]:
        shape = print_shape(obj)
        mesh = MeshPart.meshFromShape(
            Shape=shape,
            LinearDeflection=0.03,
            AngularDeflection=0.08,
            Relative=False,
        )
        check = mesh_checks(shape, mesh)
        report["geometry"].append(
            {
                "name": obj.Name,
                **check,
                "passed": check["valid_brep"]
                and check["solid_count"] == 1
                and check["single_closed_solid"]
                and check["watertight_mesh"]
                and check["mesh_components"] == 1,
            }
        )


def _complete_report(report, module):
    """Require every evidence row and its independently declared count."""
    report["all_bought_parts_excluded_from_prints"] = all(
        obj not in module["printed"] and not bool(getattr(obj, "PrintPart", False))
        for obj in module["hardware"]
    )
    evidence = propulsion_evidence_check(report)
    report["expected_evidence_counts"] = dict(PROPULSION_EVIDENCE_COUNTS)
    report["required_evidence_inventory"] = evidence["inventory"]
    report["evidence_row_failures"] = evidence["row_failures"]
    report["overlap_failures"] = overlap_failures(report, TOL)
    report["passed"] = (
        not report["overlap_failures"]
        and report["all_bought_parts_excluded_from_prints"]
        and evidence["passed"]
    )


def _write_report(report, source):
    """Persist the validation JSON and emit its completion message."""
    target = source.parent / (source.stem + "_propulsion_validation.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {"local_propulsion_report": str(target), "passed": report["passed"]}
        ),
        flush=True,
    )


def validate(source=None, *, drive=SELECTED_DRIVE):
    """Build the source mechanism and audit its actual mating and service shapes."""
    source = (
        Path(source).resolve() if source else OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")
    )
    doc = App.newDocument("PropulsionSourceAudit")
    try:
        module = propulsion.build_propulsion_module(doc, drive=drive)
        propulsion.build_fit_coupons(doc)
        frame = world_shape(module["frame"])
        objects = module["printed"] + module["hardware"] + module["references"]
        physical = {obj.Name: world_shape(obj) for obj in objects}
        report = {
            "gear_configuration": drive_for_document(doc).key,
            "scope": "Source rigid-envelope, nominal fit and bench-service audit; OEM fit, friction retention and loaded operation remain unqualified.",
            "printed_parts": len(module["printed"]),
            "purchased_hardware": len(module["hardware"]),
            "metrics": module["metrics"],
        }
        report.update({key: [] for key in PROPULSION_EVIDENCE_COUNTS})
        from .horn_coupling import profile_compatibility_checks

        report["horn_profile_compatibility"] = profile_compatibility_checks()
        report["integrated_frame"].append(integrated_frame_check(doc, module))
        report["servo_service_preparation"].append(
            servo_service_preparation_check(doc, module)
        )
        report["rail_mount_clearance"].append(rail_mount_clearance_check(doc, module))
        report["bearing_post_roots"] = bearing_post_roots_check(doc)
        from .nut_guides import installed_nut_guide_checks

        report["nut_guides"] = installed_nut_guide_checks(doc)
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            _record_drive_checks(report, doc, module, physical, frame, prefix, sign)
        _record_fastener_checks(report, module, physical)
        _record_print_checks(report, module, physical)
        report["relative_motion"].append(relative_motion_check(doc, module))
        _complete_report(report, module)
        _write_report(report, source)
        return report
    finally:
        App.closeDocument(doc.Name)
