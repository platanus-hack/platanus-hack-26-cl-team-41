"""Independent held-out FK, free-body and collision-stop checks for the curriculum."""
import json,hashlib
import numpy as np,mujoco
from arm_sim import ArmSimulation,ROOT
from manipulation_tasks import downward_ik
from obstacle_curriculum import ExpandedGoal,BOUNDS,SCENE,OUT,DiverseTrial
from dock_curriculum import DockPolicy,upright_ik,TIP,SCENE as DOCK_SCENE

def check_fk(model_path,policy,ik,lower,upper,seed):
    s=ArmSimulation(scene_path=model_path);rng=np.random.default_rng(seed);errors=[];refused=0
    while len(errors)+refused<1000:
        p=rng.uniform(lower,upper)
        try:ik(p)
        except ValueError:continue
        try:q=policy.predict(p)
        except ValueError:refused+=1;continue
        s.data.qpos[s.qadr[:5]]=q;mujoco.mj_forward(s.model,s.data);errors.append(np.linalg.norm(s.tcp-p))
    s.close();assert np.quantile(errors,.95)<.0015
    return {'sampled_teacher_feasible_goals':1000,'neural_joint_limit_refusals':refused,'mean_fk_error_mm':float(np.mean(errors)*1000),'p95_fk_error_mm':float(np.quantile(errors,.95)*1000),'max_fk_error_mm':float(max(errors)*1000),'seed':seed}

def main():
    reach=check_fk(SCENE,ExpandedGoal(),downward_ik,*BOUNDS,17641)
    dock=check_fk(DOCK_SCENE,DockPolicy(),upright_ik,TIP+[-.009,-.009,-.028],TIP+[.009,.009,.018],17642)
    model=mujoco.MjModel.from_xml_path(str(DOCK_SCENE));assert not any(model.eq_type==mujoco.mjtEq.mjEQ_WELD)
    assert model.joint('receiver_free').type[0]==mujoco.mjtJoint.mjJNT_FREE
    # Fault injection: place an obstacle inside a finger; a single step must stop.
    t=DiverseTrial(18771,0);g=t.sim.model.geom('JawR_part_finger').id;position=t.sim.data.geom_xpos[g].copy()
    t.guard.set_obstacles(np.array([np.r_[position,[.008,.008,.008]], [.3,.3,.02,.01,.01,.02]]))
    stopped=False
    try:t.sim.step(1)
    except RuntimeError:stopped=True
    assert stopped and t.collision_events
    t.close()
    files=['curriculum_network.py','obstacle_curriculum.py','dock_curriculum.py','servo_physics.py','physics_profile.json','manipulation_tasks.py']
    hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    for f in ['reach_policy.npz','route_policy.npz','dock_reach_policy.npz','route_dataset.npz']:hashes[f]=hashlib.sha256((OUT/f).read_bytes()).hexdigest()
    report={'reach_fk':reach,'dock_fk':dock,'holder_has_free_joint_and_no_welds':True,'injected_collision_stopped_within_one_2ms_step':stopped,'hashes':hashes,
        'limits':'FK errors are simulation kinematics, not physical accuracy. Discrete primitive guards do not certify CAD clearance or hardware safety.'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
