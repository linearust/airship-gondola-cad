"""Common bought carbon plates and independent FC shaft bolts.

The rail owns the two16mm plate clamps. No printed equipment saddle is added.
Only published nominal holes are cut in the conservative external envelope;
its filled regions do not qualify the received laminate's contact or strength.
"""

import json

import FreeCAD as App
import Part

from gondola.cad import box, set_property
from gondola.contracts import fasteners
from gondola.contracts import stack_adapter as specification

from . import purchased_hardware

V = App.Vector
PLATE_BOTTOM_Z = 7.0
PLATE_TOP_Z = PLATE_BOTTOM_Z + specification.THICKNESS_MM
FC_BOLT_LENGTH_MM = 20.0
PORTAL_FOOT_THICKNESS_MM = 2.0
PLATE_OBJECT_NAME = "StockFCAdapter"
BOLT_OBJECT_NAMES = tuple(f"FCAdapterBolt{index}" for index in range(4))
NUT_OBJECT_NAMES = tuple(f"FCAdapterNut{index}" for index in range(4))
MOUNT_KINDS = ("battery", "electronics", "accessory")
CARRIER_SPECS = tuple(
    {
        "key": key,
        "kind": kind,
        "role": role,
        "parent_name": parent,
        "plate_name": name,
        "local_centre_xy": centre,
        "plate_thickness_mm": specification.THICKNESS_MM,
        "parent_z_mm": 0.0,
        "clamp_prefix": name,
        "covering_devices": devices,
    }
    for key, kind, role, parent, name, centre, devices in (
        (
            "battery",
            "battery",
            "battery",
            "BatteryEquipmentModule",
            "StockBatteryAdapter",
            (0.0, 0.0),
            ("ModuleBatteryEnvelope",),
        ),
        (
            "electronics",
            "electronics",
            "flight_controller",
            "ElectronicsEquipmentModule",
            PLATE_OBJECT_NAME,
            (0.0, 0.0),
            ("ModuleFCEnvelope",),
        ),
        (
            "navigation",
            "accessory",
            "navigation",
            "AccessoryEquipmentModule",
            "StockNavigationAdapter",
            (24.0, 0.0),
            ("ModulePASEnvelope",),
        ),
        (
            "radio",
            "accessory",
            "radio",
            "AccessoryEquipmentModule",
            "StockRadioAdapter",
            (-22.0, 0.0),
            ("ModuleRadioEnvelope",),
        ),
    )
)


def joint_specs():
    """All four source-authoritative bought-plate/rail joints, excluding propulsion."""
    return [dict(row) for row in CARRIER_SPECS]


def plate_instances(kind):
    """Fresh rows in the equipment group's local frame, not world station X."""
    if kind not in MOUNT_KINDS:
        raise ValueError("Unknown carbon-plate region: " + str(kind))
    return [
        {
            "name": row["plate_name"],
            "role": row["role"],
            "kind": kind,
            "centre_xy_mm": row["local_centre_xy"],
        }
        for row in CARRIER_SPECS
        if row["kind"] == kind
    ]


def plate_shape(bottom=PLATE_BOTTOM_Z, centre_xy_mm=(0.0, 0.0)):
    """One bought external envelope; missing cutouts must not imply support."""
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
    shape.translate(V(*centre_xy_mm, 0))
    return shape.removeSplitter()


