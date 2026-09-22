"""Isolated source preview and guarded library chart installation."""
import copy
import json
import uuid
from pathlib import Path
import requests
import jamroom_import as ji
from jamroom_chart_author import validate, lyric_items


def revision(server, cfg, song):
    key=f"song:{song['id']}:revision"
    response=requests.get(server._reaper_web(cfg)+'/_/GET/PROJEXTSTATE/ReaSetSong/'+key,timeout=10)
    response.raise_for_status()
    for line in response.text.splitlines():
        fields=line.split('\t')
        if len(fields)>=3 and fields[0]=='PROJEXTSTATE' and fields[2]==key:return fields[3] if len(fields)>3 else ''
    raise ValueError('Could not read the current chart revision from REAPER.')


def preview(server, body):
    cfg=ji.load_config(None);project=server.project_identity(cfg)
    song=next((s for s in server.project_songs() if s['name']==body['name']),None)
    if not song:raise ValueError('Song is no longer in this project.')
    song['project']=project;rev=revision(server,cfg,song)
    folder=Path(cfg['jobs_dir'])/ji.sanitize_filename(song['name'])
    job=copy.deepcopy(ji.load_job(folder));job.pop('authored_chart',None)
    job['duration']=song['end']-song['start']
    if body.get('url'):
        result=ji.build_chart_chords(job,body['url'],job_dir=folder,key_offset=body.get('key_offset'))
        job['chords']=result['chords'];job['chart']={**result,'url':body['url']}
    else:
        if body.get('id') is not None:ji.lyrics_use_record(job,folder,body['id'],persist=False)
        if body.get('offset') is not None:job.setdefault('lyrics',{})['offset_override']=float(body['offset'])
        ji.prepare_chart_document(job,folder)
    ident=uuid.uuid4().hex;cache=Path(cfg['jobs_dir'])/'.chart-candidates';cache.mkdir(parents=True,exist_ok=True)
    (cache/(ident+'.json')).write_text(json.dumps({'job':job,'song':song,'revision':rev}),encoding='utf-8')
    return {'candidate':ident,'document':job['chart_document'],'duration':job['duration']}


def install(server,body):
    ident=body.get('candidate','')
    if len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident):raise ValueError('Invalid chart preview')
    cfg=ji.load_config(None);entry=json.loads((Path(cfg['jobs_dir'])/'.chart-candidates'/(ident+'.json')).read_text(encoding='utf-8'))
    song=entry['song'];doc=validate(body['document'],song['end']-song['start'])
    if server.QUEUE is not None:server.QUEUE.protect([song['name']])
    folder=Path(cfg['jobs_dir'])/ji.sanitize_filename(song['name'])
    operation=Path(cfg['jobs_dir'])/'.chart-candidates'/ident
    operation.mkdir(parents=True,exist_ok=True)
    # A lost response can be retried with the same native transaction receipt.
    # Freeze its content and revision before sending anything to REAPER.
    accepted_path=operation/'accepted.json'
    if accepted_path.exists():
        accepted=json.loads(accepted_path.read_text(encoding='utf-8'))
        if accepted['requested']!=doc:
            raise ValueError('This preview was already submitted with different edits. Open a new preview.')
        doc=accepted['document']
    else:
        requested=copy.deepcopy(doc)
        doc['revision']='manual:'+uuid.uuid4().hex
        temporary=operation/'accepted.tmp'
        temporary.write_text(json.dumps({'requested':requested,'document':doc}),encoding='utf-8')
        temporary.replace(accepted_path)
    if not (operation/'job-before.json').exists():
        (operation/'job-before.json').write_text(json.dumps(ji.load_job(folder)),encoding='utf-8')
    result=server._push_song_items(cfg,song['name'],song,document=doc,lyric_lines=lyric_items(doc),expected_revision=entry['revision'],operation_dir=operation)
    job=entry['job'];job['authored_chart']=doc;job['chart_document']=doc
    ji.save_job(folder,job)
    return {'ok':True,'revision':doc['revision'],'message':result}
