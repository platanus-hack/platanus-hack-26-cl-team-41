import json
from manipulation_tasks import ManipulationTrial,prepare_scene,ROOT
from train_skills import GoalPolicy,OUT
scene=prepare_scene('block');policy=GoalPolicy(OUT/'goal_policy.npz');results=[]
for size in (.012,.016,.018):
    for seed in range(3000,3004):
        trial=ManipulationTrial('block',seed,scene=scene,object_size=size)
        result=trial.run(policy=policy);result['seed']=seed;result['size_m']=size
        result['mass_kg']=float(trial.sim.model.body_mass[trial.sim.blockid]);trial.close();results.append(result)
        print('block variant mm',round(size*1000),'seed',seed,'pick/place',result['pick_place_success'],flush=True)
report={'task':'Held-out size/mass variations of the learned hybrid block pick-and-place skill.',
 'episodes':len(results),'successes':sum(r['pick_place_success'] for r in results),'sizes_mm':[12,16,18],
 'mass_rule':'6g at 16mm, scaled with cube volume.','results':results,'hardware_validated':False}
(OUT/'block_variant_evaluation.json').write_text(json.dumps(report,indent=2))
