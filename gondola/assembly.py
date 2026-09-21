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
from gondola.config import OUTPUT_DIR as OUT
from gondola.config import STEM
from gondola.design_contract import (
    DESIGN_REVISION,
    MODULE_STATIONS,
    NOTION_LAST_EDITED,
    NOTION_URL,
    RAIL_LENGTH_MM,
    SCOPED_LISTED_EQUIPMENT_MASS_G,
    WIRING_PURCHASE_PLAN,
    release_status,
)
from gondola.mass_budget import mass_budget
from gondola.parts.equipment_envelopes import build_equipment
from gondola.provenance import source_fingerprint

V = App.Vector


def add_assembly_notes(doc):
    s = doc.addObject("Spreadsheet::Sheet", "StartHere")
    s.Label = f"READ FIRST | Rev {DESIGN_REVISION} | rail/tape/metric hardware"
    rows = [
        (
            f"REV {DESIGN_REVISION}",
            f"{RAIL_LENGTH_MM:g}mm PA12 rail with role-specific battery/electronics mounts. Gold=buy; teal/grey=print.",
        ),
        (
            "Rail",
            "One continuous 1.2mm flexible base with 13.5mm head lands, 4.5mm reliefs and seven tape-pad stations. Supplier acceptance and full-length bend testing remain required.",
        ),
        (
            "Tape",
            "12mm single-sided strips OVER each wing onto the envelope. Keep running head and flex gaps clear. Battery, LR900-A and MTF-02P retain adhesive mounting.",
        ),
        (
            "Clamp",
            "M2x6 DIN913 flat-point screw and DIN562 M2 SQUARE nut, one pair per module. Do not substitute a hex nut. Use 0.9mm hex key; loosen three turns before sliding.",
        ),
        (
            "Removal",
            "Disconnect external leads before sliding modules off a rail end. Remove the neighboring battery/electronics module before propulsion. Keep each 18mm shoe fully supported and clamp within 4mm of a full land centre.",
        ),
        (
            "Mounts",
            "Small battery adhesive deck and one open electronics carrier replace the three oversized identical boards and their 30mm stack. No unused upper rail shoe or expansion hardware.",
        ),
        (
            "Confirmed holes",
            "FC: 25.5mm square, manufacturer 45deg orientation. P-AS: two M2 holes, 23mm pitch. Device fastening planes and fastener lengths are not inferred from the overall bounding boxes.",
        ),
        (
            "FC clearance",
            "Reserve 8mm below the entire conservative FC envelope above the mount face. This is our wiring-space allowance, not a published connector dimension. Use the supplied M2x7.5 silicone sleeves and purchased spacers; final assembled height/fasteners remain to measure.",
        ),
        (
            "OEM interfaces",
            "Only published device mounting patterns may be generated. Do not invent servo spline, horn attachment, PCB thickness or motor screw insertion depth. Exact mounting holes do not certify a complete bolted assembly.",
        ),
        (
            "Scope",
            "Two DS-M005/RS1102 main tilt units, bounded +/-150deg, 1:1. Includes MTF-02P. No yaw motor, fins or fin servos.",
        ),
        (
            "Purchasing",
            "Buy standard fasteners, spacers and OEM horns. Printed D journals are custom torque interfaces, not generic replacement bearings; the horn connection remains unresolved.",
        ),
        (
            "Clearance",
            "FC has a connected underbody/perimeter wiring reservation and rounded exits. Connector service lanes are design allowances; unplug leads before device or module removal. Verify actual port locations, antenna, moving phase leads and adhesive retention.",
        ),
        (
            "PA12",
            "SLS preferred; MJF alternative by supplier agreement. Nominal functional walls at least 1.5mm, with the recorded 1.2mm rail flexure exception. No strength or flight qualification from CAD checks.",
        ),
        (
            "References",
            "Source: gondola/parts/. Confirmed interfaces: mounting_interfaces.py. Remaining evidence: design_contract.py. Buy only the hardware specifications; do not print equipment/reference/clearance shapes.",
        ),
    ]
    for i, (a, b) in enumerate(rows, 1):
        s.set("A%d" % i, a)
        s.set("B%d" % i, b)
    s.setColumnWidth("A", 175)
    s.setColumnWidth("B", 1100)