def mounting_contract(kind="electronics", with_portal=False):
    if with_portal and kind != "electronics":
        raise ValueError("FC shared-stud state only applies to the electronics plate")
    return {
        "purchased_plate": specification.stack_adapter_contract(),
        "kind": kind,
        "instances": plate_instances(kind),
        "plate_bottom_z_mm": PLATE_BOTTOM_Z,
        "plate_top_z_mm": PLATE_TOP_Z,
        "rail_fix_centres_relative_to_each_plate_mm": specification.RAIL_FIX_CENTRES,
        "rail_clamps_owned_by": "gondola.parts.rail",
        "rail_clamping": "Two downward owned-kit M2x6 screws per plate at opposed16mm Y axes. Ordinary M2 nuts bear under the open-bottom rail roof. No separate printed saddle, rail shoe or lateral set screw. The rail contract defines nut insertion, finished capture fit, bearing and bounded trim.",
        "fc_portal_installed": bool(with_portal),
        "fc_fasteners": {
            "quantity": 4,
            "centres_xy_mm": specification.COMMON_HOLE_CENTRES,
            "bolt": "Owned-kit M2x20, upwards from the carbon underside",
            "bolt_length_mm": FC_BOLT_LENGTH_MM,
            "bolt_bearing_z_mm": PLATE_BOTTOM_Z,
            "bolt_tip_z_mm": PLATE_BOTTOM_Z + FC_BOLT_LENGTH_MM,
            "nut": "Ordinary M2 intermediate nuts; X-axis pair moves above the optional2mm portal feet",
            "nut_bottom_z_by_axis_mm": [
                PLATE_TOP_Z
                + (PORTAL_FOOT_THICKNESS_MM if with_portal and abs(x) > 1 else 0)
                for x, _ in specification.COMMON_HOLE_CENTRES
            ],
        }
        if kind == "electronics"
        else None,
        "load_path": "Equipment or optional light portal -> bought carbon laminate -> two16mm rail clamps/contact strips -> paired PA12 tracks -> tape pads. Propulsion uses its own PA12 bridge; the purchased plate is not qualified for propulsion or tether loads.",
        "clamping": "Carbon-to-rail clamping is independent of all FC damping. The four25.5mm bolts clamp rigidly to carbon with intermediate nuts. When a portal is present, only its twoX-axis feet share those studs and nuts; do not add duplicate studs or compress PCB/silicone as a rigid stop.",
        "upper_stack": "Maintain8mm from carbon top to lowest FC component. The actual PCB bearing plane, insulating spacers, supplied damper compression, upper retention and final screw length remain unverified. M2x20 is a modeled lower-stack allocation, not guaranteed complete FC fastening.",
        "service": "Preassemble FC shaft bolts/intermediate nuts on the loose plate. Remove the FC before reaching its two covered rail-clamp heads from above. The rail's open-bottom guides do not retain unbolted nuts; support nuts while starting screws and keep them threaded during permitted fine trim. Disconnect wires before relocating a plate.",
        "contact_scope": "Use published holes, not undimensioned cutouts, as axes. Known20mm holes already interrupt some potential16mm bearing material. The filled square is only a conservative collision envelope; actual contact lands, flatness, anti-rock support, laminate bending, rail-roof retention, preload and creep need physical verification. Carbon is conductive and requires electrical insulation.",
        "installed_pattern_scope": "The16mm Y pair attaches each plate to its rail bay. Four25.5mm axes support FC bolts and selected optional portal feet. The20mm pattern is not assigned an installed function. Factory patterns do not imply simultaneous hardware compatibility.",
        "physical_fit_verified": False,
    }


def _placed(shape, x, y, z):
    placed = shape.copy()
    placed.translate(V(x, y, z))
    return placed


def fc_hardware_rows(with_portal=False):
    """Four upward FC bolts and four independently seated intermediate nuts."""
    contract = mounting_contract("electronics", with_portal)
    rows = []
    for index, (x, y) in enumerate(specification.COMMON_HOLE_CENTRES):
        nut_bottom = PLATE_TOP_Z + (
            PORTAL_FOOT_THICKNESS_MM if with_portal and abs(x) > 1 else 0
        )
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
                    "joint": "FC/optional-portal-to-carbon",
                    "notes": contract["upper_stack"],
                },
                {
                    "name": NUT_OBJECT_NAMES[index],
                    "label": "BUY | M2 intermediate nut | rigid FC/portal clamp",
                    "shape": _placed(
                        purchased_hardware.hex_nut_shape(), x, y, nut_bottom
                    ),
                    "sku": "M2_HEX_NUT",
                    "joint": "FC/optional-portal-to-carbon",
                    "notes": contract["clamping"] + " " + contract["contact_scope"],
                },
            )
        )
    return rows


