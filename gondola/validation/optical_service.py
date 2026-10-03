"""Disconnected sensor service on the integral FC/optical carrier."""

import FreeCAD as App

from gondola.cad import world_shape

from .geometry import intersection_volume, translation_sweep

V = App.Vector
TOL = 1e-5


def mounting_service_check(doc, physical, kit):
    """Lift only the unretained sensor; the integral carrier stays installed.

    Adhesive/Velcro release and unplugging are prerequisites, not modeled actions.
    Every other physical part remains an obstacle, including unknown kit stock.
    """
    from .optical_envelopes import instrument_context

    try:
        _, _, frame, _ = instrument_context(doc.getObject("OpticalFlowModule"))
    except (AttributeError, TypeError, ValueError) as error:
        return {"error": str(error), "paths": [], "passed": False}
    expected = {"ModuleMTF02PEnvelope"}
    names = [obj.Name for obj in kit]
    physical_names = [obj.Name for obj in physical]
    missing = sorted(expected - set(names))
    extra = sorted(set(names) - expected)
    if (
        missing
        or extra
        or len(names) != 1
        or physical_names.count("ModuleMTF02PEnvelope") != 1
        or physical_names.count("ElectronicsMount") != 1
    ):
        return {
            "missing_parts": missing,
            "unexpected_moving_parts": extra,
            "physical_inventory_valid": False,
            "paths": [],
            "passed": False,
        }
    inverse = frame.getGlobalPlacement().inverse()

    def local(obj):
        shape = world_shape(obj)
        shape.Placement = inverse.multiply(shape.Placement)
        return shape

    sensor = doc.ModuleMTF02PEnvelope
    if sensor.getParentGeoFeatureGroup() != frame:
        return {"error": "Sensor does not follow its fixed frame", "passed": False}
    fixed = {obj.Name: local(obj) for obj in physical if obj != sensor}
    sweep, method = translation_sweep(local(sensor), (0, 0, 40))
    hits = [
        {"object": name, "intersection_mm3": volume}
        for name, target in fixed.items()
        if (volume := intersection_volume(sweep, target)) > TOL
    ]
    row = {
        "part": sensor.Name,
        "segments": [
            {
                "start_mm": (0, 0, 0),
                "end_mm": (0, 0, 40),
                "methods": [method],
                "collisions": hits,
                "passed": not hits,
            }
        ],
        "passed": not hits,
    }
    return {
        "paths": [row],
        "retained_parts": sorted(fixed),
        "moving_parts": [sensor.Name],
        "passed": row["passed"],
        "scope": "Disconnect the lead and release external adhesive/Velcro retention before translating the selected sensor40mm along optical-frame+Z. The FC and integral carrier remain installed. There is no detachable printed optical bracket or foot fastener. This continuous rigid clearance reservation does not qualify adhesive release, fingers, tools, connected-cable service or any other extraction direction.",
    }
