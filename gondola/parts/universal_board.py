"""One interchangeable open-grid board, with purchased metric stacking.

The battery, flight-controller and upper equipment levels use the same solid.
Only the common rail clamp and four M3 clearance holes are built into the part;
there are no device-specific posts, custom printed threads or battery features.
"""

import functools
import math

import FreeCAD as App
import MeshPart
import Part

from gondola.cad import set_property

V = App.Vector
BOARD_X, BOARD_Y, BOARD_THICKNESS, BOARD_BOTTOM = 64.0, 76.0, 2.0, 10.2
RIB, RIM, COLUMNS, ROWS = 1.6, 2.4, 5, 6
STACK_CENTRES = ((-26.0, -32.0), (-26.0, 32.0), (26.0, -32.0), (26.0, 32.0))
STACK_HOLE_DIAMETER, STACK_PAD_DIAMETER = 4.2, 8.0
CENTRE_PATCH_X, CENTRE_PATCH_Y = 18.0, 24.0
PRINT_ROTATION = App.Rotation(V(1, 0, 0), 180)
CREALLO_SOURCE = "https://creallo.com/en/guide/design-spec-guide"


def box(dx, dy, dz, x, y, z):
    return Part.makeBox(dx, dy, dz, V(x, y, z))


@functools.lru_cache(None)
def board_shape(include_shoe=True):
    shape = box(
        BOARD_X, BOARD_Y, BOARD_THICKNESS, -BOARD_X / 2, -BOARD_Y / 2, BOARD_BOTTOM
    )
    cell_x = (BOARD_X - 2 * RIM - (COLUMNS - 1) * RIB) / COLUMNS
    cell_y = (BOARD_Y - 2 * RIM - (ROWS - 1) * RIB) / ROWS
    for ix in range(COLUMNS):
        for iy in range(ROWS):
            shape = shape.cut(
                box(
                    cell_x,
                    cell_y,
                    BOARD_THICKNESS + 2,
                    -BOARD_X / 2 + RIM + ix * (cell_x + RIB),
                    -BOARD_Y / 2 + RIM + iy * (cell_y + RIB),
                    BOARD_BOTTOM - 1,
                )
            )
    additions = [
        box(
            CENTRE_PATCH_X,
            CENTRE_PATCH_Y,
            BOARD_THICKNESS,
            -CENTRE_PATCH_X / 2,
            -CENTRE_PATCH_Y / 2,
            BOARD_BOTTOM,
        )
    ]
    additions += [
        Part.makeCylinder(
            STACK_PAD_DIAMETER / 2, BOARD_THICKNESS, V(x, y, BOARD_BOTTOM)
        )
        for x, y in STACK_CENTRES
    ]
    if include_shoe:
        from gondola.parts import rail

        additions.append(rail.shoe_shape())
    shape = shape.multiFuse(additions)
    for x, y in STACK_CENTRES:
        shape = shape.cut(
            Part.makeCylinder(
                STACK_HOLE_DIAMETER / 2, BOARD_THICKNESS + 2, V(x, y, BOARD_BOTTOM - 1)
            )
        )
    shape = shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Universal board is not one valid solid")
    return shape


