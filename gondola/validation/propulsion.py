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

from .bearing_capture import bearing_stack_check, keeper_alignment_sensitivity
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
from .geometry import (
    belongs_to_group,
    intersection_volume,
)
from .horn_coupling import coupling_frame
from .motion_clearance import carrier_axial_travel, carrier_metal_clearance_check
from .propulsion_evidence import PROPULSION_EVIDENCE_COUNTS, propulsion_evidence_check
from .propulsion_service import (
    contained_region_paths,
    continuous_path,
    fastener_service_check,
    module_service_shapes,
    retained_obstacles,
    servo_bench_members,
)
from .rail_contact import attachment_check
from .relative_motion import relative_motion_check
from .servo_interface import horn_spline_contact
from .servo_module import bridge_joint_check, servo_module_service_check

TOL = 1e-5


def output_bearing_stack_check(doc, prefix, suffix, axial_stops=None):
    """Normalize all real saved placements before the local capture proof."""
    from .motion_clearance import _in_pod_coordinates

    pod = doc.getObject(prefix + "Pod")
    names = [
        prefix + "OutputBearing" + suffix,
        prefix + "OutputShaft" + suffix,
        "PropulsionFixedFrame",
        prefix + "MotorCarrier",
        prefix + "OutputBearingKeeper" + suffix,
    ]
    fastener_names = [
        prefix + "OutputBearingKeeper" + suffix + kind for kind in ("Bolt", "Nut")
    ]
    objects = [doc.getObject(name) for name in names]
    fasteners = [doc.getObject(name) for name in fastener_names]
    if pod is None or any(obj is None for obj in objects + fasteners):
        return {"passed": False, "error": "Missing output bearing capture component"}
    stops = (
        axial_stops if axial_stops is not None else carrier_axial_travel(doc, prefix)
    )
    if not stops.get("passed"):
        return {
            "passed": False,
            "error": "Unproven carrier/frame axial stops",
            "axial_stops": stops,
        }
    shapes = [_in_pod_coordinates(obj, pod) for obj in objects]
    if suffix == "Negative":
        for shape in shapes:
            shape.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
    capture = bearing_stack_check(
        *shapes,
        toward_travel=stops["positive_mm" if suffix == "Positive" else "negative_mm"],
        away_travel=stops["negative_mm" if suffix == "Positive" else "positive_mm"],
    )

    seated = clamp_fastener_check(
        Part.makeCompound([world_shape(objects[2]), world_shape(objects[4])]),
        world_shape(fasteners[0]),
        world_shape(fasteners[1]),
    )
    return {
        "bearing": names[0],
        **capture,
        "keeper_fastener": seated,
        "passed": capture["passed"] and seated["passed"],
    }


def _planar_contact_area(first, second):
    area = 0.0
    for face in first.Faces:
        if type(face.Surface).__name__ != "Plane":
            continue
        normal = face.normalAt(0, 0)
        for seat in second.Faces:
            if type(seat.Surface).__name__ != "Plane":
                continue
            if (
                abs(abs(normal.dot(seat.normalAt(0, 0))) - 1) < 1e-7
                and abs((face.CenterOfMass - seat.CenterOfMass).dot(normal)) < 1e-7
            ):
                area += face.common(seat).Area
    return area


def clamp_fastener_check(clamp, bolt, nut, *, thread_diameter=2.0, nut_height=1.6):
    """Require seated bolt/nut bearing faces and a complete nominal metric nut core.

    This checks assembly geometry only. A tightened split clamp's shaft torque
    capacity, creep and axial grip are not established by a rigid CAD model.
    """
    contacts = []
    for name, fastener in (("Bolt", bolt), ("Nut", nut)):
        area = _planar_contact_area(fastener, clamp)
        contacts.append(
            {"part": name, "bearing_contact_area_mm2": area, "passed": area > TOL}
        )
    bore_surfaces = [
        face.Surface
        for face in nut.Faces
        if type(face.Surface).__name__ == "Cylinder"
        and abs(face.Surface.Radius - thread_diameter / 2) < TOL
    ]
    if not bore_surfaces:
        return {
            "contacts": contacts,
            "passed": False,
            "error": "Missing metric nut bore",
        }
    bore = bore_surfaces[0]
    axis = bore.Axis
    projections = [vertex.Point.dot(axis) for vertex in nut.Vertexes]
    low, high = min(projections), max(projections)
    origin = bore.Center + axis * (low - bore.Center.dot(axis))
    core = Part.makeCylinder(thread_diameter * 0.4, high - low, origin, axis)
    missing_core = abs(core.cut(bolt).Volume)
    clamp_overlap = intersection_volume(clamp, bolt) + intersection_volume(clamp, nut)
    return {
        "contacts": contacts,
        "nut_engagement_length_mm": high - low,
        "missing_bolt_thread_core_mm3": missing_core,
        "fastener_clamp_overlap_mm3": clamp_overlap,
        "scope": "Nominal seated metric fasteners with full nut core; no helical-thread, preload, shaft-friction or printed-clamp strength qualification.",
        "passed": all(row["passed"] for row in contacts)
        and missing_core < TOL
        and high - low >= nut_height - TOL
        and clamp_overlap < TOL,
    }


def output_stub_check(shaft, motor, pivot_y):
    """Keep each purchased output stub clear of the central propulsion motor."""
    bounds = shaft.optimalBoundingBox(False, False)
    stays_on_one_side = bounds.YMax < pivot_y - TOL or bounds.YMin > pivot_y + TOL
    volume = intersection_volume(shaft, motor)
    clearance = shaft.distToShape(motor)[0]
    return {
        "shaft_y_bounds_mm": [bounds.YMin, bounds.YMax],
        "pivot_y_mm": pivot_y,
        "separate_stub_on_one_side": stays_on_one_side,
        "motor_overlap_mm3": volume,
        "motor_gap_mm": clearance,
        "minimum_motor_gap_mm": 0.3,
        "passed": stays_on_one_side and volume < TOL and clearance >= 0.3 - TOL,
    }


def _coupling_shape_world(doc, prefix, shape):
    """Place a horn-local probe through the actual moving input-drive parents."""
    shape = shape.copy()
    shape.Placement = coupling_frame(doc, prefix).multiply(shape.Placement)
    return shape


