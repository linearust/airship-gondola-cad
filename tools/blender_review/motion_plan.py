"""Fixed, reviewed mechanical moves for the Blender visual derivative.

These values are presentation assumptions checked against native evidence, never
inferred from that evidence. This is not a general animation or service planner.
"""

import math
from dataclasses import dataclass


def ramp(frame, start, end):
    return max(0.0, min(1.0, (frame - start) / (end - start)))


def curve(frame, points):
    for (start, a), (end, b) in zip(points, points[1:]):
        if frame <= end:
            return a + (b - a) * ramp(frame, start, end)
    return points[-1][1]


def _matches_number(actual, target, tolerance=1e-8):
    return (
        isinstance(actual, (int, float))
        and math.isfinite(actual)
        and abs(actual - target) <= tolerance
    )


def rotor_members(prefix):
    suffix = "Negative" if prefix == "Port" else "Positive"
    return {
        prefix + name
        for name in (
            "MotorCarrier",
            "Motor",
            "Shaft",
            "PropellerDisk",
            "OutputShaft" + suffix,
            "OutputClamp" + suffix + "Bolt",
            "OutputClamp" + suffix + "Nut",
        )
    }


def _path_matches(path, waypoints, retained):
    segments = path.get("segments", [])
    if path.get("passed") is not True or len(segments) != len(waypoints) - 1:
        return False
    if not retained.issubset(path.get("obstacles", [])):
        return False
    for segment, start, end in zip(segments, waypoints, waypoints[1:]):
        if segment.get("passed") is not True:
            return False
        for key, expected in (("start_mm", start), ("end_mm", end)):
            actual = segment.get(key)
            if (
                not isinstance(actual, (list, tuple))
                or len(actual) != 3
                or not all(_matches_number(a, b) for a, b in zip(actual, expected))
            ):
                return False
        hits = segment.get("intersection_mm3", {})
        if not retained.issubset(hits) or any(
            not isinstance(value, (int, float))
            or not math.isfinite(value)
            or abs(value) >= 1e-7
            for value in hits.values()
        ):
            return False
    return True


