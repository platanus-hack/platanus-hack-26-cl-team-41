"""Replay trained hybrid skills, optionally showing live physics or exporting an animation."""
import argparse,json,time,hashlib
import numpy as np
from PIL import Image
from manipulation_tasks import ManipulationTrial,prepare_scene,ROOT
from train_skills import GoalPolicy,OUT

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--task',choices=['pick-place','tool-hold'],default='pick-place');parser.add_argument('--seed',type=int,default=2005)
    parser.add_argument('--view',action='store_true');parser.add_argument('--gif',action='store_true');args=parser.parse_args()
    name='block' if args.task=='pick-place' else 'mounted_tool'
    trial=ManipulationTrial(name,args.seed,scene=prepare_scene(name));policy=GoalPolicy(OUT/'goal_policy.npz');frames=[];viewer=None
    if args.view:
        import mujoco.viewer
        viewer=mujoco.viewer.launch_passive(trial.sim.model,trial.sim.data)
        viewer.cam.lookat[:]=[.09,0,.15];viewer.cam.distance=.7;viewer.cam.azimuth=100;viewer.cam.elevation=-30;viewer.opt.geomgroup[3]=0
    def capture(t,phase):
        if args.gif and len(t.records)%6==0:frames.append(Image.fromarray(t.sim.rgb()).resize((480,360)))
        if viewer:
            if not viewer.is_running():raise KeyboardInterrupt
            viewer.sync();time.sleep(.02)
    try:
        if args.task=='pick-place':result=trial.run(policy=policy,callback=capture)
        else:
            results=[]
            for point in ([.13,.01,.034],[.13,-.02,.031],[.128,.015,.038]):
                trial.move(point,.15,2.,'position_cold_tool',False,policy,capture)
                error=trial.move(point,.15,1.2,'hold_cold_tool',False,policy,capture);results.append({'goal_m':point,'final_tcp_error_m':error})
            result={'task':'cold tool in an assumed rigid holder','heat':False,'loose_grasp':False,'results':results}
        (OUT/(args.task+'_demo.json')).write_text(json.dumps(result,indent=2))
        if frames:
            frames[0].save(OUT/(args.task+'.gif'),save_all=True,append_images=frames[1:],duration=120,loop=0,optimize=True)
        print(json.dumps(result,indent=2))
        if viewer:
            print('Demonstration finished. Close the viewer to exit.')
            while viewer.is_running():viewer.sync();time.sleep(.05)
    except KeyboardInterrupt:pass
    finally:
        if viewer:viewer.close()
        trial.close()
if __name__=='__main__':main()
