"""Read-only audit of service reservations, bought hardware, and source metadata."""

import json
import os
from collections import Counter
from pathlib import Path

import FreeCAD as App
import Part

from gondola.cad import (
    belongs_to_group,
    placed_shape,
    world_shape,
)
from gondola.config import ARTIFACT_SCHEMA_VERSION, ARTIFACT_STEM, OUTPUT_DIR, REPO_ROOT
from gondola.contracts import equipment_interfaces as interfaces
from gondola.contracts.design import (
    EXPECTED_INVENTORY,
    FC_INSTALLATION_LOCAL_YAW_DEG,
    HARDWARE_MATERIALS,
    MODULE_STATIONS,
    PURCHASED_HARDWARE_QUANTITIES,
    WIRING_PURCHASE_PLAN,
    hardware_bom_scope,
)
from gondola.contracts.equipment_options import (
    get_navigation_profile,
    get_radio_profile,
)
from gondola.parts import equipment_envelopes as devices
from gondola.parts import equipment_layout as layout
from gondola.parts import equipment_mounts as mounts
from gondola.parts import stack_interface
from gondola.print_export import geometry_comparison
from gondola.procurement import (
    PURCHASE_METADATA_FIELDS,
    REQUIRED_PURCHASE_FIELDS,
    purchase_code,
    purchase_evidence,
)
from gondola.provenance import file_sha256, source_fingerprint

from . import wiring as wiring_validation
from .evidence import comparison_passed
from .geometry import (
    intersection_volume,
    local_shape,
    translation_sweep,
)
from .optical import mtf_sensor_check

TOL = 1e-6


def fc_installation_check(doc):
    """Check FC identity and orientation beyond its symmetric reference solid."""
    board = doc.getObject("ModuleFCEnvelope")
    parent = doc.getObject("ElectronicsEquipmentModule")
    station = next(
        station
        for station in MODULE_STATIONS
        if station.object_name == "ElectronicsEquipmentModule"
    )
    if board is None or parent is None:
        return {"passed": False, "error": "Missing FC or electronics carrier"}
    intended_local = App.Placement(
        App.Vector(*mounts.FC_CENTRE_XY, devices.FC_BOTTOM_Z),
        App.Rotation(
            App.Vector(0, 0, 1),
            mounts.FC_ROTATION_DEG + FC_INSTALLATION_LOCAL_YAW_DEG,
        ),
    )
    native_pose_matches = board.Placement.isSame(intended_local, TOL)
    expected_carrier_rotation = App.Rotation(App.Vector(0, 0, 1), station.yaw_deg)
    carrier_rotation_matches = parent.Placement.Rotation.isSame(
        expected_carrier_rotation, TOL
    )
    metadata_matches = (
        "InstallationYawInCarrier" in board.PropertiesList
        and abs(float(board.InstallationYawInCarrier) - FC_INSTALLATION_LOCAL_YAW_DEG)
        < TOL
    )
    try:
        contract_matches = json.loads(
            str(board.FlightControllerContract)
        ) == json.loads(json.dumps(interfaces.flight_controller_contract()))
    except (AttributeError, TypeError, ValueError):
        contract_matches = False
    correct_parent = board.getParentGeoFeatureGroup() == parent
    return {
        "installation_turn_in_carrier_deg": FC_INSTALLATION_LOCAL_YAW_DEG,
        "carrier_yaw_deg": station.yaw_deg,
        "native_board_placement_matches": native_pose_matches,
        "carrier_rotation_matches": carrier_rotation_matches,
        "native_installation_marker_matches": metadata_matches,
        "native_flight_controller_contract_matches": contract_matches,
        "board_parent_matches": correct_parent,
        "scope": "Native design orientation relative to the previous FC installation only. The square envelope cannot identify the physical board arrow; verify the received FC orientation and firmware configuration during assembly.",
        "passed": native_pose_matches
        and carrier_rotation_matches
        and metadata_matches
        and contract_matches
        and correct_parent,
    }


def mounting_pad_check(
    shape, centre, *, bottom, thickness, hole_diameter, pad_diameter
):
    """Measure the entire bearing annulus and bore, not a few points on a grid."""
    origin = App.Vector(centre[0], centre[1], bottom)
    bore = Part.makeCylinder(hole_diameter / 2, thickness, origin)
    annulus = Part.makeCylinder(pad_diameter / 2, thickness, origin).cut(bore)
    obstruction = intersection_volume(shape, bore)
    missing_material = annulus.cut(shape).Volume
    return {
        "centre_xy_mm": list(centre),
        "hole_diameter_mm": hole_diameter,
        "pad_diameter_mm": pad_diameter,
        "nominal_radial_wall_mm": (pad_diameter - hole_diameter) / 2,
        "bore_obstruction_mm3": obstruction,
        "missing_full_thickness_bearing_annulus_mm3": missing_material,
        "passed": obstruction < TOL
        and missing_material < TOL
        and (pad_diameter - hole_diameter) / 2 >= 1.5 - TOL,
    }


