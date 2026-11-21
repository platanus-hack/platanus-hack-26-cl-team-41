"""Diverse contact grasps, learned route proposals and a full-arm primitive collision guard.

Privileged-state imitation. The guard is deterministic and is not learned safety.
"""
from pathlib import Path
import argparse,json,time,math,hashlib,xml.etree.ElementTree as E
import numpy as np,mujoco
from manipulation_tasks import ManipulationTrial,downward_ik,ROOT
from build_scene import build,fmt
from curriculum_network import Network,fit
OUT=ROOT/'trained'/'curriculum';OUT.mkdir(parents=True,exist_ok=True)
SCENE=ROOT/'curriculum_scene.xml'
OBJECTS=[
    {'name':'small_cube','type':'box','size':[.006,.006,.006],'mass':.003},
    {'name':'cube','type':'box','size':[.008,.008,.008],'mass':.006},
    {'name':'large_cube','type':'box','size':[.009,.009,.009],'mass':.009},
    {'name':'rectangular_block','type':'box','size':[.007,.009,.008],'mass':.006},
    {'name':'upright_cylinder','type':'cylinder','size':[.007,.008],'mass':.005},
    {'name':'sphere','type':'sphere','size':[.007],'mass':.004},
    {'name':'ellipsoid','type':'ellipsoid','size':[.007,.009,.008],'mass':.005},
]
ROUTES=['direct','over_45mm','inner_115mm_over_50mm','outer_140mm','inner_115mm','inner_105mm_over_45mm']
BOUNDS=np.array([[.102,-.085,.010],[.174,.045,.074]])

