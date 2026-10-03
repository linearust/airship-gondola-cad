"""PA12 wall measurements and supplier manufacturing allowances.

These geometric screens preserve explicit fit, fatigue and supplier-acceptance
limits; they are not structural or process qualification.
"""

from math import sqrt

import FreeCAD as App
import Part

from gondola.cad import world_shape
from gondola.contracts.design import CREALLO_GUIDE_URL, MANUFACTURING_DECISION
from gondola.contracts.drive import drive_for_document
from gondola.parts import equipment_mounts as mounts
from gondola.parts import optical_interface, propulsion, rail

from .geometry import local_shape

TOL = 1e-5
V = App.Vector


def planar_wall_regions(shape, maximum=1.51001):
    """Opposed parallel planar faces plus interior samples, not a medial-axis proof."""
    planes = [
        (i, f, f.normalAt(0, 0), f.CenterOfMass)
        for i, f in enumerate(shape.Faces)
        if type(f.Surface).__name__ == "Plane"
    ]
    found = []
    for index, (i, first, normal, point) in enumerate(planes):
        for k, second, other_normal, other_point in planes[index + 1 :]:
            if normal.dot(other_normal) > -0.999999:
                continue
            thickness = -(other_point - point).dot(normal)
            if not 1e-4 < thickness < maximum:
                continue
            projected = first.copy()
            projected.translate(-normal * thickness)
            common = projected.common(second)
            if common.Area < 1e-5:
                continue
            interiors = []
            for face in common.Faces:
                points, triangles = face.tessellate(0.5)
                for triangle in triangles[:10]:
                    sample = (
                        sum((points[t] for t in triangle), V()) / 3
                        + normal * thickness / 2
                    )
                    if shape.isInside(sample, 1e-6, False):
                        interiors.append([sample.x, sample.y, sample.z])
            if interiors:
                found.append(
                    {
                        "faces": [i, k],
                        "material_thickness_mm": thickness,
                        "projected_overlap_area_mm2": common.Area,
                        "interior_samples_mm": interiors[:2],
                    }
                )
    return found


def material_length_on_line(shape, a, b):
    result = shape.common(Part.makeLine(V(*a), V(*b)))
    return sum(edge.Length for edge in result.Edges)


def rail_mount_wall_probes():
    """Native sections of the web, U saddle and downward-open outer recesses."""
    e = 0.01
    probes = [
        (
            "rail_flexible_base",
            "ContinuousRail",
            (17, 0, -e),
            (17, 0, rail.PAD_THICKNESS + e),
            rail.PAD_THICKNESS,
        ),
        (
            "rail_straight_base_width",
            "ContinuousRail",
            (17, -rail.BASE_WIDTH / 2 - e, rail.PAD_THICKNESS / 2),
            (17, rail.BASE_WIDTH / 2 + e, rail.PAD_THICKNESS / 2),
            rail.BASE_WIDTH,
        ),
        (
            "rail_wall_thickness",
            "ContinuousRail",
            (0, -rail.WEB_THICKNESS / 2 - e, 3),
            (0, rail.WEB_THICKNESS / 2 + e, 3),
            rail.WEB_THICKNESS,
        ),
        (
            "rail_slot_top_ligament",
            "ContinuousRail",
            (0, 0, rail.BOLT_AXIS_Z + rail.SLOT_HEIGHT / 2 - e),
            (0, 0, rail.WEB_TOP_Z + e),
            rail.WEB_TOP_Z - rail.BOLT_AXIS_Z - rail.SLOT_HEIGHT / 2,
        ),
        (
            "carrier_roof",
            "BatteryMount",
            (0, 0, rail.CARRIER_INNER_ROOF_Z - e),
            (0, 0, rail.MOUNT_TOP_Z + e),
            rail.MOUNT_TOP_Z - rail.CARRIER_INNER_ROOF_Z,
        ),
        (
            "carrier_clamp_leg",
            "BatteryMount",
            (4, rail.MOUNT_OUTER_Y - e, 8),
            (4, -rail.WEB_THICKNESS / 2 + e, 8),
            rail.MOUNT_LEG_THICKNESS,
        ),
    ]
    probes.extend(
        [
            (
                "carrier_head_recess_floor",
                "BatteryMount",
                (2.5, -3.25 - e, 6),
                (2.5, -1.25 + e, 6),
                2.0,
            ),
            (
                "carrier_positive_clamp_leg",
                "BatteryMount",
                (4, 1.25 - e, 8),
                (4, 5.25 + e, 8),
                4.0,
            ),
            (
                "carrier_nut_pocket_floor",
                "BatteryMount",
                (2.5, 1.25 - e, 6),
                (2.5, 3.25 + e, 6),
                2.0,
            ),
            (
                "carrier_nut_pocket_top_ligament",
                "BatteryMount",
                (0, 4.5, 6 + 5.9 / sqrt(3) - e),
                (0, 4.5, 12.5 + e),
                12.5 - 6 - 5.9 / sqrt(3),
            ),
            (
                "carrier_nut_pocket_bottom_opening",
                "BatteryMount",
                (0, 4.5, rail.CARRIER_LEG_BOTTOM_Z - e),
                (0, 4.5, 4.05 + e),
                0.0,
            ),
        ]
    )
    for sign in (-1, 1):
        probes.append(
            (
                f"carrier_deck_support_{sign:+d}",
                "BatteryMount",
                (sign * 5, 0, rail.MOUNT_TOP_Z),
                (sign * 5, 0, mounts.DECK_BOTTOM_Z),
                mounts.DECK_BOTTOM_Z - rail.MOUNT_TOP_Z,
            )
        )
    return probes


