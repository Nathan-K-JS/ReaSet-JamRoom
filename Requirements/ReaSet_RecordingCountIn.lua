-- Read the installed song click, independently of the importer's tempo label.
-- No audio, project tempo or source files are changed. GPL-3.0.
local M={}
local function finite(v)return type(v)=='number' and v==v and math.abs(v)<math.huge end
local function wave_beats(path)
  local f=io.open(path,'rb');if not f then return end
  local ok,result=pcall(function()
    local header=f:read(12)
    if not header or header:sub(1,4)~='RIFF' or header:sub(9,12)~='WAVE' then return end
    local rate,align
    for _=1,64 do
      local chunk=f:read(8);if not chunk or #chunk<8 then return end
      local size=string.unpack('<I4',chunk,5);local pos=f:seek()
      if chunk:sub(1,4)=='fmt ' then
        local fmt=f:read(16);if not fmt or #fmt<16 then return end
        local format,channels,sr,_,block,bits=string.unpack('<I2I2I4I4I2I2',fmt)
        if format~=1 or channels~=1 or bits~=16 or block~=2 then return end
        rate=sr;align=block
      elseif chunk:sub(1,4)=='data' and rate and rate>=8000 and rate<=192000 then
        -- Generated clicks are mono PCM16. Bound fallback work to 30 seconds.
        local data=f:read(math.min(size,rate*align*30));local beats={};local last=-1
        for n=1,#data-1,align do
          local v=string.unpack('<i2',data,n);local time=(n-1)/align/rate
          if math.abs(v)>327 and time-last>.08 then beats[#beats+1]=time;last=time end
        end
        return beats
      end
      if not f:seek('set',pos+size+size%2)then return end
    end
  end)
  f:close();if ok then return result end
end
function M.grid(song,rows,read,decode)
  for _,r in ipairs(rows)do if r.slot=='CLICK' then
    local take=reaper.GetActiveTake(r.item)
    if take then
      local source=reaper.GetMediaItemTake_Source(take)
      local path=reaper.GetMediaSourceFileName(source,'')
      local raw=read((path:gsub('%.[Ww][Aa][Vv]$',''))..'-review.json')
      local ok,report=pcall(decode,raw or '')
      local beats=ok and type(report)=='table' and report.beats or nil
      if type(beats)~='table' or #beats<3 then beats=wave_beats(path)end
      if beats then
        local rate=reaper.GetMediaItemTakeInfo_Value(take,'D_PLAYRATE')
        local offset=reaper.GetMediaItemTakeInfo_Value(take,'D_STARTOFFS')
        local start=reaper.GetMediaItemInfo_Value(r.item,'D_POSITION')-song.start
        local length=reaper.GetMediaItemInfo_Value(r.item,'D_LENGTH')
        if finite(rate) and rate>0 and finite(offset) then
          local times={}
          for _,b in ipairs(beats)do
            if not finite(b)then times={};break end
            local time=start+(b-offset)/rate
            if time>=0 and time<start+length then times[#times+1]=time;if #times==9 then break end end
          end
          local intervals={}
          for i=2,#times do local d=times[i]-times[i-1];if d<.1 or d>3 then intervals={};break end;intervals[#intervals+1]=d end
          if #intervals>=2 then
            table.sort(intervals);local mid=math.floor(#intervals/2)+1
            local beat=#intervals%2==1 and intervals[mid] or (intervals[mid-1]+intervals[mid])/2
            return beat,times[1]%beat
          end
        end
      end
    end
  end end
end
return M
