"""Connected wiring and connector-access allowances, never physical cable models.

Catalog housing dimensions do not locate a connector on its PCB. Whole-edge
lanes preserve room while actual plugs, pinouts, wire bundles and bends remain
to be checked on the selected equipment.
"""

import copy
import math

import FreeCAD as App
import Part

from . import equipment_mounts as mounts
from . import mounting_interfaces as interfaces

V = App.Vector
FC_PERIPHERAL_DEPTH_MM = 5.0
FC_PERIPHERAL_Z_MARGIN_MM = 1.0
FC_EXIT_BUNDLE_DIAMETER_MM = 3.0
FC_EXIT_BEND_RADIUS_MM = 5.0
FC_MINIMUM_NEIGHBOUR_GAP_MM = 1.0
PAS_CONNECTOR_TRAVEL_MM = 15.0
LR_CONNECTOR_TRAVEL_MM = 15.0
XT30_BODY_ALLOCATION_MM = (10.0, 22.0, 15.0)
XT30_WITHDRAWAL_ALLOWANCE_MM = 10.0


def _box(size, origin):
    return Part.makeBox(*size, V(*origin))


def _fc_exit_tube(side):
    """A C1 continuous quarter-turn around each end of the underbody corridor."""
    y = mounts.FC_WIRING_CORRIDOR_CENTRE_Y
    z = mounts.SUPPORT_FACE_Z + mounts.FC_WIRING_CLEARANCE / 2
    radius = FC_EXIT_BEND_RADIUS_MM
    turn = -side
    start, bend_start = V(side * 20, y, z), V(side * 24, y, z)
    middle = V(
        side * (24 + radius / math.sqrt(2)),
        y + turn * radius * (1 - 1 / math.sqrt(2)),
        z,
    )
    bend_end = V(side * (24 + radius), y + turn * radius, z)
    end = V(bend_end.x, bend_end.y + turn * 8, z)
    path = Part.Wire(
        [
            Part.makeLine(start, bend_start),
            Part.Arc(bend_start, middle, bend_end).toShape(),
            Part.makeLine(bend_end, end),
        ]
    )
    section = Part.Wire(
        Part.makeCircle(FC_EXIT_BUNDLE_DIAMETER_MM / 2, start, V(side, 0, 0))
    )
    return path.makePipeShell([section], True, False)


def _fc_peripheral_band():
    length, width, height = interfaces.FC_SIZE_MM
    bottom = mounts.SUPPORT_FACE_Z + mounts.FC_WIRING_CLEARANCE
    depth, margin = FC_PERIPHERAL_DEPTH_MM, FC_PERIPHERAL_Z_MARGIN_MM
    outer = _box(
        (length + 2 * depth, width + 2 * depth, height + 2 * margin),
        (-length / 2 - depth, -width / 2 - depth, bottom - margin),
    )
    inner = _box(
        (length, width, height + 4 * margin),
        (-length / 2, -width / 2, bottom - 2 * margin),
    )
    band = outer.cut(inner)
    band.rotate(V(), V(0, 0, 1), mounts.FC_ROTATION_DEG)
    band.translate(V(*mounts.FC_CENTRE_XY, 0))
    return band


def reserve_shapes():
    """Return fresh local shapes in the electronics module's coordinate frame."""
    core = mounts.fc_wiring_reserve_shape()
    fc = core.multiFuse(
        [_fc_peripheral_band(), _fc_exit_tube(-1), _fc_exit_tube(1)]
    ).removeSplitter()
    bottom = mounts.SUPPORT_FACE_Z + mounts.ADHESIVE_ALLOWANCE
    lr_x, lr_y = mounts.LR_CENTRE_XY
    lr_length, lr_width, lr_height = interfaces.LR_SIZE_MM
    pas_x, pas_y = mounts.PAS_CENTRE_XY
    pas_width = interfaces.DEVICE_CONNECTOR_EVIDENCE["PAS"]["connector_band_width_mm"]
    xt30_x, xt30_y, xt30_z = XT30_BODY_ALLOCATION_MM
    shapes = {
        "FCWiringClearanceReserve": fc,
        "XT30ServiceReserve": _box(
            (xt30_x, xt30_y + 2 * XT30_WITHDRAWAL_ALLOWANCE_MM, xt30_z),
            (-44, -xt30_y / 2 - XT30_WITHDRAWAL_ALLOWANCE_MM, bottom),
        ),
        "LR900NegativeXConnectorReserve": _box(
            (LR_CONNECTOR_TRAVEL_MM, lr_width, lr_height),
            (
                lr_x - lr_length / 2 - LR_CONNECTOR_TRAVEL_MM,
                lr_y - lr_width / 2,
                bottom,
            ),
        ),
        "LR900PositiveXConnectorReserve": _box(
            (LR_CONNECTOR_TRAVEL_MM, lr_width, lr_height),
            (lr_x + lr_length / 2, lr_y - lr_width / 2, bottom),
        ),
        "PASConnectorReserve": _box(
            (pas_width, PAS_CONNECTOR_TRAVEL_MM, interfaces.PAS_SIZE_MM[2]),
            (
                pas_x - pas_width / 2,
                pas_y - interfaces.PAS_SIZE_MM[1] / 2 - PAS_CONNECTOR_TRAVEL_MM,
                mounts.SUPPORT_FACE_Z + mounts.PAS_SERVICE_CLEARANCE,
            ),
        ),
    }
    for name, shape in shapes.items():
        if not shape.isValid() or len(shape.Solids) != 1:
            raise RuntimeError("Wiring reservation is not one connected solid: " + name)
    return shapes


