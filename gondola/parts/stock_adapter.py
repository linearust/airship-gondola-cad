"""Bought carbon spans the16mm saddle and25.5mm FC axes; no invented soft stack."""

import json

import FreeCAD as App
import Part

from gondola.cad import box, set_property
from gondola.contracts import fasteners
from gondola.contracts import stack_adapter as specification

from . import purchased_hardware

V = App.Vector
SADDLE_THICKNESS_MM = 2.0
SADDLE_BOTTOM_Z = 14.3
SADDLE_STEM_SIZE_MM = (12.0, 12.0)
SADDLE_PAD_DIAMETER_MM = 5.8
SADDLE_PAD_CENTRES = specification.hole_centres(16.0, 45.0)
SADDLE_FIX_CENTRES = tuple((x, y) for x, y in SADDLE_PAD_CENTRES if abs(x) > 1)
PLATE_BOTTOM_Z = SADDLE_BOTTOM_Z + SADDLE_THICKNESS_MM
PLATE_TOP_Z = PLATE_BOTTOM_Z + specification.THICKNESS_MM
FC_BOLT_LENGTH_MM = 20.0
SADDLE_BOLT_LENGTH_MM = 6.0
PLATE_OBJECT_NAME = "StockFCAdapter"
BOLT_OBJECT_NAMES = tuple(f"FCAdapterBolt{index}" for index in range(4))
NUT_OBJECT_NAMES = tuple(f"FCAdapterNut{index}" for index in range(4))
SADDLE_BOLT_OBJECT_NAMES = tuple(f"FCAdapterSaddleBolt{index}" for index in range(2))
SADDLE_NUT_OBJECT_NAMES = tuple(f"FCAdapterSaddleNut{index}" for index in range(2))


def plate_shape(bottom=PLATE_BOTTOM_Z):
    """Conservative filled outline with only the published mounting bores."""
    width, length = specification.OUTER_SIZE_MM
    shape = box(
        width, length, specification.THICKNESS_MM, (-width / 2, -length / 2, bottom)
    )
    for pitch in specification.SQUARE_PITCHES_MM:
        for x, y in specification.hole_centres(pitch):
            shape = shape.cut(
                Part.makeCylinder(
                    specification.HOLE_DIAMETER_MM / 2,
                    specification.THICKNESS_MM + 2,
                    V(x, y, bottom - 1),
                )
            )
    shape.rotate(V(), V(0, 0, 1), specification.COMMON_ROTATION_DEG)
    return shape.removeSplitter()


