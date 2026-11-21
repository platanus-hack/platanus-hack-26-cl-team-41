"""FreeCAD 1.1 BREP generator. Run with FreeCAD's bundled Python, or run BuildArm.FCMacro.
All dimensions are mm. See README.md before manufacturing. No third-party CAD modules.
"""
import os, sys, math, json, csv, traceback
from pathlib import Path
import FreeCAD as A
import Part, MeshPart
import FreeCADGui as Gui
Gui.showMainWindow()
Gui.activateWorkbench('PartWorkbench')
Gui.getMainWindow().hide()

ROOT = Path(__file__).resolve().parent
P = json.loads((ROOT / 'parameters.json').read_text())
V = A.Vector
DOC = A.newDocument('MG995_5DOF_Arm')
CAT = DOC.addObject('App::Part', 'Print_Catalog')
ASM = DOC.addObject('App::Part', 'Desk_Assembly')
REF = DOC.addObject('App::Part', 'Purchased_References')
catalog, instances, hardware, records = {}, [], [], []
BLUE=(0.12,0.38,0.57); TEAL=(0.10,0.63,0.62); ORANGE=(0.96,0.47,0.17)
DARK=(0.12,0.14,0.17); METAL=(0.65,0.69,0.72)

def box(x,y,z,dx,dy,dz): return Part.makeBox(dx,dy,dz,V(x,y,z))
def cyl(r,h,x=0,y=0,z=0,d=V(0,0,1)): return Part.makeCylinder(r,h,V(x,y,z),d)
def fuse(*ss):
    return ss[0].multiFuse(list(ss[1:])).removeSplitter() if len(ss)>1 else ss[0]
def cut(s,*tools):
    for t in tools: s=s.cut(t)
    return s.removeSplitter()
def moved(s, p):
    n=s.copy(); n.Placement=p.multiply(n.Placement); return n
def place(x=0,y=0,z=0,rot=None): return A.Placement(V(x,y,z),rot or A.Rotation())
def rz(deg): return A.Rotation(V(0,0,1),deg)
def compose(*pp):
    out=A.Placement()
    for pp1 in pp: out=out.multiply(pp1)
    return out
def poly(points, height, z=0):
    pts=[V(x,y,z) for x,y in points]; pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts)).extrude(V(0,0,height))
def rounded_rect(w,h,r,z,t):
    return fuse(box(-w/2+r,-h/2,z,w-2*r,h,t),box(-w/2,-h/2+r,z,w,h-2*r,t),
                *[cyl(r,t,x,y,z) for x in (-w/2+r,w/2-r) for y in (-h/2+r,h/2-r)])
def slot(cx,cy,length,d,z,h,along='x'):
    a=(length-d)/2
    if along=='x': return fuse(cyl(d/2,h,cx-a,cy,z),cyl(d/2,h,cx+a,cy,z),box(cx-a,cy-d/2,z,2*a,d,h))
    return fuse(cyl(d/2,h,cx,cy-a,z),cyl(d/2,h,cx,cy+a,z),box(cx-d/2,cy-a,z,d,2*a,h))
def polar(r,ang): return r*math.cos(ang),r*math.sin(ang)
def gear(n,m,h=8,phase=0):
    """20 degree full-depth involute spur, explicit sampled involute flanks, 0.2mm backlash per gear."""
    rp=m*n/2; rb=rp*math.cos(math.radians(20)); ra=rp+m; rf=rp-1.25*m
    half=math.pi/(2*n)-P['gear_backlash_mm']/(2*rp)
    def inv(r):
        if r<=rb: return 0
        a=math.acos(rb/r); return math.tan(a)-a
    ip=inv(rp); pts=[]
    for k in range(n):
        c=2*math.pi*k/n+math.radians(phase)
        r0=max(rb,rf); a0=half+ip-inv(r0)
        pts.append(polar(rf,c-a0))
        for j in range(10):
            r=r0+(ra-r0)*j/9; pts.append(polar(r,c-half-ip+inv(r)))
        at=half+ip-inv(ra)
        for j in range(1,5): pts.append(polar(ra,c-at+2*at*j/4))
        for j in range(1,10):
            r=ra-(ra-r0)*j/9; pts.append(polar(r,c+half+ip-inv(r)))
        pts.append(polar(rf,c+a0))
        end=2*math.pi*(k+1)/n+math.radians(phase)-a0
        for j in range(1,5): pts.append(polar(rf,c+a0+(end-c-a0)*j/4))
    return poly(pts,h)

