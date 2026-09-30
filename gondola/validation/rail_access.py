"""Side access and populated lift-off service for the slotted rail.

Every other module stays installed. Rigid paths do not qualify real tools,
flexible leads, curved installation, clamp preload or adhesive loading.
"""

from collections import Counter

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, union, world_shape
from gondola.contracts.design import MODULE_STATIONS
from gondola.parts import rail

from .baseline import module_attachment_pose, module_control_bindings
from .geometry import TOL
from .propulsion_service import continuous_path

V = App.Vector


def side_driver_clearance(screw, obstacles):
    """Local -Y approach, including the stem, handle and full insertion path."""
    bounds = screw.BoundBox
    origin = V(bounds.Center.x, bounds.YMin - 0.1, bounds.Center.z)
    tool = union(
        [
            Part.makeCylinder(2, 140, origin, V(0, -1, 0)),
            Part.makeCylinder(6, 40, origin + V(0, -140, 0), V(0, -1, 0)),
        ]
    )
    return {
        **continuous_path(tool, [(0, -25, 0), (0, 0, 0)], obstacles),
        "driver_stem_diameter_mm": 4.0,
        "handle_diameter_mm": 12.0,
        "scope": "Straight tool acceptance envelope, ending0.1mm before the solid head. Actual socket/bit and hand fit remain unverified.",
    }


def nut_capture_check(x, nut, guard):
    """The saved hex window admits the nut axially and blocks continuous rotation.

    Only guard material around the nut is considered. Axial clamping support
    belongs to the rail web and is checked separately by attachment_check.
    """
    region = Part.makeBox(8, 2.5, 8, V(x - 4, 1.45, 3))
    retaining_guard = guard.common(region)
    nominal = abs(nut.common(retaining_guard).Volume)
    turns = []
    for angle in (-30, 30):
        rotated = nut.copy()
        rotated.rotate(V(x, 0, 7), V(0, 1, 0), angle)
        blocked = abs(rotated.common(retaining_guard).Volume)
        turns.append({"rotation_deg": angle, "rotation_block_mm3": blocked})
    return {
        "nominal_nut_to_guard_overlap_mm3": nominal,
        "rotation_limits": turns,
        "external_holding_wrench_required": False,
        "nut_axial_clamping_surface": "Rail web at Y=1.25 mm; guard carries no axial preload.",
        "scope": "Nominal saved hex-window anti-rotation geometry. The nut remains removable in +Y; actual nut fit, corner clearance, printed-wall torque capacity and wear require inspection.",
        "passed": nominal < TOL
        and all(row["rotation_block_mm3"] > 0.1 for row in turns),
    }


def _lift_path(name, shape, obstacles, offset):
    """Keep the U opening in the only region that can initially contact rail."""
    bounds = shape.BoundBox
    mount_names = {
        "BatteryMount",
        "ElectronicsMount",
        "AccessoryMount",
        "PropulsionFixedFrame",
        "ServoDriveBridge",
    }
    if name not in mount_names or bounds.ZMin >= rail.MOUNT_TOP_Z - TOL:
        pieces = [(name, shape)]
    else:
        low_region = Part.makeBox(
            bounds.XLength + 2,
            bounds.YLength + 2,
            rail.MOUNT_TOP_Z - bounds.ZMin + 1,
            V(bounds.XMin - 1, bounds.YMin - 1, bounds.ZMin - 1),
        )
        lower, upper = shape.common(low_region), shape.cut(low_region)
        # Bound the transverse bore by a small rectangular plug outside the web,
        # preserving the open U profile. Include the larger head counterbore;
        # the locating key lies away from this filled region.
        from gondola.parts import servo_bridge

        if name == "ServoDriveBridge":
            bore_start, bore_length = (
                servo_bridge.CHEEK_OUTER_Y,
                servo_bridge.CHEEK_THICKNESS,
            )
        else:
            bore_start, bore_length = rail.MOUNT_OUTER_Y, rail.MOUNT_LEG_THICKNESS
        fill = Part.makeBox(
            rail.HEAD_RECESS_DIAMETER,
            bore_length,
            rail.HEAD_RECESS_DIAMETER,
            V(
                offset - rail.HEAD_RECESS_DIAMETER / 2,
                bore_start,
                rail.BOLT_AXIS_Z - rail.HEAD_RECESS_DIAMETER / 2,
            ),
        )
        lower = lower.fuse(fill).removeSplitter()
        pieces = [(name + "Lower", lower), (name + "Upper", upper)]
    rows = [
        {"region": label, **continuous_path(part, [(0, 0, 0), (0, 0, 30)], obstacles)}
        for label, part in pieces
        if part.Solids and abs(part.Volume) > TOL
    ]
    return {
        "part": name,
        "regions": rows,
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }


def _service_inventory(doc, registry, objects):
    """Reject omitted neighbours, duplicates and look-alike objects before paths."""
    expected = [
        obj
        for name in (
            "PrintedParts",
            "ReferenceParts",
            "HardwareParts",
            "TapeReferences",
        )
        for obj in getattr(registry, name)
    ]
    expected_counts = Counter(obj.Name for obj in expected)
    supplied_counts = Counter(obj.Name for obj in objects)
    duplicates = sorted(name for name, count in supplied_counts.items() if count != 1)
    registry_duplicates = sorted(
        name for name, count in expected_counts.items() if count != 1
    )
    missing = sorted(expected_counts.keys() - supplied_counts.keys())
    extra = sorted(supplied_counts.keys() - expected_counts.keys())
    identities = all(obj is doc.getObject(obj.Name) for obj in expected + list(objects))
    return {
        "missing_registered_obstacles": missing,
        "unexpected_objects": extra,
        "duplicate_objects": duplicates,
        "duplicate_registry_objects": registry_duplicates,
        "native_identities_match": identities,
        "passed": identities
        and not (missing or extra or duplicates or registry_duplicates),
    }


