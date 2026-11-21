"""FreeCAD adapter for the imported SolidCraft compact gripper; original CAD unchanged.
Common CAD frame: jaw pivots X=+/-10.6, Y=0, Z=0; fingers point +Z.
Source printing meshes use Y=14.5, Z=376 at that datum. Dimensions mm.
"""
from pathlib import Path
import math,json
import FreeCAD as A,Part,Mesh,MeshPart
import FreeCADGui as Gui
ROOT=Path(__file__).resolve().parent;P=json.loads((ROOT/'parameters.json').read_text())
for f in ('stl','step','renders'):(ROOT/f).mkdir(exist_ok=True)
Gui.showMainWindow();Gui.activateWorkbench('PartWorkbench');Gui.getMainWindow().hide()
D=A.newDocument('Expanding_Toolhead_13mm');V=A.Vector
catalog=D.addObject('App::Part','Part_Catalog');assembly=D.addObject('App::Part','Toolhead_Assembly')
controls=D.addObject('App::DocumentObjectGroup','Toolhead_Controls');controls.addProperty('App::PropertyAngle','Opening','Motion');controls.Opening=P['latch_angle_deg']
controls.addProperty('App::PropertyString','Instructions','Motion');controls.Instructions='0 deg inserts/releases; 5.5 deg latches. Prototype operating maximum 6 deg. No power-off retention claim.'
blue=(.12,.4,.55);orange=(.95,.4,.12);green=(.15,.55,.3);gray=(.58,.62,.67)
parts={};scene=[]
def box(x,y,z,a,b,c):return Part.makeBox(a,b,c,V(x,y,z))
def cyl(r,h,x=0,y=0,z=0,axis=V(0,0,1)):return Part.makeCylinder(r,h,V(x,y,z),axis)
def union(*s):return s[0].multiFuse(list(s[1:])).removeSplitter() if len(s)>1 else s[0]
def subtract(s,*tools):
    for t in tools:s=s.cut(t)
    return s.removeSplitter()
def transform(s,placement):
    s=s.copy();s.Placement=placement.multiply(s.Placement);return s
def mirror_x(s):
    m=A.Matrix();m.A11=-1;return s.transformGeometry(m)
def prism_xz(points,y,h):
    pts=[V(x,y,z) for x,z in points];pts.append(pts[0]);return Part.Face(Part.makePolygon(pts)).extrude(V(0,h,0))
def hex_y(x,z,y,h,af=5.7):
    r=af/math.sqrt(3);return prism_xz([(x+r*math.cos(math.radians(30+60*k)),z+r*math.sin(math.radians(30+60*k))) for k in range(6)],y,h)
def hex_z(x,y,z,h,af=5.7):
    r=af/math.sqrt(3);p=[V(x+r*math.cos(math.radians(30+60*k)),y+r*math.sin(math.radians(30+60*k)),z) for k in range(6)];p.append(p[0]);return Part.Face(Part.makePolygon(p)).extrude(V(0,0,h))
def rotor(s,side,angle,shift=0):
    pivot=V(side*10.6,0,0);q=s.copy();q.rotate(pivot,V(0,1,0),side*angle);q.translate(V(0,0,shift));return q
def add(name,shape,qty=1,color=blue,note='',orientation=None):
    shape=shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids)!=1:raise ValueError((name,shape.isValid(),len(shape.Solids)))
    o=D.addObject('PartDesign::Feature',name);o.Label=name.replace('_',' ');o.Shape=shape;catalog.addObject(o)
    o.addProperty('App::PropertyInteger','Quantity','Manufacturing');o.Quantity=qty
    o.addProperty('App::PropertyString','PrintingNote','Manufacturing');o.PrintingNote=note
    if o.ViewObject:o.ViewObject.ShapeColor=color
    parts[name]=(shape,color,note)
    printshape=transform(shape,orientation or A.Placement());bb=printshape.BoundBox;printshape.translate(V(-bb.XMin,-bb.YMin,-bb.ZMin))
    mesh=MeshPart.meshFromShape(Shape=printshape,LinearDeflection=.06,AngularDeflection=.12,Relative=False)
    if not mesh.isSolid():raise ValueError('Open STL '+name)
    mesh.write(str(ROOT/'stl'/(name+'.stl')));Part.export([o],str(ROOT/'step'/(name+'.step')))
    return o