def slot_mounting_pad_check(
    shape, centre, *, bottom, thickness, hole_diameter, pad_diameter
):
    """Check a P-AS axis in a slot and the complete two-sided bearing material.

    A slot deliberately removes part of a circular annulus. Its expected bearing
    region is the pad disk minus the exact slot, not a filled round-hole annulus.
    This is a geometric seat check; the final fastener and clamp force are pending.
    """
    from gondola.parts import mounting_slots

    origin = App.Vector(*centre, bottom)
    bore = Part.makeCylinder(hole_diameter / 2, thickness, origin)
    candidates = []
    for spec in mounting_slots.rows():
        if spec["family"] != "square16_23":
            continue
        opening = mounting_slots.shape(spec, bottom, thickness)
        if bore.cut(opening).Volume < TOL:
            candidates.append((spec, opening))
    if len(candidates) != 1:
        return {
            "centre_xy_mm": list(centre),
            "matching_slot_count": len(candidates),
            "error": "Device fastener axis must fit exactly one diagonal M2 slot",
            "passed": False,
        }
    spec, opening = candidates[0]
    bearing = Part.makeCylinder(pad_diameter / 2, thickness, origin).cut(opening)
    obstruction = intersection_volume(shape, bore)
    missing = bearing.cut(shape).Volume
    side_land = (pad_diameter - spec["width_mm"]) / 2
    return {
        "centre_xy_mm": list(centre),
        "slot_name": spec["name"],
        "matching_slot_count": 1,
        "hole_diameter_mm": hole_diameter,
        "pad_diameter_mm": pad_diameter,
        "slot_width_mm": spec["width_mm"],
        "nominal_side_land_mm": side_land,
        "expected_slot_bearing_area_mm2": bearing.Volume / thickness,
        "bore_obstruction_mm3": obstruction,
        "missing_full_thickness_slot_bearing_mm3": missing,
        "full_circular_annulus_required": False,
        "passed": obstruction < TOL
        and missing < TOL
        and side_land >= mounting_slots.MINIMUM_LAND - TOL
        and bearing.Volume > TOL,
    }


def carrier_symmetry_check(shape, *, bottom, thickness):
    """Measure the saved deck, excluding the intentionally directional rail shoe."""
    bounds = shape.BoundBox
    slab = Part.makeBox(
        bounds.XLength + 2,
        bounds.YLength + 2,
        thickness,
        App.Vector(bounds.XMin - 1, bounds.YMin - 1, bottom),
    )
    deck = shape.common(slab)
    if deck.isNull() or not deck.isValid() or len(deck.Solids) != 1:
        return {"passed": False, "error": "Saved deck must be one valid solid"}
    box = deck.BoundBox
    centred_square = (
        abs(box.XLength - mounts.COMMON_DECK_SIZE[0]) < TOL
        and abs(box.YLength - mounts.COMMON_DECK_SIZE[1]) < TOL
        and abs(box.XLength - box.YLength) < TOL
        and abs(box.Center.x) < TOL
        and abs(box.Center.y) < TOL
        and abs(box.ZLength - thickness) < TOL
    )
    differences = {}
    for name, axis, angle in (
        ("quarter_turn", App.Vector(0, 0, 1), 90),
        ("mirror_x", App.Vector(0, 1, 0), 180),
        ("mirror_y", App.Vector(1, 0, 0), 180),
    ):
        transformed = deck.copy()
        transformed.rotate(App.Vector(0, 0, bottom + thickness / 2), axis, angle)
        differences[name + "_difference_mm3"] = (
            transformed.cut(deck).Volume + deck.cut(transformed).Volume
        )
    return {
        "centred_nominal_square": centred_square,
        **differences,
        "scope": "Deck outline and all openings only; rail shoe/clamp are directional.",
        "passed": centred_square and all(value < TOL for value in differences.values()),
    }


def carrier_contact_patch_checks(shape, *, bottom, thickness):
    """Keep unused alternatives' declared tape regions intact on every carrier."""
    specs = [
        (f"battery_{index}", centre, size)
        for index, (centre, size) in enumerate(mounts.BATTERY_ADHESIVE_REGIONS)
    ] + [
        ("navigation", mounts.NAVIGATION_CENTRE_XY, mounts.GPS_ADHESIVE_SIZE),
        ("radio", mounts.RADIO_ADHESIVE_CENTRE_XY, mounts.RADIO_ADHESIVE_SIZE),
    ]
    rows = []
    for name, centre, size in specs:
        patch = Part.makeBox(
            *size,
            thickness,
            App.Vector(centre[0] - size[0] / 2, centre[1] - size[1] / 2, bottom),
        )
        missing = patch.cut(shape).Volume
        rows.append(
            {
                "allocation": name,
                "centre_xy_mm": centre,
                "size_xy_mm": size,
                "nominal_contact_area_mm2": size[0] * size[1],
                "missing_full_thickness_material_mm3": missing,
                "passed": missing < TOL,
            }
        )
    return {
        "patches": rows,
        "scope": "Alternative nominal contact allocations, not simultaneous equipment or physical adhesive qualification. Shifted batteries need not cover the entire nominal allocation.",
        "passed": all(row["passed"] for row in rows),
    }


