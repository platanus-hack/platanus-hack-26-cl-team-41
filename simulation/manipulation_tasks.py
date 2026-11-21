"""Contact-based pick/hold experiments with the SolidCraft arm. No object welds."""
from pathlib import Path
import math,json,time,xml.etree.ElementTree as E
import numpy as np,mujoco
from arm_sim import ArmSimulation,HOME,ROOT
from build_scene import build
from servo_physics import load_profile

def prepare_scene(task='block'):
    path=ROOT/(task+'_task_scene.xml');build(output_path=path)
    tree=E.parse(path);root=tree.getroot();world=root.find('worldbody')
    # Better-resolved friction cones and a no-slip solve reduce numerical drift
    # of very light objects pinched between the narrow CAD finger pads.
    option=root.find('option');option.set('cone','elliptic');option.set('impratio','10');option.set('noslip_iterations','5')
    for name in ('JawR_part','JawL_part'):
        for geom in root.findall(f".//body[@name='{name}']/geom"):
            if geom.get('group')=='3':geom.set('condim','6')
    world.find("body[@name='tray']").set('pos','0.13 -0.06 0')
    if task=='tool':
        body=world.find("body[@name='block']");body.set('pos','0.13 0.0145 0.006')
        body.find('inertial').set('mass','0.025');body.find('inertial').set('diaginertia','0.000012 0.00000045 0.000012')
        geom=body.find('geom');geom.set('type','capsule');geom.set('size','0.006 0.035');geom.set('quat','0.707106781 0.707106781 0 0');geom.set('rgba','0.2 0.25 0.3 1')
        E.SubElement(body,'geom',name='cold_tool_shaft',type='capsule',fromto='0 0.035 0 0 0.08 0',size='0.002',rgba='0.65 0.68 0.72 1',contype='0',conaffinity='0',mass='0')
    elif task=='mounted_tool':
        # An explicit mechanical holder, not a hidden weld used to pass a grasp test.
        # This fixture is a simulation assumption and still needs a physical design.
        world.find("body[@name='block']").set('pos','0.4 0.2 0.008')
        gripper=root.find(".//body[@name='Gripper_part']")
        holder=E.SubElement(gripper,'body',name='tool_holder',pos='0.0145 0 0.0735')
        E.SubElement(holder,'inertial',pos='0 0 -0.02',mass='0.008',diaginertia='0.000002 0.000002 0.0000005')
        E.SubElement(holder,'geom',type='capsule',fromto='0 0 -0.05 0 0 0',size='0.004',rgba='0.1 0.5 0.3 1')
        tool=E.SubElement(holder,'body',name='mounted_cold_tool')
        E.SubElement(tool,'inertial',pos='0.005 0 0',mass='0.025',diaginertia='0.00000045 0.000014 0.000014')
        E.SubElement(tool,'geom',type='capsule',fromto='-0.035 0 0 0.035 0 0',size='0.006',rgba='0.18 0.22 0.27 1')
        E.SubElement(tool,'geom',type='capsule',fromto='0.035 0 0 0.095 0 0',size='0.002',rgba='0.65 0.68 0.72 1')
        E.SubElement(tool,'site',name='mounted_tool_tip',pos='0.095 0 0',size='0.002',rgba='0.9 0.3 0.1 1')
    E.indent(root);tree.write(path,encoding='utf-8',xml_declaration=True)
    return path

def downward_ik(point):
    """Analytic fixed-down, zero-roll branch for this CAD's actual five axes."""
    x,y,z=np.asarray(point);offset=.0145
    radial_sq=x*x+y*y-offset*offset
    if radial_sq<=0:raise ValueError('Target too near base axis')
    radial=np.sqrt(radial_sq);vertical=z+.0235
    c=(radial**2+vertical**2-.09**2-.085**2)/(2*.09*.085)
    if not -1<=c<=1:raise ValueError('Target outside link reach')
    elbow=np.arccos(c);shoulder=np.arctan2(radial,vertical)-np.arctan2(.085*np.sin(elbow),.09+.085*np.cos(elbow))
    q=np.array([np.arctan2(y,x)-np.arctan2(offset,radial),shoulder,elbow,np.pi-shoulder-elbow,0.])
    if np.any(np.abs(q)>np.pi/2-.001):raise ValueError('Downward pose exceeds joint ranges')
    return q