def install(name,parent=assembly,placement=None,label=None):
    shape,color,note=parts[name];o=D.addObject('PartDesign::Feature',name+'_installed');o.Label=label or name.replace('_',' ');o.Shape=shape.copy();parent.addObject(o)
    if placement:o.Placement=placement
    if o.ViewObject:o.ViewObject.ShapeColor=color
    return o

# Retaining shoes have a distinct rear-facing shoulder and positive M3 attachment.
shoe=union(box(14.9,-4.5,47,3.3,9,10.5),box(6.8,-4.5,47,11.4,1.7,8.3),box(6.8,2.8,47,11.4,1.7,8.3),box(6.8,-4.5,55.3,11.4,9,2.2),cyl(4.5,4,10.6,4.5,50.5,V(0,1,0)))
shoe=subtract(shoe,cyl(1.65,16,10.6,-5,50.5,V(0,1,0)),hex_y(10.6,50.5,5.8,2.8))
add('01_Right_Retention_Shoe',shoe,color=orange,note='M3x16 through the replacement jaw; captive M3 nut. Print side down, support only nut pocket.',orientation=A.Placement(V(),A.Rotation(V(1,0,0),-90)))
leftshoe=mirror_x(shoe);add('02_Left_Retention_Shoe',leftshoe,color=orange,note='Mirror shoe. M3x16 and M3 hex nut.',orientation=A.Placement(V(),A.Rotation(V(1,0,0),-90)))

# One-piece receiver with a larger rear pocket and a narrower retaining mouth.
receiver=union(box(-27.6,-11.3,40,55.2,26.6,20.8),box(-33,-13,57.8,66,30,3))
receiver=subtract(receiver,box(-20.1,-8.3,39,40.2,20.6,6.4),box(-24.6,-8.3,45.4,49.2,20.6,12.4))
# Lead-in on the first 1.2mm of the mouth; the retaining lip remains intact.
lead=Part.makeLoft([Part.Wire(Part.makePolygon([V(-21.2,-9.4,39.9),V(21.2,-9.4,39.9),V(21.2,13.4,39.9),V(-21.2,13.4,39.9),V(-21.2,-9.4,39.9)])),Part.Wire(Part.makePolygon([V(-20.1,-8.3,41.2),V(20.1,-8.3,41.2),V(20.1,12.3,41.2),V(-20.1,12.3,41.2),V(-20.1,-8.3,41.2)]))],True)
receiver=subtract(receiver,lead)
for x in (-29,29):
    for y in (-8,8):receiver=subtract(receiver,cyl(1.65,5,x,y,57),cyl(3,3.2,x,y,54.7))
add('03_Expansion_Receiver',receiver,color=blue,note='Entry face down with removable internal supports. Clean the 40.2mm throat and shoulders before testing.')

# Angled split collar. Its entire 30mm contact length sits inside the 40mm cool section.
R=11.7;r=P['bore_diameter_mm']/2;L=P['clamp_length_mm']
ring=subtract(cyl(R,L,0,0,-L/2),cyl(r,L+2,0,0,-L/2-1))
low=ring.common(box(-20,-20,-L/2-1,40,19.75,L+2))
cap=ring.common(box(-20,.25,-L/2-1,40,20,L+2))
for x in (-12.5,12.5):
    low=union(low,box(x-3.5,-5,-5,7,4.75,10));cap=union(cap,box(x-3.5,.25,-5,7,4.75,10))
    low=subtract(low,cyl(1.65,8,x,-6,0,V(0,1,0)),hex_y(x,0,-5.1,2.6))
    cap=subtract(cap,cyl(1.65,8,x,0,0,V(0,1,0)))
collar_pose=A.Placement(V(0,2,85),A.Rotation(V(1,0,0),P['tool_angle_deg']))
low=transform(low,collar_pose);cap=transform(cap,collar_pose)
base=box(-33,-13,60.8,66,30,4)
for x in (-29,29):
    for y in (-8,8):base=subtract(base,cyl(1.65,6,x,y,60),hex_z(x,y,62.3,2.6))
