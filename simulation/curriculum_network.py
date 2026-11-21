"""Small NumPy imitation networks; no extra machine-learning dependencies."""
import numpy as np

class Network:
    def __init__(self,path):
        z=np.load(path);self.w=[z[f'w{i}'] for i in range(3)];self.b=[z[f'b{i}'] for i in range(3)]
        self.xm=z['xm'];self.xs=z['xs'];self.ym=z['ym'];self.ys=z['ys'];self.binary=bool(z['binary'])
    def predict(self,x):
        a=(np.asarray(x)-self.xm)/self.xs
        for w,b in zip(self.w[:2],self.b[:2]):a=np.tanh(a@w+b)
        a=a@self.w[2]+self.b[2]
        return 1/(1+np.exp(-np.clip(a,-40,40))) if self.binary else a*self.ys+self.ym

def fit(x,y,path,binary=False,epochs=160,seed=72):
    rng=np.random.default_rng(seed);order=rng.permutation(len(x));nv=max(100,len(x)//6);valid=order[:nv];train=order[nv:]
    xm=x[train].mean(0);xs=np.maximum(x[train].std(0),1e-5)
    ym=np.zeros(y.shape[1]) if binary else y[train].mean(0);ys=np.ones(y.shape[1]) if binary else np.maximum(y[train].std(0),1e-5)
    x=(x-xm)/xs;y=(y-ym)/ys
    sizes=[x.shape[1],64,64,y.shape[1]];w=[rng.normal(0,np.sqrt(2/(a+b)),(a,b)) for a,b in zip(sizes[:-1],sizes[1:])];b=[np.zeros(k) for k in sizes[1:]]
    params=w+b;mom=[np.zeros_like(p) for p in params];vel=[np.zeros_like(p) for p in params];step=0;history=[]
    for epoch in range(epochs):
        rng.shuffle(train)
        for start in range(0,len(train),128):
            ids=train[start:start+128];a0=x[ids];a1=np.tanh(a0@w[0]+b[0]);a2=np.tanh(a1@w[1]+b[1]);z=a2@w[2]+b[2]
            pred=1/(1+np.exp(-np.clip(z,-40,40))) if binary else z
            delta=(pred-y[ids])/(len(ids)*y.shape[1])*(1 if binary else 2)
            dw2=a2.T@delta;db2=delta.sum(0);d2=delta@w[2].T*(1-a2*a2)
            dw1=a1.T@d2;db1=d2.sum(0);d1=d2@w[1].T*(1-a1*a1)
            grads=[a0.T@d1,dw1,dw2,d1.sum(0),db1,db2];step+=1
            for p,g,m,v in zip(params,grads,mom,vel):
                m*=.9;m+=.1*g;v*=.999;v+=.001*g*g;p-=.001*(m/(1-.9**step))/(np.sqrt(v/(1-.999**step))+1e-8)
        if epoch%40==0 or epoch==epochs-1:
            z=np.tanh(np.tanh(x[valid]@w[0]+b[0])@w[1]+b[1])@w[2]+b[2]
            metric=float(np.mean((z>0)==(y[valid]>.5))) if binary else float(np.sqrt(np.mean(((z-y[valid])*ys)**2)))
            history.append({'epoch':epoch+1,'validation_binary_accuracy' if binary else 'validation_rmse':metric});print(path.name,history[-1],flush=True)
    np.savez_compressed(path,**{f'w{i}':v for i,v in enumerate(w)},**{f'b{i}':v for i,v in enumerate(b)},xm=xm,xs=xs,ym=ym,ys=ys,binary=binary)
    return Network(path),{'examples':len(x),'training_examples':len(train),'validation_examples':len(valid),'history':history}
