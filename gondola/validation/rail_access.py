"""Side access and populated lift-off service for the slotted rail.

Every other module stays installed. Rigid paths do not qualify real tools,
flexible leads, curved installation, clamp preload or adhesive loading.
"""

import math
from collections import Counter

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, placed_shape, union, world_shape
from gondola.contracts.design import MODULE_STATIONS
from gondola.parts import rail

from .baseline import module_attachment_pose, module_control_bindings
from .geometry import TOL, translation_sweep
from .propulsion_service import continuous_path
from .rail_interface import attachment_sites, mount_binding, site_placement

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


def _rail_hex_nut(across_flats, height, x, seat):
    """Literal ordinary-M3 envelope independent of the production nut builder."""
    radius = across_flats / math.sqrt(3)
    points = [
        V(
            x + radius * math.cos(i * math.pi / 3 + math.pi / 6),
            seat,
            6 + radius * math.sin(i * math.pi / 3 + math.pi / 6),
        )
        for i in range(6)
    ]
    return Part.Face(Part.makePolygon(points + points[:1])).extrude(V(0, height, 0))


def standard_nut_clearance_check(x, support, seat):
    """Free axial insertion and rotation stops across ordinary-M3 envelopes.

    Dimensions span DIN934 AF5.32..5.50 and height2.15..2.40. No flange,
    prevailing-torque nut, chamfer engagement or as-printed fit claim.
    """
    offsets = [(0.0, 0.0)] + [
        (0.2 * math.cos(i * math.pi / 4), 0.2 * math.sin(i * math.pi / 4))
        for i in range(8)
    ]
    rows = []
    for dx, dz in offsets:
        large = _rail_hex_nut(5.5, 2.4, x + dx, seat)
        large.translate(V(0, 0, dz))
        swept, method = translation_sweep(large, (0, 10, 0))
        collision = abs(swept.common(support).Volume)
        stops = []
        for angle in (-30, 30):
            small = _rail_hex_nut(5.32, 2.15, x, seat)
            small.rotate(V(x, seat, 6), V(0, 1, 0), angle)
            small.translate(V(dx, 0, dz))
            stops.append(abs(small.common(support).Volume))
        rows.append(
            {
                "axis_offset_xz_mm": [dx, dz],
                "maximum_nut_service_overlap_mm3": collision,
                "minimum_nut_rotation_block_mm3": stops,
                "method": method,
                "passed": collision < TOL and min(stops) > TOL,
            }
        )
    return {
        "cases": rows,
        "nut_af_range_mm": [5.32, 5.5],
        "nut_height_range_mm": [2.15, 2.4],
        "nominal_axis_float_radius_mm": 0.2,
        "scope": "Sharp hex and sampled transverse offsets/rotation; actual chamfer and free seating require coupon inspection. Clearance does not imply operating looseness after clamping.",
        "passed": all(row["passed"] for row in rows),
    }


def nut_capture_check(x, nut, support, *, shared=False):
    """Independent saved open-bottom recess floor and anti-rotation checks."""
    inner, seat, outer = (6.0, 8.0, 11.0) if shared else (1.25, 3.25, 5.25)
    region = Part.makeBox(8, outer - seat, 8, V(x - 4, seat, 2))
    pocket_wall = support.common(region)
    nominal = abs(nut.common(support).Volume)
    floor = Part.makeCylinder(2.75, 2, V(x, inner, 6), V(0, 1, 0)).cut(
        Part.makeCylinder(1.7, 2, V(x, inner, 6), V(0, 1, 0))
    )
    missing_floor = abs(floor.cut(support).Volume)
    seated = abs(nut.BoundBox.YMin - seat) < TOL
    turns = []
    for angle in (-30, 30):
        rotated = nut.copy()
        rotated.rotate(V(x, 0, 6), V(0, 1, 0), angle)
        turns.append(
            {
                "rotation_deg": angle,
                "rotation_block_mm3": abs(rotated.common(pocket_wall).Volume),
            }
        )
    standard_envelope = standard_nut_clearance_check(x, support, seat)
    return {
        "standard_nut_envelope": standard_envelope,
        "nut_recess_depth_mm": outer - seat,
        "nominal_nut_to_guard_overlap_mm3": nominal,
        "missing_nut_floor_mm3": missing_floor,
        "nut_on_expected_bearing_plane": seated,
        "rotation_limits": turns,
        "external_holding_wrench_required": False,
        "nut_captive_without_screw": False,
        "nut_axial_clamping_surface": f"Printed 2 mm nominal floor at Y={seat:g} mm; both U sides are in the fitted compression stack.",
        "scope": "Nominal saved floor/hex geometry. Remove the bolt before withdrawing the nut in +Y. Coupon-fit and finish contact faces before tightening; no physical torque, creep or retention rating.",
        "passed": nominal < TOL
        and standard_envelope["passed"]
        and missing_floor < TOL
        and seated
        and all(row["rotation_block_mm3"] > 0.1 for row in turns),
    }