def carrier_opening_checks(
    shape,
    *,
    bottom=mounts.DECK_BOTTOM_Z,
    thickness=mounts.DECK_THICKNESS,
    through_bottom=None,
    through_depth=None,
):
    """Audit complete fixed bores and slot rims on the saved physical plate.

    ``through_bottom``/``through_depth`` include material beneath an optional
    deck, such as its fused top beam. Lands cover the entire declared deck
    thickness; they are geometric sections, not a clamp-strength qualification.
    """
    from gondola.parts import mounting_slots

    through_bottom = bottom if through_bottom is None else through_bottom
    through_depth = thickness if through_depth is None else through_depth
    if (
        thickness <= 0
        or through_depth <= 0
        or through_bottom > bottom + TOL
        or through_bottom + through_depth < bottom + thickness - TOL
    ):
        raise ValueError("Opening probe must include the complete plate thickness")
    fixed = []
    for centre in mounts.COMMON_DEVICE_HOLE_CENTRES:
        row = mounting_pad_check(
            shape,
            centre,
            bottom=bottom,
            thickness=thickness,
            hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
            pad_diameter=mounts.MOUNT_PAD_DIAMETER,
        )
        bore = Part.makeCylinder(
            mounts.MOUNT_HOLE_DIAMETER / 2,
            through_depth,
            App.Vector(*centre, through_bottom),
        )
        obstruction = intersection_volume(shape, bore)
        row["through_bore_obstruction_mm3"] = obstruction
        row["passed"] &= obstruction < TOL
        fixed.append(row)
    slots = []
    for spec in mounting_slots.rows():
        opening = mounting_slots.shape(spec, through_bottom, through_depth)
        deck_opening = mounting_slots.shape(spec, bottom, thickness)
        expanded = mounting_slots.shape(spec, bottom, thickness, border=1.5)
        rim = expanded.cut(deck_opening)
        obstruction = intersection_volume(shape, opening)
        missing_land = rim.cut(shape).Volume
        slots.append(
            {
                **spec,
                "minimum_full_thickness_land_mm": 1.5,
                "through_slot_obstruction_mm3": obstruction,
                "missing_continuous_full_thickness_land_mm3": missing_land,
                "passed": obstruction < TOL and missing_land < TOL,
            }
        )
    single_solid = shape.isValid() and len(shape.Solids) == 1
    symmetry = carrier_symmetry_check(shape, bottom=bottom, thickness=thickness)
    contact = carrier_contact_patch_checks(shape, bottom=bottom, thickness=thickness)
    pas = [
        slot_mounting_pad_check(
            shape,
            centre,
            bottom=bottom,
            thickness=thickness,
            hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
            pad_diameter=mounts.MOUNT_PAD_DIAMETER,
        )
        for centre in mounts.PAS_HOLE_CENTRES
    ]
    return {
        "fixed_device_bores": fixed,
        "mounting_slots": slots,
        "fixed_bore_count": len(fixed),
        "slot_count": len(slots),
        "deck_probe_bottom_mm": bottom,
        "deck_probe_thickness_mm": thickness,
        "through_probe_bottom_mm": through_bottom,
        "through_probe_depth_mm": through_depth,
        "single_valid_solid": single_solid,
        "deck_symmetry": symmetry,
        "nominal_adhesive_patches": contact,
        "pas_slot_mounts": pas,
        "scope": "Exact full-opening and continuous rim volume checks, including rounded ends and the entire curved edges. Fixed FC axes retain complete bearing annuli; P-AS axes use the diagonal slots with the complete expected side-bearing material. The saved deck is a centred square with quarter-turn and X/Y mirror symmetry. These checks do not qualify loaded slot clamping, arbitrary bolt heads, adhesive strength or every position's equipment clearance.",
        "passed": single_solid
        and bool(fixed)
        and bool(slots)
        and symmetry["passed"]
        and contact["passed"]
        and all(row["passed"] for row in fixed + slots + pas),
    }