def horn_holes(s,z,h):
    s=cut(s,cyl(4,h,0,0,z))
    # Adjustable radii 8.5..11.5mm; the actual horn must be transfer-drilled.
    for a in (0,90,180,270):
        t=slot(10,0,5.5,2.5,z,h)
        t=moved(t,place(rot=rz(a))); s=cut(s,t)
    return s

def saddle(tail=True, rear=True):
    # Shaft/horn face is z=0. Case length points toward -X.
    mount=box(-42,-18,-20,63,36,4)
    # Measured case clearance, not overall flange dimensions.
    cl=P['case_clearance_mm']; bl=P['servo_body_length_mm']; bw=P['servo_body_width_mm']
    x0=-P['shaft_from_near_end_mm']-(bl-P['shaft_from_near_end_mm']) # -body far end, reset below
    far=bl-P['shaft_from_near_end_mm']
    mount=cut(mount,box(-far-cl/2,-(bw+cl)/2,-22,bl+cl,bw+cl,8))
    for x in (-35,14.5):
        for y in (-5,5): mount=cut(mount,slot(x,y,7,3.5,-22,9))
    # The ears rest on the top surface at -16; 1mm shim washers tune actual horn height.
    rails=[box(-42,y,-48,63,5,28) for y in (-18,13)]
    items=[mount]+rails
    if rear:
        deck=box(-42,-18,-50,56,36,2)
        deck=cut(deck,box(-43,-6,-52,17,12,6)) # cable exit
        ring=cut(cyl(12,7,0,0,-55),cyl(P['bearing_625_seat_mm']/2,5.05,0,0,-55.05),cyl(3,10,0,0,-56))
        deck=cut(deck,cyl(3,6,0,0,-52))
        items += [deck,ring]
    if tail:
        items += [box(-52,y,-58,10,10,58) for y in (-16,6)]
    s=fuse(*items)
    if tail:
        for y in (-11,11): s=cut(s,cyl(1.75,70,-47,y,-64))
    if rear:
        for x,y in ((-7.1,7.1),(7.1,-7.1)):
            s=cut(s,cyl(1.05,7,x,y,-55.1))
    return s

def cheek(L,z,drive='horn'):
    length=L-42
    s=fuse(cyl(18,5,0,0,z),box(0,-15,z,length,30,5))
    if drive=='horn': s=horn_holes(s,z-1,7)
    else: s=cut(s,cyl(2.65,8,0,0,z-1))
    for y in (-11,11): s=cut(s,cyl(1.75,8,L-47,y,z-1))
    # Lightening window leaves 5+mm perimeter and a solid fastener zone.
    if length>45: s=cut(s,slot(31,0,20,12,z-1,7))
    return s

def bearing_retainer():
    s=cut(cyl(12,1.5,0,0,-56.5),cyl(5,3,0,0,-57))
    for x,y in ((-7.1,7.1),(7.1,-7.1)): s=cut(s,cyl(1.25,3,x,y,-57))
    return s
def bearing625(): return cut(cyl(8,5,0,0,-55),cyl(2.5,7,0,0,-56))
def spacer(z=-58,h=3): return cut(cyl(4,h,0,0,z),cyl(2.65,h+2,0,0,z-1))

def servo():
    body=box(-30.5,-9.85,-43,40.7,19.7,37)
    ears=box(-37,-9.85,-16,54,19.7,3)
    s=fuse(body,ears,cyl(6,5,0,0,-6))
    for x in (-35,14.5):
        for y in (-5,5): s=cut(s,cyl(1.6,5,x,y,-17))
    return s
def horn():
    return cut(cyl(10.5,2,0,0,-2),cyl(1.6,4,0,0,-3))

