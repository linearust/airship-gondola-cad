"""PA12 wall measurements and supplier manufacturing allowances.

These geometric screens preserve explicit fit, fatigue and supplier-acceptance
limits; they are not structural or process qualification.
"""

import FreeCAD as App
import Part

from gondola.cad import world_shape
from gondola.contracts.design import CREALLO_GUIDE_URL, MANUFACTURING_DECISION
from gondola.contracts.drive import drive_for_document
from gondola.parts import equipment_mounts as mounts
from gondola.parts import propulsion, rail, stack_interface, stock_adapter

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
    analytic = [
        (
            "rail_slotted_roof_thickness",
            "ContinuousRail",
            (0, rail.TRACK_OFFSET + 1.8, rail.NUT_TOP_Z - 0.01),
            (0, rail.TRACK_OFFSET + 1.8, rail.TOP_Z + 0.01),
            rail.ROOF_THICKNESS,
        ),
        (
            "rail_functional_flexure_thickness",
            "ContinuousRail",
            (24, rail.TRACK_OFFSET, -0.01),
            (24, rail.TRACK_OFFSET, 1.3),
            rail.BASE_THICKNESS,
        ),
        (
            "tape_wing_thickness",
            "ContinuousRail",
            (0, 22, -0.01),
            (0, 22, 1.3),
            rail.PAD_THICKNESS,
        ),
        ("guard_radial_wall", "PortMotorCarrier", (12, 0, 22.79), (12, 0, 24.31), 1.5),
        (
            "central_servo_support_web",
            "PropulsionFixedFrame",
            (0, -2.51, 8),
            (0, 2.51, 8),
            5.0,
        ),
        (
            "direct_rail_foot_thickness",
            "PropulsionFixedFrame",
            (5, 10, propulsion.BASE_Z - 0.01),
            (5, 10, propulsion.BASE_Z + propulsion.RAIL_FOOT_THICKNESS + 0.01),
            propulsion.RAIL_FOOT_THICKNESS,
        ),
        (
            "frame_foot_thickness",
            "PropulsionFixedFrame",
            (8, propulsion.PIVOT_HALF_SPAN, propulsion.BASE_Z - 0.01),
            (
                8,
                propulsion.PIVOT_HALF_SPAN,
                propulsion.BASE_Z + propulsion.FOOT_THICKNESS + 0.01,
            ),
            propulsion.FOOT_THICKNESS,
        ),
        (
            "optical_base_pivot_wall",
            "OpticalMountBase",
            (-optical_mount.EAR_THICKNESS - 0.01, 0, 4),
            (0.01, 0, 4),
            optical_mount.EAR_THICKNESS,
        ),
        (
            "optical_roll_bracket_wall",
            "OpticalRollBracket",
            (-0.01, -1, 5),
            (optical_mount.ROLL_POST_WIDTH + 0.01, -1, 5),
            optical_mount.ROLL_POST_WIDTH,
        ),
        (
            "optical_tray_neck_wall",
            "OpticalSensorTray",
            (0, -0.01, 3.8),
            (0, optical_mount.EAR_THICKNESS + 0.01, 3.8),
            optical_mount.EAR_THICKNESS,
        ),
        (
            "optical_tray_deck_thickness",
            "OpticalSensorTray",
            (0, 4, optical_mount.TRAY_BOTTOM_Z - 0.01),
            (0, 4, optical_mount.TRAY_TOP_Z + 0.01),
            optical_mount.TRAY_TOP_Z - optical_mount.TRAY_BOTTOM_Z,
        ),
    ]
    analytic.extend(stack_interface.manufacturing_wall_probes(doc))
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
    exception = str(getattr(registry.RailSegments[0], "ManufacturingException", ""))
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
            "printed_role_deck_or_shoe_count": 0,
            "purchased_carbon_plates": [
                stock_adapter.mounting_contract(kind) for kind in mounts.MOUNT_NAMES
            ],
            "carbon_scope": "Purchased laminate is not part of the PA12 wall screen. Its filled square CAD is a collision envelope, not proof of material/contact at undimensioned cutouts. Received support lands, fastener bearing, insulation, flatness and strength remain unqualified.",
            "independent_optical_mount_contract": optical_mount.mount_contract(),
        },
        "rail_functional_flexure_exception": exception,
        "supplier_acceptance_status": "Not yet confirmed: 1.2 mm narrow flexure, tape wings and one-piece manufacture require quote review.",
        "opposed_planar_face_screen": probes,
        "actual_feature_measurements": measurements,
        "wall_screen_limits": "Sampled opposed planar faces and explicit line probes only. Fillet/taper/cylindrical transitions are not exhaustively certified as a global minimum-wall field. No strength or fatigue qualification.",
        "powder_removal": "Open rail channel, through nut entries, open support arms and through journals; depowder before installing hardware. No sealed hollow print is claimed.",
        "tolerance": {
            "dimensional_percent": 0.3,
            "minimum_absolute_mm": 0.3,
            "rail_fit": rail.fit_contract(),
            "not_a_GDT_position_or_actual_fit_guarantee": True,
        },
        "blanket_guide_compliance_claimed": False,
        "passed": bool(exception)
        and "1.2mm" in exception
        and all(row["no_detected_planar_wall_under_1p5mm"] for row in probes)
        and all(row["passed"] for row in measurements),
    }
