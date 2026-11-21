"""Local MuJoCo tabletop simulation, virtual RGB camera, IK and Gymnasium reach task."""
from pathlib import Path
import argparse,json,time
import tempfile
from datetime import datetime
import numpy as np
import mujoco
import gymnasium as gym
from gymnasium import spaces
from servo_physics import ServoBank,load_profile
ROOT=Path(__file__).resolve().parent
NAMES=['J1_base','J2_shoulder','J3_elbow','J4_wrist_pitch','J5_wrist_roll','J6_jaw_R']
HOME=np.radians([0,20,65,40,0,20])

class ArmSimulation:
    def __init__(self,physics_profile=None,timestep_s=None,scene_path=None):
        self.profile=load_profile() if physics_profile is None else physics_profile
        if scene_path is not None:
            self.model=mujoco.MjModel.from_xml_path(str(scene_path))
        elif physics_profile is not None:
            from build_scene import build
            with tempfile.NamedTemporaryFile(dir=ROOT,suffix='.xml',prefix='_physics_',delete=False) as file:path=Path(file.name)
            try:
                build(profile=self.profile,output_path=path);self.model=mujoco.MjModel.from_xml_path(str(path))
            finally:path.unlink(missing_ok=True)
        else:
            dependencies=[ROOT/'physics_profile.json',ROOT/'mass_properties.py',ROOT/'build_scene.py',ROOT/'calibration'/'part_masses.csv']
            stale=not (ROOT/'scene.xml').exists() or any(p.exists() and p.stat().st_mtime>(ROOT/'scene.xml').stat().st_mtime for p in dependencies)
            if stale:
                from build_scene import build
                build()
            self.model=mujoco.MjModel.from_xml_path(str(ROOT/'scene.xml'))
        if timestep_s is not None:
            if not 0<float(timestep_s)<=.005:raise ValueError('Timestep must be positive and no more than 5ms')
            self.model.opt.timestep=float(timestep_s)
        self.data=mujoco.MjData(self.model)
        self.joints=np.array([mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_JOINT,n) for n in NAMES])
        self.qadr=self.model.jnt_qposadr[self.joints];self.dadr=self.model.jnt_dofadr[self.joints]
        self.limits=self.model.jnt_range[self.joints].copy()
        self.tcpid=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_SITE,'tcp')
        self.goalid=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_SITE,'reach_goal')
        self.left=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_JOINT,'J6_jaw_L')
        self.blockid=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_BODY,'block')
        self.servos=ServoBank(self.model,self.qadr,self.dadr,self.profile)
        self.renderer=None;self.targets=HOME.copy();self.reset()
    def reset(self,seed=0):
        mujoco.mj_resetData(self.model,self.data);self.data.qpos[self.qadr]=HOME
        self.data.qpos[self.model.jnt_qposadr[self.left]]=-HOME[-1]
        self.targets=HOME.copy();self.data.ctrl[:]=self.targets
        self.servos.reset(self.targets)
        mujoco.mj_forward(self.model,self.data)
        self.step(100)
    def step(self,n=10):
        requested=np.clip(self.targets,self.limits[:,0],self.limits[:,1])
        for _ in range(n):
            self.servos.apply(self.data,requested)
            mujoco.mj_step(self.model,self.data)
        # Keep native viewer sliders in requested-angle units, rather than filtered references.
        self.data.ctrl[:]=requested
    @property
    def tcp(self):return self.data.site_xpos[self.tcpid].copy()
    def jacobian(self):
        pos=np.zeros((3,self.model.nv));rot=pos.copy();mujoco.mj_jacSite(self.model,self.data,pos,rot,self.tcpid)
        return np.vstack((pos[:,self.dadr[:5]],rot[:,self.dadr[:5]]))
    def status(self):
        j=self.jacobian();scaled=np.vstack((j[:3]/.32,j[3:]));sv=np.linalg.svd(scaled,compute_uv=False)
        return {'tcp_m':self.tcp.tolist(),'joint_deg':np.degrees(self.data.qpos[self.qadr]).tolist(),
            'xyz_rank':int(np.linalg.matrix_rank(j[:3],tol=1e-8)),'arm_rank':int(np.linalg.matrix_rank(scaled,tol=1e-8)),
            'scaled_sigma_min':float(sv[-1]),'block_m':self.data.xpos[self.blockid].tolist(),
            'jaw_coupling_error_rad':float(self.data.qpos[self.model.jnt_qposadr[self.left]]+self.data.qpos[self.qadr[-1]]),
            'physics_status':self.profile['status'],'command_delay_s':self.servos.actual_delay_s}
    def solve_position(self,target,iterations=300):
        """Position-only damped IK; five-joint orientation remains unconstrained."""
        scratch=mujoco.MjData(self.model);scratch.qpos[:]=self.data.qpos
        target=np.asarray(target);q=self.targets.copy()
        for _ in range(iterations):
            scratch.qpos[self.qadr]=q;scratch.qpos[self.model.jnt_qposadr[self.left]]=-q[-1]
            mujoco.mj_forward(self.model,scratch);error=target-scratch.site_xpos[self.tcpid]
            if np.linalg.norm(error)<.001:break
            jp=np.zeros((3,self.model.nv));jr=jp.copy();mujoco.mj_jacSite(self.model,scratch,jp,jr,self.tcpid)
            j=jp[:,self.dadr[:5]];delta=j.T@np.linalg.solve(j@j.T+np.eye(3)*.00003,error)
            q[:5]+=np.clip(delta,-.08,.08);q=np.clip(q,self.limits[:,0]+.002,self.limits[:,1]-.002)
        return q,float(np.linalg.norm(error))
    def rgb(self,camera='workspace'):
        if self.renderer is None:self.renderer=mujoco.Renderer(self.model,height=480,width=640)
        options=mujoco.MjvOption();options.geomgroup[3]=0
        self.renderer.update_scene(self.data,camera=camera,scene_option=options);return self.renderer.render().copy()
    def close(self):
        if self.renderer is not None:self.renderer.close();self.renderer=None