def board_contract():
    return {
        "standard_part": "UniversalBoardI",
        "same_geometry_for_all_equipment": True,
        "deck_size_mm": [BOARD_X, BOARD_Y, BOARD_THICKNESS],
        "deck_bottom_z_mm": BOARD_BOTTOM,
        "equipment_face_z_mm": BOARD_BOTTOM + BOARD_THICKNESS,
        "rib_mm": RIB,
        "rim_mm": RIM,
        "grid_columns_rows": [COLUMNS, ROWS],
        "nominal_open_cell_mm": [
            (BOARD_X - 2 * RIM - (COLUMNS - 1) * RIB) / COLUMNS,
            (BOARD_Y - 2 * RIM - (ROWS - 1) * RIB) / ROWS,
        ],
        "integral_shoe_outer_bound_mm": {"x": [-9, 9], "y": [-12, 12], "z": [2, 10.2]},
        "central_structural_patch_mm": [
            CENTRE_PATCH_X,
            CENTRE_PATCH_Y,
            BOARD_THICKNESS,
        ],
        "stack_hole_centres_xy_mm": STACK_CENTRES,
        "stack_hole_diameter_mm": STACK_HOLE_DIAMETER,
        "stack_bearing_pad_diameter_mm": STACK_PAD_DIAMETER,
        "purchased_stack_thread": "M3 x0.5",
        "standoff_body_mm": 30,
        "board_pitch_mm": 32,
        "free_height_below_next_shoe_mm": 30 - (BOARD_BOTTOM - 2),
        "process": "PA12 SLS or MJF",
        "process_design_reference": {
            "source": CREALLO_SOURCE,
            "dimensional_tolerance_percent": 0.3,
            "minimum_absolute_tolerance_mm": 0.3,
            "minimum_supported_wall_mm": 0.8,
            "minimum_mating_clearance_mm": 0.3,
        },
        "nominal_diametral_M3_clearance_mm": STACK_HOLE_DIAMETER - 3,
        "minimum_diametral_clearance_if_hole_is_0p3mm_undersize_mm": STACK_HOLE_DIAMETER
        - 0.3
        - 3,
        "tolerance_note": "Ø4.2mm is an unthreaded clearance hole with extra allowance for multi-post alignment. The published tolerance is dimensional, not a GD&T true-position guarantee; verify actual hole positions and purchased fasteners.",
        "features_omitted": [
            "device-specific FC/P-AS posts",
            "printed stack threads",
            "battery strap slots",
            "hook-and-loop features",
        ],
        "rotational_symmetry": "180 degrees about the local Z axis, with symmetric rail clamp ports",
        "board_orientation": "Equipment face remains up; rail clamp screw port can be chosen on either side. This is not top-to-bottom reversibility.",
        "sls_long_thin_pa12_review": {
            "board_maximum_length_mm": 76,
            "reference_length_mm": 100,
            "reference_wall_mm": 1.5,
            "deck_thickness_mm": 2,
            "rib_width_mm": 1.6,
            "interpretation": "76mm board is assessed against the100mm entry, not the200mm-and-longer3mm entry; no strength qualification is implied.",
        },
        "scope": "Static geometric specification; no strength, adhesive, thread-torque or physical fit test is implied.",
    }


