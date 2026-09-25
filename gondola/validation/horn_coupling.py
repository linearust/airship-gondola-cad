"""Selected factory-threaded horn and nominal integral-register evidence.

A PASS establishes the saved geometry, thread engagement envelopes and limited
registration function. It cannot certify purchased root concentricity, the axial
proxy, printed fit, preload, retention or physical gear runout.
"""

import FreeCAD as App
import Part

from gondola.cad import world_shape
from gondola.parts import purchased_hardware as hardware
from gondola.parts import servo_coupling as coupling

TOL = 1e-5
V = App.Vector


def coupling_frame(doc, prefix):
    """Map horn-local geometry through the actual mirrored input-drive parents."""
    mirror = App.Rotation(V(0, 0, 1), 180 if prefix == "Starboard" else 0)
    return (
        doc.getObject(prefix + "InputDrive")
        .getGlobalPlacement()
        .multiply(App.Placement(V(), mirror))
        .multiply(App.Placement(V(0, coupling.HORN_BOTTOM_Y, 0), App.Rotation()))
    )


def _difference(first, second):
    return abs(first.cut(second).Volume) + abs(second.cut(first).Volume)


def _plane_contact(first, second, y):
    plane = Part.Face(
        Part.makePolygon(
            [
                V(x, y, z)
                for x, z in ((-20, -20), (25, -20), (25, 20), (-20, 20), (-20, -20))
            ]
        )
    )
    return first.common(plane).common(second.common(plane)).Area