def review(doc, registry):
    from gondola.parts import optical_mount

    probes = []
    seen_skus = set()
    for obj in registry.PrintedParts:
        if obj in registry.RailSegments or obj.PrintSKU in seen_skus:
            continue
        seen_skus.add(obj.PrintSKU)
        shape = local_shape(obj)
        regions = planar_wall_regions(shape)
        probes.append(
            {
                "part": obj.Name,
                "planar_material_regions_up_to_1p51mm": regions,
                "no_detected_planar_wall_under_1p5mm": all(
                    row["material_thickness_mm"] >= 1.5 - TOL for row in regions
                ),
            }
        )
    analytic = rail_mount_wall_probes() + [
        (
            "guard_radial_wall",
            "PortMotorCarrier",
            (9.5, 0, 22.99),
            (9.5, 0, 26.01),
            3.0,
        ),
        (
            "guard_axial_wall",
            "PortMotorCarrier",
            (7.99, 0, 24.5),
            (11.01, 0, 24.5),
            3.0,
        ),
        ("guard_root_fan", "PortMotorCarrier", (7.99, -29, 5), (11.01, -29, 5), 3.0),
        ("guard_rear_bridge", "PortMotorCarrier", (-8.01, 16, 0), (-4.99, 16, 0), 3.0),
        ("guard_outer_return", "PortMotorCarrier", (2, 22.99, 0), (2, 26.01, 0), 3.0),
        (
            "battery_mount_deck_thickness",
            "BatteryMount",
            (0, 20, mounts.DECK_BOTTOM_Z - 0.01),
            (0, 20, mounts.SUPPORT_FACE_Z + 0.01),
            mounts.DECK_THICKNESS,
        ),
        (
            "fc_support_deck_thickness",
            "ElectronicsMount",
            (0, 20, mounts.DECK_BOTTOM_Z - 0.01),
            (0, 20, mounts.SUPPORT_FACE_Z + 0.01),
            mounts.DECK_THICKNESS,
        ),
        (
            "accessory_plate_thickness",
            "AccessoryMount",
            (14, -24, mounts.DECK_BOTTOM_Z - 0.01),
            (14, -24, mounts.SUPPORT_FACE_Z + 0.01),
            mounts.DECK_THICKNESS,
        ),
        (
            "frame_foot_thickness",
            "PropulsionFixedFrame",
            (8.0, 20.0, propulsion.FOOT_BOTTOM_Z - 0.01),
            (
                8.0,
                20.0,
                propulsion.FOOT_BOTTOM_Z + propulsion.FOOT_THICKNESS + 0.01,
            ),
            propulsion.FOOT_THICKNESS,
        ),
        (
            "optical_tray_deck_thickness",
            "OpticalSensorTray",
            (0, 4, optical_mount.TRAY_BOTTOM_Z - 0.01),
            (0, 4, optical_mount.TRAY_TOP_Z + 0.01),
            optical_mount.TRAY_TOP_Z - optical_mount.TRAY_BOTTOM_Z,
        ),
    ]
    analytic.extend(
        (
            f"tape_wing_thickness_x{x:g}_side{side:+d}",
            "ContinuousRail",
            (x, side * 12, -0.01),
            (x, side * 12, rail.PAD_THICKNESS + 0.1),
            rail.PAD_THICKNESS,
        )
        for x in rail.PAD_CENTRES
        for side in (-1, 1)
    )
    analytic.extend(optical_interface.manufacturing_wall_probes())
    measurements = []
    probes_with_frames = [(probe, False) for probe in analytic] + [
        (probe, True)
        for probe in propulsion.manufacturing_wall_probes(drive=drive_for_document(doc))
    ]
    for (feature, name, start, end, expected), module_coordinates in probes_with_frames:
        obj = doc.getObject(name)
        shape = local_shape(obj)
        if module_coordinates:
            shape = world_shape(obj)
            shape.Placement = (
                doc.MainPropulsionModule.getGlobalPlacement()
                .inverse()
                .multiply(shape.Placement)
            )
        actual = material_length_on_line(shape, start, end)
        measurements.append(
            {
                "feature": feature,
                "part": name,
                "sample_line_mm": [start, end],
                "coordinate_frame": "propulsion module"
                if module_coordinates
                else "part local",
                "measured_material_length_mm": actual,
                "nominal_expected_mm": expected,
                "passed": abs(actual - expected) < TOL,
            }
        )
    return {
        "source": CREALLO_GUIDE_URL,
        "published_sls_pa12_thin_broad_guidance_mm": [
            [50, 1.0],
            [100, 1.5],
            [150, 2.0],
            ["200+", 3.0],
        ],
        "wall_guidance_source": MANUFACTURING_DECISION["sources"][
            "dimensions_and_tolerances"
        ],
        "guide_scope": f"Creallo's table covers thin and broad SLS PA12 plates; use it as a conservative review reference while SLS/MJF selection is pending. This is not a blanket 3 mm wall requirement for every small feature, nor permission to claim the {rail.LENGTH:g} mm flexure automatically compliant.",
        "generic_nylon_minimum_mm": 0.8,
        "general_functional_wall_target_mm": 1.5,
        "rail_flexure_target_mm": rail.PAD_THICKNESS,
        "short_50mm_guidance_mm": 1.0,
        "equipment_mount_assessment": {
            "deck_mm": mounts.DECK_THICKNESS,
            "fc_support_deck_size_mm": [
                *mounts.ELECTRONICS_DECK_SIZE,
                mounts.DECK_THICKNESS,
            ],
            "accessory_deck_size_mm": mounts.ACCESSORY_DECK_SIZE,
            "hole_pad_diameter_mm": mounts.MOUNT_PAD_DIAMETER,
            "contracts": [mounts.mount_contract(kind) for kind in mounts.MOUNT_NAMES],
            "rigid_optical_mount_contract": optical_mount.mount_contract(),
        },
        "rail_functional_flexure_assessment": {
            "nominal_base_and_tape_wing_thickness_mm": rail.PAD_THICKNESS,
            "minimum_requested_tape_attachment_thickness_mm": 1.5,
            "wall_lengths_mm": [last - first for first, last in rail.wall_segments()],
            "gap_lengths_mm": [last - first for first, last in rail.flex_spans()],
            "base_width_mm": rail.BASE_WIDTH,
            "scope": "The straight base and tape-wing pairs retain the nominal thickness reported here. Every attachment uses the same wall-top shoe with a1mm nominal gap between its lower legs and the rail base. The propulsion frame pairs these shoes28mm apart; the rigid pair requires coplanar occupied wall tops and does not independently follow local wall tilt. Attachment contracts distinguish individual bolt travel from paired-module travel, including end limits and shared clamp load zones. Top seating is checked independently. Curvature under occupied mounts, adhesion, lateral/torsional stability, strain, fatigue and supplier acceptance remain unqualified.",
        },
        "supplier_acceptance_status": f"User-reported manufacturing review requires at least1.5mm nominal tape attachment. Current base/wings are{rail.PAD_THICKNESS:g}mm; delivered fit, full-length curvature/fatigue and one-piece acceptance remain unqualified.",
        "opposed_planar_face_screen": probes,
        "actual_feature_measurements": measurements,
        "wall_screen_limits": "Sampled opposed planar faces and explicit line probes only. Fillet/taper/cylindrical transitions are not exhaustively certified as a global minimum-wall field. No strength or fatigue qualification.",
        "powder_removal": "Wall slots, U saddles, downward-open outer nut/head recesses, support arms and journals remain accessible before hardware installation. Rail nut pockets restrain rotation and retain 2 mm nominal bearing floors; they are not captive before bolt insertion. Other recesses follow their respective interface contracts. No sealed hollow print is claimed.",
        "tolerance": {
            "dimensional_percent": 0.3,
            "minimum_absolute_mm": 0.3,
            "rail_fit": rail.attachment_contract(),
            "not_a_GDT_position_or_actual_fit_guarantee": True,
        },
        "blanket_guide_compliance_claimed": False,
        "passed": rail.PAD_THICKNESS >= 1.5
        and all(row["no_detected_planar_wall_under_1p5mm"] for row in probes)
        and all(row["passed"] for row in measurements),
    }
