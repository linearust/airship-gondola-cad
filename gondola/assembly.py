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
    release_status,
)
from gondola.parts.equipment_envelopes import build_equipment
from gondola.provenance import source_fingerprint

V = App.Vector


def add_assembly_notes(doc):
    s = doc.addObject("Spreadsheet::Sheet", "StartHere")
    s.Label = f"READ FIRST | Rev {DESIGN_REVISION} | rail/tape/metric hardware"
    rows = [
        (
            f"REV {DESIGN_REVISION}",
            f"{RAIL_LENGTH_MM:g}mm single flexible rail. Standard64x76mm board. PA12 SLS preferred; MJF alternative. Gold=buy; teal/grey=print.",
        ),
        (
            "Rail continuity",
            "Unbroken1mm base;15mm head lands at18mm pitch,3mm flex gaps. The short shoe slides across these gaps. One printed part.",
        ),
        (
            "Tape OVER wings",
            "Use separate12mm-wide single-sided strips on EACH lateral wing, then onto balloon. No double-sided tape beneath rail. Never cross the central running head or hinge gaps.",
        ),
        (
            "Clamp",
            "M3x0.5 x8 ISO4026/DIN913 flat-point set screw and M3 hex nut.1.5mm metric hex key. No separate printed rail keys or pins.",
        ),
        (
            "Adjustment",
            "Loosen3turns. Slide along rail. Clamp only over solid head land, preferably within5mm of an18mm-pitch land centre. Keep the whole18mm shoe on the rail; check module/rotor clearances after moving.",
        ),
        (
            "Removal",
            "Slide modules off a rail END. Remove an intervening neighboring module before the middle propulsion module. End access must remain clear.",
        ),
        (
            "Board",
            "Same board at every level; fourØ4.2 holes andØ8 pads for commonM3 stacking. No battery/FC-specific mounting patterns.",
        ),
        (
            "Stack",
            "M3 male/female standoffs body30mm+stud6mm;32mm board pitch. M3x6 bottom screws; topM3nuts;3.2x7x0.5 washers.",
        ),
        (
            "Extend",
            "Add same board+4same standoffs. Move top washers/nuts to new top. Washers only under bottom screwheads and top nuts.",
        ),
        (
            "PA12",
            "SLS preferred, MJF alternative; ±0.3%/min±0.3mm.45deg print orientation passes published size screening. Creallo combines SLS/MJF quotes; agree process and ONE-PIECE manufacture. Supplier must accept1mm narrow functional flexures.",
        ),
        (
            "Screw side",
            "Select BatteryClampApproach, PropulsionClampApproach or ElectronicsClampApproach under AssemblySettings. Either side accepts the same M3 screw/nut pair; unused port remains empty. Shoe and board are180deg symmetric.",
        ),
        (
            "Notion2026-09-20",
            "Two main300deg DS-M005/RS1102 tilt units, bounded±150deg,1:1. No yaw motor, fin servos or underside MTF sensor.55.932g scoped listed equipment subtotal excludes structure/hardware/wiring.",
        ),
        (
            "Wiring",
            "XT30,35V220uF capacitor and outside-rotor cable-loop reserves are provisional CLEARANCE shapes. Inspect them via DesignRegistry.ClearanceVolumes. Size actual parts and prove phase-lead slack through±150deg; no unlimited rotation.",
        ),
        (
            "Fit",
            "Rail gap0.45mm per side. Nominal total0.9mm leaves0.3mm under two±0.3mm size errors. Not a physical fit guarantee. Print sample pair first.",
        ),
        (
            "Hardware",
            "All NEW threaded hardware M3x0.5 ISO metric coarse. No old customG6.6 printed threads. Gold parts excluded from print exports.",
        ),
        (
            "OEM interfaces",
            "RS1102 motor screw pattern/thread depth and DS-M005 horn coupling must be checked from real parts; supplied OEM screws are not replaced by guessedM3.",
        ),
        (
            "Mechanical limits",
            "Friction lock, PA12 bending/fatigue, tape attachment, thrust loads and OEM fit require physical tests. Flat CAD service paths do not certify a curved installed rail.",
        ),
        (
            "References",
            "Source: gondola/parts/*.py; unresolved interfaces: gondola/design_contract.py. Primary dimension evidence is in references/; purchasing requirements are native hardware properties.",
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
    from gondola.parts import metric_hardware as metric
    from gondola.parts import propulsion, rail
    from gondola.parts import universal_board as board

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
    battery = create_group(doc, "BatteryEquipmentModule", "Battery | universal board")
    elec = create_group(
        doc,
        "ElectronicsEquipmentModule",
        "Electronics | two identical universal boards",
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
            f"Default land centre. Clamp within5mm of an18mm-pitch land centre, with the whole shoe supported: |X| <= {(rail.LENGTH - rail.SHOE_LENGTH) / 2:g}mm. Avoid other modules and exposed ends.",
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
    boards = [
        board.build_board(doc, battery, "BatteryUniversalBoard"),
        board.build_board(doc, elec, "FCUniversalBoard"),
        board.build_board(doc, elec, "UpperUniversalBoard"),
    ]
    boards[-1].Placement.Base = V(0, 0, metric.BODY_LENGTH + board.BOARD_THICKNESS)
    for o in boards:
        set_print_sku(o, "UniversalBoard")
    stack = metric.build_stack(
        doc,
        elec,
        prefix="EquipmentStack",
        lower_board_bottom_z=board.BOARD_BOTTOM,
        levels=1,
    )
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
            Part.makeTorus(8, 1.5, V(38, sign * 80, 48.2), V(1, 0, 0)),
            "Illustrative reserve for flexible three-phase motor leads at bounded±150deg tilt. This is not a rigid cable route or a specified bend radius. Check actual silicone leads at every tilt angle, strain relief, current capacity and connector clearance. Do not pass leads through the occupied M3 journal bore.",
        )
        o.Role = "Clearance"
        o.Label = "RESERVE | " + suffix + " flexible motor-lead loop"
        clearance.append(o)
    coupon = rail.build_coupons(doc)
    printed = ra["printed"] + boards + pr["printed"]
    hardware = stack["hardware"] + clamps + pr.get("hardware", [])
    for objects, cat in [
        (ra["printed"], "Rail"),
        (boards, "Universal boards"),
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
        ("StandardBoards", boards),
        ("StackPosts", stack["posts"]),
        ("StackLocks", stack["locks"]),
        ("StackWashers", stack["washers"]),
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
        "PA12 CAD fit prototype:1mm rail-flexure supplier exception, tape/curvature, friction retention, motor/horn coupling and actual OEM mounting fasteners remain unqualified.",
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
        "Yaw motor, fins/fin servos, underside MTF-02P, optional360deg servo conversion",
    )
    set_property(reg, "ReleaseStatus", json.dumps(release_status(), ensure_ascii=False))
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
        "rail_length_mm": rail.LENGTH,
        "rail_count": 1,
        "rail_head_relief_gap_mm": rail.FLEX_GAP,
        "rail_land_pitch_mm": rail.LAND_PITCH,
        "board_size_mm": [board.BOARD_X, board.BOARD_Y, board.BOARD_THICKNESS],
        "board_holes_mm": board.STACK_HOLE_DIAMETER,
        "stack_clear_gap_mm": metric.BODY_LENGTH,
        "stack_pitch_mm": metric.BODY_LENGTH + board.BOARD_THICKNESS,
        "upper_shoe_clearance_mm": metric.BODY_LENGTH
        - (board.BOARD_BOTTOM - rail.SHOE_BOTTOM),
        "installed_printed_part_count": len(printed),
        "purchased_hardware_count": len(hardware),
        "unique_stl_count": manifest["unique_stl_count"],
        "fit_sample_count": len(coupon["printed"]),
        "printed_structure_volume_cm3": sum(o.Shape.Volume for o in printed) / 1000,
        "rail_volume_cm3": ra["printed"][0].Shape.Volume / 1000,
        "overall_bounds_mm": [bounds.XLength, bounds.YLength, bounds.ZLength],
        "rail": rr,
        "stack": stack["metrics"],
        "propulsion": pr["metrics"],
        "status": reg.Status,
        "total_flight_mass": "Not established: add actual battery, printed material, hardware, adhesive, wiring and equipment.",
    }
    (OUT / (STEM + "_metrics.json")).write_text(json.dumps(metrics, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in metrics.items()
                if k not in ("rail", "stack", "propulsion")
            },
            indent=2,
        ),
        flush=True,
    )
    return doc


if __name__ == "__main__":
    build_assembly()
