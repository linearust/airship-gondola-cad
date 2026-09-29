"""Independent optical rail shoe; one native longitudinal station control."""

import json

import FreeCAD as App

from gondola.cad import box, set_property

from . import rail

DEFAULT_STATION_X = 144.0
DIRECT_POWER_STATION_X = 158.0


def placement(station_x=DEFAULT_STATION_X, clamp_shift_y=rail.CLAMP_SHIFT_Y):
    return App.Placement(App.Vector(station_x, clamp_shift_y, 0), App.Rotation())


def interface_contract():
    return {
        "mechanism": "Integral common T-rail shoe and straight centred pitch support",
        "industry_standard_claimed": False,
        "native_position_control": "OpticalFlowModule.RailPositionX",
        "default_station_x_mm": DEFAULT_STATION_X,
        "direct_tether_station_x_mm": DIRECT_POWER_STATION_X,
        "nominal_lateral_offset_mm": rail.CLAMP_SHIFT_Y,
        "hardware": "One M2x8 button-head screw and ordinary M2 nut lock the rail shoe; one identical pair locks the pitch ears. No separate carrier foot or washers.",
        "relocation": "Slide on the same rail and seat against its solid T-head land. Recheck all physical, wire and optical reserves after moving; arbitrary stations or equipment combinations are not prequalified.",
        "service": "Disconnect the optical lead, release the rail screw and slide the module off the rail end, removing intervening modules first. Bench-support before loosening the pitch joint. Balloon and connected-harness service are not modeled.",
        "qualification": "Nominal rail fit and geometry only. Actual print fit, clamp friction, PA12 creep, adhesive retention and optical pointing remain unqualified.",
    }


def annotate_interface(obj):
    set_property(
        obj,
        "OpticalInterfaceContract",
        json.dumps(interface_contract(), sort_keys=True),
    )
    set_property(obj, "OpticalFitVerified", False, "App::PropertyBool")


def manufacturing_wall_probes():
    from . import optical_mount as mount

    x, y, z = mount.PIVOT_CENTRE
    return [
        (
            "optical_upright_thickness",
            "OpticalMountBase",
            (x, y - mount.EAR_THICKNESS - 0.01, 23),
            (x, y + 0.01, 23),
            mount.EAR_THICKNESS,
        ),
        (
            "optical_fixed_pivot_ear",
            "OpticalMountBase",
            (x, y - mount.EAR_THICKNESS - 0.01, z + 2.5),
            (x, y + 0.01, z + 2.5),
            mount.EAR_THICKNESS,
        ),
    ]


def base_component_proxies():
    """Keep the open T-channel out of service and neighbouring-part envelopes."""
    from . import optical_mount as mount

    x, y, z = mount.PIVOT_CENTRE
    return [
        ("rail_shoe", rail.shoe_shape()),
        ("upright", mount.upright_shape()),
        (
            "fixed_pitch_ear",
            box(
                2 * mount.EAR_RADIUS,
                mount.EAR_THICKNESS,
                2 * mount.EAR_RADIUS,
                (x - mount.EAR_RADIUS, y - mount.EAR_THICKNESS, z - mount.EAR_RADIUS),
            ),
        ),
    ]
