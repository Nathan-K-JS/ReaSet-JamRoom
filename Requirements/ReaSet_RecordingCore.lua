-- REAPER-owned recording sessions and recovery. GPL-3.0.
local dir=debug.getinfo(1,'S').source:match('@?(.*[\\/])') or ''
local J=dofile(dir..'ReaSet_JSON.lua')
local P=dofile(dir..'ReaSet_Playback.lua')
local M={J=J,P=P}
dofile(dir..'ReaSet_Listening.lua')(M)
dofile(dir..'ReaSet_RecordingParts.lua')(M)
function M.read(path)
  local f=io.open(path,'rb');if not f then return nil end
  local s=f:read('*a');f:close();return s
end
function M.write(path,value)
  local tmp=path..'.new';local f=assert(io.open(tmp,'wb'),'Cannot write '..tmp)
  assert(f:write(value));assert(f:close())
  local old=M.read(path)
  if old then
    os.remove(path..'.previous')
    assert(os.rename(path,path..'.previous'),'Cannot preserve previous session record')
  end
  local ok,why=os.rename(tmp,path)
  if not ok and old then os.rename(path..'.previous',path) end
  assert(ok,why)
end
function M.guid()return reaper.genGuid():gsub('[{}%-]','')end
function M.samechunk(a,b)
  -- Selecting another take changes SEL without changing recorded content.
  local function stable(s)return s and s:gsub('\nSEL [01]\n','\nSEL 0\n',1)end
  return stable(a)==stable(b)
end
function M.ext(obj,key,value,track)
  local fn=track and reaper.GetSetMediaTrackInfo_String or reaper.GetSetMediaItemInfo_String
  local _,v=fn(obj,'P_EXT:'..key,value or '',value~=nil);return v
end
function M.defaults()
  local names={'Vox 1','Vox 2','Vox 3','Vox 4','Bass','Guitar 1','Guitar 2','Utility Mic','Drums EAD10','Keys','Spare 1','Spare 2','Spare 3','Spare 4'}
  local ins={0,1,2,3,4,5,6,7,8,10,12,13,14,15}
  local outs={12,12,12,12,3,4,6,14,0,8,14,14,14,14}
  local a=J.array()
  for i,name in ipairs(names) do a[i]={id=tostring(i),name=name,input=ins[i],stereo=i==9 or i==10,output=outs[i],outStereo=i==6 or i==7 or i==9 or i==10,selected=false,extra=i==8 or i>10} end
  return a
end
function M.tracks()
  local a={}
  for i=0,reaper.CountTracks(0)-1 do
    local t=reaper.GetTrack(0,i);local id=M.ext(t,'ReaSetRec',nil,true)
    if id~='' then assert(not a[id],'Duplicate recording track '..id);a[id]=t end
  end
  return a
end
function M.owned_items(fn)
  for _,tr in pairs(M.tracks()) do
    for n=reaper.CountTrackMediaItems(tr)-1,0,-1 do
      local it=reaper.GetTrackMediaItem(tr,n);local tag=M.ext(it,'ReaSetRec')
      if tag~='' then fn(it,tr,tag) end
    end
  end