def style_assembly(doc):
    if not App.GuiUp:
        return
    import FreeCADGui as Gui

    r = doc.DesignRegistry
    shown = set(
        o.Name
        for o in list(r.PrintedParts)
        + list(r.ReferenceParts)
        + list(r.HardwareParts)
        + list(r.TapeReferences)
    )
    for o in doc.Objects:
        if o.TypeId == "App::Part":
            o.ViewObject.Visibility = True
        if o.isDerivedFrom("Part::Feature"):
            o.ViewObject.Visibility = o.Name in shown
            o.ViewObject.DisplayMode = "Flat Lines"
            o.ViewObject.LineColor = (0.14, 0.22, 0.25)
    for o in r.PrintedParts:
        o.ViewObject.ShapeColor = (
            (0.72, 0.78, 0.8) if o in r.RailSegments else (0.31, 0.66, 0.76)
        )
    for o in r.HardwareParts:
        o.ViewObject.ShapeColor = (0.92, 0.64, 0.19)
        o.ViewObject.LineColor = (0.35, 0.24, 0.07)
    for o in r.ReferenceParts:
        o.ViewObject.ShapeColor = (
            (0.18, 0.48, 0.29)
            if any(k in o.Name for k in ("FC", "LR900", "PAS"))
            else (0.29, 0.34, 0.4)
        )
        if "Propeller" in o.Name:
            o.ViewObject.ShapeColor = (0.23, 0.54, 0.91)
            o.ViewObject.Transparency = 70
    for o in r.TapeReferences:
        o.ViewObject.ShapeColor = (0.64, 0.4, 0.82)
        o.ViewObject.Transparency = 40
    Gui.activateWorkbench("PartWorkbench")


