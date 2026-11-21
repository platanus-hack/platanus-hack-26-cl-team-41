"""Uncalibrated, parameterized hobby-servo approximation with 50Hz command timing.
This models a delayed/sample-held command, bounded reference slew, a position
deadband, and a linear torque-speed envelope. It does not identify real hardware.
"""
from pathlib import Path
import copy,json,math
import numpy as np
ROOT=Path(__file__).resolve().parent
NAMES=['J1_base','J2_shoulder','J3_elbow','J4_wrist_pitch','J5_wrist_roll','J6_jaw_R']
def load_profile():return json.loads((ROOT/'physics_profile.json').read_text())
def joint_parameters(profile,name):
    kind='SG90' if name.startswith(('J5','J6')) else 'MG995'
    result=copy.deepcopy(profile['servo_types'][kind]);result.update(profile.get('joint_overrides',{}).get(name,{}));result['type']=kind
    for k in ('stall_torque_Nm','no_load_speed_rad_s','kp_Nm_rad','kv_Nm_s_rad','passive_damping_Nm_s_rad','armature_kg_m2'):
        if not np.isfinite(result[k]) or result[k]<=0:raise ValueError('Invalid servo parameter '+name+' '+k)
    for k in ('frictionloss_Nm','deadband_deg'):
        if not np.isfinite(result[k]) or result[k]<0:raise ValueError('Invalid servo parameter '+name+' '+k)
    return result
class ServoBank:
    def __init__(self,model,qadr,dadr,profile):
        self.model=model;self.qadr=qadr;self.dadr=dadr;self.profile=profile
        self.parameters=[joint_parameters(profile,n) for n in NAMES]
        self.stall=np.array([p['stall_torque_Nm'] for p in self.parameters]);self.speed=np.array([p['no_load_speed_rad_s'] for p in self.parameters])
        self.deadband=np.radians([p['deadband_deg'] for p in self.parameters])
        period=profile['controller']['command_period_s'];delay=profile['controller']['command_delay_s'];dt=model.opt.timestep
        if period<dt or delay<0:raise ValueError('Invalid command timing')
        self.period_steps=max(1,int(round(period/dt)));self.delay_frames=int(math.ceil(delay/(self.period_steps*dt)-1e-10))
        self.actual_delay_s=self.delay_frames*self.period_steps*dt;self.index=0
    def reset(self,target):
        self.requested=np.array(target,dtype=float).copy();self.reference=self.requested.copy();self.held=self.requested.copy()
        self.queue=[self.requested.copy() for _ in range(self.delay_frames)];self.index=0
    def apply(self,data,target):
        self.requested=np.clip(target,self.model.actuator_ctrlrange[:,0],self.model.actuator_ctrlrange[:,1]).copy()
        if self.index%self.period_steps==0:
            if self.delay_frames:
                self.held=self.queue.pop(0);self.queue.append(self.requested.copy())
            else:self.held=self.requested.copy()
        self.reference+=np.clip(self.held-self.reference,-self.speed*self.model.opt.timestep,self.speed*self.model.opt.timestep)
        q=data.qpos[self.qadr];v=data.qvel[self.dadr];error=self.reference-q
        effective_error=np.sign(error)*np.maximum(np.abs(error)-self.deadband,0)
        data.ctrl[:]=np.clip(q+effective_error,self.model.actuator_ctrlrange[:,0],self.model.actuator_ctrlrange[:,1])
        # Reduce torque only while driving in the same direction as shaft velocity.
        # Opposing torque brakes at up to stall torque; gravity can exceed no-load speed.
        self.model.actuator_forcerange[:,1]=self.stall*np.maximum(0,1-np.maximum(v,0)/self.speed)
        self.model.actuator_forcerange[:,0]=-self.stall*np.maximum(0,1-np.maximum(-v,0)/self.speed)
        self.index+=1
    def state(self):
        queued=np.concatenate(self.queue) if self.queue else np.empty(0)
        return np.r_[self.requested,self.reference,self.held,queued,(self.index%self.period_steps)/self.period_steps]