def _saved_stage_settings(doc):
    """Record manual values and actual saved rotations without claiming neutral."""
    rows = {}
    for name, control in (
        ("PortPod", "Tilt"),
        ("StarboardPod", "Tilt"),
        ("OpticalPitchStage", "Pitch"),
    ):
        stage = doc.getObject(name)
        if stage is not None:
            rows[name] = {
                "control": control,
                "commanded_angle_deg": float(getattr(stage, control)),
                "actual_local_rotation_quaternion_xyzw": list(
                    stage.Placement.Rotation.Q
                ),
            }
    return rows


def rail_attachment_service(doc, registry, objects):
    """Check each populated module independently, with all neighbours present."""
    objects = list(objects)
    inventory = _service_inventory(doc, registry, objects)
    if not inventory["passed"]:
        return {
            "passed": False,
            "obstacle_inventory": inventory,
            "error": "Service obstacle inventory mismatch",
        }
    try:
        bindings = module_control_bindings(doc)
    except (AttributeError, ValueError) as error:
        return {"passed": False, "error": str(error)}
    world = {obj.Name: world_shape(obj) for obj in objects}
    rows = []
    for station, module in bindings:
        pose = module_attachment_pose(station, module)
        members = {obj.Name for obj in objects if belongs_to_group(obj, module)}
        attachment_names = [
            obj.Name for obj in registry.RailLocks if belongs_to_group(obj, module)
        ]
        attachments = set(attachment_names)
        screw_name, nut_name = (
            module.Name + "RailMountScrew",
            module.Name + "RailMountNut",
        )
        if len(attachment_names) != 2 or attachments != {screw_name, nut_name}:
            rows.append(
                {
                    "module": module.Name,
                    "passed": False,
                    "error": "Rail attachment inventory mismatch",
                }
            )
            continue
        inverse = module.getGlobalPlacement().inverse()
        shapes = {name: shape.copy() for name, shape in world.items()}
        for shape in shapes.values():
            shape.Placement = inverse.multiply(shape.Placement)
        screw, nut = shapes[screw_name], shapes[nut_name]
        offset = float(module.RailAttachmentOffsetX)
        bolt_obstacles = {
            name: shape for name, shape in shapes.items() if name != screw_name
        }
        driver = side_driver_clearance(screw, bolt_obstacles)
        mount_name = {
            "BatteryEquipmentModule": "BatteryMount",
            "ElectronicsEquipmentModule": "ElectronicsMount",
            "AccessoryEquipmentModule": "AccessoryMount",
            "MainPropulsionModule": "PropulsionFixedFrame",
        }[module.Name]
        nut_capture = nut_capture_check(offset, nut, shapes[mount_name])
        withdrawal = continuous_path(screw, [(0, 0, 0), (0, -15, 0)], bolt_obstacles)
        after_bolt = {
            name: shape for name, shape in shapes.items() if name not in attachments
        }
        nut_path = continuous_path(nut, [(0, 0, 0), (0, 4, 0), (25, 4, 0)], after_bolt)
        moving = members - attachments
        fixed = {name: shape for name, shape in shapes.items() if name not in members}
        lifts = [
            _lift_path(name, shapes[name], fixed, offset) for name in sorted(moving)
        ]
        rows.append(
            {
                "module": module.Name,
                "native_attachment_pose": pose,
                "shared_servo_bridge_clamp": module.Name == "MainPropulsionModule",
                "covering_devices_removed": [],
                "other_modules_removed": [],
                "side_driver_access": driver,
                "nut_window_anti_rotation": nut_capture,
                "rail_screw_withdrawal": withdrawal,
                "nut_removal_after_screw": nut_path,
                "populated_module_lift": lifts,
                "passed": pose["passed"]
                and driver["passed"]
                and nut_capture["passed"]
                and withdrawal["passed"]
                and nut_path["passed"]
                and bool(lifts)
                and all(row["passed"] for row in lifts),
            }
        )
    return {
        "modules": rows,
        "obstacle_inventory": inventory,
        "saved_stage_settings": _saved_stage_settings(doc),
        "scope": "Each populated module is checked at its saved configuration and recorded stage settings, with every other registered physical part installed. These paths do not certify other angles or positions. The through-hex window restrains nut rotation. Withdraw the transverse screw completely, slide the nut out in +Y, then lift30mm. No covering board, battery or servo bridge removal. Support frame and bridge together when their shared propulsion clamp is loose; the lift treats them as a held assembly, not as self-retaining. Disconnect/release flexible leads and external retention before lifting. Continuous rigid envelopes, including full screw head and specified tools, do not qualify hands, supplied bit/nut-window fit, curved rail, wiring, friction, PA12 creep or adhesive strength. Local slot travel does not imply every alternative module position is collision-free; revalidate after moving.",
        "passed": len(rows) == len(MODULE_STATIONS)
        and all(row["passed"] for row in rows),
    }
