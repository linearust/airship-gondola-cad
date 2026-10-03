"""Two-print, manually locked pitch platform on the unchanged standard rail shoe.

A fixed pivot and off-axis lock cross both lower cheeks. The moving upper lug
contains the arc slot, so both ordinary nuts remain in fixed accessible pockets.
The common plate and all attached instruments share one native pitch stage.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import box, create_group, create_printed_part, set_property, union
from gondola.contracts import equipment_interfaces, fasteners
from gondola.contracts import instrument_mount as spec

from . import mounting_plate, purchased_hardware, rail, stack_interface

V = App.Vector


def _cylinder(radius, length, origin):
    return Part.makeCylinder(radius, length, V(*origin), V(0, 1, 0))


def _finished(shape, name):
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Instrument mount must be one valid solid: " + name)
    return shape


def _capsule(first, second, radius, y, width):
    """Exact constant-radius capsule in XZ, extruded parallel to the hinge."""
    dx, dz = second[0] - first[0], second[1] - first[1]
    length = math.hypot(dx, dz)
    nx, nz = -dz * radius / length, dx * radius / length
    points = [
        V(first[0] + nx, y, first[1] + nz),
        V(second[0] + nx, y, second[1] + nz),
        V(second[0] - nx, y, second[1] - nz),
        V(first[0] - nx, y, first[1] - nz),
    ]
    web = Part.Face(Part.makePolygon(points + [points[0]])).extrude(V(0, width, 0))
    return union(
        [
            web,
            _cylinder(radius, width, (first[0], y, first[1])),
            _cylinder(radius, width, (second[0], y, second[1])),
        ]
    )


def arc_shape(radius, y, width, *, pivot_z=spec.PIVOT_UPPER_MM[2]):
    """Round-ended exact circular arc around the literal lock centre travel."""
    dx, dz = spec.LOCK_OFFSET_XZ_MM
    centre_radius = math.hypot(dx, dz)
    middle = math.atan2(dz, dx)
    half = math.radians(spec.PITCH_LIMIT_DEG)
    low, high = middle - half, middle + half

    def point(r, angle):
        return V(r * math.cos(angle), y, pivot_z + r * math.sin(angle))

    outer, inner = centre_radius + radius, centre_radius - radius
    edges = [
        Part.Arc(point(outer, low), point(outer, middle), point(outer, high)).toShape(),
        Part.makeLine(point(outer, high), point(inner, high)),
        Part.Arc(point(inner, high), point(inner, middle), point(inner, low)).toShape(),
        Part.makeLine(point(inner, low), point(outer, low)),
    ]
    web = Part.Face(Part.Wire(edges)).extrude(V(0, width, 0))
    return union(
        [
            web,
            _cylinder(radius, width, tuple(point(centre_radius, low))),
            _cylinder(radius, width, tuple(point(centre_radius, high))),
        ]
    )


def joint_axes():
    x, _, z = spec.PIVOT_MODULE_MM
    dx, dz = spec.LOCK_OFFSET_XZ_MM
    return {"Pivot": (x, z), "Lock": (x + dx, z + dz)}


def _nut_pocket(x, z):
    shape = purchased_hardware.hex_prism(spec.NUT_POCKET_AF_MM, 2.6)
    shape.rotate(V(), V(1, 0, 0), -90)
    shape.translate(V(x, spec.NUT_BEARING_Y_MM, z))
    return shape


def base_shape():
    """Unchanged shoe below Z12.5, two solid symmetric cheeks above it."""
    pivot, lock = joint_axes().values()
    pieces = [rail.mount_base_shape()]
    # The crosspiece stays above the standard shoe's roof, so it adds no rail
    # contact or rigid span below that datum.
    pieces.append(
        box(19, 2 * spec.CHEEK_OUTER_Y_MM, 3, (-5, -spec.CHEEK_OUTER_Y_MM, 12.5))
    )
    for y in (-spec.CHEEK_OUTER_Y_MM, spec.CHEEK_INNER_Y_MM):
        cheek = union(
            [
                _capsule(pivot, lock, spec.BOSS_RADIUS_MM, y, spec.CHEEK_THICKNESS_MM),
                box(19, spec.CHEEK_THICKNESS_MM, 15, (-5, y, 12.5)),
            ]
        )
        pieces.append(cheek)
    shape = union(pieces)
    for x, z in joint_axes().values():
        shape = shape.cut(_cylinder(spec.BORE_DIAMETER_MM / 2, 20, (x, -10, z)))
        shape = shape.cut(_nut_pocket(x, z))
    return _finished(shape, "lower yoke")


def upper_shape():
    """Same plate datums/openings, with its rotating support entirely below."""
    pz = spec.PIVOT_UPPER_MM[2]
    dx, dz = spec.LOCK_OFFSET_XZ_MM
    width = spec.LUG_WIDTH_MM
    pieces = [
        mounting_plate.shape(),
        _capsule((0, pz), (dx, pz + dz), spec.BOSS_RADIUS_MM, -width / 2, width),
        arc_shape(spec.BOSS_RADIUS_MM, -width / 2, width),
    ]
    # Preserve the same six-mm centre-bore access corridor under the plate.
    for x in (-8, 3):
        pieces.append(box(5, width, 9, (x, -width / 2, 8)))
    shape = union(pieces)
    shape = shape.cut(
        _cylinder(spec.BORE_DIAMETER_MM / 2, width + 2, (0, -width / 2 - 1, pz))
    )
    shape = shape.cut(arc_shape(spec.BORE_DIAMETER_MM / 2, -width / 2 - 1, width + 2))
    # The positive-X spare slot retains its complete Ø4.5x2mm head sweep
    # plus0.4mm clearance. Remove the full lug width so no thin side lips remain;
    # the R9 locking arc retains more than1.8mm material below this simple relief.
    shape = shape.cut(box(7.2, 8.2, 2.4, (8.8, -4.1, 14.6)))
    # Re-cut through the unchanged plate only; every original opening remains.
    for cutter in mounting_plate.cutters(16.99, 2.02):
        shape = shape.cut(cutter)
    return _finished(shape, "upper common plate")


def stage_placement(angle):
    """Rigid upper-local -> module transform about its own Y-axis datum."""
    if not math.isfinite(float(angle)):
        raise ValueError("Instrument pitch must be finite")
    angle = max(-spec.PITCH_LIMIT_DEG, min(spec.PITCH_LIMIT_DEG, float(angle)))
    rotation = App.Rotation(V(0, 1, 0), angle)
    return App.Placement(
        V(*spec.PIVOT_MODULE_MM) - rotation.multVec(V(*spec.PIVOT_UPPER_MM)), rotation
    )


def screw_shape():
    return union(
        [
            Part.makeCylinder(3, 2, V(0, 0, -2)),
            Part.makeCylinder(1.5, spec.SCREW_LENGTH_MM),
        ]
    )


def nut_shape():
    return (
        purchased_hardware.hex_prism(5.5, 2.4)
        .cut(Part.makeCylinder(1.5, 2.6, V(0, 0, -0.1)))
        .removeSplitter()
    )


def hardware_shapes():
    """Installed fixed-axis M3 envelopes, independent of the moving plate."""
    result = {}
    for joint, (x, z) in joint_axes().items():
        for kind, shape, y in (
            ("Bolt", screw_shape(), -spec.CHEEK_OUTER_Y_MM),
            ("Nut", nut_shape(), spec.NUT_BEARING_Y_MM),
        ):
            shape.rotate(V(), V(1, 0, 0), -90)
            shape.translate(V(x, y, z))
            result[joint + kind] = shape
    return result


def mount_contract():
    return {
        "mechanism": "Setup-only common instrument plate with fixed pivot and off-axis arc-slot clamp",
        "axis": "Module-local Y",
        "angle_limit_deg": spec.PITCH_LIMIT_DEG,
        "pivot_module_mm": spec.PIVOT_MODULE_MM,
        "pivot_upper_mm": spec.PIVOT_UPPER_MM,
        "fixed_lock_axis_module_mm": (9.0, 0.0, 27.5),
        "positive_x_spare_slot_head_relief_mm": {
            "minimum_x": 8.8,
            "floor_z": 14.6,
            "head_clearance": 0.4,
            "arc_slot_minimum_web": 1.5,
        },
        "common_plate_local_z_mm": (17.0, 19.0),
        "neutral_plate_module_z_mm": (36.5, 38.5),
        "lug_width_mm": spec.LUG_WIDTH_MM,
        "total_face_fit_reserve_mm": spec.FACE_FIT_RESERVE_MM,
        "cheek_thickness_mm": spec.CHEEK_THICKNESS_MM,
        "nut_pocket_af_mm": spec.NUT_POCKET_AF_MM,
        "nut_floor_mm": spec.CHEEK_THICKNESS_MM - spec.NUT_POCKET_DEPTH_MM,
        "nominal_grip_mm": spec.CHEEK_OUTER_Y_MM + spec.NUT_BEARING_Y_MM,
        "nominal_tip_beyond_nut_mm": spec.SCREW_LENGTH_MM
        - spec.CHEEK_OUTER_Y_MM
        - spec.NUT_BEARING_Y_MM
        - 2.4,
        "hardware": "Two M3x16 button-head screws and ordinary M3 nuts, in addition to the unchanged M3x10 rail clamp. No washers or bearings.",
        "fit": "0.2 mm total nominal side-face reserve permits free insertion before finishing. Fit the broad opposing lug/cheek faces freely, then clamp both joints with faces seated. Do not force an oversized print into the yoke, leave operating side play, or assume the stated reserve proves an acceptable elastic deflection or preload. Trial actual nuts in the open outer pockets; antirotation and retention need physical checks.",
        "assembly": "Support the instruments. Place the upper lug between the yoke cheeks, insert both M3 screws from negative Y and ordinary nuts freely from positive Y. Loosen both joints for setup, align, then tighten both while maintaining contact. Remove the nuts and withdraw both screws before lifting the complete upper assembly. Disconnect leads first.",
        "qualification": "Nominal single-axis setup mechanism, not automatic or in-flight levelling. Native limits are planning controls, not physical angle stops. Printed stiffness, clamp friction, creep, vibration, actual FC damper compliance and the measured IMU/sensor transform remain unqualified.",
        "holding_torque_verified": False,
        "self_levelling": False,
        "physical_angle_stops_modeled": False,
    }


def build_mount(doc, electronics_module):
    """Build two prints and four purchased parts beneath one native pitch stage."""
    from . import equipment_mounts

    notes = mount_contract()
    encoded = json.dumps(notes, sort_keys=True)
    set_property(electronics_module, "InstrumentMountContract", encoded)
    stage = create_group(doc, "InstrumentPitchStage", "Instrument setup pitch | Y axis")
    electronics_module.addObject(stage)
    stage.Placement = App.Placement(V(), App.Rotation(V(0, 1, 0), 1))
    for name, value in (("Pitch", 0), ("MinimumAngle", -20), ("MaximumAngle", 20)):
        set_property(stage, name, value, "App::PropertyAngle", "Manual adjustment")
    stage.setEditorMode("MinimumAngle", 1)
    stage.setEditorMode("MaximumAngle", 1)
    bounded = "min(MaximumAngle; max(MinimumAngle; Pitch))"
    stage.setExpression("Placement.Rotation.Angle", bounded)
    stage.setExpression("Placement.Base.x", "-8 mm * sin(" + bounded + ")")
    stage.setExpression("Placement.Base.z", "27.5 mm - 8 mm * cos(" + bounded + ")")
    lower = create_printed_part(
        doc,
        electronics_module,
        "InstrumentMountBase",
        "PRINT | Instrument rail shoe and yoke",
        base_shape(),
        App.Rotation(),
        notes["fit"],
    )
    upper = create_printed_part(
        doc,
        stage,
        "ElectronicsMount",
        "PRINT | Common instrument pitch plate",
        upper_shape(),
        equipment_mounts.PRINT_ROTATION,
        notes["qualification"],
    )
    for obj, sku in ((lower, spec.LOWER_SKU), (upper, spec.UPPER_SKU)):
        set_property(obj, "PrintSKU", sku)
        set_property(obj, "InstrumentMountContract", encoded)
        set_property(obj, "HoldingTorqueVerified", False, "App::PropertyBool")
    set_property(upper, "Role", "Printed equipment carrier")
    set_property(upper, "MountKind", "electronics")
    stack_interface.annotate_interface(upper, "ElectronicsMount")
    set_property(
        upper,
        "MountContract",
        json.dumps(equipment_mounts.mount_contract("electronics"), sort_keys=True),
    )
    set_property(upper, "HalfTurnSymmetric", False, "App::PropertyBool")
    set_property(upper, "MountingStackVerified", False, "App::PropertyBool")
    set_property(upper, "EquipmentFaceZ", 19, "App::PropertyLength")
    set_property(upper, "SourceURL", equipment_interfaces.FC_SOURCE)
    set_property(
        upper,
        "MountingEvidence",
        json.dumps(equipment_interfaces.MOUNTING_EVIDENCE, sort_keys=True),
    )
    set_property(
        upper,
        "MountHoleCentres",
        [V(x, y, 17) for x, y in mounting_plate.FC_HOLE_CENTRES],
        "App::PropertyVectorList",
    )
    set_property(upper, "MountHoleDiameter", 2.6, "App::PropertyLength")
    hardware = []
    for suffix, shape in hardware_shapes().items():
        bolt = suffix.endswith("Bolt")
        hardware.append(
            purchased_hardware.add_hardware(
                doc,
                electronics_module,
                "Instrument" + suffix,
                "BUY | instrument " + suffix,
                shape,
                spec.SCREW_SKU if bolt else spec.NUT_SKU,
                notes["hardware"] + " " + notes["fit"],
                fasteners.RAIL_FASTENER_SOURCE,
                fasteners.RAIL_FASTENER_MATERIAL,
                thread_diameter=3,
                thread_pitch=0.5,
            )
        )
    doc.recompute()
    return {
        "group": electronics_module,
        "pitch_stage": stage,
        "lower": lower,
        "upper": upper,
        "printed": [lower, upper],
        "hardware": hardware,
    }


def set_pitch(doc, angle):
    """Set setup pitch; native expressions clamp the finite command to ±20°."""
    if not math.isfinite(float(angle)):
        raise ValueError("Instrument pitch must be finite")
    doc.InstrumentPitchStage.Pitch = float(angle)
    doc.recompute()
