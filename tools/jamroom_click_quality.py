"""Click checks independent of the beat decoder; thresholds are in seconds.

Model agreement and drum support are evidence, not listening approval. Expose
failed time windows instead of averaging a bad passage into a good song score.
"""
import numpy as np
from scipy.signal import stft, find_peaks


def nearest_errors(reference, candidate):
    ref=np.asarray(reference,float); beats=np.asarray(candidate,float)
    if not len(ref): return np.full(len(beats),np.inf)
    idx=np.searchsorted(ref,beats)
    return np.minimum(abs(beats-ref[np.minimum(idx,len(ref)-1)]),
                      abs(beats-ref[np.maximum(idx-1,0)]))


def reference_scores(reference, candidate, tolerance=.05):
    """One-to-one precision/recall: extra and missing beats both count.

    Unlike nearest-hit percentage, double-speed and random dense clicks cannot
    get full marks. Strict phase is evaluated; no half/double/offbeat forgiveness.
    """
    ref=np.sort(np.asarray(reference,float)); est=np.sort(np.asarray(candidate,float))
    i=j=0;errors=[]
    while i<len(ref) and j<len(est):
        delta=est[j]-ref[i]
        if abs(delta)<=tolerance: errors.append(delta);i+=1;j+=1
        elif delta<0:j+=1
        else:i+=1
    p=len(errors)/len(est) if len(est) else 0
    r=len(errors)/len(ref) if len(ref) else 0
    return {'precision':p,'recall':r,'f1':2*p*r/(p+r) if p+r else 0,
            'matched':len(errors),'reference_beats':len(ref),'candidate_beats':len(est),
            'matched_p95_ms':float(np.percentile(np.abs(errors),95)*1000) if errors else None}


def drum_evidence(audio, sr=22050):
    f,t,z=stft(audio,sr,nperseg=512,noverlap=402)
    mag=np.abs(z)
    # Raw spectral changes, no tempo or click times are used to find attacks.
    bands=[]
    for lo,hi in [(30,180),(180,2000),(2000,10000)]:
        s=mag[(f>=lo)&(f<hi)]
        flux=np.maximum(0,np.diff(np.log1p(100*s),axis=1)).sum(axis=0)
        bands.append(flux)
    strength=sum(bands)
    peaks,_=find_peaks(strength,distance=12,prominence=max(.05,np.percentile(strength,85)*.2))
    energy=np.sqrt((mag**2).sum(axis=0))[1:]
    return {'times':t[1:],'strength':strength,'attacks':t[1:][peaks],
            'energy':energy,'active_threshold':max(1e-5,float(np.percentile(energy,90))*.025)}


def assess(beats, prediction, drums, duration):
    beats=np.asarray(beats,float)
    ev=drum_evidence(drums)
    errors=nearest_errors(ev['attacks'],beats)
    active=np.interp(beats,ev['times'],ev['energy'])>ev['active_threshold']
    probs=prediction['probabilities']
    support=[]
    for b in beats:
        i=round(b*50);support.append(np.mean(np.max(probs[:,max(0,i-2):i+3],axis=1)>=.5))
    support=np.asarray(support)
    # Missing alternate predictions represent metrical ambiguity. They can be
    # reconciled only with independent drum support AND no competing phase.
    model_beats=np.concatenate(prediction['raw_beats'])
    phase_errors=nearest_errors(beats,model_beats)
    windows=[]
    for start in np.arange(0,duration,12):
        mask=(beats>=start)&(beats<start+12)
        if not np.any(mask): continue
        hit=mask&active
        aligned=float(np.mean(errors[hit]<=.05)) if np.any(hit) else None
        agreement=float(np.mean(support[mask]>=2/3))
        raw=(model_beats>=start)&(model_beats<start+12)
        competing=float(np.mean(phase_errors[raw]>.06)) if np.any(raw) else 1
        intervals=np.diff(beats)[mask[:-1]]
        expected=np.interp(beats[mask],np.arange(len(prediction['period']))/50,prediction['period'])
        pace=float(np.median(intervals)/np.median(expected)) if len(intervals) else 1
        reasons=[]
        reconciled=agreement<.85 and aligned is not None and aligned>=.9 and competing<.1 and .85<pace<1.15
        if agreement<.85 and not reconciled: reasons.append('beat trackers disagree')
        if not .85<pace<1.15: reasons.append('pulse changes to half/double or wrong tempo')
        if np.sum(hit)>=8 and aligned<.8: reasons.append('click misses drum attacks')
        windows.append({'start':float(start),'end':min(float(start+12),duration),
                        'model_agreement':round(agreement,3),'drum_alignment':round(aligned,3) if aligned is not None else None,
                        'drum_beats':int(np.sum(hit)),'metre_reconciled':bool(reconciled),'reasons':reasons})
    reasons=[w for w in windows if w['reasons']]
    if np.sum(active)<min(32,len(beats)*.2):
        missing={'start':0.,'end':float(duration),'reasons':['insufficient independent drum evidence'],
                 'drum_alignment':None,'drum_beats':int(np.sum(active)),'metre_reconciled':False,'model_agreement':0.}
        reasons.append(missing);windows.append(missing)
    return {'status':'needs_review' if reasons else 'checks_passed',
            'label':'Needs click review' if reasons else 'Automatic timing checks passed; not listening-approved',
            'windows':windows,'flagged_windows':reasons,
            'first_beat':float(beats[0]),'last_beat':float(beats[-1]),
            'drum_alignment':float(np.mean(errors[active]<=.05)) if np.any(active) else None,
            'drum_active_beats':int(np.sum(active)),
            'median_bpm':float(60/np.median(np.diff(beats))),
            'note':'Beat-model agreement plus independent drum-attack checks. These do not prove musical correctness.'}