@dataclass(frozen=True)
class ReviewMotionPlan:
    axial_allowance_mm: float = 0.5
    # Frame and signed multiple of the permitted carrier travel.
    axial_steps: tuple = ((1, 0), (49, 1), (97, -1), (145, 0), (193, 1), (241, 0))
    rotor_service_frames: int = 193

    def check_basis(self, evidence):
        """Require both saved carrier proofs before illustrating axial play."""
        clearances = evidence.get("saved_carrier_metal_clearances", [])
        if (
            not isinstance(clearances, list)
            or len(clearances) != 2
            or {row.get("pod") for row in clearances} != {"Port", "Starboard"}
            or any(
                row.get("passed") is not True
                or row.get("axial_travel", {}).get("passed") is not True
                or any(
                    not _matches_number(
                        row.get("axial_travel", {}).get(key),
                        self.axial_allowance_mm,
                        # OCCT stop bounds include ~1e-7 mm numerical padding.
                        tolerance=1e-6,
                    )
                    for key in ("negative_mm", "positive_mm")
                )
                for row in clearances
            )
        ):
            raise RuntimeError(
                "Update axial-travel poses and captions for the new stops."
            )

    def check_rotor_service_basis(self, evidence):
        rows = evidence.get("local_checks", {}).get("output_carrier_service", [])
        if len(rows) != 2 or {row.get("pod") for row in rows} != {"Port", "Starboard"}:
            raise RuntimeError("Missing complete rotor-removal evidence.")
        for row in rows:
            prefix = row["pod"]
            sign = 1 if prefix == "Port" else -1
            other = "Starboard" if prefix == "Port" else "Port"
            moving = rotor_members(prefix)
            gear = prefix + "OutputGear"
            retained = {
                "PropulsionFixedFrame",
                prefix + "BearingCap",
                prefix + "OutputBearingInboard",
                prefix + "OutputBearingOutboard",
                prefix + "Servo",
                prefix + "DriverGear",
                prefix + "HornGearAdapter",
                other + "OutputGear",
                *rotor_members(other),
            }
            paths = row.get("carrier_removal", [])
            expected_gear = [
                (0, 0, 0),
                (0, -sign * 11, 0),
                (0, -sign * 11, 20),
                (30, -sign * 11, 20),
            ]
            if (
                row.get("passed") is not True
                or set(row.get("moving_parts", [])) != moving
                or set(row.get("removed_parts", [])) != moving | {gear}
                or row.get("removed_output_gear") != gear
                or row.get("shaft_moves_with_carrier")
                != prefix
                + ("OutputShaftNegative" if sign > 0 else "OutputShaftPositive")
                or not retained.issubset(row.get("retained_parts", []))
                or not _path_matches(
                    row.get("output_gear_removal", {}), expected_gear, retained | moving
                )
                or len(paths) != len(moving)
                or {path.get("part") for path in paths} != moving
                or any(
                    not _path_matches(path, [(0, 0, 0), (0, sign * 60, 0)], retained)
                    for path in paths
                )
            ):
                raise RuntimeError(
                    "Update rotor-removal poses for changed native service evidence."
                )

    def check_rotor_members(self, pod_names):
        if set(pod_names) != {"Port", "Starboard"} or any(
            set(names) != rotor_members(prefix) | {prefix + "OutputGear"}
            for prefix, names in pod_names.items()
        ):
            raise RuntimeError(
                "Update rotor-removal poses for changed saved pod membership."
            )

    def rotor_service_pose(self, frame):
        # Output gear clears the shaft, rises, then moves aside. Only after it
        # has left does the complete locked rotor/shaft move outward.
        gear_offset = (
            30 * ramp(frame, 73, 97),
            -11 * ramp(frame, 25, 49),
            20 * ramp(frame, 49, 73),
        )
        offsets = {"PortOutputGear": gear_offset}
        offsets.update(
            {name: (0, 60 * ramp(frame, 121, 169), 0) for name in rotor_members("Port")}
        )
        return offsets, {"PortOutputGear"} if frame > 97 else set()

    def rotor_service_markers(self):
        return [
            (1, "Unpowered bench: leads freed; rotor supported"),
            (25, "Release gear set screw; withdraw output gear"),
            (49, "Gear clears shaft; lift and move aside"),
            (97, "Output gear removed"),
            (121, "Withdraw rotor with its shaft still clamped"),
            (169, "Rotor clear; both bearings and cap remain installed"),
        ]

    def rotor_service_description(self):
        return (
            "Unpowered bench sequence with leads freed and rotor supported. Release the bought output gear set screw, "
            "withdraw the gear 11mm inward, lift20mm and move30mm aside. Then withdraw the complete Port rotor and "
            "its locked output shaft60mm outward through both inboard bearings. The jack clamp, bearing cap, fixed frame, "
            "servos and opposite rotor stay assembled. Gear set screw, hands, wires and physical fitted friction are not simulated. "
            "No servo saddle withdrawal or separate shaft staging is shown."
        )

    def axial_shift(self, frame):
        return curve(
            frame,
            [
                (at, multiple * self.axial_allowance_mm)
                for at, multiple in self.axial_steps
            ],
        )

    def axial_markers(self):
        frames = [at for at, _ in self.axial_steps]
        return [
            (frames[0], "Nominal"),
            (frames[1], f"+{self.axial_allowance_mm:g} mm stop"),
            (frames[2], f"-{self.axial_allowance_mm:g} mm stop"),
            (frames[3], "Rotation with permitted travel"),
            (frames[-1], "Nominal"),
        ]

    def axial_description(self):
        return (
            f"Carrier and its single output shaft move +/-{self.axial_allowance_mm:g} mm between the inboard housing stop lands; "
            "NOT bearing internal play. Bearings stay fixed in this prescribed pose; no spacer is installed. "
            "No friction, bearing-capture deformation, retention or load simulation."
        )


REVIEW_MOTION = ReviewMotionPlan()
