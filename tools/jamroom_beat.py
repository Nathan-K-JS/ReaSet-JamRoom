"""Decode music beat activations with a consistent pulse and local tempo.

No Fadr BPM, drum-onset snapping, or extrapolated fixed-grid fallback.
"""
import numpy as np
from scipy.special import expit
from scipy.ndimage import gaussian_filter1d

FPS = 50


def decode_activations(predictions):
    sequences = [np.asarray(p['beats'], dtype=float) for p in predictions]
    if any(len(b) < 16 for b in sequences):
        raise ValueError('Too little beat evidence to establish a rehearsal pulse')
    if any(not np.isfinite(b).all() or np.any(np.diff(b)<=0) for b in sequences):
        raise ValueError('Beat model returned invalid beat times')
    intervals = np.concatenate([np.diff(b) for b in sequences])
    intervals = intervals[(intervals >= .25) & (intervals <= 1.5)]
    if not len(intervals): raise ValueError('No usable beat intervals')
    # A common metrical level across the recording, not a BPM from metadata.
    typical = float(np.median(intervals))
    probabilities = np.array([expit(p['beat_logits']) for p in predictions])
    if not np.isfinite(probabilities).all(): raise ValueError('Beat model returned invalid activations')
    evidence = np.median(probabilities, axis=0)
    times = np.arange(len(evidence))/FPS
    period = np.full(len(times), typical)
    for center in np.arange(0, times[-1]+4, 4):
        estimates=[]
        for b in sequences:
            ds=np.diff(b); ts=(b[:-1]+b[1:])/2
            local=ds[np.abs(ts-center)<16]
            # Preserve one pulse through a model's temporary half/double-time
            # interpretation. Actual gradual tempo changes remain in the data.
            local=np.where(local>typical*1.6,local/2,local)
            local=np.where(local<typical*.65,local*2,local)
            local=local[(local>typical*.75)&(local<typical*1.3)]
            if len(local)>4:
                lo,hi=np.percentile(local,[10,90]); kept=local[(local>=lo)&(local<=hi)]
                estimates.append(float(np.mean(kept)))
        if estimates:
            period[np.abs(times-center)<=2]=np.median(estimates)
    period=gaussian_filter1d(period, FPS*2)
    first=max(0,int(min(b[0] for b in sequences)*FPS))
    last=min(len(times)-1,int(max(b[-1] for b in sequences)*FPS))
    score=np.full(len(times),-1e9); previous=np.full(len(times),-1,dtype=int)
    # Centre broad activation peaks instead of arbitrarily choosing their
    # leading frame. This also avoids a systematic early-click bias.
    reward=gaussian_filter1d(evidence,.7)*2-.25
    for t in range(max(0,first-3),last+1):
        p=period[t]*FPS
        ds=np.arange(max(1,int(p*.72)),int(p*1.28)+1)
        ds=ds[ds<=t]
        if len(ds):
            values=score[t-ds]-30*np.log(ds/p)**2
            k=int(np.argmax(values)); score[t]=values[k]+reward[t]; previous[t]=t-ds[k]
        if t<=first+3 and reward[t]>score[t]:
            score[t]=reward[t];previous[t]=-1
    end_window=np.arange(max(first,last-int(typical*FPS*.6)),last+1)
    end=int(end_window[np.argmax(score[end_window])]); frames=[]
    while end>=0:
        frames.append(end);end=int(previous[end])
    frames=np.array(frames[::-1]);beats=frames/FPS
    supported=np.mean(np.array([np.max(probabilities[:,max(0,i-2):i+3],axis=1) for i in frames])>=.5,axis=1)>=2/3
    good=np.flatnonzero(supported)
    if len(good)<16: raise ValueError('Too little agreement to establish a rehearsal pulse')
    frames=frames[good[0]:good[-1]+1];beats=frames/FPS
    # Remove 20 ms frame quantisation from the pulse without snapping it to
    # drum fills or changing its metrical phase. Limit corrections to 20 ms.
    smoothed=beats.copy()
    for i in range(2,len(beats)-2):
        smoothed[i]=beats[i]+np.clip(np.mean(beats[i-2:i+3])-beats[i],-.02,.02)
    return smoothed, {'probabilities':probabilities,'evidence':evidence,'period':period,
                      'raw_beats':sequences,'frames':frames}
