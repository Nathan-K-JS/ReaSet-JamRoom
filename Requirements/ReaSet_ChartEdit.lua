-- Source-chart editing. Chord/word columns never change when a cue moves.
-- GPL-3.0
local M = {}
local function finite(n) return type(n)=='number' and n==n and math.abs(n)<math.huge end
local function require_ok(ok, message) if not ok then error(message,0) end end
local function row_key(si,ri,row) return row.id or ('legacy-'..si..'-'..ri) end

function M.apply(doc,action,data,duration)
  require_ok(type(doc)=='table' and type(doc.sections)=='table','No chart to edit')
  require_ok(type(data)=='table' and finite(duration) and duration>0,'Invalid edit')
  local function array() return setmetatable({},getmetatable(doc.sections)) end
  if action=='offset' then
    require_ok(finite(data.seconds) and math.abs(data.seconds)<duration,'Offset must be shorter than the song')
    doc.timing_offset=data.seconds
  elseif action=='layout' then
    local rows,order={},{}
    for si,s in ipairs(doc.sections) do
      for ri,row in ipairs(s.rows or {}) do
        local key=row_key(si,ri,row);rows[key]=row;order[#order+1]=key
      end
    end
    require_ok(type(data.sections)=='table' and #data.sections>0 and #data.sections<=256,'Choose sections')
    local sections,seen,cursor={}, {},1
    for i,group in ipairs(data.sections) do
      local a=group.start
      local b=data.sections[i+1] and data.sections[i+1].start or duration
      require_ok(finite(a) and finite(b) and a>=0 and b>a and b<=duration,'Section starts must be in song order')
      require_ok(i~=1 or a==0,'The first page starts at zero')
      require_ok(type(group.label)=='string' and #group.label>0 and #group.label<=160,'Name each section')
      require_ok(type(group.rows)=='table','Missing chart lines')
      local section={id='section-'..i,label=group.label,start=a,['end']=b,rows=array(),progression=array(),
        kind='instrumental',evidence=doc.source_preserved and 'chart' or 'manual',confidence='estimated',event_timing='unresolved'}
      for _,key in ipairs(group.rows) do
        require_ok(rows[key] and not seen[key] and order[cursor]==key,'Chart lines must be kept once, in their original order')
        seen[key]=true;cursor=cursor+1
        local row=rows[key];section.rows[#section.rows+1]=row
        if row.text and row.text:match('%S') then section.kind='vocal' end
        for _,anchor in ipairs(row.anchors or {}) do section.progression[#section.progression+1]=anchor.symbol end
      end
      local original=doc.sections[i]
      if original and original.start==a then section.confidence=original.confidence end
      section['repeat']=tonumber(group['repeat']) or 1
      require_ok(section['repeat']>=1 and section['repeat']<=32,'Invalid repeat count')
      sections[#sections+1]=section
    end
    require_ok(cursor==#order+1,'Some source lines are missing')
    doc.sections=sections
  elseif action=='cue' then
    local i,t=tonumber(data.section),data.time
    local s=i and doc.sections[i]
    require_ok(s and finite(t),'Select a section and a time')
    local previous=doc.sections[i-1]
    require_ok(t>=0 and t<s['end'] and (not previous or t>previous.start),'Cue would cross another section')
    require_ok(i~=1 or t==0,'The first page already starts at zero')
    s.start=t;s.confidence='section checked'
    if previous then previous['end']=t end
    -- No stretching rows or moving a single chord relative to a word.
  elseif action=='pagecue' then
    local s=doc.sections[tonumber(data.section) or 0]
    local t,col=data.time,data.column
    require_ok(s and finite(t) and t>=s.start and t<s['end'],'Page cue must be inside its section')
    require_ok(finite(col) and col>=0 and col==math.floor(col),'Invalid page column')
    local found
    for ri,row in ipairs(s.rows or {}) do
      if row_key(data.section,ri,row)==data.row then found=row;break end
    end
    require_ok(found,'Chart line changed')
    found.page_cues=found.page_cues or {};found.page_cues[tostring(col)]=t
  else error('Unknown chart edit',0) end
  doc.manual=true
  return doc
end
return M
