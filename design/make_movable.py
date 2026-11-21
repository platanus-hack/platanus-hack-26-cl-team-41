"""Build a self-contained, expression-driven FreeCAD kinematic arm from the BREP catalogue.
No STL export, collision checking, add-on solver, or external Python proxy is used.
"""
from pathlib import Path
import FreeCAD as A, FreeCADGui as G, Part, json, math
ROOT=Path(__file__).resolve().parent
G.showMainWindow(); G.activateWorkbench('PartWorkbench'); G.getMainWindow().hide()
src=A.openDocument(str(ROOT/'MG995_5DOF_Arm.FCStd'))
templates={o.Label[:2]:(o.Shape.copy(),tuple(o.ViewObject.ShapeColor)[:3],o.Label) for o in src.Print_Catalog.Group}
servo=src.getObject('REF_J1_MG995').Shape.copy(); servo.translate(A.Vector(0,0,-64))
horn=src.getObject('REF_J1_stock_horn').Shape.copy(); horn.translate(A.Vector(0,0,-64))
A.closeDocument(src.Name)
D=A.newDocument('MG995_5DOF_Movable')
V=A.Vector
def p(x=0,y=0,z=0,angle=0,rotation=None):return A.Placement(V(x,y,z),rotation or A.Rotation(V(0,0,1),angle))
def group(name,parent=None,placement=None):
    o=D.addObject('App::Part',name)
    if parent:parent.addObject(o)
    if placement:o.Placement=placement
    return o
controls=D.addObject('App::DocumentObjectGroup','JointControls');controls.Label='Joint Controls - edit these angles'
for name,val,desc in [('BaseYaw',0,'J1 base rotation'),('ShoulderPitch',55,'J2 output angle, motor has 2:1 reduction'),('ElbowPitch',-65,'J3 angle relative to upper link'),('WristPitch',20,'J4 angle relative to forearm'),('WristRoll',0,'J5 rotation around hand axis'),('GripperOpening',16,'J6 jaw angle, 0 near closed, 35 open')]:
    controls.addProperty('App::PropertyAngle',name,'Joint Angles',desc);setattr(controls,name,val)
controls.addProperty('App::PropertyAngle','ShoulderServoCommand','Servo reference','Nominal centred 180-degree servo mapping')
controls.setExpression('ShoulderServoCommand','90 deg - 2 * (ShoulderPitch - 55 deg)')
controls.setEditorMode('ShoulderServoCommand',1)
controls.addProperty('App::PropertyLength','AdapterThickness','Mount');controls.AdapterThickness=8
controls.addProperty('App::PropertyString','Instructions','Help');controls.Instructions='Edit Joint Angles here, or run MoveArm.FCMacro for sliders. Save document to retain pose.'
controls.addProperty('App::PropertyString','MotionScope','Help');controls.MotionScope='Kinematic visualization; contact and collision limits are not enforced.'
robot=group('Robot_Mechanism',placement=p(z=8));robot.setExpression('Placement.Base.z','JointControls.AdapterThickness')
static=group('Fixed_Base',robot)
refs=[]
def item(key,parent,placement=None,name=None):
    shape,color,label=templates[key]
    o=D.addObject('PartDesign::Feature',name or ('Part_'+key+'_'+label[3:].replace(' ','_')))
    o.Label=label;o.Shape=shape.copy();parent.addObject(o)
    if placement:o.Placement=placement
    o.ViewObject.ShapeColor=color;o.ViewObject.LineColor=(0.12,0.16,0.20)
    o.ViewObject.DisplayMode='Flat Lines'
    o.addProperty('App::PropertyString','SourcePart','Design');o.SourcePart=label
    return o
def ref(name,shape,parent,placement=None,color=(0.10,0.12,0.15)):
    o=D.addObject('PartDesign::Feature','Ref_'+name);o.Label='MG995 '+name if name.startswith('J') else name
    o.Shape=shape.copy();parent.addObject(o)
    if placement:o.Placement=placement
    o.ViewObject.ShapeColor=color;o.ViewObject.LineColor=(0.1,0.1,0.1);refs.append(o);return o
desk=item('01',None if False else group('Desk_Adapter'),name='DeskMount')
chassisGroup=group('Chassis_Adapter');chassis=item('02',chassisGroup,name='ChassisMount');chassisGroup.Visibility=False;chassis.Visibility=False
for key in ('03','04','05','07'):item(key,static)
ref('J1_base',servo,static,p(z=56));ref('Stock_horn_J1',horn,static,p(z=56),(0.55,0.59,0.62))
def cylinder(r,h,z=0):return Part.makeCylinder(r,h,V(0,0,z))
br=cylinder(21,7,54).cut(cylinder(15,9,53));ref('6806_yaw_bearing',br,static,color=(0.62,0.66,0.70))
def rotor(name,parent,expr):
    o=group(name,parent);o.setExpression('Placement.Rotation.Angle',expr);return o