def mounting_contract():
    return {
        "purchased_plate": specification.stack_adapter_contract(),
        "plate_bottom_z_mm": PLATE_BOTTOM_Z,
        "plate_top_z_mm": PLATE_TOP_Z,
        "saddle_bottom_z_mm": SADDLE_BOTTOM_Z,
        "printed_saddle_thickness_mm": SADDLE_THICKNESS_MM,
        "saddle_stem_size_mm": SADDLE_STEM_SIZE_MM,
        "saddle_pad_centres_xy_mm": SADDLE_PAD_CENTRES,
        "saddle_pad_diameter_mm": SADDLE_PAD_DIAMETER_MM,
        "saddle_fix_centres_xy_mm": SADDLE_FIX_CENTRES,
        "saddle_rigid_grip_mm": SADDLE_THICKNESS_MM + specification.THICKNESS_MM,
        "saddle_fasteners": {
            "quantity": 2,
            "bolt": "Owned-kit M2x6, heads above carbon, shafts downwards",
            "bolt_length_mm": SADDLE_BOLT_LENGTH_MM,
            "bolt_bearing_z_mm": PLATE_TOP_Z,
            "bolt_tip_z_mm": PLATE_TOP_Z - SADDLE_BOLT_LENGTH_MM,
            "nut": "Ordinary M2 hex nut below the printed pad",
            "nut_bottom_z_mm": SADDLE_BOTTOM_Z - fasteners.HEX_NUT_HEIGHT,
            "nominal_tip_projection_beyond_nut_mm": SADDLE_BOLT_LENGTH_MM
            - SADDLE_THICKNESS_MM
            - specification.THICKNESS_MM
            - fasteners.HEX_NUT_HEIGHT,
            "tip_projection_with_print_plus0_3_carbon_plus0_1_screw_minus0_3_mm": SADDLE_BOLT_LENGTH_MM
            - 0.3
            - SADDLE_THICKNESS_MM
            - 0.3
            - specification.THICKNESS_MM
            - 0.1
            - fasteners.HEX_NUT_HEIGHT,
            "projection_scope": "Conditional dimensional allowances, not measured supplier tolerances. Verify full nut engagement and received bolt length before tightening.",
        },
        "fc_fasteners": {
            "quantity": 4,
            "centres_xy_mm": specification.COMMON_HOLE_CENTRES,
            "bolt": "Owned-kit M2x20, upwards from the carbon underside",
            "bolt_length_mm": FC_BOLT_LENGTH_MM,
            "bolt_bearing_z_mm": PLATE_BOTTOM_Z,
            "bolt_tip_z_mm": PLATE_BOTTOM_Z + FC_BOLT_LENGTH_MM,
            "nut": "Ordinary M2 intermediate nut against the carbon upper face",
            "nut_bottom_z_mm": PLATE_TOP_Z,
        },
        "load_path": "FC soft support -> four25.5mm bought-plate axes -> carbon laminate -> two opposed16mm saddle clamps and four printed contact pads ->12x12mm stem -> integral rail shoe. The carbon spans the outer FC axes; no printed outer frame duplicates that span.",
        "clamping": "Two reversed16mm screws clamp carbon to PA12. Four separate25.5mm bolts clamp to carbon with intermediate nuts below the FC. Neither rigid joint uses PCB or silicone compression as its stop.",
        "upper_stack": "The four20mm shafts allow separately retained insulating spacers and supplied FC dampers. Actual PCB bearing plane, sleeve compression, upper hardware and required final screw length remain unverified. Keep the lowest component envelope8mm above carbon;20mm is not a guaranteed complete FC mounting length.",
        "service": "Remove the carrier from the rail and the FC before servicing its carbon plate. Lower16mm screws are reached from above; hold their exposed nuts from the outboardX sides, then remove the screws before sliding the nuts out. A provisional2mm-thick fine-jaw tool fits below the support pads while gripping the lower part of the nut flats; actual tool fit remains unverified. Do not attempt sideways shaft insertion through a closed bore.",
        "contact_scope": "Published hole axes locate the joint; the full square is only a clearance envelope. Even the known neighboring20mm bores interrupt the theoretical16mm carbon contact annuli; undimensioned cutouts add uncertainty. The printed pads have complete1.6mm radial lands, but continuous carbon bearing rings are not claimed. Inspect received support contact, flatness, rocking and loaded retention at all four pads. Nominal2mm bores do not guarantee free-running M2 fit. Laminate strength, stiffness, torque, creep and electrical insulation remain unqualified.",
        "installed_pattern_scope": "The16mm pattern attaches the saddle at its twoX axes; the unboltedY pads provide contact surfaces. The25.5mm pattern mounts the FC. The factory20mm holes remain visible but have no qualified installed use. The existing clamps and contact pads prevent any universal simultaneous-pattern claim.",
        "tradeoff": "Two additional M2x6 screws and two existing-type M2 nuts make the carbon structurally useful. A nominal design-envelope comparison adds about1.17g including roughly0.107cm3 extraPA12; this is not a measured mass or a stiffness qualification.",
        "physical_fit_verified": False,
    }


def _placed(shape, x, y, z, *, reversed_axis=False):
    placed = shape.copy()
    if reversed_axis:
        placed.rotate(V(), V(1, 0, 0), 180)
    placed.translate(V(x, y, z))
    return placed


def fc_hardware_rows():
    """Four plate-mounted shaft bolts and independent intermediate nuts."""
    contract = mounting_contract()
    rows = []
    for index, (x, y) in enumerate(specification.COMMON_HOLE_CENTRES):
        rows.extend(
            (
                {
                    "name": BOLT_OBJECT_NAMES[index],
                    "label": "BUY | M2x20 FC bolt | upper soft stack unverified",
                    "shape": _placed(
                        purchased_hardware.screw_shape(FC_BOLT_LENGTH_MM),
                        x,
                        y,
                        PLATE_BOTTOM_Z,
                    ),
                    "sku": "M2X20_BUTTON_HEAD",
                    "joint": "FC-to-carbon",
                    "notes": contract["upper_stack"],
                },
                {
                    "name": NUT_OBJECT_NAMES[index],
                    "label": "BUY | M2 intermediate nut | rigid FC-bolt clamp",
                    "shape": _placed(
                        purchased_hardware.hex_nut_shape(), x, y, PLATE_TOP_Z
                    ),
                    "sku": "M2_HEX_NUT",
                    "joint": "FC-to-carbon",
                    "notes": contract["clamping"] + " " + contract["contact_scope"],
                },
            )
        )
    return rows