# Two side webs connect the rear mounting plate to the cool-handle saddle.
webs=[]
for x in (-7.5,4.5):
    upper=collar_pose.multVec(V(0,-7,10));lower=collar_pose.multVec(V(0,-7,-10))
    pts=[V(x,-8,64.8),V(x,12,64.8),V(x,upper.y,upper.z),V(x,lower.y,lower.z),V(x,-8,64.8)]
    webs.append(Part.Face(Part.makePolygon(pts)).extrude(V(3,0,0)))
saddle=union(base,low,*webs)
# Recut the bore through supporting material to preserve the full 13.4mm passage.
saddle=subtract(saddle,transform(cyl(r,L+4,0,0,-L/2-2),collar_pose))
add('04_Angled_Handle_Saddle',saddle,color=green,note='4x M3x8 to receiver; captive nuts. Collar bore 13.4mm. Supports under the angled saddle may be required.')
add('05_Handle_Clamp_Cap',cap,color=green,note='2x M3x12 and M3 nuts. Tighten evenly against the cool handle only.',orientation=A.Placement(V(),A.Rotation(V(1,0,0),-P['tool_angle_deg'])))

# Replacement jaws preserve the exact original mesh and add only the shoe bolt hole.
for side,name in ((1,'JawR'),(-1,'JawL')):
    mesh=Mesh.Mesh(str(ROOT.parent/'solidcraft_import'/'brazo_compacto'/'stl'/(name+'.stl')))
    shell=Part.Shape();shell.makeShapeFromMesh(mesh.Topology,.01)
    solid=Part.makeSolid(Part.Shell(shell.Faces));solid.translate(V(0,-14.5,-376))
    solid=subtract(solid,cyl(1.6,10,side*10.6,-5,50.5,V(0,1,0)))
    add('06_JawR_M3' if side==1 else '07_JawL_M3',solid,color=gray,note='Exact original jaw geometry plus one 3.2mm through-hole for shoe retention. Print flat.',orientation=A.Placement(V(),A.Rotation(V(1,0,0),-90)))

coupon=box(-12,-12,0,72,24,5)
for i,diameter in enumerate((13.,13.2,13.4)):
    coupon=subtract(coupon,cyl(diameter/2,7,i*24,0,-1))
    for k in range(i+1):coupon=subtract(coupon,box(i*24-3+k*3,10,3,1,3,3))
add('08_Handle_Fit_Coupon',coupon,color=orange,note='One notch: 13.0; two: 13.2; three: 13.4mm. Check the real handle before printing the clamp.')

# Native model moves original jaws and shoes through the same coupled opening.
for name in ('03_Expansion_Receiver','04_Angled_Handle_Saddle','05_Handle_Clamp_Cap'):install(name)
for side,jaw,shoe_name in ((1,'06_JawR_M3','01_Right_Retention_Shoe'),(-1,'07_JawL_M3','02_Left_Retention_Shoe')):
    group=D.addObject('App::Part','Right_Jaw' if side==1 else 'Left_Jaw');assembly.addObject(group)
    group.Placement=A.Placement(V(side*10.6,0,0),A.Rotation(V(0,1,0),side*P['latch_angle_deg']))
    group.setExpression('Placement.Rotation.Angle',('' if side==1 else '-')+'Toolhead_Controls.Opening')
    for name in (jaw,shoe_name):install(name,group,A.Placement(V(-side*10.6,0,0),A.Rotation()))

