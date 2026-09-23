"""Render the assembly and explanatory native CAD details, then show assembly."""

import json
import os
import re
import traceback
import uuid

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore

from gondola.assembly import style_assembly
from gondola.cad import belongs_to_group, create_group, translated_shape, world_shape
from gondola.config import ARTIFACT_STEM, OUTPUT_DIR
from gondola.contracts.design import DESIGN_REVISION
from gondola.parts import stack_interface
from gondola.provenance import file_sha256, source_fingerprint


def frame_for_export(active, view, width, height):
    # Fit to the exported image aspect, independent of the desktop viewport.
    rot = view.getCameraOrientation()
    right = rot.multVec(App.Vector(1, 0, 0))
    up = rot.multVec(App.Vector(0, 1, 0))
    front = rot.multVec(App.Vector(0, 0, 1))
    points = []
    for o in active.Objects:
        if o.isDerivedFrom("Part::Feature") and o.ViewObject.Visibility:
            b = world_shape(o).optimalBoundingBox(False, False)
            for x in (b.XMin, b.XMax):
                for y in (b.YMin, b.YMax):
                    for z in (b.ZMin, b.ZMax):
                        points.append(App.Vector(x, y, z))
    xs = [p.dot(right) for p in points]
    ys = [p.dot(up) for p in points]
    zs = [p.dot(front) for p in points]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    size = max(max(ys) - min(ys), (max(xs) - min(xs)) * height / width) * 1.12
    pos = right * cx + up * cy + front * (max(zs) + 1000)
    camera = view.getCamera()
    camera = re.sub(
        r"\bposition\s+[-0-9.eE+]+\s+[-0-9.eE+]+\s+[-0-9.eE+]+",
        f"position {pos.x} {pos.y} {pos.z}",
        camera,
    )
    camera = re.sub(r"\bheight\s+[-0-9.eE+]+", f"height {size}", camera)
    camera = re.sub(r"\bnearDistance\s+[-0-9.eE+]+", "nearDistance 1", camera)
    camera = re.sub(r"\bfarDistance\s+[-0-9.eE+]+", "farDistance 3000", camera)
    camera = re.sub(r"\bfocalDistance\s+[-0-9.eE+]+", "focalDistance 1000", camera)
    view.setCamera(camera)


def create_attachment_detail_document(side=1):
    from gondola.parts import rail

    doc = App.newDocument("AttachmentDetail" + ("Negative" if side < 0 else "Positive"))
    doc.Label = f"Rev {DESIGN_REVISION} | tape OVER wings and M2 clamp " + (
        "NegativeY" if side < 0 else "PositiveY"
    )
    g = create_group(doc, "Attachment", "Attachment detail | not a print assembly")

    def add_detail_object(name, shape, color, alpha=0):
        o = doc.addObject("Part::Feature", name)
        g.addObject(o)
        o.Shape = shape
        o.ViewObject.ShapeColor = color
        o.ViewObject.DisplayMode = "Flat Lines"
        o.ViewObject.Transparency = alpha
        return o

    add_detail_object("RailSection", rail.rail_shape(48, (0,)), (0.7, 0.76, 0.79))
    add_detail_object(
        "IntegratedShoe",
        translated_shape(rail.shoe_shape(), y=side * rail.CLAMP_SHIFT_Y),
        (0.31, 0.66, 0.76),
        65,
    )

    def orient(shape):
        return shape if side > 0 else rail.half_turn(shape)

    add_detail_object(
        "PurchasedM2x6",
        translated_shape(orient(rail.clamp_screw_shape()), y=side * rail.CLAMP_SHIFT_Y),
        (0.92, 0.64, 0.19),
    )
    add_detail_object(
        "PurchasedM2Nut",
        translated_shape(orient(rail.nut_shape()), y=side * rail.CLAMP_SHIFT_Y),
        (0.92, 0.64, 0.19),
    )
    for sign in (-1, 1):
        add_detail_object(
            "TapeOverWing" + ("L" if sign < 0 else "R"),
            rail.tape_shape(0, sign),
            (0.64, 0.4, 0.82),
            35,
        )
    surface = add_detail_object(
        "EnvelopeSurfaceIllustration",
        Part.makeBox(58, 82, 0.4, App.Vector(-29, -41, -0.4)),
        (0.82, 0.91, 0.94),
        72,
    )
    surface.Label = "REFERENCE | balloon surface, locally flat illustration"
    doc.recompute()
    return doc


