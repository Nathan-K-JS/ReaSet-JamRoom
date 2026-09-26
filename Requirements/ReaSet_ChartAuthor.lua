-- Validate authored chart content before publishing it. GPL-3.0.
return function(doc,data,duration)
  local function finite(n)return type(n)=='number' and n==n and math.abs(n)<math.huge end
  local function text(s,max)return type(s)=='string' and #s<=max end
  assert(type(data)=='table' and (data.schema==2 or data.schema==3) and type(data.sections)=='table','Invalid chart')
  assert(doc.schema~=3 or data.schema==3,'Chart format changed. Refresh the editor before saving.')
  assert(#data.sections>0 and #data.sections<=256,'Choose between 1 and 256 sections')
  local offset=data.timing_offset or 0
  assert(finite(offset) and math.abs(offset)<duration,'Invalid timing offset')
  local ids,total={},0
  local function ident(s)
    assert(text(s,100) and #s>0 and not ids[s],'Chart identities must be unique');ids[s]=true
  end
  for i,s in ipairs(data.sections)do
    ident(s.id)
    local a,b=s.start,data.sections[i+1] and data.sections[i+1].start or duration
    assert(finite(a) and finite(b) and a>=0 and b>a and b<=duration and (i~=1 or a==0),'Section starts must increase from zero')
    assert(text(s.label,640) and s.label:match('%S'),'Name each section')
    assert(type(s.rows)=='table','Invalid chart lines');total=total+#s.rows;assert(total<=4096,'Too many chart lines')
    assert(finite(s['repeat'] or 1) and (s['repeat'] or 1)>=1 and (s['repeat'] or 1)<=32,'Invalid repeat count')
    s['end']=b;s.kind='instrumental';s.progression=setmetatable({},getmetatable(data.sections))
    local states={estimated=true,matched=true,manual=true,checked=true}
    s.timing_status=states[s.timing_status] and s.timing_status or 'estimated'
    s.confidence=s.timing_status=='checked' and 'section checked' or 'estimated'
    for _,r in ipairs(s.rows)do
      ident(r.id);assert(text(r.text or '',32768) and text(r.chord_line or '',32768),'Chart line is too long')
      if (r.text or ''):match('%S')then s.kind='vocal' end
      assert(type(r.anchors)=='table' and #r.anchors<=256,'Invalid chords')
      local last=-1
      for _,c in ipairs(r.anchors)do
        assert(finite(c.offset) and c.offset%1==0 and c.offset>=0 and c.offset<=8192 and c.offset>=last,'Invalid chord position')
        assert(text(c.symbol,160) and #c.symbol>0,'Invalid chord symbol')
        assert(finite(c.width or #c.symbol) and (c.width or #c.symbol)>0 and (c.width or #c.symbol)<=40,'Invalid chord width')
        last=c.offset;s.progression[#s.progression+1]=c.symbol
      end
      if r.cue and (not finite(r.cue) or r.cue<a or r.cue>=b)then r.cue=nil;r.cue_confidence=nil end
      assert(r.page_cues==nil or type(r.page_cues)=='table','Invalid page cues')
      assert(data.schema~=3 or not r.page_cues or next(r.page_cues)==nil,'Use section timing. Refresh the editor.')
      for col,t in pairs(r.page_cues or {})do
        local n=tonumber(col)
        if not n or n<0 or n>8192 or n%1~=0 or not finite(t) or t<a or t>=b then r.page_cues[col]=nil end
      end
    end
    s.missing_source_chords=s.kind=='instrumental' and #s.progression==0
  end
  doc.schema=data.schema;doc.duration=duration;doc.sections=data.sections;doc.timing_offset=offset
  doc.migration_snapshot=data.migration_snapshot or doc.migration_snapshot
  doc.authored=true;doc.manual=true;doc.source_preserved=false;doc.review=nil
  if data.source_url and text(data.source_url,2048)then doc.source_url=data.source_url end
  doc.editing_key=data.editing_key
  return doc
end
