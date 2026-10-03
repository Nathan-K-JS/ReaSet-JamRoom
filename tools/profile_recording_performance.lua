-- Launched only by profile_recording_performance.py with newly generated data.
local folder=assert(PROFILE_FOLDER)
local root=folder..'/code'
local J=dofile(root..'/Requirements/ReaSet_JSON.lua')
local report={timings={},native=reaper.GetAppVersion()}
local isolated=false
local function read(path)local f=assert(io.open(path,'rb'));local s=f:read('*a');f:close();return s end
local function write_report()
  local f=assert(io.open(folder..'/result.json','wb'));f:write(J.encode(report));f:close()
end
local function timed(name,fn)
  report.stage=name;write_report()
  local start=reaper.time_precise();fn();report.timings[name]=reaper.time_precise()-start
  write_report()
end
local ok,why=xpcall(function()
  local resource=reaper.GetResourcePath():gsub('\\','/')
  assert(resource:lower()==(folder..'/resource'):lower(),'Private resource guard failed')
  local yes,device=reaper.GetAudioDeviceInfo('MODE')
  assert(yes and device=='Dummy Audio','Dummy Audio guard failed')
  local _,path=reaper.EnumProjects(-1,'')
  assert(path=='' and reaper.CountTracks(0)==0 and reaper.GetPlayState()==0,'Expected a fresh empty project')
  assert(not reaper.EnumProjects(1,''),'Unexpected second project')
  isolated=true;report.resource=resource;report.device=device
  assert(reaper.ULT_SetMediaItemNote,'Private SWS copy was not loaded')
  reaper.Main_openProject('noprompt:'..folder..'/dummy.RPP')
  local _,opened=reaper.EnumProjects(-1,'')
  assert(opened:gsub('\\','/'):lower()==(folder..'/dummy.RPP'):lower(),'Dummy project guard failed')
  assert(reaper.CountMediaItems(0)==8388,'Unexpected synthetic item count')
  report.items=reaper.CountMediaItems(0);report.tracks=reaper.CountTracks(0)
  -- Approximate the saved library's size without copying any user content.
  -- This exercises serialization cost; it does not simulate chart bridge work.
  reaper.SetProjExtState(0,'PerformanceFixture','padding',string.rep('dummy-data-',700000))
  local M=dofile(root..'/Requirements/ReaSet_RecordingCore.lua')
  local self=M.new()
  local function prepare()
    self.audition={}
    for i=0,reaper.CountMediaItems(0)-1 do
      local it=reaper.GetMediaItem(0,i);local _,guid=reaper.GetSetMediaItemInfo_String(it,'GUID','',false)
      self.audition[guid]=i%2;reaper.SetMediaItemInfo_Value(it,'B_MUTE',1)
    end
  end
  local function verify()
    for i=0,reaper.CountMediaItems(0)-1 do
      assert(reaper.GetMediaItemInfo_Value(reaper.GetMediaItem(0,i),'B_MUTE')==i%2,'Original mute not restored')
    end
    assert(next(self.audition)==nil,'Restoration journal not cleared')
  end
  prepare();timed('park_fixed',function()self:park()end);verify()
  prepare()
  local baseline=read(folder..'/baseline.lua')
  local first=assert(baseline:find('  function self:park()',1,true))
  local last=assert(baseline:find('  function self:setup()',first,true))
  local native=reaper;local calls=0;local deadline=native.time_precise()+15
  local proxy=setmetatable({GetMediaItem=function(...)
    calls=calls+1
    if calls%10000==0 then assert(native.time_precise()<deadline,'Baseline exceeded 15 second budget')end
    return native.GetMediaItem(...)
  end},{__index=native})
  local old={audition=self.audition,clear_timeline=function()self:clear_timeline()end,jam_clear_click=function()self:jam_clear_click()end}
  assert(load(baseline:sub(first,last-1),'baseline','t',setmetatable({self=old,M=M,reaper=proxy},{__index=_G})))()
  local start=native.time_precise()
  local completed,message=pcall(function()old:park()end)
  report.baseline={completed=completed,seconds=native.time_precise()-start,item_lookups=calls,error=message}
  -- The comparison may be bounded; always restore before measuring other work.
  self:park();verify()
  timed('save_project_and_verify',function()self:save(true)end)
  timed('save_project_and_verify_repeat',function()self:save(true)end)
  timed('backing_snapshot',function()reaper.Main_SaveProjectEx(0,folder..'/backing.RPP',0)end)
  timed('reconcile_library',function()M.P.reconcile()end)
  -- Time selected native Apply stages while running the real importer script.
  local totals={}
  for _,name in ipairs({'Undo_BeginBlock','Undo_EndBlock','PCM_Source_CreateFromFile','ULT_SetMediaItemNote','AddMediaItemToTrack','TrackList_AdjustWindows','UpdateArrange'})do
    local fn=reaper[name]
    reaper[name]=function(...)
      local t=reaper.time_precise();local out=table.pack(fn(...))
      local row=totals[name] or {calls=0,seconds=0};totals[name]=row
      row.calls=row.calls+1;row.seconds=row.seconds+reaper.time_precise()-t
      return table.unpack(out,1,out.n)
    end
  end
  timed('apply_import',function()dofile(root..'/tools/jamroom_import_apply.lua')end)
  assert(read(folder..'/job/applied.txt'):find('Synthetic import',1,true),'Apply did not confirm success')
  report.import_calls=totals
  timed('reconcile_after_import',function()M.P.reconcile()end)
  report.final_items=reaper.CountMediaItems(0)
  assert(report.final_items==8598,'Expected ten stems and 200 chart items')
  report.project_bytes=#read(folder..'/dummy.RPP')
  reaper.Main_SaveProject(0,false)
end,debug.traceback)
report.ok=ok;report.error=not ok and tostring(why) or nil;write_report()
if isolated and ok then reaper.Main_OnCommand(40004,0)end -- Quit only the validated private worker.