def build_board(doc, parent, name="UniversalBoardI"):
    shape = board_shape().copy()
    obj = doc.addObject("Part::Feature", name)
    obj.Label = "PRINT | universal64×76 lattice board | M3 stack + rail clamp"
    obj.Shape = shape
    if parent is not None:
        parent.addObject(obj)
    set_property(obj, "Role", "Printed universal mounting board")
    set_property(obj, "PrintPart", True, "App::PropertyBool")
    set_property(obj, "PrintSKU", "UniversalBoardI")
    set_property(obj, "StandardPartCode", "UNIVERSAL-64x76-M3-I")
    set_property(obj, "PrintProcess", "PA12 SLS or MJF")
    set_property(
        obj, "PrintRotation", PRINT_ROTATION, "App::PropertyRotation", "Printing"
    )
    oriented = shape.copy()
    oriented.rotate(V(), PRINT_ROTATION.Axis, math.degrees(PRINT_ROTATION.Angle))
    bb = oriented.optimalBoundingBox(False, False)
    set_property(
        obj,
        "PrintPlacement",
        App.Placement(V(-bb.XMin, -bb.YMin, -bb.ZMin), PRINT_ROTATION),
        "App::PropertyPlacement",
        "Printing",
    )
    set_property(obj, "PrintSupportsRequired", False, "App::PropertyBool", "Printing")
    set_property(obj, "FDMPrintValidated", False, "App::PropertyBool", "Printing")
    set_property(
        obj,
        "PrintNotes",
        "PA12 SLS or MJF part.1.6mm ribs,2mm board thickness and open cells; manufacturer packs/orients the job. "
        "Supplied orientation is for inspection/export and is not a claim of FDM support-free printing. "
        "M3 clearance holes are Ø4.2mm. Powder must be removed from the open clamp/nut pocket before assembly. "
        "Buy the metric hardware separately; do not print reference hardware.",
        group="Printing",
    )
    set_property(obj, "HalfTurnSymmetric", True, "App::PropertyBool")
    set_property(
        obj,
        "ClampDirectionSelection",
        "Use either of the two identical opposed ports; only one purchased clamp screw/nut per base module. Equipment face stays up.",
    )
    set_property(obj, "NotionReviewDate", "2026-09-20")
    set_property(
        obj,
        "Interchangeable",
        "One identical board geometry for battery, FC and upper equipment levels. The upper board retains the same unused paired rail-clamp pockets but no unnecessary clamp screw/nut.",
    )
    set_property(obj, "BoardSize", "64×76×2mm; flat equipment face at localZ12.2")
    set_property(
        obj,
        "StackHoleCentres",
        [V(x, y, BOARD_BOTTOM) for x, y in STACK_CENTRES],
        "App::PropertyVectorList",
    )
    set_property(obj, "StackHoleDiameter", STACK_HOLE_DIAMETER, "App::PropertyLength")
    set_property(obj, "StackPadDiameter", STACK_PAD_DIAMETER, "App::PropertyLength")
    set_property(obj, "RetainedMountingHoleCount", 4, "App::PropertyInteger")
    set_property(
        obj,
        "RetainedHolePurpose",
        "Four standard M3 stack positions on52×64mm pattern; no FC-specific hole pattern or custom printed threads",
    )
    set_property(
        obj,
        "Notes",
        "Integral common rail shoe replaces separate carriage. Mount equipment on the existing flat grid; no battery or adhesive-specific features. "
        "Use purchased M3×0.5 hardware for30mm clear board gap /32mm repeatable pitch. Source code regenerates dimensional variants.",
    )
    set_property(obj, "SourceURL", CREALLO_SOURCE)
    if App.GuiUp:
        obj.ViewObject.ShapeColor = (0.72, 0.81, 0.85)
        obj.ViewObject.LineColor = (0.17, 0.24, 0.28)
        obj.ViewObject.DisplayMode = "Flat Lines"
        obj.ViewObject.Visibility = True
    return obj


def validate_board(include_shoe=True):
    shape = board_shape(include_shoe)
    holes = []
    for x, y in STACK_CENTRES:
        envelope = Part.makeCylinder(1.5, BOARD_THICKNESS, V(x, y, BOARD_BOTTOM))
        holes.append(
            {
                "centre_xy_mm": [x, y],
                "M3_shaft_intersection_mm3": shape.common(envelope).Volume,
            }
        )
    rotated = shape.copy()
    rotated.rotate(V(), V(0, 0, 1), 180)
    symmetry_difference = abs(shape.cut(rotated).Volume) + abs(
        rotated.cut(shape).Volume
    )
    mesh = MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=0.05, AngularDeflection=0.12, Relative=False
    )
    bb = shape.optimalBoundingBox(False, False)
    return {
        "valid_brep": shape.isValid(),
        "single_solid": len(shape.Solids) == 1,
        "watertight_mesh": mesh.isSolid(),
        "mesh_components": mesh.countComponents(),
        "volume_cm3": shape.Volume / 1000,
        "size_mm": [bb.XLength, bb.YLength, bb.ZLength],
        "stack_hole_checks": holes,
        "nominal_rib_mm": RIB,
        "half_turn_symmetric_difference_mm3": symmetry_difference,
        "passed": shape.isValid()
        and len(shape.Solids) == 1
        and mesh.isSolid()
        and mesh.countComponents() == 1
        and symmetry_difference < 1e-6
        and all(h["M3_shaft_intersection_mm3"] < 1e-7 for h in holes),
    }


if __name__ == "__main__":
    import json

    print(
        json.dumps(
            {"contract": board_contract(), "board_checks": validate_board()}, indent=2
        ),
        flush=True,
    )
