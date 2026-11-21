"""Checks physics units and prior sensitivity; results are simulated, not hardware calibration."""
from pathlib import Path
import copy,json,math,csv
import numpy as np,mujoco
from arm_sim import ArmSimulation,HOME
from servo_physics import load_profile
from mass_properties import build_masses
ROOT=Path(__file__).resolve().parent
profile=load_profile();report={'status':profile['status'],'hardware_measurements_present':False,'checks':{}}
masses=build_masses(profile)
report['mass_estimate_kg']=masses['total_mass_kg']
report['mass_provenance']=masses['status']
report['hardware_measurements_present']=bool(masses['measured_components'] or profile['measurements_applied'])
for link,item in masses['links'].items():
    inertia=np.array(item['inertia_kg_m2']);eig=np.linalg.eigvalsh(inertia)
    assert np.all(eig>0) and eig[-1]<=eig[0]+eig[1]+1e-12,('Invalid rigid-body inertia',link,eig)
report['checks']['positive_physical_inertias']=True
sim=ArmSimulation();dt=sim.model.opt.timestep
# Check joint force envelope, finite-state dynamics, reference slew and delayed commands.
sim.targets=HOME.copy();sim.targets[0]+=.4;start=sim.servos.reference[0];first_change=None;max_slew=0.;max_force_ratio=0.
for i in range(1000):
    previous=sim.servos.reference.copy();sim.step(1)
    delta=np.abs(sim.servos.reference-previous);max_slew=max(max_slew,float(np.max(delta/(sim.servos.speed*dt))))
    if first_change is None and abs(sim.servos.reference[0]-start)>1e-8:first_change=i*dt
    assert np.isfinite(sim.data.qpos).all()
    assert np.all(sim.data.actuator_force<=sim.model.actuator_forcerange[:,1]+1e-6)
    assert np.all(sim.data.actuator_force>=sim.model.actuator_forcerange[:,0]-1e-6)
    max_force_ratio=max(max_force_ratio,float(np.max(np.abs(sim.data.actuator_force)/sim.servos.stall)))
assert abs(first_change-sim.servos.actual_delay_s)<=dt+1e-8,(first_change,sim.servos.actual_delay_s)
assert max_slew<=1+1e-8
report['checks']['command_delay_s']=first_change;report['checks']['reference_slew_fraction_max']=max_slew;report['checks']['stall_torque_fraction_max']=max_force_ratio
# Verify a free falling block against gravity away from arm/tray contacts.
blockjoint=mujoco.mj_name2id(sim.model,mujoco.mjtObj.mjOBJ_JOINT,'block_free')
qa=sim.model.jnt_qposadr[blockjoint];da=sim.model.jnt_dofadr[blockjoint]
sim.reset();sim.data.qpos[qa:qa+3]=[.38,.2,.1];sim.data.qvel[da:da+6]=0;mujoco.mj_forward(sim.model,sim.data)
steps=round(.1/dt);sim.step(steps);expected=.1-.5*9.81*(steps*dt)**2
drop_error=abs(sim.data.qpos[qa+2]-expected);assert drop_error<.002,drop_error
report['checks']['free_fall_error_m']=float(drop_error)
sim.step(round(1/dt));geom=mujoco.mj_name2id(sim.model,mujoco.mjtObj.mjOBJ_GEOM,'block_geom')
normal=0.
for k in range(sim.data.ncon):
    contact=sim.data.contact[k]
    if geom not in contact.geom:continue
    force=np.zeros(6);mujoco.mj_contactForce(sim.model,sim.data,k,force)
    normal+=force[0]*abs(contact.frame[2])
weight=sim.model.body_mass[sim.blockid]*9.81
assert abs(normal-weight)<.002,(normal,weight)
report['checks']['resting_block_normal_N']=normal;report['checks']['block_weight_N']=weight
# A static horizontal load audit is compared to STALL torque only, never a continuous rating.
sim.reset();sim.data.qpos[sim.qadr]=np.radians([0,90,0,0,0,0]);sim.data.qpos[sim.model.jnt_qposadr[sim.left]]=0;sim.data.qvel[:]=0
mujoco.mj_forward(sim.model,sim.data)
report['horizontal_static_load']={'gravity_torque_Nm':sim.data.qfrc_bias[sim.dadr].tolist(),
    'stall_fraction':(np.abs(sim.data.qfrc_bias[sim.dadr])/sim.servos.stall).tolist(),
    'interpretation':'No payload. Stall fractions do not establish safe continuous duty or thermal behavior.'}
sim.close()
# Same real-time maneuver at two integrator timesteps: detects numerical tuning artifacts.
states=[]
for timestep in (.002,.001):
    s=ArmSimulation(timestep_s=timestep);s.targets=np.radians([10,25,60,35,15,12]);s.step(round(2/timestep));states.append(s.tcp);s.close()
error=float(np.linalg.norm(states[0]-states[1]));assert error<.002,error
report['checks']['timestep_tcp_difference_m']=error
# Bound uncertainty before measurements exist; these are scenarios, not parameter fits.
scenarios=[]
for name,fraction,torque_factor in [('lighter_prints',.65,1.0),('nominal',.85,1.0),('heavy_prints_weaker_servos',1.0,.7)]:
    p=copy.deepcopy(profile);p['mass']['printed_solid_fraction']=fraction
    for servo in p['servo_types'].values():servo['stall_torque_Nm']*=torque_factor
    s=ArmSimulation(physics_profile=p);q,err=s.solve_position([.15,.04,.08]);s.targets=q;s.step(2000)
    scenarios.append({'name':name,'printed_fraction':fraction,'torque_factor':torque_factor,
        'tcp_error_m':float(np.linalg.norm(s.tcp-[.15,.04,.08])),'finite':bool(np.isfinite(s.data.qpos).all())});s.close()
report['prior_sensitivity_scenarios']=scenarios
(ROOT/'physics_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
