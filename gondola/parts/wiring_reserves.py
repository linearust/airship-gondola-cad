"""Connected wiring and connector-access allowances, never physical cable models.

Catalog housing dimensions do not locate a connector on its PCB. Whole-edge
lanes preserve room while actual plugs, pinouts, wire bundles and bends remain
to be checked on the selected equipment.
"""

import copy
import math

import FreeCAD as App
import Part

from gondola.contracts import equipment_interfaces as interfaces
from gondola.contracts.design import FC_INSTALLATION_LOCAL_YAW_DEG
from gondola.contracts.equipment_options import (
    get_navigation_profile,
    get_radio_profile,
)

from . import equipment_layout as layout
from . import equipment_mounts as mounts

V = App.Vector
FC_PERIPHERAL_DEPTH_MM = 9.0
FC_PERIPHERAL_Z_MARGIN_MM = 1.0
FC_EXIT_BUNDLE_DIAMETER_MM = 3.0
FC_EXIT_BEND_RADIUS_MM = 5.0
PAS_CONNECTOR_TRAVEL_MM = 15.0
LR_CONNECTOR_TRAVEL_MM = 15.0
CONNECTOR_SIDE_MARGIN_MM = 2.0
CONNECTOR_TOP_MARGIN_MM = 2.0
CONNECTOR_SERVICE_GAP_MM = 1.5
MINIMUM_NEIGHBOUR_GAPS = {
    "FCWiringClearanceReserve": {
        "ModuleLR900Envelope": 2.0,
        "ModulePASEnvelope": 2.0,
        "XT30ServiceReserve": 2.0,
        "MTF02POpticalClearanceReserve": 1.5,
        "OpticalMountBase": 1.5,
        "CapacitorServiceReserve": 1.5,
    }
}
XT30_BODY_ALLOCATION_MM = (22.0, 10.0, 15.0)
XT30_WITHDRAWAL_ALLOWANCE_MM = 10.0
XT30_ALLOCATION_CENTRE_XY_MM = (0.0, -49.0)


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


def _orient_fc_reserve(shape):
    shape.rotate(V(*mounts.FC_CENTRE_XY, 0), V(0, 0, 1), FC_INSTALLATION_LOCAL_YAW_DEG)
    return shape


def fc_underbody_reserve_shape():
    """The underbody corridor in the selected electronics-local FC orientation."""
    return _orient_fc_reserve(mounts.fc_wiring_reserve_shape())


def direct_antenna_reserve_shape(profile=None):
    """Conservative direct-helix bound; never an invented exact antenna model.

    Allow the helix centre anywhere over the body footprint. +Z is away from
    the balloon, so this is a downward installation screen, not a sky-view or
    outdoor reception qualification. Remote upward installation is unplaced.
    """
    profile = profile or get_navigation_profile()
    antenna = profile.external_antenna
    if antenna is None:
        return None
    length, width, height = profile.size_mm
    x, y = layout.navigation_centre(profile)
    size = (length + antenna.diameter_mm, width + antenna.diameter_mm)
    return _box(
        (*size, height + antenna.length_mm),
        (
            x - size[0] / 2,
            y - size[1] / 2,
            layout.navigation_bottom(profile),
        ),
    )


def reserve_shapes(navigation_profile=None, radio_profile=None):
    """Return fresh local shapes in the electronics module's coordinate frame."""
    navigation_profile = navigation_profile or get_navigation_profile()
    radio_profile = radio_profile or get_radio_profile()
    core = mounts.fc_wiring_reserve_shape()
    fc = core.multiFuse(
        [_fc_peripheral_band(), _fc_exit_tube(-1), _fc_exit_tube(1)]
    ).removeSplitter()
    fc = _orient_fc_reserve(fc)
    bottom = mounts.SUPPORT_FACE_Z + mounts.ADHESIVE_ALLOWANCE
    lr_x, lr_y = mounts.LR_CENTRE_XY
    lr_length, lr_width, lr_height = radio_profile.size_mm
    lr_lane_size = (
        LR_CONNECTOR_TRAVEL_MM,
        lr_width + 2 * CONNECTOR_SIDE_MARGIN_MM,
        lr_height + CONNECTOR_TOP_MARGIN_MM,
    )
    lr_lane_y = lr_y - lr_width / 2 - CONNECTOR_SIDE_MARGIN_MM
    navigation_x, navigation_y = layout.navigation_centre(navigation_profile)
    navigation_width = navigation_profile.connector_band_width_mm
    xt30_x, xt30_y, xt30_z = XT30_BODY_ALLOCATION_MM
    xt30_cx, xt30_cy = XT30_ALLOCATION_CENTRE_XY_MM
    shapes = {
        "FCWiringClearanceReserve": fc,
        "XT30ServiceReserve": _box(
            (xt30_x + 2 * XT30_WITHDRAWAL_ALLOWANCE_MM, xt30_y, xt30_z),
            (
                xt30_cx - xt30_x / 2 - XT30_WITHDRAWAL_ALLOWANCE_MM,
                xt30_cy - xt30_y / 2,
                bottom,
            ),
        ),
        "LR900NegativeXConnectorReserve": _box(
            lr_lane_size,
            (
                lr_x - lr_length / 2 - LR_CONNECTOR_TRAVEL_MM,
                lr_lane_y,
                bottom,
            ),
        ),
        "LR900PositiveXConnectorReserve": _box(
            lr_lane_size,
            (lr_x + lr_length / 2, lr_lane_y, bottom),
        ),
        "PASConnectorReserve": _box(
            (
                navigation_width + 2 * CONNECTOR_SIDE_MARGIN_MM,
                PAS_CONNECTOR_TRAVEL_MM,
                navigation_profile.size_mm[2] + CONNECTOR_TOP_MARGIN_MM,
            ),
            (
                navigation_x - navigation_width / 2 - CONNECTOR_SIDE_MARGIN_MM,
                navigation_y
                - navigation_profile.size_mm[1] / 2
                - PAS_CONNECTOR_TRAVEL_MM,
                layout.navigation_bottom(navigation_profile),
            ),
        ),
    }
    antenna = direct_antenna_reserve_shape(navigation_profile)
    if antenna is not None:
        shapes["NavigationDirectAntennaReserve"] = antenna
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


