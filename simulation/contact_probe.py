from manipulation_tasks import ManipulationTrial
import mujoco,numpy as np
t=ManipulationTrial('block',0);s=t.sim
s.data.qpos[t.object_qadr:t.object_qadr+3]=[.13,.0145,.008];s.step(100);t.start_object=s.data.xpos[s.blockid].copy()
def probe(trial,phase):
    if len(t.records) not in (260,265,270,280,300,320):return
    print('STEP',len(t.records),phase,'tcp',s.tcp,'obj',s.data.xpos[s.blockid], 'qR',s.data.qpos[s.qadr[-1]],'cmd',s.targets[-1],'torque',s.data.actuator_force[-1],flush=True)
    for c in s.data.contact:
        if t.object_geom not in c.geom:continue
        f=np.zeros(6);mujoco.mj_contactForce(s.model,s.data,list(s.data.contact).index(c),f)
        print('CONTACT',[mujoco.mj_id2name(s.model,mujoco.mjtObj.mjOBJ_GEOM,int(g)) for g in c.geom], 'normal',c.frame[:3],'force',f[:3], 'dist',c.dist,flush=True)
print(t.run(callback=probe));t.close()
