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

TOL = 1e-5


def _positive_module_shapes(doc, prefix, objects):
    """Normalize actual placements to module coordinates, +Y toward this rotor."""
    inverse = doc.MainPropulsionModule.getGlobalPlacement().inverse()
    shapes = []
    for obj in objects:
        shape = world_shape(obj)
        shape.Placement = inverse.multiply(shape.Placement)
        if prefix == "Starboard":
            shape = shape.mirror(App.Vector(), App.Vector(0, 1, 0))
        shapes.append(shape)
    return shapes


def output_bearing_stack_check(doc, prefix, suffix, axial_stops=None):
    """Check each real split-housing bearing and both cap fasteners."""
    shaft_suffix = "Negative" if prefix == "Port" else "Positive"
    names = [
        prefix + "OutputBearing" + suffix,
        prefix + "OutputShaft" + shaft_suffix,
        "PropulsionFixedFrame",
        prefix + "BearingCap",
    ]
    fastener_names = [
        prefix + "BearingCap" + side + kind
        for side in ("Negative", "Positive")
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
        for index in (0, 2)
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


def carrier_shaft_retention_check(doc, prefix):
    """Prove the D socket and radial jack geometry of the one driven rotor shaft."""
    from gondola.contracts import fasteners
    from gondola.parts import purchased_hardware as hardware

    from .motion_clearance import _in_pod_coordinates

    pod = doc.getObject(prefix + "Pod")
    side = "Negative" if prefix == "Port" else "Positive"
    names = [
        _output_shaft_name(prefix),
        prefix + "MotorCarrier",
        prefix + "OutputClamp" + side + "Bolt",
        prefix + "OutputClamp" + side + "Nut",
    ]
    objects = [doc.getObject(name) for name in names]
    if pod is None or any(obj is None for obj in objects):
        return {
            "pod": prefix,
            "passed": False,
            "error": "Missing output jack component",
        }
    shapes = [_in_pod_coordinates(obj, pod) for obj in objects]
    if prefix == "Starboard":
        shapes = [shape.mirror(App.Vector(), App.Vector(0, 1, 0)) for shape in shapes]
    shaft, carrier, bolt, nut = shapes
    expected = Part.makeCylinder(1.5, 42, App.Vector(0, -62, 0), App.Vector(0, 1, 0))
    for start, length in ((-62, 5), (-31, 11)):
        expected = expected.cut(Part.makeBox(3, length, 4, App.Vector(1, start, -2)))
    missing = abs(expected.cut(shaft).Volume)
    extra = abs(shaft.cut(expected).Volume)
    socket = Part.makeBox(4, 10, 4, App.Vector(-2, -30.5, -2))
    grip = expected.common(socket)
    missing_grip = abs(grip.cut(shaft).Volume)
    tip_contact = _planar_contact_area(bolt, shaft)
    head = bolt.common(Part.makeBox(4, 6, 6, App.Vector(13, -28.5, -3)))
    head_gap = head.distToShape(carrier)[0] if head.Solids else -1
    wall = Part.Face(
        Part.makePolygon(
            [
                App.Vector(8, y, z)
                for y, z in (
                    (-28.5, -3),
                    (-22.5, -3),
                    (-22.5, 3),
                    (-28.5, 3),
                    (-28.5, -3),
                )
            ]
        )
    ).common(carrier)
    nut_contact = _planar_contact_area(nut, wall)
    thread_core = Part.makeCylinder(
        0.8, 1.6, App.Vector(6.4, -25.5, 0), App.Vector(1, 0, 0)
    )
    missing_thread = abs(thread_core.cut(bolt).Volume)
    support = Part.makeLine(App.Vector(-1.5, -30.4, 0), App.Vector(-1.5, -20.6, 0))
    reaction = support.common(carrier).common(shaft).Length
    shifted = translated_shape(shaft, x=-0.01)
    radial_block = intersection_volume(shifted, carrier)
    key_rows = []
    for angle in (-15, 15):
        rotated = shaft.copy()
        rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
        penetration = intersection_volume(rotated, carrier)
        key_rows.append(
            {
                "attempted_rotation_deg": angle,
                "key_probe_penetration_mm3": penetration,
                "passed": penetration > 0.001,
            }
        )
    minimum_nut = hardware.hex_prism(
        fasteners.HEX_NUT_MIN_AF, fasteners.HEX_NUT_MIN_HEIGHT
    ).cut(
        Part.makeCylinder(1, fasteners.HEX_NUT_MIN_HEIGHT + 0.2, App.Vector(0, 0, -0.1))
    )
    minimum_nut.Placement = App.Placement(
        App.Vector(8, -25.5, 0), App.Rotation(App.Vector(0, 0, 1), App.Vector(-1, 0, 0))
    )
    neutral_nut = intersection_volume(minimum_nut, carrier)
    minimum_contact = _planar_contact_area(minimum_nut, wall)
    nut_blocks = []
    for angle in (-30, 30):
        probe = minimum_nut.copy()
        probe.rotate(App.Vector(8, -25.5, 0), App.Vector(1, 0, 0), angle)
        nut_blocks.append(intersection_volume(probe, carrier))
    overlaps = {
        "shaft_carrier_overlap_mm3": intersection_volume(shaft, carrier),
        "bolt_carrier_overlap_mm3": intersection_volume(bolt, carrier),
        "bolt_shaft_overlap_mm3": intersection_volume(bolt, shaft),
        "nut_carrier_overlap_mm3": intersection_volume(nut, carrier),
        "bolt_nut_overlap_mm3": intersection_volume(bolt, nut),
    }
    return {
        "pod": prefix,
        "shaft": names[0],
        "shaft_length_mm": 42.0,
        "gear_flat_length_mm": 5.0,
        "carrier_flat_length_mm": 11.0,
        "socket_engagement_mm": 10.0,
        "missing_nominal_shaft_mm3": missing,
        "extra_shaft_material_mm3": extra,
        "missing_socket_engagement_mm3": missing_grip,
        "screw_tip_to_flat_contact_mm2": tip_contact,
        "nut_to_retaining_wall_contact_mm2": nut_contact,
        "missing_bolt_thread_core_mm3": missing_thread,
        "screw_head_to_carrier_gap_mm": head_gap,
        "centred_reaction_contact_length_mm": reaction,
        "jack_direction_probe_penetration_mm3": radial_block,
        "key_checks": key_rows,
        "minimum_nut_capture": {
            "neutral_pocket_overlap_mm3": neutral_nut,
            "retaining_wall_contact_mm2": minimum_contact,
            "rotation_stop_penetration_mm3": nut_blocks,
        },
        **overlaps,
        "scope": "Literal42mm bought Ø3 rod with5mm gear-end and11mm carrier-end flats,10mm D socket, M2x12 radial jack and captive ordinary nut. The screw tip must contact the flat while its head stays free, and the opposite circular journal reacts without lateral take-up. The D key provides nominal torsional interference; axial grip still depends on jack friction and the purchased gear set screw. No printed strength, shaft bending, clamp preload or physical retention certification.",
        "passed": missing < TOL
        and extra < TOL
        and missing_grip < TOL
        and grip.Volume > 1
        and tip_contact > 1
        and nut_contact > 1
        and missing_thread < TOL
        and head_gap >= 0.5 - TOL
        and abs(reaction - 9.8) < TOL
        and radial_block > 0.01
        and all(row["passed"] for row in key_rows)
        and neutral_nut < TOL
        and minimum_contact > 1
        and min(nut_blocks) > TOL
        and all(value < TOL for value in overlaps.values()),
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
        "scope": "Selected bought Ø3 bore remains unchanged. The20mm metal D stub spans the full8mm driver and projects4mm beyond it for side-grip removal; this is a metal-length reserve, not a qualified axial adjustment range or arbitrary-gear compatibility. The printed adapter stays outside the bore. The unmodified manufacturer X06 half arm1 uses M1 hex bolts and front nuts through the existing nominalØ1 holes at6.8/13.2mm. Physical no-drill slip fit remains unverified; do not force threads through the plastic. The adapter also offers an optional10mm slot, not a qualified three-bolt assembly. The open C register and flat face limit misalignment; the nominal STEP fixes the hole positions and root geometry, while installed seating, delivered concentricity and runout remain unmeasured. Finish the local register against the received horn and check final runout. Horn strength, clamp preload, stainless rod quality, gear set screw and servo radial-load capacity remain physical checks.",
        "passed": specification.bore_mm == coupling.GEAR_BORE_DIAMETER
        and specification.total_length_mm == coupling.GEAR_LENGTH
        and bore_intrusion < TOL
        and missing_hub < TOL
        and adapter_in_gear_bore < TOL
        and gear_journal.Volume > TOL
        and missing_gear_engagement < TOL
        and abs(projection - 4) < TOL
        and reserve.Volume > TOL
        and missing_reserve < TOL
        and retention["passed"]
        and registration["passed"]
        and all(row["intersection_mm3"] < TOL for row in rows)
        and all(area > 1 for area in capture.values()),
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
    foot = Part.makeBox(16.7, 5, 5, App.Vector(6, -10.5, 24.5))
    other_foot = foot.copy()
    other_foot.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
    connections = {"port_foot": foot, "starboard_foot": other_foot}
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
        "scope": "Independent closed rectangular wall stock and7.4x20.4 case window, excluding literal ear slots opening into the window and shallow nut seats. Both3mm walls and two16.7x5x5 local feet are required. The feet overlap the main18mm beam by3mm. The space between the frames stays empty above the beam. Nominal case clearance is0.2mm per face; finish tight prints and never force case compression. Installed ear joints locate and clamp the servo. Closed stock does not qualify torsional stiffness or strength.",
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
        for x in (-5.5, 5.5):
            bed = bed.cut(Part.makeCylinder(1.1, 3, App.Vector(x, sign * 34.5, 42)))
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


def _output_shaft_name(prefix):
    return prefix + "OutputShaft" + ("Negative" if prefix == "Port" else "Positive")


def _record_output_stub_checks(report, prefix, pod, physical, frame):
    """Check each shaft's motor separation and outward whole-rotor route."""
    shaft_name = _output_shaft_name(prefix)
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
    gear, shaft = prefix + "OutputGear", _output_shaft_name(prefix)
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
    future_obstacle = {"replacement_rotor_bulk": moving}
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
                Part.makeBox(15, 3.8, height, App.Vector(14.5, 22.7, z))
                for z, height in ((47, 1.6), (51.5, 1.5))
            ]
        )
        if grip_sign < 0:
            jaws.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
        points = [(grip_sign * 60, 0, 0), *input_shaft_service_waypoints(side)]
        grip_tools.append(
            {
                "pod": side,
                "waypoints_mm": points,
                "scope": "Literal side-entry jaw envelope from the checked shaft-first service route. The lower jaw includes0.1mm closure toward the clocked D-flat; actual hand tools and grip are unqualified.",
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
        "input_grip_tools_past_future_bulk": grip_tools,
        "scope": "Continuous enclosing cylinder for a future replacement rotor bulk, including measured current axial stops. The inboard housing, every retained physical propulsion part, outward rotor Y60 and separate input-service stages are checked. Each input shaft moves18mm outward inY then60mm outward inX; its released driver moves60mm outward inX. After ear hardware release, the remaining servo/horn/adapter moves14mm outward inY then60mm outward inX. The future bulk is58mm wide; the separate shaft and root thrust interfaces lie outside this bulk. The present40mm guard and return arm do not accept a50mm propeller. Replacement shaft/clamp interfaces, assembly strength, future motor/propeller hardware and wiring still require design and tests; this is a space reservation only.",
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
        shapes = {
            name: shape.mirror(App.Vector(), App.Vector(0, 1, 0))
            for name, shape in shapes.items()
        }
    staged = retained_obstacles(shapes, set(carrier_service.get("removed_parts", [])))
    cap_name = prefix + "BearingCap"
    pairs = [
        (cap_name + side + "Bolt", cap_name + side + "Nut")
        for side in ("Negative", "Positive")
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
                nut_lateral_direction=(-1 if "Negative" in bolt else 1, 0, 0),
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
                and len(release) == 2
                and all(row["passed"] for row in release)
                and cap_path["passed"]
                and path["passed"],
            }
        )
        staged.pop(name, None)


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
            "scope": "After output-gear unmeshing, loosen the input jack and bought driver set screw, support the driver and withdraw its shaft18mm axially then60mm outward inX. Only then remove the loose driver60mm outward inX. The servo/horn/adapter, fixed frame, bearings and rotors remain installed for this stage. Actual set-screw and handling access remain physical checks.",
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
            prerequisite = "Remove both small output gears. Withdraw the lower ear screw and release its shallow-pocket nut, then the upper pair. The whole servo input unit and integrated frame remain installed until both pairs are free."
        else:
            prior = [
                row
                for row in report["bearing_service"]
                if row["bearing"] == prefix + "OutputBearingInboard"
            ]
            rows = prior[0].get("fastener_release", []) if len(prior) == 1 else []
            dependency = "bearing_service"
            prerequisite = "Remove the selected output gear and withdraw its rotor/shaft outward. Hold each side-entry cap nut, withdraw the cap bolt upward, then move the unthreaded nut0.2mm down and outward alongX. Release the negativeX pair before the positiveX pair."
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