end
function M.new()
  local self={project=reaper.EnumProjects(-1,''),mode='idle',message='',revision=0,seen={},ack='',audition={}}
  local _,projectfile=reaper.EnumProjects(-1,'');self.projectfile=projectfile
  local _,id=reaper.GetProjExtState(0,'ReaSet','projectId')
  if id=='' then id=M.guid();reaper.SetProjExtState(0,'ReaSet','projectId',id) end
  self.id=id;self.root=projectfile~='' and (projectfile:gsub('\\','/')..'.recordings') or nil
  self.db={version=1,project=id,inputs=M.defaults(),sessions=J.array(),countin=true}
  if self.root then
    reaper.RecursiveCreateDirectory(self.root,0)
    local found,loaded=false,false
    for _,suffix in ipairs({'/index.json','/index.json.previous'})do
      local raw=M.read(self.root..suffix)
      if raw then
        found=true;local ok,db=pcall(J.decode,raw)
        if ok and (db.version==1 or db.version==2) and db.project==id then self.db=db;loaded=true;break end
      end
    end
    assert(not found or loaded,'Recording index needs recovery; original files retained')
    if loaded and self.db.version==1 and not M.read(self.root..'/index.v1.json')then M.write(self.root..'/index.v1.json',J.encode(self.db))end
  end
  dofile(dir..'ReaSet_FreeJam.lua')(self,M)
  dofile(dir..'ReaSet_RecordingReady.lua')(self,M)
  dofile(dir..'ReaSet_RecordingTimeline.lua')(self,M)
  function self:save(project)
    assert(self.root,'Save the REAPER setlist project before recording')
    M.write(self.root..'/index.json',J.encode(self.db))
    reaper.SetProjExtState(0,'ReaSetRec','index',self.root..'/index.json')
    if project then
      local receipt=M.guid();reaper.SetProjExtState(0,'ReaSetRec','saveReceipt',receipt)
      reaper.Main_SaveProject(0,false)
      local saved=M.read(self.projectfile)
      assert(saved and saved:find(receipt,1,true),'REAPER project save was not confirmed; session recovery record retained')
    end
    self.revision=self.revision+1
  end
  function self:session(id)
    for _,s in ipairs(self.db.sessions) do if s.id==id then return s end end
    error('Recording session no longer exists')
  end
  function self:song(key)
    local jam=self:jam_song(key);if jam then return jam end
    for _,s in ipairs(P.songs()) do if s.key==key then return s end end
    error('Song changed; cue it again')
  end
  function self:park()
    self:clear_timeline()
    self:jam_clear_click()
    M.owned_items(function(it)reaper.SetMediaItemInfo_Value(it,'B_MUTE',1)end)
    for _,tr in pairs(M.tracks()) do reaper.SetMediaTrackInfo_Value(tr,'I_RECARM',0);reaper.SetMediaTrackInfo_Value(tr,'I_RECMON',0)end
    for guid,value in pairs(self.audition) do
      for i=0,reaper.CountMediaItems(0)-1 do
        local it=reaper.GetMediaItem(0,i);local _,g=reaper.GetSetMediaItemInfo_String(it,'GUID','',false)
        if g==guid then reaper.SetMediaItemInfo_Value(it,'B_MUTE',value)end
      end
    end
    if self.auditionOptions then
      reaper.CSurf_OnPlayRateChange(self.auditionOptions.rate)
      for i=0,reaper.CountMediaItems(0)-1 do
        local it=reaper.GetMediaItem(0,i)
        for n=0,reaper.CountTakes(it)-1 do
          local tk=reaper.GetTake(it,n);local _,g=reaper.GetSetMediaItemTakeInfo_String(tk,'GUID','',false)
          local old=self.auditionOptions.pitches[g]
          if old then reaper.SetMediaItemTakeInfo_Value(tk,'D_PITCH',old)end
        end
      end
    end
    self.auditionOptions=nil
    self.audition={};reaper.SetProjExtState(0,'ReaSetRec','audition','');reaper.SetProjExtState(0,'ReaSetRec','auditionOptions','')
    reaper.UpdateArrange()
  end
  function self:setup()
    assert(reaper.GetPlayState()==0,'Stop playback before setup')
    assert(self.root,'Save the REAPER setlist project first')
    local tracks=M.tracks()
    local folder=tracks.folder
    if not folder then
      reaper.InsertTrackAtIndex(reaper.CountTracks(0),false)
      folder=reaper.GetTrack(0,reaper.CountTracks(0)-1)
      reaper.GetSetMediaTrackInfo_String(folder,'P_NAME','Recording',true)
      M.ext(folder,'ReaSetRec','folder',true)
    end
    for _,cfg in ipairs(self.db.inputs) do
      if not tracks[cfg.id] then
        local last=reaper.GetMediaTrackInfo_Value(folder,'IP_TRACKNUMBER')-1
        local depth=reaper.GetMediaTrackInfo_Value(folder,'I_FOLDERDEPTH')
        local ending=-1
        if depth==1 then
          while depth>0 and last+1<reaper.CountTracks(0) do
            last=last+1;depth=depth+reaper.GetMediaTrackInfo_Value(reaper.GetTrack(0,last),'I_FOLDERDEPTH')
          end
          local tail=reaper.GetTrack(0,last);ending=reaper.GetMediaTrackInfo_Value(tail,'I_FOLDERDEPTH')
          reaper.SetMediaTrackInfo_Value(tail,'I_FOLDERDEPTH',0)
        else reaper.SetMediaTrackInfo_Value(folder,'I_FOLDERDEPTH',1)end
        reaper.InsertTrackAtIndex(last+1,false)
        local tr=reaper.GetTrack(0,last+1)
        reaper.SetMediaTrackInfo_Value(tr,'I_FOLDERDEPTH',ending)
        reaper.GetSetMediaTrackInfo_String(tr,'P_NAME','REC '..cfg.name,true)
        M.ext(tr,'ReaSetRec',cfg.id,true)
        reaper.SetMediaTrackInfo_Value(tr,'B_MAINSEND',0)
        local send=reaper.CreateTrackSend(tr,nil)
        reaper.SetTrackSendInfo_Value(tr,1,send,'I_DSTCHAN',cfg.output | (cfg.outStereo and 0 or 1024))
        reaper.SetMediaTrackInfo_Value(tr,'I_RECINPUT',cfg.input | (cfg.stereo and 1024 or 0))
        reaper.SetMediaTrackInfo_Value(tr,'I_RECMON',0)
        reaper.SetMediaTrackInfo_Value(tr,'I_RECARM',0)
      end
    end
    reaper.SetProjExtState(0,'ReaSetRec','templateSetup','1')
    reaper.TrackList_AdjustWindows(false);self:save(true)
    self.message='Recording tracks ready. Select instruments and check input meters.'
  end
  function self:auto_setup()
    if not self.root or self.mode~='idle' or self.db.active or reaper.GetPlayState()~=0 then return false end
    local _,done=reaper.GetProjExtState(0,'ReaSetRec','templateSetup')
    local _,exported=reaper.GetProjExtState(0,'ReaSet','recordingProject')
    if done=='1' or exported=='1' then return false end
    -- Recognize the existing Jam Room bus layout, not an arbitrary open RPP.
    local found={}
    for i=0,reaper.CountTracks(0)-1 do
      local _,name=reaper.GetTrackName(reaper.GetTrack(0,i));found[name]=true
    end
    if not (found['PB DRUMS'] and found['PB CLICK']) then return false end
    self:setup()
    self.message='Recording tracks created and saved. Check the X32 inputs, then select instruments to record.'
    return true
  end
  function self:arm(take)
    if self.deviceState~='ready' then self:prepare_device();self:device_tick()end
    local tracks=M.tracks();local count=0
    for _,tr in pairs(tracks)do reaper.SetMediaTrackInfo_Value(tr,'I_RECARM',0)end
    for _,cfg in ipairs(self.db.inputs)do
      assert(tracks[cfg.id],'Set up recording tracks first')
      if cfg.selected then assert(cfg.input+(cfg.stereo and 2 or 1)<=reaper.GetNumAudioInputs(),cfg.name..' input unavailable')end
    end
    for _,cfg in ipairs(self.db.inputs) do
      local tr=tracks[take and take.dest[cfg.id] or cfg.id]
      if not tr then tr=tracks[cfg.id]end
      assert(tr,'Set up recording tracks first')
      if cfg.selected then
        assert(cfg.input+(cfg.stereo and 2 or 1)<=reaper.GetNumAudioInputs(),cfg.name..' input unavailable')
        count=count+1
      end
      reaper.SetMediaTrackInfo_Value(tr,'I_RECINPUT',cfg.input | (cfg.stereo and 1024 or 0))
      reaper.SetMediaTrackInfo_Value(tr,'I_RECMODE',0)
      reaper.SetMediaTrackInfo_Value(tr,'I_RECMON',0)
      reaper.SetMediaTrackInfo_Value(tr,'I_RECARM',cfg.selected and 1 or 0)
    end
    return count
  end
  function self:restore_options()
    local o=self.db.options
    if o then
      reaper.GetSetProjectInfo_String(0,'RECORD_PATH',o.path,true)
      reaper.GetSetProjectInfo_String(0,'RECORD_PATH_SECONDARY',o.secondary,true)
      reaper.SNM_SetIntConfigVar('promptendrec',o.prompt)
      reaper.SNM_SetIntConfigVar('projmetroen',o.metro)
      reaper.SNM_SetIntConfigVar('projrecmode',o.recmode)
      reaper.GetSetRepeat(o.repeatMode)
      if o.overlap then reaper.Main_OnCommand(o.overlap,0)end
      for action,state in pairs(o.lanes or {})do
        local command=tonumber(action)
        if reaper.GetToggleCommandState(command)~=state then reaper.Main_OnCommand(command,0)end
      end
      if o.rate then reaper.CSurf_OnPlayRateChange(o.rate)end
      self.db.options=nil
    end
  end
  function self:start_native()
    reaper.Main_OnCommand(1013,0)
    assert((reaper.GetPlayState()&4)==4,'REAPER did not start recording; check the audio device')
    self.mode='recording'
  end
  function self:begin(key,parentId,sessionId)
    assert(self.root,'Save the REAPER setlist project before recording')
    assert(self.mode=='idle' or self.mode=='review','Stop the current take first')
    assert(reaper.GetPlayState()==0,'Stop playback before recording')
    assert(reaper.SNM_GetIntConfigVar and reaper.SNM_SetIntConfigVar,'SWS is required for recording')
    local song=self:song(key);key=song.key
    for i=0,reaper.CountTracks(0)-1 do
      local tr=reaper.GetTrack(0,i)
      assert(reaper.GetMediaTrackInfo_Value(tr,'I_RECARM')==0 or M.ext(tr,'ReaSetRec',nil,true)~='','Disarm other REAPER tracks before recording')
    end
    self:park();assert(self:arm()>0,'Select at least one instrument');assert(self.deviceState=='ready','Recording inputs are still connecting; wait for Ready or use Reconnect inputs')
    local rate=reaper.Master_GetPlayRate(0)
    local _,tk=reaper.GetExtState('ReaSetTK','state'):match('^([^|]+)|([^|]+)')
    local semis=tonumber(tk) or 0
    if song.free then rate=1;semis=0 end
    local session=sessionId and self:session(sessionId) or nil
    if session then assert(not session.deleted and not session.exported and session.song.key==key,'Choose a live recording session');rate=session.rate;semis=session.semis end
    for _,s in ipairs(self.db.sessions)do
      if not session and s.song.key==key and not s.deleted and not s.exported and math.abs(s.rate-rate)<.00001 and s.semis==semis then session=s end
    end
    if not session then
      local sid=os.date('%Y%m%d-%H%M%S')..'-'..M.guid():sub(1,8)
      session={id=sid,song=song,rate=rate,semis=semis,takes=J.array(),created=os.date('%Y-%m-%d %H:%M'),folder=self.root..'/'..sid,pitches={}}
      for _,r in ipairs(P.items(song,true))do
        for n=0,reaper.CountTakes(r.item)-1 do
          local tk=reaper.GetTake(r.item,n);local _,guid=reaper.GetSetMediaItemTakeInfo_String(tk,'GUID','',false)
          session.pitches[guid]=reaper.GetMediaItemTakeInfo_Value(tk,'D_PITCH')
        end
      end
      reaper.RecursiveCreateDirectory(session.folder,0)
      P.reconcile()
      reaper.Main_SaveProjectEx(0,session.folder..'/backing.RPP',0)
      assert(M.read(session.folder..'/backing.RPP'),'Cannot save backing snapshot')
      self.db.sessions[#self.db.sessions+1]=session
    end
    assert(math.abs(session.song.start-song.start)<.001 and math.abs(session.song.finish-song.finish)<.001,'Song boundaries changed; export this session before recording again')
    local parent
    if parentId then for _,v in ipairs(session.takes)do if v.id==parentId then parent=v end end;assert(parent and parent.status~='discarded','Choose a kept take to build on')end
    local take={id=M.guid(),number=#session.takes+1,items=J.array(),started=os.date('%Y-%m-%d %H:%M'),status='recording',inputs=J.array(),before={},trackNames={}}
    for _,cfg in ipairs(self.db.inputs) do if cfg.selected then take.inputs[#take.inputs+1]=cfg.id end end
    session.takes[#session.takes+1]=take
    self.db.active={session=session.id,take=take.id}
    M.parts(self,session,take,parent)
    self:arm(take)
    for id,tr in pairs(M.tracks()) do
      local _,name=reaper.GetTrackName(tr);take.trackNames[id]=name
      for input,dest in pairs(take.dest)do if dest==id then take.trackNames[input]=name end end
      for i=0,reaper.CountTrackMediaItems(tr)-1 do local it=reaper.GetTrackMediaItem(tr,i);local _,g=reaper.GetSetMediaItemInfo_String(it,'GUID','',false);take.before[g]=true end
    end
    local _,path=reaper.GetSetProjectInfo_String(0,'RECORD_PATH','',false)
    local _,secondary=reaper.GetSetProjectInfo_String(0,'RECORD_PATH_SECONDARY','',false)
    self.db.options={path=path,secondary=secondary,prompt=reaper.SNM_GetIntConfigVar('promptendrec',0),metro=reaper.SNM_GetIntConfigVar('projmetroen',0),recmode=reaper.SNM_GetIntConfigVar('projrecmode',0),repeatMode=reaper.GetSetRepeat(-1)}
    for _,action in ipairs({41186,41330,42677})do if reaper.GetToggleCommandState(action)==1 then self.db.options.overlap=action end end
    self.db.options.lanes={}
    for _,action in ipairs({41329,42702})do self.db.options.lanes[tostring(action)]=reaper.GetToggleCommandState(action)end
    self.db.options.rate=reaper.Master_GetPlayRate(0)
    self.db.active={session=session.id,take=take.id}
    self.selected=session.id;self.take=take.id;self:save(true)
    reaper.GetSetProjectInfo_String(0,'RECORD_PATH',session.folder..'/'..take.id,true)
    reaper.RecursiveCreateDirectory(session.folder..'/'..take.id,0)
    reaper.GetSetProjectInfo_String(0,'RECORD_PATH_SECONDARY','',true)
    reaper.SNM_SetIntConfigVar('promptendrec',0)
    reaper.SNM_SetIntConfigVar('projmetroen',0)
    reaper.Main_OnCommand(40252,0) -- Record mode: normal (0 is selected-item auto-punch).
    assert(reaper.kbd_getTextFromCmd(42677,0)~='','This REAPER version does not support independent recording layers')
    reaper.Main_OnCommand(42677,0)
    reaper.GetSetRepeat(0)
    reaper.SetExtState('ReaSet','nativeLoop','off',false)
    reaper.CSurf_OnPlayRateChange(session.rate)
    M.load_mix(self,take)
    self:prepare_timeline(session,take)
  end
  function self:click_output()
    local output,volume=0,1
    for i=0,reaper.CountTracks(0)-1 do
      local tr=reaper.GetTrack(0,i);local _,name=reaper.GetTrackName(tr)
      if name=='PB CLICK' then
        volume=reaper.GetMediaTrackInfo_Value(tr,'D_VOL')
        if reaper.GetTrackNumSends(tr,1)>0 then output=reaper.GetTrackSendInfo_Value(tr,1,0,'I_DSTCHAN')end
      end
    end
    assert((output&1023)<reaper.GetNumAudioOutputs(),'Click output unavailable; check PB CLICK routing')
    return output,volume
  end
  function self:stop_preview()
    if self.preview then reaper.CF_Preview_Stop(self.preview);self.preview=nil end
    if self.previewSource then reaper.PCM_Source_Destroy(self.previewSource);self.previewSource=nil end
  end
  function self:drop_empty_take(s,take)
    if take.status~='empty' or take.unresolved or #take.items>0 then return false end
    -- Unknown/unfinished media must stay discoverable, even when REAPER did not
    -- create an item. Only a genuinely empty capture folder can be dismissed.
    if not take.leadOnly and reaper.EnumerateFiles(s.folder..'/'..take.id,0) then take.unresolved=true;return false end
    if take.dest then M.remove_empty_parts(s,take.dest);for _,id in pairs(take.dest)do s.parts[id]=nil end end
    for i=#s.takes,1,-1 do if s.takes[i]==take then table.remove(s.takes,i)end end
    if #s.takes==0 then
      for i=#self.db.sessions,1,-1 do if self.db.sessions[i]==s then table.remove(self.db.sessions,i)end end
    end
    return true
  end
  function self:finish(recovered)
    local active=self.db.active;if not active then return end
    local s=self:session(active.session);local take
    for _,t in ipairs(s.takes)do if t.id==active.take then take=t end end
    assert(take,'Missing active take')
    local selected={};for _,id in ipairs(take.inputs)do selected[(take.dest or {})[id] or id]=true end
    local known={};for _,r in ipairs(take.items)do known[r.guid]=r end
    for id,tr in pairs(M.tracks()) do
      if selected[id] then for i=0,reaper.CountTrackMediaItems(tr)-1 do
        local it=reaper.GetTrackMediaItem(tr,i);local _,guid=reaper.GetSetMediaItemInfo_String(it,'GUID','',false)
        local tk=reaper.GetActiveTake(it)
        local file=tk and reaper.GetMediaSourceFileName(reaper.GetMediaItemTake_Source(tk),'') or ''
        local owned_path=file:gsub('\\','/'):sub(1,#s.folder+#take.id+2)==s.folder..'/'..take.id..'/'
        if not take.before[guid] and (known[guid] or owned_path) then
          if self:align_capture(s,take,it) then
          M.ext(it,'ReaSetRec',s.id..'/'..take.id)
          if s.song.free then reaper.SetMediaItemInfo_Value(it,'C_BEATATTACHMODE',0)end
          reaper.SetMediaItemInfo_Value(it,'B_MUTE',1)
          local ok,chunk=reaper.GetItemStateChunk(it,'',false);assert(ok,'Cannot capture recording metadata')
          if known[guid] then known[guid].chunk=chunk else take.items[#take.items+1]={guid=guid,track=id,chunk=chunk}end
          else take.leadOnly=true;M.ext(it,'ReaSetRecPreview',take.id)end
        end
      end end
    end
    if #take.items>0 then take.leadOnly=nil end
    if not take.leadOnly and (recovered or #take.items==0) then self:recover_audio(s,take)end
    take.status=#take.items==0 and not take.unresolved and 'empty' or (recovered and 'recovered' or 'kept')
    take.duration=0
    M.owned_items(function(it,_,tag)if tag==s.id..'/'..take.id then take.duration=math.max(take.duration,reaper.GetMediaItemInfo_Value(it,'D_POSITION')+reaper.GetMediaItemInfo_Value(it,'D_LENGTH')-s.song.start)end end)
    take.duration=math.max(take.duration,take.limit or 0)
    if s.song.free then s.song.finish=math.max(s.song.finish,s.song.start+take.duration)end
    self:restore_options();self:park();reaper.SetEditCurPos(s.song.start,false,false)
    if self:drop_empty_take(s,take) then
      self.db.active=nil;self.mode='idle';self.selected=nil;self.take=nil
      self:arm();self:save(true);self.message='No audio captured — ready to record again'
      return
    end
    self.db.active=nil;self.mode='review';self.selected=s.id;self.take=take.id
    M.load_mix(self,take)
    s.selected=take.id
    self:save(true);self.message=take.unresolved and ('Recovered audio needs review in REAPER: '..s.folder..'/'..take.id) or (#take.items==0 and 'No audio captured' or (recovered and 'Recovered — check take' or 'Saved in session'))
  end
  function self:review(sid,tid)
    assert(reaper.GetPlayState()==0,'Stop playback before changing takes')
    self:park();local s=self:session(sid)
    assert(not s.deleted and not s.exported,'This session has been cleared from the setlist')
    local take
    for _,t in ipairs(s.takes) do if t.id==tid then take=t end end
    assert(take and take.status~='discarded','Select a kept take')
    assert(not take.unresolved,'Some interrupted media needs recovery in REAPER: '..s.folder..'/'..take.id)
    self.selected=sid;self.take=tid;self.mode='review';self.overdub=nil;s.selected=tid
    M.load_mix(self,take)
    self.auditionOptions={rate=reaper.Master_GetPlayRate(0),pitches={}}
    for _,r in ipairs(P.items(s.song,true))do
      for n=0,reaper.CountTakes(r.item)-1 do
        local tk=reaper.GetTake(r.item,n);local _,guid=reaper.GetSetMediaItemTakeInfo_String(tk,'GUID','',false)
        if (s.pitches or {})[guid] then
          self.auditionOptions.pitches[guid]=reaper.GetMediaItemTakeInfo_Value(tk,'D_PITCH')
          reaper.SetMediaItemTakeInfo_Value(tk,'D_PITCH',s.pitches[guid])
        end
      end
    end
    reaper.SetProjExtState(0,'ReaSetRec','auditionOptions',J.encode(self.auditionOptions))
    reaper.CSurf_OnPlayRateChange(s.rate)
    if s.song.free then self:jam_silence()end
    reaper.SetEditCurPos(s.song.start,false,false)
    self:audition_mix()
  end
  function self:audition_mix()
    local s=self:session(self.selected)
    local _,take=M.mix_take(self);local _,allowed=M.arrangement(self,s,take)
    M.owned_items(function(it,tr,owner)
      local id=M.ext(tr,'ReaSetRec',nil,true);local mix=(take.mix or {})[id] or {gain=1}
      reaper.SetMediaItemInfo_Value(it,'B_MUTE',allowed[id] and self.recordingOn~=false and not mix.muted and 0 or 1)
      if allowed[id] then reaper.SetMediaTrackInfo_Value(tr,'D_VOL',(s.parts[id].baseGain or 1)*mix.gain)end
    end)
    for _,r in ipairs(P.items(s.song,true))do
      local _,g=reaper.GetSetMediaItemInfo_String(r.item,'GUID','',false)
      if self.audition[g]==nil then self.audition[g]=reaper.GetMediaItemInfo_Value(r.item,'B_MUTE')end
      reaper.SetMediaItemInfo_Value(r.item,'B_MUTE',(self.backingOn==false or (self.stemMutes or {})[r.slot]) and 1 or self.audition[g])
    end
    reaper.SetProjExtState(0,'ReaSetRec','audition',J.encode(self.audition))
  end
  function self:remove_session(s)
    local known={}
    for _,t in ipairs(s.takes)do for _,r in ipairs(t.items)do known[r.guid]=r.chunk end end
    M.owned_items(function(it,_,tag)
      if tag:sub(1,#s.id+1)==s.id..'/' then
        local _,guid=reaper.GetSetMediaItemInfo_String(it,'GUID','',false)
        local _,chunk=reaper.GetItemStateChunk(it,'',false)
        assert(M.samechunk(known[guid],chunk),'Recording items changed; cleanup stopped and audio retained')
      end
    end)
    M.owned_items(function(it,tr,tag)if tag:sub(1,#s.id+1)==s.id..'/' then reaper.DeleteTrackMediaItem(tr,it) end end)
    self:park();self.mode='idle';for _,t in ipairs(s.takes)do M.remove_empty_parts(s,t.dest)end;self:save(true)
  end
  function self:restore_session(s)
    for _,p in pairs(s.parts or {})do M.part_track(self,p)end
    local tracks=M.tracks();local present={}
    M.owned_items(function(it)local _,g=reaper.GetSetMediaItemInfo_String(it,'GUID','',false);present[g]=true end)
    for _,take in ipairs(s.takes)do for _,row in ipairs(take.items)do
      if not present[row.guid] then
        assert(tracks[row.track],'Set up recording tracks before restoring')
        local it=reaper.AddMediaItemToTrack(tracks[row.track]);assert(reaper.SetItemStateChunk(it,row.chunk,false),'Could not restore take')
        reaper.SetMediaItemInfo_Value(it,'B_MUTE',1)
      end
    end end
    s.deleted=nil;self:save(true)
  end
  function self:recover_audio(s,take)
    -- Restore indexed chunks missing from an older saved RPP first.
    local present,files={},{}
    M.owned_items(function(it)
      local _,g=reaper.GetSetMediaItemInfo_String(it,'GUID','',false);present[g]=true
      for n=0,reaper.CountTakes(it)-1 do local tk=reaper.GetTake(it,n);files[reaper.GetMediaSourceFileName(reaper.GetMediaItemTake_Source(tk),''):gsub('\\','/')]=true end
    end)
    if take.leadOnly then return end
    if take.dest then for _,id in pairs(take.dest)do M.part_track(self,s.parts[id])end end
    local tracks=M.tracks()
    for _,r in ipairs(take.items)do
      if not present[r.guid] and tracks[r.track] then
        local it=reaper.AddMediaItemToTrack(tracks[r.track]);assert(reaper.SetItemStateChunk(it,r.chunk,false),'Recovery chunk could not be restored')
        reaper.SetMediaItemInfo_Value(it,'B_MUTE',1)
        for n=0,reaper.CountTakes(it)-1 do local tk=reaper.GetTake(it,n);files[reaper.GetMediaSourceFileName(reaper.GetMediaItemTake_Source(tk),''):gsub('\\','/')]=true end
      end
    end
    local folder=s.folder..'/'..take.id;local candidates={};local n=0
    while true do
      local file=reaper.EnumerateFiles(folder,n);if not file then break end;n=n+1
      if file:lower():match('%.wav$') or file:lower():match('%.flac$') then
        local full=folder..'/'..file
        if not files[full:gsub('\\','/')] then
          local ids={}
          for _,id in ipairs(take.inputs)do if file:find((take.trackNames or {})[id] or 'UNMATCHABLE',1,true)then ids[#ids+1]=id end end
          if #ids==0 and #take.inputs==1 then ids=take.inputs end
          if #ids==1 then
            candidates[ids[1]]=candidates[ids[1]] or {};table.insert(candidates[ids[1]],full)
          else take.unresolved=true end
        end
      end
    end
    for id,list in pairs(candidates)do
      local dest=(take.dest or {})[id] or id
      if #list~=1 or not tracks[dest] then take.unresolved=true
      else
        local source=reaper.PCM_Source_CreateFromFile(list[1])
        local length=source and reaper.GetMediaSourceLength(source) or 0
        if take.leadin and length>0 and length*s.rate<=take.leadin then take.leadOnly=true;reaper.PCM_Source_Destroy(source)
        elseif length>0 then
          local it=reaper.AddMediaItemToTrack(tracks[dest]);local tk=reaper.AddTakeToMediaItem(it)
          reaper.SetMediaItemTake_Source(tk,source)
          if s.song.free then reaper.SetMediaItemInfo_Value(it,'C_BEATATTACHMODE',0)end
          reaper.SetMediaItemInfo_Value(it,'D_POSITION',s.song.start)
          reaper.SetMediaItemInfo_Value(it,'D_LENGTH',math.max(0,length*s.rate-(take.leadin or 0)))
          reaper.SetMediaItemTakeInfo_Value(tk,'D_STARTOFFS',(take.leadin or 0)/s.rate)
          reaper.SetMediaItemTakeInfo_Value(tk,'D_PLAYRATE',1/s.rate)
          reaper.SetMediaItemInfo_Value(it,'B_MUTE',1);M.ext(it,'ReaSetRec',s.id..'/'..take.id)
          local _,guid=reaper.GetSetMediaItemInfo_String(it,'GUID','',false);local _,chunk=reaper.GetItemStateChunk(it,'',false)
          take.items[#take.items+1]={guid=guid,track=dest,chunk=chunk}
        else take.unresolved=true;if source then reaper.PCM_Source_Destroy(source)end end
      end
    end
  end
  function self:command(c)
    assert(c.project==self.id,'Project changed; refresh recording state')
    if c.op=='stop' then self:stop_preview();reaper.Main_OnCommand(1016,0);if self.db.active then self:finish()end;return end
    assert(c.revision==self.revision,'Recording state changed; retry your action')
    if c.op=='pause' then assert(self.mode=='recording','Not recording');reaper.Main_OnCommand(1008,0);return end
    if c.op=='save' then self:save(true);self.message='Saved in session';return end
    if c.op=='matchGain' then
      assert(not self.db.active,'Finish recording before changing playback volume')
      local song=self:song(c.song);local level=P.level(song)
      assert(level and level.status=='measured','No matched level available; run library volume matching first')
      self.message=P.match(song,level,true);if self.root then self:save(true)end;return
    end
    if c.op=='gain' then
      assert(not self.db.active,'Finish recording before changing playback volume')
      P.set(self:song(c.song),c.value);if self.root then self:save(true)end;return
    end
    assert(self.mode~='recording' and self.mode~='countin','Stop recording first')
    if c.op=='setup' then self:setup()
    elseif c.op=='ready' or c.op=='reconnect' then assert(reaper.GetPlayState()==0,'Stop playback first');self:prepare_device();self.deviceArm=true
      if self.mode=='idle' then self:park()end
    elseif c.op=='select' then
      assert(reaper.GetPlayState()==0,'Stop playback first')
      for _,cfg in ipairs(self.db.inputs)do if cfg.id==c.input then cfg.selected=c.value==true end end
      if reaper.GetNumAudioInputs()>0 then self:arm()end;self:save(false)
    elseif c.op=='configure' then
      assert(reaper.GetPlayState()==0,'Stop playback first')
      for _,cfg in ipairs(self.db.inputs)do if cfg.id==c.input then
        assert(type(c.channel)=='number' and c.channel>=0 and c.channel%1==0 and c.channel<128,'Invalid input')
        assert(type(c.output)=='number' and c.output>=0 and c.output%1==0 and c.output<128,'Invalid output')
        cfg.input=c.channel;cfg.output=c.output
        local tr=M.tracks()[cfg.id]
        if tr then
          assert(reaper.GetTrackNumSends(tr,1)==1,'Configure this track routing in REAPER')
          reaper.SetTrackSendInfo_Value(tr,1,0,'I_DSTCHAN',cfg.output | (cfg.outStereo and 0 or 1024))
        end
      end end
      self:arm();self:save(true)
    elseif c.op=='recordMode' then
      assert(self.mode=='idle' and reaper.GetPlayState()==0,'Finish the current take first')
      assert(c.value=='song' or c.value=='freejam','Choose Song or Free jam')
      self.db.recordMode=c.value;self:save(false)
    elseif c.op=='jamSettings' then
      assert(self.mode=='idle' and reaper.GetPlayState()==0,'Finish the current take first')
      self:jam_settings(c);self:save(false)
    elseif c.op=='countin' then self.db.countin=c.value==true;self:save(false)
    elseif c.op=='overdub' then
      self:review(c.session,c.take)
      self.overdub={session=c.session,take=c.take,stopAtEnd=true}
      for _,cfg in ipairs(self.db.inputs)do cfg.selected=false end
      self:prepare_device();self:save(false)
    elseif c.op=='jamClick' then
      assert(reaper.GetPlayState()==0,'Stop playback first');local s=M.mix_take(self);assert(s.song.free,'Free-jam click only');s.song.click=c.value==true;self:save(false)
    elseif c.op=='recordPart' then
      assert(self.overdub,'Choose Add another part first')
      local s,t=M.mix_take(self)
      assert(self:song(s.song.key).start==s.song.start,'Song moved; export this recording first')
      assert(math.abs(reaper.Master_GetPlayRate(0)-s.rate)<.00001,'Return to the recording tempo first')
      self:begin(s.song.key,t.id,s.id)
      local _,new=M.mix_take(self);new.stopAtEnd=c.stopAtEnd~=false;self.overdub=nil;self:save(false)
    elseif c.op=='partMix' then
      local s,t=M.mix_take(self);local mix=t.mix[c.part];assert(mix,'Part is not in this arrangement')
      if c.gain~=nil then assert(type(c.gain)=='number' and c.gain==c.gain and c.gain>=0 and c.gain<=4,'Invalid part volume');mix.gain=c.gain end
      if c.muted~=nil then mix.muted=c.muted==true end
      if c.name~=nil then assert(type(c.name)=='string' and #c.name<=100,'Name must be at most 100 characters');s.parts[c.part].name=c.name end
      self:audition_mix();self:save(false)
    elseif c.op=='record' then
      if self.db.recordMode=='freejam' and c.jam then self:jam_settings(c.jam)end
      self:begin(self.db.recordMode=='freejam' and 'freejam' or c.song)
    elseif c.op=='listening' then M.make_listening(self,c)
    elseif c.op=='review' then self:review(c.session,c.take)
    elseif c.op=='listen' then
      local same=self.selected==c.session and self.take==c.take and self.mode=='review'
      local overdub=self.overdub
      local backing,recording,inputs,stems=self.backingOn,self.recordingOn,self.recMutes,self.stemMutes
      self:review(c.session,c.take)
      if same then self.overdub=overdub;self.backingOn=backing;self.recordingOn=recording;self.recMutes=inputs;self.stemMutes=stems;self:audition_mix()end
      reaper.Main_OnCommand(1007,0);self.mode='audition'
    elseif c.op=='mix' then
      assert(self.selected,'Select a take');if c.group=='backing' then self.backingOn=c.value==true
      elseif c.group=='recording' then self.recordingOn=c.value==true
      elseif c.group=='stem' then self.stemMutes=self.stemMutes or {};self.stemMutes[c.input]=c.value==true
      else self.recMutes=self.recMutes or {};self.recMutes[c.input]=c.value==true end
      if c.group=='input' then local s,t=M.mix_take(self);for _,id in ipairs(t.layers)do if s.parts[id].input==c.input then t.mix[id].muted=c.value==true end end end
      self:audition_mix();M.save_mix(self)
    elseif c.op=='done' then assert(reaper.GetPlayState()==0,'Stop playback first');self:park();self.mode='idle';self.overdub=nil;self:release_device();self:save(true)
    elseif c.op=='later' then self.later=true
    elseif c.op=='open' then
      assert(reaper.GetPlayState()==0,'Stop playback before opening a recording project')
      local s=self:session(c.session);assert(s.exported and M.read(s.exported),'Exported project is missing')
      self:park();self.mode='idle';self:save(true)
      reaper.Main_OnCommand(40859,0);reaper.Main_openProject('noprompt:'..s.exported)
    elseif c.op=='exportBatch' or c.op=='deleteBatch' then
      assert(reaper.GetPlayState()==0,'Stop playback before housekeeping')
      assert(type(c.sessions)=='table' and #c.sessions>0 and #c.sessions<=200,'Select recording sessions')
      if c.op=='deleteBatch' then assert(c.confirm==table.concat(c.sessions,'|'),'Confirm the selected sessions')end
      local successes,errors=0,{}
      self:park()
      for _,sid in ipairs(c.sessions)do
        local ok,why=pcall(function()
          local s=self:session(sid)
          if c.op=='exportBatch' then M.export(self,s)
          else s.deleted=true;self:save(false);self:remove_session(s)end
        end)
        if ok then successes=successes+1 else errors[#errors+1]=sid..': '..tostring(why)end
      end
      self.message=tostring(successes)..' sessions completed'..(#errors>0 and ('; retained for review: '..table.concat(errors,'; ')) or '')
    elseif c.op=='delete' or c.op=='restore' or c.op=='export' then
      assert(reaper.GetPlayState()==0,'Stop playback before housekeeping')
      local s=self:session(c.session)
      if c.op=='delete' then assert(c.confirm==s.id,'Confirm this session');s.deleted=true;self:save(false);self:remove_session(s)
      elseif c.op=='restore' then self:restore_session(s)
      else self:park();M.export(self,s)end
    elseif c.op=='discard' or c.op=='retry' or c.op=='keep' or c.op=='restoreTake' or c.op=='favourite' or c.op=='rename' then
      assert(reaper.GetPlayState()==0,'Stop playback first')
      local s=self:session(c.session);local t
      for _,v in ipairs(s.takes)do if v.id==c.take then t=v end end
      assert(t,'Take no longer exists')
      if c.op=='rename' then assert(type(c.name)=='string' and #c.name<=100,'Name must be at most 100 characters');t.name=c.name
      elseif c.op=='favourite' then t.favourite=not t.favourite
      elseif c.op=='restoreTake' then t.status='kept'
      elseif c.op=='discard' then t.status='discarded'
      elseif c.op=='retry' then assert(t==s.takes[#s.takes],'Only retry the latest take');t.status='discarded' end
      self:park();self:save(true)
      if c.op=='discard' then
        if t.parent then self:review(s.id,t.parent)else self.mode='idle';self.selected=nil;self.take=nil end
        self.message='New recording discarded. Restore it from Saved recordings if needed.'
      end
      if c.op=='keep' or c.op=='retry' then
        for _,cfg in ipairs(self.db.inputs)do cfg.selected=false;for _,id in ipairs(t.inputs)do if cfg.id==id then cfg.selected=true end end end
        self.mode='idle';self:begin(s.song.key,c.op=='retry' and t.parent or nil,s.id)
      end
    else error('Unknown recording command')end
  end
  function self:tick()
    self:device_tick()
    if self.deviceArm and self.deviceState=='ready' and reaper.GetPlayState()==0 then self.deviceArm=nil;self:arm()end
    if self.mode=='countin' or self.mode=='recording' then
      local s,t=M.mix_take(self);local state=reaper.GetPlayState()
      if reaper.GetNumAudioInputs()==0 then
        reaper.Main_OnCommand(1016,0);self:finish(true);self.deviceState='unavailable';self.error='Recording inputs disconnected. Captured audio has been retained.';return
      end
      local origin=t.origin or s.song.start
      if self.mode=='countin' and reaper.GetPlayPosition()>=origin then self.mode='recording'end
      if s.song.free then self:jam_extend(s)end
      local finish=origin+(s.song.free and (t.limit or 0) or (s.song.finish-s.song.start))
      if (not s.song.free or t.parent and t.stopAtEnd~=false) and (state&1)==1 and reaper.GetPlayPosition()>=finish then reaper.Main_OnCommand(1016,0);self:finish()
      elseif state==0 then self:finish()end
    elseif self.mode=='audition' then
      local s=self:session(self.selected);local finish=s.song.finish
      if s.song.free then
        for _,t in ipairs(s.takes)do if t.id==self.take then finish=s.song.start+t.duration end end
      end
      if reaper.GetPlayState()==0 then self.mode='review'
      elseif reaper.GetPlayPosition()>=finish then reaper.Main_OnCommand(1016,0);self.mode='review'end
    end
  end
  function self:state()
    local inputs=J.array();local tracks=M.tracks()
    for _,cfg in ipairs(self.db.inputs)do
      local tr=tracks[cfg.id];local row={}
      if self.db.active then local _,t=M.mix_take(self);tr=tracks[(t.dest or {})[cfg.id]] or tr end
      for k,v in pairs(cfg)do row[k]=v end
      row.exists=tr~=nil;row.available=cfg.input+(cfg.stereo and 2 or 1)<=reaper.GetNumAudioInputs()
      row.armed=tr and reaper.GetMediaTrackInfo_Value(tr,'I_RECARM')==1 or false
      row.left=tr and reaper.Track_GetPeakInfo(tr,0) or 0
      row.right=tr and reaper.Track_GetPeakInfo(tr,1) or 0
      row.peak=math.max(row.left,row.right)
      inputs[#inputs+1]=row
    end
    local sessions=J.array();local pending=0
    for _,s in ipairs(self.db.sessions) do
      local row={id=s.id,song=s.song,created=s.created,deleted=s.deleted,exported=s.exported,takes=J.array()}
      for _,t in ipairs(s.takes)do row.takes[#row.takes+1]={id=t.id,name=t.name,number=t.number,status=t.unresolved and 'Needs recovery' or t.status,duration=t.duration or 0,favourite=t.favourite,inputs=t.inputs,parent=t.parent}end
      if not s.deleted and not s.exported then pending=pending+1 end
      sessions[#sessions+1]=row
    end
    local parts=J.array()
    if self.selected and self.take then local s,t=M.mix_take(self);for _,id in ipairs(t.layers or {})do local p=s.parts[id];parts[#parts+1]={id=id,name=p.name,stereo=p.stereo,input=p.input,new=p.take==t.id,gain=(t.mix[id] or {}).gain or 1,muted=(t.mix[id] or {}).muted==true}end end
    local songs=P.songs();for _,s in ipairs(songs)do s.gain=P.gain(s);s.level=P.level(s)end
    return {elapsed=self.db.active and math.max(0,reaper.GetPlayPosition()-(self.db.active.origin or 0)) or 0,device=self.deviceState,overdub=self.overdub,parts=parts,project=self.id,revision=self.revision,mode=self.mode,paused=(reaper.GetPlayState()&2)==2,inputs=inputs,sessions=sessions,songs=J.array(songs),pending=pending,notice=pending>0 and not self.later,recordMode=self.db.recordMode or 'song',jam=self.db.jam,countin=self.db.countin,selected=self.selected,take=self.take,message=self.message,error=self.error,ack=self.ack,ready=self.root~=nil,backingOn=self.backingOn~=false,recordingOn=self.recordingOn~=false,recMutes=self.recMutes or {},stemMutes=self.stemMutes or {}}
  end
  -- Restore preview overrides before ordinary rehearsal playback is available.
  local _,raw=reaper.GetProjExtState(0,'ReaSetRec','audition')
  if raw~='' then local ok,v=pcall(J.decode,raw);if ok then self.audition=v end end
  local _,opts=reaper.GetProjExtState(0,'ReaSetRec','auditionOptions')
  if opts~='' then local ok,v=pcall(J.decode,opts);if ok then self.auditionOptions=v end end
  if reaper.GetPlayState()==0 then
    self:release_device()
    local migration=J.encode(self.db)
    for _,s in ipairs(self.db.sessions)do for _,t in ipairs(s.takes)do M.parts(self,s,t,nil,s.deleted or s.exported)end end
    self.db.version=2
    if self.root and not self.db.active and migration~=J.encode(self.db)then self:save(true)end
    if self.db.active then self:finish(true) else
      local before=J.encode(self.db);local changes=reaper.GetProjectStateChangeCount(0)
      self:restore_options();self:park()
      for i=#self.db.sessions,1,-1 do
        local s=self.db.sessions[i]
        local ok,why=pcall(function()
          if s.deleted or s.exported then self:remove_session(s)
          else for j=#s.takes,1,-1 do
            local t=s.takes[j];self:recover_audio(s,t)
            if t.status=='empty' and #t.items>0 then t.status='recovered' end
            self:drop_empty_take(s,t)
          end end
        end)
        if not ok then self.error=tostring(why)end
      end
      if self.root and (before~=J.encode(self.db) or (#self.db.sessions>0 and changes~=reaper.GetProjectStateChangeCount(0))) then self:save(true)end
    end
  elseif self.db.active then
    self.mode='recording';self.selected=self.db.active.session;self.take=self.db.active.take
    for i=0,reaper.CountMediaItems(0)-1 do
      local it=reaper.GetMediaItem(0,i)
      if M.ext(it,'ReaSetJamClick')==self.selected then self.jamClick=it end
    end
  end
  return self
end
return M