class ManipulationTrial:
    def __init__(self,task='block',seed=0,scene=None,object_size=.016):
        self.task=task;self.rng=np.random.default_rng(seed)
        self.object_size=float(object_size)
        self.sim=ArmSimulation(scene_path=scene or prepare_scene(task))
        self.scratch=mujoco.MjData(self.sim.model)
        self.object_geom=mujoco.mj_name2id(self.sim.model,mujoco.mjtObj.mjOBJ_GEOM,'block_geom')
        if task=='block' and not np.isclose(self.object_size,.016):
            half=self.object_size/2;mass=.006*(self.object_size/.016)**3
            self.sim.model.geom_size[self.object_geom]=half
            self.sim.model.geom_rbound[self.object_geom]=np.sqrt(3)*half
            self.sim.model.body_mass[self.sim.blockid]=mass
            self.sim.model.body_inertia[self.sim.blockid]=mass*self.object_size**2/6
            mujoco.mj_setConst(self.sim.model,self.sim.data)
        self.right_body=mujoco.mj_name2id(self.sim.model,mujoco.mjtObj.mjOBJ_BODY,'JawR_part')
        self.left_body=mujoco.mj_name2id(self.sim.model,mujoco.mjtObj.mjOBJ_BODY,'JawL_part')
        j=mujoco.mj_name2id(self.sim.model,mujoco.mjtObj.mjOBJ_JOINT,'block_free');self.object_qadr=self.sim.model.jnt_qposadr[j];self.object_dadr=self.sim.model.jnt_dofadr[j]
        self.records=[];self.metrics={};self.reset(seed)
    def reset(self,seed):
        self.rng=np.random.default_rng(seed);self.sim.reset()
        x=float(self.rng.uniform(.126,.134));y=float(self.rng.uniform(.006,.023));z=self.object_size/2 if self.task=='block' else .006
        self.sim.data.qpos[self.object_qadr:self.object_qadr+3]=[x,y,z]
        self.sim.data.qvel[self.object_dadr:self.object_dadr+6]=0;mujoco.mj_forward(self.sim.model,self.sim.data);self.sim.step(100)
        self.start_object=self.sim.data.xpos[self.sim.blockid].copy();self.records=[];self.last_point=None;self.grasp_command=None
    def compensated_target(self,point,gripper,payload=False,q_model=None):
        s=self.sim;q=downward_ik(point) if q_model is None else np.array(q_model)
        self.scratch.qpos[:]=s.data.qpos;self.scratch.qvel[:]=0;self.scratch.qpos[s.qadr[:5]]=q
        self.scratch.qpos[s.qadr[-1]]=gripper;self.scratch.qpos[s.model.jnt_qposadr[s.left]]=-gripper
        mujoco.mj_forward(s.model,self.scratch);tau=self.scratch.qfrc_bias[s.dadr].copy()
        if payload:
            jp=np.zeros((3,s.model.nv));jr=jp.copy();mujoco.mj_jacSite(s.model,self.scratch,jp,jr,s.tcpid)
            tau[:5]+=s.model.body_mass[s.blockid]*9.81*jp[2,s.dadr[:5]]
        kp=np.array([p['kp_Nm_rad'] for p in s.servos.parameters]);dead=s.servos.deadband
        friction=np.array([p['frictionloss_Nm'] for p in s.servos.parameters])
        direction=np.where(np.abs(tau)>friction*.5,np.sign(tau),0.)
        correction=tau/kp+dead*direction
        target=np.r_[q,gripper]+correction;target[-1]=gripper
        target[:5]+=np.clip(.15*(q-s.data.qpos[s.qadr[:5]]),-.015,.015)
        return np.clip(target,s.limits[:,0]+.001,s.limits[:,1]-.001)
    def contact_sides(self):
        result=set();s=self.sim
        for c in s.data.contact:
            if self.object_geom not in c.geom:continue
            other=int(c.geom[1] if c.geom[0]==self.object_geom else c.geom[0]);body=s.model.geom_bodyid[other]
            if body==self.right_body:result.add('right')
            if body==self.left_body:result.add('left')
        return result
    def move(self,point,gripper,duration=1.0,phase='move',payload=False,policy=None,callback=None):
        s=self.sim;target=self.compensated_target(point,gripper,payload,q_model=None if policy is None else policy.predict(point))
        start=s.targets.copy();frames=max(1,round(duration/.02))
        for i in range(frames):
            t=(i+1)/frames;blend=t*t*(3-2*t)
            if self.last_point is None:s.targets=start+(target-start)*blend
            else:
                waypoint=self.last_point+(np.asarray(point)-self.last_point)*blend
                grip=start[-1]+(gripper-start[-1])*blend
                if phase=='close':
                    contacts=self.contact_sides()
                    grip=max(gripper,float(s.data.qpos[s.qadr[-1]])-.012) if contacts else max(gripper,float(s.targets[-1])-.003)
                    if len(contacts)==2:self.grasp_command=grip
                elif payload and self.grasp_command is not None:grip=max(0.,float(s.data.qpos[s.qadr[-1]])-.012)
                s.targets=self.compensated_target(waypoint,grip,payload,q_model=None if policy is None else policy.predict(waypoint))
            s.step(10)
            self.records.append({'phase':phase,'point':list(point),'q':s.data.qpos[s.qadr].tolist(),'command':s.targets.tolist(),
                'tcp':s.tcp.tolist(),'object':s.data.xpos[s.blockid].tolist(),'contacts':sorted(self.contact_sides())})
            if callback:callback(self,phase)
        self.last_point=np.asarray(point).copy()
        return float(np.linalg.norm(s.tcp-np.asarray(point)))
    def run(self,policy=None,callback=None,place=True):
        obj=self.start_object;x,y=obj[:2]
        approach=np.array([x,y,.041]);grasp=np.array([x,y,max(.0105,self.object_size/2+.0025)]);lift=np.array([x,y,.039])
        errors={}
        errors['approach']=self.move(approach,.40,1.5,'approach',policy=policy,callback=callback)
        errors['descend']=self.move(grasp,.40,1.0,'descend',policy=policy,callback=callback)
        errors['close']=self.move(grasp,0.,2.8,'close',policy=policy,callback=callback)
        errors['lift']=self.move(lift,0.,1.5,'lift',True,policy,callback)
        errors['hold']=self.move(lift,0.,1.0,'hold',True,policy,callback)
        hold=self.records[-50:];lifted=min(r['object'][2] for r in hold)>obj[2]+.018
        both=sum(len(r['contacts'])==2 for r in hold)>=40
        self.metrics={'task':self.task,'lift_success':bool(lifted and both),'min_hold_height_m':min(r['object'][2] for r in hold),
            'start_height_m':float(obj[2]),'bilateral_hold_fraction':sum(len(r['contacts'])==2 for r in hold)/len(hold),
            'tcp_errors_m':errors,'object_final_m':self.sim.data.xpos[self.sim.blockid].tolist()}
        if place and self.task=='block':
            tray=np.array([.13,-.06,.039])
            self.move(tray,0.,1.8,'transfer',True,policy,callback)
            place_height=max(.0105,self.object_size/2+.0025)+.004
            self.move([.13,-.06,place_height],0.,1.2,'lower',True,policy,callback)
            self.move([.13,-.06,place_height],.4,1.,'release',False,policy,callback)
            self.move(tray,.4,1.,'retract',False,policy,callback)
            final=self.sim.data.xpos[self.sim.blockid].copy();velocity=self.sim.data.qvel[self.object_dadr:self.object_dadr+3]
            inside=np.all(np.abs(final[:2]-tray[:2])<.019) and .007<final[2]<.020 and np.linalg.norm(velocity)<.02
            released=all(not r['contacts'] for r in self.records[-25:])
            self.metrics.update(place_success=bool(inside and released),pick_place_success=bool(lifted and both and inside and released),object_final_m=final.tolist())
        return self.metrics
    def close(self):self.sim.close()
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--task',choices=['block','tool'],default='block');p.add_argument('--seed',type=int,default=0);args=p.parse_args()
    trial=ManipulationTrial(args.task,args.seed);print(json.dumps(trial.run(),indent=2));(ROOT/(args.task+'_expert_debug.json')).write_text(json.dumps(trial.records));trial.close()
