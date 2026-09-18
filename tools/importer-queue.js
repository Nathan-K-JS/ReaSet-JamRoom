/* Persistent import workspaces. Vanilla browser UI; GPL v3. */
window.ImportJobs = (function(){
  'use strict';
  var api = {enabled:false}, selected = null, detail = null, rows = [], paused = false;
  var dirty = false, timer = null, saving = null, version = 0, selection = 0, busy = false, polling = false;
  var rendered = '', listSignature = '', card, list, message, saved, target;
  function el(tag, text, parent){
    var node = document.createElement(tag);
    if(text !== undefined) node.textContent = text;
    if(parent) parent.appendChild(node);
    return node;
  }
  function button(text, action, parent){
    var node = el('button', text, parent); node.className = 'small';
    node.onclick = function(){ Promise.resolve().then(action).catch(failure); };
    return node;
  }
  function failure(error){
    message.textContent = error.message || String(error);
    message.style.color = '#ffb3a7';
  }
  async function request(path, body){
    var response = await fetch('/api/jobs' + path, body === undefined ? {} : {
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
    if(!selected || !detail || detail.state !== 'review' || busy) return;
    dirty = true; version++; saved.textContent = 'Saving...';
    clearTimeout(timer); timer = setTimeout(function(){flush().catch(failure);}, 400);
  }
  function renderDetail(row){
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
  }
  async function select(id){
    if(busy) throw new Error('Let the current review change finish first.');
    await flush();
    var generation = ++selection;
    busy = true; $('reviewCard').inert = true;
    var row;
    try {row = await request('/' + id);}
    finally {busy = false; $('reviewCard').inert = false;}
    if(generation !== selection) return;
    stopPolling(); dismissReceipt(); resetReviewPanel();
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
    interrupted:'Resume available', paused:'Paused', cached:'Cached song', editing:'Updating review'};
  function renderList(){
    var signature = JSON.stringify([rows, selected, paused]);
    if(signature === listSignature) return;
    listSignature = signature;
    var expanded = list.querySelector('details') && list.querySelector('details').open;
    list.replaceChildren();
    var active = rows.filter(function(r){return r.state !== 'done' && r.state !== 'cached';});
    var ready = active.filter(function(r){return r.state === 'review';}).length;
    $('queueCounts').textContent = active.length + ' unfinished · ' + ready + ' ready to review' + (paused ? ' · Queue paused' : '');
    function draw(row, parent){
      var line = el('div', undefined, parent);
      line.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 0;border-bottom:1px solid #ffffff18';
      var open = button(row.song, function(){return select(row.id);}, line);
      open.style.flex = '1'; open.style.textAlign = 'left';
      if(selected === row.id) open.style.outline = '2px solid #70cbbb';
      el('span', names[row.state] || row.state, line).className = 'note';
      if(['failed','paused','interrupted','cached'].includes(row.state)){
        button(row.apply_started ? 'Check Apply' : 'Resume / open', async function(){
          await select(row.id);
          if(row.apply_started){ await api.apply(); return; }
          await request('/' + row.id + '/resume', {}); await refresh();
        }, line);
      }
      if(row.state === 'done') button('Review / re-add', async function(){
        await select(row.id); await request('/' + row.id + '/reopen', {revision:detail.revision});
        await refresh();
      }, line);
      if(!['preparing','applying','editing'].includes(row.state)) button('Remove', async function(){
        if(row.id === selected) await close();
        await request('/' + row.id + '/remove', {}); await refresh();
      }, line);
    }
    active.forEach(function(row){draw(row, list);});
    var rest = rows.filter(function(r){return r.state === 'done' || r.state === 'cached';});
    if(rest.length){
      var other = el('details', undefined, list);
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
      var result = await request('', body);
      $('confirmCard').classList.add('hide');
      await refresh(); await select(result.id);
    } catch(error){failure(error);}
    finally {$('importBtn').disabled = false; setPipelineActive(false);}
  };
  api.cached = async function(name){
    try {
      var row = rows.find(function(r){return r.song === name;});
      if(!row) throw new Error('Reopen the importer to discover this cached song.');
      await select(row.id);
      if(row.state === 'cached') {await request('/' + row.id + '/resume', {}); await refresh();}
    } catch(error){failure(error);}
  };
  api.apply = async function(){
    try {
      if(busy || !selected) return;
      // Save the initial default choices too, even when no control was edited.
      if(detail.state === 'review'){dirty = true; version++; await flush();}
      await request('/' + selected + '/apply', {revision:detail.revision});
      rendered = ''; await refresh();
    } catch(error){failure(error);}
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
  api.close = function(){return close().catch(failure);};
  api.source = async function(source){
    try {await close(); setSource(source, true);} catch(error){failure(error);}
  };
  async function init(){
    var result = await request('');
    if(result.schema !== 1) return; // Old-server/browser test compatibility.
    api.enabled = true; stopPolling(); setPipelineActive(false);
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
    document.querySelectorAll('#reviewCard button').forEach(function(b){
      if(b.getAttribute('onclick') === 'doCancel()') b.textContent = 'Close review — keep for later';
    });
    $('reviewCard').addEventListener('input', edited); $('reviewCard').addEventListener('change', edited);
    window.addEventListener('beforeunload', function(event){if(dirty || saving){event.preventDefault(); event.returnValue = '';}});
    rows = result.jobs; paused = result.paused; renderList();
    var prior = localStorage.getItem('jamroom-import-job');
    if(prior && rows.some(function(r){return r.id === prior;})) await select(prior);
    setInterval(function(){refresh().catch(failure);}, 1500);
  }
  init().catch(function(error){
    var warning = $('staleWarn');
    warning.textContent = 'Saved import queue is unavailable: ' + error.message + '. Restart the importer and reload this page.';
    warning.classList.remove('hide');
  });
  return api;
})();
