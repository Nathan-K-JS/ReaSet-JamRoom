-- Independent performances, arrangements and saved playback balance. GPL-3.0.
return function(M)
function M.part_track(self,p)
  local tracks=M.tracks();local tr=tracks[p.id]
  if tr then return tr end
  reaper.InsertTrackAtIndex(reaper.CountTracks(0),false)
  tr=reaper.GetTrack(0,reaper.CountTracks(0)-1)
  M.ext(tr,'ReaSetRec',p.id,true)
  reaper.GetSetMediaTrackInfo_String(tr,'P_NAME','REC '..p.name,true)
  reaper.SetMediaTrackInfo_Value(tr,'D_VOL',p.baseGain or 1)
  reaper.SetMediaTrackInfo_Value(tr,'B_MAINSEND',0)
  reaper.SetMediaTrackInfo_Value(tr,'I_RECMON',0)
  reaper.SetMediaTrackInfo_Value(tr,'I_RECARM',0)
  reaper.SetMediaTrackInfo_Value(tr,'I_RECINPUT',p.channel | (p.stereo and 1024 or 0))
  local send=reaper.CreateTrackSend(tr,nil)
  reaper.SetTrackSendInfo_Value(tr,1,send,'I_DSTCHAN',p.output | (p.outStereo and 0 or 1024))
  return tr
end
function M.parts(self,s,t,parent,metadata_only)
  s.parts=s.parts or {};t.dest=t.dest or {};t.layers=t.layers or M.J.array();t.mix=t.mix or {}
  if parent and not t.parent then
    t.parent=parent.id;t.limit=parent.duration;t.backingOn=parent.backingOn;t.recordingOn=parent.recordingOn
    t.stemMutes=M.J.decode(M.J.encode(parent.stemMutes or {}))
    for _,id in ipairs(parent.layers)do t.layers[#t.layers+1]=id;t.mix[id]=M.J.decode(M.J.encode(parent.mix[id] or {gain=1}))end
  end
  for _,input in ipairs(t.inputs)do
    if not t.dest[input] then
      local cfg;for _,v in ipairs(self.db.inputs)do if v.id==input then cfg=v end end
      assert(cfg,'Recording input missing from setup')
      local id='part_'..t.id..'_'..input;local n=1
      for _,p in pairs(s.parts)do if p.input==input then n=n+1 end end
      local source=M.tracks()[input];local base=source and reaper.GetMediaTrackInfo_Value(source,'D_VOL') or 1
      s.parts[id]={baseGain=base,id=id,input=input,take=t.id,name=cfg.name..(n>1 and (' ('..n..')') or ''),channel=cfg.input,stereo=cfg.stereo,output=cfg.output,outStereo=cfg.outStereo}
      t.dest[input]=id;t.layers[#t.layers+1]=id;t.mix[id]={gain=1}
    end
  end
  if metadata_only then for _,r in ipairs(t.items)do r.track=t.dest[r.track] or r.track end;return end
  if self.root then self:save(false)end -- Durable destinations precede track creation/moves.
  local present={};M.owned_items(function(it)local _,g=reaper.GetSetMediaItemInfo_String(it,'GUID','',false);present[g]=it end)
  for _,id in pairs(t.dest)do M.part_track(self,s.parts[id])end
  for _,r in ipairs(t.items)do
    r.track=t.dest[r.track] or r.track
    local it=present[r.guid];local tr=M.tracks()[r.track]
    if it and tr and reaper.GetMediaItem_Track(it)~=tr then reaper.MoveMediaItemToTrack(it,tr)end
  end
end
function M.arrangement(self,s,t)
  local rows=M.J.array();local allowed={}
  for _,id in ipairs(t.layers or {})do allowed[id]=true end
  for _,pass in ipairs(s.takes)do for _,r in ipairs(pass.items)do if allowed[r.track] then
    assert(not pass.unresolved,'Recover interrupted parts before listening or exporting')
    rows[#rows+1]=r
  end end end
  return rows,allowed
end
function M.mix_take(self)
  local s=self:session(self.selected)
  for _,t in ipairs(s.takes)do if t.id==self.take then return s,t end end
  error('Select a saved take')
end
function M.load_mix(self,t)
  self.backingOn=t.backingOn~=false;self.recordingOn=t.recordingOn~=false
  self.stemMutes=t.stemMutes or {};self.recMutes={}
end
function M.save_mix(self)
  local _,t=M.mix_take(self)
  t.backingOn=self.backingOn;t.recordingOn=self.recordingOn;t.stemMutes=self.stemMutes
  self:save(false)
end
function M.remove_empty_parts(s,ids)
  local tracks=M.tracks()
  for _,id in pairs(ids or {})do
    local tr=tracks[id]
    if tr and reaper.CountTrackMediaItems(tr)==0 then reaper.DeleteTrack(tr)end
  end
end
end
