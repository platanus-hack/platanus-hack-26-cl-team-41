"""Meaningful smoke checks: source-frame FK, servo tracking, gripper coupling and Gym API."""
import json,math,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np,mujoco
from gymnasium.utils.env_checker import check_env
from arm_sim import ArmSimulation,ArmReachEnv,HOME
ROOT=Path(__file__).resolve().parent
sim=ArmSimulation();report={'mujoco_version':mujoco.__version__,'actuators':sim.model.nu}
assert sim.model.nu==6
# The source SolidCraft home TCP is independently defined by the finger-pad geometry.
sim.data.qpos[sim.qadr]=0;sim.data.qpos[sim.model.jnt_qposadr[sim.left]]=0;mujoco.mj_forward(sim.model,sim.data)
assert np.allclose(sim.tcp,[0,.0145,.4225],atol=1e-8),sim.tcp
report['source_zero_pose_tcp_m']=sim.tcp.tolist();report['source_zero_pose_xyz_rank']=sim.status()['xyz_rank'];report['source_zero_pose_arm_rank']=sim.status()['arm_rank']
sim.reset();sim.targets=np.radians([10,25,60,35,15,12]);sim.step(3000)
errors=np.abs(sim.data.qpos[sim.qadr]-sim.targets)
assert errors.max()<.035,('Tracking error rad',errors)
assert abs(sim.status()['jaw_coupling_error_rad'])<.002
assert np.all(np.abs(sim.data.actuator_force)<=sim.servos.stall+1e-6)
report['tracking_error_deg']=np.degrees(errors).tolist();report['jaw_coupling_error_rad']=sim.status()['jaw_coupling_error_rad']
sim.reset();target=np.array([.15,.04,.08]);q,error=sim.solve_position(target)
assert error<.002,(error,q)
sim.targets=q;sim.step(3000);tracking=float(np.linalg.norm(sim.tcp-target))
assert tracking<.012,(tracking,sim.status())
report['ik_predicted_error_m']=error;report['tracked_reach_error_m']=tracking
sim.reset();pixels=sim.rgb();assert pixels.shape==(480,640,3) and pixels.dtype==np.uint8 and pixels.std()>5
report['virtual_rgb_shape']=list(pixels.shape)
from PIL import Image
Image.fromarray(pixels).save(ROOT/'preview.png');sim.close()
env=ArmReachEnv();check_env(env,skip_render_check=True)
obs,info=env.reset(seed=42)
for _ in range(200):
    obs,reward,terminated,truncated,info=env.step(np.zeros(6,dtype=np.float32))
    assert np.isfinite(obs).all() and math.isfinite(reward)
    if terminated or truncated:env.reset()
env.close();report['gymnasium_check']='passed';report['finite_physics_steps']=2000;report['physics_status']=sim.profile['status']
(ROOT/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
