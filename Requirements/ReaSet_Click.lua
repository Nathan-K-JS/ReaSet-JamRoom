-- Owned click items: musical audio and the project tempo map stay untouched.
-- GPL-3.0
local M={}
function M.track(create)
  local parent,depth,last
  for i=0,reaper.CountTracks(0)-1 do
    local tr=reaper.GetTrack(0,i);local _,name=reaper.GetTrackName(tr)
    if name=='[JR:CLICK] Click' then return tr end
    if name=='PB CLICK' then parent=i end
  end
  if not create then return nil end
  assert(parent,'Missing PB CLICK bus; run Build buses first')
  local pb=reaper.GetTrack(0,parent)
  local fd=reaper.GetMediaTrackInfo_Value(pb,'I_FOLDERDEPTH')
  last=parent;depth=fd
  if fd==1 then
    while depth>0 and last+1<reaper.CountTracks(0) do
      last=last+1;depth=depth+reaper.GetMediaTrackInfo_Value(reaper.GetTrack(0,last),'I_FOLDERDEPTH')
    end
  end
  local ending=fd-1
  if fd==1 then
    local tr=reaper.GetTrack(0,last);ending=reaper.GetMediaTrackInfo_Value(tr,'I_FOLDERDEPTH')
    reaper.SetMediaTrackInfo_Value(tr,'I_FOLDERDEPTH',0)
  else reaper.SetMediaTrackInfo_Value(pb,'I_FOLDERDEPTH',1)end
  reaper.InsertTrackAtIndex(last+1,false)
  local tr=reaper.GetTrack(0,last+1)
  reaper.GetSetMediaTrackInfo_String(tr,'P_NAME','[JR:CLICK] Click',true)
  reaper.SetMediaTrackInfo_Value(tr,'I_FOLDERDEPTH',ending)
  return tr
end
function M.owned(item)
  local _,value=reaper.GetSetMediaItemInfo_String(item,'P_EXT:ReaSetClick','',false)
  return value=='1'
end
function M.install(track,source,start,duration,name)
  local item=reaper.AddMediaItemToTrack(track)
  reaper.SetMediaItemInfo_Value(item,'D_POSITION',start)
  reaper.SetMediaItemInfo_Value(item,'D_LENGTH',duration)
  local take=reaper.AddTakeToMediaItem(item);reaper.SetMediaItemTake_Source(take,source)
  reaper.GetSetMediaItemTakeInfo_String(take,'P_NAME',name..' - Click',true)
  reaper.GetSetMediaItemInfo_String(item,'P_EXT:ReaSetClick','1',true)
  return item
end
return M