class _PreviewSession:
    """Carry failures across Qt callbacks and invalidate stale completion files."""

    def __init__(self, output_dir, close_after):
        self.output_dir = output_dir
        self.close_after = close_after
        self.run_id = os.environ.get("GONDOLA_PREVIEW_RUN_ID") or uuid.uuid4().hex
        self.failed = False

    def write_state(self, **state):
        (self.output_dir / "preview_state.json").write_text(
            json.dumps({**state, "run_id": self.run_id}, indent=2) + "\n"
        )

    def close_application(self):
        # This is only used by the dedicated preview process. Closing documents
        # first avoids save prompts after an error halfway through rendering.
        for name in list(App.listDocuments()):
            App.closeDocument(name)
        Gui.getMainWindow().close()

    def invoke(self, callback):
        if self.failed:
            return
        try:
            callback()
        except Exception:
            self.failed = True
            error = traceback.format_exc()
            App.Console.PrintError(error)
            try:
                self.write_state(passed=False, status="failed", error=error)
            except Exception:
                App.Console.PrintError(traceback.format_exc())
            finally:
                if self.close_after:
                    try:
                        self.close_application()
                    except Exception:
                        App.Console.PrintError(traceback.format_exc())

    def schedule(self, delay_ms, callback):
        QtCore.QTimer.singleShot(delay_ms, lambda: self.invoke(callback))


