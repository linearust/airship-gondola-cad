"""Required propulsion audit evidence, independent of generated row counts."""

from types import MappingProxyType

PROPULSION_EVIDENCE_COUNTS = MappingProxyType(
    {
        "drive_motion": 2,
        "gear_mesh_alignment": 2,
        "gear_rotation": 2,
        "fixed_servo_datum": 2,
        "servo_mounts": 2,
        "bridge_joint": 1,
        "servo_module_service": 1,
        "direct_adapter_fit": 2,
        "input_shaft_retention": 2,
        "bearing_stacks": 4,
        "bearing_post_roots": 4,
        "output_stub_clearance": 4,
        "shaft_service": 4,
        "bearing_service": 4,
        "spacer_service": 4,
        "output_carrier_service": 2,
        "gear_service": 4,
        "motor_and_prop_insertion": 4,
        "tilt_clearance": 2,
        "carrier_metal_clearance": 2,
        "relative_motion": 1,
        "input_drive_service": 2,
        "servo_case_service": 2,
        "rail_key_access": 2,
        # Six seated M2 propulsion joints and six M1.6 horn/servo-ear joints.
        # Rail screws are outside this module. The two radial input-stub jack
        # clamps stay assembled during service and use input_shaft_retention;
        # their deliberately unseated heads are not bearing-face stacks.
        "fastener_stacks": 12,
        "fastener_service": 12,
        "functional_wall_probes": 17,  # Four post webs and the common servo-wall web.
        "continuous_nut_loading": 2,
        "geometry": 6,  # Frame, servo bridge, two carriers and two horn adapters.
    }
)


def propulsion_evidence_check(report):
    """Recheck required rows without trusting a report's own success or counts."""
    inventory = {}
    row_failures = []
    for key, expected in PROPULSION_EVIDENCE_COUNTS.items():
        rows = report.get(key)
        inventory[key] = {
            "expected": expected,
            "actual": len(rows) if isinstance(rows, list) else None,
        }
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or row.get("passed") is not True:
                row_failures.append(
                    {"field": f"/{key}/{index}", "reason": "Missing or failed row"}
                )
            elif key == "geometry" and not (
                row.get("valid_brep") is True
                and row.get("solid_count") == 1
                and row.get("single_closed_solid") is True
                and row.get("watertight_mesh") is True
                and row.get("mesh_components") == 1
            ):
                row_failures.append(
                    {"field": f"/{key}/{index}", "reason": "Invalid solid or mesh"}
                )
    return {
        "inventory": inventory,
        "row_failures": row_failures,
        "passed": not row_failures
        and all(row["expected"] == row["actual"] for row in inventory.values()),
    }
