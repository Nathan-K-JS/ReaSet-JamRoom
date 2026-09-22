-- Project extstate is not undoable in REAPER. An inert property on the existing
-- Lyrics utility track carries the chart snapshot through native track undo.
-- No media, routing, track level or monitoring is changed. GPL-3.0.
local dir=debug.getinfo(1,'S').source:match('@?(.*[\\/])') or ''
local J=dofile(dir..'ReaSet_JSON.lua')
local M={}
local function track(id)
  local _,owner=reaper.GetProjExtState(0,'ReaSetChartUndo','owner:'..id)
  if owner=='master' then return reaper.GetMasterTrack(0)end
  for i=0,reaper.CountTracks(0)-1 do
    local tr=reaper.GetTrack(0,i);local _,name=reaper.GetTrackName(tr)
    if name:lower():match('^%s*lyrics%s*$')then return tr end
  end
  return reaper.GetMasterTrack and reaper.GetMasterTrack(0) or nil
end
local function snapshot(id)
  local p='song:'..id..':'
  local data={}
  for _,key in ipairs({'document','revision','previous'})do local _,v=reaper.GetProjExtState(0,'ReaSetSong',p..key);data[key]=v end
  for _,key in ipairs({'lyrics','chords','lyrics:reviewed','chords:reviewed'})do local _,v=reaper.GetProjExtState(0,'ReaSetCLRepair',p..key);data['repair:'..key]=v end
  return data
end
function M.prepare(id)
  local tr=assert(track(id),'No project track is available for chart undo')
  if reaper.GetMasterTrack and tr==reaper.GetMasterTrack(0) then reaper.SetProjExtState(0,'ReaSetChartUndo','owner:'..id,'master')end
  local _,old=reaper.GetSetMediaTrackInfo_String(tr,'P_EXT:ReaSetChartUndo:'..id,'',false)
  if old=='' then reaper.SetProjExtState(0,'ReaSetChartUndo','baseline:'..id,J.encode(snapshot(id))) end
  return tr
end
function M.commit(id,tr)
  local value=J.encode(snapshot(id))
  reaper.GetSetMediaTrackInfo_String(tr,'P_EXT:ReaSetChartUndo:'..id,value,true)
  reaper.SetProjExtState(0,'ReaSetChartUndo','watch:'..id,value)
end
function M.sync(id)
  local tr=track(id);if not tr then return end
  local _,watch=reaper.GetProjExtState(0,'ReaSetChartUndo','watch:'..id)
  local _,baseline=reaper.GetProjExtState(0,'ReaSetChartUndo','baseline:'..id)
  if watch=='' and baseline=='' then return end
  local _,value=reaper.GetSetMediaTrackInfo_String(tr,'P_EXT:ReaSetChartUndo:'..id,'',false)
  if value==watch then return end
  local ok,data=pcall(J.decode,value~='' and value or baseline);if not ok or type(data)~='table' then return end
  local p='song:'..id..':'
  for key,v in pairs(data)do
    if key:sub(1,7)=='repair:' then reaper.SetProjExtState(0,'ReaSetCLRepair',p..key:sub(8),v)
    else reaper.SetProjExtState(0,'ReaSetSong',p..key,v)end
  end
  reaper.SetProjExtState(0,'ReaSetChartUndo','watch:'..id,value)
end
function M.sync_all()
  local ids={};local i=0
  while true do
    local ok,key=reaper.EnumProjExtState(0,'ReaSetChartUndo',i)
    if not ok then break end
    key=key:lower()
    local id=key:match('^watch:(%d+)$') or key:match('^baseline:(%d+)$')
    if id then ids[id]=true end;i=i+1
  end
  for id in pairs(ids)do M.sync(id)end
end
return M
