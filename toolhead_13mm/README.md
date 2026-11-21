# Angled 13 mm toolhead — cold-fit prototype

An expansion-latch receiver for the imported SolidCraft compact arm. Close the jaws to insert them into the receiver, then open to 5.5 degrees per jaw so the added shoes sit behind the receiver lip. Close to release. The receiver stays attached to the tool. Opening is actively maintained by the gripper servo; this is not a power-off lock.

## Dimensions and assumptions

- Cool handle: maximum diameter 13 mm, usable length 40 mm, user supplied.
- Tip to front of handle: 53 mm, interpreted from the supplied measurement.
- Selected tool angle: 45 degrees relative to the gripper insertion axis.
- Split collar: 13.4 mm nominal bore, 30 mm contact length, centered on the 40 mm section. There is 5 mm of unused handle at either end. Tip is therefore 73 mm from collar center.
- Selected latch opening: 5.5 degrees per jaw; prototype operating limit 6 degrees. The original gripper's wider travel must not be commanded while docked.
- Receiver mouth: 40.2 mm; rear pocket: 49.2 mm; axial capture clearance and sliding fits must be confirmed on the actual print.
- Iron weight, balance point, cable pull and temperatures are unknown. There is no rated load or hot-use validation.

## Files and editing

`Expanding_Toolhead_13mm.FCStd` is the native FreeCAD assembly. Open it in FreeCAD, expand `Toolhead Controls`, and change `Opening` in the Data properties between 0 and 5.5 degrees. This couples both original-geometry jaws and their shoes. Receiver and collar remain fixed, allowing the latch geometry to be inspected. The supplied parts are BREP features; adjust bore, collar length and tool angle in `parameters.json` and regenerate with `build_toolhead.py`. Other mechanical dimensions are currently in the builder.

`Toolhead_Assembly.step` is a flattened assembly with global placements, for import into SolidCraft or Inventor. It does not carry the FreeCAD motion expression. Individual STEP files are in `step/`. Original SolidCraft source files and original jaw meshes were not modified. New source is FreeCAD, not a native SolidCraft `.sc` design.

`stl/` contains eight closed printable part types, including a fit coupon. These are prototype exports and have not been sliced. `validation.json` records BREP, sampled CAD clearance and axial pullout-interference checks; `renders/` contains views from actual exported geometry.

To regenerate on this laptop, from the project root:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
& 'C:\Program Files\FreeCAD 1.1\bin\python.exe' -u toolhead_13mm\build_toolhead.py
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' -b --python toolhead_13mm\render_toolhead.py
```

## Parts and M3 hardware

Print one of each: right/left retention shoe, expansion receiver, angled handle saddle, clamp cap, right/left replacement jaw. The optional eighth part is a handle fit coupon. Replacement jaws preserve the supplied jaw geometry and add a transverse 3.2 mm hole at 50.5 mm from each pivot. Shoes wrap around the outer ends and bolt through those holes; the original inward gripping pads remain exposed.

| Joint | Screws | Nuts |
|---|---|---|
| Shoes to replacement jaws | 2 × M3×16 | 2 × M3 |
| Clamp cap to saddle | 2 × M3×12 | 2 × M3 |
| Saddle to receiver | 4 × M3×8 | 4 × M3 |

Use standard socket-head screws and hex nuts; traps are nominal 5.7 mm across flats and screw clearance is 3.3 mm except the replacement-jaw holes. Confirm actual screw protrusion, nut seating and access during a cold assembly. Do not overtighten printed ears.

## Printing and cold fit

1. Print the coupon first. One/two/three edge notches identify 13.0/13.2/13.4 mm holes. Check against the actual cool handle section and adjust the bore if needed.
2. Start with 0.2 mm layers, 4 walls and 35–40% infill for fit prototypes. Exported meshes are placed on the print bed. Shoes and jaws are oriented on their sides. Remove supports from nut pockets and holes.
3. The receiver has an internal overhang. Use removable internal supports accessible through the mouth; clean the lip and pocket fully. The angled saddle may also need supports. Confirm orientation and support access in the slicer before printing.
4. Replace both jaws and fasten their shoes. Assemble receiver, saddle and cap with M3 hardware. Tighten the split collar evenly around an unpowered iron's confirmed cool handle section.
5. With the assembly supported on a bench, insert at 0 degrees, open gradually to 5.5 degrees, and gently check axial retention. Close fully before withdrawal. Check screw/nut clearance and lateral rocking as well as axial pullout.

PLA is suitable for a cold fit experiment only at this stage. Keep the hot barrel and tip clear of printed parts. Do not suspend a powered iron or leave it unattended with this prototype. A rigid-body geometric catch does not establish printed-part strength, servo holding reliability or thermal resistance; a secondary restraint and measured loads are needed before heated operation.

## What has been checked

Each printable part is a valid single CAD solid and exports as a closed STL. Sampled insertion at closed jaws and seated openings of 0, 4.5, 5.5 and 6 degrees are checked against the receiver. Separate axial withdrawal samples check whether shoes intersect the lip when opened and clear it when closed. These checks cover the modeled jaws/shoes and receiver, not a full-arm collision sweep, deformation, friction, fastener strength or a physical test. No new MuJoCo holder training or load simulation is claimed.

`native_verification.json` also confirms the persisted FreeCAD expressions move both jaws correctly at 0, 5.5 and 6 degrees. STEP round-trip bounds match the native assembled bounds within 0.00001 mm; total solid volume differs by about 0.0014% after STEP sewing of the imported mesh facets. Run `verify_toolhead.py` with the same FreeCAD Python executable to repeat these checks.

The subsequent MuJoCo experiment is documented in `../simulation/trained/curriculum/README.md`. It uses this CAD as visual geometry and a simplified concave collision decomposition, with a freely moving receiver. Closing under an off-axis pull can wedge the holder; the tested sequence unloads and reseats it on a fixture before closing and withdrawing. This simulation does not replace a cold physical fit/load test or validate heated use.