def add_part(name,shape,qty,color=BLUE,note='',orient=None):
    shape=shape.removeSplitter()
    if not shape.isValid() or len(shape.Solids)!=1:
        raise ValueError('%s invalid or disconnected: valid=%s solids=%d'%(name,shape.isValid(),len(shape.Solids)))
    obj=DOC.addObject('PartDesign::Feature',name)
    obj.Label=name.replace('_',' '); obj.Shape=shape; CAT.addObject(obj)
    for typ,key,val in [('App::PropertyInteger','PrintQuantity',qty),('App::PropertyString','ManufacturingNote',note),('App::PropertyString','Material','PETG / PLA+ prototype')]:
        obj.addProperty(typ,key,'Manufacturing'); setattr(obj,key,val)
    catalog[name]=(obj,color)
    if obj.ViewObject: obj.ViewObject.ShapeColor=color
    # Export in explicit bed orientation, translated to positive Z.
    ss=moved(shape,orient or A.Placement()); bb=ss.BoundBox
    ss.translate(V(-bb.XMin,-bb.YMin,-bb.ZMin))
    mesh=MeshPart.meshFromShape(Shape=ss,LinearDeflection=0.08,AngularDeflection=0.15,Relative=False)
    mesh.write(str(ROOT/'stl'/(name+'.stl')))
    # Recheck triangulation and a mesh->solid roundtrip in FreeCAD.
    if not mesh.isSolid(): raise ValueError('Non-watertight STL: '+name)
    records.append({'part':name,'qty':qty,'volume_mm3':round(shape.Volume,2),
        'stl_size_mm':[round(ss.BoundBox.XLength,2),round(ss.BoundBox.YLength,2),round(ss.BoundBox.ZLength,2)],
        'triangles':mesh.CountFacets,'brep_valid':True,'solids':1,'mesh_closed':True,'note':note})
    return obj

def inst(name,p=A.Placement(),suffix='',group=ASM):
    src,color=catalog[name]; obj=DOC.addObject('PartDesign::Feature',name+suffix+'_installed')
    obj.Shape=moved(src.Shape,p); obj.Label=name.replace('_',' ')+suffix; group.addObject(obj)
    if obj.ViewObject: obj.ViewObject.ShapeColor=color
    instances.append((obj,name)); return obj
def ref(name,shape,p=A.Placement(),color=DARK):
    obj=DOC.addObject('PartDesign::Feature','REF_'+name); obj.Label='REFERENCE - '+name
    obj.Shape=moved(shape,p); REF.addObject(obj)
    if obj.ViewObject: obj.ViewObject.ShapeColor=color
    hardware.append(obj); return obj

