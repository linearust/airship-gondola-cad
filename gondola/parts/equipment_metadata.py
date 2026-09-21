"""Shared evidence metadata for purchased devices and reserved cable access."""

import json

import FreeCAD as App

from gondola.cad import create_reference, set_property

from . import mounting_interfaces as interfaces

V = App.Vector


def add_interface_metadata(obj, key, hole_centres=(), hole_diameter=None):
    set_property(
        obj,
        "MountingEvidence",
        json.dumps(interfaces.MOUNTING_EVIDENCE[key], sort_keys=True),
    )
    set_property(obj, "MountingStackVerified", False, "App::PropertyBool")
    set_property(obj, "PCBHeightMeasured", False, "App::PropertyBool")
    set_property(
        obj,
        "ConnectorEvidence",
        json.dumps(interfaces.DEVICE_CONNECTOR_EVIDENCE[key], sort_keys=True),
    )
    set_property(obj, "InstalledConnectorFitVerified", False, "App::PropertyBool")
    if hole_diameter is not None:
        set_property(
            obj, "PublishedMountHoleDiameter", hole_diameter, "App::PropertyLength"
        )
        set_property(
            obj,
            "VerifiedHoleAxesXY",
            [V(x, y, 0) for x, y in hole_centres],
            "App::PropertyVectorList",
        )
        set_property(
            obj,
            "HoleAxisScope",
            "XY axes only. Cylindrical cuts pass through the reference envelope for registration; no real PCB thickness or bearing-plane Z is claimed.",
        )


def create_wiring_reserve(doc, parent, name, shape, contract):
    obj = create_reference(
        doc,
        parent,
        name,
        name,
        shape,
        "Design allowance for connector access and wiring; not an exact installed connector or certified cable route. See WiringContract and retained primary evidence. Disconnect external leads before removal or adjustment.",
        contract["source_url"],
    )
    obj.Role = "Clearance"
    obj.Label = "RESERVE | " + name.removesuffix("Reserve")
    set_property(obj, "WiringContract", json.dumps(contract, sort_keys=True))
    set_property(obj, "InstalledConnectorFitVerified", False, "App::PropertyBool")
    return obj
