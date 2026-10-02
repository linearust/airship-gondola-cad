# Horn source map

The [manufacturer provenance record](manufacturer/kst_x06_servo_horns_2026-09-28.json)
identifies the user-supplied archive, retained STEP, units and coordinate transform.
These are nominal source geometry, not measurements of a received horn.

Current selection and no-drill fastener limits belong to
[servo_horns.py](../gondola/contracts/servo_horns.py); adapter geometry and fit
allowances to [servo_coupling.py](../gondola/parts/servo_coupling.py).
Use [servo_module.py](../gondola/validation/servo_module.py) and
[horn_coupling.py](../gondola/validation/horn_coupling.py) for ordered
service checks.
