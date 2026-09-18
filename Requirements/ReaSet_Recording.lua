-- Recording/volume controller. Native REAPER state is authoritative. GPL-3.0.
local dir=debug.getinfo(1,'S').source:match('@?(.*[\\/])') or ''
local M=dofile(dir..'ReaSet_RecordingCore.lua')
dofile(dir..'ReaSet_RecordingExport.lua')(M)
local SEC='ReaSetRec'
local instance=M.guid();reaper.SetExtState(SEC,'instance',instance,false)
reaper.SetExtState(SEC,'want','',false)
local controller,owner,last_csc,last_data,generation,next_tick=nil,nil,-1,'',0,0
local function publish(value)
  local json=M.J.encode(value)
  if json==last_data then return end
  last_data=json;generation=generation+1
  local count=math.ceil(#json/800)
  for i=0,count-1 do reaper.SetExtState(SEC,'d'..i,generation..':'..json:sub(i*800+1,(i+1)*800),false)end
  reaper.SetExtState(SEC,'meta',generation..':'..count,false)
end
local function leave()
  if controller and reaper.ValidatePtr(owner,'ReaProject*') then
    local active=reaper.EnumProjects(-1,'');reaper.SelectProjectInstance(owner)
    controller:stop_preview()
    if controller.db.active then reaper.Main_OnCommand(1016,0);controller:finish(true)
    else controller:park()end
    reaper.SelectProjectInstance(active)
  end
end
local function tick()
  if reaper.GetExtState(SEC,'instance')~=instance then return end
  if reaper.GetExtState(SEC,'quit')=='1' then reaper.SetExtState(SEC,'quit','',false);return end
  local now=reaper.time_precise()
  if now<next_tick then reaper.defer(tick);return end
  next_tick=now+.1
  reaper.SetExtState(SEC,'heartbeat',tostring(now),false)
  local project=reaper.EnumProjects(-1,'')
  if project~=owner then
    pcall(leave);controller=nil;owner=project;last_csc=-1
    reaper.SetExtState(SEC,'want','',false)
  end
  local _,exported=reaper.GetProjExtState(0,'ReaSet','recordingProject')
  if exported=='1' then
    reaper.SetExtState(SEC,'lock','',false)
    publish({exported=true,mode='idle',message='Recording project: edit and mix in REAPER.'})
    reaper.defer(tick);return
  end
  local ok,why=xpcall(function()
    if not controller then controller=M.new()end
    if reaper.GetProjectStateChangeCount(0)~=last_csc and not controller.db.active then
      M.P.reconcile();last_csc=reaper.GetProjectStateChangeCount(0)
    end
    controller:tick()
    local raw=reaper.GetExtState(SEC,'want')
    if raw~='' then
      reaper.SetExtState(SEC,'want','',false)
      local parsed,c=pcall(M.J.decode,raw)
      if parsed and type(c)=='table' and type(c.nonce)=='string' and #c.nonce<100 and not controller.seen[c.nonce] then
        controller.seen[c.nonce]=true
        controller.error=nil
        local success,message=pcall(function()controller:command(c)end)
        if not success then
          if controller.db.active and reaper.GetPlayState()==0 and controller.mode~='countin' then pcall(function()controller:stop_preview();controller:finish(true)end)end
          controller.message=tostring(message)
          controller.error=tostring(message)
        end
        controller.ack=c.nonce;controller.revision=controller.revision+1
      end
    end
    local state=controller:state()
    reaper.SetExtState(SEC,'lock',controller.mode~='idle' and controller.id or '',false)
    publish(state)
  end,debug.traceback)
  if not ok then
    publish({error=tostring(why),mode=controller and controller.mode or 'idle',project=controller and controller.id,message='Recording needs attention. Files have been retained.'})
  end
  reaper.defer(tick)
end
reaper.atexit(function()
  if reaper.GetExtState(SEC,'instance')==instance then
    pcall(leave)
    for _,key in ipairs({'heartbeat','meta','lock','instance'})do reaper.SetExtState(SEC,key,'',false)end
  end
end)
tick()
