# Robot project files

Clone or download the whole repository into a normal local folder, for example `C:\Projects\PlatanusHack`. Keep the folders together; simulation meshes and CAD generators use their relative locations. Do not copy just the simulator scripts.

- `solidcraft_import/brazo_compacto/`: current SolidCraft compact arm, STEP, URDF and print meshes; 4 MG995 + 2 SG90 servos.
- `solidcraft_import/base_movil/`: imported mobile chassis design.
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