def input_shaft_retention_check(doc, prefix):
    """Measure the metal stub's keyed socket, axial stop and radial jack clamp."""
    from gondola.contracts import fasteners
    from gondola.parts import purchased_hardware as hardware
    from gondola.parts import servo_coupling as coupling

    names = (
        "InputShaft",
        "InputShaftClampBolt",
        "InputShaftClampNut",
        "HornGearAdapter",
    )
    if any(doc.getObject(prefix + suffix) is None for suffix in names):
        return {"pod": prefix, "passed": False, "error": "Missing driver stub or clamp"}
    shaft, screw, nut, adapter = (
        world_shape(doc.getObject(prefix + suffix)) for suffix in names
    )
    expected_shaft = _coupling_shape_world(doc, prefix, coupling.driver_shaft_shape())
    missing_shaft = abs(expected_shaft.cut(shaft).Volume)
    extra_shaft = abs(shaft.cut(expected_shaft).Volume)
    head_probe = Part.makeCylinder(
        hardware.SCREW_HEAD_DIAMETER / 2 + 0.01,
        hardware.SCREW_HEAD_HEIGHT + 0.1,
        App.Vector(coupling.SHAFT_SCREW_HEAD_X, coupling.SHAFT_CLAMP_Y, 0),
        App.Vector(-1, 0, 0),
    )
    head = screw.common(
        _coupling_shape_world(doc, prefix, coupling.shaft_frame_shape(head_probe))
    )
    head_gap = head.distToShape(adapter)[0] if head.Volume > TOL else -1
    tip_contact = _planar_contact_area(screw, shaft)
    # Only the outer pocket wall reacts against tightening the radial screw.
    # Contact with the opposite insertion-slot wall cannot establish preload.
    seat_x, seat_y = coupling.SHAFT_NUT_SEAT_X, coupling.SHAFT_CLAMP_Y
    seat_points = [
        App.Vector(seat_x, seat_y + y, z)
        for y, z in ((-3, -3), (3, -3), (3, 3), (-3, 3))
    ]
    seat_plane = Part.Face(Part.makePolygon(seat_points + seat_points[:1]))
    retaining_wall = adapter.common(
        _coupling_shape_world(doc, prefix, coupling.shaft_frame_shape(seat_plane))
    )
    nut_wall_contact = _planar_contact_area(nut, retaining_wall)
    # The smallest accepted nut must also encounter the saved pocket walls.
    # Keep its threaded axis fixed at the installed screw; this does not model
    # an unthreaded nut lifted through the deliberately open loading slot.
    minimum_nut = hardware.hex_prism(
        fasteners.HEX_NUT_MIN_AF, fasteners.HEX_NUT_MIN_HEIGHT
    ).cut(
        Part.makeCylinder(
            fasteners.THREAD_DIAMETER / 2,
            fasteners.HEX_NUT_MIN_HEIGHT + 0.2,
            App.Vector(0, 0, -0.1),
        )
    )
    minimum_nut.Placement = App.Placement(
        App.Vector(seat_x, seat_y, 0),
        App.Rotation(App.Vector(0, 0, 1), App.Vector(*coupling.SHAFT_BOLT_DIRECTION)),
    )
    placed_minimum_nut = _coupling_shape_world(
        doc, prefix, coupling.shaft_frame_shape(minimum_nut)
    )
    minimum_nut_overlap = intersection_volume(placed_minimum_nut, adapter)
    minimum_nut_contact = _planar_contact_area(placed_minimum_nut, retaining_wall)
    nut_rotation_checks = []
    for angle in (-30, 30):
        rotated = minimum_nut.copy()
        rotated.rotate(App.Vector(seat_x, seat_y, 0), App.Vector(1, 0, 0), angle)
        overlap = intersection_volume(
            adapter,
            _coupling_shape_world(doc, prefix, coupling.shaft_frame_shape(rotated)),
        )
        nut_rotation_checks.append(
            {
                "attempted_rotation_deg": angle,
                "pocket_probe_penetration_mm3": overlap,
                "passed": overlap > TOL,
            }
        )
    minimum_nut_capture = {
        "across_flats_mm": fasteners.HEX_NUT_MIN_AF,
        "height_mm": fasteners.HEX_NUT_MIN_HEIGHT,
        "neutral_pocket_overlap_mm3": minimum_nut_overlap,
        "retaining_wall_contact_mm2": minimum_nut_contact,
        "rotation_stop_checks": nut_rotation_checks,
        "scope": "Smallest accepted nut on the fixed threaded axis against the actual saved nominal pocket. Both 30-degree attempts must be blocked. This does not bound angular play or certify as-printed capture with +/-0.3 mm manufacturing variation, nut handling, tightening torque or PA12 strength; finish and trial the received nut.",
        "passed": minimum_nut_overlap < TOL
        and minimum_nut_contact > 1
        and all(row["passed"] for row in nut_rotation_checks),
    }
    stop_contact = _planar_contact_area(shaft, adapter)
    roof_probe = Part.makeLine(
        App.Vector(2, coupling.OEM_HEAD_CAVITY_TOP_Y, 0),
        App.Vector(2, coupling.SHAFT_START_Y, 0),
    )
    roof_thickness = adapter.common(
        _coupling_shape_world(doc, prefix, roof_probe)
    ).Length
    key_checks = []
    for angle in (-15, 15):
        rotated = coupling.driver_shaft_shape()
        rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
        overlap = intersection_volume(
            adapter, _coupling_shape_world(doc, prefix, rotated)
        )
        key_checks.append(
            {
                "attempted_rotation_deg": angle,
                "key_probe_penetration_mm3": overlap,
                "passed": overlap > 1e-3,
            }
        )
    stop_probe = coupling.driver_shaft_shape()
    stop_probe.translate(App.Vector(0, -0.01, 0))
    stop_overlap = intersection_volume(
        adapter, _coupling_shape_world(doc, prefix, stop_probe)
    )
    socket_probe = Part.makeCylinder(
        2,
        coupling.SHAFT_SOCKET_LENGTH,
        App.Vector(0, coupling.SHAFT_START_Y, 0),
        App.Vector(0, 1, 0),
    )
    socket_shaft = expected_shaft.common(
        _coupling_shape_world(doc, prefix, socket_probe)
    )
    missing_engagement = abs(socket_shaft.cut(shaft).Volume)
    # The jack must have a reaction at the centred shaft, not after taking up
    # a radial gap. That gap would turn with the horn and make the gear run out.
    support_line = coupling.shaft_frame_shape(
        Part.makeLine(App.Vector(1.5, 7.2, 0), App.Vector(1.5, 15.0, 0))
    )
    support_line = _coupling_shape_world(doc, prefix, support_line)
    centred_support = adapter.common(support_line).common(shaft).Length
    loaded_probe = coupling.driver_shaft_shape()
    loaded_probe.translate(coupling.shaft_frame_point(0.01, 0, 0))
    loaded_penetration = intersection_volume(
        adapter, _coupling_shape_world(doc, prefix, loaded_probe)
    )
    radial_seating = {
        "centred_reaction_contact_length_mm": centred_support,
        "required_contact_length_mm": 7.8,
        "jack_direction_probe_travel_mm": 0.01,
        "jack_direction_probe_penetration_mm3": loaded_penetration,
        "scope": "Nominal circular journal contact opposite the jack at the horn axis, with a 0.01 mm attempted radial shift blocked. The filed flat is relieved. Finish the actual socket for hand insertion without rocking; reprint an oversized bore. No as-printed fit, concentricity or loaded-strength qualification.",
        "passed": abs(centred_support - 7.8) < TOL and loaded_penetration > 0.01,
    }
    return {
        "pod": prefix,
        "shaft_nominal_diameter_mm": coupling.SHAFT_DIAMETER,
        "shaft_length_mm": coupling.SHAFT_LENGTH,
        "filed_flat_depth_mm": coupling.SHAFT_FLAT_DEPTH,
        "socket_engagement_mm": coupling.SHAFT_SOCKET_LENGTH,
        "missing_nominal_stub_mm3": missing_shaft,
        "extra_stub_material_mm3": extra_shaft,
        "missing_socket_engagement_mm3": missing_engagement,
        "centred_jack_reaction": radial_seating,
        "shaft_stop_contact_mm2": stop_contact,
        "stop_probe_penetration_mm3": stop_overlap,
        "key_checks": key_checks,
        "screw_tip_to_flat_contact_mm2": tip_contact,
        "nut_to_retaining_wall_contact_mm2": nut_wall_contact,
        "minimum_nut_capture": minimum_nut_capture,
        "screw_head_to_adapter_gap_mm": head_gap,
        "required_nominal_head_gap_mm": 0.5,
        "shaft_stop_roof_thickness_mm": roof_thickness,
        "scope": "Nominal metal D stub and finished printed socket; the centred circular journal reacts against the radial M2x6 jack without designed lateral take-up. Only the filed flat is relieved. Positive key engagement, axial stop and retained hex nut remain separate checks. The screw head must remain free to advance against the flat. Manual rod diameter/straightness/flat, nut capture, clamp preload, axial grip, actual gear set-screw retention and loaded servo deflection remain physical checks. The bore key alone is not axial retention.",
        "passed": missing_shaft < TOL
        and extra_shaft < TOL
        and socket_shaft.Volume > TOL
        and missing_engagement < TOL
        and radial_seating["passed"]
        and stop_contact > 1
        and stop_overlap > 1e-5
        and all(row["passed"] for row in key_checks)
        and tip_contact > 1
        and nut_wall_contact > 1
        and minimum_nut_capture["passed"]
        and abs(head_gap - 0.5) < TOL
        and abs(roof_thickness - 1.5) < TOL
        and all(
            intersection_volume(a, b) < TOL
            for a, b in (
                (shaft, adapter),
                (screw, shaft),
                (screw, adapter),
                (nut, adapter),
                (screw, nut),
            )
        ),
    }


