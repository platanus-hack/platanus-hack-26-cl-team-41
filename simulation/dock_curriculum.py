"""Learn upright docking reach targets and test the unwelded expansion receiver.

Collision decomposition follows the new CAD dimensions. Contact/material priors
remain uncalibrated. Phases/latch control are scripted, reaching is learned.
"""
import argparse,json,math,time,xml.etree.ElementTree as E
import numpy as np,mujoco
from manipulation_tasks import ManipulationTrial,ROOT
from build_scene import build,fmt
from curriculum_network import fit,Network
OUT=ROOT/'trained'/'curriculum';OUT.mkdir(parents=True,exist_ok=True)
SCENE=ROOT/'dock_curriculum_scene.xml'
TIP=np.array([.10317,.0145,.36351])

def upright_ik(point):
    x,y,z=np.asarray(point);rr=x*x+y*y-.0145**2
    if rr<=0:raise ValueError('Inside base axis')
    r=np.sqrt(rr);v=z-.2475;c=(r*r+v*v-.09**2-.085**2)/(2*.09*.085)
    if abs(c)>1:raise ValueError('Outside upright reach')
    e=np.arccos(c);s=np.arctan2(r,v)-np.arctan2(.085*np.sin(e),.09+.085*np.cos(e))
    q=np.array([np.arctan2(y,x)-np.arctan2(.0145,r),s,e,-s-e,0])
    if np.any(np.abs(q)>np.pi/2-.002):raise ValueError('Upright pose exceeds joints')
    return q

def train(epochs=140):
    rng=np.random.default_rng(909);x=[];y=[]
    while len(x)<10000:
        p=rng.uniform(TIP+[-.009,-.009,-.028],TIP+[.009,.009,.018])
        try:q=upright_ik(p)
        except ValueError:continue
        x.append(p);y.append(q[:3])
    _,report=fit(np.asarray(x),np.asarray(y),OUT/'dock_reach_policy.npz',epochs=epochs)
    (OUT/'dock_training_report.json').write_text(json.dumps(report,indent=2));return report

class DockPolicy:
    def __init__(self):self.net=Network(OUT/'dock_reach_policy.npz')
    def predict(self,p):
        p=np.asarray(p)
        if np.any(p<TIP+[-.009,-.009,-.028]) or np.any(p>TIP+[.009,.009,.018]):raise ValueError('Outside docking training region')
        q=self.net.predict(p);return np.r_[q,-q[1]-q[2],0]

def prepare():
    build(output_path=SCENE);tree=E.parse(SCENE);r=tree.getroot();world=r.find('worldbody');r.find('option').attrib.update(cone='elliptic',impratio='10',noslip_iterations='3',iterations='100')
    # Original jaws use local X=-common Z, local Y=side*10.6-common X,
    # local Z=common Y+2.5 mm. The SG90 hinge rotates common Y.
    def shoe(side):
        jaw=r.find(f".//body[@name='Jaw{'R' if side==1 else 'L'}_part']")
        boxes=[(16.55,0,52.25,1.65,4.5,5.25),(12.5,-3.65,51.15,5.7,.85,4.15),(12.5,3.65,51.15,5.7,.85,4.15),(12.5,0,56.4,5.7,4.5,1.1)]
        for i,(x,y,z,hx,hy,hz) in enumerate(boxes):
            pos=np.array([-z,side*(10.6-x),y+2.5])*.001
            E.SubElement(jaw,'geom',name=f'shoe_{side}_{i}',type='box',pos=fmt(pos),size=fmt(np.array([hz,hx,hy])*.001),rgba='.95 .4 .12 1',condim='6',friction='.3 .003 .0001')
    shoe(1);shoe(-1)
    holder=E.SubElement(world,'body',name='receiver',pos=fmt(TIP-[0,0,.0465]));E.SubElement(holder,'freejoint',name='receiver_free')
    E.SubElement(holder,'inertial',pos='0 -.004 .080',mass='.067',diaginertia='.00004 .00004 .000012')
    boxes=[(-26.1,2,50.4,1.5,13.3,10.4),(26.1,2,50.4,1.5,13.3,10.4),(0,-9.8,50.4,24.6,1.5,10.4),(0,13.8,50.4,24.6,1.5,10.4),
        (-22.35,2,42.7,2.25,10.3,2.7),(22.35,2,42.7,2.25,10.3,2.7),(0,2,59.3,33,15,1.5)]
    for i,box in enumerate(boxes):
        E.SubElement(holder,'geom',name=f'receiver_collision_{i}',type='box',pos=fmt(np.array(box[:3])*.001),size=fmt(np.array(box[3:])*.001),rgba='.12 .4 .55 .25',group='3',condim='6',friction='.3 .003 .0001')
    # CAD visuals are unchanged and non-colliding; concavity is represented by the boxes above.
    assets=r.find('asset')
    for name in ('03_Expansion_Receiver','04_Angled_Handle_Saddle','05_Handle_Clamp_Cap'):
        path=ROOT.parent/'toolhead_13mm'/'renders'/('_'+name+'_installed.stl')
        # Relative to the arm compiler's meshdir, so clones outside OneDrive work.
        E.SubElement(assets,'mesh',name=name,file='../../toolhead_13mm/renders/'+path.name,scale='.001 .001 .001')
        E.SubElement(holder,'geom',type='mesh',mesh=name,contype='0',conaffinity='0',group='2',rgba=('.12 .4 .55 1' if name.startswith('03') else '.15 .55 .3 1'))
    E.SubElement(holder,'geom',name='handle_proxy',type='cylinder',pos='0 .002 .085',size='.0065 .020',quat='.9238795 .3826834 0 0',rgba='.15 .17 .2 1')
    axis=np.array([0,-1/np.sqrt(2),1/np.sqrt(2)]);c=np.array([0,.002,.085])
    E.SubElement(holder,'geom',name='tip_proxy',type='capsule',fromto=fmt(np.r_[c+axis*.020,c+axis*.073]),size='.0022',rgba='.65 .68 .72 1')
    for side in (-1,1):
        b=E.SubElement(world,'body',name=f'cradle_{side}',pos=fmt(TIP-[0,0,.0465]))
        for k,y in enumerate((-.009,.013)):
            E.SubElement(b,'geom',name=f'cradle_pad_{side}_{k}',type='box',pos=fmt([side*.0315,y,.0548]),size='.0013 .003 .003',rgba='.45 .45 .5 1')
    E.indent(r);tree.write(SCENE,encoding='utf-8',xml_declaration=True);return SCENE

