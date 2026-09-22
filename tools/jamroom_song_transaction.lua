-- Replace/restore chart data and owned clicks with durable guarded snapshots.
-- GPL-3.0. Musical stems and song regions are never replaced.
local dir = debug.getinfo(1,"S").source:match("@?(.*[\\/])") or ""
local J = dofile(dir .. "../Requirements/ReaSet_JSON.lua")
local C = dofile(dir .. "../Requirements/ReaSet_Click.lua")
local P = dofile(dir .. "../Requirements/ReaSet_Playback.lua")
local ok, job = pcall(dofile, dir .. "jamroom_pending_rechord.lua")
if not ok or type(job) ~= "table" then return end
local function write(path, value)
  local f=assert(io.open(path .. ".tmp","wb")); f:write(value); f:close()
  os.remove(path); assert(os.rename(path .. ".tmp",path))
end
local function read(path)
  local f=assert(io.open(path,"rb")); local s=f:read("*a"); f:close(); return s
end
local function reply(status, message)
  if job.receipt then write(job.receipt,J.encode({operation=job.operation,status=status,message=tostring(message)})) end
  reaper.SetExtState("ReaSetJR","rechord",status .. ":" .. tostring(message),false)
end
local function run()
  assert(reaper.GetPlayState()==0,"Stop playback before updating song data")
  assert(reaper.ULT_SetMediaItemNote,"SWS extension is required")
  local _, project = reaper.GetProjExtState(0,"ReaSet","projectId")
  assert(project=='' or reaper.GetExtState('ReaSetRec','lock')~=project,'Choose Done in Recording before updating song data')
  assert(job.project and project==job.project,"Target project changed; refresh the song list")
  local song
  local i=0
  while true do
    local n,isr,s,e,name,id = reaper.EnumProjectMarkers2(0,i); if n==0 then break end
    if isr and id==job.id and name==job.region and math.abs(s-job.start)<.001 and math.abs(e-job["end"])<.001 then
      song={id=id,s=s,e=e}
    end
    i=i+1
  end
  assert(song,"Song identity or boundaries changed; refresh the song list")
  local prefix="song:" .. song.id .. ":"
  local restored=job.restore and J.decode(read(job.restore)) or nil
  local with_click=job.click or (restored and restored.items.click)
  local with_level=job.level or (restored and restored.level)
  local level_song
  if with_level then
    for _,s in ipairs(P.songs())do if s.id==song.id then level_song=s end end
    assert(level_song,'Cannot resolve playback level song')
  end
  if job.level and job.level.status=='measured' then
    local actual={}
    for _,r in ipairs(P.items(level_song,false))do
      assert(reaper.CountTakes(r.item)==1,'Backing takes changed; volume matching needs the original imported stems')
      local tk=reaper.GetActiveTake(r.item)
      local source=reaper.GetMediaItemTake_Source(tk)
      -- Cached-source loudness remains a useful suggestion after timing edits.
      -- Do not block chart/click updates or reset musical settings for this.
      local original_timing=math.abs(reaper.GetMediaItemInfo_Value(r.item,'D_POSITION')-level_song.start)<.001 and
        math.abs(reaper.GetMediaItemTakeInfo_Value(tk,'D_STARTOFFS'))<.001 and
        math.abs(reaper.GetMediaItemTakeInfo_Value(tk,'D_PLAYRATE')-1)<.00001 and
        math.abs(reaper.GetMediaItemInfo_Value(r.item,'D_LENGTH')-reaper.GetMediaSourceLength(source))<.02
      if not original_timing then job.level.source_timing_changed=true end
      local file=reaper.GetMediaSourceFileName(reaper.GetMediaItemTake_Source(tk),''):gsub('\\','/'):lower()
      actual[file]=(actual[file] or 0)+1
    end
    for _,file in ipairs(job.level.files or {})do
      file=file:gsub('\\','/'):lower();assert(actual[file] and actual[file]>0,'Backing files changed; refresh source stems before matching volume')
      actual[file]=actual[file]-1
    end
    for _,n in pairs(actual)do assert(n==0,'Backing selection differs from cached stems; volume was not changed')end
  end
  local _, previous_op = reaper.GetProjExtState(0,"ReaSetSong",prefix .. "operation")
  if previous_op == job.operation then reply("ok","Already applied"); return end
  if job.expected_revision~=nil then
    local _,rev=reaper.GetProjExtState(0,'ReaSetSong',prefix..'revision')
    assert(rev==job.expected_revision,'Chart changed since this review opened; reopen it before saving')
  end
  local tracks={}
  for ti=0,reaper.CountTracks(0)-1 do
    local tr=reaper.GetTrack(0,ti); local _,name=reaper.GetTrackName(tr)
    name=name:lower():gsub("^%s+",""):gsub("%s+$","")
    if name=="lyrics" or name=="chords" then
      assert(not tracks[name],"Duplicate " .. name .. " tracks")
      tracks[name]=tr
    end
  end
  for _, name in ipairs({"lyrics","chords"}) do assert(tracks[name],"Missing " .. name .. " track") end
  local function snapshot()
    local data={items={},ext={}}
    for _,name in ipairs({"lyrics","chords"}) do
      local list=J.array(); data.items[name]=list
      for ii=0,reaper.CountTrackMediaItems(tracks[name])-1 do
        local it=reaper.GetTrackMediaItem(tracks[name],ii)
        local p=reaper.GetMediaItemInfo_Value(it,"D_POSITION")
        local e=p+reaper.GetMediaItemInfo_Value(it,"D_LENGTH")
        if p<song.e and e>song.s then
          assert(p>=song.s-.001 and e<=song.e+.001,"Text item crosses a song boundary")
          assert(not reaper.GetActiveTake(it),"Audio/takes on utility tracks cannot be replaced")
          local success,chunk=reaper.GetItemStateChunk(it,"",false); assert(success,"Cannot snapshot text item")
          list[#list+1]=chunk
        end
      end
    end
    for _, field in ipairs({"document","revision","operation"}) do
      local _, v=reaper.GetProjExtState(0,"ReaSetSong",prefix .. field); data.ext[field]=v
    end
    for _,field in ipairs({"lyrics","chords","lyrics:reviewed","chords:reviewed"}) do
      local _,v=reaper.GetProjExtState(0,"ReaSetCLRepair",prefix .. field); data.ext["repair:" .. field]=v
    end
    if with_click then
      local _,value=reaper.GetProjExtState(0,'ReaSetSong',prefix..'click');data.ext.click=value
      data.items.click=J.array()
      local track=C.track(false)
      for i=0,(track and reaper.CountTrackMediaItems(track) or 0)-1 do
        local item=reaper.GetTrackMediaItem(track,i)
        local p=reaper.GetMediaItemInfo_Value(item,'D_POSITION')
        local e=p+reaper.GetMediaItemInfo_Value(item,'D_LENGTH')
        if p<song.e and e>song.s then
          assert(p>=song.s-.001 and e<=song.e+.001 and C.owned(item),'Existing click is not owned by the importer; keep it')
          local ok,chunk=reaper.GetItemStateChunk(item,'',false);assert(ok);table.insert(data.items.click,chunk)
        end
      end
    end
    if with_level then
      data.level={ext={},items={}}
      for _,sec in ipairs({'ReaSetGain','ReaSetGainMode','ReaSetLevel'})do
        local _,v=reaper.GetProjExtState(0,sec,level_song.key);data.level.ext[sec]=v
      end
      local _,v=reaper.GetProjExtState(0,'ReaSetSong',prefix..'level');data.level.revision=v
      for _,r in ipairs(P.items(level_song,false))do
        local _,g=reaper.GetSetMediaItemInfo_String(r.item,'GUID','',false)
        local _,tag=reaper.GetSetMediaItemInfo_String(r.item,'P_EXT:ReaSetGain','',false)
        data.level.items[g]={gain=reaper.GetMediaItemInfo_Value(r.item,'D_VOL'),tag=tag}
      end
    end
    return data
  end
  local before=snapshot()
  if job.expected then
    local expected=J.decode(read(job.expected))
    local comparison=J.decode(J.encode(before))
    if not expected.items.click then comparison.items.click=nil end
    if expected.ext.click==nil then comparison.ext.click=nil end
    if not restored then comparison.level=nil;expected.level=nil end
    assert(J.encode(comparison)==J.encode(expected),"Song was edited since this revision; keep it or explicitly rebuild")
  end
  local click_source
  if job.click then
    assert(type(job.click.file)=='string' and type(job.click.revision)=='string','Invalid click request')
    click_source=reaper.PCM_Source_CreateFromFile(job.click.file)
    if click_source and reaper.GetMediaSourceLength(click_source)<song.e-song.s-.02 then
      reaper.PCM_Source_Destroy(click_source);click_source=nil
    end
    assert(click_source,'Click audio is missing or too short')
  end
  if not restored then
    for _,name in ipairs({"lyrics","chords"}) do
      for _,event in ipairs(job[name] or {}) do
        assert(type(event.s)=="number" and type(event.e)=="number" and event.s>=0 and
          event.e>event.s and event.e<=song.e-song.s+.001,"Invalid " .. name .. " timing")
      end
    end
    if job.document then
      local doc=J.decode(job.document); assert(doc.schema==2 and type(doc.sections)=="table","Invalid chart document")
    end
  end
  write(job.before,J.encode(before)) -- durable before any project mutation
  local function clear(name)
    local tr=tracks[name]
    for ii=reaper.CountTrackMediaItems(tr)-1,0,-1 do
      local it=reaper.GetTrackMediaItem(tr,ii); local p=reaper.GetMediaItemInfo_Value(it,"D_POSITION")
      if p>=song.s-.001 and p<song.e then reaper.DeleteTrackMediaItem(tr,it) end
    end
  end
  local function install_snapshot(data)
    if data.level then
      for sec,v in pairs(data.level.ext)do reaper.SetProjExtState(0,sec,level_song.key,v)end
      reaper.SetProjExtState(0,'ReaSetSong',prefix..'level',data.level.revision)
      for _,r in ipairs(P.items(level_song,false))do
        local _,g=reaper.GetSetMediaItemInfo_String(r.item,'GUID','',false)
        local old=data.level.items[g];assert(old,'Backing items changed; cannot restore playback level')
        reaper.SetMediaItemInfo_Value(r.item,'D_VOL',old.gain)
        reaper.GetSetMediaItemInfo_String(r.item,'P_EXT:ReaSetGain',old.tag,true)
      end
    end
    for _,name in ipairs({"lyrics","chords"}) do
      clear(name)
      for _,chunk in ipairs(data.items[name]) do
        local it=reaper.AddMediaItemToTrack(tracks[name]); assert(reaper.SetItemStateChunk(it,chunk,false),"Cannot restore text item")
      end
    end
    for field,v in pairs(data.ext) do
      local repair=field:match("^repair:(.*)")
      reaper.SetProjExtState(0,repair and "ReaSetCLRepair" or "ReaSetSong",prefix .. (repair or field),v)
    end
    if data.items.click then
      local track=C.track(#data.items.click>0)
      if track then
        for i=reaper.CountTrackMediaItems(track)-1,0,-1 do
          local item=reaper.GetTrackMediaItem(track,i);local p=reaper.GetMediaItemInfo_Value(item,'D_POSITION')
          if p>=song.s-.001 and p<song.e and C.owned(item) then reaper.DeleteTrackMediaItem(track,item)end
        end
        for _,chunk in ipairs(data.items.click) do
          local item=reaper.AddMediaItemToTrack(track);assert(reaper.SetItemStateChunk(item,chunk,false))
        end
      end
    end
  end
  local chart_undo=dofile(dir..'../Requirements/ReaSet_ChartUndo.lua')
  local restored_chart=restored and (restored.ext.document~=before.ext.document or restored.ext.revision~=before.ext.revision)
  local undo_track=(job.document or restored_chart) and chart_undo.prepare(song.id) or nil
  reaper.Undo_BeginBlock(); reaper.PreventUIRefresh(1)
  local level_message
  local success,err=pcall(function()
    if restored then install_snapshot(restored)
    else
      for _,name in ipairs({"lyrics","chords"}) do
        if job[name] then
          clear(name)
          for _,event in ipairs(job[name]) do
            local it=reaper.AddMediaItemToTrack(tracks[name])
            reaper.SetMediaItemInfo_Value(it,"D_POSITION",song.s+event.s)
            reaper.SetMediaItemInfo_Value(it,"D_LENGTH",event.e-event.s)
            reaper.ULT_SetMediaItemNote(it,event.name or event.text or "")
          end
          for _,suffix in ipairs({"",":reviewed"}) do
            reaper.SetProjExtState(0,"ReaSetCLRepair",prefix .. name .. suffix,"")
          end
        end
      end
      if job.level then
        level_message=P.match(level_song,job.level,job.level.replace)
        if job.level.source_timing_changed then
          level_message=level_message..'; estimated from cached stems (backing timing differs)'
        end
      end
      if job.document then
        local _,old_document=reaper.GetProjExtState(0,'ReaSetSong',prefix..'document')
        reaper.SetProjExtState(0,'ReaSetSong',prefix..'previous',old_document)
        reaper.SetProjExtState(0,"ReaSetSong",prefix .. "document",job.document)
        reaper.SetProjExtState(0,"ReaSetSong",prefix .. "revision",job.revision or "")
      end
      if job.click then
        local track=C.track(true)
        for i=reaper.CountTrackMediaItems(track)-1,0,-1 do
          local item=reaper.GetTrackMediaItem(track,i);local p=reaper.GetMediaItemInfo_Value(item,'D_POSITION')
          if p>=song.s-.001 and p<song.e and C.owned(item) then reaper.DeleteTrackMediaItem(track,item)end
        end
        C.install(track,click_source,song.s,song.e-song.s,job.region,job.click.muted);click_source=nil
        reaper.SetProjExtState(0,'ReaSetSong',prefix..'click',job.click.revision)
      end
    end
    reaper.SetProjExtState(0,"ReaSetSong",prefix .. "operation",job.operation)
    if undo_track then chart_undo.commit(song.id,undo_track)end
    write(job.after,J.encode(snapshot()))
  end)
  if not success then
    local recovered,why=pcall(install_snapshot,before)
    if not recovered then err=tostring(err) .. "; restore from " .. job.before .. ": " .. tostring(why) end
  end
  reaper.PreventUIRefresh(-1); reaper.TrackList_AdjustWindows(false); reaper.UpdateArrange(); reaper.MarkProjectDirty(0)
  if click_source then reaper.PCM_Source_Destroy(click_source)end
  reaper.Undo_EndBlock((restored and "Restore" or "Update") .. (job.click and " chart/click: " or " lyrics & chords: ") .. job.region,-1)
  assert(success,err)
  if level_message then reply("ok",level_message);return end
  reply("ok",restored and "Previous song version restored" or job.click and (job.document and "Chart and click updated" or "Click updated; chart preserved") or "Lyrics and chords updated")
end
local success,err=pcall(run)
if not success then reply("error",err); reaper.ShowConsoleMsg("[JamRoom update] " .. tostring(err) .. "\n") end