def horn_registration_check(doc, prefix):
    from .horn_coupling import horn_registration_check as check_selected_horn

    return check_selected_horn(doc, prefix)


def direct_adapter_fit_check(doc, prefix):
    """Preserve the actual Ø3 gear bore, metal engagement and stock-horn capture."""
    from gondola.parts import servo_coupling as coupling

    parts = {
        suffix: world_shape(doc.getObject(prefix + suffix))
        for suffix in (
            "DriverGear",
            "ServoHorn",
            "HornGearAdapter",
            "HornGearClampNearBolt",
            "HornGearClampFarBolt",
            "InputShaft",
            "InputShaftClampBolt",
            "InputShaftClampNut",
        )
    }
    specification = drive_for_document(doc).driver
    origin = App.Vector(0, coupling.GEAR_START_Y, 0)
    axis = App.Vector(0, 1, 0)
    bore = Part.makeCylinder(
        specification.bore_mm / 2, specification.total_length_mm, origin, axis
    )
    ring = Part.makeCylinder(
        specification.bore_mm / 2 + 0.3, specification.total_length_mm, origin, axis
    ).cut(bore)
    bore = _coupling_shape_world(doc, prefix, bore)
    ring = _coupling_shape_world(doc, prefix, ring)
    bore_intrusion = intersection_volume(bore, parts["DriverGear"])
    missing_hub = abs(ring.cut(parts["DriverGear"]).Volume)
    adapter_in_gear_bore = intersection_volume(bore, parts["HornGearAdapter"])
    expected_shaft = _coupling_shape_world(doc, prefix, coupling.driver_shaft_shape())
    gear_journal = expected_shaft.common(bore)
    missing_gear_engagement = abs(gear_journal.cut(parts["InputShaft"]).Volume)
    projection = (
        coupling.SHAFT_START_Y
        + coupling.SHAFT_LENGTH
        - (coupling.GEAR_START_Y + specification.total_length_mm)
    )
    reserve = expected_shaft.common(
        _coupling_shape_world(
            doc,
            prefix,
            Part.makeCylinder(
                specification.bore_mm / 2,
                projection,
                App.Vector(0, coupling.GEAR_START_Y + specification.total_length_mm, 0),
                axis,
            ),
        )
    )
    missing_reserve = abs(reserve.cut(parts["InputShaft"]).Volume)
    rows = []
    names = list(parts)
    for index, name in enumerate(names):
        for other in names[index + 1 :]:
            rows.append(
                {
                    "parts": [prefix + name, prefix + other],
                    "intersection_mm3": intersection_volume(parts[name], parts[other]),
                }
            )
    capture = {
        name: _planar_contact_area(parts["ServoHorn"], parts[name])
        for name in ("HornGearAdapter",)
    }
    retention = input_shaft_retention_check(doc, prefix)
    registration = horn_registration_check(doc, prefix)
    return {
        "pod": prefix,
        "gear_bore_mm": specification.bore_mm,
        "gear_bore_intrusion_mm3": bore_intrusion,
        "missing_gear_hub_ring_mm3": missing_hub,
        "printed_adapter_in_gear_bore_mm3": adapter_in_gear_bore,
        "metal_gear_engagement_mm": specification.total_length_mm,
        "missing_metal_gear_engagement_mm3": missing_gear_engagement,
        "metal_projection_beyond_gear_mm": projection,
        "missing_gear_end_reserve_mm3": missing_reserve,
        "input_shaft_retention_passed": retention["passed"],
        "horn_registration": registration,
        "internal_pairs": rows,
        "nominal_horn_contact_area_mm2": capture,
        "scope": "Selected bought Ø3 bore remains unchanged. The metal D stub spans the full 8 mm driver and projects 2 mm beyond it; this is a metal-length reserve, not a qualified axial adjustment range or arbitrary-gear compatibility. The printed adapter stays outside the bore. The manufacturer X06 half arm 1 uses rear M1.4x8 screws and front nuts through its two enlarged existing Ø1 pilot holes at 6.8/13.2 mm. No new hole centres are transferred. The open C register and flat face limit misalignment; the nominal STEP fixes the hole positions and root geometry, while installed seating, delivered concentricity and runout remain unmeasured. Finish the local register against the received horn and check final runout. Horn strength, clamp preload, stainless rod quality, gear set screw and servo radial-load capacity remain physical checks.",
        "passed": specification.bore_mm == coupling.GEAR_BORE_DIAMETER
        and specification.total_length_mm == coupling.GEAR_LENGTH
        and bore_intrusion < TOL
        and missing_hub < TOL
        and adapter_in_gear_bore < TOL
        and gear_journal.Volume > TOL
        and missing_gear_engagement < TOL
        and abs(projection - 2) < TOL
        and reserve.Volume > TOL
        and missing_reserve < TOL
        and retention["passed"]
        and registration["passed"]
        and all(row["intersection_mm3"] < TOL for row in rows)
        and all(area > 1 for area in capture.values()),
    }