def make_bases():
    # Same 90 x 70 M4 interface for both adapters.
    desk=rounded_rect(200,180,15,0,8)
    for x in (-45,45):
        for y in (-35,35): desk=cut(desk,cyl(2.25,12,x,y,-1))
    for x in (-85,85):
        for y in (-75,75): desk=cut(desk,cyl(2.75,12,x,y,-1))
    desk=cut(desk,cyl(9,12,-65,0,-1))
    add_part('01_Desk_Base',desk,1,BLUE,'Bolt or clamp to desk; 4 x M5 anchor holes. 200 x 180 bed footprint.')
    ch=rounded_rect(160,130,8,0,6)
    for x in (-45,45):
        for y in (-35,35): ch=cut(ch,cyl(2.25,10,x,y,-1))
    for x in (-48,48):
        for y in (-50,50): ch=cut(ch,slot(x,y,36,4.5,-1,10))
    for x in (-70,70):
        for y in (-20,20): ch=cut(ch,slot(x,y,32,4.5,-1,10,'y'))
    ch=cut(ch,cyl(9,10,-55,0,-1))
    add_part('02_Chassis_Adapter',ch,1,BLUE,'Alternative to desk base. Slots accept M4; drill chassis to suit if patterns do not align.')
    foot=rounded_rect(120,100,8,0,6)
    for x in (-45,45):
        for y in (-35,35):
            foot=cut(foot,cyl(2.25,8,x,y,-1))
            # Captive M4 hex nut, entered from above.
            nut=poly([polar(4.15,math.radians(30+60*k)) for k in range(6)],3.6,2.4)
            foot=cut(foot,moved(nut,place(x,y,0)))
    pillars=[]
    for x in (-32,32):
        for y in (-25,25):
            c=box(x-5,y-5,6,10,10,44)
            c=cut(c,cyl(1.25,13,x,y,38)); pillars.append(c)
    sd=moved(saddle(False,False),place(0,0,56))
    # Carry the mounting rails down to the foot without blocking the servo case.
    legs=[box(-42,y,6,63,5,30) for y in (-18,13)]
    yaw=fuse(foot,sd,*pillars,*legs)
    add_part('03_Yaw_Servo_Stand',yaw,1,BLUE,'Print upright. Localized supports under servo mounting ledges. Captive M4 nuts in floor.')
    bridge=rounded_rect(76,62,5,50,4)
    ring=cut(cyl(27,9.2,0,0,52),cyl(18,12,0,0,51),cyl(P['bearing_6806_seat_mm']/2,7.3,0,0,54))
    bridge=fuse(cut(bridge,cyl(18,8,0,0,49)),ring)
    for x in (-32,32):
        for y in (-25,25): bridge=cut(bridge,cyl(1.75,8,x,y,49))
    for a in (0,120,240):
        x,y=polar(24,math.radians(a)); bridge=cut(bridge,cyl(1.05,8,x,y,55))
    add_part('04_Yaw_Bearing_Bridge',bridge,1,TEAL,'42.2 mm seat for 6806-2RS, 30 x 42 x 7. Print flat underside down.')
    keeper=cut(cyl(27,1.5,0,0,61.2),cyl(18,3,0,0,60.5))
    for a in (0,120,240):
        x,y=polar(24,math.radians(a)); keeper=cut(keeper,cyl(1.25,4,x,y,60))
    add_part('05_Yaw_Outer_Retainer',keeper,1,ORANGE,'3 x M2 x 6 self tapping; only capture outer race, no preload.')
    top=fuse(cyl(75,6,0,0,64),cyl(17,3,0,0,61),cyl(P['yaw_hub_od_mm']/2,7,0,0,54))
    top=cut(top,cyl(11,2.1,0,0,53.95))
    top=horn_holes(top,55.9,15)
    for x,y in ((10,0),(-10,0),(0,10),(0,-10)): top=cut(top,cyl(3.5,10,x,y,61))
    for a in (30,150,270):
        x,y=polar(13,math.radians(a)); top=cut(top,cyl(1.05,8,x,y,53))
    for x in (-45,30):
        for y in (-24,24): top=cut(top,cyl(2.25,10,x,y,62))
    add_part('06_Yaw_Platform',top,1,TEAL,'Print top face on bed (STL already flipped). Stock horn inside hub; 4 transfer-drilled M2 holes.',place(rot=A.Rotation(V(1,0,0),180)))
    lock=cut(cyl(17,2,0,0,52),cyl(11,4,0,0,51))
    for a in (30,150,270):
        x,y=polar(13,math.radians(a)); lock=cut(lock,cyl(1.25,4,x,y,51))
    add_part('07_Yaw_Inner_Retainer',lock,1,ORANGE,'3 x M2 x 6 to rotating hub; bearing inner race only.')

def make_shoulder():
    foot=box(-85,-65,-58,105,6,61)
    for x in (-70,5):
        for z in (-53,-5): foot=cut(foot,cyl(2.25,10,x,-66,z,V(0,1,0)))
    motor=moved(saddle(False,False),place(-45,0,0))
    webs=[box(-85,-59,z,61,43,4) for z in (-48,-20)]
    front=box(-13,-59,-9,26,59,7)
    front=fuse(front,cyl(13,7,0,0,-9))
    front=cut(front,cyl(3,12,0,0,-10),cyl(P['bearing_625_seat_mm']/2,5.05,0,0,-7))
    rear=box(-13,-59,-55,26,59,7)
    rear=fuse(rear,cyl(13,7,0,0,-55))
    rear=cut(rear,cyl(3,12,0,0,-56),cyl(P['bearing_625_seat_mm']/2,5.05,0,0,-55.05))
    tower=fuse(foot,motor,*webs,front,rear)
    for z in (-9,-55):
        for x,y in ((-7.1,7.1),(7.1,-7.1)): tower=cut(tower,cyl(1.05,8,x,y,z-0.1))
    # Tolerance: motor flange screw slots also permit 1mm mesh adjustment along X.
    add_part('08_Shoulder_Tower',tower,1,BLUE,'Print foot down with supports at bearing seats and motor ledges. Shoulder ratio 2:1.',place(rot=A.Rotation(V(1,0,0),90)))
    g=horn_holes(gear(20,1.5,8),-1,10)
    add_part('09_Shoulder_Drive_20T',g,1,ORANGE,'Module 1.5, 20T. Stock horn required. Adjust case on slotted mount to set backlash.')
    L=P['upper_link_mm']
    upper=fuse(gear(40,1.5,8,4.5),box(0,-15,0,L-42,30,8))
    upper=cut(upper,cyl(2.65,10,0,0,-1))
    for y in (-11,11): upper=cut(upper,cyl(1.75,10,L-47,y,-1))
    upper=cut(upper,slot(35,0,18,10,-1,10))
    add_part('10_Upper_Front_40T',upper,1,TEAL,'Driven shoulder gear is integral with front link. Flat on bed.')
    add_part('11_Upper_Rear',cheek(L,-63,'idler'),1,TEAL,'Flat on bed. M5 stub axle at shoulder, 2 long M3 tie bolts at distal tail.')
    add_part('12_Elbow_Saddle',moved(saddle(),place(L,0,0)),1,BLUE,'Servo case faces back along the upper link; 2 x M3 x 75 tie bolts.',place(rot=A.Rotation(V(0,1,0),90)))

