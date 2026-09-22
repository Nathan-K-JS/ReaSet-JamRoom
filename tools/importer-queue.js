/* Persistent import workspaces. Vanilla browser UI; GPL v3. */
window.ImportJobs = (function(){
  'use strict';
  var api = {enabled:false}, selected = null, detail = null, rows = [], paused = false;
  var dirty = false, timer = null, saving = null, version = 0, selection = 0, busy = false, polling = false;
  var filterText='',filterState='all',conflict=false;
  var chartDraft=null,previousChart=null,chartView='edit';
  var rendered = '', listSignature = '', card, list, message, saved, target, recovery;
  function el(tag, text, parent){
    var node = document.createElement(tag);
    if(text !== undefined) node.textContent = text;
    if(parent) parent.appendChild(node);
    return node;
  }
  function button(text, action, parent){
    var node = el('button', text, parent); node.className = 'small';
    node.onclick = function(){
      if(node.disabled)return;
      node.disabled=true;node.textContent='Working…';
      Promise.resolve().then(action).catch(failure).finally(function(){node.disabled=false;node.textContent=text;});
    };
    return node;
  }
  function failure(error){
    if(window.ImporterActivity)ImporterActivity.notice('Import needs attention',error.message||String(error),true);
    message.textContent = error.message || String(error);
    message.style.color = '#ffb3a7';
  }
  async function request(path, body){
    var response = await fetch('/api/jobs' + path, body === undefined ? {signal:AbortSignal.timeout(20000)} : {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    var data = await response.json();
    if(!response.ok || data.error) throw new Error(data.error || 'Importer request failed');
    return data;
  }
  function draft(){
    var value = {slots:{}, labels:{}, fields:{}};
    value.chart_view=chartView;
    if(chartDraft)value.chart_document=chartDraft;
    if(previousChart)value.previous_chart=previousChart;
    document.querySelectorAll('#stemList select').forEach(function(node){value.slots[node.dataset.file] = node.value;});
    document.querySelectorAll('#stemList input.lbl').forEach(function(node){value.labels[node.dataset.file] = node.value.trim();});
    var offset = parseFloat($('lyrOffset').value);
    value.lyrics_offset = Number.isFinite(offset) ? offset : null;
    ['lyrQuery','ugQuery','ugUrl'].forEach(function(id){value.fields[id] = $(id).value;});
    return value;
  }
  function restoreDraft(value){
    value = value || {};
    chartView=value.chart_view||'edit';chartDraft=value.chart_document||null;previousChart=value.previous_chart||null;
    document.querySelectorAll('#stemList select').forEach(function(node){
      if(value.slots && Object.hasOwn(value.slots, node.dataset.file)) node.value = value.slots[node.dataset.file];
    });
    document.querySelectorAll('#stemList input.lbl').forEach(function(node){
      if(value.labels && Object.hasOwn(value.labels, node.dataset.file)){
        node.value = value.labels[node.dataset.file]; node.dataset.touched = '1';
      }
      node.classList.toggle('hide', node.closest('.stemrow').querySelector('select').value === 'SKIP');
    });
    if(value.lyrics_offset != null) $('lyrOffset').value = value.lyrics_offset;
    Object.keys(value.fields || {}).forEach(function(id){if($(id)) $(id).value = value.fields[id];});
  }
  async function flush(){
    clearTimeout(timer);
    if(saving) await saving;
    if(!dirty || !selected || !detail || detail.state !== 'review') return;
    var id = selected, sequence = version, value = draft();
    saved.textContent = 'Saving...';
    saving = request('/' + id + '/draft', {revision:detail.revision, draft:value});
    try {
      var result = await saving;
      if(selected === id){
        detail.revision = result.revision; detail.draft = value;
        dirty = version !== sequence;
        saved.textContent = dirty ? 'Saving...' : 'Saved';
      }
    } catch(error){
      saved.textContent = 'Could not save. Keep this page open; retry or reopen the saved review.';
      throw error;
    } finally { saving = null; }
    if(dirty) await flush();
  }
  function edited(){
    if(!selected || !detail || detail.state !== 'review' || detail.apply_started || busy) return;
    dirty = true; version++; saved.textContent = 'Saving...';
    clearTimeout(timer); timer = setTimeout(function(){flush().catch(failure);}, 400);
  }
  function renderDetail(row){
    if(window.ImporterActivity)ImporterActivity.jobDetail(row);
    $('progressCard').classList.remove('hide');
    $('log').textContent = (row.log || []).join('\n');
    $('progTitle').textContent = row.song + ' — ' + (row.stage || row.state);
    target.textContent = 'Apply target: ' + (row.target || 'Choose the open REAPER project before applying');
    message.textContent = row.summary||'';
    if(row.state === 'review' && row.review && rendered !== row.id + ':review'){
      showReview(row.review); restoreDraft(row.draft);
      rendered = row.id + ':review'; saved.textContent = 'Saved';
    } else if(row.state !== 'review'){
      resetReviewPanel(); rendered = row.id + ':' + row.state;
    }
    $('applyBtn').disabled = row.state !== 'review' || busy;
    $('applyBtn').textContent = row.apply_started ? 'Check / retry Apply' : 'Add to REAPER';
    document.querySelectorAll('#reviewCard input,#reviewCard select').forEach(function(node){node.disabled = !!row.apply_started;});
    if(window.ImportWorkspace)ImportWorkspace.job(row,false);
    renderJobActions(row);
  }
  async function select(id){
    if(window.ChartAuthor&&ChartAuthor.active)ChartAuthor.active.close();
    if(busy) throw new Error('Let the current review change finish first.');
    await flush();
    var generation = ++selection;
    busy = true; $('reviewCard').inert = true;
    if(window.ImporterActivity)ImporterActivity.put('opening-review',{title:'Opening saved import',detail:'Loading review…',state:'sending',foreground:true});
    var row;
    try {row = await request('/' + id);}
    finally {busy = false; $('reviewCard').inert = false;if(window.ImporterActivity)ImporterActivity.remove('opening-review');}
    if(generation !== selection) return;
    dismissReceipt(); resetReviewPanel();
    selected = id; detail = row; rendered = ''; dirty = false; conflict=false;
    localStorage.setItem('jamroom-import-job', id);
    message.textContent = ''; renderDetail(row); renderList();
    if(window.ImportWorkspace)ImportWorkspace.job(row,true);
    if(row.state === 'cached') message.textContent = 'Cached song: press Resume / open to prepare its review. Existing completed stages are reused.';
  }
  async function close(){
    if(window.ChartAuthor&&ChartAuthor.active)ChartAuthor.active.close();
    if(busy) throw new Error('Let the current review change finish first.');
    await flush(); selection++; selected = null; detail = null; rendered = '';
    localStorage.removeItem('jamroom-import-job');
    resetReadyState(); target.textContent = ''; saved.textContent = '';
    message.textContent = 'Work is kept in the song list. Add another song whenever you like.';
    setPipelineActive(false); renderList();
    if(window.ImportWorkspace)ImportWorkspace.clearJob();
  }
  var names = {queued:'Queued', preparing:'Processing', review:'Ready to review',
    applying:'Adding to REAPER', done:'Added — save REAPER', failed:'Needs attention',
    interrupted:'Resume available', paused:'Paused', cached:'Cached song', editing:'Updating review', checking:'Checking Fadr'};
  var actionSignature='';
  function renderJobActions(row){
    var host=$('workspaceJobActions');if(!host)return;
    var sig=JSON.stringify([row.id,row.state,row.apply_started]);if(sig===actionSignature)return;
    actionSignature=sig;host.replaceChildren();
    if(['failed','paused','interrupted','cached'].includes(row.state)){
      button(row.apply_started?'Check Apply':'Resume import',async function(){
        if(row.apply_started){await api.apply();return;}
        await request('/'+row.id+'/resume',{});await refresh();
      },host);
      if(row.state!=='cached'&&!row.apply_started)button('Check Fadr / recover',function(){return provider(row.id);},host);
    }
    if(row.state==='done')button('Review / re-add',async function(){await request('/'+row.id+'/reopen',{revision:detail.revision});rendered='';await refresh();},host);
  }
  function renderList(){
    var signature=JSON.stringify([rows,selected,paused,filterText,filterState]);if(signature===listSignature)return;listSignature=signature;
    var menus=new Set(Array.from(list.querySelectorAll('details[open]')).map(function(n){return n.dataset.song;}));
    var focus=document.activeElement,focusJob=focus&&focus.closest('[data-job]'),focusLabel=focus&&focus.textContent;
    var top=$('workspaceQueue')&&$('workspaceQueue').scrollTop;
    list.replaceChildren();
    var active=rows.filter(function(r){return !['done','cached'].includes(r.state);});
    $('queueCounts').textContent=active.length+' unfinished / '+active.filter(function(r){return r.state==='review';}).length+' ready'+(paused?' / Queue paused':'');
    var shown=rows.filter(function(r){
      if(filterText&&!r.song.toLowerCase().includes(filterText.toLowerCase()))return false;
      if(filterState==='completed')return ['done','cached'].includes(r.state);
      if(filterState==='attention')return ['failed','interrupted','paused'].includes(r.state);
      if(filterState==='review')return r.state==='review';
      if(filterState==='progress')return ['queued','preparing','applying','checking','editing'].includes(r.state);
      return !['done','cached'].includes(r.state);
    });
    shown.forEach(function(row){
      var line=el('div',undefined,list);line.className='queue-row'+(selected===row.id?' selected':'');line.dataset.job=row.id;
      el('strong',row.song,line);el('span',names[row.state]||row.state,line).className='note';
      var open=button('Open',function(){return select(row.id);},line);open.setAttribute('aria-label','Open '+row.song);
      if(!['preparing','applying','editing','checking'].includes(row.state)){
        var more=el('details',undefined,line);more.dataset.song=row.id;more.open=menus.has(row.id);el('summary','More',more);var actions=el('div',undefined,more);
        if(row.state==='queued'){
          button('Move first',async function(){await request('/'+row.id+'/first',{});await refresh();},actions);
          button('Pause',async function(){await request('/'+row.id+'/pause',{});await refresh();},actions);
        }
        button('Remove from queue',async function(){
          if(!confirm('Remove '+row.song+' from the queue? Downloaded files and saved review choices are kept. You can reopen it later.'))return;
          if(selected===row.id)await close();await request('/'+row.id+'/remove',{});await refresh();
        },actions);
      }
    });
    if(!shown.length)el('p',rows.length?'No imports match this filter.':'Add a song to begin. Saved work will appear here.',list).className='note';
    if($('workspaceQueue'))$('workspaceQueue').scrollTop=top||0;
    if(focusJob){var row=Array.from(list.children).find(function(n){return n.dataset.job===focusJob.dataset.job;});var replacement=row&&Array.from(row.querySelectorAll('button,summary')).find(function(n){return n.textContent===focusLabel;});if(replacement)replacement.focus({preventScroll:true});}
  }

  async function refresh(){
    if(polling) return;
    polling = true;
    try {
      var result = await request('');
      if(result.schema !== 1) return;
      rows = result.jobs; paused = result.paused; renderList();
      if(window.ImporterActivity)ImporterActivity.jobs(result);
      if(selected && !busy && !dirty && !saving){
        var id = selected, generation = selection, row = await request('/' + selected);
        if(id !== selected || generation !== selection || dirty || saving || busy) return;
        if(conflict||detail&&row.state==='review'&&row.revision!==detail.revision&&($('reviewCard').contains(document.activeElement)||window.ChartAuthor&&ChartAuthor.active)){
          conflict=true;$('workspaceReviewTools').open=true;
          saved.textContent='This review changed elsewhere. Reload the saved review before continuing.';
          $('applyBtn').disabled=true;return;
        }
        if(detail && row.revision !== detail.revision) rendered = '';
        detail = row; renderDetail(row);
      }
    } finally { polling = false; }
  }
  api.add = async function(){
    try {
      await flush();
      var body = {band:$('band').value.trim(), title:$('title').value.trim()};
      if(g_source === 'lib'){
        if(!g_libPicked) return;
        Object.assign(body, {asset:g_libPicked.id, duration:g_libPicked.duration,
          allow_new_splits:g_libPicked.subsplits_done >= 2 || $('allowSplits').checked});
      } else { if(!picked) return; body.url = picked.url; }
      $('importBtn').disabled = true;
      var previous = selected;
      var result = await request('', body);
      $('confirmCard').classList.add('hide');
      await refresh();
      if(!previous){
        await select(result.id);
        if(detail.state==='review'){if(window.ImportWorkspace)ImportWorkspace.job(detail,true);else $('reviewCard').scrollIntoView({block:'start'});}
        else if(window.ImporterActivity)ImporterActivity.open();
      }
      else message.textContent = body.band + ' - ' + body.title + ' is in your import list. Your earlier review is saved.';
    } catch(error){failure(error);}
    finally {$('importBtn').disabled = false; setPipelineActive(false);}
  };
  api.cached = async function(name){
    try {
      var row = rows.find(function(r){return r.song === name;});
      if(!row){var restored = await request('/control', {open_cached:name}); await refresh(); row = rows.find(function(r){return r.id === restored.id;});}
      if(!row) throw new Error('Cached song is not available.');
      await select(row.id);
      if(row.state === 'cached') {await request('/' + row.id + '/resume', {}); await refresh();}
    } catch(error){failure(error);}
  };
  api.apply = async function(){
    if(busy || !selected) return;
    busy=true; $('applyBtn').disabled=true;
    try {
      // Save the initial default choices too, even when no control was edited.
      if(detail.state === 'review' && !detail.apply_started){dirty = true; version++; await flush();}
      var checked = await request('/' + selected + '/check-target', {revision:detail.revision});
      if(!checked.matches){
        if(!checked.can_select)throw new Error('This import may already have been added. Open its original target project and use Check Apply; it cannot safely be redirected.');
        if(!confirm('This saved review has no matching project target. Add this song to the project currently active in REAPER? Check the selected REAPER project tab before continuing.'))return;
        var rebound = await request('/' + selected + '/target', {revision:detail.revision,expected_project:checked.current});
        detail.revision=rebound.revision;detail.target=rebound.target;renderDetail(detail);
      }
      await request('/' + selected + '/apply', {revision:detail.revision});
      rendered = ''; busy=false; await refresh();
    } catch(error){failure(error);}
    finally{busy=false; $('applyBtn').disabled=!detail||detail.state!=='review';}
  };
  api.choose = async function(action, body, btn){
    try {
      if(busy) return;
      await flush(); busy = true; btn.disabled = true;
      var result = await request('/' + selected + '/' + action, Object.assign({}, body, {revision:detail.revision,preview:true}));
      var candidate=result.candidate,id=selected;
      ChartAuthor.open({title:'Preview replacement · '+detail.song,document:result.review.document,duration:result.review.duration,
        save:async function(doc){
          if(selected!==id)throw Error('Selected import changed.');
          var accepted=await request('/'+id+'/accept-chart',{revision:detail.revision,candidate:candidate});
          detail=accepted;showReview(detail.review);restoreDraft(detail.draft);chartDraft=doc;dirty=true;version++;await flush();
          setTimeout(function(){ChartAuthor.active.close();api.editChart();},0);
        },savedMessage:'Chart selected.'});
      document.querySelector('#chart-author .ca-save').textContent='Use this chart';ChartAuthor.audition(ChartAuthor.active,{job:id});
      return;

    } catch(error){failure(error);}
    finally {busy = false; btn.disabled = false;}
  };
  api.editChart=function(){
    if(!detail||detail.state!=='review'||detail.apply_started)return;
    var id=selected,audio=new Audio(),stopped=false;
    document.querySelectorAll('audio').forEach(function(a){a.pause();});
    var editor=ChartAuthor.open({view:chartView,onView:function(view){chartView=view;edited();},title:detail.song,document:chartDraft||detail.review.document,duration:detail.review.duration,
      draftStatus:function(){return conflict?'Review conflict':saving||dirty?'Saving draft…':'Draft saved';},previous:previousChart,onPrevious:function(doc){previousChart=doc;},draftKey:'import-chart:'+id,audio:audio,audioStatus:'Preparing song audio…',
      onChange:function(doc){if(selected===id){chartDraft=doc;edited();}},
      canSave:function(){return conflict?'Review changed in another browser. Reload the saved review.':'';},
      save:async function(doc){chartDraft=doc;edited();await flush();},
      onClose:function(){stopped=true;audio.pause();flush().catch(failure);},
      changeSource:function(){ChartAuthor.active.close();if(window.ImportWorkspace)ImportWorkspace.tab('chords');$('ugQuery').focus();$('ugQuery').scrollIntoView({block:'center'});}
    });
    async function prepare(){try{var response=await fetch('/api/chart-preview?job='+encodeURIComponent(id)),data=await response.json();if(stopped)return;if(data.error||data.state==='error'){editor.status(data.error||data.message);return;}if(data.state==='ready'){audio.src='/api/chart-preview?job='+encodeURIComponent(id)+'&audio=1';editor.setAudio(audio,data.peaks);}else{editor.status(data.message||'Preparing audio…');setTimeout(prepare,1000);}}catch(e){if(!stopped)editor.status('Audio unavailable: '+e.message+'. Chart editing is still available.');}}
    audio.addEventListener('play',function(){document.querySelectorAll('audio').forEach(function(a){a.pause();});});
    prepare();
  };
  api.open = select;
  api.nextReady=async function(){var next=rows.find(function(r){return r.state==='review'&&r.id!==selected;});if(next)await select(next.id);else if(window.ImportWorkspace)ImportWorkspace.showQueue();};
  api.close = function(){return close().catch(failure);};
  async function provider(id, body){
    var result=await request('/'+id+'/provider',body||{});
    await refresh();message.textContent=result.summary;
    recovery.replaceChildren();el('p',result.summary,recovery);
    if(result.retryable)button('Retry failed split (may charge)',async function(){
      if(!confirm('Fadr confirmed failure. Allow a replacement split, which may incur a new charge?'))return;
      await provider(id,{retry_failed:true});await request('/'+id+'/resume',{});await refresh();
    },recovery);
    button('Choose existing Fadr recording',async function(){
      var response=await fetch('/api/library'),data=await response.json();
      if(data.error)throw new Error(data.error);
      var chooser=el('select',undefined,recovery);chooser.setAttribute('aria-label','Existing Fadr recording');
      (data.songs||[]).forEach(function(song){var option=el('option',song.name||song.title||song.id,chooser);option.value=song.id;});
      button('Use selected recording',async function(){
        if(!chooser.value)return;
        if(!confirm('Use '+chooser.selectedOptions[0].textContent+' as this song’s recovered recording?'))return;
        await provider(id,{asset:chooser.value});
      },recovery);
    },recovery);
  }
  api.source = async function(source){
    try {await flush(); setSource(source, true);} catch(error){failure(error);}
  };
  async function init(){
    var result = await request('');
    if(result.schema !== 1) return; // Old-server/browser test compatibility.
    api.enabled = true; setPipelineActive(false);
    card = document.createElement('div'); card.className = 'card'; card.id = 'importQueue';
    $('checksCard').after(card);
    var top=el('div',undefined,card);top.className='queue-top';el('h2','Your imports',top);
    button('Add songs',async function(){await flush();setSource('yt',true);},top);
    el('div','',card).id='queueCounts';
    var search=el('input',undefined,card);search.type='search';search.id='queueSearch';search.placeholder='Find an import';search.setAttribute('aria-label','Find an import');search.oninput=function(){filterText=search.value;renderList();};
    var filter=el('select',undefined,card);filter.className='queue-filter';filter.setAttribute('aria-label','Filter imports');
    [['all','All unfinished'],['attention','Needs attention'],['review','Ready to review'],['progress','In progress'],['completed','Completed and cached']].forEach(function(v){var o=el('option',v[1],filter);o.value=v[0];});filter.onchange=function(){filterState=filter.value;renderList();};
    var controls = el('div', undefined, card);controls.id='queueControls';
    controls.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;margin:12px 0';

    button('Stop importer safely', async function(){
      if(!confirm('Stop the importer after current work reaches a saved checkpoint? Imports will be kept for later. Recording downloads will be unavailable until you restart it.'))return;
      await flush();
      var response=await fetch('/api/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      var result=await response.json();if(!response.ok)throw new Error(result.error||'Could not stop importer');
      location.replace(URL.createObjectURL(new Blob(['<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Importer stopping</title><body style="background:#161b22;color:#eef2f7;font:18px system-ui;padding:24px;max-width:640px;margin:auto"><h1>Importer is stopping safely</h1><p>Current work will finish its saved checkpoint before the service stops. You can close this page.</p><p>Run JamRoom Importer.bat to return, then use Resume unfinished for queued songs.</p>'],{type:'text/html'})));
    }, controls);
    button('Resume unfinished', async function(){await request('/control', {resume:true}); await refresh();}, controls);
    button('Pause / continue queue', async function(){await request('/control', {pause:!paused}); await refresh();}, controls);
    list = el('div', undefined, card);list.id='queueList';
    message = el('div', '', card); message.id = 'queueMessage'; message.setAttribute('role','status');
    recovery = el('div', '', card);recovery.id='queueRecovery';
    el('p', 'You can close this page while work continues. After restarting the importer, use Resume unfinished. Pause lets the current stage finish; files are kept when a song is removed.', card).className = 'note';
    var bar = document.createElement('div'); bar.style.cssText = 'margin:10px 0;display:flex;gap:12px;flex-wrap:wrap;align-items:center';
    $('reviewCard').prepend(bar);
    saved = el('span', '', bar); saved.id = 'queueSaved'; saved.setAttribute('role','status');
    target = el('span', '', bar); target.id = 'queueTarget'; target.className = 'note';
    button('Use open REAPER project', async function(){
      await flush();
      var result = await request('/' + selected + '/target', {revision:detail.revision});
      detail.revision = result.revision; detail.target = result.target; renderDetail(detail);
    }, bar);
    button('Retry saving', flush, bar);
    button('Reload saved review', async function(){
      if(saving) {try {await saving;} catch(error){/* Keep the local draft until the choice below. */}}
      if(dirty && !confirm('Discard the unsaved edits in this browser and reload the saved review?')) return;
      dirty = false; clearTimeout(timer); await select(selected);
    }, bar);
    document.querySelectorAll('#reviewCard button').forEach(function(b){
      if(b.getAttribute('onclick') === 'doCancel()') b.textContent = 'Keep for later';
    });
    if(window.ImportWorkspace){ImportWorkspace.mountQueue(card);ImportWorkspace.tools(bar);}
    $('reviewCard').addEventListener('input', edited); $('reviewCard').addEventListener('change', edited);
    window.addEventListener('beforeunload', function(event){if(dirty || saving){event.preventDefault(); event.returnValue = '';}});
    rows = result.jobs; paused = result.paused; renderList();
    if(window.ImporterActivity)ImporterActivity.jobs(result);
    var prior = localStorage.getItem('jamroom-import-job');
    if(prior && rows.some(function(r){return r.id === prior;})) await select(prior);
    setInterval(function(){refresh().catch(function(e){if(window.ImporterActivity)ImporterActivity.notice('Import status unavailable','Connection lost; work may still be running. Reconnecting…',true);else failure(e);});}, 1500);
  }
  init().catch(function(error){
    var warning = $('staleWarn');
    warning.textContent = 'Saved import queue is unavailable: ' + error.message + '. Restart the importer and reload this page.';
    warning.classList.remove('hide');
  });
  return api;
})();
