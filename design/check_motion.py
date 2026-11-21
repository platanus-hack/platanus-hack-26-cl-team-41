"""Sample-pose collision and conservative static gravity estimate using the actual FreeCAD solids."""
import FreeCAD as A, Part, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
P=json.loads((ROOT/'parameters.json').read_text())
D=A.openDocument(str(ROOT/'MG995_5DOF_Arm.FCStd'))
C={o.Name:o.Shape for o in D.Print_Catalog.Group}
V=A.Vector
def pl(x=0,y=0,z=0,a=0):return A.Placement(V(x,y,z),A.Rotation(V(0,0,1),a))
def chain(*args):
    p=A.Placement()
    for a in args:p=p.multiply(a)
    return p
def tr(s,p):
    s=s.copy();s.Placement=p.multiply(s.Placement);return s
def get(prefix):return next(s for n,s in C.items() if n.startswith(prefix))
def named(prefix):return next(n for n in C if n.startswith(prefix))
mat=A.Matrix();mat.A11=0;mat.A12=0;mat.A13=1;mat.A21=1;mat.A22=0;mat.A23=0;mat.A31=0;mat.A32=1;mat.A33=0
rp=A.Placement(V(P['wrist_to_roll_mm'],10,-29),A.Rotation(mat))
sh=A.Placement(V(25,-29,143),A.Rotation(V(1,0,0),90))
gr=A.Placement(V(0,-24,35),A.Rotation(V(1,0,0),90))
servo=next(o.Shape for o in D.Purchased_References.Group if 'J1_MG995' in o.Label)
# Reference geometry is saved in world coordinates; normalize to its horn face.
servo=tr(servo,pl(0,0,-64))
def pose(qs,qe,qw,qr=0,qg=16):
    up=chain(sh,pl(a=qs));el=chain(up,pl(P['upper_link_mm']));fo=chain(el,pl(a=qe))
    wr=chain(fo,pl(P['fore_link_mm']));ha=chain(wr,pl(a=qw));ro=chain(ha,rp);gp=chain(ro,pl(a=qr),gr)
    parts=[]
    def add(k,f):parts.append((named(k),tr(get(k),f)))
    add('08_',sh);add('09_',chain(sh,pl(-45,a=-2*qs)))
    for k in ('10_','11_','12_'):add(k,up)
    for k in ('13_','14_','15_'):add(k,fo)
    for k in ('16_','17_','18_'):add(k,ha)
    add('22_',gp);add('23_',chain(gp,pl(a=qg)));add('24_',chain(gp,pl(30,a=-qg)))
    servos=[('J2',tr(servo,chain(sh,pl(-45)))),('J3',tr(servo,el)),('J4',tr(servo,wr)),('J5',tr(servo,ro)),('J6',tr(servo,gp))]
    tip=gp.multVec(V(15,61,3))
    return parts,servos,tip,{'elbow':el,'wrist':wr,'roll':ro,'gripper':gp}

def collide(parts,servos):
    hits=[]
    for i,(na,a) in enumerate(parts):
        for nb,b in parts[i+1:]+servos:
            if not a.BoundBox.intersect(b.BoundBox):continue
            vol=a.common(b).Volume
            if vol>0.10:hits.append([na,nb,round(vol,3)])
    # Desk/yaw platform clearance for everything moving above the shoulder.
    for n,s in parts:
        if n.startswith(('08_','09_')):continue
        if s.BoundBox.ZMin<79:hits.append([n,'yaw_platform_height',round(s.BoundBox.ZMin,2)])
    return hits

tests=[('display',55,-65,20,0,16),('near_reach',15,0,0,0,0),('raised',95,-65,0,0,16),
       ('elbow_low_limit',55,-85,0,0,16),('elbow_high_limit',55,70,0,0,16),
       ('wrist_down',55,-45,-45,0,16),('wrist_up',55,-45,45,0,16),
       ('roll_left',55,-45,0,-80,16),('roll_right',55,-45,0,80,16),
       ('gripper_wide',55,-45,0,0,35)]
results=[]
for name,*q in tests:
    parts,servos,tip,frames=pose(*q);hits=collide(parts,servos)
    results.append({'name':name,'angles_deg':q,'collisions':hits,'tip_world_mm':list(tip)})
    print(name,json.dumps(hits),flush=True)

# At the deliberately conservative all-horizontal pose, use 80% of solid CAD PETG mass.
# This bounds neither dynamics nor FDM strength; actual slicer mass overrides the estimate.
parts,servos,tip,frames=pose(0,0,0,0,0)
moving=[(n,s) for n,s in parts if not n.startswith(('08_','09_'))]
rho=1.27e-6*0.80 # kg/mm3, PETG 1.27g/cm3 and conservative 80% solid mass assumption
mass=sum(s.Volume*rho for n,s in moving)
def centre(s):
    solids=s.Solids;v=sum(t.Volume for t in solids)
    out=V()
    for t in solids:out+=t.CenterOfMass*t.Volume/v
    return out
def moment(origin,exclude=()):
    m=sum((centre(s).x-origin)*s.Volume*rho/10 for n,s in moving if not n.startswith(exclude))
    return m
shoulder=moment(25)+sum((centre(s).x-25)*0.060/10 for n,s in servos if n!='J2')
elx=frames['elbow'].Base.x;wrx=frames['wrist'].Base.x
elbow=moment(elx,('10_','11_','12_'))+sum((centre(s).x-elx)*0.060/10 for n,s in servos if n in ('J4','J5','J6'))
wrist=moment(wrx,('10_','11_','12_','13_','14_','15_'))+sum((centre(s).x-wrx)*0.060/10 for n,s in servos if n in ('J5','J6'))
payload=P['provisional_payload_g']/1000
moments={'shoulder_output_kgf_cm':shoulder+(tip.x-25)*payload/10,
         'elbow_kgf_cm':elbow+(tip.x-elx)*payload/10,'wrist_pitch_kgf_cm':wrist+(tip.x-wrx)*payload/10}
moments['shoulder_servo_kgf_cm_assuming_75pct_efficiency']=moments['shoulder_output_kgf_cm']/(2*.75)
report={'sampled_poses':results,'all_sampled_poses_clear':all(not r['collisions'] for r in results),
 'static_estimate':{'method':'All horizontal, printed moving solids at 80% solid PETG density, each servo 60g; ignores fasteners, wires, acceleration and friction except 75% shoulder gear efficiency. No physical testing.',
 'moving_printed_mass_g':round(mass*1000,1),'payload_g':P['provisional_payload_g'],
 'moments':{k:round(v,2) for k,v in moments.items()}},
 'limits':'Sparse configuration samples only. Not a continuous swept-volume, fatigue, FEA or payload certification.'}
(ROOT/'motion_and_torque.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report['static_estimate'],indent=2),flush=True)