def make_fore_wrist():
    L=P['fore_link_mm']
    add_part('13_Forearm_Front',cheek(L,0),1,TEAL,'Stock elbow horn. Transfer drill horn to 2-4 of the radial slots.')
    add_part('14_Forearm_Rear',cheek(L,-63,'idler'),1,TEAL,'M5 stub axle + 625ZZ idler.')
    add_part('15_Wrist_Pitch_Saddle',moved(saddle(),place(L,0,0)),1,BLUE,'Wrist pitch servo with rear 625ZZ support.',place(rot=A.Rotation(V(0,1,0),90)))
    # A short U yoke carries a transverse roll servo; its axis points along the hand.
    def wp(z,mode):
        s=fuse(cyl(18,5,0,0,z),box(0,-15,z,39,30,5))
        s=horn_holes(s,z-1,7) if mode=='horn' else cut(s,cyl(2.65,8,0,0,z-1))
        for y in (-11,11): s=cut(s,cyl(1.75,8,34,y,z-1))
        return s
    add_part('16_Wrist_Yoke_Front',wp(0,'horn'),1,TEAL,'Stock wrist pitch horn.')
    add_part('17_Wrist_Yoke_Rear',wp(-63,'idler'),1,TEAL,'Passive wrist pitch M5 + 625ZZ support.')
    global ROLL_P
    # Basis x->Y, y->Z, z->X.
    mat=A.Matrix(); mat.A11=0;mat.A12=0;mat.A13=1;mat.A21=1;mat.A22=0;mat.A23=0;mat.A31=0;mat.A32=1;mat.A33=0
    ROLL_P=place(P['wrist_to_roll_mm'],10,-29,A.Rotation(mat))
    cradle=moved(saddle(False,True),ROLL_P)
    posts=[box(29,y,-58,10,10,58) for y in (-16,6)]
    carrier=fuse(cradle,*posts)
    for y in (-11,11): carrier=cut(carrier,cyl(1.75,70,34,y,-64))
    # The roll servo is directly coupled to the light gripper; no rear roll axle.
    add_part('18_Roll_Carrier',carrier,1,BLUE,'Roll servo axis is along reach. Empty rear bearing pocket is a lightening/access opening.',place(rot=A.Rotation(V(0,1,0),90)))
    add_part('19_625_Retainer',bearing_retainer(),4,ORANGE,'2 x M2 x 6 self tapping. Shoulder front uses the same retainer flipped.')
    add_part('20_M5_Spacer_3mm',spacer(),3,ORANGE,'Rear idlers: OD8 x ID5.3 x 3mm. Metal precision spacers preferred.')
    add_part('21_M5_Spacer_2mm',spacer(0,2),2,ORANGE,'Shoulder front and passive gripper jaw. Metal precision spacers preferred.')