def build_assembly():
    from gondola.manufacturing import export_hardware_bom, export_print_parts
    from gondola.parts import equipment_mounts as mounts
    from gondola.parts import metric_hardware as metric
    from gondola.parts import propulsion, rail

    fingerprint = source_fingerprint()
    OUT.mkdir(parents=True, exist_ok=True)
    rr = rail.validate_mechanism()
    if not rr["passed"]:
        raise RuntimeError("Rail mechanism validation failed before assembly.")
    (OUT / (STEM + "_rail_validation.json")).write_text(json.dumps(rr, indent=2) + "\n")
    doc = App.newDocument("GondolaPA12Rev" + DESIGN_REVISION)
    doc.Label = f"Gondola Rev {DESIGN_REVISION} |{rail.LENGTH:g}mm rail, over-tape, metric hardware"
    add_assembly_notes(doc)
    ra = rail.build_rail(doc)
    # 45deg flat orientation leaves margin within both published size screens.
    ra["printed"][0].PrintRotation = App.Rotation(V(0, 0, 1), 45)
    settings = doc.addObject("App::FeaturePython", "AssemblySettings")
    settings.Label = "EDIT | clamp approach for each module"
    for station in MODULE_STATIONS:
        key, default = station.clamp_control, station.default_approach
        settings.addProperty("App::PropertyEnumeration", key, "Clamp direction")
        setattr(settings, key, ["PositiveY", "NegativeY"])
        setattr(settings, key, default)
    battery = create_group(
        doc, "BatteryEquipmentModule", "Battery | compact adhesive mount"
    )
    elec = create_group(
        doc,
        "ElectronicsEquipmentModule",
        "Electronics | open carrier with confirmed mounting patterns",
    )
    pr = propulsion.build_propulsion_module(doc)
    modules = [battery, pr["group"], elec]
    sidekeys = [station.clamp_control for station in MODULE_STATIONS]
    for m, station in zip(modules, MODULE_STATIONS):
        x, sidekey = station.x_mm, station.clamp_control
        if m.Name != station.object_name:
            raise RuntimeError("Module order disagrees with the design contract.")
        set_property(m, "RailPositionX", x, "App::PropertyDistance", "Rail adjustment")
        set_property(
            m,
            "RailPositionNotes",
            f"Default land centre. Clamp within4mm of an18mm-pitch land centre, with the whole shoe supported: |X| <= {(rail.LENGTH - rail.SHOE_LENGTH) / 2:g}mm. Avoid other modules and exposed ends.",
        )
        m.setExpression("Placement.Base.x", "RailPositionX")
        m.setExpression(
            "Placement.Base.y",
            "AssemblySettings." + sidekey + " == 0 ? 0.45 mm : -0.45 mm",
        )
        set_property(
            m,
            "ClampDirectionControl",
            "AssemblySettings."
            + sidekey
            + "; change before assembling. PositiveY nut loads+X, NegativeY nut loads-X.",
        )
    mounts_list = [
        mounts.build_mount(doc, battery, "battery"),
        mounts.build_mount(doc, elec, "electronics"),
    ]
    clamps = []
    for m, key in zip(modules, sidekeys):
        clamps += rail.build_clamp_hardware(doc, m, m.Name, "AssemblySettings." + key)
    for o in pr["printed"]:
        if "MotorCarrier" in o.Name:
            set_print_sku(o, "MotorCarrier")
        elif o.Name == "PropulsionFixedFrame":
            set_print_sku(o, "PropulsionFixedFrame")
    refs, clearance = build_equipment(doc, battery, elec)
    refs += pr["references"]
    clearance += pr["clearances"]
    for sign, suffix in ((1, "Port"), (-1, "Starboard")):
        o = create_reference(
            doc,
            pr["group"],
            suffix + "PhaseLeadLoopReserve",
            "phase-lead slack-loop space outside rotor sweep",
            Part.makeTorus(8, 1.5, V(-38, sign * 80, 48.2), V(1, 0, 0)),
            "Illustrative slack space behind the motor in its neutral pose, outside the full rotor bound. This isolated torus is not a connected cable route or a specified bend radius. Check actual lead exits, flexible silicone wires through bounded±150deg tilt, strain relief and current capacity. Use purchased small nylon ties at existing frame windows; do not clamp a moving loop taut or pass wires through the occupied M2 journal bore.",
        )
        o.Role = "Clearance"
        o.Label = "RESERVE | " + suffix + " flexible motor-lead loop"
        clearance.append(o)
    coupon = rail.build_coupons(doc)
    printed = ra["printed"] + mounts_list + pr["printed"]
    hardware = clamps + pr.get("hardware", [])
    for objects, cat in [
        (ra["printed"], "Rail"),
        (mounts_list, "Equipment mounts"),
        (pr["printed"], "Propulsion"),
        (coupon["printed"], "Fit samples"),
    ]:
        set_print_category(objects, cat)
    reg = doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
    for name, items in [
        ("PrintedParts", printed),
        ("ReferenceParts", refs),
        ("ClearanceVolumes", clearance),
        ("FitCoupons", coupon["printed"]),
        ("Modules", modules),
        ("EquipmentMounts", mounts_list),
        ("RailSegments", ra["printed"]),
        ("RailLocks", clamps),
        ("HardwareParts", hardware),
        ("TapeReferences", ra["tapes"]),
        ("TiltingPods", pr["pods"]),
    ]:
        reg.addProperty("App::PropertyLinkListGlobal", name, "Categories")
        setattr(reg, name, items)
    set_property(
        reg,
        "Status",
        "PA12 CAD fit prototype:1.2mm rail-flexure supplier exception, tape/curvature, friction retention, motor/horn coupling and actual OEM mounting fasteners remain unqualified.",
    )
    set_property(reg, "SourceFingerprint", fingerprint)
    set_property(reg, "NotionSource", NOTION_URL)
    set_property(reg, "NotionLastEdited", NOTION_LAST_EDITED)
    set_property(
        reg,
        "ScopedListedEquipmentMassGrams",
        SCOPED_LISTED_EQUIPMENT_MASS_G,
        "App::PropertyFloat",
    )
    set_property(
        reg,
        "ScopeExclusions",
        "Yaw motor, fins/fin servos, optional360deg servo conversion",
    )
    set_property(reg, "ReleaseStatus", json.dumps(release_status(), ensure_ascii=False))
    set_property(
        reg, "WiringPurchasePlan", json.dumps(WIRING_PURCHASE_PLAN, sort_keys=True)
    )
    doc.recompute()
    for o in printed + hardware + refs + clearance + coupon["printed"] + ra["tapes"]:
        if not o.Shape.isValid() or o.Shape.isNull():
            raise RuntimeError("Invalid assembly geometry: " + o.Name)
    for item in hardware:
        metric.add_procurement_properties(item)
    style_assembly(doc)
    doc.saveAs(str(OUT / (STEM + ".FCStd")))
    Part.makeCompound([world_shape(o) for o in printed]).exportStep(
        str(OUT / (STEM + "_printed_structure.step"))
    )
    Part.makeCompound([world_shape(o) for o in printed + hardware + refs]).exportStep(
        str(OUT / (STEM + "_assembly_reference.step"))
    )
    manifest = export_print_parts(doc, printed, coupon["printed"], OUT, STEM)
    export_hardware_bom(hardware, OUT, STEM)
    bounds = Part.makeCompound(
        [world_shape(o) for o in printed + hardware + refs]
    ).optimalBoundingBox(False, False)
    if source_fingerprint() != fingerprint:
        raise RuntimeError("Source changed during build; rebuild before validation.")
    metrics = {
        "source_fingerprint": fingerprint,
        "revision": DESIGN_REVISION,
        "mass_budget": mass_budget(printed, hardware),
        "rail_length_mm": rail.LENGTH,
        "rail_count": 1,
        "rail_head_relief_gap_mm": rail.FLEX_GAP,
        "rail_land_pitch_mm": rail.LAND_PITCH,
        "equipment_mounts": {
            kind: mounts.mount_contract(kind) for kind in ("battery", "electronics")
        },
        "installed_printed_part_count": len(printed),
        "purchased_hardware_count": len(hardware),
        "unique_stl_count": manifest["unique_stl_count"],
        "fit_sample_count": len(coupon["printed"]),
        "printed_structure_volume_cm3": sum(o.Shape.Volume for o in printed) / 1000,
        "rail_volume_cm3": ra["printed"][0].Shape.Volume / 1000,
        "overall_bounds_mm": [bounds.XLength, bounds.YLength, bounds.ZLength],
        "rail": rr,
        "propulsion": pr["metrics"],
        "status": reg.Status,
        "total_flight_mass": "Not established: add actual battery, printed material, hardware, adhesive, wiring and equipment.",
    }
    (OUT / (STEM + "_metrics.json")).write_text(json.dumps(metrics, indent=2) + "\n")
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
