# Physics calibration

**Status: pre-assembly estimates; no measured hardware calibration.** The user confirmed four MG995 servos, two SG90 servos, a 5 V rail, and an arm that is not yet assembled.

## Updated model

Mass and inertia now come from the eleven original printing meshes, transformed into the real URDF link frames. Printed PLA uses an assumed density of 1240 kg/m3 and 85% of the CAD solid material mass, with 65–100% used for sensitivity checks. This fraction is not the slicer's infill setting: the CAD already has hollow shells, and printed perimeters/top/bottom layers use material too.

Servos are assigned separate nominal masses (55 g MG995, 9 g SG90) with case-sized box inertia estimates. Screw/horn/external-wire allowances are explicit estimates. The parallel-axis theorem combines components correctly. The total full-arm estimate, including its stationary base, is **0.776 kg**. Actual weights and internal distributions are still unknown.

The 5 V prior conservatively uses published 4.8 V data: MG995 9.4 kgf cm = 0.922 N m stall and 0.20 s/60 degrees; analog SG90 1.8 kgf cm = 0.177 N m stall and 0.12 s/60 degrees. These are not continuous-duty ratings or measurements of the user's servos.

The Python controller adds 50 Hz commands, an assumed 40 ms delay, bounded reference slew, assumed position deadband, and a linear motoring torque-speed envelope. Braking can use full configured stall torque. External forces can move a joint faster than motor free speed. Gains, friction, damping, reflected inertia and contacts remain priors; backlash, thermal limits and electrical voltage sag are not yet identified.

`../physics_profile.json` records assumptions and provenance. `../mass_estimates.json` lists component masses, link COM and full inertia tensors. **Use the launcher or ArmSimulation**: opening scene.xml alone bypasses the Python servo model.

Sources:

- [Soldered MG995 datasheet](https://www.mouser.com/catalog/specsheets/Soldered_109042.pdf): main servo specification says 55 g; packaging/header/footer says 66 g. We use the main specification pending weighing.
- [TowerPro analog SG90](https://towerpro.com.tw/product/sg90-analog/): specification says 0.12 s/60 degrees, while another table says 0.1 s. We use the slower value; actual analog/digital variant remains unconfirmed.

## Numerical checks completed

`../physics_audit.json` records simulated consistency checks, not hardware agreement:

- Positive physical inertia tensors and valid triangle inequalities.
- The intended 40 ms delay, reference speed limits and torque-speed envelope.
- Free fall matches gravity to 0.98 mm over 0.1 s at a 2 ms timestep.
- Resting-block normal force 0.05886 N matches the modeled 6 g block's weight.
- Halving timestep changes the tested settled TCP position by about 0.089 mm.
- Three mass/torque uncertainty scenarios remain numerically finite.

The no-payload horizontal arm needs about **0.553 N m shoulder gravity torque**, about **60% of nominal stall torque**. This does not establish a thermally safe holding time. Physical payload and duty cycle require brief, supported load checks. The updated reach test has **6.9 mm simulated tracking error**, replacing the earlier idealized 1.9 mm result. Neither predicts physical accuracy.

## Measurements after printing

1. **Weigh components:** fill `part_masses.csv` in grams. Blank entries remain estimated. Weigh prints separately; servo weights include their own leads, while hardware includes horns, fasteners and additional wires. Avoid double counting. Nonblank weights automatically update the mass model on next launch. Scaling CAD distribution by measured mass does not measure actual infill/servo mass distribution.
2. **Record servo timing:** start with isolated, unloaded servos at the confirmed rail voltage, using small motions within known travel. A printed protractor and phone video (ideally 120 fps+) can measure command-to-first-motion delay and first-motion-to-target travel time in both directions. An LED driven alongside the command can mark command time. Do not drive against mechanical end stops to estimate torque.
3. **Fill `servo_steps.csv`:** run the commands below from this directory. The script validates entries and previews changes before `--apply`. Sweep angle divided by travel time is an effective average response approximation, not a directly identified motor free-speed constant. Gains, torque, deadband and damping cannot be identified from one sweep and remain unchanged.
4. **Measure assembled tracking:** secure the base, start bent and unloaded, record small steps, holding errors and gentle direction reversals. Camera markers can observe actual angles; PWM commands alone do not report shaft position. Fit against measured trajectories and validate against separate trajectories.
5. **Measure contacts:** `surface_tests.csv` captures incline tests with the actual printed surfaces. Onset angle gives static friction via tan(angle); it should not automatically replace kinetic friction. Sliding deceleration and gentle block-bounce measurements provide dynamic-friction/compliance evidence. The current script deliberately does not apply incline rows automatically.

```powershell
..\.venv\Scripts\python.exe ..\apply_measurements.py
..\.venv\Scripts\python.exe ..\apply_measurements.py --apply
```

The fitter averages supplied delays into a global delay, then the simulator quantizes it to 50 Hz command frames. Use actual firmware timings once available. Choose hardware agreement tolerances from measured repeatability and task requirements. Do not label the model hardware-calibrated until held-out angle/time/contact tests support that claim.