def make_gripper():
    s=saddle(False,False)
    # Idler support projects to +X; bearing inserted from the gear side.
    support=box(18,-14,-20,26,28,18)
    support=fuse(support,cyl(13,7,30,0,-9))
    support=cut(support,cyl(3,22,30,0,-21),cyl(P['bearing_625_seat_mm']/2,5.05,30,0,-7))
    # Roll horn mounting disc, its normal is gripper +Y (the forward direction).
    disc=cyl(18,5,0,-35,-24,V(0,1,0))
    disc=cut(disc,cyl(4,8,0,-36,-24,V(0,1,0)))
    for x,z in ((10,-24),(-10,-24),(0,-14),(0,-34)):
        disc=cut(disc,cyl(1.25,8,x,-36,z,V(0,1,0)))
    bridge=box(-18,-30,-24,36,14,8)
    s=fuse(s,support,disc,bridge)
    # Drill after the bridge is fused: install on the roll horn BEFORE inserting J6.
    s=cut(s,cyl(4,23,0,-36,-24,V(0,1,0)))
    for x,z in ((10,-24),(-10,-24),(0,-14),(0,-34)):
        s=cut(s,cyl(1.25,23,x,-36,z,V(0,1,0)))
        s=cut(s,cyl(3,16,x,-30,z,V(0,1,0)))
    for x,y in ((22.9,7.1),(37.1,-7.1)): s=cut(s,cyl(1.05,8,x,y,-9.1))
    add_part('22_Gripper_Housing',s,1,BLUE,'Bolts to stock roll horn through four 2.5mm holes; transfer drill horn. Print on side with supports.',place(rot=A.Rotation(V(0,1,0),90)))
    finger=[(-10,9),(-2,9),(-2,42),(14.25,49),(14.25,61),(8,61),(8,54),(-10,47)]
    left=fuse(gear(24,1.25,6),poly(finger,6))
    left=horn_holes(left,-1,8)
    add_part('23_Gripper_Driven_Jaw',left,1,ORANGE,'24T module1.25; nominal closed 1.5mm pad gap. Add adhesive TPU/rubber grip strips.')
    right=fuse(gear(24,1.25,6,7.5),poly([(-x,y) for x,y in reversed(finger)],6))
    right=cut(right,cyl(2.65,9,0,0,-1))
    add_part('24_Gripper_Idler_Jaw',right,1,ORANGE,'Mirror finger; phase-shifted teeth mesh with driven jaw at 30mm centres.')
    # Fit coupon: body opening, one pair of slotted ear holes, bearing pockets, horn pad, gear sample.
    coupon=box(-45,-22,0,110,44,6)
    cl=P['case_clearance_mm']; far=P['servo_body_length_mm']-P['shaft_from_near_end_mm']
    coupon=cut(coupon,box(-far-cl/2,-(P['servo_body_width_mm']+cl)/2,-1,P['servo_body_length_mm']+cl,P['servo_body_width_mm']+cl,8))
    for x in (-35,14.5):
        for y in (-5,5): coupon=cut(coupon,slot(x,y,7,3.5,-1,8))
    coupon=cut(coupon,cyl(P['bearing_625_seat_mm']/2,5.2,31,0,0.8),cyl(3,8,31,0,-1),cyl(1.75,8,49,-12,-1),cyl(2.25,8,49,0,-1),cyl(2.65,8,49,12,-1))
    add_part('25_Fit_Coupon',coupon,1,ORANGE,'Print FIRST: servo body/ears, 625 bearing, M3/M4/M5 clearance holes.')
    ring=cut(cyl(26,9),cyl(P['bearing_6806_seat_mm']/2,7.2,0,0,1.8),cyl(18,12,0,0,-1))
    add_part('26_Yaw_Bearing_Coupon',ring,1,ORANGE,'Print FIRST: verify 6806 outer fit; use inner retainer/hub to check inner fit.')

