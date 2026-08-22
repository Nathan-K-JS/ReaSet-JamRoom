-- ReaSet_TempoKey.lua  v1  — PERSISTENT BACKGROUND SCRIPT  (GPL v3)
-- ─────────────────────────────────────────────────────────────────────────────
-- Per-song TEMPO (time-stretch, pitch preserved) and KEY (pitch shift,
-- length preserved) for ReaSet, commanded over extstate like the mute bridge.
--
--   Tempo: REAPER's master playrate, with "preserve pitch when changing
--          master playrate" (action 40671) forced ON. Affects everything.
--   Key:   take D_PITCH (semitones) on every AUDIO stem item overlapping the
--          active song's region — except groups the musician excluded (drums
--          by default; a cowbell FX track can be excluded, a strings FX track
--          included). Lyrics/chords note items and MIDI items are untouched.
--
-- SAFETY MODEL (the "only ever per-song" guarantee):
--   • The script tracks exactly what it applied, per item GUID.
--   • Leaving the song, changing the exclusions, script exit, or REAPER
--     restart after a crash all revert precisely those offsets.
--   • The applied map is mirrored into PROJECT extstate, so if the project
--     is saved mid-transpose (or REAPER dies), the next run of this script
--     finds the leftover offsets and reverts them before doing anything else.
--
-- EXTSTATE CONTRACT
--   IN  (from ReaSet, global, non-persistent):
--     ReaSetTK/want = "rate|semis|excludedSlotsCsv|songStart|songEnd"
--       e.g. "1.10|-2|DRUMS,CLICK|160.000|417.544".  songStart/End identify
--       the song by TIME (same convention as the Tracks tab — no reliance on
--       region-id equivalence between the web API and Lua).
--   OUT (global, non-persistent):
--     ReaSetTK/heartbeat  incrementing ~1/s
--     ReaSetTK/state = "rate|semis|excludedSlotsCsv|songStart|itemsShifted"
--       — CONFIRMED state, only written after REAPER actually applied it.
--   PROJECT extstate (persistent, crash/save recovery):
--     ReaSetTK/applied = "guid=offset;guid=offset;..."
-- ─────────────────────────────────────────────────────────────────────────────

local SEC        = "ReaSetTK"
local HB_PERIOD  = 1.0
local LOOP_RGN   = "ReaSet Loop"
local PRESERVE_PITCH_CMD = 40671
local MIN_RATE, MAX_RATE = 0.5, 1.5
local MAX_SEMIS = 7

local function trim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end

-- ─── Song + track discovery (same conventions as the other bridges) ──────────

