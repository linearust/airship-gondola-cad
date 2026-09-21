"""Single flexible rail, over-wing tape and purchased metric hardware."""

import json

import FreeCAD as App
import Part

from gondola.cad import (
    create_group,
    create_reference,
    set_print_category,
    set_print_sku,
    set_property,
    world_shape,
)
from gondola.config import ARTIFACT_STEM, OUTPUT_DIR
from gondola.contracts.design import (
    DESIGN_REVISION,
    MODULE_STATIONS,
    NOTION_LAST_EDITED,
    NOTION_URL,
    OPTICAL_STACK_HOST,
    SCOPED_LISTED_EQUIPMENT_MASS_G,
    WIRING_PURCHASE_PLAN,
    release_status,
)
from gondola.mass_budget import mass_budget
from gondola.parts.equipment_envelopes import build_equipment
from gondola.provenance import source_fingerprint

V = App.Vector


def style_assembly(doc):
    if not App.GuiUp:
        return
    import FreeCADGui as Gui

    registry = doc.DesignRegistry
    visible_names = set(
        obj.Name
        for obj in list(registry.PrintedParts)
        + list(registry.ReferenceParts)
        + list(registry.HardwareParts)
        + list(registry.TapeReferences)
    )
    for obj in doc.Objects:
        if obj.TypeId == "App::Part":
            obj.ViewObject.Visibility = True
        if obj.isDerivedFrom("Part::Feature"):
            obj.ViewObject.Visibility = obj.Name in visible_names
            obj.ViewObject.DisplayMode = "Flat Lines"
            obj.ViewObject.LineColor = (0.14, 0.22, 0.25)
    for obj in registry.PrintedParts:
        obj.ViewObject.ShapeColor = (
            (0.72, 0.78, 0.8) if obj in registry.RailSegments else (0.31, 0.66, 0.76)
        )
    for obj in registry.HardwareParts:
        obj.ViewObject.ShapeColor = (0.92, 0.64, 0.19)
        obj.ViewObject.LineColor = (0.35, 0.24, 0.07)
    for obj in registry.ReferenceParts:
        obj.ViewObject.ShapeColor = (
            (0.18, 0.48, 0.29)
            if any(k in obj.Name for k in ("FC", "LR900", "PAS"))
            else (0.29, 0.34, 0.4)
        )
        if "Propeller" in obj.Name:
            obj.ViewObject.ShapeColor = (0.23, 0.54, 0.91)
            obj.ViewObject.Transparency = 70
    for obj in registry.TapeReferences:
        obj.ViewObject.ShapeColor = (0.64, 0.4, 0.82)
        obj.ViewObject.Transparency = 40
    Gui.activateWorkbench("PartWorkbench")


