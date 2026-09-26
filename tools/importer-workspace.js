/* Task navigation and bounded layout; queue/server journals own all job state. GPL-3.0. */
window.ImportWorkspace=(function(){
  const $=id=>document.getElementById(id), root=$('importWorkspace');
  let task='add',selected=null,tab='stems',queueScroll=0;
  function node(tag,id,parent){const n=document.createElement(tag);if(id)n.id=id;if(parent)parent.append(n);return n;}
  function button(label,fn,parent){const b=node('button',null,parent);b.type='button';b.textContent=label;b.onclick=fn;return b;}
  const header=node('header','workspaceHeader');document.body.insertBefore(header,$('activityBar'));
  const brand=node('div',null,header);brand.className='workspace-brand';brand.append(root.querySelector('h1'));
  const nav=node('nav',null,header);nav.setAttribute('aria-label','Importer navigation');
  button('Imports',()=>showQueue(),nav);button('Song library',()=>window.setSource('man'),nav);
  button('Exported recordings',()=>location.assign('/recordings'),nav);
  button('Settings',()=>show('settings'),nav);
  const connection=node('div','workspaceConnection');header.after(connection);connection.hidden=true;
  node('span',null,connection).textContent='Importer setup needs attention. ';
  button('Check setup',()=>show('settings'),connection);
  root.querySelector('.sub').remove();
  const side=node('aside','workspaceQueue',root);side.setAttribute('aria-label','Your imports');
  const main=node('section','workspaceMain',root);main.setAttribute('aria-label','Current task');
  const head=node('header','workspaceTaskHead',main);
  const back=button('Imports',showQueue,head);back.id='workspaceBack';
  const heading=node('div',null,head);node('h2','workspaceTitle',heading).textContent='Add songs';node('p','workspaceSubtitle',heading).textContent='Prepare another song while your queue keeps working.';
  const content=node('div','workspaceContent',main);
  const settings=node('section','workspaceSettings',content);settings.append($('checksCard'));
  const warning=$('staleWarn');header.after(warning);
  const sources=$('srcYt').closest('.card');sources.id='workspaceSources';$('srcMan').hidden=true;
  const add=node('section','workspaceAdd',content);add.append(sources,$('searchCard'),$('libCard'),$('confirmCard'));
  const library=$('manCard');content.append(library);const libNav=node('nav','workspaceLibraryNav');library.prepend(libNav);
  button('Browse songs',()=>{library.dataset.view='browse';$('workspaceUpdateFooter').hidden=true;},libNav);
  button('Update songs',()=>window.openUpdates(),libNav);
  const updates=$('updatesBox');updates.style.cssText='';
  const filters=node('div','workspaceUpdateFilters');updates.insertBefore(filters,$('updateSongs'));
  const filter=node('input','workspaceUpdateSearch',filters);filter.type='search';filter.placeholder='Find songs to update';filter.setAttribute('aria-label','Find songs to update');filter.oninput=()=>window.renderUpdateSongs();
  const eligibility=node('select','workspaceUpdateFilter',filters);eligibility.setAttribute('aria-label','Filter update songs');
  for(const [value,label] of [['all','All songs'],['eligible','Eligible'],['attention','Needs attention']]){const o=node('option',null,eligibility);o.value=value;o.textContent=label;}
  eligibility.onchange=()=>window.renderUpdateSongs();
  const options=node('details','workspaceUpdateOptions',updates);node('summary',null,options).textContent='Update options and restore';
  for(const id of ['replaceTiming','replaceLevels'])options.append($(id).closest('label'));
  for(const b of Array.from(updates.querySelectorAll('button'))){if(/Restore|Resume|Pause|whole library/.test(b.textContent))options.append(b);}
  const chooser=node('details','workspaceUpdateChooser');updates.insertBefore(chooser,filters);
  node('summary',null,chooser).textContent='Selection options';
  const choices=node('div',null,chooser);choices.append($('updateMode').closest('label'),$('updateScope'));
  for(const b of Array.from(updates.children))if(b.tagName==='BUTTON')choices.append(b);
  const compactChoices=matchMedia('(max-width:760px), (max-height:700px)');
  chooser.open=!compactChoices.matches;compactChoices.addEventListener('change',()=>chooser.open=!compactChoices.matches);
  const updateFoot=node('footer','workspaceUpdateFooter',updates);node('span','workspaceSelection',updateFoot);updateFoot.append($('updateStart'));updateFoot.hidden=true;
  const review=$('reviewCard');content.append(review);
  const reviewTools=node('details','workspaceReviewTools');node('summary',null,reviewTools).textContent='Review tools';
  const tabs=node('nav','workspaceReviewTabs');tabs.setAttribute('aria-label','Song review');
  const panes=node('div','workspaceReviewPanes');
  const stems=node('section','workspace-stems',panes),lyrics=node('section','workspace-lyrics',panes),chords=node('section','workspace-chords',panes);
  stems.dataset.reviewTab='stems';lyrics.dataset.reviewTab='retired';lyrics.hidden=true;lyrics.inert=true;chords.dataset.reviewTab='chart';
  let target=stems;const apply=$('applyBtn'),cancel=review.querySelector('button[onclick="doCancel()"]');
  for(const n of Array.from(review.children)){
    if(n===apply||n===cancel)continue;
    if(n.tagName==='H2'&&n.textContent.includes('Lyric'))target=lyrics;
    if(n.tagName==='H2'&&n.textContent.includes('Chord'))target=chords;
    target.append(n);
  }
  const footer=node('footer','workspaceReviewFooter');const save=node('div','workspaceSave',footer);footer.append(apply,cancel);
  for(const name of ['stems','chart']){const b=button(name[0].toUpperCase()+name.slice(1),()=>chooseTab(name),tabs);b.dataset.reviewTab=name;}
  review.replaceChildren(tabs,reviewTools,panes,footer);
  stems.querySelector('h2').hidden=true;
  const stemHelp=stems.querySelector('.note'),fullHelp=node('p',null,reviewTools);
  fullHelp.className='note';fullHelp.textContent=stemHelp.textContent;
  stemHelp.textContent='Preview each stem and choose its playback group.';
  const job=node('section','workspaceJob',content);node('h3','workspaceJobState',job);node('p','workspaceJobSummary',job);node('div','workspaceJobActions',job);
  const recoveryHost=node('div','workspaceRecovery',job);
  const jobFooter=node('footer','workspaceJobFooter',job);button('Review next ready song',()=>window.ImportJobs.nextReady(),jobFooter);
  button('View activity',()=>window.ImporterActivity.open(),jobFooter);
  for(const id of ['receiptCard','progressCard'])content.append($(id));
  const overlay=$('delOverlay');document.body.append(overlay);
  function show(next){
    task=next;root.dataset.task=next;root.dataset.pane='work';
    if(window.ImporterActivity)ImporterActivity.close();
    if(next==='add'){$('workspaceTitle').textContent='Add songs';$('workspaceSubtitle').textContent='Choose a source. Existing work stays in your import list.';}
    if(next==='library'){$('workspaceTitle').textContent='Song library';$('workspaceSubtitle').textContent='Browse, repair or update songs in this REAPER project.';}
    if(next==='settings'){$('workspaceTitle').textContent='Importer settings';$('workspaceSubtitle').textContent='Connection, setup and service controls.';}
    if(next==='review'||next==='job')renderJobHeader();
  }
  function showQueue(){
    if(window.ImporterActivity)ImporterActivity.close();root.dataset.pane='queue';side.scrollTop=queueScroll;
    if(selected&&task!=='review'&&task!=='job')show(selected.state==='review'?'review':'job');
    else if(!selected&&task!=='add')show('add');
    root.dataset.pane='queue';
  }
  function chooseTab(name){
    if(name==='lyrics'||name==='chords')name='chart';if(!['stems','chart'].includes(name))name='stems';
    document.querySelectorAll('audio').forEach(a=>a.pause());
    tab=name;if(selected)localStorage.setItem('jamroom-review-tab:'+selected.id,name);
    for(const p of panes.children)p.hidden=p.dataset.reviewTab!==name;
    for(const b of tabs.children)b.setAttribute('aria-pressed',String(b.dataset.reviewTab===name));
  }
  function renderJobHeader(){if(!selected)return;$('workspaceTitle').textContent=selected.song;$('workspaceSubtitle').textContent='Target: '+(selected.target||'Choose the open REAPER project when adding');}
  function clearJob(){selected=null;show('add');showQueue();}
  function updateJob(row,navigate){
    const changed=!selected||selected.id!==row.id;selected=row;
    if(changed)chooseTab(localStorage.getItem('jamroom-review-tab:'+row.id)||'stems');
    if(navigate){queueScroll=side.scrollTop;show(row.state==='review'?'review':'job');}
    else if(task==='review'||task==='job'){task=row.state==='review'?'review':'job';root.dataset.task=task;renderJobHeader();}
    $('workspaceJobState').textContent={done:'Added to REAPER',failed:'This import needs attention',interrupted:'Ready to resume',queued:'Waiting in the queue',preparing:'Preparing your song',applying:'Adding to REAPER',cached:'Saved source files available',paused:'Paused'}[row.state]||row.stage||row.state;
    $('workspaceJobSummary').textContent=row.summary||(row.state==='done'?'Save the REAPER project. You can review the next ready song.':'Work and review choices are saved. Open Activity for detailed progress.');
    tabs.children[0].textContent='Stems'+(row.review?' ('+row.review.stems.length+')':'');
    tabs.children[1].textContent='Chart';
  }
  function compactStems(){
    for(const row of $('stemList').children){
      if(row.querySelector('.stem-preview-body'))continue;
      const preview=node('button');preview.type='button';preview.textContent='Hide preview';preview.className='stem-preview';preview.setAttribute('aria-expanded','true');
      const body=node('div');body.className='stem-preview-body';body.hidden=false;
      for(const child of Array.from(row.children))if(!child.matches('.stemname,select'))body.append(child);
      row.append(preview,body);
      preview.onclick=()=>{body.hidden=!body.hidden;preview.setAttribute('aria-expanded',String(!body.hidden));preview.textContent=body.hidden?'Show preview':'Hide preview';};
    }
  }
  function mountQueue(card){side.append(card);const controls=$('queueControls');if(controls)settings.append(controls);if($('queueRecovery'))recoveryHost.append($('queueRecovery'));if($('queueMessage'))content.before($('queueMessage'));}
  function tools(bar){reviewTools.append(bar);for(const id of ['queueSaved','queueTarget'])if($(id))save.append($(id));}
  function updated(){library.dataset.view='updates';updateFoot.hidden=false;show('library');}
  function selection(){const n=window.updateSongs?.filter(s=>window.updateSelection[s.id]&&($('updateScope').value==='all'||!window.updateScopeIds||window.updateScopeIds.includes(s.id))).length||0;$('workspaceSelection').textContent=n+' selected / '+({both:'Charts, click & levels',convert:'Convert chart display',levels:'Volume matching',clicks:'Click tracks'}[$('updateMode').value])+($('replaceTiming').checked?' / Replace edits':'')+($('replaceLevels').checked?' / Replace manual levels':'');if(!window.updateLoading&&!window.updateStarting)$('updateStart').textContent='Update '+n+' selected songs';}
  chooseTab('stems');show(window.g_source==='man'?'library':'add');
  if(!$('updatesBox').classList.contains('hide'))updated();
  function checks(c){connection.hidden=!!c&&!['ytdlp','ffmpeg','key','reaper'].some(k=>c[k]===false);}
  return {show,showQueue,clearJob,checks,job:updateJob,compactStems,mountQueue,tools,updated,selection,source:s=>show(s==='man'?'library':'add'),tab:chooseTab};
})();