local function song_at(pos)
    local all, i = {}, 0
    while true do
        local ok, isrgn, s, e, name = reaper.EnumProjectMarkers2(0, i)
        if ok == 0 then break end
        if isrgn and name ~= LOOP_RGN then
            all[#all + 1] = { s = s, e = e, name = name }
        end
        i = i + 1
    end
    local best
    for _, r in ipairs(all) do
        local nested = false
        for _, o in ipairs(all) do
            if o ~= r and o.s <= r.s and o.e >= r.e and (o.s < r.s or o.e > r.e) then
                nested = true; break
            end
        end
        if not nested and pos >= r.s and pos < r.e then
            if not best or r.s > best.s then best = r end
        end
    end
    return best
end

-- track index -> slot id ("DRUMS", "GTR1", ...) for every track inside a
-- [JR:SLOT] subtree; other tracks have no slot.
local function slot_by_trackidx()
    local tracks, d = {}, 0
    for i = 0, reaper.CountTracks(0) - 1 do
        local tr = reaper.GetTrack(0, i)
        local _, name = reaper.GetTrackName(tr)
        tracks[#tracks + 1] = { tr = tr, name = name, depth = d }
        local fd = reaper.GetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH")
        d = d + (fd > 0 and 1 or fd)
        if d < 0 then d = 0 end
    end
    local map = {}
    for i, t in ipairs(tracks) do
        local slot = t.name:match("^%s*%[%s*[Jj][Rr]%s*:%s*([%w_]+)%s*%]")
        if slot then
            slot = slot:upper()
            map[i - 1] = slot
            for j = i + 1, #tracks do
                if tracks[j].depth <= t.depth then break end
                map[j - 1] = slot
            end
        end
    end
    return map
end

local function item_guid(it)
    local _, g = reaper.GetSetMediaItemInfo_String(it, "GUID", "", false)
    return g
end

-- ─── Applied-offset bookkeeping (with project-extstate mirror) ───────────────

local applied = {}      -- guid -> semitone offset currently applied by us

local function persist_applied()
    local parts = {}
    for g, off in pairs(applied) do
        if off ~= 0 then parts[#parts + 1] = g .. "=" .. off end
    end
    reaper.SetProjExtState(0, SEC, "applied", table.concat(parts, ";"))
end

local function all_audio_items(fn)
    for ti = 0, reaper.CountTracks(0) - 1 do
        local tr = reaper.GetTrack(0, ti)
        for ii = 0, reaper.CountTrackMediaItems(tr) - 1 do
            local it = reaper.GetTrackMediaItem(tr, ii)
            local tk = reaper.GetActiveTake(it)
            if tk and not reaper.TakeIsMIDI(tk) then fn(it, tk, ti) end
        end
    end
end

-- Crash/save recovery: revert any offsets a previous run left behind.
local function recover_leftovers()
    local _, blob = reaper.GetProjExtState(0, SEC, "applied")
    if not blob or blob == "" then return end
    local leftover = {}
    for pair in blob:gmatch("[^;]+") do
        local g, off = pair:match("^(.-)=(-?[%d%.]+)$")
        if g and tonumber(off) then leftover[g] = tonumber(off) end
    end
    local n = 0
    all_audio_items(function(it, tk)
        local g = item_guid(it)
        local off = leftover[g]
        if off and off ~= 0 then
            reaper.SetMediaItemTakeInfo_Value(tk, "D_PITCH",
                reaper.GetMediaItemTakeInfo_Value(tk, "D_PITCH") - off)
            n = n + 1
        end
    end)
    reaper.SetProjExtState(0, SEC, "applied", "")
    if n > 0 then
        reaper.ShowConsoleMsg(string.format(
            "[ReaSet tempo/key] reverted %d leftover pitch offset(s) from a "
            .. "previous session.\n", n))
        reaper.UpdateArrange()
    end
end

-- ─── Application ─────────────────────────────────────────────────────────────

local cur = { rate = 1.0, semis = 0, excl = "", s = -1, e = -1, items = 0 }

-- Force "preserve pitch when changing master playrate" ON, and report whether
-- it actually stuck. Without it, a tempo change resamples and the whole song
-- goes chipmunk. Checking for == 0 was not enough: some installs report -1
-- ("state unknown"), in which case the old code silently skipped and left the
-- preference off, which is exactly how tempo shipped broken.
local function ensure_preserve_pitch()
    local st = reaper.GetToggleCommandState(PRESERVE_PITCH_CMD)
    if st ~= 1 then
        reaper.Main_OnCommand(PRESERVE_PITCH_CMD, 0)
        st = reaper.GetToggleCommandState(PRESERVE_PITCH_CMD)
        if st ~= 1 then                       -- unknown state: try the once more
            reaper.Main_OnCommand(PRESERVE_PITCH_CMD, 0)
            st = reaper.GetToggleCommandState(PRESERVE_PITCH_CMD)
        end
    end
    return st
end

local s_pp = -1        -- last known preserve-pitch state, published to ReaSet

local function set_rate(rate)
    rate = math.max(MIN_RATE, math.min(MAX_RATE, rate))
    -- Re-assert before every change, not just at boot: the preference is
    -- global and anything (a preset, another script, the user) can flip it.
    if math.abs(rate - 1.0) > 0.0005 then
        s_pp = ensure_preserve_pitch()
    end
    if math.abs(reaper.Master_GetPlayRate(0) - rate) > 0.0005 then
        reaper.CSurf_OnPlayRateChange(rate)
    end
end

-- Bring every item to its target offset for the active song (0 for excluded
-- groups and for items outside the song). Deltas only — idempotent.
local function apply_pitch(song, semis, excl_csv)
    local excl = {}
    for s in (excl_csv or ""):gmatch("[^,]+") do excl[trim(s):upper()] = true end
    local slots = slot_by_trackidx()
    local touched = 0
    local new_applied = {}
    all_audio_items(function(it, tk, tidx)
        local g = item_guid(it)
        local target = 0
        if song and semis ~= 0 then
            local p = reaper.GetMediaItemInfo_Value(it, "D_POSITION")
            local l = reaper.GetMediaItemInfo_Value(it, "D_LENGTH")
            if p < song.e and (p + l) > song.s then
                local slot = slots[tidx]
                if not (slot and excl[slot]) then target = semis end
            end
        end
        local have = applied[g] or 0
        if target ~= have then
            reaper.SetMediaItemTakeInfo_Value(tk, "D_PITCH",
                reaper.GetMediaItemTakeInfo_Value(tk, "D_PITCH") + (target - have))
        end
        if target ~= 0 then
            new_applied[g] = target
            touched = touched + 1
        end
    end)
    applied = new_applied
    persist_applied()
    return touched
end

local function publish_state()
    -- Include the song's detected BPM (stamped at import) so ReaSet can offer
    -- "detected -> typed target BPM" as well as a percentage.
    local bpm = ""
    if cur.name and cur.name ~= "" then
        local _, v = reaper.GetProjExtState(0, SEC, "bpm:" .. cur.name)
        bpm = v or ""
    end
    -- Trailing field: preserve-pitch state (1 = on). ReaSet warns if it is not,
    -- because that is the difference between time-stretch and chipmunk.
    reaper.SetExtState(SEC, "state", string.format("%.4f|%d|%s|%.3f|%d|%s|%d",
        cur.rate, cur.semis, cur.excl, cur.s, cur.items, bpm, s_pp), false)
end

-- ─── Main loop ───────────────────────────────────────────────────────────────

local s_hb, s_hb_next = 0, 0
local s_last_want = nil

local function main_loop()
    -- Remote shutdown (tooling/updates): fire-and-forget quit flag lets a new
    -- copy be started without REAPER's modal "task control" dialog.
    if reaper.GetExtState(SEC, "quit") == "1" then
        reaper.SetExtState(SEC, "quit", "", false)
        return   -- atexit runs cleanup
    end
    local now = reaper.time_precise()
    if now >= s_hb_next then
        s_hb = s_hb + 1
        reaper.SetExtState(SEC, "heartbeat", tostring(s_hb), false)
        s_hb_next = now + HB_PERIOD
    end

    local pos = reaper.GetPlayState() > 0 and reaper.GetPlayPosition()
                                          or reaper.GetCursorPosition()
    local song = song_at(pos)

    local want = reaper.GetExtState(SEC, "want")
    local w_rate, w_semis, w_excl, w_s, w_e = 1.0, 0, "", nil, nil
    if want ~= "" then
        local r, sm, ex, ss, se =
            want:match("^([%d%.]+)|(-?%d+)|([^|]*)|([%d%.%-]+)|([%d%.%-]+)$")
        if r then
            w_rate, w_semis, w_excl = tonumber(r) or 1.0, tonumber(sm) or 0, ex
            w_s, w_e = tonumber(ss), tonumber(se)
        end
    end

    -- The want only applies while ITS song is the active one; anywhere else
    -- everything is neutral. Song identity is by time, tolerating tiny drift.
    local active_matches = song and w_s and math.abs(song.s - w_s) < 0.05
    local t_rate  = active_matches and w_rate or 1.0
    local t_semis = active_matches and w_semis or 0
    local t_excl  = active_matches and w_excl or ""
    t_semis = math.max(-MAX_SEMIS, math.min(MAX_SEMIS, t_semis))

    local song_s = song and song.s or -1
    if t_rate ~= cur.rate or t_semis ~= cur.semis or t_excl ~= cur.excl
            or song_s ~= cur.s then
        set_rate(t_rate)
        local items = apply_pitch(song, t_semis, t_excl)
        cur = { rate = t_rate, semis = t_semis, excl = t_excl,
                s = song_s, e = song and song.e or -1, items = items,
                name = song and song.name or "" }
        publish_state()
        if t_semis ~= 0 or next(applied) then reaper.UpdateArrange() end
    end

    reaper.defer(main_loop)
end

-- ─── Boot / exit ─────────────────────────────────────────────────────────────

local function cleanup()
    set_rate(1.0)
    apply_pitch(nil, 0, "")
    reaper.SetExtState(SEC, "heartbeat", "", false)
    reaper.SetExtState(SEC, "state", "", false)
    reaper.UpdateArrange()
end

recover_leftovers()
-- Tempo changes must never chipmunk the audio.
s_pp = ensure_preserve_pitch()
reaper.ShowConsoleMsg("[ReaSet tempo/key] preserve pitch on master playrate: "
    .. (s_pp == 1 and "ON" or ("COULD NOT ENABLE (state " .. s_pp ..
        ") - tempo changes would shift pitch; enable it by hand at "
        .. "Options > Preferences > Audio > Playback")) .. "\n")
reaper.atexit(cleanup)
publish_state()
main_loop()