def device_connector_contract(key):
    evidence = interfaces.DEVICE_CONNECTOR_EVIDENCE[key]
    return {
        "device": key,
        "source_url": evidence["sources"][0],
        "device_connector_evidence": copy.deepcopy(evidence),
        "connector_catalog_evidence": {
            name: copy.deepcopy(interfaces.CONNECTOR_EVIDENCE[name])
            for name in evidence["catalog_references"]
        },
        "installed_connector_fit_verified": False,
        "installed_port_datums_verified": False,
        "withdrawal_stroke_verified": False,
        "wire_bend_radius_qualified": False,
        "complete_connected_harness_modeled": False,
        "service_prerequisite": "Disconnect external leads before lifting devices or sliding modules; bare-device removal tests do not prove removal with a connected harness.",
    }


def reserve_contracts():
    """Attach measured evidence and explicitly unverified design allowances."""
    fc = {
        **device_connector_contract("FC"),
        "operating_scope": "Connected peripheral housing space, underbody corridor and two continuous exit turns. No individual port centre, exact plug or cable is modeled.",
        "peripheral_normal_depth_mm": FC_PERIPHERAL_DEPTH_MM,
        "peripheral_z_margin_mm": FC_PERIPHERAL_Z_MARGIN_MM,
        "underbody_height_mm": mounts.FC_WIRING_CLEARANCE,
        "underbody_corridor_width_mm": mounts.FC_WIRING_CORRIDOR_WIDTH,
        "design_exit_bundle_diameter_mm": FC_EXIT_BUNDLE_DIAMETER_MM,
        "design_exit_centreline_bend_radius_mm": FC_EXIT_BEND_RADIUS_MM,
        "minimum_neighbour_gap_mm": FC_MINIMUM_NEIGHBOUR_GAP_MM,
        "withdrawal_scope": "The 5mm peripheral band is housing room only, not a complete unplug stroke or grip/latch-access proof. The 3mm bundle and 5mm bend are planning choices, not wire specifications.",
        "ventilation_limit": "Reserved volume is not permission to cover ESC MOS regions; route actual wires with cooling, insulation and strain relief checked.",
    }
    xt30 = {
        "device": "XT30U pigtail",
        "source_url": interfaces.CONNECTOR_EVIDENCE["AMASS_XT30U"]["source"],
        "connector_catalog_evidence": copy.deepcopy(
            interfaces.CONNECTOR_EVIDENCE["AMASS_XT30U"]
        ),
        "selected_mating_axis": "Y",
        "maximum_mated_body_xyz_mm": [5.9, 20.6, 10.5],
        "body_allocation_xyz_mm": list(XT30_BODY_ALLOCATION_MM),
        "design_withdrawal_allowance_each_y_mm": XT30_WITHDRAWAL_ALLOWANCE_MM,
        "operating_scope": "A 10x22x15mm body allocation contains the catalog maximum mated envelope in the chosen orientation; soldered wires, insulation and mounting remain unmodeled.",
        "withdrawal_scope": "Continuous 10mm extension at both Y ends. This is our pull/lead allowance, not a published withdrawal stroke or a proven retained pigtail.",
        "installed_connector_fit_verified": False,
        "withdrawal_stroke_verified": False,
        "wire_bend_radius_qualified": False,
        "complete_connected_harness_modeled": False,
    }
    lr = {
        **device_connector_contract("LR"),
        "edge_width_mm": interfaces.LR_SIZE_MM[1],
        "edge_height_mm": interfaces.LR_SIZE_MM[2],
        "design_outward_travel_mm": LR_CONNECTOR_TRAVEL_MM,
        "operating_scope": "Reserve both complete ends of the long body axis; exact GH/USB/SMA coordinates and which installed end faces +X are unverified.",
        "withdrawal_scope": "Continuous 15mm end lanes are design access allowances, not a measured plug stroke or an antenna keepout. Actual SMA socket/antenna and USB plug dimensions remain required.",
    }
    return {
        "FCWiringClearanceReserve": fc,
        "XT30ServiceReserve": xt30,
        "LR900NegativeXConnectorReserve": {**copy.deepcopy(lr), "outward_axis": "-X"},
        "LR900PositiveXConnectorReserve": {**copy.deepcopy(lr), "outward_axis": "+X"},
        "PASConnectorReserve": {
            **device_connector_contract("PAS"),
            "outward_axis": "-Y",
            "edge_width_mm": interfaces.DEVICE_CONNECTOR_EVIDENCE["PAS"][
                "connector_band_width_mm"
            ],
            "edge_height_mm": interfaces.PAS_SIZE_MM[2],
            "design_outward_travel_mm": PAS_CONNECTOR_TRAVEL_MM,
            "operating_scope": "Use the side-entry GH port at the documented connector end. Cover the entire 19mm central connector band because individual XYZ are unpublished.",
            "withdrawal_scope": "Continuous 15mm lane is a design allowance. The parallel top-entry alternative is not allocated here; use one port and verify latch access and the selected cable.",
        },
    }
