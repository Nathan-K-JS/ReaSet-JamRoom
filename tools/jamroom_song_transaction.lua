-- Replace/restore chart data and owned clicks with durable guarded snapshots.
-- GPL-3.0. Musical stems and song regions are never replaced.
local dir = debug.getinfo(1,"S").source:match("@?(.*[\\/])") or ""
local J = dofile(dir .. "../Requirements/ReaSet_JSON.lua")
local C = dofile(dir .. "../Requirements/ReaSet_Click.lua")
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
  local _, previous_op = reaper.GetProjExtState(0,"ReaSetSong",prefix .. "operation")
  if previous_op == job.operation then reply("ok","Already applied"); return end
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
    return data
  end
  local before=snapshot()
  if job.expected then
    local expected=J.decode(read(job.expected))
    local comparison=J.decode(J.encode(before))
    if not expected.items.click then comparison.items.click=nil end
    if expected.ext.click==nil then comparison.ext.click=nil end
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
  reaper.Undo_BeginBlock(); reaper.PreventUIRefresh(1)
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
      if job.document then
        reaper.SetProjExtState(0,"ReaSetSong",prefix .. "document",job.document)
        reaper.SetProjExtState(0,"ReaSetSong",prefix .. "revision",job.revision or "")
      end
      if job.click then
        local track=C.track(true)
        for i=reaper.CountTrackMediaItems(track)-1,0,-1 do
          local item=reaper.GetTrackMediaItem(track,i);local p=reaper.GetMediaItemInfo_Value(item,'D_POSITION')
          if p>=song.s-.001 and p<song.e and C.owned(item) then reaper.DeleteTrackMediaItem(track,item)end
        end
        C.install(track,click_source,song.s,song.e-song.s,job.region);click_source=nil
        reaper.SetProjExtState(0,'ReaSetSong',prefix..'click',job.click.revision)
      end
    end
    reaper.SetProjExtState(0,"ReaSetSong",prefix .. "operation",job.operation)
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
  reply("ok",restored and "Previous song version restored" or job.click and (job.document and "Chart and click updated" or "Click updated; chart preserved") or "Lyrics and chords updated")
end
local success,err=pcall(run)
if not success then reply("error",err); reaper.ShowConsoleMsg("[JamRoom update] " .. tostring(err) .. "\n") end
