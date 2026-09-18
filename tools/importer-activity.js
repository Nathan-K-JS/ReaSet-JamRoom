/* Shared importer activity. Vanilla JS; GPL-3.0. Server journals own job state. */
window.ImporterActivity = (function () {
  'use strict';
  const $ = id => document.getElementById(id), tasks = new Map(), dismissed = new Map();
  const pending = new Map(), nativeFetch = window.fetch.bind(window);
  let serial = 0, visible = false, scroll = 0, focus = null, polling = false, project = null;
  const style = document.createElement('style');
  style.textContent = `
    [hidden]{display:none!important}html{scroll-padding-top:100px}
    #activityBar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:12px;
      background:#17362b;border:1px solid #39785f;border-radius:12px;padding:10px 12px;margin-bottom:16px}
    #activitySummary{flex:1;min-width:0;font-size:.9rem;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
    #activityToggle{width:auto;flex:none;margin:0;padding:10px;font-size:.85rem}
    #activitySignal{width:12px;height:12px;flex:none;border-radius:50%;background:#a1eac9}
    #activitySignal.busy{background:none;border:2px solid #a1eac955;border-top-color:#a1eac9;animation:activity-spin 1s linear infinite}
    #activitySignal.error{background:#ffb3a7}
    @keyframes activity-spin{to{transform:rotate(360deg)}}
    @media(prefers-reduced-motion:reduce){#activitySignal.busy{animation:none}}
    #activityTasks article{margin:16px 0;padding:16px;border:1px solid #39785f;border-radius:12px;background:#1d2026;overflow-wrap:anywhere}
    #activityTasks h2{margin-bottom:8px}#activityTasks p{line-height:1.5;margin:6px 0}
    #activityTasks nav{display:flex;gap:8px;flex-wrap:wrap}#activityTasks button{width:auto;margin:4px 0;font-size:.9rem}
    #activityTasks pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.8rem;background:#12141a;padding:12px;max-height:280px;overflow:auto}
    #activityTasks summary{cursor:pointer;padding:12px 0;min-height:44px}
    #activityTasks progress{width:100%;accent-color:#70dba6}
    #activityTasks .attention{border-color:#db9a65}#activityTasks .activity-result{padding:10px 0;border-bottom:1px solid #ffffff18}
    body.has-activity #progressCard,body.has-activity #receiptCard,body.has-activity #updateProgress{display:none!important}
    #activityHeading:focus{outline:2px solid #70dba6;outline-offset:4px}
    #importWorkspace select{max-width:100%}#updateMode{width:100%}
    .songrow .sname{min-width:0;overflow-wrap:anywhere}
    @media(max-width:500px){#activityBar{gap:8px;padding:8px}#activitySummary{font-size:.82rem}#activityToggle{font-size:.8rem}}
  `;
  document.head.append(style); document.body.classList.add('has-activity');
  $('activityTasks').innerHTML='<div id="activityCurrent"></div><details id="activityHistory"><summary>Recent results</summary><div id="activityHistoryTasks"></div></details>';
  new ResizeObserver(() => {
    document.documentElement.style.scrollPaddingTop = ($('activityBar').offsetHeight + 16) + 'px';
  }).observe($('activityBar'));
  function el(tag, text, parent) {
    const n = document.createElement(tag); if (text != null) n.textContent = text;
    if (parent) parent.append(n); return n;
  }
  function button(parent, label, action) {
    const b = el('button', label, parent); b.type = 'button';
    b.dataset.actionLabel=label;
    b.onclick = async () => { b.disabled = true; try { await action(); }
      catch(e) { notice(label, e.message, true); } finally { b.disabled = false; } };
  }
  function put(id, value) {
    const prior = tasks.get(id), signature = JSON.stringify(value);
    if (prior && prior.signature === signature) return;
    const sameRun=prior && prior.generation===value.generation && prior.batch?.id===value.batch?.id;
    tasks.set(id, {...value, id, signature, order:++serial, since:sameRun ? prior.since : Date.now()});
    render();
  }
  function open() {
    if (visible) return;
    visible = true; scroll = window.scrollY; focus = document.activeElement;
    $('importWorkspace').hidden = true; $('activityView').hidden = false;
    $('activityToggle').textContent = 'Back to songs'; window.scrollTo(0, 0);
    $('activityHeading').focus({preventScroll:true}); render();
  }
  function close() {
    if (!visible) return;
    visible = false; $('activityView').hidden = true; $('importWorkspace').hidden = false;
    $('activityToggle').textContent = 'View activity'; window.scrollTo(0, scroll);
    if (focus && focus.isConnected) focus.focus({preventScroll:true});
  }
  function remove(id){tasks.delete(id);render();}
  $('activityTasks').addEventListener('focusout',()=>setTimeout(render,0));
  $('activityToggle').onclick = () => visible ? close() : open();
  function notice(title, detail, failed, lines) {
    put('notice:' + title, {title, detail:detail || '', state:failed ? 'failed' : 'done', lines:lines || []});
  }
  function render() {
    const rows = Array.from(tasks.values()).filter(t => dismissed.get(t.id) !== t.signature);
    const rank=t=>['failed','interrupted','offline'].includes(t.state)?0:['running','sending','queued','preparing','applying','editing','checking'].includes(t.state)?1:2;
    rows.sort((a,b) => rank(a)-rank(b)||b.order-a.order);
    const active = rows.filter(t => ['running','sending','queued','preparing','applying','editing','checking'].includes(t.state));
    const errors = rows.filter(t => ['failed','interrupted','offline'].includes(t.state));
    const current = errors.find(t=>t.state==='offline') || active.find(t => t.foreground) || errors[0] || active[0] || rows[0];
    const summary = current ? (current.compact || current.title + ' — ' + current.detail) + (active.length>1 ? ' · '+active.length+' active' : '') : 'Ready · No active tasks';
    if ($('activitySummary').textContent !== summary) $('activitySummary').textContent = summary;
    $('activitySignal').className = errors.length ? 'error' : active.length ? 'busy' : '';
    if (!visible) return;
    // Keep unchanged cards, expanded details and keyboard focus intact while polling.
    const root=$('activityTasks');
    if(rows.length&&!$('activityCurrent').children.length)$('activityCurrent').textContent='';
    for (const n of Array.from(root.querySelectorAll('article'))) if (!rows.some(t => t.id === n.dataset.id)) n.remove();
    $('activityHistory').hidden=!rows.some(t=>t.state==='done'&&(t.id.startsWith('request:')||t.job));
    for (const t of rows) {
      const host=$(t.state==='done'&&(t.id.startsWith('request:')||t.job)?'activityHistoryTasks':'activityCurrent');
      let card = Array.from(root.querySelectorAll('article')).find(n => n.dataset.id === t.id);
      if(card&&card.parentElement!==host)host.append(card);
      if (card && card.dataset.signature === t.signature) continue;
      const expanded = card ? Array.from(card.querySelectorAll('details')).map(n=>n.open) : [];
      const problemsOnly=card?.querySelector('#activityProblems')?.checked;
      const wasFocused = card && card.contains(document.activeElement);
      const focused=wasFocused?document.activeElement:null;
      const summaryIndex=focused?.tagName==='SUMMARY'?Array.from(card.querySelectorAll('summary')).indexOf(focused):-1;
      const logScroll=card?Array.from(card.querySelectorAll('pre')).map(n=>n.scrollTop):[];
      const next = el('article'); next.dataset.id=t.id; next.dataset.signature=t.signature;
      if (['failed','offline','interrupted'].includes(t.state)) next.className='attention';
      el('h2',t.title,next); el('p',t.detail,next);
      if (t.total) { const p=el('progress',null,next);p.max=t.total;p.value=t.processed;p.setAttribute('aria-label','Songs processed'); }
      if (t.state==='sending' || t.state==='running') {
        const timer=el('p','',next); timer.className='note';timer.dataset.since=t.since;
      }
      const nav=el('nav',null,next);
      if (t.batch) {
        if(t.state==='running')button(nav,'Pause after this song',()=>window.pauseUpdates());
        else if(['paused','interrupted','failed'].includes(t.state) || t.batch.songs.some(s=>s.status==='failed'))
          button(nav,'Resume / retry batch',()=>window.startUpdates(true,false));
        button(nav,'Back to library',()=>{close();window.setSource('man');window.openUpdates();});
        const details=el('details',null,next);el('summary','Song results and details',details);
        const filter=el('input',null,details);filter.type='checkbox';filter.id='activityProblems';filter.checked=!!problemsOnly;
        const label=el('label','Show only problems',details);label.htmlFor=filter.id;
        const results=el('div',null,details);
        const show=()=>{results.replaceChildren();for(const s of t.batch.songs){
          if(filter.checked && s.status!=='failed')continue;
          const row=el('div',s.name+' — '+s.status+(s.message?' · '+s.message:''),results);row.className='activity-result';
          if(s.log&&s.log.length){const d=el('details',null,row);el('summary','Technical details',d);el('pre',s.log.join('\n'),d);}
        }};filter.onchange=show;show();
      }
      if(t.job)button(nav,['failed','interrupted','paused'].includes(t.state)?'Open recovery':'Open song',async()=>{
        if(window.ImportJobs && ImportJobs.open){
          await ImportJobs.open(t.job);close();
          ($('reviewCard').classList.contains('hide')?$('importQueue'):$('reviewCard')).scrollIntoView({block:'start'});
        }
      });
      if(t.lines && t.lines.length){const d=el('details',null,next);el('summary','Technical details',d);el('pre',t.lines.join('\n'),d);}
      if(!active.includes(t))button(nav,'Dismiss',()=>{dismissed.set(t.id,t.signature);render();});
      Array.from(next.querySelectorAll('details')).forEach((d,i)=>d.open=!!expanded[i]);
      if(card)card.replaceWith(next);else host.append(next);
      Array.from(next.querySelectorAll('pre')).forEach((n,i)=>n.scrollTop=logScroll[i]||0);
      if(focused){
        const replacement=focused.id?next.querySelector('#'+focused.id):focused.dataset.actionLabel?
          Array.from(next.querySelectorAll('button')).find(b=>b.dataset.actionLabel===focused.dataset.actionLabel):
          summaryIndex>=0?next.querySelectorAll('summary')[summaryIndex]:null;
        if(replacement)replacement.focus({preventScroll:true});
        else {next.tabIndex=-1;next.focus({preventScroll:true});}
      }
    }
    // New work appears before old results. Never move keyboard focus during polling.
    if(!root.contains(document.activeElement))for(const host of [$('activityCurrent'),$('activityHistoryTasks')]){
      let i=0;
      for(const t of rows){const card=Array.from(host.children).find(n=>n.dataset.id===t.id);if(!card)continue;
        if(host.children[i]!==card)host.insertBefore(card,host.children[i]||null);i++;
      }
    }
    if(!rows.length)$('activityCurrent').textContent='No work to show yet.';
  }
  setInterval(()=>document.querySelectorAll('[data-since]').forEach(n=>{
    const seconds=Math.floor((Date.now()-Number(n.dataset.since))/1000);
    n.textContent='Elapsed: '+seconds+'s'+(seconds>=30?' · Waiting for the next confirmed update.':'');
  }),1000);
  function jobs(data) {
    if(data.schema!==1)return;
    tasks.delete('notice:Import status unavailable');
    const ids=new Set(data.jobs.map(j=>'job:'+j.id));
    for(const id of tasks.keys())if(id.startsWith('job:')&&!ids.has(id))tasks.delete(id);
    for(const j of data.jobs) {
      if(j.state==='cached'){tasks.delete('job:'+j.id);continue;}
      const names={review:'Ready to review',done:'Added to REAPER — save your project',failed:'Needs attention',interrupted:'Resume available',paused:'Paused',queued:'Queued'};
      const queuePaused=data.paused&&j.state==='queued';
      put('job:'+j.id,{title:j.song,detail:queuePaused?'Queue paused':j.summary||j.stage||names[j.state]||j.state,state:queuePaused?'paused':j.state,job:j.id,lines:tasks.get('job:'+j.id)?.lines||[]});
    }
    render();
  }
  function jobDetail(row){
    const prior=tasks.get('job:'+row.id);
    if(prior){const {id,signature,order,since,...value}=prior;put(id,{...value,lines:row.log||[]});}
  }
  function batch(data) {
    if(project && project!==data.project){
      tasks.delete('batch');window.updateSelection={};window.updateSongs=[];window.updateProject=null;
      if(window.renderUpdateSongs)window.renderUpdateSongs();
      notice('REAPER project changed','Refresh the update list before selecting songs.');
    }
    project=data.project;window.updateBatch=data.batch;
    if(window.updateControls)window.updateControls();
    const b=data.batch;if(!b){tasks.delete('batch');render();return;}
    const count=state=>b.songs.filter(s=>s.status===state).length;
    const processed=count('done')+count('failed')+count('skipped'), current=b.songs.find(s=>s.status==='working');
    const detail=processed+'/'+b.songs.length+' processed · '+count('done')+' updated · '+count('failed')+' need attention · '+count('skipped')+' skipped'+
      (current?' · '+current.name+' — '+(current.stage||'Working'):b.error?' · '+b.error:'');
    const compact='Library update · '+processed+'/'+b.songs.length+' · '+(current?(current.stage||'Working')+' — '+current.name:b.status+(count('failed')?' · '+count('failed')+' need attention':''));
    put('batch',{title:'Library update — '+b.status,detail,compact,state:b.status==='complete'?(count('failed')?'failed':'done'):b.status,batch:b,total:b.songs.length,processed});
  }
  const labels={
    '/api/updates':'Checking library', '/api/updates/start':'Starting library update', '/api/updates/pause':'Requesting pause after this song',
    '/api/updates/protect':'Saving song protection', '/api/songs':'Reading REAPER songs', '/api/orphans':'Checking cached songs',
    '/api/library':'Loading Fadr library', '/api/search':'Searching songs', '/api/ug_search':'Searching charts',
    '/api/lyrics_search':'Searching lyrics', '/api/rechord':'Updating chart in REAPER', '/api/relyric':'Updating lyrics in REAPER',
    '/api/cue_repair':'Opening chart tools', '/api/delete_song':'Deleting song', '/api/setkey':'Saving Fadr key'
  };
  window.fetch = function(input, options) {
    const path=new URL(typeof input==='string'?input:input.url,location.href).pathname;
    const method=(options&&options.method||'GET').toUpperCase();
    const jobAction=path.startsWith('/api/jobs')&&method==='POST'&&!path.endsWith('/draft');
    const action=path.split('/').pop(), job=tasks.get('job:'+path.split('/')[3]);
    const actionNames={jobs:'Adding song',resume:'Resuming import',apply:'Submitting to REAPER',lyrics:'Updating lyrics',chart:'Updating chart',control:'Updating import queue',recover:'Checking Fadr recovery',reopen:'Opening saved review',remove:'Removing from queue',first:'Moving song first',pause:'Pausing import'};
    const title=labels[path]||(jobAction?(actionNames[action]||'Updating import')+(job?' — '+job.title:''):null);
    if(!title)return nativeFetch(input,options);
    const key=path+':'+(options&&options.body||'');
    // A double tap shares one request; mutations are never automatically retried.
    if(pending.has(key))return pending.get(key).then(r=>r.clone());
    const id='request:'+path;
    if(path==='/api/updates'||path==='/api/updates/start')tasks.delete('notice:Library update');
    if(jobAction)tasks.delete('notice:Import needs attention');
    const generation=++serial;
    put(id,{title,detail:method==='GET'?'Checking…':'Sending request…',state:'sending',foreground:true,generation});
    const promise=(async()=>{
      const controller=new AbortController();
      const readOnly=method==='GET'||['/api/search','/api/ug_search','/api/lyrics_search'].includes(path);
      const timeout=readOnly?setTimeout(()=>controller.abort(),20000):null;
      try {
        const response=await nativeFetch(input,{...options,signal:options?.signal||controller.signal}), data=await response.clone().json();
        if(!response.ok||data.error)throw Error(data.error||'Importer answered HTTP '+response.status);
        if(path==='/api/updates')batch(data);
        if(tasks.get(id)?.generation===generation){
          if(jobAction||path==='/api/updates/start'){tasks.delete(id);render();}
          else put(id,{title,detail:method==='GET'?'Check complete':'Request confirmed',state:'done',generation});
        }
        return response;
      }catch(e){
        const detail=e.message+(e instanceof TypeError?' — Connection lost; work may still be running. Check status before retrying.':e.name==='AbortError'?' — Check timed out. Try refreshing the list.':'');
        if(tasks.get(id)?.generation===generation)put(id,{title,detail,state:'failed',generation});
        throw Error(detail);
      }finally{clearTimeout(timeout);pending.delete(key);}
    })();pending.set(key,promise);return promise.then(r=>r.clone());
  };
  async function poll() {
    if(polling)return;polling=true;
    try {
      const response=await nativeFetch('/api/updates/status',{signal:AbortSignal.timeout(15000)});
      const data=await response.json();if(!response.ok||data.error)throw Error(data.error||'Cannot read library status');
      tasks.delete('connection:updates');batch(data);
    }catch(e){put('connection:updates',{title:'Library status unavailable',detail:'Work may still be running. Reconnecting… '+e.message,state:'offline'});}
    finally{polling=false;render();}
  }
  setTimeout(poll,0);setInterval(poll,2500);
  return {open,close,notice,jobs,jobDetail,batch,poll,put,remove};
})();
