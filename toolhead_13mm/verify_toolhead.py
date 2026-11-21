"""Check persisted native motion, STEP assembly placement and exported checks."""
from pathlib import Path
import json
import FreeCAD as A,Part
ROOT=Path(__file__).resolve().parent
D=A.openDocument(str(ROOT/'Expanding_Toolhead_13mm.FCStd'))
controls=D.getObject('Toolhead_Controls');groups=[D.getObject('Right_Jaw'),D.getObject('Left_Jaw')]
motion=[]
for angle in (0,5.5,6):
    controls.Opening=angle;D.recompute()
    result=[]
    for side,group in zip((1,-1),groups):
        v=group.Placement.Rotation.multVec(A.Vector(0,0,1))
        expected=A.Rotation(A.Vector(0,1,0),side*angle).multVec(A.Vector(0,0,1))
        assert (v-expected).Length<1e-9,(angle,group.Name,v,expected)
        result.append(list((v.x,v.y,v.z)))
    motion.append({'opening_deg':angle,'jaw_axis_vectors':result})
controls.Opening=5.5;D.recompute()
catalog=D.getObject('Part_Catalog')
installed=[o for o in D.Objects if o.TypeId=='PartDesign::Feature' and o not in catalog.Group]
shapes=[]
for obj in installed:
    s=obj.Shape.copy();s.Placement=obj.getGlobalPlacement();shapes.append(s)
native=Part.makeCompound(shapes)
step=Part.read(str(ROOT/'Toolhead_Assembly.step'))
def bounds(s):
    b=s.BoundBox;return [b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax]
assert max(abs(a-b) for a,b in zip(bounds(native),bounds(step)))<1e-5
print('VOLUMES',native.Volume,step.Volume,'SOLIDS',len(native.Solids),len(step.Solids),flush=True)
# STEP round-trip sews the many source-mesh facets; allow 0.005% volume drift.
volume_error=abs(native.Volume-step.Volume)/native.Volume
assert volume_error<5e-5
report=json.loads((ROOT/'validation.json').read_text())
assert all(not c['receiver_interferences'] for c in report['opening_checks'])
assert all(c['interference_mm3']<.05 for c in report['closed_insertion_samples'])
assert all(c['lip_blocks_axial_withdrawal']==(c['opening_deg']>0) for c in report['withdrawal_checks'])
result={'native_motion':motion,'step_bounds_mm':bounds(step),'step_volume_mm3':step.Volume,'step_relative_volume_error':volume_error,'step_matches_native_within_tolerance':True,'cad_clearance_and_lip_capture_checks_passed':True}
(ROOT/'native_verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
A.closeDocument(D.Name)
