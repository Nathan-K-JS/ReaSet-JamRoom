-- The simple listening template supports dry files and ordinary folder routing.
-- Fail visibly for custom processing instead of silently dropping part of a mix.
-- GPL-3.0.
return function(tr)
  while tr do
    local _,name=reaper.GetTrackName(tr)
    assert(reaper.TrackFX_GetCount(tr)==0 and reaper.GetTrackNumSends(tr,0)==0,'Custom FX or sends on '..name..': mix this session in REAPER')
    for i=0,reaper.CountTrackEnvelopes(tr)-1 do
      local env=reaper.GetTrackEnvelope(tr,i)
      local ok,chunk=reaper.GetEnvelopeStateChunk(env,'',false)
      assert(ok,'Cannot check listening automation')
      -- Master tempo is represented by item timing/rate in this dry-file mix.
      assert(chunk:match('^<TEMPOENVEX') or not chunk:match('\nACT 1'),'Custom automation on '..name..': mix this session in REAPER')
    end
    tr=reaper.GetParentTrack(tr)
  end
end