def mounting_check(doc):
    """Inspect saved supports, confirmed XY axes, free space and removal paths.

    Pending device fasteners, PCB bearing planes and compressed dampers are not
    modeled. These tests prove the printed interfaces and explicit reservations;
    they do not claim a completed, retained equipment assembly.
    """
    from gondola.parts import wiring_reserves as wiring_clearances

    from .equipment_options import adhesive_support_check

    registry = doc.DesignRegistry
    physical_objects = (
        list(registry.PrintedParts)
        + list(registry.HardwareParts)
        + list(registry.ReferenceParts)
        + list(registry.TapeReferences)
    )
    physical_shapes_by_name = {obj.Name: world_shape(obj) for obj in physical_objects}
    support_rows = []
    expected_supports = {name: kind for kind, name in mounts.MOUNT_NAMES.items()}
    shared_reference = doc.getObject("BatteryMount")
    for name, kind in expected_supports.items():
        obj = doc.getObject(name)
        if obj is None:
            support_rows.append({"object": name, "passed": False, "error": "missing"})
            continue
        shape = local_shape(obj)
        comparison = geometry_comparison(shape, mounts.mount_shape(kind))
        expected_contract = json.loads(json.dumps(mounts.mount_contract(kind)))
        try:
            contract_matches = json.loads(obj.MountContract) == expected_contract
        except (AttributeError, ValueError, TypeError):
            contract_matches = False
        no_posts = abs(shape.BoundBox.ZMax - mounts.SUPPORT_FACE_Z) < TOL
        unverified_stack = "MountingStackVerified" in obj.PropertiesList and not bool(
            obj.MountingStackVerified
        )
        try:
            stack_contract_matches = json.loads(
                obj.StackInterfaceContract
            ) == json.loads(json.dumps(stack_interface.interface_contract(name)))
        except (AttributeError, ValueError, TypeError):
            stack_contract_matches = False
        openings = carrier_opening_checks(shape)
        shared_comparison = (
            geometry_comparison(shape, local_shape(shared_reference))
            if shared_reference is not None
            else None
        )
        shared_print_matches = (
            shared_comparison is not None
            and comparison_passed(shared_comparison, TOL)
            and str(getattr(obj, "PrintSKU", "")) == mounts.COMMON_PRINT_SKU
            and str(getattr(obj, "MountKind", "")) == kind
            and "HalfTurnSymmetric" in obj.PropertiesList
            and not bool(obj.HalfTurnSymmetric)
        )
        support_rows.append(
            {
                "object": name,
                "kind": kind,
                "source_comparison": comparison,
                "contract_matches": contract_matches,
                "single_valid_solid": shape.isValid() and len(shape.Solids) == 1,
                "no_unverified_device_posts_above_support_face": no_posts,
                "mounting_stack_remains_unverified": unverified_stack,
                "structural_stack_contract_matches": stack_contract_matches,
                "shared_print_comparison": shared_comparison,
                "shared_print_geometry_and_metadata_match": shared_print_matches,
                "physical_plate_openings": openings,
                "passed": obj in registry.EquipmentMounts
                and obj in registry.PrintedParts
                and shape.isValid()
                and len(shape.Solids) == 1
                and comparison_passed(comparison, TOL)
                and contract_matches
                and no_posts
                and unverified_stack
                and stack_contract_matches
                and shared_print_matches
                and openings["passed"],
            }
        )
    carriers = {
        "ModuleFCEnvelope": doc.getObject("ElectronicsMount"),
        "ModulePASEnvelope": doc.getObject("AccessoryMount"),
    }
    if any(carrier is None for carrier in carriers.values()):
        return {"supports": support_rows, "passed": False}
    mounting_rows = []
    navigation_profile = get_navigation_profile()
    radio_profile = get_radio_profile()
    device_specs = [
        (
            "ModuleFCEnvelope",
            mounts.FC_HOLE_CENTRES,
            interfaces.FC_HOLE_DIAMETER,
            devices.fc_envelope_shape,
        ),
    ]
    if navigation_profile.key == "PAS":
        device_specs.append(
            (
                "ModulePASEnvelope",
                mounts.PAS_HOLE_CENTRES,
                interfaces.PAS_HOLE_DIAMETER,
                devices.navigation_envelope_shape,
            ),
        )
    for name, centres, device_hole_diameter, factory in device_specs:
        carrier = carriers[name]
        carrier_shape = local_shape(carrier)
        parent = carrier.getParentGeoFeatureGroup()
        if name == "ModuleFCEnvelope":
            rotation = App.Rotation(App.Vector(0, 0, 1), mounts.FC_ROTATION_DEG)
            published_hole_axes = [
                rotation.multVec(App.Vector(x, y, 0))
                + App.Vector(*mounts.FC_CENTRE_XY, 0)
                for x, y in interfaces.FC_HOLE_CENTRES
            ]
        else:
            published_hole_axes = [
                App.Vector(
                    x + mounts.NAVIGATION_CENTRE_XY[0],
                    y + mounts.NAVIGATION_CENTRE_XY[1],
                    0,
                )
                for x, y in interfaces.PAS_HOLE_CENTRES
            ]
        axes_match = len(centres) == len(published_hole_axes) and all(
            min(
                (App.Vector(*centre, 0) - expected).Length
                for expected in published_hole_axes
            )
            < TOL
            for centre in centres
        )
        obj = doc.getObject(name)
        body = physical_shapes_by_name[name]
        comparison = geometry_comparison(
            body, placed_shape(factory(), parent.getGlobalPlacement())
        )
        bounds = body.optimalBoundingBox(False, False)
        holes = []
        for centre in centres:
            pad_check = (
                mounting_pad_check
                if name == "ModuleFCEnvelope"
                else slot_mounting_pad_check
            )
            pad = pad_check(
                carrier_shape,
                centre,
                bottom=mounts.DECK_BOTTOM_Z,
                thickness=mounts.DECK_THICKNESS,
                hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
                pad_diameter=mounts.MOUNT_PAD_DIAMETER,
            )
            world_axis = parent.getGlobalPlacement().multVec(App.Vector(*centre, 0))
            axis_probe = Part.makeCylinder(
                device_hole_diameter / 2,
                bounds.ZLength + 2,
                App.Vector(world_axis.x, world_axis.y, bounds.ZMin - 1),
            )
            obstruction = intersection_volume(body, axis_probe)
            pad["device_hole_diameter_mm"] = device_hole_diameter
            pad["device_hole_axis_obstruction_mm3"] = obstruction
            pad["passed"] &= obstruction < TOL
            holes.append(pad)
        mounting_rows.append(
            {
                "device": name,
                "confirmed_hole_count": len(centres),
                "mount_axes_match_published_device_pattern": axes_match,
                "device_source_comparison": comparison,
                "carrier": carrier.Name,
                "device_parent_matches_carrier": obj.getParentGeoFeatureGroup()
                == parent,
                "holes": holes,
                "passed": axes_match
                and comparison_passed(comparison, TOL)
                and obj.getParentGeoFeatureGroup() == parent
                and all(row["passed"] for row in holes),
            }
        )
    adhesive_rows = []
    adhesive_specs = [
        *(
            ("BatteryMount", "ModuleBatteryEnvelope", centre, size, "top")
            for centre, size in mounts.BATTERY_ADHESIVE_REGIONS
        ),
        (
            "AccessoryMount",
            "ModuleRadioEnvelope",
            mounts.RADIO_ADHESIVE_CENTRE_XY,
            mounts.RADIO_ADHESIVE_SIZE,
            "bottom",
        ),
    ]
    if navigation_profile.key != "PAS":
        adhesive_specs.append(
            (
                "AccessoryMount",
                "ModulePASEnvelope",
                mounts.NAVIGATION_CENTRE_XY,
                mounts.GPS_ADHESIVE_SIZE,
                "top",
            )
        )
    for mount_name, device_name, centre, size, face in adhesive_specs:
        support = doc.getObject(mount_name)
        owner = support.getParentGeoFeatureGroup()
        device_local = physical_shapes_by_name[device_name].copy()
        device_local.Placement = (
            owner.getGlobalPlacement().inverse().multiply(device_local.Placement)
        )
        adhesive_rows.append(
            {
                "device": device_name,
                **adhesive_support_check(
                    local_shape(support), device_local, centre, size, face=face
                ),
            }
        )
    free_height_rows = []
    for name, expected_gap in (
        ("ModuleFCEnvelope", mounts.FC_WIRING_CLEARANCE),
        (
            "ModulePASEnvelope",
            layout.navigation_bottom(navigation_profile) - mounts.SUPPORT_FACE_Z,
        ),
    ):
        parent = carriers[name].getParentGeoFeatureGroup()
        bounds = physical_shapes_by_name[name].optimalBoundingBox(False, False)
        support_top = (
            parent.getGlobalPlacement()
            .multVec(App.Vector(0, 0, mounts.SUPPORT_FACE_Z))
            .z
        )
        gap = bounds.ZMin - support_top
        # Preserve the complete device rectangle in its actual rotated frame;
        # a world bounding box would falsely occupy the FC's empty corners.
        dimensions = (
            interfaces.FC_SIZE_MM
            if name == "ModuleFCEnvelope"
            else navigation_profile.size_mm
        )
        centre = (
            mounts.FC_CENTRE_XY
            if name == "ModuleFCEnvelope"
            else layout.navigation_centre()
        )
        space = Part.makeBox(
            dimensions[0],
            dimensions[1],
            expected_gap,
            App.Vector(-dimensions[0] / 2, -dimensions[1] / 2, mounts.SUPPORT_FACE_Z),
        )
        if name == "ModuleFCEnvelope":
            space.rotate(App.Vector(), App.Vector(0, 0, 1), mounts.FC_ROTATION_DEG)
        space.translate(App.Vector(*centre, 0))
        space = placed_shape(space, parent.getGlobalPlacement())
        hits = [
            {
                "object": other.Name,
                "intersection_mm3": intersection_volume(
                    space, physical_shapes_by_name[other.Name]
                ),
            }
            for other in physical_objects
            if intersection_volume(space, physical_shapes_by_name[other.Name]) > TOL
        ]
        free_height_rows.append(
            {
                "device": name,
                "measured_underbody_gap_mm": gap,
                "required_underbody_gap_mm": expected_gap,
                "full_underbody_reservation_collisions": hits,
                "passed": abs(gap - expected_gap) < TOL and not hits,
            }
        )
    reserve = doc.getObject("FCWiringClearanceReserve")
    parent = doc.ElectronicsEquipmentModule
    wiring_report = {"passed": False, "error": "missing FC wiring corridor"}
    if reserve is not None:
        actual = world_shape(reserve)
        comparison = geometry_comparison(
            actual,
            placed_shape(
                wiring_clearances.reserve_shapes()["FCWiringClearanceReserve"],
                parent.getGlobalPlacement(),
            ),
        )
        hits = [
            obj.Name
            for obj in physical_objects
            if intersection_volume(actual, physical_shapes_by_name[obj.Name]) > TOL
        ]
        local_reserve = actual.copy()
        local_reserve.Placement = (
            parent.getGlobalPlacement().inverse().multiply(local_reserve.Placement)
        )
        axis_distances = []
        for x, y in mounts.FC_HOLE_CENTRES:
            axis = Part.makeLine(
                App.Vector(x, y, mounts.SUPPORT_FACE_Z),
                App.Vector(x, y, mounts.SUPPORT_FACE_Z + mounts.FC_WIRING_CLEARANCE),
            )
            distance = local_reserve.distToShape(axis)[0]
            axis_distances.append(
                {
                    "mount_axis_xy_mm": [x, y],
                    "distance_mm": distance,
                    "passed": distance >= 5.0 - TOL,
                }
            )
        wiring_report = {
            "source_comparison": comparison,
            "physical_collisions": hits,
            "clearance_from_confirmed_mount_axes": axis_distances,
            "scope": "Connected eight-mm underbody corridor, peripheral housing band and two planning exit bends. Future damper/spacer envelopes, exact plugged leads and qualified cable bend radii require actual dimensions.",
            "passed": reserve in registry.ClearanceVolumes
            and reserve not in registry.PrintedParts
            and reserve not in registry.HardwareParts
            and comparison_passed(comparison, TOL)
            and not hits
            and all(row["passed"] for row in axis_distances),
        }
    service_rows = []
    for name in (
        "ModuleBatteryEnvelope",
        "ModuleFCEnvelope",
        "ModulePASEnvelope",
        "ModuleRadioEnvelope",
    ):
        optical_group = doc.getObject("OpticalFlowModule")
        device_parent = doc.getObject(name).getParentGeoFeatureGroup()
        local_travel = App.Vector(*layout.device_removal_vector(name))
        world_travel = device_parent.getGlobalPlacement().Rotation.multVec(local_travel)
        sweep, sweep_method = translation_sweep(
            physical_shapes_by_name[name], tuple(world_travel)
        )
        release_head = (
            optical_group is not None
            and optical_group.getParentGeoFeatureGroup() == device_parent
        )
        removed_head_names = {
            obj.Name
            for obj in physical_objects
            if release_head and belongs_to_group(obj, optical_group)
        }
        detached_carrier = name == "ModuleRadioEnvelope"
        off_carrier_names = {
            obj.Name
            for obj in physical_objects
            if detached_carrier and not belongs_to_group(obj, device_parent)
        }
        hits = [
            obj.Name
            for obj in physical_objects
            if obj.Name != name
            and obj.Name not in removed_head_names
            and obj.Name not in off_carrier_names
            and intersection_volume(sweep, physical_shapes_by_name[obj.Name]) > TOL
        ]
        service_rows.append(
            {
                "device": name,
                "local_removal_vector_mm": tuple(local_travel),
                "world_removal_vector_mm": tuple(world_travel),
                "bench_access_required": release_head or detached_carrier,
                "service_collision_scope": "Detached carrier assembly only"
                if detached_carrier
                else "Installed assembly after declared tower release",
                "off_carrier_parts_excluded_for_bench_service": sorted(
                    off_carrier_names
                ),
                "optical_head_must_be_removed_first": release_head,
                "complete_optical_mount_removed": release_head,
                "temporarily_removed_head_parts": sorted(removed_head_names),
                "method": sweep_method,
                "prerequisite": "Disconnect leads and release device retention. For the underside radio, detach the carrier from the rail and remove the device along carrier-Z on the bench. When this carrier hosts the optical mount, detach the carrier for bench access, support the complete optical assembly, release its foot clamps and lift it away before servicing the device. The balloon is not modeled, so in-place underside access is not established. Bare-device path, not a connected harness.",
                "collisions": hits,
                "passed": not hits,
            }
        )
    evidence_matches = all(
        json.loads(str(carrier.MountingEvidence)) == interfaces.MOUNTING_EVIDENCE
        for carrier in carriers.values()
    )
    pending_metadata = []
    for name, key in (
        ("ModuleFCEnvelope", "FC"),
        ("ModulePASEnvelope", navigation_profile.interface_key),
        ("ModuleRadioEnvelope", radio_profile.interface_key),
        ("ModuleMTF02PEnvelope", doc.OpticalFlowModule.SensorModel),
    ):
        obj = doc.getObject(name)
        documented = (
            json.loads(str(obj.MountingEvidence)) == interfaces.MOUNTING_EVIDENCE[key]
        )
        try:
            connector_evidence_matches = (
                json.loads(str(obj.ConnectorEvidence))
                == interfaces.DEVICE_CONNECTOR_EVIDENCE[key]
            )
        except (AttributeError, TypeError, ValueError):
            connector_evidence_matches = False
        connector_unverified = (
            "InstalledConnectorFitVerified" in obj.PropertiesList
            and not obj.InstalledConnectorFitVerified
        )
        unverified = not bool(obj.MountingStackVerified) and not bool(
            obj.PCBHeightMeasured
        )
        pending_metadata.append(
            {
                "device": name,
                "evidence_matches": documented,
                "mounting_stack_and_pcb_height_unverified": unverified,
                "connector_evidence_matches_sources": connector_evidence_matches,
                "installed_connector_fit_unverified": connector_unverified,
                "passed": documented
                and unverified
                and connector_evidence_matches
                and connector_unverified,
            }
        )
    registered_names = {obj.Name for obj in registry.EquipmentMounts}
    fc_installation = fc_installation_check(doc)
    return {
        "supports": support_rows,
        "confirmed_device_holes": mounting_rows,
        "continuous_adhesive_pads": adhesive_rows,
        "underbody_clearance": free_height_rows,
        "fc_wiring_corridor": wiring_report,
        "fc_installation": fc_installation,
        "device_service": service_rows,
        "native_mounting_evidence_matches_sources": evidence_matches,
        "pending_device_mounting_evidence": pending_metadata,
        "limits": "Printed XY mounting interfaces and reservations only. Purchase FC dampers and device mounting hardware after confirming PCB bearing planes, compressed damper heights and bolt/spacer lengths. Lift checks assume adhesive/retaining hardware has been released; no complete retained device mounting stack is claimed.",
        "passed": registered_names == set(expected_supports)
        and len(registry.EquipmentMounts) == len(expected_supports)
        and all(
            row["passed"]
            for row in support_rows
            + mounting_rows
            + adhesive_rows
            + free_height_rows
            + service_rows
        )
        and wiring_report["passed"]
        and fc_installation["passed"]
        and evidence_matches
        and all(row["passed"] for row in pending_metadata),
    }