def evaluate(count=12,gif=False,view=False):
    prepare();policy=DockPolicy();results=[];frames=[]
    for n in range(count):
        seed=9300+n;rng=np.random.default_rng(seed);t=ManipulationTrial('block',seed,scene=SCENE);s=t.sim;m=s.model;d=s.data
        receiver=m.body('receiver').id;j=m.joint('receiver_free').id;adr=m.jnt_qposadr[j];dadr=m.jnt_dofadr[j]
        iron_mass=[.025,.050,.100][n%3];m.body_mass[receiver]=.042+iron_mass;m.body_inertia[receiver]*=m.body_mass[receiver]/.067
        goal=TIP+np.r_[rng.uniform(-.004,.004,2),0.];q=upright_ik(goal);yaw=q[0]
        quat=np.array([np.cos(yaw/2),0,0,np.sin(yaw/2)]);origin=goal-[0,0,.0465]
        for side in (-1,1):
            bid=m.body(f'cradle_{side}').id;m.body_pos[bid]=origin;m.body_quat[bid]=quat
        # Establish the exact initial free-body/cradle state after model-constant updates.
        mujoco.mj_setConst(m,d);d.qpos[adr:adr+3]=origin;d.qpos[adr+3:adr+7]=quat;d.qvel[dadr:dadr+6]=0
        approach=goal-[0,0,.022];qa=upright_ik(approach);d.qpos[s.qadr]=np.r_[qa,0.];d.qpos[m.jnt_qposadr[s.left]]=0
        s.targets=np.r_[qa,0.];s.servos.reset(s.targets);mujoco.mj_forward(m,d);t.last_point=approach.copy();viewer=None
        if view:
            from mujoco import viewer as mjviewer
            viewer=mjviewer.launch_passive(m,d);viewer.cam.lookat[:]=goal+[0,0,.025];viewer.cam.distance=.30;viewer.cam.azimuth=105;viewer.cam.elevation=-10;viewer.opt.geomgroup[3]=0
        def capture(tt,phase):
            if gif and n==0 and len(tt.records)%6==0:
                from PIL import Image,ImageDraw
                # A close camera exposing the entire arm and unwelded holder.
                if s.renderer is None:s.renderer=mujoco.Renderer(m,height=480,width=640)
                cam=mujoco.MjvCamera();cam.lookat[:]=goal+[0,0,.015];cam.distance=.33;cam.azimuth=110;cam.elevation=-15
                opt=mujoco.MjvOption();opt.geomgroup[3]=0;s.renderer.update_scene(d,camera=cam,scene_option=opt)
                im=Image.fromarray(s.renderer.render()).resize((480,360));ImageDraw.Draw(im).text((10,10),phase,fill='white');frames.append(im)
            if viewer:
                if not viewer.is_running():raise KeyboardInterrupt
                viewer.sync();time.sleep(.02)
        try:
            t.move(approach,0.,.5,'align_cold_holder',policy=policy,callback=capture)
            origin_start=d.xpos[receiver].copy()
            t.move(goal,0.,1.5,'insert_closed',policy=policy,callback=capture)
            t.move(goal,math.radians(5.5),1.,'open_to_latch',policy=policy,callback=capture)
            seated=d.xpos[receiver].copy()
            # Pull the free receiver away from the jaws, beyond its own weight.
            # No equality, weld or hidden attachment is used on the holder.
            d.xfrc_applied[receiver,2]=m.body_mass[receiver]*9.81+.15
            t.move(goal,math.radians(5.5),1.2,'axial_pull_test_0.15N_net',policy=policy,callback=capture)
            held=d.xpos[receiver].copy();held_delta=float(held[2]-seated[2]);lateral=float(np.linalg.norm(held[:2]-seated[:2]))
            latch_contacts=[[m.geom(int(c.geom[0])).name,m.geom(int(c.geom[1])).name] for c in d.contact if receiver in m.geom_bodyid[c.geom] and any(m.geom(int(g)).name.startswith('shoe_') for g in c.geom)]
            latch_angle=float(np.degrees(d.qpos[s.qadr[-1]]))
            # Release is performed unloaded on the fixture. Closing against an
            # off-axis pull can tilt and wedge this unsprung receiver.
            d.xfrc_applied[receiver]=0
            t.move(goal,math.radians(5.5),.8,'remove_pull_reseat_on_fixture',policy=policy,callback=capture)
            t.move(goal,0.,.8,'close_to_release',policy=policy,callback=capture)
            t.move(approach,0.,1.,'withdraw_gripper_from_holder',policy=policy,callback=capture)
            undocked=d.xpos[receiver].copy()
            # Repeat the external pull after undocking as a no-attachment control.
            d.xfrc_applied[receiver,2]=m.body_mass[receiver]*9.81+.15
            t.move(approach,0.,.3,'free_holder_pull_control',policy=policy,callback=capture)
            released=d.xpos[receiver].copy();release_delta=float(released[2]-undocked[2])
            release_contacts=[[m.geom(int(c.geom[0])).name,m.geom(int(c.geom[1])).name,float(c.dist)] for c in d.contact if receiver in m.geom_bodyid[c.geom]]
            passed=abs(held_delta)<.008 and lateral<.006 and release_delta>.010 and len(latch_contacts)>0 and np.linalg.norm(undocked-seated)<.005
            result={'seed':seed,'hypothetical_iron_mass_g':iron_mass*1000,'success':bool(passed),'latched_axial_displacement_m':held_delta,'latched_lateral_displacement_m':lateral,'released_axial_travel_m':release_delta,'actual_latched_jaw_deg':latch_angle,'latch_contact_pairs':latch_contacts,'release_contacts':release_contacts,'released_quat':d.qpos[adr+3:adr+7].tolist(),'jaw_angle_after_release_deg':float(np.degrees(d.qpos[s.qadr[-1]])),'receiver_initial_m':origin_start.tolist(),'receiver_seated_m':seated.tolist()}
        except ValueError as e:result={'seed':seed,'success':False,'failure':str(e)}
        finally:
            if viewer:viewer.close()
            t.close()
        results.append(result);print('dock',result,flush=True)
    if frames:frames[0].save(OUT/'dock-latch-release.gif',save_all=True,append_images=frames[1:],duration=120,loop=0,optimize=True)
    report={'episodes':count,'successes':sum(r['success'] for r in results),'results':results,'holder_weld':False,'full_arm':True,'net_axial_pull_N':.15,'gravity':'normal world -Z','holder_collision':'concave CAD-dimension box decomposition; no flexible deformation','limitations':['upright fixed-orientation fixture; privileged receiver pose','scripted insertion/open/pull/release phases, learned reaching only','hypothetical iron masses and COM; uncalibrated servos and friction','not a strength or thermal validation']}
    (OUT/'dock_evaluation.json').write_text(json.dumps(report,indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--train',action='store_true');p.add_argument('--tests',type=int,default=12);p.add_argument('--gif',action='store_true');p.add_argument('--view',action='store_true');a=p.parse_args()
    if a.train:train()
    print(json.dumps(evaluate(a.tests,a.gif,a.view),indent=2))