def reserve_contracts(navigation_profile=None, radio_profile=None):
    """Attach measured evidence and explicitly unverified design allowances."""
    navigation_profile = navigation_profile or get_navigation_profile()
    radio_profile = radio_profile or get_radio_profile()
    fc = {
        **device_connector_contract("FC"),
        "operating_scope": "Connected peripheral housing and handling space, underbody corridor and two continuous exit turns. No individual port centre, exact plug or cable is modeled.",
        "peripheral_normal_depth_mm": FC_PERIPHERAL_DEPTH_MM,
        "peripheral_z_margin_mm": FC_PERIPHERAL_Z_MARGIN_MM,
        "underbody_height_mm": mounts.FC_WIRING_CLEARANCE,
        "underbody_corridor_width_mm": mounts.FC_WIRING_CORRIDOR_WIDTH,
        "fc_installation_local_yaw_deg": FC_INSTALLATION_LOCAL_YAW_DEG,
        "orientation_scope": "FC, underbody corridor and exit turns are clocked together180deg in the electronics carrier to retain the prior world-heading design basis. The square envelope does not establish the actual board arrow, firmware orientation or port coordinates.",
        "design_exit_bundle_diameter_mm": FC_EXIT_BUNDLE_DIAMETER_MM,
        "design_exit_centreline_bend_radius_mm": FC_EXIT_BEND_RADIUS_MM,
        "minimum_neighbour_gaps_mm": copy.deepcopy(
            MINIMUM_NEIGHBOUR_GAPS["FCWiringClearanceReserve"]
        ),
        "withdrawal_scope": f"The {FC_PERIPHERAL_DEPTH_MM:g}mm peripheral band adds handling allowance beyond the nominal SH housing length; it is not a measured installed projection, complete unplug stroke or grip/latch-access proof. The {FC_EXIT_BUNDLE_DIAMETER_MM:g}mm bundle and {FC_EXIT_BEND_RADIUS_MM:g}mm bend are planning choices, not wire specifications.",
        "ventilation_limit": "Reserved volume is not permission to cover ESC MOS regions; route actual wires with cooling, insulation and strain relief checked.",
    }
    xt30 = {
        "device": "XT30U pigtail",
        "source_url": interfaces.CONNECTOR_EVIDENCE["AMASS_XT30U"]["source"],
        "connector_catalog_evidence": copy.deepcopy(
            interfaces.CONNECTOR_EVIDENCE["AMASS_XT30U"]
        ),
        "selected_mating_axis": "X",
        "maximum_mated_body_xyz_mm": [20.6, 5.9, 10.5],
        "body_allocation_xyz_mm": list(XT30_BODY_ALLOCATION_MM),
        "body_allocation_centre_xy_in_electronics_frame_mm": list(
            XT30_ALLOCATION_CENTRE_XY_MM
        ),
        "design_withdrawal_allowance_each_x_mm": XT30_WITHDRAWAL_ALLOWANCE_MM,
        "operating_scope": "A 22x10x15mm body allocation beside the FC, opposite the radio region, contains the catalog maximum mated envelope in the chosen orientation; soldered wires, insulation and mounting remain unmodeled.",
        "withdrawal_scope": "Continuous 10mm extension at both local X ends. This is our pull/lead allowance, not a published withdrawal stroke or a proven retained pigtail.",
        "installed_connector_fit_verified": False,
        "withdrawal_stroke_verified": False,
        "wire_bend_radius_qualified": False,
        "complete_connected_harness_modeled": False,
    }
    lr = {
        **device_connector_contract(radio_profile.interface_key),
        "selected_model": radio_profile.key,
        "edge_width_mm": radio_profile.size_mm[1],
        "edge_height_mm": radio_profile.size_mm[2],
        "transverse_margin_each_side_mm": CONNECTOR_SIDE_MARGIN_MM,
        "top_service_margin_mm": CONNECTOR_TOP_MARGIN_MM,
        "design_outward_travel_mm": LR_CONNECTOR_TRAVEL_MM,
        "operating_scope": "Reserve both complete ends of the selected radio's long body axis. Actual UART, RF and any USB connector coordinates and which installed end faces +X remain unverified. The Mini has no USB; its IPEX1 mating/lead direction away from the populated face requires a separate physical check.",
        "withdrawal_scope": f"Continuous {LR_CONNECTOR_TRAVEL_MM:g}mm end lanes include {CONNECTOR_SIDE_MARGIN_MM:g}mm transverse and {CONNECTOR_TOP_MARGIN_MM:g}mm top service margins beyond the body envelope. These are planning allowances, not a measured plug stroke, latch-access proof or antenna keepout. Check actual antenna, pigtail and selected plugs.",
    }
    contracts = {
        "FCWiringClearanceReserve": fc,
        "XT30ServiceReserve": xt30,
        "LR900NegativeXConnectorReserve": {**copy.deepcopy(lr), "outward_axis": "-X"},
        "LR900PositiveXConnectorReserve": {**copy.deepcopy(lr), "outward_axis": "+X"},
        "PASConnectorReserve": {
            **device_connector_contract(navigation_profile.interface_key),
            "selected_model": navigation_profile.key,
            "outward_axis": "-Y",
            "edge_width_mm": navigation_profile.connector_band_width_mm,
            "edge_height_mm": navigation_profile.size_mm[2],
            "transverse_margin_each_side_mm": CONNECTOR_SIDE_MARGIN_MM,
            "top_service_margin_mm": CONNECTOR_TOP_MARGIN_MM,
            "design_outward_travel_mm": PAS_CONNECTOR_TRAVEL_MM,
            "operating_scope": "Reserve the source-oriented -Y connector edge: P-AS uses the documented19mm central side-entry GH band; GPS alternatives use their whole short SH edge. Individual XYZ are unpublished. Verify physical board arrow and compass/firmware orientation after installation.",
            "withdrawal_scope": f"The continuous {PAS_CONNECTOR_TRAVEL_MM:g}mm lane adds {CONNECTOR_SIDE_MARGIN_MM:g}mm at both sides of the documented connector band and {CONNECTOR_TOP_MARGIN_MM:g}mm above the body envelope for service. These are planning allowances, not measured header coordinates, latch access or withdrawal stroke."
            + (
                " The P-AS parallel top-entry alternative is not allocated here; use one port and verify the selected cable."
                if navigation_profile.key == "PAS"
                else " Verify the selected SH1.0-6P cable and its exact pin labels."
            ),
        },
    }
    if navigation_profile.external_antenna is not None:
        contracts["NavigationDirectAntennaReserve"] = {
            "device": navigation_profile.key + " direct external helix",
            "source_url": navigation_profile.external_antenna.source,
            "selected_model": navigation_profile.key,
            "antenna_reference": navigation_profile.contract()["external_antenna"],
            "direct_orientation": "+Z away from balloon; downward in flight",
            "operating_scope": "Conservative whole-footprint direct-helix planning bound: allow the antenna centre anywhere over the module rectangle, expand each horizontal side by the published antenna radius, and span from the module bottom through59.3mm beyond its top. The body and its own connector lane intentionally overlap this uncertainty bound; unscrew the direct helix before SH connector service. This is not a measured SMA seating plane, exact installed antenna or support-strength qualification.",
            "remote_installation_scope": "A remotely connected helix may face upward at a suitable reception location. Its mount, cable route/length, loss, bending, clearances and retention are unplaced and unqualified. No remote antenna position or extra printed bracket is invented.",
            "reception_scope": "The modeled direct downward installation is a mechanical option only. Prefer appropriate upward sky view when outdoor GNSS reception matters; CAD clearance does not establish RF, compass or indoor GNSS performance.",
            "installed_connector_fit_verified": False,
            "installed_port_datums_verified": False,
            "withdrawal_stroke_verified": False,
            "wire_bend_radius_qualified": False,
            "complete_connected_harness_modeled": False,
            "antenna_retention_verified": False,
        }
    return contracts