# Transparent reference envelope: 40mm usable handle, 53mm forward shaft to tip.
reference=union(cyl(6.5,40,0,0,-20),cyl(2.2,53,0,0,20))
reference=transform(reference,collar_pose)
o=D.addObject('PartDesign::Feature','Reference_13mm_Tool');assembly.addObject(o);o.Shape=reference
o.addProperty('App::PropertyString','Note');o.Note='Envelope only; diameter 13, usable handle 40, tip 73 from collar centre. Tool mass and hot-zone temperatures unknown.'
if o.ViewObject:o.ViewObject.ShapeColor=(.3,.3,.35);o.ViewObject.Transparency=45
for o in catalog.Group:o.Visibility=False
catalog.Visibility=False
D.recompute();D.saveAs(str(ROOT/'Expanding_Toolhead_13mm.FCStd'))
# Flatten parent transforms explicitly so STEP and previews match the native assembly.
installed=[o for o in D.Objects if o.TypeId=='PartDesign::Feature' and o not in catalog.Group]
flattened=[];render_scene=[]
for obj in installed:
    shape=obj.Shape.copy();shape.Placement=obj.getGlobalPlacement();flattened.append(shape)
    mesh=MeshPart.meshFromShape(Shape=shape,LinearDeflection=.08,AngularDeflection=.15,Relative=False)
    mesh.write(str(ROOT/'renders'/(obj.Name+'.stl')))
    render_scene.append({'name':obj.Name,'mesh':obj.Name+'.stl','color':list(obj.ViewObject.ShapeColor)})
Part.makeCompound(flattened).exportStep(str(ROOT/'Toolhead_Assembly.step'))
cut_receiver=receiver.cut(box(-50,-40,35,100,42,40))
MeshPart.meshFromShape(Shape=cut_receiver,LinearDeflection=.08,AngularDeflection=.15,Relative=False).write(str(ROOT/'renders'/'Receiver_Cutaway.stl'))
(ROOT/'renders'/'scene.json').write_text(json.dumps(render_scene,indent=2))

# Kinematic checks use the actual source-derived jaw meshes and actual new solids.
checks=[]
for angle in (0.,4.5,5.5,6.):
    clashes=[]
    for side,jaw,sh in ((1,'06_JawR_M3','01_Right_Retention_Shoe'),(-1,'07_JawL_M3','02_Left_Retention_Shoe')):
        moving=union(rotor(parts[jaw][0],side,angle),rotor(parts[sh][0],side,angle))
        volume=moving.common(receiver).Volume
        if volume>.05:clashes.append({'side':side,'volume_mm3':volume})
    checks.append({'opening_deg':angle,'receiver_interferences':clashes})
insertion=[]
for dz in (0.,-2.,-5.,-10.,-15.,-20.):
    volume=sum(rotor(parts[n][0],side,0,dz).common(receiver).Volume for side,n in ((1,'01_Right_Retention_Shoe'),(-1,'02_Left_Retention_Shoe'),(1,'06_JawR_M3'),(-1,'07_JawL_M3')))
    insertion.append({'axial_offset_mm':dz,'interference_mm3':volume})
# A pullout sweep must hit the lip when open, and remain clear when closed.
withdrawal=[]
for angle in (0.,4.5,5.5,6.):
    samples=[]
    for dz in (-1.,-2.,-4.,-8.,-12.):
        volume=sum(rotor(parts[n][0],side,angle,dz).common(receiver).Volume for side,n in ((1,'01_Right_Retention_Shoe'),(-1,'02_Left_Retention_Shoe')))
        samples.append({'axial_offset_mm':dz,'interference_mm3':volume})
    withdrawal.append({'opening_deg':angle,'samples':samples,'lip_blocks_axial_withdrawal':any(v['interference_mm3']>.05 for v in samples)})
report={'parameters':P,'frame':'Jaw pivots +/-10.6 X, 0 Y, 0 Z; +Z insertion. Original CAD shifted Y=-14.5 and Z=-376.',
    'opening_checks':checks,'closed_insertion_samples':insertion,'withdrawal_checks':withdrawal,
    'parts':[{'part':name,'volume_mm3':shape.Volume,'solid_valid':shape.isValid(),'solids':len(shape.Solids),'fully_solid_PLA_mass_g':shape.Volume*.00124,'note':note} for name,(shape,color,note) in parts.items()],
    'limits':'Geometric and export checks only. No certified retention force, print-fit, thermal or physical validation.'}
(ROOT/'validation.json').write_text(json.dumps(report,indent=2))
print('OPENING CHECKS',json.dumps(checks),flush=True);print('INSERTION',json.dumps(insertion),flush=True)
print('Saved native FreeCAD model, STEP files and 8 closed STL parts.',flush=True)
