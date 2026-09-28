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
    bolt_withdrawal_mm: float = 8.2
    nut_drop_mm: float = 0.2
    nut_slide_mm: float = 25
    module_lift_mm: float = 0.5
    module_slide_mm: float = 80
    # Each side stage is (native prefix, direction sign, first frame).
    gear_stages: tuple = (("Port", 1, 13), ("Starboard", -1, 61))
    mount_stages: tuple = (("Port", 1, 109), ("Starboard", -1, 181))
    gear_duration: int = 35
    bolt_duration: int = 23
    nut_drop_end: int = 29
    nut_slide_end: int = 59
    module_lift_frames: tuple = (253, 276)
    module_slide_frames: tuple = (277, 336)
    removal_frames: int = 361
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
        waypoints = [
            [0, 0, 0],
            [0, 0, self.module_lift_mm],
            [self.module_slide_mm, 0, self.module_lift_mm],
        ]
        for row in service["part_paths"]:
            if row["waypoints_mm"] != waypoints:
                raise RuntimeError(
                    "Update the review for changed servo-module removal paths."
                )
        for index, (_, sign, _) in enumerate(self.gear_stages):
            gear = service["output_gear_removal"][index]
            pair = service["mount_fastener_release"][index]
            expected = (
                (
                    gear["segments"][-1]["end_mm"],
                    [0, -sign * self.gear_withdrawal_mm, 0],
                ),
                (
                    pair["bolt_axial_withdrawal"]["segments"][-1]["end_mm"],
                    [0, 0, self.bolt_withdrawal_mm],
                ),
                (
                    pair["nut_axial_removal"]["segments"][0]["end_mm"],
                    [0, 0, -self.nut_drop_mm],
                ),
                (
                    pair["nut_axial_removal"]["segments"][-1]["end_mm"],
                    [sign * self.nut_slide_mm, 0, -self.nut_drop_mm],
                ),
            )
            if any(not _matches_vector(actual, target) for actual, target in expected):
                raise RuntimeError(
                    "Update the review for changed gear/fastener removal paths."
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
        for prefix, sign, start in self.mount_stages:
            bolt, nut = "ServoBridge" + prefix + "Bolt", "ServoBridge" + prefix + "Nut"
            offsets[bolt] = (
                0,
                0,
                self.bolt_withdrawal_mm
                * ramp(frame, start, start + self.bolt_duration),
            )
            offsets[nut] = (
                sign
                * self.nut_slide_mm
                * ramp(frame, start + self.nut_drop_end, start + self.nut_slide_end),
                0,
                -self.nut_drop_mm
                * ramp(frame, start + self.bolt_duration, start + self.nut_drop_end),
            )
            if frame > start + self.bolt_duration:
                hidden.add(bolt)
            if frame > start + self.nut_slide_end:
                hidden.add(nut)
        shift = (
            self.module_slide_mm * ramp(frame, *self.module_slide_frames),
            0,
            self.module_lift_mm * ramp(frame, *self.module_lift_frames),
        )
        offsets.update({name: shift for name in drive_names})
        return offsets, hidden

    def removal_markers(self):
        return (
            [(1, "Disconnect leads / release gear set screws")]
            + [(start, f"Remove {prefix} 16T") for prefix, _, start in self.gear_stages]
            + [
                (start, f"Remove {prefix} mount bolt / nut")
                for prefix, _, start in self.mount_stages
            ]
            + [
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
            "UNPOWERED BENCH ONLY: leads disconnected and gear set screws released first. "
            f"Sequentially remove 16T gears and two M2 pairs; lift {self.module_lift_mm:g} mm, "
            f"slide +X {self.module_slide_mm:g} mm. Nearby rail equipment excluded. "
            "Playback repeats by resetting the bench state, not by a verified reassembly operation."
        )


REVIEW_MOTION = ReviewMotionPlan()
