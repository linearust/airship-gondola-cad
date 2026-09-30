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


def _matches_vector(actual, target):
    return (
        isinstance(actual, (list, tuple))
        and len(actual) == 3
        and all(_matches_number(a, b) for a, b in zip(actual, target))
    )


@dataclass(frozen=True)
class ReviewMotionPlan:
    axial_allowance_mm: float = 0.5
    gear_withdrawal_mm: float = 35
    key_release_mm: float = 2.7
    module_lift_mm: float = 0.5
    module_slide_mm: float = 80
    # Each side stage is (native prefix, direction sign, first frame).
    gear_stages: tuple = (("Port", 1, 13), ("Starboard", -1, 61))
    gear_duration: int = 35
    key_release_frames: tuple = (109, 132)
    module_lift_frames: tuple = (133, 156)
    module_slide_frames: tuple = (157, 216)
    removal_frames: int = 241
    shared_rail_fasteners: tuple = (
        "MainPropulsionModuleRailMountNut",
        "MainPropulsionModuleRailMountScrew",
    )
    # Frame and signed multiple of the permitted carrier travel.
    axial_steps: tuple = ((1, 0), (49, 1), (97, -1), (145, 0), (193, 1), (241, 0))

    def check_basis(self, evidence):
        """Reject native evidence outside this explicitly reviewed motion plan."""
        for row in evidence["saved_carrier_metal_clearances"]:
            if any(
                not _matches_number(row["axial_travel"][key], self.axial_allowance_mm)
                for key in ("negative_mm", "positive_mm")
            ):
                raise RuntimeError(
                    "Update axial-travel poses and captions for the new stops."
                )
        service = evidence["saved_servo_module_service"]
        if (
            service.get("passed") is not True
            or service.get("shared_rail_fasteners_removed_before_bench")
            != list(self.shared_rail_fasteners)
            or service.get("released_fasteners") != []
        ):
            raise RuntimeError(
                "Update the review for changed shared rail clamp / off-rail bench prerequisites."
            )
        waypoints = [
            [0, 0, 0],
            [0, -self.key_release_mm, 0],
            [0, -self.key_release_mm, self.module_lift_mm],
            [self.module_slide_mm, -self.key_release_mm, self.module_lift_mm],
        ]
        if not service["part_paths"] or any(
            row["waypoints_mm"] != waypoints for row in service["part_paths"]
        ):
            raise RuntimeError(
                "Update the review for changed servo-module removal paths."
            )
        gears = service["output_gear_removal"]
        if len(gears) != len(self.gear_stages):
            raise RuntimeError("Update the review for changed gear removal paths.")
        for gear, (prefix, sign, _) in zip(gears, self.gear_stages, strict=True):
            if (
                gear.get("part") != prefix + "OutputGear"
                or len(gear["segments"]) != 1
                or not _matches_vector(gear["segments"][0]["start_mm"], [0, 0, 0])
                or not _matches_vector(
                    gear["segments"][0]["end_mm"],
                    [0, -sign * self.gear_withdrawal_mm, 0],
                )
            ):
                raise RuntimeError("Update the review for changed gear removal paths.")

    def bench_parts(self, propulsion_names):
        """Hide the released shared pair before the explicitly off-rail scene."""
        names = list(propulsion_names)
        if not set(self.shared_rail_fasteners) <= set(names) or any(
            name.startswith("ServoBridge") and name.endswith(("Bolt", "Nut"))
            for name in names
        ):
            raise RuntimeError("Expected the shared rail clamp before bench filtering.")
        return [name for name in names if name not in self.shared_rail_fasteners]

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
            f"Carrier and shafts move +/-{self.axial_allowance_mm:g} mm toward integral frame stops; "
            "NOT bearing internal play. Bearings stay fixed in this prescribed pose; no spacer is installed. "
            "No friction, bearing-capture deformation, retention or load simulation."
        )

    def removal_pose(self, frame, drive_names):
        offsets, hidden = {}, set()
        for prefix, sign, start in self.gear_stages:
            name = prefix + "OutputGear"
            offsets[name] = (
                0,
                -sign
                * self.gear_withdrawal_mm
                * ramp(frame, start, start + self.gear_duration),
                0,
            )
            if frame > start + self.gear_duration:
                hidden.add(name)
        shift = (
            self.module_slide_mm * ramp(frame, *self.module_slide_frames),
            -self.key_release_mm * ramp(frame, *self.key_release_frames),
            self.module_lift_mm * ramp(frame, *self.module_lift_frames),
        )
        offsets.update({name: shift for name in drive_names})
        return offsets, hidden

    def removal_markers(self):
        return (
            [(1, "Off-rail bench / shared clamp already removed / support both parts")]
            + [(start, f"Remove {prefix} 16T") for prefix, _, start in self.gear_stages]
            + [
                (
                    self.key_release_frames[0],
                    f"Release key -Y {self.key_release_mm:g} mm",
                ),
                (self.module_lift_frames[0], f"Lift module {self.module_lift_mm:g} mm"),
                (
                    self.module_slide_frames[0],
                    f"Slide module +X {self.module_slide_mm:g} mm",
                ),
                (
                    self.module_slide_frames[1] + 1,
                    "Module removed; output supports retained",
                ),
            ]
        )

    def removal_description(self):
        return (
            "UNPOWERED OFF-RAIL BENCH ONLY: disconnect leads, remove the shared M3x12 rail screw/nut "
            "and lift the entire propulsion assembly from the rail while supporting frame and bridge together. "
            "Those prerequisites are checked separately and are not animated here; the common clamp and "
            "surrounding rail equipment are absent throughout this scene. Release gear set screws, then "
            f"sequentially remove both 16T gears. Shift the bridge -Y {self.key_release_mm:g} mm to release "
            f"its key, lift {self.module_lift_mm:g} mm and slide +X {self.module_slide_mm:g} mm. "
            "Playback repeats by resetting the bench state, not by a verified reassembly operation."
        )


REVIEW_MOTION = ReviewMotionPlan()