def hardware_check(doc, source):
    registry = doc.DesignRegistry
    sku_quantities = Counter(str(obj.HardwareSKU) for obj in registry.HardwareParts)
    materials_by_sku, material_checks = {}, []
    for obj in registry.HardwareParts:
        materials_by_sku.setdefault(str(obj.HardwareSKU), set()).add(
            str(obj.MaterialSelection)
        )
        expected = HARDWARE_MATERIALS.get(str(obj.HardwareSKU))
        material_checks.append(
            {
                "object": obj.Name,
                "material": str(obj.MaterialSelection),
                "passed": expected == str(obj.MaterialSelection),
            }
        )
    bom = json.loads((source.parent / (source.stem + "_hardware_bom.json")).read_text())
    bom_instance_names = [name for row in bom["items"] for name in row["instances"]]
    hardware_by_name = {obj.Name: obj for obj in registry.HardwareParts}
    bom_rows = []
    for row in bom["items"]:
        instances = [hardware_by_name.get(name) for name in row["instances"]]
        matched = bool(instances) and all(obj is not None for obj in instances)
        if matched:
            procurement_matches = all(
                field in row
                and all(
                    row[field] == str(getattr(obj, property_name, ""))
                    for obj in instances
                )
                and (field not in REQUIRED_PURCHASE_FIELDS or bool(row[field]))
                for field, property_name in PURCHASE_METADATA_FIELDS.items()
            )
            expected_material = HARDWARE_MATERIALS.get(row["sku"])
            matched = (
                procurement_matches
                and expected_material is not None
                and row.get("purchase_code")
                == purchase_code(row["sku"], expected_material)
                and all(
                    row.get(field) == values
                    for field, values in purchase_evidence(instances).items()
                )
                and row["quantity"] == len(instances)
                and all(
                    row["sku"] == str(obj.HardwareSKU)
                    and row["material"] == str(obj.MaterialSelection)
                    for obj in instances
                )
            )
        bom_rows.append({"sku": row["sku"], "matches_native_instances": matched})
    fingerprint = source_fingerprint()
    identity_matches = (
        bom.get("schema_version") == ARTIFACT_SCHEMA_VERSION
        and bom.get("source_fingerprint") == fingerprint
        and str(getattr(registry, "SourceFingerprint", "")) == fingerprint
    )
    return {
        "total_quantity": len(registry.HardwareParts),
        "unique_sku_count": len(sku_quantities),
        "sku_quantities": dict(sku_quantities),
        "materials_by_sku": {
            sku: sorted(values) for sku, values in materials_by_sku.items()
        },
        "material_checks": material_checks,
        "bom_source_identity_matches": identity_matches,
        "bom_purchase_scope_matches_contract": bom.get("purchase_scope")
        == hardware_bom_scope(),
        "bom_rows": bom_rows,
        "not_printed": all(
            obj not in registry.PrintedParts
            and not bool(getattr(obj, "PrintPart", False))
            for obj in registry.HardwareParts
        ),
        "bom_each_instance_exactly_once": len(bom_instance_names)
        == EXPECTED_INVENTORY["purchased_hardware"]
        and len(set(bom_instance_names)) == EXPECTED_INVENTORY["purchased_hardware"]
        and set(bom_instance_names) == {obj.Name for obj in registry.HardwareParts},
        "bom_stated_quantity": bom["purchased_hardware_quantity"],
        "bom_stated_unique_specs": bom["unique_purchase_spec_count"],
        "passed": dict(sku_quantities) == PURCHASED_HARDWARE_QUANTITIES
        and bom.get("purchase_scope") == hardware_bom_scope()
        and all(row["passed"] for row in material_checks)
        and identity_matches
        and all(row["matches_native_instances"] for row in bom_rows),
    }