def _lift_path(name, shape, obstacles, offset, *, waypoints=None):
    """Continuously move each supported stock region without filling empty corners."""
    waypoints = [(0, 0, 0), (0, 0, 30)] if waypoints is None else waypoints
    if name == "ServoDriveBridge":
        from gondola.parts import servo_bridge

        blocks = servo_bridge.bridge_blank_blocks()
        uncovered = abs(shape.cut(union(blocks)).Volume)
        rows = [
            {
                "region": name + "Stock" + str(index),
                **continuous_path(block, waypoints, obstacles),
            }
            for index, block in enumerate(blocks)
        ]
        return {
            "part": name,
            "regions": rows,
            "bridge_outside_stock_mm3": uncovered,
            "scope": "Separate solid stock blocks contain the complete saved bridge, with holes filled conservatively. Each block is swept continuously; the broad roof does not extend to the height of the narrower cradle.",
            "passed": uncovered < TOL
            and bool(rows)
            and all(row["passed"] for row in rows),
        }
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
        # Fill every transverse cylindrical face so the continuous sweep can
        # preserve the fitted U channel. The carrier's open-bottom recess floor adds a
        # second bore; each shared frame station has two full 4.75 mm legs.
        module_name = (
            "MainPropulsionModule"
            if name in {"PropulsionFixedFrame", "ServoDriveBridge"}
            else "Carrier"
        )
        sections = (
            ((-6.0, 4.75, 3.4), (1.25, 4.75, 3.4))
            if module_name == "MainPropulsionModule"
            else ((-5.25, 4.0, 6.4), (1.25, 2.0, 3.4))
        )
        canonical_fills = [
            Part.makeBox(width, depth, width, V(-width / 2, y, 6 - width / 2))
            for y, depth, width in sections
        ]
        for site in attachment_sites(module_name, offset):
            for fill in canonical_fills:
                lower = lower.fuse(placed_shape(fill, site_placement(site)))
        lower = lower.removeSplitter()
        if name in {"BatteryMount", "ElectronicsMount", "AccessoryMount"}:
            # The deck is broad, but its two supports are narrow. A whole upper
            # bounding box invents stock below the deck and blocks the adjacent
            # servo cap during a real horizontal service slide. Literal stock
            # bounds are independent of the carrier builder; containment below
            # rejects an added feature outside them instead of omitting it.
            pieces = [
                (name + "Lower", lower),
                (name + "Deck", Part.makeBox(66, 66, 2, V(-33, -33, 17))),
                (
                    name + "SupportNegativeX",
                    Part.makeBox(5, 5, 4.5, V(-8, -2.5, 12.5)),
                ),
                (name + "SupportPositiveX", Part.makeBox(5, 5, 4.5, V(3, -2.5, 12.5))),
            ]
        else:
            pieces = [(name + "Lower", lower), (name + "Upper", upper)]
    solids = [
        (label, part)
        for label, part in pieces
        if part.Solids and abs(part.Volume) > TOL
    ]
    uncovered = (
        abs(shape.cut(union([part for _, part in solids])).Volume)
        if solids
        else abs(shape.Volume)
    )
    rows = [
        {"region": label, **continuous_path(part, waypoints, obstacles)}
        for label, part in solids
    ]
    return {
        "part": name,
        "regions": rows,
        "shape_outside_service_envelope_mm3": uncovered,
        "passed": bool(rows) and uncovered < TOL and all(row["passed"] for row in rows),
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


def _service_preflight(doc, registry, bindings):
    """Require saved poses and mounted prints before constructing service shapes."""
    checked, failures = [], []
    for station, module in bindings:
        pose = module_attachment_pose(station, module)
        binding = mount_binding(module.Name)
        name = binding[0] if binding is not None else None
        required = (
            (name, "ServoDriveBridge")
            if module.Name == "MainPropulsionModule"
            else (name,)
        )
        for required_name in required:
            mount = doc.getObject(required_name) if required_name is not None else None
            mount_check = {
                "object": required_name,
                "present": mount is not None,
                "registered_once_as_print": mount is not None
                and list(registry.PrintedParts).count(mount) == 1,
                "belongs_to_module": mount is not None
                and belongs_to_group(mount, module),
                "valid_solid": mount is not None
                and hasattr(mount, "Shape")
                and not mount.Shape.isNull()
                and mount.Shape.isValid()
                and bool(mount.Shape.Solids),
            }
            if not all(value for key, value in mount_check.items() if key != "object"):
                failures.append(
                    {
                        "module": module.Name,
                        "required_mount": mount_check,
                        "error": "Invalid required rail mount",
                        "passed": False,
                    }
                )
                break
        else:
            if pose["passed"]:
                checked.append((module, pose, name))
            else:
                failures.append(
                    {
                        "module": module.Name,
                        "native_attachment_pose": pose,
                        "error": "Invalid native rail attachment pose",
                        "passed": False,
                    }
                )
    return checked, failures


def _shared_trim_interval(pose):
    """Intersect ±3 mm bolt windows; a 30 mm pair on 28 mm pitch gives 4 mm."""
    limits = []
    axes = sorted(pose["attachment_world_axes_x_mm"])
    if len(axes) != 2 or abs(axes[1] - axes[0] - 30) > TOL:
        raise ValueError("Shared trim requires two rail-clamp axes30mm apart")
    centres = []
    for axis in axes:
        matches = [
            centre for centre in range(-140, 141, 28) if abs(axis - centre) <= 3 + TOL
        ]
        if len(matches) != 1:
            raise ValueError("Shared trim axis is outside the reviewed wall range")
        centres.append(matches[0])
        limits.append((matches[0] - 3 - axis, matches[0] + 3 - axis))
    if abs(centres[1] - centres[0] - 28) > TOL:
        raise ValueError("Shared trim requires two adjacent rail walls")
    low, high = max(row[0] for row in limits), min(row[1] for row in limits)
    if abs(high - low - 4) > TOL:
        raise ValueError("Shared clamp intervals do not give the reviewed4mm trim")
    # The continuous46mm bottom lands must also stay inside the full-width
    # base, X±149 before its1mm end chamfers. Outer wall pairs have less travel.
    centre = sum(axes) / 2
    low, high = max(low, -126 - centre), min(high, 126 - centre)
    if low > TOL or high < -TOL:
        raise ValueError("Shared bottom datum is outside the full-width rail base")
    return low, high


def _shared_screw_slide(name, shape, obstacles, low, high):
    """Exact two-cylinder swept envelopes, without filling slot-end corners."""
    opposite = "Opposite" in name
    x = -15 if opposite else 15
    reference, swept = [], []
    for radius, y, depth in (
        (3.0, 9.0 if opposite else -11.0, 2.0),
        (1.5, -11.0 if opposite else -9.0, 20.0),
    ):
        reference.append(Part.makeCylinder(radius, depth, V(x, y, 6), V(0, 1, 0)))
        ends = [
            Part.makeCylinder(radius, depth, V(x + shift, y, 6), V(0, 1, 0))
            for shift in (low, high)
        ]
        middle = Part.makeBox(high - low, depth, 2 * radius, V(x + low, y, 6 - radius))
        swept.append(union([*ends, middle]))
    outside = abs(shape.cut(union(reference)).Volume)
    envelope = union(swept)
    hits = {
        name: abs(envelope.common(other).Volume)
        for name, other in obstacles.items()
        if envelope.BoundBox.intersect(other.BoundBox)
    }
    return {
        "part": name,
        "method": "Exact X sweep of the separate M3 head and shank cylinder envelopes",
        "actual_shape_outside_envelope_mm3": outside,
        "intersection_mm3": hits,
        "passed": outside < TOL and all(value < TOL for value in hits.values()),
    }


def supported_propulsion_slide(shapes, obstacles, pose):
    """Sweep every carried solid, including the loosened nominal hardware."""
    low, high = _shared_trim_interval(pose)
    path = [(low, 0, 0), (high, 0, 0)]
    rows = []
    for name, shape in sorted(shapes.items()):
        if name in ("PropulsionFixedFrame", "ServoDriveBridge"):
            row = _lift_path(name, shape, obstacles, 15, waypoints=path)
        elif name in (
            "MainPropulsionModuleRailMountScrew",
            "MainPropulsionModuleOppositeRailMountScrew",
        ):
            row = _shared_screw_slide(name, shape, obstacles, low, high)
        else:
            row = {"part": name, **continuous_path(shape, path, obstacles)}
        rows.append(row)
    return {
        "relative_x_range_mm": [low, high],
        "travel_mm": high - low,
        "parts": rows,
        "scope": "Continuous nominal rigid slide across the reported relative_x_range_mm, including full-width base clipping at the end pairs, with all registered neighbours retained. Loosen both M3 pairs and support the assembly; disconnect/reroute leads and regenerate wiring reservations before operation. This is not a friction, preload, curved-rail or cable-motion qualification.",
        "passed": bool(rows) and all(row["passed"] for row in rows),
    }


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
    checked, failures = _service_preflight(doc, registry, bindings)
    if failures:
        return {
            "modules": failures,
            "obstacle_inventory": inventory,
            "error": "Rail service preflight failed",
            "passed": False,
        }
    world = {obj.Name: world_shape(obj) for obj in objects}
    rows = []
    for module, pose, mount_name in checked:
        members = {obj.Name for obj in objects if belongs_to_group(obj, module)}
        attachment_names = [
            obj.Name for obj in registry.RailLocks if belongs_to_group(obj, module)
        ]
        attachments = set(attachment_names)
        offset = float(module.RailAttachmentOffsetX)
        sites = attachment_sites(module.Name, offset)
        expected = {
            module.Name + site["prefix"] + suffix
            for site in sites
            for suffix in ("RailMountScrew", "RailMountNut")
        }
        if (
            len(attachment_names) != len(expected)
            or attachments != expected
            or not expected.issubset(world)
        ):
            rows.append(
                {
                    "module": module.Name,
                    "passed": False,
                    "expected_attachment_hardware": sorted(expected),
                    "actual_attachment_hardware": sorted(attachment_names),
                    "error": "Rail attachment inventory mismatch",
                }
            )
            continue
        inverse = module.getGlobalPlacement().inverse()
        shapes = {name: shape.copy() for name, shape in world.items()}
        for shape in shapes.values():
            shape.Placement = inverse.multiply(shape.Placement)
        services, removed = [], set()
        for site in sites:
            site_inverse = site_placement(site).inverse()
            canonical = {
                name: placed_shape(shape, site_inverse)
                for name, shape in shapes.items()
            }
            screw_name = module.Name + site["prefix"] + "RailMountScrew"
            nut_name = module.Name + site["prefix"] + "RailMountNut"
            screw, nut = canonical[screw_name], canonical[nut_name]
            bolt_obstacles = {
                name: shape
                for name, shape in canonical.items()
                if name not in removed | {screw_name}
            }
            driver = side_driver_clearance(screw, bolt_obstacles)
            shared = module.Name == "MainPropulsionModule"
            nut_capture = nut_capture_check(
                0,
                nut,
                canonical["ServoDriveBridge" if shared else mount_name],
                shared=shared,
            )
            withdrawal = continuous_path(
                screw, [(0, 0, 0), (0, -25, 0)], bolt_obstacles
            )
            after_bolt = {
                name: shape
                for name, shape in canonical.items()
                if name not in removed | {screw_name, nut_name}
            }
            nut_path = continuous_path(
                nut, [(0, 0, 0), (0, 4, 0), (25, 4, 0)], after_bolt
            )
            services.append(
                {
                    "attachment_prefix": site["prefix"],
                    "attachment_local_x_mm": site["x_offset"],
                    "attachment_side": site["side"],
                    "screw": screw_name,
                    "nut": nut_name,
                    "previously_removed_attachment_hardware": sorted(removed),
                    "other_attachment_hardware_retained": sorted(
                        attachments - removed - {screw_name, nut_name}
                    ),
                    "side_driver_access": driver,
                    "nut_window_anti_rotation": nut_capture,
                    "rail_screw_withdrawal": withdrawal,
                    "nut_removal_after_screw": nut_path,
                    "passed": all(
                        row["passed"]
                        for row in (driver, nut_capture, withdrawal, nut_path)
                    ),
                }
            )
            removed.update((screw_name, nut_name))
        moving = members - attachments
        fixed = {name: shape for name, shape in shapes.items() if name not in members}
        shared = module.Name == "MainPropulsionModule"
        trim = (
            supported_propulsion_slide(
                {name: shapes[name] for name in members}, fixed, pose
            )
            if shared
            else None
        )
        slide = (
            10 if shared else 4 if module.Name == "ElectronicsEquipmentModule" else 0
        )
        removal_path = (
            [(0, 0, 0), (slide, 0, 0), (slide, 0, 30)]
            if slide
            else [(0, 0, 0), (0, 0, 30)]
        )
        lifts = [
            _lift_path(name, shapes[name], fixed, offset, waypoints=removal_path)
            for name in sorted(moving)
        ]
        rows.append(
            {
                "module": module.Name,
                "native_attachment_pose": pose,
                "shared_servo_bridge_clamp": module.Name == "MainPropulsionModule",
                "covering_devices_removed": [],
                "other_modules_removed": [],
                "attachment_services": services,
                "removed_attachment_hardware": sorted(removed),
                "populated_module_removal_path_mm": removal_path,
                "removal_path_coordinate_frame": "Module local; electronics +X is world -X at its required 180-degree yaw.",
                "unclamped_module_held_during_rail_slide": bool(slide),
                "unclamped_propulsion_held_during_rail_slide": shared,
                "populated_supported_trim": trim,
                "populated_module_lift": lifts,
                "passed": pose["passed"]
                and len(services) == len(sites)
                and all(row["passed"] for row in services)
                and bool(lifts)
                and all(row["passed"] for row in lifts)
                and (trim is None or trim["passed"]),
            }
        )
    return {
        "modules": rows,
        "obstacle_inventory": inventory,
        "saved_stage_settings": _saved_stage_settings(doc),
        "scope": "Each populated module is checked at its saved configuration and recorded stage settings, with every other registered physical part installed. These paths do not certify other angles or positions. The open-bottom hex recess restrains nut rotation and its 2 mm nominal floor carries axial load. For each clamp in order, withdraw its transverse screw and slide its nut outward through the pocket opening, retaining the other pair until its turn. The opposite propulsion clamp reverses these directions. After removing both propulsion pairs, hold the complete assembly, slide it +X10mm along the open U channels, then lift30mm. The unclamped feet cross wall gaps during hand-supported removal; this is not an operating attachment position or an extension of allowed clamped adjustment. The populated FC carrier similarly slides world -X4mm (its local +X4mm) while held before lifting30mm; this temporary unclamped position is not an operating setting. Battery and accessory carriers retain direct vertical lift. No covering board, battery or servo bridge removal. Support frame and bridge together when their shared propulsion clamp is loose; the lift treats them as a held assembly, not as self-retaining. Disconnect/release flexible leads and external retention before lifting. Continuous rigid envelopes, including full screw head and specified tools, do not qualify hands, supplied bit/nut-pocket fit, curved rail, wiring, friction, PA12 creep or adhesive strength. Local slot travel does not imply every alternative module position is collision-free; revalidate after moving.",
        "passed": len(rows) == len(MODULE_STATIONS)
        and all(row["passed"] for row in rows),
    }