class DemonstrationRecorder:
    """Stream state/actions at 50Hz and timestamped RGB frames at 5Hz to disk."""
    def __init__(self):
        self.path=ROOT/'recordings'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        (self.path/'rgb').mkdir(parents=True);self.stream=(self.path/'trajectory.jsonl').open('w');self.count=0
    def write(self,sim,image=True):
        if self.count==0:
            (self.path/'physics_profile.json').write_text(json.dumps(sim.profile,indent=2))
        sample={'time_s':float(sim.data.time),'joint_rad':sim.data.qpos[sim.qadr].tolist(),
            'command_rad':sim.targets.tolist(),'applied_reference_rad':sim.servos.reference.tolist(),
            'joint_velocity_rad_s':sim.data.qvel[sim.dadr].tolist(),'actuator_torque_Nm':sim.data.actuator_force.tolist(),
            'tcp_m':sim.tcp.tolist(),'block_m':sim.data.xpos[sim.blockid].tolist(),'physics_status':sim.profile['status']}
        if image and self.count%10==0:
            from PIL import Image
            filename='rgb/%06d.jpg'%self.count;Image.fromarray(sim.rgb()).save(self.path/filename,quality=90);sample['rgb']=filename
        self.stream.write(json.dumps(sample)+'\n');self.count+=1
    def close(self):self.stream.close();print('Demonstration saved:',self.path)

class ArmReachEnv(gym.Env):
    """Six bounded joint increments at 50 Hz; observation is state, not yet learned vision."""
    metadata={'render_modes':['rgb_array'],'render_fps':50}
    def __init__(self,render_mode=None):
        self.sim=ArmSimulation();self.render_mode=render_mode;self.steps=0
        self.action_space=spaces.Box(-1,1,shape=(6,),dtype=np.float32)
        self.observation_space=spaces.Box(-np.inf,np.inf,shape=(21+len(self.sim.servos.state()),),dtype=np.float32)
    def observation(self):
        s=self.sim
        return np.r_[s.data.qpos[s.qadr],s.data.qvel[s.dadr],s.tcp,s.model.site_pos[s.goalid],s.data.xpos[s.blockid],s.servos.state()].astype(np.float32)
    def reset(self,seed=None,options=None):
        super().reset(seed=seed);self.sim.reset();self.steps=0
        # Task goals are random joint-reachable points near the nominal bent pose.
        scratch=mujoco.MjData(self.sim.model);scratch.qpos[:]=self.sim.data.qpos
        q=np.clip(HOME+self.np_random.uniform(-.16,.16,size=6),self.sim.limits[:,0],self.sim.limits[:,1])
        scratch.qpos[self.sim.qadr]=q;mujoco.mj_forward(self.sim.model,scratch)
        self.sim.model.site_pos[self.sim.goalid]=scratch.site_xpos[self.sim.tcpid]
        return self.observation(),self.sim.status()
    def step(self,action):
        a=np.clip(np.asarray(action,dtype=float),-1,1)
        self.sim.targets=np.clip(self.sim.targets+.025*a,self.sim.limits[:,0],self.sim.limits[:,1]);self.sim.step(10);self.steps+=1
        distance=float(np.linalg.norm(self.sim.tcp-self.sim.model.site_pos[self.sim.goalid]));success=distance<.008
        return self.observation(),-distance-.001*float(a@a)+float(success),bool(success),self.steps>=500,{'distance_m':distance,'success':success,**self.sim.status()}
    def render(self):return self.sim.rgb()
    def close(self):self.sim.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--headless',action='store_true');parser.add_argument('--steps',type=int,default=1000)
    parser.add_argument('--snapshot',action='store_true');parser.add_argument('--record',action='store_true');parser.add_argument('--demo',action='store_true');args=parser.parse_args()
    sim=ArmSimulation()
    recorder=DemonstrationRecorder() if args.record else None
    if args.headless:
        for i in range(args.steps):
            if args.demo:
                phase=i*sim.model.opt.timestep
                sim.targets=HOME+np.radians([15*np.sin(phase),5*np.sin(phase*.8),-8*np.sin(phase*.8),5*np.sin(phase*.8),12*np.sin(phase),0])
            sim.step(1)
            if recorder and i%10==0:recorder.write(sim,image=args.snapshot)
        if args.snapshot:
            from PIL import Image
            Image.fromarray(sim.rgb()).save(ROOT/'preview.png')
        if recorder:recorder.close()
        print(json.dumps(sim.status(),indent=2));sim.close();return
    import mujoco.viewer
    paused=[False]
    def keypress(key):
        if key==32:paused[0]=not paused[0]
    print('Use the viewer Control panel for all six servo targets. Space pauses physics. Close window to exit.')
    with mujoco.viewer.launch_passive(sim.model,sim.data,key_callback=keypress) as viewer:
        viewer.cam.lookat[:]=[.08,0,.19];viewer.cam.distance=.8;viewer.cam.azimuth=125;viewer.cam.elevation=-25
        viewer.opt.geomgroup[3]=0 # simplified collisions remain active, but hidden in the view
        while viewer.is_running():
            start=time.perf_counter()
            # The native Control panel writes data.ctrl, preserving the user's slider commands.
            sim.targets=sim.data.ctrl.copy()
            if not paused[0]:
                sim.step(10)
                if recorder:recorder.write(sim)
            viewer.sync()
            time.sleep(max(0,.02-(time.perf_counter()-start)))
    if recorder:recorder.close()
    sim.close()
if __name__=='__main__':main()
