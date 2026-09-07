-- Small JSON codec for our persisted chart documents. GPL-3.0.
local J = {}
local null = {}; J.null = null
local array_mt = {}; function J.array(t) return setmetatable(t or {}, array_mt) end
function J.encode(v)
  local kind = type(v)
  if v == null or v == nil then return "null" end
  if kind == "boolean" then return tostring(v) end
  if kind == "number" then assert(v == v and math.abs(v) < math.huge, "nonfinite number"); return tostring(v) end
  if kind == "string" then
    return '"' .. v:gsub('[%z\1-\31\\"]', function(c)
      return ({['"']='\\"', ['\\']='\\\\', ['\n']='\\n', ['\r']='\\r', ['\t']='\\t'})[c]
        or string.format('\\u%04x', c:byte())
    end) .. '"'
  end
  assert(kind == "table", "unsupported JSON value")
  local out = {}
  if getmetatable(v) == array_mt or #v > 0 then
    for _, x in ipairs(v) do out[#out+1] = J.encode(x) end
    return '[' .. table.concat(out, ',') .. ']'
  end
  for k, x in pairs(v) do out[#out+1] = J.encode(tostring(k)) .. ':' .. J.encode(x) end
  table.sort(out)
  return '{' .. table.concat(out, ',') .. '}'
end
function J.decode(s)
  local pos, depth = 1, 0
  local function ws() local _, e = s:find('^%s*', pos); pos = (e or pos-1)+1 end
  local function str()
    assert(s:sub(pos,pos) == '"', 'expected string'); pos = pos+1
    local out = {}
    while pos <= #s do
      local c = s:sub(pos,pos); pos = pos+1
      if c == '"' then return table.concat(out) end
      if c == '\\' then
        c = s:sub(pos,pos); pos = pos+1
        if c == 'u' then
          local h = s:sub(pos,pos+3); assert(h:match('^%x%x%x%x$'), 'bad unicode'); pos = pos+4
          local n = tonumber(h,16)
          if n >= 0xD800 and n <= 0xDBFF then
            assert(s:sub(pos,pos+1) == '\\u', 'missing low surrogate')
            local low = tonumber(s:sub(pos+2,pos+5),16)
            assert(low and low >= 0xDC00 and low <= 0xDFFF, 'bad low surrogate')
            n = 0x10000 + (n-0xD800)*1024 + low-0xDC00; pos=pos+6
          end
          assert(not (n >= 0xD800 and n <= 0xDFFF), 'bad surrogate')
          out[#out+1] = utf8.char(n)
        else
          local escaped = ({['"']='"',['\\']='\\',['/']='/',b='\b',f='\f',n='\n',r='\r',t='\t'})[c]
          assert(escaped, 'bad escape'); out[#out+1] = escaped
        end
      else assert(c:byte() >= 32, 'control character'); out[#out+1] = c end
    end
    error('unterminated string')
  end
  local value
  value = function()
    ws(); depth=depth+1; assert(depth <= 64, 'JSON nesting too deep')
    local c, v = s:sub(pos,pos)
    if c == '"' then v=str()
    elseif c == '[' or c == '{' then
      local arr = c == '['; local close = arr and ']' or '}'
      v = arr and J.array() or {}; pos=pos+1; ws()
      if s:sub(pos,pos) ~= close then
        while true do
          local key
          if not arr then ws(); key=str(); ws(); assert(s:sub(pos,pos)==':','expected colon'); pos=pos+1 end
          local x=value(); if arr then v[#v+1]=x else v[key]=x end
          ws(); if s:sub(pos,pos)==close then break end
          assert(s:sub(pos,pos)==',','expected comma'); pos=pos+1
        end
      end
      pos=pos+1
    elseif s:sub(pos,pos+3)=='true' then v=true; pos=pos+4
    elseif s:sub(pos,pos+4)=='false' then v=false; pos=pos+5
    elseif s:sub(pos,pos+3)=='null' then v=null; pos=pos+4
    else
      local token=s:match('^-?%d+%.?%d*[eE]?[+-]?%d*',pos)
      v=tonumber(token); assert(v and v==v and math.abs(v)<math.huge,'bad number'); pos=pos+#token
    end
    depth=depth-1; return v
  end
  local out=value(); ws(); assert(pos>#s,'trailing JSON'); return out
end
return J