def prepare():
    build(output_path=SCENE);tree=E.parse(SCENE);r=tree.getroot();w=r.find('worldbody')
    r.find('option').attrib.update(cone='elliptic',impratio='10',noslip_iterations='5')
    w.find("body[@name='tray']").set('pos','0.13 -0.06 0')
    for n in ('JawR_part','JawL_part'):
        for g in r.findall(f".//body[@name='{n}']/geom"):
            if g.get('group')=='3':g.set('condim','6')
    for i in range(2):
        b=E.SubElement(w,'body',name=f'obstacle{i}',pos=f'{.13+i*.07} -.024 .01')
        E.SubElement(b,'geom',name=f'obstacle{i}_geom',type='box',size='.012 .006 .01',rgba=('0.8 .55 .12 1' if i==0 else '.48 .28 .65 1'),margin='.002')
    # All catalog entries are genuinely separate movable objects in the scene.
    # One is moved into the pickup area for each episode; others remain in staging.
    for i,obj in enumerate(OBJECTS[1:]):
        b=E.SubElement(w,'body',name='staged_'+obj['name'],pos=fmt([.23+(i%3)*.03,.03+(i//3)*.035,.012]))
        E.SubElement(b,'freejoint');E.SubElement(b,'inertial',pos='0 0 0',mass=str(obj['mass']),diaginertia='0.0000003 0.0000003 0.0000003')
        E.SubElement(b,'geom',type=obj['type'],size=fmt(obj['size']),rgba=fmt([.25+.1*(i%3),.45,.75-.08*i,1]))
    E.indent(r);tree.write(SCENE,encoding='utf-8',xml_declaration=True)
    return SCENE

def path_for(index,start,goal):
    s=np.asarray(start);g=np.asarray(goal)
    if index==0:return [s,g]
    if index==1:
        return [s,np.r_[s[:2],.045],np.array([.13,-.044,.045]),np.array([.13,-.048,.039]),g]
    x={2:.115,3:.140,4:.115,5:.105}[index];z={2:.050,3:.039,4:.039,5:.045}[index]
    # Raise while moving inward: this respects the fixed-down wrist limit.
    return [s,np.array([x,s[1],z]),np.array([x,-.044,z]),np.array([.13,-.048,.039]),g]

def samples(path,spacing=.004):
    for a,b in zip(path[:-1],path[1:]):
        for t in np.linspace(0,1,max(2,math.ceil(np.linalg.norm(b-a)/spacing)+1)):
            yield a+(b-a)*t

def features(start,goal,obstacles,radius):return np.r_[start,goal,np.asarray(obstacles).ravel(),radius]

class ExpandedGoal:
    def __init__(self):self.net=Network(OUT/'reach_policy.npz')
    def predict(self,point):
        p=np.asarray(point)
        if not np.isfinite(p).all() or np.any(p<BOUNDS[0]) or np.any(p>BOUNDS[1]):raise ValueError('Goal outside curriculum bounds')
        q=self.net.predict(p);full=np.r_[q,np.pi-q[1]-q[2],0.]
        if np.any(np.abs(full)>np.pi/2-.001):raise ValueError('Predicted pose exceeds joints')
        return full

class Guard:
    def __init__(self,sim):
        self.sim=sim;self.d=mujoco.MjData(sim.model)
        self.obstacles=[sim.model.geom(f'obstacle{i}_geom').id for i in range(2)]
        self.robot=[g for g in range(sim.model.ngeom) if sim.model.geom_group[g]==3]
        self.table=sim.model.geom('table').id
        self.obstacle_bodies=[sim.model.body(f'obstacle{i}').id for i in range(2)]
        self.checks=0
    def set_obstacles(self,obstacles):
        m=self.sim.model
        for body,geom,box in zip(self.obstacle_bodies,self.obstacles,obstacles):
            m.body_pos[body]=box[:3];m.geom_size[geom]=box[3:];m.geom_rbound[geom]=np.linalg.norm(box[3:])
        self.obstacle_boxes=np.asarray(obstacles)
        mujoco.mj_forward(m,self.sim.data)
    def clear(self,path,radius,policy=None):
        s=self.sim;m=s.model;d=self.d;d.qpos[:]=s.data.qpos
        for point in samples(path):
            self.checks+=1
            try:q=downward_ik(point) if policy is None else policy.predict(point)
            except ValueError:return False
            d.qpos[s.qadr[:5]]=q;d.qpos[s.qadr[-1]]=0.;d.qpos[m.jnt_qposadr[s.left]]=0.
            mujoco.mj_forward(m,d)
            if any(c.dist<-.0005 and int(c.geom[0]) in self.robot and int(c.geom[1]) in self.robot for c in d.contact):return False
            # Conservative carried-object sphere, in addition to the entire arm.
            center=point+np.array([0,0,-.0025])
            if center[2]-radius<.003:return False
            for box in self.obstacle_boxes:
                if np.linalg.norm(np.maximum(np.abs(center-box[:3])-box[3:],0))<radius+.003:return False
            for a in self.robot:
                for b in self.obstacles:
                    if mujoco.mj_geomDistance(m,d,a,b,.003,None)<.003:return False
                # The base's intended desk contact is excluded.
                if m.geom(a).name!='base_collision' and mujoco.mj_geomDistance(m,d,a,self.table,.0001,None)<-.0005:return False
        return True
    def plan(self,start,goal,radius,net,policy):
        scores=net.predict(features(start,goal,self.obstacle_boxes,radius))
        paths=[path_for(i,start,goal) for i in range(len(ROUTES))]
        lengths=np.array([sum(np.linalg.norm(b-a) for a,b in zip(p[:-1],p[1:])) for p in paths])
        proposed=int(min(range(len(paths)),key=lambda i:(scores[i]<.5,lengths[i] if scores[i]>=.5 else -scores[i])))
        order=[proposed]+[i for i in np.argsort(lengths) if i!=proposed]
        for i in order:
            if self.clear(paths[i],radius,policy):return paths[i],{'proposed':ROUTES[proposed],'executed':ROUTES[i],'guard_fallback':bool(i!=proposed),'scores':scores.tolist()}
        return None,{'proposed':ROUTES[proposed],'executed':None,'guard_fallback':True,'scores':scores.tolist()}

def random_case(rng,blocked=False):
    start=np.array([rng.uniform(.126,.136),rng.uniform(.009,.023),.039]);goal=np.array([.13,-.06,.039])
    ob=np.array([[rng.uniform(.118,.15),rng.uniform(-.038,-.018),0,rng.uniform(.007,.019),rng.uniform(.004,.008),rng.uniform(.009,.023)],
        [rng.uniform(.155,.205),rng.uniform(-.045,-.010),0,rng.uniform(.005,.012),rng.uniform(.004,.009),rng.uniform(.009,.022)]])
    ob[:,2]=ob[:,5]
    if blocked:ob[0]=[.13,-.025,.055,.07,.009,.055]
    return start,goal,ob,float(rng.uniform(.009,.015))

def train(epochs=160,cases=1800):
    started=time.time();rng=np.random.default_rng(520);x=[];y=[]
    while len(x)<18000:
        p=rng.uniform(*BOUNDS)
        try:q=downward_ik(p)
        except ValueError:continue
        x.append(p);y.append(q[:3])
    _,reach=fit(np.array(x),np.array(y),OUT/'reach_policy.npz',epochs=epochs)
    trial=ManipulationTrial('block',0,scene=prepare());guard=Guard(trial.sim);x=[];y=[]
    for n in range(cases):
        s,g,obs,r=random_case(rng,blocked=n%11==0);guard.set_obstacles(obs)
        labels=[guard.clear(path_for(i,s,g),r) for i in range(len(ROUTES))]
        x.append(features(s,g,obs,r));y.append(labels)
        if n%200==0:print('collision teacher',n,'/',cases,flush=True)
    trial.close();np.savez_compressed(OUT/'route_dataset.npz',x=x,y=y)
    _,routes=fit(np.array(x),np.array(y,dtype=float),OUT/'route_policy.npz',binary=True,epochs=epochs*2)
    report={'method':'supervised imitation; learned expanded downward reach + per-candidate collision-free route probabilities; deterministic full-arm primitive guard',
        'reach':reach,'routes':routes,'route_positive_fraction':np.mean(y,axis=0).tolist(),'route_names':ROUTES,'elapsed_s':time.time()-started,
        'workspace_bounds_m':BOUNDS.tolist(),'training_seed':520,'teacher_margin_m':.003,'path_sample_spacing_m':.004,
        'not_learned':['grasp phase sequence','jaw feedback and gravity compensation','collision guard'],'state_source':'privileged simulator object/obstacle poses'}
    (OUT/'training_report.json').write_text(json.dumps(report,indent=2));return report

class DiverseTrial(ManipulationTrial):
    def __init__(self,seed,object_index,randomize=True):
        super().__init__('block',seed,scene=SCENE);self.obj=OBJECTS[object_index];m=self.sim.model;obj=self.obj;size=np.array(obj['size'])
        self.object_size=float(2*size[-1] if obj['type']!='sphere' else 2*size[0])
        gid=self.object_geom;m.geom_type[gid]={'box':mujoco.mjtGeom.mjGEOM_BOX,'sphere':mujoco.mjtGeom.mjGEOM_SPHERE,'cylinder':mujoco.mjtGeom.mjGEOM_CYLINDER,'ellipsoid':mujoco.mjtGeom.mjGEOM_ELLIPSOID}[obj['type']]
        m.geom_size[gid]=0;m.geom_size[gid,:len(size)]=size;m.geom_rbound[gid]=max(.02,float(np.linalg.norm(size)))
        mass=obj['mass']*(self.rng.uniform(.8,1.25) if randomize else 1);m.body_mass[self.sim.blockid]=mass
        # Conservative diagonal approximation; clearly an unmeasured prior.
        m.body_inertia[self.sim.blockid]=mass*(max(size)*2)**2/6
        if randomize:
            m.geom_friction[gid,0]=self.rng.uniform(.65,1.15)
            self.sim.servos.stall*=self.rng.uniform(.85,1.0,size=6)
            self.sim.servos.speed*=self.rng.uniform(.8,1.0,size=6)
            self.sim.servos.deadband*=self.rng.uniform(.8,1.2,size=6)
        mujoco.mj_setConst(m,self.sim.data)
        self.sim.data.qpos[self.object_qadr+2]=self.object_size/2
        self.sim.data.qvel[self.object_dadr:self.object_dadr+6]=0
        # Rectangular objects get a small unseen orientation perturbation.
        yaw=float(self.rng.uniform(-.15,.15));self.sim.data.qpos[self.object_qadr+3:self.object_qadr+7]=[np.cos(yaw/2),0,0,np.sin(yaw/2)]
        mujoco.mj_forward(m,self.sim.data);self.sim.step(100);self.start_object=self.sim.data.xpos[self.sim.blockid].copy()
        self.guard=Guard(self.sim);self.collision_events=[];self.minimum_obstacle_distance=.2;self.abort=False
        self.phase='initial';native_step=self.sim.step
        def checked_step(n=10):
            for _ in range(n):
                native_step(1);self.monitor(self,self.phase)
        self.sim.step=checked_step
    def move(self,*args,**kwargs):
        self.phase=kwargs.get('phase',args[3] if len(args)>3 else 'move')
        return super().move(*args,**kwargs)
    def monitor(self,trial,phase):
        s=self.sim
        for c in s.data.contact:
            a,b=map(int,c.geom)
            obstacle=a in self.guard.obstacles or b in self.guard.obstacles
            robot=a in self.guard.robot or b in self.guard.robot
            target=a==self.object_geom or b==self.object_geom
            other=b if a in self.guard.robot else a
            self_contact=a in self.guard.robot and b in self.guard.robot
            table_contact=robot and other==self.guard.table and s.model.geom(a if a in self.guard.robot else b).name!='base_collision'
            # Grasp contacts with the selected object are intentional; all other
            # robot contacts (tray, distractors, table, obstacles, self) are forbidden.
            unexpected=robot and not target and other not in self.guard.robot and not (other==self.guard.table and not table_contact)
            if ((obstacle and (robot or target)) or self_contact or table_contact or unexpected) and c.dist<-.00005:
                self.collision_events.append({'phase':phase,'time':float(s.data.time),'depth_m':float(-c.dist),'geoms':[s.model.geom(a).name,s.model.geom(b).name],'obstacle':obstacle});self.abort=True
        if self.abort:raise RuntimeError('Forbidden contact: episode stopped at physics timestep')

def run_trial(trial,policy,net,seed,callback=None,feasible_suite=True):
    t=trial;s=t.sim;rng=np.random.default_rng(seed);start,goal,obs,_=random_case(rng)
    x,y=t.start_object[:2];grasp=[x,y,max(.0105,t.object_size/2+.0025)];lift=np.array([x,y,.039])
    radii=np.array(t.obj['size']);radius=float(np.linalg.norm(radii) if t.obj['type'] in ('box','ellipsoid') else max(radii)*1.5)
    # This manipulation suite samples geometrically feasible scenes, using the
    # analytic teacher BEFORE execution, never resampling a failed grasp.
    # Separate route challenges retain blocked scenes and score refusal.
    attempts=0
    while True:
        attempts+=1;t.guard.set_obstacles(obs)
        if not feasible_suite or any(t.guard.clear(path_for(i,lift,goal),radius) for i in range(len(ROUTES))) or attempts>=40:break
        _,_,obs,_=random_case(rng)
    plan,route=t.guard.plan(lift,goal,radius,net,policy)
    result={'seed':seed,'object':t.obj['name'],'obstacles_m':obs.tolist(),'teacher_scene_sampling_attempts':attempts,'route':route,'success':False,'mass_kg':float(s.model.body_mass[s.blockid]),'friction':float(s.model.geom_friction[t.object_geom,0])}
    def monitor(tt,phase):
        t.monitor(tt,phase)
        if callback:callback(tt,phase)
    if plan is None:return {**result,'failure':'no collision-free candidate; refused'}
    try:
        t.move([x,y,.041],.40,1.5,'approach',policy=policy,callback=monitor)
        t.move(grasp,.40,1.,'descend',policy=policy,callback=monitor)
        t.move(grasp,0.,2.8,'close',policy=policy,callback=monitor)
        t.move(lift,0.,1.5,'lift',True,policy,monitor)
        t.move(lift,0.,1.,'hold',True,policy,monitor)
        hold=t.records[-50:];lifted=min(r['object'][2] for r in hold)>t.start_object[2]+.018
        bilateral=sum(len(r['contacts'])==2 for r in hold)/50
        result.update(lift_success=bool(lifted and bilateral>=.8),bilateral_hold_fraction=bilateral)
        if not result['lift_success']:return {**result,'failure':'grasp/lift criteria failed'}
        for point in plan[1:]:t.move(point,0.,max(.7,np.linalg.norm(point-t.last_point)/.025),'avoid_obstacle',True,policy,monitor)
        # A narrow release fits inside the tray and places close to its floor.
        # Wide low opening hits a wall; dropping round objects from above rolls them.
        t.move([.13,-.06,max(.0105,t.object_size/2+.0025)+.004],0.,1.2,'lower',True,policy,monitor)
        t.move(t.last_point,.16,1.,'release',False,policy,monitor)
        t.move(goal,.16,1.,'retract',False,policy,monitor)
        t.move(goal,.4,1.,'settle',False,policy,monitor)
        final=s.data.xpos[s.blockid].copy();velocity=s.data.qvel[t.object_dadr:t.object_dadr+3]
        inside=np.all(np.abs(final[:2]-goal[:2])<.019) and .006<final[2]<.021 and np.linalg.norm(velocity)<.02
        released=all(not r['contacts'] for r in t.records[-25:]);result.update(success=bool(inside and released),final_object_m=final.tolist(),released=released)
        if not result['success']:result['failure']='placement or release criteria failed'
    except (RuntimeError,ValueError) as e:result['failure']=str(e)
    result['obstacle_contact_events']=sum(e['obstacle'] for e in t.collision_events)
    result['forbidden_contact_events']=t.collision_events
    return result

def evaluate(count=28,start_seed=6100,gif=False,view=False):
    prepare();policy=ExpandedGoal();net=Network(OUT/'route_policy.npz');results=[];frames=[]
    for i in range(count):
        seed=start_seed+i;t=DiverseTrial(seed,i%len(OBJECTS));viewer=None
        if view:
            from mujoco import viewer as mjviewer
            viewer=mjviewer.launch_passive(t.sim.model,t.sim.data);viewer.cam.lookat[:]=[.11,-.015,.10];viewer.cam.distance=.5;viewer.cam.azimuth=110;viewer.cam.elevation=-35;viewer.opt.geomgroup[3]=0
        def capture(tt,phase):
            if gif and i in (0,4,6) and len(tt.records)%10==0:
                from PIL import Image,ImageDraw
                sim=tt.sim
                if sim.renderer is None:sim.renderer=mujoco.Renderer(sim.model,height=480,width=640)
                cam=mujoco.MjvCamera();cam.lookat[:]=[.13,-.02,.07];cam.distance=.34;cam.azimuth=110;cam.elevation=-40
                opt=mujoco.MjvOption();opt.geomgroup[3]=0;sim.renderer.update_scene(sim.data,camera=cam,scene_option=opt)
                im=Image.fromarray(sim.renderer.render()).resize((480,360));draw=ImageDraw.Draw(im);draw.rectangle((0,0,480,26),fill='#152633');draw.text((12,8),f'{tt.obj["name"]} | {phase}',fill='white');frames.append(im)
            if viewer:
                if not viewer.is_running():raise KeyboardInterrupt
                viewer.sync();time.sleep(.02)
        try:result=run_trial(t,policy,net,seed,capture)
        finally:
            if viewer:viewer.close()
            t.close()
        results.append(result);print('curriculum',seed,result['object'],result['success'],result.get('failure'),result['route']['executed'],flush=True)
        if (i+1)%7==0:(OUT/'evaluation_progress.json').write_text(json.dumps(results,indent=2))
    if frames:frames[0].save(OUT/'objects-obstacles.gif',save_all=True,append_images=frames[1:],duration=160,loop=0,optimize=True)
    report={'episodes':count,'held_out_seeds':[start_seed,start_seed+count-1],'scene_sampling':'geometrically feasible teacher-screened obstacle layouts; no resampling after execution starts','successes':sum(r['success'] for r in results),'obstacle_contact_events':sum(r.get('obstacle_contact_events',0) for r in results),
        'per_object':{o['name']:{'episodes':sum(r['object']==o['name'] for r in results),'successes':sum(r['object']==o['name'] and r['success'] for r in results)} for o in OBJECTS},
        'guard_fallbacks':sum(r['route']['guard_fallback'] for r in results),'results':results,'physics':'uncalibrated preassembly priors; primitive collision shapes','no_object_weld':True}
    (OUT/'object_evaluation.json').write_text(json.dumps(report,indent=2));return report

def evaluate_routes(count=200):
    rng=np.random.default_rng(8271);trial=ManipulationTrial('block',0,scene=prepare());guard=Guard(trial.sim);net=Network(OUT/'route_policy.npz');policy=ExpandedGoal();rows=[]
    for n in range(count):
        s,g,o,r=random_case(rng,blocked=n%10==0);guard.set_obstacles(o)
        path,info=guard.plan(s,g,r,net,policy)
        raw=guard.clear(path_for(ROUTES.index(info['proposed']),s,g),r,policy)
        teacher_feasible=any(guard.clear(path_for(i,s,g),r) for i in range(len(ROUTES)))
        rows.append({'blocked_challenge':n%10==0,'teacher_feasible':teacher_feasible,'network_proposal_clear':raw,'executed_clear':None if path is None else guard.clear(path,r,policy),'refused':path is None,'fallback':info['guard_fallback'],'route':info['executed']})
    trial.close();report={'cases':count,'independent_seed':8271,'raw_network_proposals_clear':sum(r['network_proposal_clear'] for r in rows),'teacher_feasible':sum(r['teacher_feasible'] for r in rows),'guarded_executions':sum(not r['refused'] for r in rows),'unsafe_guarded_paths':sum(r['executed_clear'] is False for r in rows),'refusals':sum(r['refused'] for r in rows),'blocked_challenges':sum(r['blocked_challenge'] for r in rows),'blocked_challenges_refused':sum(r['blocked_challenge'] and r['refused'] for r in rows),'feasible_guard_fallbacks':sum(not r['refused'] and r['fallback'] for r in rows),'results':rows}
    (OUT/'route_evaluation.json').write_text(json.dumps(report,indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--train',action='store_true');p.add_argument('--epochs',type=int,default=160);p.add_argument('--cases',type=int,default=1800);p.add_argument('--tests',type=int,default=28);p.add_argument('--gif',action='store_true');p.add_argument('--view',action='store_true');p.add_argument('--routes-only',action='store_true');a=p.parse_args()
    if a.train:train(a.epochs,a.cases)
    if a.routes_only:print(json.dumps(evaluate_routes(),indent=2))
    else:
        print(json.dumps(evaluate(a.tests,gif=a.gif,view=a.view),indent=2));print(json.dumps(evaluate_routes(),indent=2))
