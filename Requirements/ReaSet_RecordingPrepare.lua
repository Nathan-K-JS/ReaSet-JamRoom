-- Preparation is not capture. Cancel never creates/discards a take. GPL-3.0.
return function(self,M)
  function self:prepare_take(c)
    assert(reaper.GetPlayState()==0,'Stop listening before preparing a take')
    assert(c.kind=='new' or c.kind=='redo' or c.kind=='part','Choose New take, Redo or Add part')
    local s=self:session(c.session);local t
    for _,v in ipairs(s.takes)do if v.id==c.take then t=v end end
    assert(t and t.status~='discarded' and not t.unresolved,'Choose a saved take')
    assert(not s.deleted and not s.exported,'Choose a live session')
    if c.kind=='redo' then assert(t==s.takes[#s.takes],'Only redo the latest take')end
    local p={kind=c.kind,session=s.id,take=t.id,inputs={},countin=self.db.countin,click=s.song.click,
      parent=c.kind=='part' and t.id or c.kind=='redo' and t.parent or nil,stopAtEnd=t.stopAtEnd~=false}
    for _,cfg in ipairs(self.db.inputs)do p.inputs[cfg.id]=cfg.selected end
    self:review(s.id,p.parent or t.id)
    self.preparation=p;self.overdub=nil
    for _,cfg in ipairs(self.db.inputs)do
      cfg.selected=false
      if c.kind~='part' then for _,id in ipairs(t.inputs)do if id==cfg.id then cfg.selected=true end end end
    end
    if c.kind=='redo' then
      if t.countin~=nil then self.db.countin=t.countin end
      if t.click~=nil then s.song.click=t.click end
    end
    self:audition_mix();self:prepare_device();self.deviceArm=true;self:save(false)
  end
  function self:cancel_preparation()
    assert(reaper.GetPlayState()==0,'Stop listening first')
    local p=assert(self.preparation,'No take is being prepared')
    self:review(p.session,p.take)
    for _,cfg in ipairs(self.db.inputs)do cfg.selected=p.inputs[cfg.id]==true end
    self.db.countin=p.countin;self:session(p.session).song.click=p.click
    self:save(false)
  end
  function self:record_prepared(c)
    assert(reaper.GetPlayState()==0,'Stop listening first')
    local p=assert(self.preparation,'Prepare a take first');local s=self:session(p.session)
    assert(self:song(s.song.key).start==s.song.start,'Song moved; export this session first')
    local mix={backingOn=self.backingOn,stemMutes=M.J.decode(M.J.encode(self.stemMutes or {}))}
    self:begin(s.song.key,p.parent,s.id,mix)
    local _,t=M.mix_take(self);t.stopAtEnd=c.stopAtEnd~=false
    if p.kind=='redo' then for _,old in ipairs(s.takes)do if old.id==p.take then old.status='discarded' end end end
    self.preparation=nil;self:save(false)
  end
end
