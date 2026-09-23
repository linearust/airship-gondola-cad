"""Saved nominal machining-example checks, never a supplied-horn fit certificate.

The purchased horn has no measured drawing. These checks deliberately distinguish
an undrilled print blank, a machined illustrative assembly and a removable bench
centring tool. Physical registration and final assembled runout remain required.
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
    # Compare actual saved bearing regions on an ample explicit joint plane.
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
    """Verify the saved preparation example and its removable centring aid.

    PASS means the declared nominal geometry agrees and has an intelligible
    assembly/registration route. It does not mean the user's unmeasured horn
    fits, a printed nose is a precision centre, or the assembled axis is true.
    """
    names = (
        "ServoHorn",
        "HornGearAdapter",
        "HornGearClampNearBolt",
        "HornGearClampNearNut",
        "HornGearClampFarBolt",
        "HornGearClampFarNut",
    )
    missing = [prefix + name for name in names if doc.getObject(prefix + name) is None]
    if doc.getObject(prefix + "InputDrive") is None:
        missing.append(prefix + "InputDrive")
    if doc.getObject("HornCenteringJig") is None:
        missing.append("HornCenteringJig")
    if missing:
        return {
            "passed": False,
            "missing_objects": missing,
            "physical_concentricity_verified": False,
        }
    inverse = coupling_frame(doc, prefix).inverse()
    shapes = {}
    for suffix in names:
        obj = doc.getObject(prefix + suffix)
        shape = world_shape(obj)
        shape.Placement = inverse.multiply(shape.Placement)
        shapes[suffix] = shape
    horn, adapter = shapes["ServoHorn"], shapes["HornGearAdapter"]
    adapter_obj = doc.getObject(prefix + "HornGearAdapter")
    if not hasattr(adapter_obj, "PrintBlankShape"):
        return {
            "passed": False,
            "error": "Saved undrilled print blank is missing",
            "physical_concentricity_verified": False,
        }
    blank = adapter_obj.PrintBlankShape.copy()
    blank.Placement = (
        inverse.multiply(adapter_obj.getGlobalPlacement())
        .multiply(adapter_obj.Placement.inverse())
        .multiply(blank.Placement)
    )
    blank_difference = _difference(blank, coupling.adapter_blank_shape())
    example_difference = _difference(adapter, coupling.adapter_shape())
    horn_difference = _difference(horn, coupling.horn_shape())
    material_added = abs(adapter.cut(blank).Volume)
    preparation_removed = abs(blank.cut(adapter).Volume)
    rows = []
    for label, (x, z), diameter in zip(
        ("Near", "Far"),
        coupling.HORN_BOLT_CENTRES,
        coupling.HORN_ADAPTER_HOLE_DIAMETERS,
    ):
        passage = Part.makeCylinder(
            diameter / 2,
            coupling.PLATE_FRONT_Y - coupling.HORN_BLADE_BOTTOM,
            V(x, coupling.HORN_BLADE_BOTTOM, z),
            V(0, 1, 0),
        )
        bolt = shapes["HornGearClamp" + label + "Bolt"]
        nut = shapes["HornGearClamp" + label + "Nut"]
        expected_bolt = hardware.servo_screw_shape().copy()
        expected_bolt.Placement = App.Placement(
            V(x, coupling.HORN_BLADE_BOTTOM, z),
            App.Rotation(V(0, 0, 1), V(*coupling.BOLT_DIRECTION)),
        )
        expected_nut = hardware.servo_nut_shape().copy()
        expected_nut.Placement = App.Placement(
            V(x, coupling.NUT_SEAT_Y, z),
            App.Rotation(V(0, 0, 1), V(*coupling.BOLT_DIRECTION)),
        )
        fastener_difference = _difference(bolt, expected_bolt) + _difference(
            nut, expected_nut
        )
        head_contact = _plane_contact(horn, bolt, coupling.HORN_BLADE_BOTTOM)
        nut_contact = _plane_contact(adapter, nut, coupling.NUT_SEAT_Y)
        blocked = horn.common(passage).Volume + adapter.common(passage).Volume
        blank_stock = blank.common(passage).Volume
        collisions = sum(
            a.common(b).Volume
            for a, b in ((bolt, horn), (bolt, adapter), (nut, horn), (nut, adapter))
        )
        turns = []
        for angle in (-3, 3):
            moved = horn.copy()
            moved.rotate(V(), V(0, 1, 0), angle)
            penetration = moved.common(bolt).Volume
            turns.append(
                {
                    "rotation_deg": angle,
                    "bolt_probe_penetration_mm3": penetration,
                    "passed": penetration > TOL,
                }
            )
        rows.append(
            {
                "joint": label,
                "nominal_fastener_difference_mm3": fastener_difference,
                "example_hole_diameter_mm": diameter,
                "prepared_passage_blockage_mm3": blocked,
                "print_blank_stock_at_hole_mm3": blank_stock,
                "head_to_horn_contact_mm2": head_contact,
                "nut_to_adapter_contact_mm2": nut_contact,
                "nominal_overlap_mm3": collisions,
                "gross_rotation_stops": turns,
                "passed": fastener_difference < TOL
                and blocked < TOL
                and blank_stock > 1
                and head_contact > 1
                and nut_contact > 1
                and collisions < TOL
                and all(row["passed"] for row in turns),
            }
        )
    jig = doc.getObject("HornCenteringJig").Shape.copy()
    jig.Placement = App.Placement()
    jig_difference = _difference(jig, coupling.centering_jig_shape())
    jig_rows = []
    lower_entry, upper_entry = coupling.JIG_ACCEPTED_ENTRY_DIAMETERS
    for diameter in (lower_entry, (lower_entry + upper_entry) / 2, upper_entry):
        cone_station = (
            coupling.JIG_NOSE_START_Y
            + (diameter - coupling.JIG_NOSE_TIP_DIAMETER)
            / (coupling.JIG_NOSE_BASE_DIAMETER - coupling.JIG_NOSE_TIP_DIAMETER)
            * coupling.JIG_NOSE_LENGTH
        )
        offset = coupling.JIG_REFERENCE_ENTRY_Y - cone_station
        placed = jig.copy()
        placed.translate(V(0, offset, 0))
        overlap = placed.common(adapter).Volume
        # A synthetic circular entrance is a tool working-range test only; it
        # deliberately models neither OEM threads nor an asserted real bore.
        annulus = Part.makeCylinder(
            2.2, 0.5, V(0, coupling.JIG_REFERENCE_ENTRY_Y - 0.5, 0), V(0, 1, 0)
        ).cut(
            Part.makeCylinder(
                diameter / 2,
                0.7,
                V(0, coupling.JIG_REFERENCE_ENTRY_Y - 0.6, 0),
                V(0, 1, 0),
            )
        )
        aperture_overlap = placed.common(annulus).Volume
        seated_gap = placed.distToShape(annulus)[0]
        guide_overlap = min(
            coupling.JIG_GUIDE_START_Y + offset + coupling.JIG_GUIDE_LENGTH,
            coupling.GEAR_START_Y,
        ) - max(coupling.JIG_GUIDE_START_Y + offset, coupling.SHAFT_START_Y)
        jig_rows.append(
            {
                "synthetic_entry_diameter_mm": diameter,
                "axial_offset_mm": offset,
                "adapter_overlap_mm3": overlap,
                "synthetic_entry_overlap_mm3": aperture_overlap,
                "entry_seating_gap_mm": seated_gap,
                "guide_engagement_mm": guide_overlap,
                "passed": overlap < TOL
                and aperture_overlap < TOL
                and seated_gap < TOL
                and guide_overlap >= 6.5,
            }
        )
    physical_unknown = not bool(
        getattr(doc.getObject(prefix + "ServoHorn"), "SuppliedHornMeasured", True)
    )
    return {
        "pod": prefix,
        "print_blank_difference_mm3": blank_difference,
        "prepared_example_difference_mm3": example_difference,
        "illustrative_horn_difference_mm3": horn_difference,
        "material_added_by_preparation_mm3": material_added,
        "material_removed_by_preparation_mm3": preparation_removed,
        "joints": rows,
        "jig_difference_mm3": jig_difference,
        "jig_working_range": jig_rows,
        "supplied_horn_measurement_explicitly_unknown": physical_unknown,
        "physical_concentricity_verified": False,
        "scope": "Saved nominal prepared example and undrilled blank, with two fitted-in-place attachment holes and a removable prototype centring jig. The small jig tip and close-fit near hole require finishing/measurement; their printed or machined accuracy is not certified. Synthetic screw-entry tests do not prove an OEM entry dimension, thread fit or actual concentricity. Measure the actual supplied horn, preserve its spline/centre-screw seat, retain paired drilling registration, and verify final stub/gear runout, motion and clamp retention after reinstallation. Working-envelope alternatives require renewed checks; this PASS is not physical fit or flight qualification.",
        "passed": blank_difference < TOL
        and example_difference < TOL
        and horn_difference < TOL
        and material_added < TOL
        and preparation_removed > 1
        and jig_difference < TOL
        and physical_unknown
        and all(row["passed"] for row in rows + jig_rows),
    }