def saddle_hardware_rows():
    """Two opposite16mm reversed bolts; ordinary exposed nuts below the pads."""
    contract = mounting_contract()
    rows = []
    for index, (x, y) in enumerate(SADDLE_FIX_CENTRES):
        rows.extend(
            (
                {
                    "name": SADDLE_BOLT_OBJECT_NAMES[index],
                    "label": "BUY | M2x6 reversed carbon-to-saddle screw",
                    "shape": _placed(
                        purchased_hardware.screw_shape(SADDLE_BOLT_LENGTH_MM),
                        x,
                        y,
                        PLATE_TOP_Z,
                        reversed_axis=True,
                    ),
                    "sku": "M2X6_BUTTON_HEAD",
                    "joint": "carbon-to-saddle",
                    "notes": contract["clamping"] + " " + contract["service"],
                },
                {
                    "name": SADDLE_NUT_OBJECT_NAMES[index],
                    "label": "BUY | M2 exposed nut | carbon-to-saddle clamp",
                    "shape": _placed(
                        purchased_hardware.hex_nut_shape(),
                        x,
                        y,
                        SADDLE_BOTTOM_Z - fasteners.HEX_NUT_HEIGHT,
                    ),
                    "sku": "M2_HEX_NUT",
                    "joint": "carbon-to-saddle",
                    "notes": contract["service"] + " " + contract["contact_scope"],
                },
            )
        )
    return rows


def lower_hardware_rows():
    """All twelve structural fasteners below the unmodeled FC soft mounting."""
    return fc_hardware_rows() + saddle_hardware_rows()


def hardware_shapes():
    """Native local shapes; the bought plate remains an approximate envelope."""
    return {
        PLATE_OBJECT_NAME: plate_shape(),
        **{row["name"]: row["shape"] for row in lower_hardware_rows()},
    }


def build_stock_adapter(doc, parent):
    """Return one bought plate and twelve structural fasteners for the BOM."""
    contract = mounting_contract()
    plate = purchased_hardware.add_hardware(
        doc,
        parent,
        PLATE_OBJECT_NAME,
        "BUY |30mm carbon FC stack adapter | conservative contour",
        plate_shape(),
        specification.PART_SKU,
        contract["contact_scope"] + " " + contract["upper_stack"],
        specification.PRODUCT_URL,
        material="Carbon fibre composite (seller claim)",
        thread_diameter=None,
    )
    set_property(plate, "StockAdapterContract", json.dumps(contract, sort_keys=True))
    set_property(
        plate, "ReferenceMassGrams", specification.LISTED_MASS_G, "App::PropertyFloat"
    )
    set_property(plate, "ReferenceMassSource", specification.PRODUCT_URL)
    set_property(
        plate,
        "ReferenceMassBasis",
        "Seller mass for one board; unmeasured and independent of conservative envelope volume",
    )
    set_property(plate, "ExactContourModeled", False, "App::PropertyBool")
    set_property(plate, "PhysicalFitVerified", False, "App::PropertyBool")
    set_property(
        plate,
        "ContourScope",
        "Full30mm square and twelve published nominal bores. Undimensioned waist, central hole and interior cutouts intentionally omitted; do not infer contact material from the envelope.",
    )
    if App.GuiUp:
        plate.ViewObject.ShapeColor = (0.18, 0.20, 0.22)
    hardware = [plate]
    for row in lower_hardware_rows():
        obj = purchased_hardware.add_hardware(
            doc,
            parent,
            row["name"],
            row["label"],
            row["shape"],
            row["sku"],
            row["notes"],
            fasteners.KIT_SOURCE,
            material=fasteners.KIT_MATERIAL,
        )
        set_property(obj, "StructuralJoint", row["joint"])
        hardware.append(obj)
    return {"hardware": hardware}