def _servo_rear_body_allowance(doc, prefix):
    """Measure the rear case separately from its lower mounting ear."""
    from gondola.parts import servo_bridge, servo_envelope

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
    if any(name not in shapes for name in (prefix + "Servo", "ServoDriveBridge")):
        return {"passed": False, "error": "Missing servo case or connecting plate"}
    rear = servo_envelope.case_rear_y()
    # Read a rear-case strip that does not contain the forward mounting ears.
    # The lower ear reaches four millimetres below the actual body.
    strip_width = servo_envelope.CASE_WIDTH + 2
    strip = Part.makeBox(
        strip_width, 1, 40, App.Vector(-strip_width / 2, rear + 0.5, -30)
    )
    body = shapes[prefix + "Servo"].common(strip)
    under = shapes["ServoDriveBridge"].common(
        Part.makeBox(
            servo_envelope.CASE_WIDTH,
            1,
            40,
            App.Vector(-servo_envelope.CASE_WIDTH / 2, rear + 0.5, -40),
        )
    )
    if not body.Solids or not under.Solids:
        return {"passed": False, "error": "Missing rear body strip or plate beneath it"}
    body_bounds = body.optimalBoundingBox(False, False)
    plate_bounds = under.optimalBoundingBox(False, False)
    gap = body_bounds.ZMin - plate_bounds.ZMax
    lane_end = rear - 0.1
    lane_start = lane_end - servo_bridge.REAR_LEAD_ALLOWANCE
    lane = Part.makeBox(
        body_bounds.XLength,
        servo_bridge.REAR_LEAD_ALLOWANCE,
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
        "plate_top_below_rear_body_z_mm": plate_bounds.ZMax,
        "rear_body_to_plate_gap_mm": gap,
        "minimum_rear_body_allowance_mm": 5.0,
        "inward_planning_volume_mm": [
            body_bounds.XLength,
            servo_bridge.REAR_LEAD_ALLOWANCE,
            body_bounds.ZLength,
        ],
        "inward_planning_y_range_mm": [lane_start, lane_end],
        "checked_physical_objects": sorted(shapes),
        "planning_volume_collisions": collisions,
        "continuous_input_drive_clearance": moving_rows,
        "scope": "Saved rear case strip excludes the lower mounting ear. Rearward planning space stops before the case rear face and never claims under-ear/nut access. Every physical input-drive part on both sides is checked through its complete bounded motion. Received lead exit position, diameter, connector and bend radius are unspecified; this rigid design allowance is not a factory cable route or installed harness qualification.",
        "passed": abs(body_bounds.ZMin - servo_envelope.CASE_BOTTOM_Z) < TOL
        and abs(body_bounds.ZLength - servo_envelope.CASE_LENGTH) < TOL
        and abs(body_bounds.XLength - servo_envelope.CASE_WIDTH) < TOL
        and gap >= 5.0 - TOL
        and not collisions
        and bool(moving_rows)
        and all(row["passed"] for row in moving_rows),
    }


