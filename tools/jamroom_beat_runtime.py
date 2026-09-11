"""Pinned, local CPU inference and verified official Beat This! checkpoints."""
import hashlib
from pathlib import Path
import threading

MODEL_DIR=Path(__file__).resolve().parent.parent/'imports'/'.beat-models'
MODEL_HASHES={
    'final0':'8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331',
    'final1':'365b553f43750717c907f32fbc42910f3b264d616654583df6e44472c93ead80',
    'final2':'8f810c0a44d3a979b0372b00fa61b4e3f83a8f2a6d963c7791b9d4852cdd1abc',
}
MODEL_VERSION='beat-this-1.1.0-final012'
_guard=threading.Lock()
_models=None


def prepare_models(log=print):
    import requests
    MODEL_DIR.mkdir(parents=True,exist_ok=True)
    for name,digest in MODEL_HASHES.items():
        path=MODEL_DIR/(name+'.ckpt')
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==digest: continue
        log('Downloading beat model '+name+' (81 MB, cached for future imports)...')
        tmp=path.with_suffix('.download')
        try:
            with requests.get('https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/'+name+'.ckpt',
                              stream=True,timeout=(15,60)) as response:
                response.raise_for_status()
                with tmp.open('wb') as output:
                    for chunk in response.iter_content(1024*1024):output.write(chunk)
            if hashlib.sha256(tmp.read_bytes()).hexdigest()!=digest:
                raise ValueError('Beat model download failed verification: '+name)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)


def models(log=print):
    global _models
    if _models is None:
        import torch
        from beat_this.inference import Audio2Frames
        prepare_models(log)
        torch.set_num_threads(4)
        _models=[Audio2Frames(str(MODEL_DIR/(name+'.ckpt')),device='cpu') for name in MODEL_HASHES]
    return _models


def predict(audio,log=print):
    from beat_this.model.postprocessor import Postprocessor
    post=Postprocessor(type='minimal')
    predictions=[]
    with _guard:
        for i,model in enumerate(models(log)):
            log('Following the music pulse: analysis '+str(i+1)+' of 3...')
            b,d=model(audio,22050)
            beats,downbeats=post(b,d)
            predictions.append({'beats':beats,'downbeats':downbeats,
                                'beat_logits':b.numpy(),'downbeat_logits':d.numpy()})
    return predictions


def check_runtime():
    import numpy as np
    with _guard:
        model=models(lambda message:print(message,flush=True))[0]
        b,_=model(np.zeros(22050*4,dtype=np.float32),22050)
        if len(b)!=201 or not np.isfinite(b.numpy()).all():
            raise RuntimeError('Beat model runtime check failed')
