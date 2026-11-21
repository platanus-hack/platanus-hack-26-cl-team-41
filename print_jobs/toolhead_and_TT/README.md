# A2L projects — base plate and M3 toolhead

All three projects target **Bambu Lab A2L, 0.4 mm standard-flow nozzle, Generic PLA, Textured PEI Plate, 330 × 320 mm bed**. They contain embedded printer, filament and process settings. Original source geometry is unchanged; no global scaling or hole compensation was applied. The base STL is copied into `sources/` for reproducibility.

| Project | Contents | Process |
|---|---|---|
| `A2L_Base_TT_PLA_0.20mm.3mf` | One supplied TT base plate | 0.20 mm layers, 6 walls, 40% gyroid, 6 top/bottom layers, 8 mm outer brim |
| `A2L_Toolhead_M3_PLA_0.16mm.3mf` | Both retention shoes, receiver, saddle, cap, both replacement jaws, handle coupon and M3 coupon | 0.16 mm layers, 5 walls, 35% gyroid, 6 top/bottom layers, 3–5 mm brims |
| `A2L_M3_and_Handle_Fit_Test_0.16mm.3mf` | Only the two coupons; optional quick first print | Same toolhead settings, supports disabled on coupons |

Print the fit test first if possible. Its coupons are also included in the full toolhead project; print them only once if the full project is sufficient.

## Orientation and supports

The supplied base is upside down in its original coordinates: its broad plate is at the highest Z. In the project it is flipped so that face lies on the bed, with the bosses and motor mounts above it. Overall size remains **178 × 170 × 42.2 mm**.

The receiver sits on its rear flange with the mouth facing upward. The shoes sit on their broad flat side with the nut boss upward. Jaws lie flat, with gear teeth in the bed plane. The saddle sits on its mounting plate; the cap stands on a collar end with a brim.

Automatic normal/snug supports are enabled on the base, receiver and saddle, including internal support where needed. They are disabled individually on the other parts and coupons. Support Z gap is 0.20 mm, XY gap 0.35 mm, with three top interface layers. Remove receiver supports through its mouth and clean the lip, pocket and nut traps before assembly. Inspect support access in Bambu Studio before printing.

## M3 fit

- The toolhead retains its designed **3.2–3.3 mm screw clearances** and **5.7 mm across-flats nut pockets**. XY hole and contour compensation are zero; elephant-foot compensation is 0.15 mm.
- The base has four **approximately 2.6 mm blind pilot bores** in its small mounting bosses. These are not M3 through-clearance holes. Use an M3 tap for standard machine screws, or suitable thread-forming screws intended for plastic. Confirm screw length against the blind depth; do not force an overlong screw into the plate.
- The new M3 coupon has through holes **3.1 / 3.2 / 3.3 / 3.4 mm**, identified by **1 / 2 / 3 / 4 edge notches**. Its other row has nut pockets **5.6 / 5.7 / 5.8 mm AF**, identified by **1 / 2 / 3 notches** on that edge. Check an actual screw and nut before committing to the full toolhead.
- The original handle coupon has **13.0 / 13.2 / 13.4 mm** bores, identified by **1 / 2 / 3 notches**. The collar itself remains 13.4 mm.

Toolhead hardware: **2 × M3×16**, **2 × M3×12**, **4 × M3×8**, **8 × M3 nuts**. This excludes whatever hardware the supplied base requires. Do not infer a base screw count or length from the toolhead list.

The 3MFs are editable arranged Bambu Studio projects. Open as **a project**, not geometry only, to retain the A2L and slicing settings. Select the actual filament spool and keep the A2L 0.4 mm printer preset. No print has been sent to a printer. The soldering-iron holder remains a PLA cold-fit prototype.

These are **unsliced projects**, as requested; use Slice Plate in Bambu Studio. The earlier CLI attempts did not provide a reliable completed slice and are retained under `cli_slices/`. No generated G-code is part of the delivery.

`job_manifest.json` records quantities, closed-mesh checks, bed bounds, orientations and source hashes. `prepare_jobs.py` regenerates these projects with the installed FreeCAD Python runtime and installed Bambu profiles. `validate_jobs.py --structure-only` verifies ZIP/XML structure, referenced geometry, object counts, transforms, bed fit and the embedded A2L/PLA settings; the delivery status is recorded in `validation_report.json`.
