-- One native Record transport for lead-in, accompaniment and capture. GPL-3.0.
-- A temporary area beyond library media avoids negative time and preceding songs.
return function(self,M)
  function self:clear_timeline()
    for i=reaper.CountMediaItems(0)-1,0,-1 do
      local it=reaper.GetMediaItem(0,i)
      if M.ext(it,'ReaSetRecPreview')~='' then reaper.DeleteTrackMediaItem(reaper.GetMediaItem_Track(it),it)end
    end
  end
  function self:prepare_timeline(s,t)
    self:clear_timeline()
    local num,den,bpm=reaper.TimeMap_GetTimeSigAtTime(0,s.song.start)
    local _,detected=reaper.GetProjExtState(0,'ReaSetTK','bpm:'..s.song.name)
    bpm=tonumber(detected) or bpm
    if s.song.free then num=s.song.beats;den=4;bpm=s.song.bpm end
    local beat=60/bpm*4/den;local lead=self.db.countin and 2*num*beat or 0
    assert(lead>=0 and lead<120,'Unsupported count-in duration')
    local origin=reaper.GetProjectLength(0)+10+lead
    t.origin=origin;t.leadin=lead
    self.db.active.origin=origin
    -- Journal coordinates and original mutes before temporary items are created.
    for i=0,reaper.CountMediaItems(0)-1 do
      local it=reaper.GetMediaItem(0,i);local _,g=reaper.GetSetMediaItemInfo_String(it,'GUID','',false)
      if M.ext(it,'ReaSetRec')=='' and M.ext(it,'ReaSetJamClick')=='' then self.audition[g]=reaper.GetMediaItemInfo_Value(it,'B_MUTE')end
    end
    reaper.SetProjExtState(0,'ReaSetRec','audition',M.J.encode(self.audition));self:save(true)
    local function clone(it,tr,muted,backing)
      local _,chunk=reaper.GetItemStateChunk(it,'',false)
      local copy=reaper.AddMediaItemToTrack(tr);assert(reaper.SetItemStateChunk(copy,chunk,false))
      reaper.GetSetMediaItemInfo_String(copy,'GUID',reaper.genGuid(),true)
      for n=0,reaper.CountTakes(copy)-1 do
        local tk=reaper.GetTake(copy,n);local _,guid=reaper.GetSetMediaItemTakeInfo_String(tk,'GUID','',false)
        if backing and (s.pitches or {})[guid]then reaper.SetMediaItemTakeInfo_Value(tk,'D_PITCH',s.pitches[guid])end
        reaper.GetSetMediaItemTakeInfo_String(tk,'GUID',reaper.genGuid(),true)
      end
      M.ext(copy,'ReaSetRec','');M.ext(copy,'ReaSetRecPreview',t.id)
      reaper.SetMediaItemInfo_Value(copy,'D_POSITION',reaper.GetMediaItemInfo_Value(it,'D_POSITION')+origin-s.song.start)
      reaper.SetMediaItemInfo_Value(copy,'C_BEATATTACHMODE',0)
      reaper.SetMediaItemInfo_Value(copy,'B_MUTE',muted and 1 or 0)
    end
    for _,r in ipairs(M.P.items(s.song,true))do
      clone(r.item,r.track,self.backingOn==false or (self.stemMutes or {})[r.slot] or reaper.GetMediaItemInfo_Value(r.item,'B_MUTE')~=0,true)
    end
    local _,allowed=M.arrangement(self,s,t)
    local parts={};M.owned_items(function(it,tr)if allowed[M.ext(tr,'ReaSetRec',nil,true)] then parts[#parts+1]={it,tr}end end)
    for _,r in ipairs(parts)do
      local id=M.ext(r[2],'ReaSetRec',nil,true);local mix=t.mix[id] or {gain=1}
      reaper.SetMediaTrackInfo_Value(r[2],'D_VOL',(s.parts[id].baseGain or 1)*mix.gain)
      clone(r[1],r[2],self.recordingOn==false or mix.muted)
    end
    for i=0,reaper.CountMediaItems(0)-1 do
      local it=reaper.GetMediaItem(0,i)
      if M.ext(it,'ReaSetRecPreview')=='' then reaper.SetMediaItemInfo_Value(it,'B_MUTE',1)end
    end
    if s.song.free then
      self:jam_click(s)
      if self.jamClick then reaper.SetMediaItemInfo_Value(self.jamClick,'D_POSITION',origin)end
    end
    if lead>0 then
      local output,volume=self:click_output();local tr
      for i=0,reaper.CountTracks(0)-1 do local v=reaper.GetTrack(0,i);if M.ext(v,'ReaSetCountIn',nil,true)=='1'then tr=v end end
      if not tr then
        reaper.InsertTrackAtIndex(reaper.CountTracks(0),false);tr=reaper.GetTrack(0,reaper.CountTracks(0)-1)
        M.ext(tr,'ReaSetCountIn','1',true);reaper.GetSetMediaTrackInfo_String(tr,'P_NAME','Recording count-in',true)
        reaper.SetMediaTrackInfo_Value(tr,'B_MAINSEND',0);reaper.CreateTrackSend(tr,nil)
      end
      reaper.SetMediaTrackInfo_Value(tr,'I_RECARM',0);reaper.SetMediaTrackInfo_Value(tr,'B_MUTE',0)
      reaper.SetMediaTrackInfo_Value(tr,'D_VOL',volume);reaper.SetTrackSendInfo_Value(tr,1,0,'I_DSTCHAN',output)
      local samples=math.floor(lead*48000+.5);local data={}
      for n=0,samples-1 do
        local time=n/48000;local b=math.floor(time/beat);local dt=time-b*beat
        local v=dt<.04 and math.sin(2*math.pi*(b%num==0 and 1500 or 1000)*dt)*math.exp(-dt*110)*.35 or 0
        data[#data+1]=string.pack('<i2',math.floor(v*32767))
      end
      local pcm=table.concat(data);local file=s.folder..'/count-in.wav'
      M.write(file,'RIFF'..string.pack('<I4',36+#pcm)..'WAVEfmt '..string.pack('<I4I2I2I4I4I2I2',16,1,1,48000,96000,2,16)..'data'..string.pack('<I4',#pcm)..pcm)
      local it=reaper.AddMediaItemToTrack(tr);local tk=reaper.AddTakeToMediaItem(it)
      reaper.SetMediaItemTake_Source(tk,assert(reaper.PCM_Source_CreateFromFile(file)))
      reaper.SetMediaItemInfo_Value(it,'D_POSITION',origin-lead);reaper.SetMediaItemInfo_Value(it,'D_LENGTH',lead)
      reaper.SetMediaItemInfo_Value(it,'C_BEATATTACHMODE',0);M.ext(it,'ReaSetRecPreview',t.id)
      for _,k in ipairs({'D_FADEINLEN','D_FADEOUTLEN','D_FADEINLEN_AUTO','D_FADEOUTLEN_AUTO'})do reaper.SetMediaItemInfo_Value(it,k,0)end
    end
    reaper.TrackList_AdjustWindows(false);reaper.UpdateArrange()
    reaper.SetEditCurPos(origin-lead,false,false)
    self:start_native()
    if lead>0 then self.mode='countin' end
  end
  function self:align_capture(s,t,it)
    if not t.origin or M.ext(it,'ReaSetRecAligned')=='1' then return true end
    local pos=reaper.GetMediaItemInfo_Value(it,'D_POSITION');local len=reaper.GetMediaItemInfo_Value(it,'D_LENGTH')
    local trim=math.max(0,t.origin-pos)
    if len<=trim then return false end
    for n=0,reaper.CountTakes(it)-1 do
      local tk=reaper.GetTake(it,n)
      reaper.SetMediaItemTakeInfo_Value(tk,'D_STARTOFFS',reaper.GetMediaItemTakeInfo_Value(tk,'D_STARTOFFS')+trim*reaper.GetMediaItemTakeInfo_Value(tk,'D_PLAYRATE'))
    end
    reaper.SetMediaItemInfo_Value(it,'D_POSITION',pos+trim-t.origin+s.song.start)
    reaper.SetMediaItemInfo_Value(it,'D_LENGTH',len-trim);M.ext(it,'ReaSetRecAligned','1')
    return true
  end
end
