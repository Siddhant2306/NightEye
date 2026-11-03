import numpy as np
from scipy.optimize import minimize
from sklearn.metrics import log_loss


def loss(y,p,task):
    return float(np.mean((y-p)**2)) if task=='return' else float(log_loss(y>0,np.clip(p,1e-7,1-1e-7),labels=[0,1]))


def weights(x,y,task,regularization):
    equal=np.full(x.shape[1],1/x.shape[1])
    scale=max(loss(y,x@equal,task),1e-10)
    result=minimize(lambda w:loss(y,x@w,task)/scale+regularization*np.sum((w-equal)**2),
                    equal,bounds=[(0,1)]*len(equal),constraints=[{'type':'eq','fun':lambda w:w.sum()-1}],
                    method='SLSQP')
    if not result.success:
        raise RuntimeError(result.message)
    w=np.clip(result.x,0,1)
    return w/w.sum()
