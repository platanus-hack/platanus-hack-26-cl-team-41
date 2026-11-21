# Robot project files

Clone or download the whole repository into a normal local folder, for example `C:\Projects\PlatanusHack`. Keep the folders together; simulation meshes and CAD generators use their relative locations. Do not copy just the simulator scripts.

- `SPECS.md`, `README_ROBOT.md`: current technical specs (Matek H743 + Radxa Zero 3W + PC) and robot overview.
- `brazo_compacto/`: current SolidCraft compact arm (4 MG995 + 2 SG90), STEP, URDF and print STLs.
- `base_tt/`: current mobile base: one-piece plate for 2 TT motors + L298N, ball casters, electronics tray (H743, Radxa) and the camera mast (12 x 500 mm carbon rod socket and tilted camera head).
- `rueda_tt/`: printed wheels for the TT motors (65 x 34 mm): PLA rim with bead flanges and TPU tyre, print-ready STLs.
- `robot_ensamble/`: articulated assembly: the arm moves on its 7 joints over the fixed base, with a contact set and validated poses (`posturas.gif`).
- `app/`: web console (Next.js); `robot_bridge/`: bridge on the Radxa (MAVLink to the H743); `h743/`: ArduPilot Lua script; `pc_vision/`: YOLO client for the PC.
- `solidcraft_import/brazo_compacto/`: copy of the current arm kept at this path for the simulator meshes (synced with `brazo_compacto/`).
- `solidcraft_import/base_movil/`, `brazo_robotico/`, `base_movil/`: discarded earlier versions (brushless 4-wheel base, open-fork arm), kept for reference.
- `toolhead_13mm/`: editable FreeCAD holder, STEP interchange, printable parts and documentation.
- `print_jobs/toolhead_and_TT/`: three **unsliced A2L 3MF projects**, embedded PLA / 0.4 mm profiles, M3 fit coupon and bundled TT base STL. Open the 3MF as a project in Bambu Studio.
- `simulation/`: MuJoCo simulator, training code, servo priors and launchers.
- `simulation/trained/curriculum/`: saved reach/route/docking networks, evaluation reports and GIF demonstrations.
- `design/`: earlier all-MG995 FreeCAD prototype; kept for reference. The SolidCraft compact arm is the current version.
- `SOLIDCRAFT 1.rar`: original imported archive.

## Run the simulation after downloading

The local virtual environment is intentionally excluded from Git. With Python 3.11 or newer installed, create it again from the new repository root:

```powershell
py -3.11 -m venv simulation\.venv
& simulation\.venv\Scripts\python.exe -m pip install -r simulation\requirements.lock.txt
& simulation\.venv\Scripts\python.exe simulation\verify_curriculum.py
```

Then double-click `simulation/Launch Simulation.cmd`, `simulation/Replay Object Avoidance.cmd` or `simulation/Replay Toolhead Docking.cmd`. The existing launchers find their virtual environment relative to their own folder. Windows launchers and the installed FreeCAD/Blender paths in examples are Windows-specific; see the component READMEs for direct Python commands.

If Python 3.11 is not registered with `py` but FreeCAD 1.1 is installed, replace the first command with `& 'C:\Program Files\FreeCAD 1.1\bin\python.exe' -m venv simulation\.venv`.

For CAD and print preparation, install FreeCAD 1.1 and Bambu Studio as needed. The prepared FCStd, STEP, STL and 3MF files can be opened without rebuilding anything. The print generator uses the bundled base STL instead of a Downloads path. The docking scene uses relative references to the included toolhead meshes.

Physics remain pre-assembly estimates. The curriculum uses simulator state with learned reach/route models and programmed grasp/latch sequencing plus collision guards. Evaluation results and limitations are in `simulation/trained/curriculum/README.md`. The PLA iron holder is a cold-fit prototype; its actual load capacity and heated operation remain unverified.

Caches, local recordings, virtual environments, FreeCAD backups, logs and temporary slicer diagnostics are excluded from Git. CAD, print jobs, source meshes, trained checkpoints, final reports and previews are included.
