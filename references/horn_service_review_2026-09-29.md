# OEM horn and service review — 2026-09-29

This maintenance update preserves BI geometry, material choices, part quantities
and the 150/50 mm propulsion datums. The user reconfirmed the manufacturer horn
archive and confirmed the selected 45A AM32 FC supports 2S. The suspected recent
FC revision change is not a documented revision identifier or minimum-voltage
specification. See [FC evidence](controller_selection_review.md).

## Source geometry and allowances

The reattached RAR is byte-identical to the retained manufacturer archive. Both
installed horns match the source half arm 1 after only the declared two Ø1 to
Ø1.5 mm enlargements at radii 6.8/13.2 mm: symmetric volume difference 0 mm³.
Original/prepared volume is 202.728148634/198.801156817 mm³. No spline, hole-axis,
other factory hole or outline is replaced with an approximate model.

Keep the near Ø1.8 round hole, far 1.8×2.4 radial slot and open Ø7.3 root seat.
These allow assembly adjustment before clamping; they are not operating play or
proof of concentricity. Print finishing and received-part fit remain required.
The separate [horn review](servo_horn_compatibility.md) distinguishes nominal
clearance from diameter error, surface-position error and installed seating.

An independent 1° input sweep from −60 to +60° on both sides found no case/ear
penetration by the horn, adapter or horn fasteners. Minimum horn/case separation
is 0.20 mm, adapter/case 2.20 mm and near rear-screw/case 0.70 mm. The 0.20 mm
horn gap remains an assumed installed seating allowance; manufacturer horn CAD
alone cannot certify actual spline seating. Sampling is not a continuous or
loaded-motion guarantee.

## Simpler service without changing the print

The old upper-ear bolt withdrawal passes within only 0.10 mm of the adapter.
Do not rely on that gap or thin the 1.5 mm root wall to enlarge it.

1. At neutral with power and leads disconnected, remove output gears and the
   paired servo/input module.
2. On the bench, remove the selected driver gear and input stub.
3. Remove only the two rear ear nuts. Keep both M1.6 bolts seated in the servo.
4. Withdraw the complete servo/horn/adapter/ear-bolt unit: 12.5 mm axially,
   then 40 mm outward, mirrored by side.
5. Remove the far then near horn nuts and detach the adapter. Remove ear bolts
   only after the adapter is clear, if necessary. Fit them before the adapter
   when assembling in reverse order.

Continuous native sweeps check the complete unit and the separate off-bridge
nut/adapter paths. The retained servo, ear bolts and horn screws remain obstacles;
the two input-shaft clamp fasteners move with the adapter. Tool reservations
remain nominal, not measured recess/tool or hand-access qualification.

## Refactoring and corrections

- Remove the obsolete threaded-metal-horn service branch and unused constants.
- Derive repeated nominal horn dimensions and screw length from the selected
  profile; preserve original source asset checksums.
- Report the actual 7.7 mm adapter release needed to clear retained horn screws,
  replacing the obsolete 1.7 mm metal-horn release value.
- Check rear screw-head contact separately from front nut contact.
- Keep the confirmed 2S selection distinct from outstanding installed-power tests.
- Correct current preparation guidance to 34/20/18 mm driven/idler/input stubs.
  Historical revision-specific reports retain their original measurements.

## Verification

An independent comparison found all 294 object identities and placements
unchanged. All 121 saved shapes had zero local/world symmetric-volume and
bounding-box differences; print blanks, solid counts, registry membership,
expressions and native control behavior were preserved. Only the reviewed
electrical/service contracts and generated provenance/UUID metadata changed.
The BI fixture was refreshed after this review; no geometry exception was added.

The frozen-source native suite ran 565 tests without skips. Its one failure was
the old fixture's unresolved FC contract. After the reviewed fixture refresh,
39 baseline/integrity/export/FC tests passed. The only source change between
these phases was the pinned fixture SHA in `config.py`.

See the [exact-source verification](horn_service_verification_2026-09-29.json)
and [compressed evidence](horn_service_checks_2026-09-29.json.gz) for original
test logs, independent probes, metadata differences and final file-bound checks.
The independent OEM/service probes read the preceding saved BI assembly; the
zero-difference shape comparison connects that evidence to this update.
Old audit records retain their original hashes and scope. Regenerated previews
replace stale local images; previous outputs were preserved outside `build/`.
