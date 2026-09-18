-- Freeze a listening request without opening tabs or changing the live mix.
-- Audio is retained by recording cleanup; the worker secures its own media copy.
-- GPL-3.0.
return function(M)
local dir=debug.getinfo(1,'S').source:match('@?(.*[\\/])') or ''
local guard=dofile(dir..'ReaSet_ListeningSafety.lua')
function M.make_listening(self,c)
  assert(reaper.GetPlayState()==0,'Stop listening or playback before making a copy')
  local s=self:session(c.session);local take
  for _,t in ipairs(s.takes)do if t.id==c.take then take=t end end
  assert(not s.deleted and take and take.status~='discarded' and not take.unresolved and #take.items>0,'Choose a saved, recovered take')
  assert(type(c.nonce)=='string' and c.nonce:match('^[%w_-]+$') and #c.nonce<100,'Invalid request identity')
  local folder=self.root..'/Listening/'..c.nonce
  if M.read(folder..'/request.json') then return end -- durable idempotency
  local same=self.selected==s.id and self.take==take.id and self.mode=='review'
  local request={version=1,id=c.nonce,project=self.id,session=s.id,take=take.id,
    title=s.song.name..' - '..(take.name and take.name~='' and take.name or 'Take '..take.number),
    created=os.date('%Y-%m-%d %H:%M'),song=s.song,rate=s.rate,items=take.items,
    duration=take.duration,inputs=self.db.inputs,pitches=s.pitches or {},
    backing=c.backing==true and not s.song.free,recording=not same or self.recordingOn~=false,
    recMutes=same and self.recMutes or {},stemMutes=same and self.stemMutes or {},
    stems=M.J.array()}
  guard(reaper.GetMasterTrack(0))
  if not s.exported then
    local captured={};request.items=M.J.array()
    M.owned_items(function(it,tr,tag)
      if tag==s.id..'/'..take.id then
        guard(tr)
        local _,guid=reaper.GetSetMediaItemInfo_String(it,'GUID','',false)
        local yes,chunk=reaper.GetItemStateChunk(it,'',false);assert(yes,'Cannot snapshot recorded item')
        request.items[#request.items+1]={guid=guid,track=M.ext(tr,'ReaSetRec',nil,true),chunk=chunk}
        captured[guid]=true
      end
    end)
    for _,r in ipairs(take.items)do assert(captured[r.guid],'Recorded items changed or are missing; recover the take first')end
  end
  -- Freeze current backing item settings when the original song is still here.
  -- Archived sessions whose song moved use their saved backing snapshot instead.
  local found
  for _,song in ipairs(M.P.songs())do
    if song.key==s.song.key and math.abs(song.start-s.song.start)<.001 and math.abs(song.finish-s.song.finish)<.001 then found=true end
  end
  if found and request.backing then
    request.liveStems=true
    for _,r in ipairs(M.P.items(s.song,false))do
      guard(r.track)
      local _,g=reaper.GetSetMediaItemInfo_String(r.item,'GUID','',false)
      local yes,chunk=reaper.GetItemStateChunk(r.item,'',false);assert(yes,'Cannot snapshot backing')
      local muted=reaper.GetMediaItemInfo_Value(r.item,'B_MUTE')
      if same and self.audition[g]~=nil then muted=self.audition[g]end
      local tr=r.track
      while tr do
        if reaper.GetMediaTrackInfo_Value(tr,'B_MUTE')~=0 then muted=1 end
        tr=reaper.GetParentTrack(tr)
      end
      request.stems[#request.stems+1]={guid=g,slot=r.slot,chunk=chunk,muted=muted}
    end
  end
  reaper.RecursiveCreateDirectory(folder,0)
  M.write(folder..'/source.RPP',assert(M.read(s.folder..'/backing.RPP'),'Backing snapshot missing; source recordings retained'))
  -- request.json is the commit marker; source snapshot is complete before discovery.
  M.write(folder..'/request.json',M.J.encode(request))
  reaper.SetProjExtState(0,'ReaSetRec','listeningRoot',self.root..'/Listening')
  self:save(false)
  self.message='Listening copy queued. Open Listening copies to follow progress and share.'
end
end
