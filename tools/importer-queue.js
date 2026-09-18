/* Persistent import workspaces. Vanilla browser UI; GPL v3. */
window.ImportJobs = (function(){
  'use strict';
  var api = {enabled:false}, selected = null, detail = null, rows = [], paused = false;
  var dirty = false, timer = null, saving = null, version = 0, selection = 0, busy = false, polling = false;
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
    document.querySelectorAll('#stemList select').forEach(function(node){value.slots[node.dataset.file] = node.value;});
    document.querySelectorAll('#stemList input.lbl').forEach(function(node){value.labels[node.dataset.file] = node.value.trim();});
    var offset = parseFloat($('lyrOffset').value);
    value.lyrics_offset = Number.isFinite(offset) ? offset : null;
    ['lyrQuery','ugQuery','ugUrl'].forEach(function(id){value.fields[id] = $(id).value;});
    return value;
  }
  function restoreDraft(value){
    value = value || {};
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
    if(row.summary) message.textContent = row.summary;
    if(row.state === 'review' && row.review && rendered !== row.id + ':review'){
      showReview(row.review); restoreDraft(row.draft);
      rendered = row.id + ':review'; saved.textContent = 'Saved';
    } else if(row.state !== 'review'){
      resetReviewPanel(); rendered = row.id + ':' + row.state;
    }
    $('applyBtn').disabled = row.state !== 'review' || busy;
    $('applyBtn').textContent = row.apply_started ? 'Check / retry Apply' : 'Apply to REAPER';
    document.querySelectorAll('#reviewCard input,#reviewCard select').forEach(function(node){node.disabled = !!row.apply_started;});
  }
  async function select(id){
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
    selected = id; detail = row; rendered = ''; dirty = false;
    localStorage.setItem('jamroom-import-job', id);
    message.textContent = ''; renderDetail(row); renderList();
    if(row.state === 'cached') message.textContent = 'Cached song: press Resume / open to prepare its review. Existing completed stages are reused.';
  }
  async function close(){
    if(busy) throw new Error('Let the current review change finish first.');
    await flush(); selection++; selected = null; detail = null; rendered = '';
    localStorage.removeItem('jamroom-import-job');
    resetReadyState(); target.textContent = ''; saved.textContent = '';
    message.textContent = 'Work is kept in the song list. Add another song whenever you like.';
    setPipelineActive(false); renderList();
  }
  var names = {queued:'Queued', preparing:'Processing', review:'Ready to review',
    applying:'Adding to REAPER', done:'Added — save REAPER', failed:'Needs attention',
    interrupted:'Resume available', paused:'Paused', cached:'Cached song', editing:'Updating review', checking:'Checking Fadr'};
  function renderList(){
    var signature = JSON.stringify([rows, selected, paused]);
    if(signature === listSignature) return;
    listSignature = signature;
    var completed = list.querySelector('details[data-completed]');
    var expanded = completed && completed.open;
    var openMenus = new Set(Array.from(list.querySelectorAll('details[data-song]')).filter(function(n){return n.open;}).map(function(n){return n.dataset.song;}));
    list.replaceChildren();
    var active = rows.filter(function(r){return r.state !== 'done' && r.state !== 'cached';});
    var ready = active.filter(function(r){return r.state === 'review';}).length;
    $('queueCounts').textContent = active.length + ' unfinished · ' + ready + ' ready to review' + (paused ? ' · Queue paused' : '');
    function draw(row, parent){
      var line = el('div', undefined, parent);
      line.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 0;border-bottom:1px solid #ffffff18';
      var name=el('strong',row.song,line);name.style.cssText='flex:1;min-width:140px;overflow-wrap:anywhere';
      var open = button('Open', async function(){await select(row.id);if(row.state==='review')$('reviewCard').scrollIntoView({block:'start'});}, line);
      open.setAttribute('aria-label','Open '+row.song);
      open.style.background='#207d59';
      if(selected === row.id) open.style.outline = '2px solid #70cbbb';
      el('span', names[row.state] || row.state, line).className = 'note';
      if(['failed','paused','interrupted','cached'].includes(row.state)){
        button(row.apply_started ? 'Check Apply' : 'Resume / open', async function(){
          await select(row.id);
          if(row.apply_started){ await api.apply(); return; }
          await request('/' + row.id + '/resume', {}); await refresh();
        }, line);
        if(row.state!=='cached' && !row.apply_started)button('Check Fadr / recover', function(){return provider(row.id);}, line);
      }
      if(row.state === 'queued'){
        button('Move first', async function(){await request('/' + row.id + '/first', {}); await refresh();}, line);
        button('Pause', async function(){await request('/' + row.id + '/pause', {}); await refresh();}, line);
      }
      if(row.state === 'done') button('Review / re-add', async function(){
        await select(row.id); await request('/' + row.id + '/reopen', {revision:detail.revision});
        await refresh();
      }, line);
      if(!['preparing','applying','editing','checking'].includes(row.state)) {
        var more=el('details',undefined,line);more.dataset.song=row.id;more.open=openMenus.has(row.id);el('summary','More',more).style.cssText='cursor:pointer;padding:12px';
        button('Remove from queue', async function(){
        if(!confirm('Remove '+row.song+' from the queue? Downloaded files and saved review choices are kept. You can reopen it later.'))return;
        if(row.id === selected) await close();
        await request('/' + row.id + '/remove', {}); await refresh();
      }, more);
      }
    }
    active.forEach(function(row){draw(row, list);});
    var rest = rows.filter(function(r){return r.state === 'done' || r.state === 'cached';});
    if(rest.length){
      var other = el('details', undefined, list);
      other.dataset.completed='1';
      other.open = !!expanded;
      el('summary', 'Completed and cached songs (' + rest.length + ')', other);
      rest.forEach(function(row){draw(row, other);});
    }
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
        if(detail.state==='review')$('reviewCard').scrollIntoView({block:'start'});
        else if(window.ImporterActivity)ImporterActivity.open();
      }
      else message.textContent = body.band + ' - ' + body.title + ' is in your import list. Your current review is still open.';
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
      await request('/' + selected + '/apply', {revision:detail.revision});
      rendered = ''; busy=false; await refresh();
    } catch(error){failure(error);}
    finally{busy=false; $('applyBtn').disabled=!detail||detail.state!=='review';}
  };
  api.choose = async function(action, body, btn){
    try {
      if(busy) return;
      await flush(); busy = true; btn.disabled = true;
      var result = await request('/' + selected + '/' + action, Object.assign({}, body, {revision:detail.revision}));
      detail.revision = result.revision; detail.review = result.review;
      showReview(result.review); restoreDraft(detail.draft);
      saved.textContent = 'Saved';
    } catch(error){failure(error);}
    finally {busy = false; btn.disabled = false;}
  };
  api.open = select;
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
    try {await close(); setSource(source, true);} catch(error){failure(error);}
  };
  async function init(){
    var result = await request('');
    if(result.schema !== 1) return; // Old-server/browser test compatibility.
    api.enabled = true; setPipelineActive(false);
    card = document.createElement('div'); card.className = 'card'; card.id = 'importQueue';
    $('checksCard').after(card);
    el('h2', 'Your imports', card); el('div', '', card).id = 'queueCounts';
    var controls = el('div', undefined, card);
    controls.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;margin:12px 0';
    button('Add song', async function(){await close(); setSource('yt', true); $('searchCard').scrollIntoView({behavior:'smooth'});}, controls);
    button('Resume unfinished', async function(){await request('/control', {resume:true}); await refresh();}, controls);
    button('Pause / continue queue', async function(){await request('/control', {pause:!paused}); await refresh();}, controls);
    list = el('div', undefined, card);
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
      if(b.getAttribute('onclick') === 'doCancel()') b.textContent = 'Close review — keep for later';
    });
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
