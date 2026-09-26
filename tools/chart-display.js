/* Shared section model and readable chart display. Embedded for offline REAPER use. GPL-3.0. */
(function(global){
'use strict';
const copy=x=>JSON.parse(JSON.stringify(x)), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const states=new WeakMap();
function convert(input){
 const doc=copy(input),original=copy(input); if(!doc.sections?.length)return doc;
 if(doc.schema===3)return doc;
 const output=[];
 try{
  for(const [si,s] of doc.sections.entries()){
   let part={...s,rows:[]},last=s.start;output.push(part);
   for(const [ri,row] of (s.rows||[]).entries()){
    const width=Math.max((row.text||'').length,(row.chord_line||'').length,...(row.anchors||[]).map(a=>a.offset+a.symbol.length));
    const cues=Object.entries(row.page_cues||{}).map(([c,t])=>[Number(c),t]).sort((a,b)=>a[0]-b[0]);
    let from=0;
    function slice(end){
     if(end<=from)return;
     const r=copy(row);r.id=(row.id||'legacy-'+si+'-'+ri)+(from?'-col-'+from:'');r.source_row=row.id;
     r.text=(row.text||'').slice(from,end);r.chord_line=(row.chord_line||'').slice(from,end);
     r.anchors=(row.anchors||[]).filter(a=>a.offset>=from&&a.offset<end).map(a=>({...a,offset:a.offset-from}));
     delete r.page_cues;if(from){delete r.cue;delete r.timing_evidence;}
     part.rows.push(r);from=end;
    }
    for(const [col,t] of cues){
     if(!Number.isInteger(col)||col<0||col>=Math.max(1,width)||!Number.isFinite(t)||t<last||t>=s.end)throw Error('A saved page cue conflicts with its section.');
     if((row.anchors||[]).some(a=>a.offset<col&&a.offset+(a.width||a.symbol.length)>col)||col>0&&/\S/.test((row.text||'')[col-1]||'')&&/\S/.test((row.text||'')[col]||''))throw Error('A saved page cue cuts through a word or chord.');
     slice(col);
     if(t===last){if(part.rows.length||col)throw Error('Saved page cues share a time.');continue;}
     part.end=t;part={...s,id:(s.id||'legacy-'+si)+'-cue-'+ri+'-'+col,label:s.label+' - continued',start:t,rows:[],timing_status:'checked',confidence:'section checked'};output.push(part);last=t;
    }
    if(width)slice(width);else{const r=copy(row);delete r.page_cues;part.rows.push(r);}
   }
  }
  if(output[0].start>0)output.unshift({id:'legacy-opening',label:'Intro',start:0,end:output[0].start,rows:[],kind:'instrumental',timing_status:'estimated'});
  doc.schema=3;doc.sections=output;doc.migration_snapshot=original;
  return doc;
 }catch(e){original.migration_issue=e.message;return original;}
}
function pages(doc,width,height,mode,semis,scroll=false,fontPreference){
 const preferred=fontPreference|| (width>=1100?32:28);
 return doc.sections.map((s,i)=>{
  function layout(size){const cols=Math.max(12,Math.floor(Math.max(80,width-48)/(size*.61)));return (s.rows||[]).flatMap((r,ri)=>global.chartFragments(r,cols,mode,i,ri,semis));}
  function cost(parts,size){return parts.reduce((n,f)=>n+((f.hasWords?1.35:0)+(f.hasChords?1.2:0)+.45)*size,0);}
  let font=preferred,parts=layout(font),available=Math.max(60,height-64);
  if(!scroll)while(font>18&&cost(parts,font)>available){font--;parts=layout(font);}
  return {section:i,part:0,total:1,font,parts,cue:s.start,checked:s.timing_status==='checked',overflow:cost(parts,font)>available};
 });
}
function lines(parts){return parts.map(f=>'<div class="uc-line" data-row="'+esc(f.row)+'" data-column="'+f.column+'">'+(f.hasChords?'<div class="uc-chords"><span>'+esc(f.decorations)+'</span>'+f.anchors.map(a=>'<b style="left:'+a.offset+'ch">'+esc(a.symbol)+'</b>').join('')+'</div>':'')+(f.hasWords?'<div class="uc-words">'+esc(f.text||' ')+'</div>':'')+'</div>').join('');}
function readPreference(key,fallback){try{return localStorage.getItem(key)||fallback;}catch(e){return fallback;}}
function preference(key,value){try{localStorage.setItem(key,value);}catch(e){}}
function render(host,options){
 let state=states.get(host);
 if(state&&!host.contains(state.body)){dispose(host);state=null;}
 if(!state){
  state={follow:true,index:0,font:Number(readPreference('reaset-chart-font','28')),view:readPreference('reaset-chart-layout','scroll'),mode:readPreference('reaset-chart-words','both')};states.set(host,state);
  host.classList.add('uc-host');
  host.innerHTML='<div class="uc-song"></div><div class="uc-toolbar"><div class="uc-toggle"><button data-view="scroll">Scroll</button><button data-view="pages">Pages</button></div><label><input type="checkbox" class="uc-chords-toggle" checked> Show chords</label><button data-action="smaller" aria-label="Smaller chart text">A−</button><button data-action="larger" aria-label="Larger chart text">A+</button><button data-action="edit">Edit chart</button><button data-action="timing">Timing</button></div><div class="uc-navigation"><button data-action="previous">Previous</button><select class="uc-select" aria-label="Chart section"></select><button data-action="next">Next</button><button class="uc-follow" data-action="follow">Following</button></div><div class="uc-scroll" tabindex="0" aria-label="Song chart"></div><div class="uc-status" role="status"></div>';
  state.body=host.querySelector('.uc-scroll');
  const rerender=()=>render(host,state.options);
  host.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{state.view=b.dataset.view;preference('reaset-chart-layout',state.view);state.key='';rerender();});
  host.querySelector('.uc-chords-toggle').onchange=e=>{state.mode=e.target.checked?'both':'lyrics';preference('reaset-chart-words',state.mode);state.key='';state.options.onMode?.(state.mode);rerender();};
  function browse(i){state.follow=false;state.index=Math.max(0,Math.min(state.doc.sections.length-1,i));state.jump=true;rerender();}
  host.querySelector('.uc-select').onchange=e=>browse(Number(e.target.value));
  host.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>{
   const a=b.dataset.action;
   if(a==='previous'||a==='next')return browse(state.index+(a==='next'?1:-1));
   if(a==='edit')return state.options.edit?.();if(a==='timing')return state.options.timing?.();
   if(a==='follow'){state.follow=true;state.jump=true;}
   if(a==='smaller'||a==='larger'){state.font=Math.max(18,Math.min(42,state.font+(a==='larger'?2:-2)));preference('reaset-chart-font',String(state.font));state.key='';}
   rerender();
  });
  function manual(){if(state.follow){state.follow=false;host.querySelector('.uc-follow').textContent='Resume following';}}
  state.body.addEventListener('wheel',manual,{passive:true});state.body.addEventListener('touchstart',manual,{passive:true});
  state.body.addEventListener('pointerdown',manual);
  state.body.addEventListener('keydown',e=>{if(['ArrowUp','ArrowDown','PageUp','PageDown','Home','End',' '].includes(e.key))manual();});
  state.body.addEventListener('scroll',()=>{if(!state.follow&&state.view==='scroll'){const entries=state.body.querySelectorAll('.uc-section');for(let i=0;i<entries.length;i++)if(entries[i].offsetTop-state.body.offsetTop<=state.body.scrollTop+state.body.clientHeight*.3)state.index=i;host.querySelector('.uc-select').value=state.index;}},{passive:true});
  state.observer=new ResizeObserver(()=>{if(host.isConnected)rerender();});state.observer.observe(host);
 }
 state.options=options;
 const source=options.document;if(state.source!==source||state.revision!==source.revision){if(state.revision!==source.revision)state.key='';state.source=source;state.revision=source.revision;state.doc=convert(source);}
 const doc=state.doc;
 if(options.song!==state.song){state.song=options.song;state.follow=true;state.jump=true;state.key='';}
 if(options.mode&&options.mode!==state.externalMode){state.mode=options.mode;state.externalMode=options.mode;state.key='';}
 if(options.browse!==undefined&&options.browse!==state.browse){state.browse=options.browse;if(options.browse!==null){state.follow=false;state.index=options.browse;state.jump=true;}else state.follow=true;}
 let active=0;const pos=(options.position||0)-(doc.timing_offset||0);
 doc.sections.forEach((s,i)=>{if(Number.isFinite(s.start)&&pos>=s.start)active=i;});
 if(state.follow)state.index=active;
 state.index=Math.max(0,Math.min(state.index,doc.sections.length-1));
 const width=state.body.clientWidth||host.clientWidth||800,height=state.body.clientHeight||400;
 const key=[doc.revision,doc.sections.length,width,height,state.view,state.mode,options.semis||0,state.font,state.view==='pages'?state.index:''].join('|');
 if(key!==state.key){
  const oldTop=state.body.scrollTop,oldHeight=state.body.scrollHeight,bodyTop=state.body.getBoundingClientRect().top;
  const anchor=Array.from(state.body.querySelectorAll('.uc-line')).find(el=>el.getBoundingClientRect().bottom>bodyTop);
  const location=anchor?{row:anchor.dataset.row,column:Number(anchor.dataset.column),offset:anchor.getBoundingClientRect().top-bodyTop}:null;state.key=key;
  state.pages=pages(doc,width,height,state.mode,options.semis||0,state.view==='scroll',state.font);
  const display=state.view==='scroll'?state.pages:[state.pages[state.index]];
  state.body.innerHTML=display.map(p=>'<section class="uc-section" data-section="'+p.section+'" style="font-size:'+p.font+'px"><h3>'+esc(doc.sections[p.section].label)+'</h3>'+lines(p.parts)+(p.parts.length?'':'<p class="uc-empty">Instrumental</p>')+'</section>').join('');
  // Measure the real DOM after chrome, wrapping and browser font metrics.
  // Keep one section; a section that cannot fit at 18px remains scrollable.
  if(state.view==='pages'){
   const p=state.pages[state.index],element=state.body.querySelector('.uc-section');
   while(p.font>18&&state.body.scrollHeight>state.body.clientHeight+1){
    p.font--;const replacement=pages(doc,width,height,state.mode,options.semis||0,true,p.font)[state.index];p.parts=replacement.parts;
    element.style.fontSize=p.font+'px';element.innerHTML='<h3>'+esc(doc.sections[p.section].label)+'</h3>'+lines(p.parts)+(p.parts.length?'':'<p class="uc-empty">Instrumental</p>');
   }
   p.overflow=state.body.scrollHeight>state.body.clientHeight+1;
  }
  state.body.scrollTop=state.view==='pages'?0:oldTop/Math.max(1,oldHeight)*state.body.scrollHeight;
  if(location&&state.view==='scroll'&&!state.follow){
   const candidates=Array.from(state.body.querySelectorAll('.uc-line')).filter(el=>el.dataset.row===location.row);
   const same=candidates.filter(el=>Number(el.dataset.column)<=location.column).pop()||candidates[0];
   if(same)state.body.scrollTop+=same.getBoundingClientRect().top-state.body.getBoundingClientRect().top-location.offset;
  }
  host.querySelector('.uc-select').innerHTML=doc.sections.map((s,i)=>'<option value="'+i+'">'+esc(s.label)+'</option>').join('');
 }
 host.querySelector('.uc-song').textContent=options.title||'';host.querySelector('.uc-song').hidden=!options.title;
 host.querySelector('.uc-select').value=state.index;
 host.querySelector('.uc-follow').textContent=state.follow?'Following':'Resume following';
 host.querySelector('.uc-chords-toggle').checked=state.mode!=='lyrics';
 host.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===state.view)));
 host.querySelector('[data-action="edit"]').hidden=!options.edit;host.querySelector('[data-action="timing"]').hidden=!options.timing;
 host.querySelector('[data-action="previous"]').disabled=state.index===0;host.querySelector('[data-action="next"]').disabled=state.index===doc.sections.length-1;
 const section=state.body.querySelector('[data-section="'+state.index+'"]');
 state.body.querySelectorAll('.uc-section').forEach(el=>el.classList.toggle('uc-active',Number(el.dataset.section)===active));
 if(section&&state.view==='scroll'&&(state.follow||state.jump)){
  const s=doc.sections[state.index],top=section.offsetTop-state.body.offsetTop;
  const interval=s.end-s.start,excess=Math.max(0,section.offsetHeight-height*.65);
  const progress=interval>2?Math.max(0,Math.min(1,(pos-s.start)/interval)):0;
  const target=Math.max(0,top-height*.18+(state.follow?excess*progress:0));
  if(state.jump||state.active!==active||Math.abs(pos-(state.pos??pos))>3)state.body.scrollTop=target;
  else if(state.follow&&options.playing&&options.connected!==false&&Math.abs(target-state.body.scrollTop)>10)state.body.scrollTop+=(target-state.body.scrollTop)*.18;
 }
 state.jump=false;state.active=active;state.pos=pos;
 host.querySelector('.uc-status').textContent=options.connected===false?'Disconnected — chart remains available':options.message|| (doc.migration_issue?'Saved legacy timing retained. Open Edit chart to resolve conflicting cues.':state.view==='pages'&&state.pages[state.index].overflow?'This section is scrollable. Use Scroll view or split it in Edit chart.':'');
 return state;
}
function setMode(host,mode){preference('reaset-chart-words',mode);const state=states.get(host);if(state){state.mode=mode;state.key='';render(host,state.options);}}
function follow(host){const state=states.get(host);if(state){state.follow=true;state.jump=true;render(host,state.options);}}
function dispose(host){const state=states.get(host);state?.observer.disconnect();states.delete(host);}
const css=`.uc-host{display:flex!important;flex-direction:column;min-height:0;overflow:hidden!important;text-align:left}.uc-toolbar,.uc-navigation{display:flex;gap:8px;align-items:center;flex-wrap:wrap;flex-shrink:0;padding:8px 12px}.uc-toolbar{border-bottom:1px solid #33485e}.uc-toggle{display:flex;gap:2px}.uc-toolbar button,.uc-navigation button,.uc-select{font:14px system-ui;color:#e8eef6;background:#233346;border:1px solid #4a6075;border-radius:8px;padding:8px 12px;min-height:38px;cursor:pointer;width:auto;margin:0}.uc-toolbar button[aria-pressed=true]{background:#285c57;border-color:#83cbbb}.uc-toolbar label{display:flex;gap:6px;align-items:center;font:14px system-ui}.uc-toolbar input{width:auto}.uc-navigation .uc-select{flex:1;min-width:100px;max-width:420px}.uc-follow{margin-left:auto!important;border-color:#78b7aa!important}.uc-scroll{position:relative;flex:1;min-height:0;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:stable;padding:12px 24px 40px;background:#101923;border-radius:10px;scroll-behavior:auto}.uc-section{position:relative;padding:16px 12px 28px;margin-bottom:24px;border-left:3px solid transparent}.uc-section.uc-active{border-left-color:#79bca8;background:#182731}.uc-section h3{font:600 18px system-ui;color:#accfc5;margin:0 0 20px}.uc-line{font-family:Consolas,monospace;white-space:pre;position:relative;margin-bottom:.45em;letter-spacing:0}.uc-chords{height:1.2em;position:relative;color:#edc278;line-height:1.2}.uc-chords b{position:absolute;top:0;font-weight:normal}.uc-words{line-height:1.35;color:#eaf0f5}.uc-empty{font:18px system-ui;color:#a5b6c6}.uc-status{font:12px system-ui;color:#a9bccb;padding:4px 12px;min-height:22px;flex-shrink:0}.uc-host button:disabled{opacity:.4}.uc-host button:focus-visible,.uc-scroll:focus-visible{outline:2px solid #edc278}@media(max-width:800px){.uc-scroll{padding:8px 8px 24px}.uc-toolbar,.uc-navigation{gap:5px;padding:6px}.uc-toolbar button,.uc-navigation button,.uc-select{padding:6px 9px}}`;
const refinements=`@media(max-height:500px){.uc-song{display:none}.uc-scroll{padding:4px}.uc-section{padding:4px 8px 16px}.uc-section h3{margin:0 0 8px}.uc-toolbar,.uc-navigation{padding:4px;gap:4px}}.uc-song{font:600 17px system-ui;color:#bbd1db;padding:4px 40px 4px 12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0}#chords-live.structured-chart.uc-host,#lyrics-live.structured-chart.uc-host{display:flex!important;gap:0;min-height:0!important;overflow:hidden!important}.source-chart:has(.uc-host)>.cv-tabs{display:none}.ca-main .uc-toolbar label{flex-direction:row;align-items:center}.ca-main .uc-toolbar input{min-height:0!important;padding:0!important}.uc-host [hidden]{display:none!important}`;
if(!document.getElementById('chart-display-style')){const style=document.createElement('style');style.id='chart-display-style';style.textContent=css+refinements;document.head.appendChild(style);}
global.ChartDisplay={convert,pages,lines,render,dispose,setMode,follow};
})(window);
