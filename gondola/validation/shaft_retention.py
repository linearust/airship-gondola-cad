"""Input and output shaft seating, keyed engagement and radial jack evidence.

Measure the saved assembly, including the horn/gear interface. Geometric contact
and interference checks do not qualify physical fits, preload or loaded strength.
"""

import FreeCAD as App
import Part

from gondola.cad import translated_shape, world_shape
from gondola.contracts.drive import drive_for_document

from .geometry import TOL, intersection_volume, planar_contact_area
from .horn_coupling import coupling_frame, horn_registration_check


def output_shaft_name(prefix):
    """Name the single driven shaft on the inboard side of each rotor."""
    return prefix + "OutputShaft" + ("Negative" if prefix == "Port" else "Positive")


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
    tip_contact = planar_contact_area(screw, shaft)
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
    nut_wall_contact = planar_contact_area(nut, retaining_wall)
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
    minimum_nut_contact = planar_contact_area(placed_minimum_nut, retaining_wall)
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
    stop_contact = planar_contact_area(shaft, adapter)
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
        output_shaft_name(prefix),
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
    tip_contact = planar_contact_area(bolt, shaft)
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
    nut_contact = planar_contact_area(nut, wall)
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
    minimum_contact = planar_contact_area(minimum_nut, wall)
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
        name: planar_contact_area(parts["ServoHorn"], parts[name])
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
        "scope": "Selected bought Ø3 bore remains unchanged. The35mm metal stub has a16mm proximal flat and a round distal journal. It spans the full8mm driver and projects19mm beyond it through the external bearing; this is a metal-length reserve, not a qualified axial adjustment range or arbitrary-gear compatibility. The printed adapter stays outside the bore. The unmodified manufacturer X06 half arm1 uses M1 hex bolts and front nuts through the existing nominalØ1 holes at6.8/13.2mm. Physical no-drill slip fit remains unverified; do not force threads through the plastic. The adapter also offers an optional10mm slot, not a qualified three-bolt assembly. The open C register and flat face limit misalignment; the nominal STEP fixes the hole positions and root geometry, while installed seating, delivered concentricity and runout remain unmeasured. Finish the local register against the received horn and check final runout. Horn strength, clamp preload, stainless rod quality, gear set screw and servo radial-load capacity remain physical checks.",
        "passed": specification.bore_mm == coupling.GEAR_BORE_DIAMETER
        and specification.total_length_mm == coupling.GEAR_LENGTH
        and bore_intrusion < TOL
        and missing_hub < TOL
        and adapter_in_gear_bore < TOL
        and gear_journal.Volume > TOL
        and missing_gear_engagement < TOL
        and abs(projection - 19) < TOL
        and reserve.Volume > TOL
        and missing_reserve < TOL
        and retention["passed"]
        and registration["passed"]
        and all(row["intersection_mm3"] < TOL for row in rows)
        and all(area > 1 for area in capture.values()),
    }
