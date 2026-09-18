-- Runs ONLY in the service's isolated Dummy Audio REAPER instance. GPL-3.0.
-- Wrapper supplies LISTEN_FOLDER, LISTEN_RESOURCE and LISTEN_ROOT.
local folder,root=LISTEN_FOLDER,LISTEN_ROOT
local J=dofile(root..'/Requirements/ReaSet_JSON.lua')
local P=dofile(root..'/Requirements/ReaSet_Playback.lua')
local copy=dofile(root..'/Requirements/ReaSet_MediaCopy.lua')
local guard=dofile(root..'/Requirements/ReaSet_ListeningSafety.lua')
local function read(path)local f=assert(io.open(path,'rb'));local s=f:read('*a');f:close();return s end
local function write(path,data)local f=assert(io.open(path..'.new','wb'));assert(f:write(J.encode(data)));assert(f:close());os.remove(path);assert(os.rename(path..'.new',path))end
local ok,why=xpcall(function()
  assert(reaper.GetResourcePath():gsub('\\','/'):lower()==LISTEN_RESOURCE:lower(),'Worker resource isolation failed')
  local yes,device=reaper.GetAudioDeviceInfo('MODE');assert(yes and device=='Dummy Audio','Worker must use Dummy Audio')
  local request=J.decode(read(folder..'/request.json'))
  assert(request.version==1 and request.duration>0 and request.rate>0,'Invalid listening request')
  local renderProject=folder..'/Listening.RPP'
  local cached=io.open(renderProject,'rb')
  if cached then cached:close();reaper.Main_openProject('noprompt:'..renderProject)
  else
    reaper.Main_openProject('noprompt:'..folder..'/source.RPP')
    local rows={};local recording={};local originals={}
    local master=reaper.GetMasterTrack(0)
    guard(master)
    local function row(it,tr,name,gain,unmute)
      guard(tr)
      assert(reaper.CountTakes(it)==1,'Layered REAPER items need a manual mix')
      local tk=reaper.GetActiveTake(it)
      assert(tk and not reaper.TakeIsMIDI(tk) and reaper.TakeFX_GetCount(tk)==0,'Custom take processing needs a manual mix')
      local source=reaper.GetMediaItemTake_Source(tk)
      assert(not reaper.GetMediaSourceParent(source),'Section/reversed sources need a manual mix')
      local file=reaper.GetMediaSourceFileName(source,'');assert(file~='','Source media is missing')
      local _,guid=reaper.GetSetMediaItemTakeInfo_String(tk,'GUID','',false)
      if not unmute and request.pitches[guid] then reaper.SetMediaItemTakeInfo_Value(tk,'D_PITCH',request.pitches[guid])end
      local good,chunk=reaper.GetItemStateChunk(it,'',false);assert(good)
      rows[#rows+1]={chunk=chunk,file=file,name=name,gain=gain,unmute=unmute}
    end
    for i=0,reaper.CountTracks(0)-1 do
      local tr=reaper.GetTrack(0,i);local _,id=reaper.GetSetMediaTrackInfo_String(tr,'P_EXT:ReaSetRec','',false)
      if id~='' then recording[id]=tr end
    end
    for _,r in ipairs(P.items(request.song,false))do
      local _,guid=reaper.GetSetMediaItemInfo_String(r.item,'GUID','',false);originals[guid]=r
    end
    if request.backing then
      if request.liveStems then
        local included={}
        for _,r in ipairs(request.stems)do
          local old=assert(originals[r.guid],'Backing changed since recording; export and mix in REAPER')
          assert(reaper.SetItemStateChunk(old.item,r.chunk,false))
          reaper.SetMediaItemInfo_Value(old.item,'B_MUTE',r.muted)
          included[r.guid]=old
        end
        originals=included
      end
      for _,r in pairs(originals)do
        if not request.stemMutes[r.slot] then
          local muted=false;local tr=r.track
          while tr and not request.liveStems do muted=muted or reaper.GetMediaTrackInfo_Value(tr,'B_MUTE')~=0;tr=reaper.GetParentTrack(tr)end
          if not muted and reaper.GetMediaItemInfo_Value(r.item,'B_MUTE')==0 then row(r.item,r.track,r.slot,1,false)end
        end
      end
    end
    local cfg={};for _,v in ipairs(request.inputs)do cfg[v.id]=v end
    for _,r in ipairs(request.items)do
      if request.recording and not request.recMutes[r.track] then
        local tr=assert(recording[r.track],'Recording track missing from snapshot')
        local it=reaper.AddMediaItemToTrack(tr);assert(reaper.SetItemStateChunk(it,r.chunk,false))
        local setting=(request.mix or {})[r.track] or {gain=1,pan=0}
        row(it,tr,(cfg[r.track] or {}).name or r.track,setting.gain,true)
        rows[#rows].pan=setting.pan
      end
    end
    assert(#rows>0,'All inputs are muted. Choose something to include.')
    reaper.RecursiveCreateDirectory(folder..'/Media',0)
    local copies={}
    for i,r in ipairs(rows)do
      if not copies[r.file] then
        local ext=r.file:match('(%.[%w]+)$') or '.wav'
        local dest=folder..'/Media/'..i..ext
        -- Only unpublished worker media is replaced when recovering a partial preparation.
        os.remove(dest);copy(r.file,dest);copies[r.file]=dest
      end
      r.file=copies[r.file]
    end
    -- All source reads and routing checks complete before replacing the worker project.
    for i=reaper.CountTracks(0)-1,0,-1 do reaper.DeleteTrack(reaper.GetTrack(0,i))end
    for _,r in ipairs(rows)do
      reaper.InsertTrackAtIndex(reaper.CountTracks(0),false);local tr=reaper.GetTrack(0,reaper.CountTracks(0)-1)
      reaper.GetSetMediaTrackInfo_String(tr,'P_NAME',r.name,true)
      for k,v in pairs({B_MAINSEND=1,I_RECARM=0,I_RECMON=0,D_VOL=r.gain,D_PAN=r.pan or 0})do reaper.SetMediaTrackInfo_Value(tr,k,v)end
      local it=reaper.AddMediaItemToTrack(tr);assert(reaper.SetItemStateChunk(it,r.chunk,false))
      reaper.SetMediaItemInfo_Value(it,'D_POSITION',reaper.GetMediaItemInfo_Value(it,'D_POSITION')-request.song.start)
      reaper.SetMediaItemInfo_Value(it,'C_BEATATTACHMODE',0)
      reaper.SetMediaItemInfo_Value(it,'B_MUTE',0)
      local tk=reaper.GetActiveTake(it);reaper.SetMediaItemTake_Source(tk,assert(reaper.PCM_Source_CreateFromFile(r.file)))
    end
    for i=reaper.CountTempoTimeSigMarkers(0)-1,0,-1 do reaper.DeleteTempoTimeSigMarker(0,i)end
    reaper.SetTempoTimeSigMarker(0,-1,0,-1,-1,request.song.bpm or 120,request.song.beats or 4,4,false)
    reaper.CSurf_OnPlayRateChange(request.rate)
    -- ReaSet's tempo controller always preserves pitch at the master rate.
    if reaper.GetToggleCommandState(40671)~=1 then reaper.Main_OnCommand(40671,0)end
    local master=reaper.GetMasterTrack(0)
    while reaper.TrackFX_GetCount(master)>0 do reaper.TrackFX_Delete(master,0)end
    for i=reaper.GetTrackNumSends(master,1)-1,0,-1 do reaper.RemoveTrackSend(master,1,i)end
    reaper.SetMediaTrackInfo_Value(master,'D_VOL',1);reaper.SetMediaTrackInfo_Value(master,'D_PAN',0);reaper.SetMediaTrackInfo_Value(master,'B_MUTE',0)
    for k,v in pairs({RENDER_SETTINGS=0,RENDER_BOUNDSFLAG=0,RENDER_STARTPOS=0,RENDER_ENDPOS=request.duration,RENDER_CHANNELS=2,RENDER_SRATE=48000,RENDER_TAILFLAG=0,RENDER_ADDTOPROJ=0,RENDER_NORMALIZE=0,PROJECT_SRATE=48000,PROJECT_SRATE_USE=1})do reaper.GetSetProjectInfo(0,k,v,true)end
    reaper.GetSetProjectInfo_String(0,'RENDER_FORMAT','ZXZhdxgAAA==',true)
    reaper.GetSetProjectInfo_String(0,'RENDER_FORMAT2','',true)
    reaper.GetSetProjectInfo_String(0,'RENDER_FILE',folder,true)
    reaper.GetSetProjectInfo_String(0,'RENDER_PATTERN','mix-pending',true)
    reaper.TrackList_AdjustWindows(false)
    reaper.Main_SaveProjectEx(0,renderProject,8)
  end
  -- On recovery too, prove this project cannot record or send to real outputs.
  for i=-1,reaper.CountTracks(0)-1 do
    local tr=i==-1 and reaper.GetMasterTrack(0) or reaper.GetTrack(0,i)
    assert(reaper.GetTrackNumSends(tr,1)==0 and reaper.GetMediaTrackInfo_Value(tr,'I_RECARM')==0,'Unsafe worker routing')
  end
  reaper.GetSetProjectInfo(0,'RENDER_NORMALIZE',0,true)
  local _,stats=reaper.GetSetProjectInfo_String(0,'RENDER_STATS','43349',false)
  local loud=tonumber(stats:match('LUFSI:([%-%d.]+)'))
  assert(loud and loud>-60,'No usable audio: this take is silent or too quiet. Check the recording inputs.')
  -- Limit normalization boost to 18 dB for quiet rehearsal captures.
  local target=math.min(-16,loud+18)
  reaper.GetSetProjectInfo(0,'RENDER_NORMALIZE',193,true)
  reaper.GetSetProjectInfo(0,'RENDER_NORMALIZE_TARGET',10^(target/20),true)
  reaper.GetSetProjectInfo(0,'RENDER_BRICKWALL',10^(-1/20),true)
  os.remove(folder..'/mix-pending.wav')
  reaper.Main_OnCommand(41824,0)
  local f=assert(io.open(folder..'/mix-pending.wav','rb'),'REAPER did not finish rendering');f:close()
  write(folder..'/render-result.json',{ok=true,device=device,resource=reaper.GetResourcePath(),input_lufs=loud,target=target,tracks=reaper.CountTracks(0)})
end,debug.traceback)
if not ok then write(folder..'/render-result.json',{ok=false,error=tostring(why)})end
-- Never leave an unsaved-project prompt in a hidden worker.
reaper.GetSetProjectInfo(0,'DIRTY',0,true)
reaper.Main_OnCommand(40004,0)
