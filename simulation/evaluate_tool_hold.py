"""Evaluate the learned movement policy under a 25g tool + 8g rigid-holder load.
This does not demonstrate grasping a loose iron or heated soldering.
"""
import json,numpy as np,mujoco
from manipulation_tasks import ManipulationTrial,prepare_scene,downward_ik,ROOT
from train_skills import GoalPolicy,OUT
def evaluate_tool(count=12,callback=None):
    scene=prepare_scene('mounted_tool');policy=GoalPolicy(OUT/'goal_policy.npz');trial=ManipulationTrial('mounted_tool',0,scene=scene)
    toolid=mujoco.mj_name2id(trial.sim.model,mujoco.mjtObj.mjOBJ_BODY,'mounted_cold_tool')
    rng=np.random.default_rng(20261121);results=[]
    for i in range(count):
        while True:
            goal=rng.uniform([.125,-.035,.025],[.135,.025,.039])
            try:downward_ik(goal);break
            except ValueError:continue
        trial.move(goal,.15,1.8,'position_cold_tool',False,policy,callback)
        trial.move(goal,.15,1.0,'hold_cold_tool',False,policy,callback)
        hold=trial.records[-50:];errors=[np.linalg.norm(np.asarray(r['tcp'])-goal) for r in hold]
        zaxis=trial.sim.data.xmat[toolid].reshape(3,3)[:,0]
        horizontal_error=abs(float(zaxis[2]));stable=max(np.linalg.norm(np.asarray(r['tcp'])-hold[-1]['tcp']) for r in hold)
        success=max(errors)<.008 and horizontal_error<.08 and stable<.004
        results.append({'trial':i,'goal_m':goal.tolist(),'success':bool(success),'max_hold_tcp_error_m':float(max(errors)),
            'hold_drift_m':float(stable),'tool_axis_vertical_component':horizontal_error})
        print('mounted cold-tool hold',i,'success',bool(success),'error mm',round(max(errors)*1000,2),flush=True)
    trial.close()
    report={'task':'Position and hold a cold 25g tool in an assumed rigid 8g holder for one second.',
       'controller':'Same learned goal policy plus scripted joint/gravity feedback','trials':count,'successes':sum(r['success'] for r in results),
       'requires_physical_holder':True,'heat_simulated':False,'cable_forces_simulated':False,
       'loose_tool_grasping_demonstrated':False,'hardware_validated':False,'results':results}
    (OUT/'tool_hold_evaluation.json').write_text(json.dumps(report,indent=2));return report
if __name__=='__main__':print(json.dumps(evaluate_tool(),indent=2))