def hardware_shapes(kind=None, *, with_portal=False):
    """Stock shapes only; rail clamps and optional printed portals are separate."""
    kinds = MOUNT_KINDS if kind is None else (kind,)
    if with_portal and "electronics" not in kinds:
        raise ValueError("FC shared-stud state requires the electronics plate")
    result = {
        row["name"]: plate_shape(centre_xy_mm=row["centre_xy_mm"])
        for region in kinds
        for row in plate_instances(region)
    }
    if "electronics" in kinds:
        result.update(
            {row["name"]: row["shape"] for row in fc_hardware_rows(with_portal)}
        )
    return result


def _set_plate_metadata(obj, row, *, with_portal=False):
    from . import equipment_mounts

    contract = mounting_contract(row["kind"], with_portal)
    set_property(obj, "StockAdapterContract", json.dumps(contract, sort_keys=True))
    set_property(
        obj,
        "MountContract",
        json.dumps(equipment_mounts.mount_contract(row["kind"]), sort_keys=True),
    )
    set_property(obj, "MountKind", row["kind"])
    set_property(obj, "PlateRole", row["role"])
    set_property(
        obj, "PlateCentreXY", V(*row["centre_xy_mm"], 0), "App::PropertyVector"
    )
    set_property(obj, "EquipmentFaceZ", PLATE_TOP_Z, "App::PropertyLength")
    set_property(obj, "FCPortalInstalled", bool(with_portal), "App::PropertyBool")
    set_property(
        obj, "ReferenceMassGrams", specification.LISTED_MASS_G, "App::PropertyFloat"
    )
    set_property(obj, "ReferenceMassSource", specification.PRODUCT_URL)
    set_property(
        obj,
        "ReferenceMassBasis",
        "Seller mass for one board; unmeasured and independent of conservative envelope volume",
    )
    set_property(obj, "ExactContourModeled", False, "App::PropertyBool")
    set_property(obj, "PhysicalFitVerified", False, "App::PropertyBool")
    set_property(obj, "MountingStackVerified", False, "App::PropertyBool")
    set_property(
        obj,
        "ContourScope",
        "Full30mm square and twelve nominal bores. Undimensioned waist, central hole and interior cutouts omitted; do not infer contact material from the envelope.",
    )


def build_stock_adapter(doc, parent, kind="electronics"):
    """One or two common boards, plus FC studs only in the electronics region."""
    instances = plate_instances(kind)
    names = [row["name"] for row in instances]
    if kind == "electronics":
        names.extend((*BOLT_OBJECT_NAMES, *NUT_OBJECT_NAMES))
    if any(doc.getObject(name) is not None for name in names):
        raise ValueError("Stock adapter objects already exist for " + kind)
    plates = []
    hardware = []
    for row in instances:
        contract = mounting_contract(kind)
        obj = purchased_hardware.add_hardware(
            doc,
            parent,
            row["name"],
            "BUY |30mm carbon adapter | " + row["role"],
            plate_shape(centre_xy_mm=row["centre_xy_mm"]),
            specification.PART_SKU,
            contract["contact_scope"] + " " + contract["service"],
            specification.PRODUCT_URL,
            material="Carbon fibre composite (seller claim)",
            thread_diameter=None,
        )
        _set_plate_metadata(obj, row)
        if App.GuiUp:
            obj.ViewObject.ShapeColor = (0.18, 0.20, 0.22)
        plates.append(obj)
        hardware.append(obj)
    if kind == "electronics":
        for row in fc_hardware_rows():
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
    return {"hardware": hardware, "plates": plates}


def set_fc_portal(doc, installed):
    """Move only the two X-axis nuts above optional feet; never duplicate parts."""
    plate = doc.getObject(PLATE_OBJECT_NAME)
    if plate is None or any(
        doc.getObject(name) is None for name in (*BOLT_OBJECT_NAMES, *NUT_OBJECT_NAMES)
    ):
        raise ValueError(
            "Complete FC plate/stud assembly is required before portal attachment"
        )
    for row in fc_hardware_rows(bool(installed)):
        obj = doc.getObject(row["name"])
        obj.Shape = row["shape"]
        set_property(obj, "Notes", row["notes"])
    _set_plate_metadata(
        plate, plate_instances("electronics")[0], with_portal=bool(installed)
    )
    doc.recompute()
