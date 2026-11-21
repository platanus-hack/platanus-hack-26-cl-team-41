# Object and obstacle curriculum

Three new saved NumPy neural networks extend the original starter policy. They run on the CPU without new packages; the laptop's GPU is not needed for these compact models. All tasks use simulator poses and joint/contact feedback. Camera perception, language understanding and physical deployment are not trained.

| Checkpoint | Learned behavior | Teacher |
|---|---|---|
| `reach_policy.npz` | Desired XYZ to three independent arm targets; wrist pitch enforces a downward gripper | 18,000 feasible analytic IK examples, 15,000 train / 3,000 validation |
| `route_policy.npz` | Six route-feasibility probabilities from start, goal, two obstacle boxes and carried-object radius | 1,800 randomized layouts labeled using full-arm primitive collisions and IK limits, 1,500 train / 300 validation |
| `dock_reach_policy.npz` | Upright XYZ docking reach targets | 10,000 analytic IK examples, 8,334 train / 1,666 validation |

All are 2-hidden-layer, 64-unit tanh networks. Reaching trains for 140 epochs; route classification trains for 280. This is supervised imitation in a hybrid controller. Task phases, jaw contact feedback, gravity compensation, collision guard, refusal and latch timing are explicitly programmed. The network does not learn a guarantee of collision avoidance.

## Scenes and behavior

The object catalog contains 12/16/18 mm cubes, a rectangular block, an upright cylinder, a sphere and an ellipsoid. Other movable shapes remain on a staging area during each target-object episode. Pickup position, small yaw perturbations, target mass/friction, servo speed, peak torque and deadband vary. The four MG995 / two SG90, 5 V servo priors remain uncalibrated; no new measurements are implied.

The route model sees two solid obstacles. Candidates include a direct transfer, a small raised transfer and inward/outward detours that respect the fixed-down wrist limits. The arm cannot simply climb over an arbitrarily tall barrier. The deterministic guard checks all original primitive arm collision geometry against the obstacles and table, checks modeled nonadjacent self-contact, and adds a conservative sphere around the carried object. It samples paths every 4 mm with 3 mm obstacle clearance. It tries an alternative when a network proposal is blocked and refuses when all candidates fail.

During manipulation, a separate monitor runs at every 2 ms physics step and aborts on penetrating obstacle, robot/table, robot/tray, robot/distractor or robot/self contacts. Intended finger/target contacts remain allowed. An abort is an evaluation failure, not a collision-free success. Primitive collision proxies, sampling, tracking error and uncalibrated physics mean this does not establish continuous CAD or hardware safety.

Object evaluation samples layouts screened as geometrically feasible by the analytic teacher before execution. Failed grasps or placements are not resampled. A separate independent 200-layout route challenge retains infeasible layouts, including 20 deliberately impassable barriers, to score refusal. Keep these two denominators separate when reading the results. Reports retain per-object outcomes and seeds.

Placement uses a limited 0.16 rad jaw opening close to the tray floor, then retracts before fully opening. A wide opening near the floor hit a tray wall; a high release let round objects roll. The earlier high-release evaluation is retained as `drop_release_evaluation.json`.

## New holder docking

`dock_curriculum_scene.xml` contains the full arm, added shoe collision geometry, CAD visuals for the new receiver/saddle/cap, and a receiver with a real free joint. It has no holder weld or equality attachment. The concave receiver uses boxes matching its CAD dimensions; the full exact BREP is not used for contact physics. Approximate shoe mass is not separately added to the jaw links in this stage; total holder mass is 42 g plus a hypothetical 25/50/100 g iron, with assumed COM and inertia.

The upright fixture supports the receiver on four small pads under its flange. The learned reach mapping drives alignment and insertion. Scripted phases open to 5.5 degrees, apply an external upward force equal to weight plus 0.15 N, verify actual shoe/lip contacts and limited holder displacement, remove the pull, reseat, close and withdraw. A repeated pull with the gripper withdrawn must move the free holder at least 10 mm as a no-attachment control.

Closing under an off-axis pull caused the receiver to tilt and wedge in the simulation. The successful sequence releases only after unloading onto the fixture. This is a controller limitation and a mechanical issue to examine in a cold physical prototype. The 0.15 N net test and assumed tool masses are not a printed strength, servo duty or thermal rating. Docking is currently an upright, known-orientation fixture task, not arbitrary 6-DOF docking, carrying the latched tool through a full-arm workspace, or soldering.

## Replay and repeat

Double-click `simulation/Replay Object Avoidance.cmd` or `simulation/Replay Toolhead Docking.cmd`. The original starter launchers are unchanged. Close the viewer to stop a replay. GIFs are `objects-obstacles.gif` and `dock-latch-release.gif`.

From the project root:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
& simulation\.venv\Scripts\python.exe simulation\obstacle_curriculum.py --tests 28 --gif
& simulation\.venv\Scripts\python.exe simulation\obstacle_curriculum.py --routes-only
& simulation\.venv\Scripts\python.exe simulation\dock_curriculum.py --tests 12 --gif
& simulation\.venv\Scripts\python.exe simulation\verify_curriculum.py
```

Add `--train` to either task script to retrain its networks. The object script accepts `--epochs` and `--cases`. Training replaces only these curriculum checkpoints. `route_dataset.npz` preserves the route features and teacher labels.

## Results and evidence

Current held-out evaluation:

| Test | Result |
|---|---|
| Contact pick/place in teacher-screened feasible obstacle layouts | 26 / 28; seeds 6100–6127 |
| Cubes, rectangular blocks, cylinders and spheres | 4 / 4 each of the six categories |
| Ellipsoids | 2 / 4; both failures were placement/release criteria, after successful lifts |
| Forbidden contacts during the 28 manipulation trials | 0 recorded at the 2 ms monitor |
| Independent route challenge | 85 guarded routes executed, 115 refused out of 200; 0 guarded paths failed the sampled collision recheck |
| Deliberately impassable route layouts | 20 / 20 refused |
| Upright free-holder latch/pull/unload/undock | 12 / 12; seeds 9300–9311, hypothetical 25/50/100 g irons |

Of the 200 route challenges, the analytic teacher found 86 feasible. The learned reach mapping plus guard executed 85, so one analytically feasible case was conservatively refused. The raw route network proposed a clear path in 82 cases; the guard recovered three more using another candidate. These are small simulation evaluations, not a physical reliability rate.

Independent FK verification on 1,000 feasible goals each measured 95th-percentile errors of 0.240 mm for downward reaching and 0.145 mm for upright docking. These measure learned target approximation inside the simulator, not servo tracking or real accuracy. A deliberately injected finger/obstacle collision triggered the stop within one 2 ms physics step. Checkpoint/source hashes match the evaluated files.

Read `object_evaluation.json`, `route_evaluation.json`, `dock_evaluation.json` and `verification.json` for the current measured results. `training_report.json` and `dock_training_report.json` contain training splits and losses. Verification uses independent analytic/FK goals, checks the free receiver joint and absence of welds, injects a collision to check the physics-step stop, and records checkpoint/source hashes. Simulation accuracy and small trial counts do not predict physical success rates.
