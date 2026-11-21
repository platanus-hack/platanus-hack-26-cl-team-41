"""Check the checkpoint against independent MuJoCo FK and summarize held-out physics results."""
import json,hashlib,numpy as np,mujoco
from PIL import Image
from train_skills import GoalPolicy,dataset,OUT
from manipulation_tasks import ManipulationTrial,prepare_scene,downward_ik,ROOT
policy=GoalPolicy(OUT/'goal_policy.npz');trial=ManipulationTrial('block',0,scene=prepare_scene('block'));s=trial.sim
positions,_=dataset(1000,seed=424242);errors=[];teacher_errors=[]
for point in positions:
    s.data.qpos[s.qadr[:5]]=policy.predict(point);mujoco.mj_forward(s.model,s.data);errors.append(float(np.linalg.norm(s.tcp-point)))
    s.data.qpos[s.qadr[:5]]=downward_ik(point);mujoco.mj_forward(s.model,s.data);teacher_errors.append(float(np.linalg.norm(s.tcp-point)))
assert max(teacher_errors)<1e-8
assert max(errors)<.002, max(errors)
trial.close()
blocks=json.loads((OUT/'block_evaluation.json').read_text());variants=json.loads((OUT/'block_variant_evaluation.json').read_text());tool=json.loads((OUT/'tool_hold_evaluation.json').read_text())
summary={'learned_component':'Goal xyz to arm joint targets, trained from analytic kinematic demonstrations.',
 'scripted_components':['Task phases','Gripper contact/preload feedback','Gravity and joint-position feedback','Mechanical jaw coupling'],
 'independent_fk_tests':1000,'learned_goal_position_rmse_m':float(np.sqrt(np.mean(np.array(errors)**2))),
 'learned_goal_position_max_error_m':max(errors),'analytic_teacher_max_fk_error_m':max(teacher_errors),
 'block_pick_place':{'passed':blocks['successes'],'total':blocks['episodes'],'seeds':blocks['held_out_seeds']},
 'block_variants':{'passed':variants['successes'],'total':variants['episodes'],'sizes_mm':variants['sizes_mm']},
 'mounted_cold_tool':{'passed':tool['successes'],'total':tool['trials'],'requires_holder':True,'heat_simulated':False,'cable_forces_simulated':False},
 'physics_status':'preassembly_prior_not_hardware_calibrated','uses_privileged_simulator_state':True,
 'hardware_deployment':False,'camera_policy_trained':False,'language_policy_trained':False,
 'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/'goal_policy.npz',ROOT/'physics_profile.json',ROOT/'manipulation_tasks.py']}}
(OUT/'verification_summary.json').write_text(json.dumps(summary,indent=2))
gif=Image.open(OUT/'pick-place.gif');n=gif.n_frames;sheet=Image.new('RGB',(960,720))
for j,index in enumerate([0,int(n*.35),int(n*.58),n-1]):
    gif.seek(index);sheet.paste(gif.convert('RGB'),((j%2)*480,(j//2)*360))
sheet.save(OUT/'pick_place_contact_sheet.png')
print(json.dumps(summary,indent=2))
