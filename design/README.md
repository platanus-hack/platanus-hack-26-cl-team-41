# MG995 arm — movable FreeCAD model

Open **MG995_5DOF_Movable.FCStd** in FreeCAD 1.1. The model has five arm joints and a separate geared gripper, driven by six MG995 servos.

## Move the arm

For sliders, open **MoveArm.FCMacro** through **Macro → Macros → Execute** (or open the macro file and run it). Keep `arm_controls.py` and the `.FCStd` file beside the macro. The panel provides all six angles, example poses, desk/chassis selection, hardware visibility, Fit view, and Save pose.

Without the macro, select **Joint Controls - edit these angles** at the top of the model tree. In its **Data** properties, edit BaseYaw, ShoulderPitch, ElbowPitch, WristPitch, WristRoll, or GripperOpening. Native FreeCAD expressions move the entire downstream assembly. Save the file to retain the pose. Those expressions work after reopening without installing an add-on or loading a Python proxy.

The displayed shoulder servo command includes the 2:1 reduction. Both gripper jaws counter-rotate. The sliders use tentative preview ranges; the model does not prevent parts passing through each other. Motion/collision verification and further STL work were deferred as requested.

For base-frame Jacobian and singularity checks, see **JACOBIAN_RESULTS.md**. The updated control panel displays XYZ and arm ranks live. Run **JacobianCheck.FCMacro** for a read-only check of the current pose and its J0 matrix.

## Design layout

| Item | Layout |
| --- | --- |
| Axes | Base yaw, shoulder pitch, elbow pitch, wrist pitch, wrist roll |
| Gripper | Sixth servo, two 24-tooth module 1.25 geared angular jaws |
| Shoulder | 20:40 teeth, module 1.5, printed 2:1 reduction |
| Link lengths | Upper 95 mm; forearm 85 mm, between pitch axes |
| Wrist | 83 mm from wrist pitch to roll output plane |
| Nominal straight reach | About 359 mm from shoulder axis to finger tips; not a verified operating envelope |
| Desk plate | 200 × 180 × 8 mm, four 5.5 mm desk anchor holes |
| Chassis plate | 160 × 130 × 6 mm, M4 slots in two directions |
| Common mount | Four M4 holes on a 90 × 70 mm rectangle |
| MG995 nominal case | 40.7 × 19.7 mm; mount opening adds 0.8 mm total clearance |
| Bearings | One 6806 (30 × 42 × 7 mm) at yaw, five 625 (5 × 16 × 5 mm) at pitch/idler supports |

`parameters.json` records the initial geometry assumptions. `build_arm.py` is the original solid generator; the movable file contains the solids themselves. Its individual solid features can be edited using FreeCAD tools. Joint motion is parametric; the geometry is generated BREP rather than a fully constrained sketch history.

This is a light-duty design prototype. The six servos, servo horns, bearings, fasteners and wiring are purchased components, not printed. Use the actual supplied MG995 horns rather than a printed spline. Horn screw patterns and mounting-ear heights vary; measure your units before manufacturing. A 25 g payload was an initial design target and is **not a tested rating**. Desk attachment, chassis stability, print fits, full travel, fastener access, torque and physical loading still need validation before building.

The static source CAD and preliminary STL/STEP exports in this directory were created before printing was deferred; use the **Movable** document for the current software review. No further manufacturing export is needed to move the model.
