-- Persistent per-song stem trim. GPL-3.0.
local M = {}
local dir=debug.getinfo(1,'S').source:match('@?(.*[\\/])') or ''
local J=dofile(dir..'ReaSet_JSON.lua')
local slots = {DRUMS=true,PERC_FX=true,BASS=true,GTR1=true,GTR2=true,KEYS=true,BVS=true,LEAD_VOX=true,EXTRA=true,CLICK=true}
function M.songs()
  local all, songs = {}, {}
  local i=0
  while true do
    local ok,isr,s,e,name,id=reaper.EnumProjectMarkers2(0,i)
    if ok==0 then break end
    if isr and name~='ReaSet Loop' then
      local _,guid=reaper.GetSetProjectInfo_String(0,'MARKER_GUID:'..i,'',false)
      all[#all+1]={id=id,key=guid~='' and guid or tostring(id),name=name,start=s,finish=e}
    end
    i=i+1
  end
  for _,s in ipairs(all) do
    local nested=false
    for _,o in ipairs(all) do if o~=s and o.start<=s.start and o.finish>=s.finish and (o.start<s.start or o.finish>s.finish) then nested=true end end
    if not nested then songs[#songs+1]=s end
  end
  return songs
end
function M.items(song, include_click)
  if song.free then return {} end
  local out,stack,depth={}, {},0
  for i=0,reaper.CountTracks(0)-1 do
    local tr=reaper.GetTrack(0,i);local _,name=reaper.GetTrackName(tr)
    while #stack>0 and stack[#stack].depth>=depth do table.remove(stack) end
    local slot=name:match('^%s*%[%s*[Jj][Rr]%s*:%s*([%w_]+)%s*%]')
    slot=slot and slot:upper() or (#stack>0 and stack[#stack].slot)
    local _,rec=reaper.GetSetMediaTrackInfo_String(tr,'P_EXT:ReaSetRec','',false)
    if slot and slots[slot] and rec=='' then
      stack[#stack+1]={depth=depth,slot=slot}
      if include_click or slot~='CLICK' then
        for n=0,reaper.CountTrackMediaItems(tr)-1 do
          local it=reaper.GetTrackMediaItem(tr,n)
          local p=reaper.GetMediaItemInfo_Value(it,'D_POSITION');local len=reaper.GetMediaItemInfo_Value(it,'D_LENGTH')
          local take=reaper.GetActiveTake(it)
          if take and not reaper.TakeIsMIDI(take) and p>=song.start-.001 and p+len<=song.finish+.001 and p<song.finish then
            out[#out+1]={item=it,track=tr,slot=slot}
          end
        end
      end
    end
    depth=depth+reaper.GetMediaTrackInfo_Value(tr,'I_FOLDERDEPTH')
  end
  return out
end
function M.gain(song)
  local _,v=reaper.GetProjExtState(0,'ReaSetGain',song.key)
  return tonumber(v) or .65
end
function M.apply(song,gain)
  assert(type(gain)=='number' and gain==gain and gain>=0 and gain<=1,'Volume must be 0–100%')
  for _,row in ipairs(M.items(song,false)) do
    local it=row.item
    local _,saved=reaper.GetSetMediaItemInfo_String(it,'P_EXT:ReaSetGain','',false)
    local base,last=saved:match('^([^|]+)|([^|]+)$');base,last=tonumber(base),tonumber(last)
    local current=reaper.GetMediaItemInfo_Value(it,'D_VOL')
    if not base then base=current
    elseif last and math.abs(current-base*last)>.0000001 then
      -- Respect manual item-level changes instead of compounding our own gain.
      base=last>0 and current/last or current
    end
    local target=base*gain
    if math.abs(current-target)>.0000001 then reaper.SetMediaItemInfo_Value(it,'D_VOL',target) end
    local value=string.format('%.17g|%.17g',base,gain)
    if value~=saved then reaper.GetSetMediaItemInfo_String(it,'P_EXT:ReaSetGain',value,true) end
  end
end
function M.set(song,gain)
  M.apply(song,gain)
  reaper.SetProjExtState(0,'ReaSetGainMode',song.key,'manual')
  reaper.SetProjExtState(0,'ReaSetGain',song.key,tostring(gain))
  reaper.UpdateArrange()
end
function M.level(song)
  local _,raw=reaper.GetProjExtState(0,'ReaSetLevel',song.key)
  local ok,data=pcall(J.decode,raw)
  if not ok or type(data)~='table' then return nil end
  local _,mode=reaper.GetProjExtState(0,'ReaSetGainMode',song.key)
  data.manual=mode=='manual'
  return data
end
function M.match(song,data,replace)
  assert(type(data)=='table' and type(data.revision)=='string','Invalid level report')
  if data.status=='measured' then assert(type(data.gain)=='number' and data.gain==data.gain and data.gain>0 and data.gain<=1,'Invalid matched gain')end
  local _,mode=reaper.GetProjExtState(0,'ReaSetGainMode',song.key)
  local _,saved=reaper.GetProjExtState(0,'ReaSetGain',song.key)
  local manual=mode=='manual' or (mode=='' and saved~='' and math.abs((tonumber(saved) or .65)-.65)>.000001)
  if manual then reaper.SetProjExtState(0,'ReaSetGainMode',song.key,'manual')end
  local stored={};for k,v in pairs(data)do if k~='files' and k~='replace' and k~='manual' then stored[k]=v end end
  reaper.SetProjExtState(0,'ReaSetLevel',song.key,J.encode(stored))
  reaper.SetProjExtState(0,'ReaSetSong','song:'..song.id..':level',data.revision)
  if data.status=='measured' and (replace or not manual) then
    M.apply(song,data.gain)
    reaper.SetProjExtState(0,'ReaSetGain',song.key,tostring(data.gain))
    reaper.SetProjExtState(0,'ReaSetGainMode',song.key,'auto')
    return 'Matched playback level applied'
  end
  return manual and 'Manual playback level kept; suggestion saved' or 'No reliable level measurement; existing level kept'
end
function M.reconcile()
  local _,exported=reaper.GetProjExtState(0,'ReaSet','recordingProject')
  if exported=='1' then return end
  for _,song in ipairs(M.songs()) do M.apply(song,M.gain(song)) end
end
return M
