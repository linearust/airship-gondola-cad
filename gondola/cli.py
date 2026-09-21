"""Executable workflow help; import CAD modules only inside FreeCAD's Python."""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


def build_argument_parser():
    parser = argparse.ArgumentParser(
        prog="python3 -m gondola",
        description="PA12 airship gondola fit prototype. Run offline from this folder.",
        epilog="Workflow: python3 -m gondola build → preview → validate → compare → bundle. "
        "build/preview overwrite generated files in build; "
        "preview must precede validate because it saves CAD display properties. "
        "Shape parameters: gondola/parts/. Unresolved interfaces: gondola/contracts/design.py. "
        "Frozen regression geometry: tests/fixtures/. Geometry changes require deliberate baseline review.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Generated output directory (default: build).",
    )
    parser.add_argument(
        "--freecad-appimage",
        type=Path,
        help="Installed FreeCAD AppImage; alternatively FREECAD_APPIMAGE.",
    )
    parser.add_argument("--inside-freecad", action="store_true", help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command")
    commands.add_parser(
        "status",
        help="Show scope, source provenance, inventory and unresolved interfaces without FreeCAD.",
    )
    commands.add_parser(
        "build",
        help="Generate native assembly, unique STL/STEP files and BOM from current code.",
    )
    commands.add_parser(
        "preview",
        help="Render views, store colors in CAD, then close this preview process.",
    )
    for name, help_text in (
        (
            "validate",
            "Recompute source evidence; audit saved geometry, clearances, service paths and print files.",
        ),
        (
            "compare",
            "Compare saved shapes and controls against the reviewed frozen design fixture.",
        ),
    ):
        subparser = commands.add_parser(name, help=help_text)
        subparser.add_argument(
            "--source",
            type=Path,
            help="Saved assembly to inspect (default: current generated assembly).",
        )
    commands.add_parser(
        "bundle",
        help="Create prototype ZIP only when saved-CAD checks and exports are current.",
    )
    return parser


def _execute_command(args):
    if args.output_dir:
        os.environ["GONDOLA_OUTPUT_DIR"] = str(args.output_dir.expanduser().resolve())
    if getattr(args, "source", None) is not None:
        args.source = args.source.expanduser().resolve()
    from .config import OUTPUT_DIR

    if args.command == "status":
        from .contracts.design import project_status

        print(json.dumps(project_status(), indent=2, ensure_ascii=False))
        return 0
    if args.command == "bundle":
        from .bundle import build_bundle

        build_bundle()
        return 0
    inside_freecad = (
        args.inside_freecad or importlib.util.find_spec("FreeCAD") is not None
    )
    if not inside_freecad or args.command == "preview":
        from .freecad_runtime import run_with_freecad

        return run_with_freecad(
            args.command,
            OUTPUT_DIR,
            args.freecad_appimage,
            getattr(args, "source", None),
        )
    if args.command == "build":
        from .assembly import build_assembly

        build_assembly()
        return 0
    if args.command == "validate":
        from .validation import assembly, equipment

        assembly_report = assembly.validate(args.source)
        equipment_report = equipment.validate(args.source)
        return 0 if assembly_report["passed"] and equipment_report["passed"] else 1
    if args.command == "compare":
        from .validation import baseline

        return 0 if baseline.validate(args.source)["passed"] else 1
    raise ValueError(args.command)


def main(argv=None):
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        return _execute_command(args)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"gondola: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("gondola: interrupted.", file=sys.stderr)
        return 130