def make_assembly():
    desk=place(); ZB=8
    inst('01_Desk_Base')
    for n in ('03_Yaw_Servo_Stand','04_Yaw_Bearing_Bridge','05_Yaw_Outer_Retainer','06_Yaw_Platform','07_Yaw_Inner_Retainer'):
        inst(n,place(0,0,ZB))
    ref('J1_MG995',servo(),place(0,0,ZB+56)); ref('J1_stock_horn',horn(),place(0,0,ZB+56),METAL)
    br=cut(cyl(21,7,0,0,54),cyl(15,9,0,0,53)); ref('6806_yaw_bearing',br,place(0,0,ZB),METAL)
    # Shoulder frame footprint x -60..45 on yaw platform. Datum includes desk adapter thickness.
    sh=place(25,-29,ZB+135,A.Rotation(V(1,0,0),90)); inst('08_Shoulder_Tower',sh)
    q=P['display_pose_deg']; up=compose(sh,place(rot=rz(q['shoulder'])))
    inst('09_Shoulder_Drive_20T',compose(sh,place(-45,0,0,rz(-2*q['shoulder']))))
    ref('J2_MG995',servo(),compose(sh,place(-45,0,0)))
    ref('J2_stock_horn',horn(),compose(sh,place(-45,0,0)),METAL)
    for n in ('10_Upper_Front_40T','11_Upper_Rear','12_Elbow_Saddle'): inst(n,up)
    elbow=compose(up,place(P['upper_link_mm'],0,0)); ref('J3_MG995',servo(),elbow); ref('J3_stock_horn',horn(),elbow,METAL)
    fore=compose(elbow,place(rot=rz(q['elbow'])))
    for n in ('13_Forearm_Front','14_Forearm_Rear','15_Wrist_Pitch_Saddle'): inst(n,fore)
    wrist=compose(fore,place(P['fore_link_mm'],0,0)); ref('J4_MG995',servo(),wrist); ref('J4_stock_horn',horn(),wrist,METAL)
    hand=compose(wrist,place(rot=rz(q['wrist_pitch'])))
    for n in ('16_Wrist_Yoke_Front','17_Wrist_Yoke_Rear','18_Roll_Carrier'): inst(n,hand)
    roll=compose(hand,ROLL_P); ref('J5_MG995',servo(),roll); ref('J5_stock_horn',horn(),roll,METAL)
    # Align gripper's roll-horn disc centre (0,-35,-24) with roll output at (0,0,0).
    gripRot=A.Rotation(V(1,0,0),90)
    gp=compose(roll,place(rot=rz(q['wrist_roll'])),place(0,-24,35,gripRot))
    inst('22_Gripper_Housing',gp)
    left=compose(gp,place(rot=rz(q['gripper_open'])))
    right=compose(gp,place(30,0,0,rz(-q['gripper_open'])))
    inst('23_Gripper_Driven_Jaw',left); inst('24_Gripper_Idler_Jaw',right)
    ref('J6_MG995',servo(),gp); ref('J6_stock_horn',horn(),gp,METAL)
    # Four rear/front retainers plus the fifth one used at the passive gripper pivot.
    for i,p in enumerate((sh,elbow,wrist)):
        ref('625_rear_%d'%i,bearing625(),p,METAL)
        inst('19_625_Retainer',p,'_rear%d'%i); inst('20_M5_Spacer_3mm',p,'_rear%d'%i)
    frontflip=place(0,0,-57,A.Rotation(V(1,0,0),180)) # -55..-50 -> -7..-2
    for name,p in (('shoulder',sh),('gripper',compose(gp,place(30,0,0)))):
        flip=compose(p,frontflip)
        ref('625_front_'+name,bearing625(),flip,METAL)
        inst('19_625_Retainer',flip,'_front_'+name)
        inst('21_M5_Spacer_2mm',compose(p,place(0,0,-2)),'_'+name)
    return {'shoulder':sh,'upper':up,'elbow':elbow,'fore':fore,'wrist':wrist,'hand':hand,'roll':roll,'gripper':gp}

