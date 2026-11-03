import time
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from src.LSTM.model import preprocessing, tensor_batch
from src.pipeline import weights


class CausalConv(nn.Conv1d):
    def forward(self, x):
        return super().forward(F.pad(x, (self.dilation[0]*(self.kernel_size[0]-1), 0)))


class Block(nn.Module):
    def __init__(self, inputs, width, kernel, dilation, dropout):
        super().__init__()
        self.body = nn.Sequential(CausalConv(inputs,width,kernel,dilation=dilation), nn.ReLU(), nn.Dropout(dropout),
                                  CausalConv(width,width,kernel,dilation=dilation), nn.ReLU(), nn.Dropout(dropout))
        self.skip = nn.Identity() if inputs == width else nn.Conv1d(inputs,width,1)

    def forward(self, x):
        return F.relu(self.body(x)+self.skip(x))


class TCN(nn.Module):
    def __init__(self, features, width, kernel, dilations, dropout):
        super().__init__()
        self.blocks = nn.Sequential(*(Block(features*2 if i==0 else width,width,kernel,d,dropout)
                                      for i,d in enumerate(dilations)))
        self.head = nn.Linear(width,2)

    def temporal(self, x):
        return self.head(self.blocks(x.transpose(1,2)).transpose(1,2))

    def forward(self, x):
        return self.temporal(x)[:,-1,:]


CONFIGS = [
    dict(lookback=20,width=16,kernel=2,dilations=[1,2,4],dropout=.1,direction_weight=.25),
    dict(lookback=60,width=16,kernel=3,dilations=[1,2,4,8],dropout=.2,direction_weight=.25),
    dict(lookback=120,width=32,kernel=3,dilations=[1,2,4,8],dropout=.1,direction_weight=.5),
]


def network(columns, config):
    return TCN(len(columns),**{k:config[k] for k in ['width','kernel','dilations','dropout']})


def fit(train, valid, columns, config):
    torch.manual_seed(42)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = network(columns,config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.001)
    center,spread = preprocessing(train,columns)
    mean,scale = float(train.target.mean()),max(float(train.target.std()),1e-8)
    rng = np.random.default_rng(42)
    best, stale, curves = float('inf'),0,[]
    started = time.monotonic()
    def epoch(frame, order, training):
        model.train(training)
        total=0.
        y=frame.target.to_numpy()
        w=weights(frame) if training else np.ones(len(frame))
        with torch.set_grad_enabled(training):
            for i in range(0,len(order),512):
                ix=order[i:i+512]
                out=model(tensor_batch(frame,ix,center,spread).to(device))
                target=torch.as_tensor((y[ix]-mean)/scale,dtype=torch.float32,device=device)
                truth=torch.as_tensor(y[ix]>0,dtype=torch.float32,device=device)
                loss=((out[:,0]-target).square()+config['direction_weight']*F.binary_cross_entropy_with_logits(out[:,1],truth,reduction='none'))
                loss=(loss*torch.as_tensor(w[ix],dtype=torch.float32,device=device)).mean()
                if training:
                    optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
                total+=float(loss.detach())*len(ix)
        return total/len(order)
    for step in range(1,5):
        training=epoch(train,rng.permutation(len(train)),True)
        validation=epoch(valid,np.arange(len(valid)),False)
        curves.append(dict(epoch=step,training_loss=training,validation_loss=validation))
        if validation < best:
            best=validation;stale=0;best_epoch=step
            state={k:v.detach().cpu().numpy().copy() for k,v in model.state_dict().items()}
        else:
            stale+=1
            if stale>=2:break
    return dict(columns=columns,config=config,center=center,spread=spread,mean=mean,scale=scale,
                state=state,curves=curves,best_epoch=best_epoch,seconds=time.monotonic()-started,device=device)


def predict(bundle, frame):
    model=network(bundle['columns'],bundle['config'])
    model.load_state_dict({k:torch.from_numpy(v) for k,v in bundle['state'].items()})
    model.eval()
    pieces=[]
    with torch.inference_mode():
        for start in range(0,len(frame),512):
            ix=np.arange(start,min(start+512,len(frame)))
            out=model(tensor_batch(frame,ix,bundle['center'],bundle['spread']))
            pieces.append(torch.stack([out[:,0]*bundle['scale']+bundle['mean'],out[:,1].sigmoid()],dim=1).numpy())
    return np.concatenate(pieces).astype(float)