def servo_mount_check(doc, prefix):
    """Require both stock ears to seat on the removable bridge without collision."""
    from .servo_ear_nuts import servo_ear_nut_check

    frame = world_shape(doc.ServoDriveBridge)
    servo = world_shape(doc.getObject(prefix + "Servo"))
    frame_overlap = intersection_volume(frame, servo)
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
        "shallow_nut_capture": nut_capture,
        "cases": rows,
        "scope": "The two published X06 ears bear directly on the removable bridge using M1.6 fasteners. Nominal rigid contact is not proof of clamp torque, stiffness or actual case fit.",
        "passed": frame_overlap < TOL
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
    """Check the stock-horn servo unit's complete off-bridge service sequence.

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
        for start_y in (-6.0, 1.25):
            plug = Part.makeCylinder(
                1.7, 4.75, App.Vector(0, start_y, 6), App.Vector(0, 1, 0)
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
    plug_volume = 4 * math.pi * 1.7**2 * 4.75
    return {
        "lower_frame_path": path,
        "upper_geometry_initial_z_gap_mm": upper_gap,
        "original_shape_missing_from_envelope_mm3": missing,
        "side_bore_filled_volume_mm3": added,
        "maximum_side_bore_plug_volume_mm3": plug_volume,
        "scope": "Fill only the four side screw bores within the solid U legs, then split at the servo-seat plane. Sweep the open U stock separately from two outboard beam stocks. The straight-rail envelope conservatively fills lower crowns toZ1.5 and beam R0.5 edge cuts while preserving roof/root relief. Complete lower-shape containment is required. Upper stock starts above the rail and moves upward. This local check does not certify adjacent equipment or a bent bonded rail.",
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
            ("RailMountScrew", rail.attachment_screw_shape(20, head_face_y=-9.0)),
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
        "shared_servo_bridge_clamp": True,
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
        rail.attachment_screw_shape(20, head_face_y=-9.0), x=x
    )
    hardware_geometry = []
    for name, expected, sku in (
        (screw_name, expected_screw, "M3X20_BUTTON_HEAD"),
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
    crop = Part.makeBox(10, 22, 11, App.Vector(x - 5, -11, 1.5))
    contact = attachment_check(
        translated_shape(shapes["LocalRailReference"], x=-x),
        translated_shape(shapes["PropulsionFixedFrame"].common(crop), x=-x),
        contact_length=38,
        shared_drive=True,
        screw_length=20,
        head_face_y=-9.0,
        nut_bearing_y=8.0,
        nut_outer_y=11.0,
        frame_contact_y=6.0,
        head_support=translated_shape(shapes["ServoDriveBridge"].common(crop), x=-x),
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
    capture = nut_capture_check(x, nut, shapes["ServoDriveBridge"], shared=True)
    lift = vertical_frame_release_check(
        shapes["PropulsionFixedFrame"], shapes["LocalRailReference"]
    )
    overlaps = {
        "screw_frame": intersection_volume(screw, shapes["PropulsionFixedFrame"]),
        "screw_bridge": intersection_volume(screw, shapes["ServoDriveBridge"]),
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
        "shared_servo_bridge_clamp": True,
        "shared_grip_contact_check": contact,
        "paired_spine_support": paired_support,
        "hardware_geometry": hardware_geometry,
        "screw_length_mm": servo_bridge.SHARED_SCREW_LENGTH,
        "driver_access": driver,
        "centred_load_zone_x_range_mm": [x - 5, x + 5],
        "physical_spine_x_range_mm": [-19, 19],
        "bolt_withdrawal": withdrawal,
        "nut_removal_after_bolt": nut_path,
        "driver_clearance_overlap_mm3": stem_hits,
        "nut_window_anti_rotation": capture,
        "frame_vertical_removal": lift,
        "seated_intersections_mm3": overlaps,
        "scope": "All local servo, gear, bearing and rotor hardware stays installed. The shared recessed M3x20 rail/bridge screw and nut are serviced; support the frame and bridge together throughout release. The Ø4 driver stem is an external access envelope; the downward-open hex pocket with vertical flats limits nut rotation and retains a 2 mm nominal load-bearing floor. Actual socket engagement, nut insertion, finger access, harnesses, clamp force and bending remain bench checks. Complete populated-assembly service is audited separately.",
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
    """Require full post cores, eight R1.5 roots and a softly edged shared beam."""
    frame = doc.getObject("PropulsionFixedFrame")
    if frame is None:
        return [{"passed": False, "error": "Missing output support frame"}]
    shape = frame.Shape.copy()
    shape.Placement = App.Placement()
    # One uninterrupted raised beam carries all four roots into the U spine.
    # Keep this literal witness independent of source-builder dimensions.
    beam = Part.makeBox(18, 226.5, 5, App.Vector(-9, -113.25, 7.5))
    beam_edges = [
        edge
        for edge in beam.Edges
        if abs(edge.Length - 226.5) < TOL
        and all(abs(v.Point.z - 7.5) < TOL for v in edge.Vertexes)
    ]
    beam = beam.makeFillet(0.5, beam_edges).cut(
        Part.makeBox(20, 3, 10.2, App.Vector(-10, -1.5, 0))
    )
    missing_beam = abs(beam.cut(shape).Volume)
    rows = []
    bottom, top = 12.5, 27.0
    for sign in (-1, 1):
        for local_y in (-34.75, 34.75):
            centre_y = sign * (75 + local_y)
            witness = Part.makeBox(
                13,
                6,
                top - bottom,
                App.Vector(-6.5, centre_y - 3, bottom),
            )
            missing = abs(witness.cut(shape).Volume)
            # Analytic concave quarter circles are independent of makeFillet
            # and edge selection in the production builder.
            positive_blend = Part.makeBox(
                1.5, 6, 1.5, App.Vector(6.5, centre_y - 3, bottom)
            ).cut(
                Part.makeCylinder(
                    1.5,
                    6,
                    App.Vector(8, centre_y - 3, bottom + 1.5),
                    App.Vector(0, 1, 0),
                )
            )
            blends = positive_blend.fuse(
                positive_blend.mirror(App.Vector(), App.Vector(1, 0, 0))
            )
            missing_blend = abs(blends.cut(shape).Volume)
            former_root_envelope = Part.makeBox(
                18, 6, top - bottom, App.Vector(-9, centre_y - 3, bottom)
            )
            extra = abs(
                former_root_envelope.cut(witness.fuse(blends)).common(shape).Volume
            )
            rows.append(
                {
                    "side": sign,
                    "post_local_y_mm": local_y,
                    "root_section_mm": [13, 6],
                    "root_height_range_mm": [bottom, top],
                    "missing_root_material_mm3": missing,
                    "root_blend_radius_mm": 1.5,
                    "missing_root_blend_mm3": missing_blend,
                    "unexpected_root_material_mm3": extra,
                    "shared_beam_z_range_mm": [7.5, 12.5],
                    "missing_shared_beam_mm3": missing_beam,
                    "scope": "Raised 18x5 transverse beam with R0.5 lower exterior edges, unchanged full 13x6 post cores through Z27 and paired R1.5 root blends along X. Keep the roof mating face flat. Upper bearing/keeper cuts are checked separately. No post thinning or quantified strength, stiffness or fatigue improvement is inferred.",
                    "passed": missing < TOL
                    and missing_blend < TOL
                    and extra < TOL
                    and missing_beam < TOL,
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
        doc, module, prefix, module_release=report["servo_module_service"][0]
    )
    report["input_drive_service"].append(input_service)
    report["servo_case_service"].append(
        servo_case_service_check(doc, module, prefix, prior_service=input_service)
    )


def _record_output_stub_checks(report, prefix, pod, physical, frame):
    """Check the two separate output stubs and describe their bearing stacks."""
    withdrawal = (
        propulsion.SHAFT_ASSEMBLY_RETRACTION + propulsion.SHAFT_FINAL_WITHDRAWAL
    )
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        shaft_name = prefix + "OutputShaft" + suffix
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
        excluded = {shaft_name, prefix + "OutputGear"}
        report["shaft_service"].append(
            {
                "shaft": shaft_name,
                "excluded_physical_parts": sorted(excluded),
                "scope": "Remove the output gear and release its selected set screw, loosen the carrier split clamp, then withdraw this separate stub axially. Nominal unclamped bore; not clamp closure or grip proof.",
                **continuous_path(
                    physical[shaft_name],
                    [
                        (0, 0, 0),
                        (
                            0,
                            side * withdrawal,
                            0,
                        ),
                        (
                            40,
                            side * withdrawal,
                            0,
                        ),
                    ],
                    retained_obstacles(physical, excluded),
                ),
            }
        )


def output_carrier_service_check(doc, module, prefix):
    """Release the rotor while its independently captured bearings stay installed."""
    shapes, missing = module_service_shapes(doc, module)
    if missing:
        return {"pod": prefix, "missing_parts": missing, "passed": False}
    sign = 1 if prefix == "Port" else -1
    gear = prefix + "OutputGear"
    gear_path = continuous_path(
        shapes[gear],
        [(0, 0, 0), (0, -sign * 35, 0)],
        retained_obstacles(shapes, {gear}),
    )
    staged = {name: shape.copy() for name, shape in shapes.items() if name != gear}
    shaft_paths = []
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        for stem, travel, rows in (
            ("OutputShaft", propulsion.SHAFT_ASSEMBLY_RETRACTION, shaft_paths),
        ):
            name = prefix + stem + suffix
            offset = (0, side * travel, 0)
            path = continuous_path(
                staged[name], [(0, 0, 0), offset], retained_obstacles(staged, {name})
            )
            rows.append({"part": name, **path})
            staged[name] = translated_shape(staged[name], *offset)
    pod = doc.getObject(prefix + "Pod")
    excluded = {
        prefix + "OutputShaft" + suffix for suffix in ("Negative", "Positive")
    } | {gear}
    moving = {
        name for name in shapes if belongs_to_group(doc.getObject(name), pod)
    } - excluded
    fixed = retained_obstacles(staged, moving)
    paths = [
        {"part": name, **continuous_path(staged[name], [(0, 0, 0), (40, 0, 0)], fixed)}
        for name in sorted(moving)
    ]
    # Withdraw both stubs after the carrier. Captured bearings stay in the frame.
    for name in moving:
        staged.pop(name)
    full_shaft_paths = []
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        name = prefix + "OutputShaft" + suffix
        path = continuous_path(
            staged[name],
            [
                (0, 0, 0),
                (0, side * propulsion.SHAFT_FINAL_WITHDRAWAL, 0),
                (40, side * propulsion.SHAFT_FINAL_WITHDRAWAL, 0),
            ],
            retained_obstacles(staged, {name}),
        )
        full_shaft_paths.append({"part": name, **path})
        staged.pop(name)
    return {
        "pod": prefix,
        "moving_parts": sorted(moving),
        "removed_output_gear": gear,
        "output_gear_removal": gear_path,
        "shaft_staging": shaft_paths,
        "carrier_removal": paths,
        "full_shaft_removal": full_shaft_paths,
        "retained_parts": sorted(fixed),
        "scope": "Unpowered bench sequence with leads freed: remove the small gear, loosen the carrier clamps, retract each stub 12 mm, then slide the complete motor/carrier and clamp fasteners 40 mm in +X. Bearings remain captured by the fixed frame. After removing the rotor, withdraw each staged stub a further 20 mm axially and 40 mm in +X. Reverse for assembly and verify shaft clamping. Physical fits and tool handling require a prototype.",
        "passed": gear_path["passed"]
        and bool(moving)
        and all(row["passed"] for row in shaft_paths + paths + full_shaft_paths),
    }


def replacement_rotor_space_check(doc, module, prefix):
    """Reserve replacement bulk through all tilt angles and both service paths.

    This does not fit a 50 mm propeller to the current guard. The replacement
    bulk is constrained to an independent radius34 / axial±30 cylinder; its
    separate shaft and clamp interfaces retain the currently checked stops.
    """
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
        34, 60, App.Vector(origin.x, origin.y - 30, origin.z), App.Vector(0, 1, 0)
    )
    moving = Part.makeCylinder(
        34,
        60 + travel["negative_mm"] + travel["positive_mm"],
        App.Vector(origin.x, origin.y - 30 - travel["negative_mm"], origin.z),
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
        nominal_gap = abs(stop["frame_stop_y_mm"]) - 30
        remaining = nominal_gap - stop["travel_mm"]
        gaps.append(
            {
                "direction": stop["direction"],
                "nominal_post_face_gap_mm": nominal_gap,
                "gap_at_axial_stop_mm": remaining,
                "passed": remaining >= 1.25 - TOL,
            }
        )
    rotor_service = continuous_path(moving, [(0, 0, 0), (40, 0, 0)], obstacles)
    servo_paths = [
        {
            "part": name,
            **continuous_path(
                shapes[name],
                list(servo_bridge.SERVICE_WAYPOINTS),
                {"replacement_rotor_bulk": moving},
            ),
        }
        for name in sorted(servo_bench_members(doc, shapes))
    ]
    nominal_frame_gap = nominal.distToShape(shapes["PropulsionFixedFrame"])[0]
    return {
        "pod": prefix,
        "future_propeller_reference_diameter_mm": 50,
        "bulk_half_width_mm": 30,
        "full_rotation_radius_mm": 34,
        "axial_travel": travel,
        "post_face_gaps": gaps,
        "nominal_frame_gap_mm": nominal_frame_gap,
        "all_angle_gaps_with_axial_travel_mm": distances,
        "excluded_replacement_interface_parts": sorted(excluded),
        "rotor_bulk_removal": rotor_service,
        "servo_module_removal_past_future_bulk": servo_paths,
        "scope": "Continuous enclosing cylinder for a future replacement rotor bulk, including measured current axial stops. Both post faces, every retained physical propulsion part and reciprocal rotor +X40 / servo module +Z11 then +X80 service paths are checked. Present 40 mm guard and struts are not 50 mm compatible. Replacement shaft/clamp interfaces, assembly strength, future motor/propeller hardware and wiring still require design and tests; this is a space reservation only.",
        "passed": all(row["passed"] for row in gaps)
        and bool(distances)
        and min(distances.values()) >= 1.25 - TOL
        and nominal_frame_gap >= 1.75 - TOL
        and rotor_service["passed"]
        and bool(servo_paths)
        and all(row["passed"] for row in servo_paths),
    }


def _bearing_cup_world(doc, prefix, side, shape):
    """Transform canonical fixed-seat geometry, independently of rotor tilt."""
    from gondola.cad import mirrored_y

    sign = 1 if prefix == "Port" else -1
    result = mirrored_y(shape, side)
    result = translated_shape(
        result,
        y=sign * propulsion.PIVOT_HALF_SPAN + side * propulsion.BEARING_START_Y,
        z=propulsion.PIVOT_Z,
    )
    result.Placement = doc.PropulsionFixedFrame.getGlobalPlacement().multiply(
        result.Placement
    )
    return result


def _record_bearing_checks(report, doc, module, prefix, physical):
    """Prove screw release, keeper withdrawal and then inward bearing removal."""
    from gondola.parts import bearing_retention as capture

    from .nut_guides import guided_nut_service_direction

    carrier_service = output_carrier_service_check(doc, module, prefix)
    report["output_carrier_service"].append(carrier_service)
    removed = (
        set(carrier_service.get("moving_parts", []))
        | {prefix + "OutputGear"}
        | {prefix + "OutputShaft" + suffix for suffix in ("Negative", "Positive")}
    )
    staged = {
        name: shape.copy() for name, shape in physical.items() if name not in removed
    }
    for side, suffix in ((-1, "Negative"), (1, "Positive")):
        name = prefix + "OutputBearing" + suffix
        keeper_name = prefix + "OutputBearingKeeper" + suffix
        bolt_name, nut_name = keeper_name + "Bolt", keeper_name + "Nut"
        stack = output_bearing_stack_check(doc, prefix, suffix)
        report["bearing_stacks"].append(stack)
        missing = [
            part
            for part in (name, keeper_name, bolt_name, nut_name)
            if part not in staged
        ]
        if missing:
            report["bearing_service"].append(
                {"bearing": name, "missing_parts": missing, "passed": False}
            )
            continue
        cup = _bearing_cup_world(doc, prefix, side, capture.cup_shape())
        missing_cup = abs(cup.cut(staged["PropulsionFixedFrame"]).Volume)
        fastener_service = fastener_service_check(
            staged[bolt_name],
            staged[nut_name],
            retained_obstacles(staged, {bolt_name, nut_name}),
            guided_nut=True,
            nut_lateral_direction=guided_nut_service_direction(doc, bolt_name),
        )
        direction = doc.PropulsionFixedFrame.getGlobalPlacement().Rotation.multVec(
            App.Vector(0, -side * 20, 0)
        )
        released = retained_obstacles(staged, {bolt_name, nut_name})
        keeper_path = continuous_path(
            staged[keeper_name],
            [(0, 0, 0), tuple(direction)],
            retained_obstacles(released, {keeper_name}),
        )
        bearing_path = continuous_path(
            staged[name],
            [(0, 0, 0), tuple(direction)],
            retained_obstacles(released, {keeper_name, name}),
        )
        alignment = keeper_alignment_sensitivity(capture.keeper_shape())
        report["bearing_service"].append(
            {
                "bearing": name,
                "keeper": keeper_name,
                "required_prior_check": "output_carrier_service",
                "missing_saved_cup_mm3": missing_cup,
                "fastener_release": fastener_service,
                "keeper_removal": keeper_path,
                "bearing_removal": bearing_path,
                "local_capture_geometry": stack.get("capture_geometry", {}),
                "keeper_alignment_sensitivity": alignment,
                "scope": "Remove the output gear, carrier and both shafts first. Release the ordinary rear M2 nut, withdraw its M2 bolt inward, withdraw the rigid keeper inward, then withdraw the bearing. All retained physical objects remain obstacles. No flexure release, forced bearing insertion, purchased spacer or bearing preload is required. Actual fitting and retained screw tightness require physical qualification.",
                "passed": carrier_service["passed"]
                and stack["passed"]
                and missing_cup < TOL
                and fastener_service["passed"]
                and keeper_path["passed"]
                and bearing_path["passed"]
                and alignment["passed"],
            }
        )
        for part in (name, keeper_name, bolt_name, nut_name):
            staged.pop(part)


def _record_drive_service_checks(report, doc, prefix, sign, physical):
    """Audit in-place output gears and driver withdrawal on the removed bridge."""
    module_removed = bool(report["servo_module_service"][0]["passed"])
    bench_members = servo_bench_members(doc, physical)
    for suffix, direction, bench in (
        ("OutputGear", -sign, False),
        ("DriverGear", sign, True),
    ):
        name = prefix + suffix
        excluded = {name}
        report["gear_service"].append(
            {
                "gear": name,
                "required_prior_check": "servo_module_service" if bench else None,
                "prior_module_removal_passed": module_removed if bench else None,
                "scope": "Release the selected radial set screw before axial withdrawal. The output gear is removed in place. After the checked whole ServoDriveModule removal, withdraw the driver and input stub before releasing the servo-ear rear nuts and withdrawing the complete servo/horn/adapter unit. Every other paired-module part remains on the bench. Set-screw tip/length and actual driver access remain physical release gates.",
                **continuous_path(
                    physical[name],
                    [(0, 0, 0), (0, direction * 35, 0)],
                    retained_obstacles(
                        physical,
                        excluded,
                        members=bench_members if bench else None,
                    ),
                ),
            }
        )
    for row in report["gear_service"][-2:]:
        if row["required_prior_check"]:
            row["passed"] = row["passed"] and module_removed
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
    _record_drive_motion_checks(report, doc, module, prefix)
    _record_output_stub_checks(report, prefix, pod, physical, frame)
    _record_bearing_checks(report, doc, module, prefix, physical)
    _record_drive_service_checks(report, doc, prefix, sign, physical)


def _record_fastener_checks(report, module, physical):
    """Verify installed fastener seats, engagement and ordered access routes."""
    from .nut_guides import (
        guided_nut_capture_depth,
        guided_nut_service_direction,
        is_guided_nut_bolt,
    )

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
        if obj.HardwareSKU in ("M2X8_BUTTON_HEAD", "M1_6X8_PAN_HEAD_KIT")
        or (obj.HardwareSKU == "M2X6_BUTTON_HEAD" and "OutputBearingKeeper" in obj.Name)
    ]
    bolts.sort(key=lambda obj: "HornGearClampNear" in obj.Name)
    for bolt in bolts:
        nut_name = bolt.Name.removesuffix("Bolt") + "Nut"
        nut = physical[nut_name]
        thread_diameter = float(bolt.NominalThreadDiameter.Value)
        nut_height = 1.6 if thread_diameter == 2 else 1.3
        report["fastener_stacks"].append(
            {
                "bolt": bolt.Name,
                "nut": nut_name,
                **clamp_fastener_check(
                    clamp_parts,
                    physical[bolt.Name],
                    nut,
                    thread_diameter=thread_diameter,
                    nut_height=nut_height,
                ),
            }
        )
        service_excluded = {bolt.Name, nut_name}
        service_parts = set(physical)
        dependencies = []
        service_group = module["group"].Name
        prerequisites = "Other local propulsion parts stay installed at neutral tilt."
        servo_ear = "ServoEar" in bolt.Name
        retain_bolt = False
        if servo_ear:
            prefix = "Port" if bolt.Name.startswith("Port") else "Starboard"
            service_excluded.update({prefix + "DriverGear", prefix + "InputShaft"})
            if "Upper" in bolt.Name:
                service_excluded.add(prefix + "ServoEarLowerNut")
                service_excluded.add(prefix + "ServoEarLowerBolt")
            service_parts = servo_bench_members(module["group"].Document, physical)
            prerequisites = "Remove the paired servo module and selected driver gear/input stub. Turn and withdraw the lower ear screw while its rear nut remains in the shallow hex pocket, then remove that nut. Repeat for the upper pair before withdrawing the complete servo/horn/adapter unit. Keep both horn screw/nut pairs attached until the unit is free."
            matches = [
                row for row in report["input_drive_service"] if row["pod"] == prefix
            ]
            dependencies.append(
                {
                    "check": "input_drive_service",
                    "object": prefix,
                    "passed": len(matches) == 1 and matches[0]["passed"],
                }
            )
        if "OutputBearingKeeper" in bolt.Name:
            prefix = "Port" if bolt.Name.startswith("Port") else "Starboard"
            prior = [
                row
                for row in report["output_carrier_service"]
                if row.get("pod") == prefix
            ]
            service_excluded.update(
                set(prior[0].get("moving_parts", [])) if len(prior) == 1 else set()
            )
            service_excluded.update(
                {prefix + "OutputGear"}
                | {prefix + "OutputShaft" + side for side in ("Negative", "Positive")}
            )
            prerequisites = "Remove the output gear, carrier and both shafts; keep the bearing keeper seated and the rear nut flat between its guides. Turn and withdraw the screw inward first, then release the nut axially beyond the guide height."
            dependencies.append(
                {
                    "check": "output_carrier_service",
                    "object": prefix,
                    "passed": len(prior) == 1 and prior[0]["passed"],
                }
            )
        retained = retained_obstacles(physical, service_excluded, members=service_parts)
        service = fastener_service_check(
            physical[bolt.Name],
            nut,
            retained,
            thread_diameter=thread_diameter,
            retain_bolt=retain_bolt,
            guided_nut=servo_ear or is_guided_nut_bolt(bolt.Name),
            capture_depth_mm=0.5 if servo_ear else guided_nut_capture_depth(bolt.Name),
            nut_lateral_direction=guided_nut_service_direction(
                module["group"].Document, bolt.Name
            ),
        )
        kept_bolts = {bolt.Name} if retain_bolt else set()
        report["fastener_service"].append(
            {
                "bolt": bolt.Name,
                "nut": nut_name,
                "assembly_prerequisites": prerequisites,
                "service_group": service_group,
                "service_dependencies": dependencies,
                "retained_service_parts": sorted(
                    (service_parts - service_excluded) | kept_bolts
                ),
                "removed_local_parts": sorted(service_excluded - kept_bolts),
                **service,
                "passed": service["passed"]
                and all(row["passed"] for row in dependencies),
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
                propulsion.PIVOT_Z + 25.01,
            ),
            2.0,
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
                    coupling.HORN_BOTTOM_Y + coupling.OEM_HEAD_CAVITY_TOP_Y - 0.01,
                    z,
                ),
                (x + 2, coupling.HORN_BOTTOM_Y + coupling.SHAFT_START_Y, z),
                1.5,
            ),
            (
                "driver_shaft_nut_retaining_wall",
                "PortHornGearAdapter",
                tuple(
                    App.Vector(x, coupling.HORN_BOTTOM_Y, z)
                    + coupling.shaft_frame_point(
                        coupling.SHAFT_NUT_SEAT_X + 0.01,
                        coupling.SHAFT_CLAMP_Y + 1.5,
                        0,
                    )
                ),
                tuple(
                    App.Vector(x, coupling.HORN_BOTTOM_Y, z)
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
        report["bridge_joint"].append(bridge_joint_check(doc, module))
        report["servo_module_service"].append(servo_module_service_check(doc, module))
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
