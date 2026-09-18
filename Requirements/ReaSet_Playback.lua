-- Persistent per-song stem trim. GPL-3.0.
local M = {}
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
  reaper.SetProjExtState(0,'ReaSetGain',song.key,tostring(gain))
  reaper.UpdateArrange()
end
function M.reconcile()
  local _,exported=reaper.GetProjExtState(0,'ReaSet','recordingProject')
  if exported=='1' then return end
  for _,song in ipairs(M.songs()) do M.apply(song,M.gain(song)) end
end
return M
