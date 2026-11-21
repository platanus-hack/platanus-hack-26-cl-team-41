# SolidCraft arm simulation

The newer object/obstacle and toolhead-docking training is in [trained/curriculum/README.md](trained/curriculum/README.md). Start it with **Replay Object Avoidance.cmd** or **Replay Toolhead Docking.cmd**. These are separate checkpoints and scenes; the original starter skills below remain available.

A local MuJoCo scene using the compact SolidCraft arm. No camera, ToF sensor, microcontroller or physical robot is required to run it. The laptop handles physics and rendering; the RTX 3050 can later accelerate compact vision models.

## Start

Double-click **Launch Simulation.cmd**. Expand the viewer's **Control** panel to move the six servo targets. Close the viewer to exit. Space toggles physics pause. The model starts with bent joints instead of its singular straight-up CAD pose.

Double-click **Record Demonstration.cmd** to record your movements. It streams joint angles, servo targets, TCP and block positions at approximately 50 Hz, plus timestamped camera images at 5 Hz, into a new `recordings` directory. A lower frame rate is possible if rendering cannot keep up.

The controls are joint-output angles in **radians**, not PWM values. The final actuator drives the right gripper jaw; an equality constraint counter-rotates the left jaw. The model has six actuator channels, matching the current four-MG995/two-SG90 design.

## What works now

- Gravity, a fixed tabletop arm, a movable 16 mm block, and a tray.
- Detailed SolidCraft visual geometry with simplified physics collision shapes.
- Six position-controlled actuators with a configurable 5 V prior, 50 Hz commands, an assumed 40 ms delay, reference slew, deadband and speed-dependent torque limits. Lower published 4.8 V stall values are used as priors (MG995 0.922 N m, SG90 0.177 N m), not measured continuous ratings. See `calibration/README.md`.
- Fixed workspace and overhead cameras, producing 640 x 480 RGB images.
- Position-only damped inverse kinematics, and a base-frame Jacobian rank/conditioning readout through the Python API.
- A Gymnasium `ArmReachEnv` for learning to reach randomly generated, locally reachable goals. Actions are six bounded joint-command increments at 50 Hz. Observations contain joint state, TCP, goal, block position and servo command/filter/queue state. The default has 52 values; changing command delay can change this dimension. This first environment uses simulator state, rather than image observations.
- Demonstration recording for later imitation learning.

The environment and camera run successfully. Verification checks source-CAD home coordinates, six-channel servo tracking, jaw coupling, torque caps, inverse kinematics, stable physics, rendering, and Gymnasium API behavior. See `verification.json`. The delayed/deadband model's reaching error is approximately 6.9 mm **inside this simulator**, not a prediction of physical accuracy. `physics_audit.json` checks gravity, contact balance, timestep sensitivity and mass/torque uncertainty scenarios. The hardware is not yet assembled or calibrated.

## Run from a terminal

From this directory:

```powershell
.\.venv\Scripts\python.exe arm_sim.py
.\.venv\Scripts\python.exe arm_sim.py --record
.\.venv\Scripts\python.exe arm_sim.py --headless --demo --steps 2000 --snapshot --record
.\.venv\Scripts\python.exe verify_simulation.py
```

Use the environment in a training script:

```python
from arm_sim import ArmReachEnv

env = ArmReachEnv(render_mode="rgb_array")
observation, info = env.reset(seed=42)
observation, reward, success, timeout, info = env.step(env.action_space.sample())
rgb = env.render()
env.close()
```

`build_scene.py` reads the supplied URDF and writes a separate `scene.xml`. Regenerate the scene when changing the conversion code. The original SolidCraft files and URDF are unchanged. Keep `simulation` beside `solidcraft_import`; the scene references its original metre-scale URDF visual meshes.

The isolated `.venv` has already been installed on this laptop using FreeCAD's Python 3.11 runtime. For another checkout, create a Python 3.11+ virtual environment and install `requirements.txt`. `requirements.lock.txt` records the versions used for verification on this machine.

## Next experiments

Starter training has now been completed. See **trained/README.md**, the saved **trained/goal_policy.npz**, and the **Run Trained Pick and Place.cmd** / **Run Trained Tool Hold.cmd** launchers. The earlier generic reaching environment remains available. Current tasks use a learned movement model inside scripted grasp/hold controllers, with privileged simulator state; camera and language policies are not trained.

1. Broaden the tested pickup region, object orientations and object shapes beyond the starter block cases.
2. Add RGB-based object localization, replacing privileged simulator object coordinates and contacts.
3. Calibrate the real arm and validate measured mass, friction, timing and tracking variations before transferring policies.
4. Design and test a physical tool holder; separately model tool mass, cable pull and heat before considering soldering tasks.
5. Randomize lighting, camera placement, friction and actuator response and evaluate on held-out configurations.
6. Map instructions such as “put the red block in the blue tray” onto validated skills.

The trained starter movement policy has not been deployed to hardware, and no camera or language policy is trained yet. The mass model integrates individual print meshes and substitutes nominal servo masses plus hardware allowances. Unmeasured values are explicit in `physics_profile.json` and `mass_estimates.json`. Fill `calibration/part_masses.csv` after weighing and follow `calibration/README.md` for timing/contact measurements. Servo dynamics, backlash, thermal behavior and collisions still require physical calibration. Approximate physics contacts do not certify the CAD's full mechanical travel or print fits.
