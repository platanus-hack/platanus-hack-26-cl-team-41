# Trained starter skills

The saved checkpoint is `goal_policy.npz` (approximately 38 kB). It is a small 3–64–64–4 neural network, trained on the CPU on 10,000 analytic kinematic goal examples, with 2,000 validation goals. The independently held-out joint-target error is about 0.040 degrees RMS. That is an inverse-kinematic prediction metric, not physical endpoint accuracy.

The learned mapping is **desired TCP XYZ → arm joint targets**, for downward-facing, zero-roll gripper poses. The task controller supplies gravity/joint feedback, phase sequencing, and gripper closure/preload. Thus this is supervised imitation inside a **hybrid controller**, not end-to-end reinforcement learning, learned RGB perception, or natural-language understanding.

## Demonstrated tasks

| Task | Final simulated evaluation |
| --- | --- |
| Lift, hold, place and release a 16 mm / 6 g block in a tray | 12 / 12 trials, new seeds 2000–2011 |
| Size/mass variants: 12, 16 and 18 mm cubes | 12 / 12 trials; mass scales with volume |
| Position and hold a 25 g cold tool with an assumed 8 g rigid holder | 12 / 12 new test goals, one-second holds |

Block success requires a sustained lift of at least 18 mm, bilateral jaw contacts during at least 80% of a one-second hold, followed by release and a settled object inside the tray. **Block trials use actual collision/friction contacts; there is no object-to-gripper weld or attachment.** The gripper joints themselves remain mechanically coupled.

Tool holding is a separate mounted-tool experiment. The virtual tool is rigidly attached through an explicitly modeled holder. This holder has not been designed or built for the real arm. Grasping a loose cylindrical tool was attempted and did not provide a reliable baseline. No heated iron, thermal transfer, cable pull, soldering contact forces or physical deployment has been demonstrated. A 25 g cold proxy does not represent an arbitrary real soldering iron.

## Replay

Double-click `../Run Trained Pick and Place.cmd` or `../Run Trained Tool Hold.cmd`. The viewer shows the saved movement policy driving the hybrid controller. Close the viewer to exit. For inline previews, open `pick-place.gif` and `tool-hold.gif`.

From the simulation directory:

```powershell
.\.venv\Scripts\python.exe run_trained_skill.py --task pick-place --view
.\.venv\Scripts\python.exe run_trained_skill.py --task tool-hold --view
.\.venv\Scripts\python.exe train_skills.py --evaluate-only --tests 12
.\.venv\Scripts\python.exe evaluate_tool_hold.py
.\.venv\Scripts\python.exe evaluate_block_variants.py
.\.venv\Scripts\python.exe verify_trained_skills.py
```

## Limits and next steps

The trained goal box is X=121–145 mm, Y=-75–35 mm, Z=10–44 mm in base/world coordinates; only the feasible downward-pose branch is represented. Physics block tests use an even smaller pickup region, X=126–134 mm and Y=6–23 mm, with a fixed tray. These counts are small starter evaluations, not proof of reliable arbitrary-object manipulation.

Task scenes use elliptic friction cones, no-slip iterations and six-dimensional finger contacts to resolve the narrow printed pads. Their physics parameters remain pre-assembly estimates. The controller uses true simulated object positions, joint positions, contacts and a model for gravity compensation. Real MG995/SG90 servos do not expose all that feedback directly to the controller. Add camera-based state estimation and validate fitted physical parameters before transferring any policy.

The next useful training stage is to infer object pose from the virtual RGB camera, broaden the pickup workspace and object orientations, validate grasp behavior across measured friction/servo variations, and design a real tool fixture. Add language commands only over skills with validated success checks.

Reports: `training_report.json`, `block_evaluation.json`, `block_variant_evaluation.json`, `tool_hold_evaluation.json`, and `verification_summary.json`. The summary includes checkpoint, controller and physics-profile hashes.