def validate(source=None):
    from .equipment_options import compatibility_check

    fingerprint_before = source_fingerprint()
    source = (
        Path(source).resolve() if source else OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")
    )
    source_hash_before = file_sha256(source)
    bom_path = source.parent / (source.stem + "_hardware_bom.json")
    bom_hash_before = file_sha256(bom_path)
    doc = App.openDocument(str(source), hidden=True)
    try:
        registry = doc.DesignRegistry
        clearance_checks, reserve_pairs = wiring_validation.reserve_checks(doc)
        optical_report = mtf_sensor_check(doc)
        mounting_report = mounting_check(doc)
        options_report = compatibility_check(doc)
        hardware_report = hardware_check(doc, source)
        try:
            wiring_plan_matches = (
                json.loads(str(registry.WiringPurchasePlan)) == WIRING_PURCHASE_PLAN
            )
        except (AttributeError, TypeError, ValueError):
            wiring_plan_matches = False
        reference_sources = {}
        for name in (
            "ModulePASEnvelope",
            "ModuleRadioEnvelope",
            "ModuleMTF02PEnvelope",
        ):
            obj = doc.getObject(name)
            reference_sources[name] = {
                key: str(getattr(obj, key))
                for key in obj.PropertiesList
                if "Source" in key or key == "Notes"
            }
        report = {
            "source_file": os.path.relpath(source, REPO_ROOT),
            "source_sha256": source_hash_before,
            "hardware_bom_sha256_before": bom_hash_before,
            "source_fingerprint": fingerprint_before,
            "scope": "Read-only saved-file clearance and purchased-hardware audit. Temporary in-memory MTF optical-obstruction tilt probes are restored; the native file is never saved.",
            "actual_object_counts": {
                "printed": len(registry.PrintedParts),
                "hardware": len(registry.HardwareParts),
                "equipment_references": len(registry.ReferenceParts),
                "tape_references": len(registry.TapeReferences),
            },
            "reserve_checks": clearance_checks,
            "reserve_pair_checks": reserve_pairs,
            "mtf02p_sensor": optical_report,
            "equipment_mounts": mounting_report,
            "equipment_options": options_report,
            "hardware": hardware_report,
            "native_wiring_purchase_plan_matches_contract": wiring_plan_matches,
            "reference_sources": reference_sources,
            "limits": [
                "Connector catalog dimensions are retained evidence; reserved lanes do not verify installed PCB port datums, actual plug fit, withdrawal stroke or wire bends. The capacitor remains a provisional space allocation.",
                "The toroidal reserves are not proven wire routes, bend radii, strain relief or validated phase-lead slack over the bounded -180 to +180 degree output range.",
                "The optical mount can use either supported host. Its 400 mm whole-face field is checked to cover modeled-gondola depth; lens datums, actual optical calibration, gravity alignment and cable slack remain unverified.",
                "No physical fit, electrical insulation/current capacity, clamp force or structural test was performed.",
            ],
        }
    finally:
        App.closeDocument(doc.Name)
    source_hash_after = file_sha256(source)
    report["source_sha256_after"] = source_hash_after
    report["source_unchanged"] = source_hash_before == source_hash_after
    report["hardware_bom_sha256_after"] = file_sha256(bom_path)
    report["hardware_bom_unchanged"] = (
        bom_hash_before == report["hardware_bom_sha256_after"]
    )
    report["source_code_unchanged"] = fingerprint_before == source_fingerprint()
    report["passed"] = (
        source_hash_before == source_hash_after
        and report["source_code_unchanged"]
        and report["hardware_bom_unchanged"]
        and optical_report["passed"]
        and mounting_report["passed"]
        and options_report["passed"]
        and all(row["passed"] for row in clearance_checks)
        and all(row["passed"] for row in reserve_pairs)
        and hardware_report["passed"]
        and wiring_plan_matches
        and hardware_report["not_printed"]
        and hardware_report["bom_each_instance_exactly_once"]
        and hardware_report["bom_stated_quantity"]
        == EXPECTED_INVENTORY["purchased_hardware"]
        and hardware_report["bom_stated_unique_specs"]
        == EXPECTED_INVENTORY["purchased_hardware_types"]
    )
    report_path = source.parent / (source.stem + "_equipment_validation.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "equipment_report": str(report_path),
                "passed": report["passed"],
                "source_unchanged": source_hash_before == source_hash_after,
            }
        ),
        flush=True,
    )
    return report