def build_assembly():
    from gondola.parts import equipment_mounts as mounts
    from gondola.parts import (
        optical_mount,
        optical_sensor,
        propulsion,
        purchased_hardware,
        rail,
        stack_interface,
    )
    from gondola.print_export import export_print_parts
    from gondola.procurement import export_hardware_bom

    fingerprint = source_fingerprint()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rail_report = rail.validate_mechanism()
    if not rail_report["passed"]:
        raise RuntimeError("Rail mechanism validation failed before assembly.")
    (OUTPUT_DIR / (ARTIFACT_STEM + "_rail_validation.json")).write_text(
        json.dumps(rail_report, indent=2) + "\n"
    )
    doc = App.newDocument("GondolaPA12Rev" + DESIGN_REVISION)
    doc.Label = f"Gondola Rev {DESIGN_REVISION} |{rail.LENGTH:g}mm rail, over-tape, metric hardware"
    rail_assembly = rail.build_rail(doc)
    # 45deg flat orientation leaves margin within both published size screens.
    rail_assembly["printed"][0].PrintRotation = App.Rotation(V(0, 0, 1), 45)
    settings = doc.addObject("App::FeaturePython", "AssemblySettings")
    settings.Label = "EDIT | clamp approach for each module"
    for station in MODULE_STATIONS:
        key, default = station.clamp_control, station.default_approach
        settings.addProperty("App::PropertyEnumeration", key, "Clamp direction")
        setattr(settings, key, ["PositiveY", "NegativeY"])
        setattr(settings, key, default)
    battery_module = create_group(
        doc, "BatteryEquipmentModule", "Battery | compact adhesive mount"
    )
    electronics_module = create_group(
        doc,
        "ElectronicsEquipmentModule",
        "Electronics | open carrier with confirmed mounting patterns",
    )
    propulsion_module = propulsion.build_propulsion_module(doc)
    modules = [battery_module, propulsion_module["group"], electronics_module]
    clamp_controls = [station.clamp_control for station in MODULE_STATIONS]
    for module, station in zip(modules, MODULE_STATIONS):
        x, clamp_control = station.x_mm, station.clamp_control
        if module.Name != station.object_name:
            raise RuntimeError("Module order disagrees with the design contract.")
        set_property(
            module, "RailPositionX", x, "App::PropertyDistance", "Rail adjustment"
        )
        set_property(
            module,
            "RailPositionNotes",
            f"Default land centre. Clamp within4mm of an18mm-pitch land centre, with the whole shoe supported: |X| <= {(rail.LENGTH - rail.SHOE_LENGTH) / 2:g}mm. Avoid other modules and exposed ends.",
        )
        module.setExpression("Placement.Base.x", "RailPositionX")
        module.setExpression(
            "Placement.Base.y",
            "AssemblySettings." + clamp_control + " == 0 ? 0.45 mm : -0.45 mm",
        )
        set_property(
            module,
            "ClampDirectionControl",
            "AssemblySettings."
            + clamp_control
            + "; change before assembling. PositiveY nut loads+X, NegativeY nut loads-X.",
        )
    mount_parts = [
        mounts.build_mount(doc, battery_module, "battery"),
        mounts.build_mount(doc, electronics_module, "electronics"),
    ]
    optical_assembly = optical_mount.build_optical_mount(
        doc, doc.getObject(OPTICAL_STACK_HOST)
    )
    stack_interface.attach_to_host(
        optical_assembly["group"], doc.getObject(OPTICAL_STACK_HOST)
    )
    optical_assembly["hardware"] += stack_interface.build_stack_hardware(
        doc, optical_assembly["group"]
    )
    rail_clamps = []
    for module, key in zip(modules, clamp_controls):
        rail_clamps += rail.build_clamp_hardware(
            doc, module, module.Name, "AssemblySettings." + key
        )
    for obj in propulsion_module["printed"]:
        if "MotorCarrier" in obj.Name:
            set_print_sku(obj, "MotorCarrier")
        elif obj.Name == "PropulsionFixedFrame":
            set_print_sku(obj, "PropulsionFixedFrame")
    reference_parts, clearance_volumes = build_equipment(
        doc, battery_module, electronics_module
    )
    sensor_references, sensor_clearances = optical_sensor.build_sensor(
        doc, optical_assembly["pitch_stage"]
    )
    reference_parts += sensor_references + propulsion_module["references"]
    clearance_volumes += sensor_clearances
    clearance_volumes += propulsion_module["clearances"]
    for sign, suffix in ((1, "Port"), (-1, "Starboard")):
        obj = create_reference(
            doc,
            propulsion_module["group"],
            suffix + "PhaseLeadLoopReserve",
            "phase-lead slack-loop space outside rotor sweep",
            Part.makeTorus(8, 1.5, V(-38, sign * 80, 48.2), V(1, 0, 0)),
            "Illustrative slack space behind the motor in its neutral pose, outside the full rotor bound. This isolated torus is not a connected cable route or a specified bend radius. Check actual lead exits, flexible silicone wires through bounded±150deg tilt, strain relief and current capacity. Use purchased small nylon ties at existing frame windows; do not clamp a moving loop taut or pass wires through the occupied M2 journal bore.",
        )
        obj.Role = "Clearance"
        obj.Label = "RESERVE | " + suffix + " flexible motor-lead loop"
        clearance_volumes.append(obj)
    fit_coupons = rail.build_coupons(doc)
    printed_parts = (
        rail_assembly["printed"]
        + mount_parts
        + propulsion_module["printed"]
        + optical_assembly["printed"]
    )
    hardware_parts = (
        rail_clamps
        + propulsion_module.get("hardware", [])
        + optical_assembly["hardware"]
    )
    for objects, category in [
        (rail_assembly["printed"], "Rail"),
        (mount_parts, "Equipment mounts"),
        (propulsion_module["printed"], "Propulsion"),
        (optical_assembly["printed"], "Adjustable optical stack"),
        (fit_coupons["printed"], "Fit samples"),
    ]:
        set_print_category(objects, category)
    registry = doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
    for name, items in [
        ("PrintedParts", printed_parts),
        ("ReferenceParts", reference_parts),
        ("ClearanceVolumes", clearance_volumes),
        ("FitCoupons", fit_coupons["printed"]),
        ("Modules", modules),
        ("EquipmentMounts", mount_parts),
        ("OpticalMountParts", optical_assembly["printed"]),
        ("RailSegments", rail_assembly["printed"]),
        ("RailLocks", rail_clamps),
        ("HardwareParts", hardware_parts),
        ("TapeReferences", rail_assembly["tapes"]),
        ("TiltingPods", propulsion_module["pods"]),
    ]:
        registry.addProperty("App::PropertyLinkListGlobal", name, "Categories")
        setattr(registry, name, items)
    set_property(
        registry,
        "Status",
        "PA12 CAD fit prototype:1.2mm rail-flexure supplier exception, tape/curvature, friction retention, motor/horn coupling and actual OEM mounting fasteners remain unqualified.",
    )
    set_property(registry, "SourceFingerprint", fingerprint)
    set_property(registry, "NotionSource", NOTION_URL)
    set_property(registry, "NotionLastEdited", NOTION_LAST_EDITED)
    set_property(
        registry,
        "ScopedListedEquipmentMassGrams",
        SCOPED_LISTED_EQUIPMENT_MASS_G,
        "App::PropertyFloat",
    )
    set_property(
        registry,
        "ScopeExclusions",
        "Yaw motor, fins/fin servos, optional360deg servo conversion",
    )
    set_property(
        registry, "ReleaseStatus", json.dumps(release_status(), ensure_ascii=False)
    )
    set_property(
        registry, "WiringPurchasePlan", json.dumps(WIRING_PURCHASE_PLAN, sort_keys=True)
    )
    doc.recompute()
    for obj in (
        printed_parts
        + hardware_parts
        + reference_parts
        + clearance_volumes
        + fit_coupons["printed"]
        + rail_assembly["tapes"]
    ):
        if not obj.Shape.isValid() or obj.Shape.isNull():
            raise RuntimeError("Invalid assembly geometry: " + obj.Name)
    for item in hardware_parts:
        purchased_hardware.add_procurement_properties(item)
    style_assembly(doc)
    doc.saveAs(str(OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")))
    Part.makeCompound([world_shape(obj) for obj in printed_parts]).exportStep(
        str(OUTPUT_DIR / (ARTIFACT_STEM + "_printed_structure.step"))
    )
    Part.makeCompound(
        [world_shape(obj) for obj in printed_parts + hardware_parts + reference_parts]
    ).exportStep(str(OUTPUT_DIR / (ARTIFACT_STEM + "_assembly_reference.step")))
    manifest = export_print_parts(
        doc, printed_parts, fit_coupons["printed"], OUTPUT_DIR, ARTIFACT_STEM
    )
    export_hardware_bom(hardware_parts, OUTPUT_DIR, ARTIFACT_STEM)
    bounds = Part.makeCompound(
        [world_shape(obj) for obj in printed_parts + hardware_parts + reference_parts]
    ).optimalBoundingBox(False, False)
    if source_fingerprint() != fingerprint:
        raise RuntimeError("Source changed during build; rebuild before validation.")
    metrics = {
        "source_fingerprint": fingerprint,
        "revision": DESIGN_REVISION,
        "mass_budget": mass_budget(printed_parts, hardware_parts),
        "rail_length_mm": rail.LENGTH,
        "rail_count": 1,
        "rail_head_relief_gap_mm": rail.FLEX_GAP,
        "rail_land_pitch_mm": rail.LAND_PITCH,
        "equipment_mounts": {
            kind: mounts.mount_contract(kind) for kind in ("battery", "electronics")
        },
        "optical_mount": optical_mount.mount_contract(),
        "optical_stack": stack_interface.interface_contract(),
        "optical_stack_host": OPTICAL_STACK_HOST,
        "installed_printed_part_count": len(printed_parts),
        "purchased_hardware_count": len(hardware_parts),
        "unique_stl_count": manifest["unique_stl_count"],
        "fit_sample_count": len(fit_coupons["printed"]),
        "printed_structure_volume_cm3": sum(obj.Shape.Volume for obj in printed_parts)
        / 1000,
        "rail_volume_cm3": rail_assembly["printed"][0].Shape.Volume / 1000,
        "overall_bounds_mm": [bounds.XLength, bounds.YLength, bounds.ZLength],
        "rail": rail_report,
        "propulsion": propulsion_module["metrics"],
        "status": registry.Status,
        "total_flight_mass": "Not established: add actual battery, printed material, hardware, adhesive, wiring and equipment.",
    }
    (OUTPUT_DIR / (ARTIFACT_STEM + "_metrics.json")).write_text(
        json.dumps(metrics, indent=2) + "\n"
    )
    print(
        json.dumps(
            {k: v for k, v in metrics.items() if k not in ("rail", "propulsion")},
            indent=2,
        ),
        flush=True,
    )
    return doc


if __name__ == "__main__":
    build_assembly()
