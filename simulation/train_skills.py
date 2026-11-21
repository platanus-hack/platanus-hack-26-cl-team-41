"""Train a compact goal-to-joint policy, then evaluate a hybrid physical grasp skill.
Learned: inverse-kinematic goal mapping. Scripted: task phases, jaw preload and
gravity feedback. This is privileged-state imitation, not RGB/language learning.
"""
from pathlib import Path
import argparse,json,time
import numpy as np
from manipulation_tasks import downward_ik,ManipulationTrial,prepare_scene,ROOT
OUT=ROOT/'trained';OUT.mkdir(exist_ok=True)

class GoalPolicy:
    def __init__(self,path):
        z=np.load(path);self.w=[z['w0'],z['w1'],z['w2']];self.b=[z['b0'],z['b1'],z['b2']]
        self.xmean=z['xmean'];self.xstd=z['xstd'];self.ymean=z['ymean'];self.ystd=z['ystd']
    def predict(self,point):
        point=np.asarray(point,dtype=float)
        if point.shape!=(3,) or not np.isfinite(point).all() or np.any(point<[.121,-.075,.010]) or np.any(point>[.145,.035,.044]):
            raise ValueError('Goal outside the trained downward-pose workspace')
        a=(point-self.xmean)/self.xstd
        a=np.tanh(a@self.w[0]+self.b[0]);a=np.tanh(a@self.w[1]+self.b[1]);y=(a@self.w[2]+self.b[2])*self.ystd+self.ymean
        # Preserve the downward tool-axis task constraint exactly.
        return np.r_[y[:3],np.pi-y[1]-y[2],0.]

def dataset(n=12000,seed=42):
    rng=np.random.default_rng(seed);x=[];y=[]
    while len(x)<n:
        point=rng.uniform([.121,-.075,.010],[.145,.035,.044])
        try:q=downward_ik(point)
        except ValueError:continue
        x.append(point);y.append(q[:4])
    return np.asarray(x),np.asarray(y)

def train(epochs=220):
    started=time.time();X,Y=dataset();rng=np.random.default_rng(91);order=rng.permutation(len(X));trainidx=order[:10000];valid=order[10000:]
    xm=X[trainidx].mean(0);xs=X[trainidx].std(0);ym=Y[trainidx].mean(0);ys=Y[trainidx].std(0)
    x=(X-xm)/xs;y=(Y-ym)/ys
    sizes=[3,64,64,4];w=[rng.normal(0,np.sqrt(2/(a+b)),(a,b)) for a,b in zip(sizes[:-1],sizes[1:])];b=[np.zeros(k) for k in sizes[1:]]
    params=w+b;m=[np.zeros_like(p) for p in params];v=[np.zeros_like(p) for p in params];step=0;history=[]
    for epoch in range(epochs):
        rng.shuffle(trainidx)
        for start in range(0,len(trainidx),256):
            ids=trainidx[start:start+256];a0=x[ids];a1=np.tanh(a0@w[0]+b[0]);a2=np.tanh(a1@w[1]+b[1]);pred=a2@w[2]+b[2]
            delta=2*(pred-y[ids])/(len(ids)*4);dw2=a2.T@delta;db2=delta.sum(0)
            d2=(delta@w[2].T)*(1-a2*a2);dw1=a1.T@d2;db1=d2.sum(0)
            d1=(d2@w[1].T)*(1-a1*a1);dw0=a0.T@d1;db0=d1.sum(0)
            step+=1
            for p,g,mm,vv in zip(params,[dw0,dw1,dw2,db0,db1,db2],m,v):
                mm*=.9;mm+=.1*g;vv*=.999;vv+=.001*g*g;p-=.001*(mm/(1-.9**step))/(np.sqrt(vv/(1-.999**step))+1e-8)
        if epoch%20==0 or epoch==epochs-1:
            pred=np.tanh(np.tanh(x[valid]@w[0]+b[0])@w[1]+b[1])@w[2]+b[2]
            rmse=float(np.sqrt(np.mean(((pred-y[valid])*ys)**2))*180/np.pi)
            history.append({'epoch':epoch+1,'validation_joint_rmse_deg':rmse});print('epoch',epoch+1,'validation RMSE deg',round(rmse,4),flush=True)
    path=OUT/'goal_policy.npz';np.savez_compressed(path,**{f'w{i}':a for i,a in enumerate(w)},**{f'b{i}':a for i,a in enumerate(b)},xmean=xm,xstd=xs,ymean=ym,ystd=ys)
    policy=GoalPolicy(path);errs=[]
    # Independent goal-set error in the predicted joint targets.
    for point,q in zip(*dataset(1000,seed=2026)):errs.append(np.degrees(policy.predict(point)-np.r_[q[:3],np.pi-q[1]-q[2],0]))
    report={'method':'Supervised imitation of analytic downward-pose IK using a 3-64-64-4 tanh MLP; hybrid contact skill uses scripted phases and state feedback.',
       'train_examples':10000,'validation_examples':2000,'unseen_goal_examples':1000,'epochs':epochs,
       'unseen_goal_joint_rmse_deg':float(np.sqrt(np.mean(np.asarray(errs)**2))),
       'history':history,'elapsed_s':time.time()-started,'physics_status':'preassembly_prior_not_hardware_calibrated',
       'input':'Desired TCP xyz in metres; all poses have downward gripper axis and zero wrist roll.',
       'limitations':['No learned camera perception or natural-language understanding.','No physical-robot deployment.','Jaw state/contact feedback is privileged simulator state.','Task contact solver uses elliptic friction cones and no-slip iterations to resolve narrow CAD pads.']}
    (OUT/'training_report.json').write_text(json.dumps(report,indent=2));return policy

def evaluate(policy,count=10,teacher=False,start_seed=2000):
    scene=prepare_scene('block');results=[]
    for seed in range(start_seed,start_seed+count):
        trial=ManipulationTrial('block',seed,scene=scene);result=trial.run(policy=None if teacher else policy);result['seed']=seed;results.append(result);trial.close()
        print('block test',seed,'lift',result['lift_success'],'place',result.get('place_success'),'bilateral fraction',result['bilateral_hold_fraction'],flush=True)
    report={'task':'Pick up a 16mm, 6g block, hold it above the table for 1 second with bilateral jaw contacts, place it in the tray and release.',
       'episodes':count,'lift_successes':sum(r['lift_success'] for r in results),'place_successes':sum(r.get('place_success',False) for r in results),
       'successes':sum(r.get('pick_place_success',False) for r in results),'success_rate':sum(r.get('pick_place_success',False) for r in results)/count,
       'held_out_seeds':[start_seed,start_seed+count-1],'controller':'analytic teacher' if teacher else 'learned goal policy + scripted contact phases + gravity/joint feedback',
       'object_position_range_m':[[.126,.006],[.134,.023]],'no_object_attachment':True,'results':results,
       'physics_status':'preassembly_prior_not_hardware_calibrated'}
    (OUT/('teacher_evaluation.json' if teacher else 'block_evaluation.json')).write_text(json.dumps(report,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epochs',type=int,default=220);p.add_argument('--tests',type=int,default=10);p.add_argument('--teacher-only',action='store_true');p.add_argument('--evaluate-only',action='store_true');args=p.parse_args()
    policy=None if args.teacher_only else GoalPolicy(OUT/'goal_policy.npz') if args.evaluate_only else train(args.epochs)
    print(json.dumps(evaluate(policy,args.tests,args.teacher_only),indent=2))