def finalize(frames):
    # Correct catalogue quantity: three rear + shoulder front + gripper front.
    catalog['19_625_Retainer'][0].PrintQuantity=5
    for r in records:
        if r['part']=='19_625_Retainer': r['qty']=5
    params=DOC.addObject('Spreadsheet::Sheet','Design_Parameters'); params.Label='Design parameters - regenerate with build_arm.py'
    rows=[('Parameter','Value','Units / meaning'),('Upper link',P['upper_link_mm'],'mm, axis to axis'),('Forearm link',P['fore_link_mm'],'mm, axis to axis'),('Wrist to roll',P['wrist_to_roll_mm'],'mm'),('Shoulder reduction',2,'motor turns / output turn'),('Servo body length',P['servo_body_length_mm'],'mm'),('Servo body width',P['servo_body_width_mm'],'mm'),('Case total clearance',P['case_clearance_mm'],'mm'),('625 seat diameter',P['bearing_625_seat_mm'],'mm'),('6806 seat diameter',P['bearing_6806_seat_mm'],'mm'),('Yaw hub diameter',P['yaw_hub_od_mm'],'mm'),('Backlash per gear',P['gear_backlash_mm'],'mm at pitch circle'),('Provisional payload',P['provisional_payload_g'],'g, untested'),('Source','parameters.json + build_arm.py','Edit JSON and regenerate; sheet is informational.')]
    for i,row in enumerate(rows,1):
        for j,v in enumerate(row): params.set(chr(65+j)+str(i),str(v))
    params.setColumnWidth('A',190); params.setColumnWidth('B',130); params.setColumnWidth('C',390)
    DOC.recompute()
    # Save neutral BREP reference copies of purchase items as well as a full native document.
    for n,(o,c) in catalog.items(): Part.export([o],str(ROOT/'step'/(n+'.step')))
    Part.export([o for o,n in instances],str(ROOT/'MG995_5DOF_Desk_Assembly.step'))
    for o in CAT.Group: o.Visibility=False
    CAT.Visibility=False; ASM.Visibility=True; REF.Visibility=True
    if Gui.activeDocument():
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
    DOC.recompute(); DOC.saveAs(str(ROOT/'MG995_5DOF_Arm.FCStd'))
    # Flat positioned meshes make deterministic CAD-derived renders in Blender or any STL viewer.
    meshes=[]
    for i,(o,n) in enumerate(instances):
        f=ROOT/'renders'/('mesh_%02d.stl'%i)
        m=MeshPart.meshFromShape(Shape=o.Shape,LinearDeflection=0.15,AngularDeflection=0.2,Relative=False); m.write(str(f))
        meshes.append({'file':str(f),'name':o.Label,'color':list(catalog[n][1]),'purchased':False})
    for i,o in enumerate(hardware):
        f=ROOT/'renders'/('ref_%02d.stl'%i)
        m=MeshPart.meshFromShape(Shape=o.Shape,LinearDeflection=0.15,AngularDeflection=0.2,Relative=False); m.write(str(f))
        meshes.append({'file':str(f),'name':o.Label,'color':list(o.ViewObject.ShapeColor)[:3] if o.ViewObject else list(DARK),'purchased':True})
    (ROOT/'renders'/'scene.json').write_text(json.dumps(meshes,indent=2))
    # Detect actual positive-volume interferences in the displayed assembly, ignoring touching faces.
    collisions=[]
    for i,(a,na) in enumerate(instances):
        for b,nb in instances[i+1:]:
            if not a.Shape.BoundBox.intersect(b.Shape.BoundBox): continue
            vol=a.Shape.common(b.Shape).Volume
            if vol>0.05: collisions.append({'a':a.Label,'b':b.Label,'intersection_mm3':round(vol,3)})
    servo_clashes=[]
    for a,na in instances:
        for b in hardware:
            if 'MG995' not in b.Label: continue
            if not a.Shape.BoundBox.intersect(b.Shape.BoundBox): continue
            vol=a.Shape.common(b.Shape).Volume
            if vol>0.1: servo_clashes.append({'printed':a.Label,'servo':b.Label,'intersection_mm3':round(vol,3)})
    report={'freecad_version':A.Version()[:3],'units':'mm','parts':records,'display_pose':P['display_pose_deg'],
       'positive_volume_printed_collisions':collisions,'servo_envelope_collisions':servo_clashes,
       'scope':'BREP and closed STL validation plus displayed-pose interference only; no physical load, FEA or full-motion certification.'}
    (ROOT/'validation.json').write_text(json.dumps(report,indent=2))
    with (ROOT/'print_manifest.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['Part','Quantity','X_mm','Y_mm','Z_mm','Solid_CAD_volume_cm3','Printing_note'])
        for r in records: w.writerow([r['part'],r['qty'],*r['stl_size_mm'],round(r['volume_mm3']/1000,2),r['note']])
    print('GENERATED %d unique printable solids; %d assembled parts; %d purchased references.'%(len(catalog),len(instances),len(hardware)),flush=True)
    print('PRINTED COLLISIONS:',json.dumps(collisions),flush=True)
    print('SERVO COLLISIONS:',json.dumps(servo_clashes),flush=True)

if __name__=='__main__':
    try:
        make_bases(); make_shoulder(); make_fore_wrist(); make_gripper(); frames=make_assembly(); finalize(frames)
    except Exception:
        traceback.print_exc(); raise