yaw=rotor('J1_Base_Yaw',robot,'JointControls.BaseYaw');item('06',yaw)
shoulder=group('Shoulder_Fixed_Frame',yaw,p(25,-29,135,rotation=A.Rotation(V(1,0,0),90)))
item('08',shoulder);ref('J2_shoulder',servo,shoulder,p(-45));ref('Stock_horn_J2',horn,shoulder,p(-45),(0.55,0.59,0.62))
drive=group('Shoulder_Motor_Gear',shoulder,p(-45));drive.setExpression('Placement.Rotation.Angle','-2 * JointControls.ShoulderPitch');item('09',drive)
upper=rotor('J2_Shoulder_Pitch',shoulder,'JointControls.ShoulderPitch')
for key in ('10','11','12'):item(key,upper)
elbow=group('Elbow_Fixed_Frame',upper,p(95));ref('J3_elbow',servo,elbow);ref('Stock_horn_J3',horn,elbow,color=(0.55,0.59,0.62))
fore=rotor('J3_Elbow_Pitch',elbow,'JointControls.ElbowPitch')
for key in ('13','14','15'):item(key,fore)
wrist=group('Wrist_Fixed_Frame',fore,p(85));ref('J4_wrist_pitch',servo,wrist);ref('Stock_horn_J4',horn,wrist,color=(0.55,0.59,0.62))
hand=rotor('J4_Wrist_Pitch',wrist,'JointControls.WristPitch')
for key in ('16','17','18'):item(key,hand)
mat=A.Matrix();mat.A11=0;mat.A12=0;mat.A13=1;mat.A21=1;mat.A22=0;mat.A23=0;mat.A31=0;mat.A32=1;mat.A33=0
rollframe=group('Roll_Fixed_Frame',hand,p(83,10,-29,rotation=A.Rotation(mat)))
ref('J5_wrist_roll',servo,rollframe);ref('Stock_horn_J5',horn,rollframe,color=(0.55,0.59,0.62))
roll=rotor('J5_Wrist_Roll',rollframe,'JointControls.WristRoll')
grip=group('Gripper_Fixed_Frame',roll,p(0,-24,35,rotation=A.Rotation(V(1,0,0),90)))
item('22',grip);ref('J6_gripper',servo,grip);ref('Stock_horn_J6',horn,grip,color=(0.55,0.59,0.62))
left=rotor('J6_Gripper_Driven',grip,'JointControls.GripperOpening');item('23',left)
right=rotor('Gripper_Coupled_Idler',grip,'-JointControls.GripperOpening');right.Placement.Base=V(30,0,0);item('24',right)
bearing=cylinder(8,5,-55).cut(cylinder(2.5,7,-56))
for fr,ro,name in ((shoulder,upper,'shoulder'),(elbow,fore,'elbow'),(wrist,hand,'wrist')):
    ref('625_'+name,bearing,fr,color=(.62,.66,.70));item('19',fr,name='Retainer_'+name);item('20',ro,name='Spacer_'+name)
flip=p(0,0,-57,rotation=A.Rotation(V(1,0,0),180))
for fr,name,offset in ((shoulder,'shoulder_front',p()),(grip,'gripper_idler',p(30))):
    fr2=group('BearingFrame_'+name,fr,offset);ref('625_'+name,bearing,fr2,flip,(.62,.66,.70));item('19',fr2,flip,name='Retainer_'+name);item('21',fr2,p(z=-2),name='Spacer_'+name)
marker=ref('Tool_reference',Part.makeSphere(1.5,V(15,61,3)),grip,color=(0.18,.8,.3));marker.Visibility=False
D.recompute()
# Verify the controls drive descendants, then restore the display pose; no collision checks.
checks=[]
for prop,child in [('BaseYaw',grip),('ShoulderPitch',grip),('ElbowPitch',grip),('WristPitch',grip),('WristRoll',grip),('GripperOpening',left)]:
    before=child.getGlobalPlacement();initial=getattr(controls,prop).Value
    setattr(controls,prop,initial+5);D.recompute();after=child.getGlobalPlacement()
    moved=not before.isSame(after,1e-7)
    if not moved:raise RuntimeError('Control failed: '+prop)
    checks.append({'control':prop,'descendant_updated':True})
    setattr(controls,prop,initial);D.recompute()
if G.activeDocument():
    G.activeDocument().activeView().viewAxonometric();G.activeDocument().activeView().fitAll()
D.recompute();D.saveAs(str(ROOT/'MG995_5DOF_Movable.FCStd'))
# Expressions survive reopening with no external module or custom object proxy.
A.closeDocument(D.Name);D=A.openDocument(str(ROOT/'MG995_5DOF_Movable.FCStd'))
old=D.JointControls.ElbowPitch.Value;D.JointControls.ElbowPitch=old+5;D.recompute()
assert abs(math.degrees(D.J3_Elbow_Pitch.Placement.Rotation.Angle)-(old+5))<1e-5
D.JointControls.ElbowPitch=old;D.recompute();D.save()
(ROOT/'kinematic_controls_check.json').write_text(json.dumps({'checks':checks,'reopen_expression_persistence':True,'collision_checks':'skipped at user request'},indent=2))
print('Movable FreeCAD document saved. Six controls and persistence verified.',flush=True)