def render_previews(close_after=False):
    session = _PreviewSession(OUTPUT_DIR, close_after)

    def start_rendering():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        session.write_state(passed=False, status="rendering")
        fingerprint = source_fingerprint()
        doc = App.openDocument(str(OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")))
        if doc.DesignRegistry.SourceFingerprint != fingerprint:
            raise RuntimeError("Saved CAD is stale; build before preview.")
        style_assembly(doc)
        default_stack_host = doc.OpticalFlowModule.getParentGeoFeatureGroup()
        alternative_stack_host = (
            doc.ElectronicsEquipmentModule
            if default_stack_host == doc.BatteryEquipmentModule
            else doc.BatteryEquipmentModule
        )
        layout = App.openDocument(
            str(OUTPUT_DIR / (ARTIFACT_STEM + "_print_parts.FCStd"))
        )
        detail = create_attachment_detail_document()
        negative = create_attachment_detail_document(-1)
        for o in layout.Objects:
            if o.isDerivedFrom("Part::Feature"):
                o.ViewObject.Visibility = True
                o.ViewObject.ShapeColor = (0.31, 0.66, 0.76)
                o.ViewObject.DisplayMode = "Flat Lines"
        jobs = [
            (doc, "axon", "_preview.png", "all", 1900, 1200),
            (doc, "top", "_top.png", "all", 1900, 1200),
            (doc, "axon", "_rail.png", "rail", 1900, 800),
            (doc, "axon", "_electronics.png", "electronics", 1400, 1400),
            (doc, "axon", "_wiring.png", "wiring", 1600, 1400),
            (doc, "axon", "_optical_stack.png", "optical", 1400, 1600),
            (doc, "axon", "_optical_fc_stack.png", "optical_alternate", 1500, 1600),
            (doc, "axon", "_propulsion.png", "propulsion", 1800, 1300),
            (doc, "axon", "_printed_structure.png", "structure", 1900, 1200),
            (detail, "axon", "_attachment_detail.png", "all", 1700, 1300),
            (detail, "front", "_attachment_section.png", "all", 1700, 850),
            (negative, "axon", "_attachment_opposite.png", "all", 1700, 1300),
            (layout, "top", "_print_parts.png", "all", 1800, 2000),
        ]
        allparts = (
            list(doc.DesignRegistry.PrintedParts)
            + list(doc.DesignRegistry.HardwareParts)
            + list(doc.DesignRegistry.ReferenceParts)
            + list(doc.DesignRegistry.TapeReferences)
        )

        def render_next_view(i=0):
            if i == len(jobs):
                finish_rendering()
                return
            active, pose, suffix, scope, w, h = jobs[i]
            App.setActiveDocument(active.Name)
            if active == doc:
                stack_interface.attach_to_host(
                    doc.OpticalFlowModule,
                    alternative_stack_host
                    if scope == "optical_alternate"
                    else default_stack_host,
                )
                style_assembly(doc)
                for o in allparts:
                    if scope == "rail":
                        o.ViewObject.Visibility = (
                            o in doc.DesignRegistry.RailSegments
                            or o in doc.DesignRegistry.TapeReferences
                        )
                    elif scope in ("electronics", "wiring"):
                        o.ViewObject.Visibility = (
                            belongs_to_group(o, doc.ElectronicsEquipmentModule)
                            or scope == "wiring"
                            and belongs_to_group(o, doc.OpticalFlowModule)
                        )
                    elif scope in ("optical", "optical_alternate"):
                        host = doc.OpticalFlowModule.getParentGeoFeatureGroup()
                        o.ViewObject.Visibility = belongs_to_group(o, host)
                    elif scope == "structure":
                        o.ViewObject.Visibility = (
                            o in doc.DesignRegistry.PrintedParts
                            or o in doc.DesignRegistry.HardwareParts
                        )
                    elif scope == "propulsion":
                        o.ViewObject.Visibility = belongs_to_group(
                            o, doc.MainPropulsionModule
                        )
                if scope == "wiring":
                    for o in doc.DesignRegistry.ClearanceVolumes:
                        if "WiringContract" in o.PropertiesList:
                            o.ViewObject.Visibility = True
                            o.ViewObject.ShapeColor = (0.95, 0.60, 0.16)
                            o.ViewObject.Transparency = 75
            view = Gui.activeDocument().activeView()
            view.setCameraType("Orthographic")
            {
                "axon": view.viewAxonometric,
                "top": view.viewTop,
                "front": view.viewRight,
            }[pose]()
            Gui.updateGui()

            def frame_view():
                view.fitAll()
                frame_for_export(active, view, w, h)
                Gui.updateGui()

                def save_image():
                    image_path = OUTPUT_DIR / (ARTIFACT_STEM + suffix)
                    image_path.unlink(missing_ok=True)
                    view.saveImage(str(image_path), w, h, "White")
                    if not image_path.is_file() or image_path.stat().st_size == 0:
                        raise RuntimeError(f"FreeCAD did not render {image_path.name}.")
                    render_next_view(i + 1)

                session.schedule(1000, save_image)

            session.schedule(1000, frame_view)

        def finish_rendering():
            detail.saveAs(
                str(OUTPUT_DIR / (ARTIFACT_STEM + "_attachment_detail.FCStd"))
            )
            layout.save()
            negative.saveAs(
                str(OUTPUT_DIR / (ARTIFACT_STEM + "_attachment_opposite.FCStd"))
            )
            App.setActiveDocument(doc.Name)
            stack_interface.attach_to_host(doc.OpticalFlowModule, default_stack_host)
            style_assembly(doc)
            Gui.activeDocument().activeView().viewAxonometric()
            Gui.updateGui()

            def save_completed_preview():
                Gui.activeDocument().activeView().fitAll()
                doc.save()
                if source_fingerprint() != fingerprint:
                    raise RuntimeError(
                        "Source changed during preview; rebuild and render again."
                    )
                session.write_state(
                    passed=True,
                    status="complete",
                    source_fingerprint=fingerprint,
                    image_sha256={
                        ARTIFACT_STEM + job[2]: file_sha256(
                            OUTPUT_DIR / (ARTIFACT_STEM + job[2])
                        )
                        for job in jobs
                    },
                    source_sha256=file_sha256(OUTPUT_DIR / (ARTIFACT_STEM + ".FCStd")),
                    images=[ARTIFACT_STEM + job[2] for job in jobs],
                )
                if close_after:
                    session.schedule(250, session.close_application)

            session.schedule(1200, save_completed_preview)

        render_next_view()

    session.invoke(start_rendering)
