-- Open configured devices without playing a song. Restore scoped preferences.
return function(self,M)
  function self:release_device()
    local saved=self.db.deviceOptions
    if saved then
      for key,value in pairs(saved)do reaper.SNM_SetIntConfigVar(key,value)end
      self.db.deviceOptions=nil
      if self.root then self:save(false)end
    end
    self.deviceState=nil
  end
  function self:prepare_device()
    assert(reaper.GetPlayState()==0,'Stop playback before reconnecting inputs')
    if not self.db.deviceOptions and self.root then
      self.db.deviceOptions={audiocloseinactive=reaper.SNM_GetIntConfigVar('audiocloseinactive',0),audioclosestop=reaper.SNM_GetIntConfigVar('audioclosestop',0)}
      self:save(false)
    end
    if self.db.deviceOptions then
      reaper.SNM_SetIntConfigVar('audiocloseinactive',self.db.deviceOptions.audiocloseinactive & ~3)
      reaper.SNM_SetIntConfigVar('audioclosestop',0)
    end
    if reaper.Audio_Init then reaper.Audio_Init()end
    self.deviceDeadline=reaper.time_precise()+5;self.deviceState='connecting'
  end
  function self:device_tick()
    if self.deviceState=='connecting' then
      if reaper.GetNumAudioInputs()>0 and (not reaper.Audio_IsRunning or reaper.Audio_IsRunning()~=0) then self.deviceState='ready';self.error=nil
      elseif reaper.time_precise()>=self.deviceDeadline then self.deviceState='unavailable' end
    elseif self.deviceState=='ready' and reaper.GetPlayState()==0 and reaper.GetNumAudioInputs()==0 then
      self.deviceState='unavailable'
    end
  end
end
