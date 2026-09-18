-- Byte-verified, non-destructive media copy shared by export and listening jobs.
-- GPL-3.0.
return function(src,dst)
  local input=assert(io.open(src,'rb'),'Missing audio: '..src)
  local output=assert(io.open(dst..'.new','wb'),'Cannot create copied audio')
  while true do local data=input:read(1024*1024);if not data then break end;assert(output:write(data))end
  input:close();assert(output:close())
  input=assert(io.open(src,'rb'));output=assert(io.open(dst..'.new','rb'))
  local same=true
  while true do local a,b=input:read(1024*1024),output:read(1024*1024);if a~=b then same=false;break end;if not a then break end end
  input:close();output:close();assert(same,'Audio verification failed: '..src)
  local old=io.open(dst,'rb');if old then old:close();error('Copy destination already exists')end
  assert(os.rename(dst..'.new',dst),'Cannot finish media copy')
end