def horn_registration_check(doc, prefix):
    """Verify front screws, no horn nuts/jig, and a directional root register."""
    names = (
        "ServoHorn",
        "HornGearAdapter",
        "HornGearClampNearBolt",
        "HornGearClampFarBolt",
    )
    missing = [
        prefix + name
        for name in (*names, "InputDrive")
        if doc.getObject(prefix + name) is None
    ]
    if missing:
        return {
            "passed": False,
            "missing_objects": missing,
            "physical_concentricity_verified": False,
        }
    obsolete = [
        name
        for name in (
            "HornCenteringJig",
            prefix + "HornGearClampNearNut",
            prefix + "HornGearClampFarNut",
        )
        if doc.getObject(name) is not None
    ]
    inverse = coupling_frame(doc, prefix).inverse()
    shapes = {}
    for suffix in names:
        shape = world_shape(doc.getObject(prefix + suffix))
        shape.Placement = inverse.multiply(shape.Placement)
        shapes[suffix] = shape
    horn, adapter = shapes["ServoHorn"], shapes["HornGearAdapter"]
    adapter_difference = _difference(adapter, coupling.adapter_shape())
    horn_difference = _difference(horn, coupling.horn_shape())
    adapter_obj = doc.getObject(prefix + "HornGearAdapter")
    # Printing a different undrilled blank would silently restore hand-transfer
    # preparation even when the assembly drawing looks correctly finished.
    export_difference = 0.0
    if hasattr(adapter_obj, "PrintBlankShape"):
        exported = adapter_obj.PrintBlankShape.copy()
        exported.Placement = (
            inverse.multiply(adapter_obj.getGlobalPlacement())
            .multiply(adapter_obj.Placement.inverse())
            .multiply(exported.Placement)
        )
        export_difference = _difference(exported, adapter)
    rows = []
    for label, (x, z) in zip(("Near", "Far"), coupling.HORN_BOLT_CENTRES):
        bolt = shapes["HornGearClamp" + label + "Bolt"]
        expected = hardware.servo_screw_shape(coupling.HORN_CLAMP_LENGTH).copy()
        expected.Placement = App.Placement(
            V(x, coupling.FASTENER_SEAT_Y, z),
            App.Rotation(V(0, 0, 1), V(*coupling.BOLT_DIRECTION)),
        )
        difference = _difference(bolt, expected)
        passage = Part.makeCylinder(
            coupling.HORN_CLAMP_THREAD_DIAMETER / 2,
            coupling.FASTENER_SEAT_Y - coupling.HORN_BLADE_BOTTOM,
            V(x, coupling.HORN_BLADE_BOTTOM, z),
            V(0, 1, 0),
        )
        blocked = horn.common(passage).Volume + adapter.common(passage).Volume
        contact = _plane_contact(adapter, bolt, coupling.FASTENER_SEAT_Y)
        tip = bolt.BoundBox.YMin
        engagement = max(
            0.0, coupling.HORN_HEIGHT - max(tip, coupling.HORN_BLADE_BOTTOM)
        )
        rear_clearance = tip - coupling.HORN_BLADE_BOTTOM
        overlap = bolt.common(adapter).Volume + bolt.common(horn).Volume
        support = []
        allowance = coupling.HORN_ADAPTER_SLOT_ALLOWANCE if label == "Far" else 0.0
        for offset in (-allowance, 0.0, allowance) if allowance else (0.0,):
            # A minimum accepted flat under-head land, separate from the larger
            # maximum kit-head envelope used for interference and tool checks.
            land = Part.makeCylinder(
                coupling.HORN_MIN_HEAD_BEARING_DIAMETER / 2,
                0.1,
                V(x + offset, coupling.FASTENER_SEAT_Y, z),
                V(0, 1, 0),
            )
            area = _plane_contact(adapter, land, coupling.FASTENER_SEAT_Y)
            support.append(
                {
                    "radial_offset_mm": offset,
                    "flat_bearing_contact_mm2": area,
                    "passed": area >= 1.0,
                }
            )
        rows.append(
            {
                "joint": label,
                "nominal_fastener_difference_mm3": difference,
                "factory_thread_passage_blockage_mm3": blocked,
                "head_to_adapter_contact_mm2": contact,
                "nominal_thread_engagement_mm": engagement,
                "nominal_tip_to_horn_back_mm": rear_clearance,
                "nominal_overlap_mm3": overlap,
                "separate_nut_required": False,
                "minimum_flat_head_bearing_diameter_mm": coupling.HORN_MIN_HEAD_BEARING_DIAMETER,
                "minimum_head_support": support,
                "passed": difference < TOL
                and blocked < TOL
                and contact > 1
                and all(item["passed"] for item in support)
                and engagement >= 1.0
                and rear_clearance >= 0.1 - TOL
                and overlap < TOL,
            }
        )
    # The open +X C seat constrains the back and sides. It deliberately does
    # not claim full circumferential self-centering or zero translational play.
    collar = adapter.common(
        Part.makeBox(
            20,
            coupling.HORN_HEIGHT - coupling.BODY_BACK_Y,
            20,
            V(-10, coupling.BODY_BACK_Y, -10),
        )
    )
    register_rows = []
    for direction in ((-1, 0), (0, -1), (0, 1)):
        moved = horn.copy()
        moved.translate(V(direction[0] * 0.25, 0, direction[1] * 0.25))
        penetration = moved.common(collar).Volume
        register_rows.append(
            {
                "horn_offset_xz_mm": [value * 0.25 for value in direction],
                "register_probe_penetration_mm3": penetration,
                "passed": penetration > TOL,
            }
        )
    seating = _plane_contact(horn, adapter, coupling.HORN_HEIGHT)
    horn_obj = doc.getObject(prefix + "ServoHorn")
    measured = bool(getattr(horn_obj, "PurchasedHornMeasured", True))
    axial_unknown = not bool(getattr(horn_obj, "AxialSeatingMeasured", True))
    compatibility_accepted = bool(getattr(horn_obj, "X06CompatibilityAccepted", False))
    factory_threads_confirmed = bool(
        getattr(horn_obj, "FactoryM1_6ThreadsConfirmed", False)
    )
    return {
        "pod": prefix,
        "adapter_difference_mm3": adapter_difference,
        "selected_horn_difference_mm3": horn_difference,
        "print_export_difference_mm3": export_difference,
        "obsolete_horn_parts": obsolete,
        "joints": rows,
        "register_directional_stops": register_rows,
        "horn_to_adapter_seating_area_mm2": seating,
        "purchased_horn_measurement_explicitly_unknown": not measured,
        "physical_concentricity_verified": False,
        "axial_seating_explicitly_unmeasured": axial_unknown,
        "x06_compatibility_accepted": compatibility_accepted,
        "factory_m1_6_threads_confirmed": factory_threads_confirmed,
        "scope": "Selected 15T/4 mm horn under the user's X06 compatibility premise; all three M1.6 threads are user-confirmed. Two factory-threaded joints avoid hand-transfer drilling and horn nuts. The open C register bounds the root at the rear and sides; it is not a precision full-circle pilot. Root width does not certify a concentric cylindrical surface, hub height remains an axial proxy, outer-hole pitch is inferred and accommodated by a slot. Finish and inspect the actual seating/register, thread engagement and gear runout before operation. No fit, tightening torque, friction retention or strength qualification is claimed.",
        "passed": adapter_difference < TOL
        and horn_difference < TOL
        and export_difference < TOL
        and not obsolete
        and not measured
        and axial_unknown
        and compatibility_accepted
        and factory_threads_confirmed
        and seating > 1
        and all(row["passed"] for row in rows + register_rows),
    }
