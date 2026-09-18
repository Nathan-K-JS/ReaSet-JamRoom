-- Export in a scratch tab, verify all media before removing any source items.
-- GPL-3.0. Returns an installer to share the recording core's IO/ownership helpers.
return function(M)
local reaper=reaper
local function copy_verified(src,dst)
  local input=assert(io.open(src,'rb'),'Missing audio: '..src)
  local output=assert(io.open(dst..'.new','wb'),'Cannot create export audio')
  while true do local data=input:read(1024*1024);if not data then break end;assert(output:write(data))end
  input:close();assert(output:close())
  input=assert(io.open(src,'rb'));output=assert(io.open(dst..'.new','rb'))
  local same=true
  while true do local a,b=input:read(1024*1024),output:read(1024*1024);if a~=b then same=false;break end;if not a then break end end
  input:close();output:close();assert(same,'Audio verification failed: '..src)
  assert(not M.read(dst),'Export destination already exists')
  assert(os.rename(dst..'.new',dst),'Cannot finish media copy')
end
function M.export(self,s)
  assert(not s.deleted,'Restore the deleted session before exporting')
  assert(not s.exported,'This session is already exported: '..tostring(s.exported))
  local kept=0
  for _,t in ipairs(s.takes)do if t.status~='discarded' then assert(not t.unresolved,'Recover interrupted audio in REAPER before exporting');kept=kept+#t.items end end
  assert(kept>0,'No recorded media to export')
  local original=reaper.EnumProjects(-1,'')
  local folder=self.root..'/Exports/'..s.id..'-'..M.guid():sub(1,6)
  reaper.RecursiveCreateDirectory(folder..'/Media',0)
  local scratch,expected=nil,{}
  local exported=folder..'/Recording.RPP'
  local ok,why=xpcall(function()
    reaper.Main_OnCommand(40859,0);scratch=reaper.EnumProjects(-1,'')
    assert(scratch~=original,'Could not create export tab')
    reaper.Main_openProject('noprompt:'..s.folder..'/backing.RPP')
    reaper.SetProjExtState(0,'ReaSet','recordingProject','1')
    reaper.SetProjExtState(0,'ReaSet','projectId',M.guid())
    reaper.SetProjExtState(0,'ReaSetTK','applied','')
    reaper.SetProjExtState(0,'ReaSetRec','index','')
    reaper.SetProjExtState(0,'ReaSetRec','audition','')
    reaper.SetProjExtState(0,'ReaSetRec','auditionOptions','')
    local allowed={}
    for _,r in ipairs(M.P.items(s.song,true))do allowed[r.item]=true end
    for i=reaper.CountMediaItems(0)-1,0,-1 do
      local it=reaper.GetMediaItem(0,i)
      if not allowed[it] then reaper.DeleteTrackMediaItem(reaper.GetMediaItem_Track(it),it)
      else reaper.SetMediaItemInfo_Value(it,'D_POSITION',reaper.GetMediaItemInfo_Value(it,'D_POSITION')-s.song.start)end
    end
    -- Keep the original bus tree/FX/routing, with only this song's media.
    local tracks=M.tracks();local latest
    for _,t in ipairs(s.takes)do if t.status~='discarded' then latest=t.id end end
    for _,t in ipairs(s.takes)do if t.status~='discarded' then
      for _,r in ipairs(t.items)do
        local tr=assert(tracks[r.track],'Recording track missing from backing snapshot')
        local it=reaper.AddMediaItemToTrack(tr)
        assert(reaper.SetItemStateChunk(it,r.chunk,false),'Could not recreate recorded take')
        reaper.SetMediaItemInfo_Value(it,'D_POSITION',reaper.GetMediaItemInfo_Value(it,'D_POSITION')-s.song.start)
        reaper.SetMediaItemInfo_Value(it,'B_MUTE',t.id==latest and 0 or 1)
        local tk=reaper.GetActiveTake(it)
        if tk then reaper.GetSetMediaItemTakeInfo_String(tk,'P_NAME',t.name and t.name~='' and t.name or 'Take '..t.number,true)end
        reaper.SetMediaTrackInfo_Value(tr,'I_RECARM',0)
        reaper.SetMediaTrackInfo_Value(tr,'I_RECMON',0)
      end
    end end
    for _,tr in pairs(tracks)do reaper.SetMediaTrackInfo_Value(tr,'I_RECARM',0);reaper.SetMediaTrackInfo_Value(tr,'I_RECMON',0)end
    local copies={}
    for i=0,reaper.CountMediaItems(0)-1 do
      local it=reaper.GetMediaItem(0,i)
      for n=0,reaper.CountTakes(it)-1 do
        local take=reaper.GetTake(it,n)
        if not reaper.TakeIsMIDI(take) then
          local source=reaper.GetMediaItemTake_Source(take)
          assert(not reaper.GetMediaSourceParent(source),'Nested/section audio source needs manual REAPER export; session retained')
          local src=reaper.GetMediaSourceFileName(source,'')
          assert(src~='','Non-file source needs manual REAPER export; session retained')
          if not copies[src] then
            local name=src:match('[^/\\]+$') or 'audio.wav'
            local dest=folder..'/Media/'..M.guid():sub(1,8)..'-'..name
            copy_verified(src,dest);copies[src]=dest
          end
          local replacement=assert(reaper.PCM_Source_CreateFromFile(copies[src]),'Cannot reopen copied media')
          reaper.SetMediaItemTake_Source(take,replacement)
        end
      end
      local row={position=reaper.GetMediaItemInfo_Value(it,'D_POSITION'),length=reaper.GetMediaItemInfo_Value(it,'D_LENGTH'),takes=reaper.CountTakes(it),audio={}}
      for n=0,reaper.CountTakes(it)-1 do
        local tk=reaper.GetTake(it,n);row.audio[n+1]={}
        for _,key in ipairs({'D_PLAYRATE','D_PITCH','D_STARTOFFS'})do row.audio[n+1][key]=reaper.GetMediaItemTakeInfo_Value(tk,key)end
      end
      expected[#expected+1]=row
    end
    local tempo={};local num,den,bpm=reaper.TimeMap_GetTimeSigAtTime(0,s.song.start)
    for i=0,reaper.CountTempoTimeSigMarkers(0)-1 do
      local yes,pos,measure,beat,b,n,d,linear=reaper.GetTempoTimeSigMarker(0,i)
      if yes and pos>s.song.start and pos<s.song.finish then tempo[#tempo+1]={pos-s.song.start,b,n,d,linear}end
    end
    for i=reaper.CountTempoTimeSigMarkers(0)-1,0,-1 do reaper.DeleteTempoTimeSigMarker(0,i)end
    reaper.SetTempoTimeSigMarker(0,-1,0,-1,-1,bpm,num,den,false)
    for _,t in ipairs(tempo)do reaper.SetTempoTimeSigMarker(0,-1,t[1],-1,-1,t[2],t[3],t[4],t[5])end
    local markers={};local i=0
    while true do local n,isr,pos,e,name,id=reaper.EnumProjectMarkers2(0,i);if n==0 then break end;markers[#markers+1]={id,isr};i=i+1 end
    for _,r in ipairs(markers)do reaper.DeleteProjectMarker(0,r[1],r[2])end
    reaper.AddProjectMarker2(0,true,0,s.song.finish-s.song.start,s.song.name,-1,0)
    reaper.CSurf_OnPlayRateChange(s.rate)
    reaper.GetSetProjectInfo_String(0,'RECORD_PATH','Media',true)
    reaper.GetSetProjectInfo_String(0,'RECORD_PATH_SECONDARY','',true)
    reaper.GetSetRepeat(0);reaper.SetEditCurPos(0,false,false)
    reaper.Main_SaveProjectEx(0,exported,8)
    assert(M.read(exported),'Export project was not saved')
    reaper.Main_openProject('noprompt:'..exported)
    assert(math.abs(reaper.Master_GetPlayRate(0)-s.rate)<.00001,'Export playback rate verification failed')
    assert(reaper.CountMediaItems(0)==#expected,'Export item count verification failed')
    for i=0,reaper.CountMediaItems(0)-1 do
      local it=reaper.GetMediaItem(0,i);local e=expected[i+1]
      assert(math.abs(reaper.GetMediaItemInfo_Value(it,'D_POSITION')-e.position)<.00001 and math.abs(reaper.GetMediaItemInfo_Value(it,'D_LENGTH')-e.length)<.00001 and reaper.CountTakes(it)==e.takes,'Export alignment verification failed')
      for n=0,reaper.CountTakes(it)-1 do
        local tk=reaper.GetTake(it,n)
        for key,value in pairs(e.audio[n+1])do assert(math.abs(reaper.GetMediaItemTakeInfo_Value(tk,key)-value)<.00001,'Export take timing/pitch verification failed')end
        if not reaper.TakeIsMIDI(tk)then
          local file=reaper.GetMediaSourceFileName(reaper.GetMediaItemTake_Source(tk),'')
          assert(file:gsub('\\','/'):sub(1,#folder+7)==folder..'/Media/','Export still references external media')
          local f=assert(io.open(file,'rb'),'Export media missing');f:close()
        end
      end
    end
  end,debug.traceback)
  if scratch and reaper.ValidatePtr(scratch,'ReaProject*')then
    reaper.SelectProjectInstance(scratch)
    -- Save failed scratch work too, without touching the original snapshot.
    reaper.Main_SaveProjectEx(scratch,ok and exported or folder..'/Incomplete.RPP',8)
    reaper.Main_OnCommand(40860,0)
  end
  reaper.SelectProjectInstance(original)
  assert(ok,why)
  -- Durable receipt precedes cleanup. Verify current items still equal the
  -- saved take chunks before removing anything from the library.
  local known={}
  for _,t in ipairs(s.takes)do for _,r in ipairs(t.items)do known[r.guid]=r.chunk end end
  M.owned_items(function(it,_,tag)
    if tag:sub(1,#s.id+1)==s.id..'/' then
      local _,g=reaper.GetSetMediaItemInfo_String(it,'GUID','',false)
      local yes,chunk=reaper.GetItemStateChunk(it,'',false)
      assert(yes and M.samechunk(known[g],chunk),'Recording changed since it was saved; export created, setlist retained')
    end
  end)
  s.exported=exported;self:save(false);self:remove_session(s)
  self.message='Saved recording project: '..exported
end
end
