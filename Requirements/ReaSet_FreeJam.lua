-- Free-jam helpers installed into the existing recording controller. GPL-3.0.
return function(self,M)
  self.db.jam=self.db.jam or {bpm=100,beats=4,click=true}
  function self:jam_settings(c)
      assert(type(c.bpm)=='number' and c.bpm>=40 and c.bpm<=240 and c.bpm%1==0,'Tempo must be 40-240 BPM')
      assert(type(c.beats)=='number' and c.beats>=2 and c.beats<=7 and c.beats%1==0,'Choose 2-7 beats per bar')
      assert(type(c.click)=='boolean','Choose click on or off')
      self.db.jam={bpm=c.bpm,beats=c.beats,click=c.click}
  end
  function self:jam_song(key)
    if key~='freejam' then
      for _,s in ipairs(self.db.sessions)do
        if s.song.free and s.song.key==key and not s.deleted and not s.exported then return s.song end
      end
      return nil
    end
    local start=reaper.GetProjectLength(0)+10
    for _,s in ipairs(self.db.sessions)do start=math.max(start,s.song.finish+10)end
    local j=self.db.jam
    return {key='jam:'..M.guid(),name='Free jam '..os.date('%d %b %H:%M'),free=true,
      start=start,finish=start,bpm=j.bpm,beats=j.beats,click=j.click}
  end
  function self:jam_silence()
    for i=0,reaper.CountMediaItems(0)-1 do
      local it=reaper.GetMediaItem(0,i)
      if M.ext(it,'ReaSetRec')=='' and M.ext(it,'ReaSetJamClick')=='' then
        local _,g=reaper.GetSetMediaItemInfo_String(it,'GUID','',false)
        if self.audition[g]==nil then self.audition[g]=reaper.GetMediaItemInfo_Value(it,'B_MUTE')end
      end
    end
    -- Persist the restoration map before changing any mutes.
    reaper.SetProjExtState(0,'ReaSetRec','audition',M.J.encode(self.audition))
    self:save(true)
    for i=0,reaper.CountMediaItems(0)-1 do
      local it=reaper.GetMediaItem(0,i);local _,g=reaper.GetSetMediaItemInfo_String(it,'GUID','',false)
      if self.audition[g]~=nil then reaper.SetMediaItemInfo_Value(it,'B_MUTE',1)end
    end
  end
  function self:jam_clear_click()
    for i=reaper.CountMediaItems(0)-1,0,-1 do
      local it=reaper.GetMediaItem(0,i)
      if M.ext(it,'ReaSetJamClick')~='' then reaper.DeleteTrackMediaItem(reaper.GetMediaItem_Track(it),it)end
    end
    self.jamClick=nil
  end
  function self:jam_click(s)
    self:jam_clear_click()
    if not s.song.click then return end
    local tr
    for i=0,reaper.CountTracks(0)-1 do
      local t=reaper.GetTrack(0,i)
      if M.ext(t,'ReaSetJamClick',nil,true)=='1' then tr=t end
    end
    local output,volume=self:click_output()
    if not tr then
      reaper.InsertTrackAtIndex(reaper.CountTracks(0),false);tr=reaper.GetTrack(0,reaper.CountTracks(0)-1)
      M.ext(tr,'ReaSetJamClick','1',true)
      reaper.GetSetMediaTrackInfo_String(tr,'P_NAME','Free jam click',true)
      reaper.SetMediaTrackInfo_Value(tr,'B_MAINSEND',0)
      reaper.CreateTrackSend(tr,nil)
    end
    reaper.SetMediaTrackInfo_Value(tr,'I_RECARM',0)
    reaper.SetMediaTrackInfo_Value(tr,'B_MUTE',0)
    reaper.SetMediaTrackInfo_Value(tr,'D_VOL',volume)
    reaper.SetTrackSendInfo_Value(tr,1,0,'I_DSTCHAN',output)
    local beat=60/s.song.bpm
    -- Sample-accurate loop duration, with rate correction for fractional samples.
    local duration=beat*s.song.beats;local count=math.floor(duration*24000+.5);local data={}
    for n=0,count-1 do
      local t=n/24000;local b=math.floor(t/beat);local dt=t-b*beat
      local v=dt<.04 and math.sin(2*math.pi*(b==0 and 1500 or 1000)*dt)*math.exp(-dt*110)*.35 or 0
      data[#data+1]=string.pack('<i2',math.floor(v*32767))
    end
    local pcm=table.concat(data);local file=s.folder..'/jam-click.wav'
    M.write(file,'RIFF'..string.pack('<I4',36+#pcm)..'WAVEfmt '..string.pack('<I4I2I2I4I4I2I2',16,1,1,24000,48000,2,16)..'data'..string.pack('<I4',#pcm)..pcm)
    local source=assert(reaper.PCM_Source_CreateFromFile(file),'Cannot load jam click')
    local it=reaper.AddMediaItemToTrack(tr);local tk=reaper.AddTakeToMediaItem(it)
    reaper.SetMediaItemTake_Source(tk,source)
    reaper.SetMediaItemTakeInfo_Value(tk,'D_PLAYRATE',(count/24000)/duration)
    M.ext(it,'ReaSetJamClick',s.id)
    reaper.SetMediaItemInfo_Value(it,'D_POSITION',s.song.start)
    reaper.SetMediaItemInfo_Value(it,'D_LENGTH',300)
    reaper.SetMediaItemInfo_Value(it,'B_LOOPSRC',1)
    reaper.SetMediaItemInfo_Value(it,'C_BEATATTACHMODE',0)
    for _,k in ipairs({'D_FADEINLEN','D_FADEOUTLEN','D_FADEINLEN_AUTO','D_FADEOUTLEN_AUTO'})do reaper.SetMediaItemInfo_Value(it,k,0)end
    self.jamClick=it
    reaper.TrackList_AdjustWindows(false);reaper.UpdateArrange()
  end
  function self:jam_extend(s)
    if self.jamClick and reaper.ValidatePtr(self.jamClick,'MediaItem*')then
      local length=reaper.GetMediaItemInfo_Value(self.jamClick,'D_LENGTH')
      local elapsed=reaper.GetPlayPosition()-((self.db.active or {}).origin or s.song.start)
      if elapsed>length-60 then reaper.SetMediaItemInfo_Value(self.jamClick,'D_LENGTH',elapsed+300)end
    end
  end
end
