-- ReaSet_ChordsLyrics.lua  v1  — PERSISTENT BACKGROUND SCRIPT  (GPL v3)
-- ─────────────────────────────────────────────────────────────────────────────
-- Publishes the CURRENT SONG'S WHOLE chord and lyric timeline, so ReaSet can
-- show what is coming rather than only what is playing right now.
--
-- Why this exists: the X-Raym publisher scripts send only the single item under
-- the play cursor. That makes it impossible to show a phrase ahead, and
-- impossible to display anything early — you cannot look ahead of a cursor you
-- do not control. With the full timeline in the browser (which already tracks
-- the play position ~30x/second), the chord chart, the lookahead and the
-- per-song lead-time slider are all just arithmetic.
--
-- INSTALL: Actions -> Load ReaScript -> this file, then Run.
--          ReaSet_Startup.lua launches it along with everything else.
--
-- Reads the same project data as the X-Raym scripts (items on tracks named
-- "lyrics" / "chords", text in item NOTES), so nothing about how songs are
-- built has to change. Running both is harmless; ReaSet prefers this one.
--
-- EXTSTATE CONTRACT (section "ReaSetCL", all NON-persistent):
--   heartbeat  incrementing integer ~1/s   (stale => script not running)
--   meta       "<generation>:<chunkCount>" (written LAST = commit record)
--   d0..dN     "<generation>:<jsonChunk>"  (<= 800 payload chars each)
-- ─────────────────────────────────────────────────────────────────────────────

local SEC        = "ReaSetCL"
local CHUNK_SIZE = 800
local MAX_CHUNKS = 64          -- ~51 KB: ample for one song
local HB_PERIOD  = 1.0
local LOOP_RGN   = "ReaSet Loop"

if not reaper.ULT_GetMediaItemNote then
    reaper.ShowConsoleMsg("[ReaSet chords/lyrics] SWS extension missing " ..
        "(ULT_GetMediaItemNote) - cannot read item notes.\n")
    return
end

local function trim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end

local function jesc(s)
    s = tostring(s):gsub('[\\"]', '\\%0')
    return (s:gsub('%c', function(c)
        local map = { ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t' }
        return map[c] or string.format('\\u%04x', c:byte())
    end))
end

local function find_track(name)
    local want = name:lower()
    for i = 0, reaper.CountTracks(0) - 1 do
        local tr = reaper.GetTrack(0, i)
        local _, n = reaper.GetTrackName(tr)
        if trim(n):lower() == want then return tr end
    end
end

-- Top-level song region containing pos (ignores the temporary loop region and
-- any region nested inside another, matching how ReaSet discovers songs).
local function song_at(pos)
    local all, i = {}, 0
    while true do
        local ok, isrgn, s, e, name, idx = reaper.EnumProjectMarkers2(0, i)
        if ok == 0 then break end
        if isrgn and name ~= LOOP_RGN then
            all[#all + 1] = { s = s, e = e, name = name, id = idx }
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

-- Items on `track` overlapping [s,e) as {position, note} pairs, in time order.
local function items_in(track, s, e)
    local out = {}
    if not track then return out end
    for i = 0, reaper.CountTrackMediaItems(track) - 1 do
        local it = reaper.GetTrackMediaItem(track, i)
        local p = reaper.GetMediaItemInfo_Value(it, "D_POSITION")
        local l = reaper.GetMediaItemInfo_Value(it, "D_LENGTH")
        if p < e and (p + l) > s then
            local note = reaper.ULT_GetMediaItemNote(it) or ""
            note = trim((note:gsub("\r?\n", " ")))
            if note ~= "" then
                out[#out + 1] = { p = p, e = p + l, text = note }
            end
        end
    end
    table.sort(out, function(a, b) return a.p < b.p end)
    return out
end

local function build_json()
    local pos = reaper.GetPlayState() > 0 and reaper.GetPlayPosition()
                                          or reaper.GetCursorPosition()
    local song = song_at(pos)
    if not song then
        return '{"schema":1,"song":null}'
    end
    local ch = items_in(find_track("chords"), song.s, song.e)
    local ly = items_in(find_track("lyrics"), song.s, song.e)

    local parts = {}
    for _, c in ipairs(ch) do
        parts[#parts + 1] = string.format('[%.3f,%.3f,"%s"]', c.p, c.e, jesc(c.text))
    end
    local chords_json = table.concat(parts, ",")

    parts = {}
    for _, l in ipairs(ly) do
        parts[#parts + 1] = string.format('[%.3f,%.3f,"%s"]', l.p, l.e, jesc(l.text))
    end
    local lyrics_json = table.concat(parts, ",")

    return string.format(
        '{"schema":1,"song":{"id":%d,"name":"%s","start":%.3f,"end":%.3f},'
        .. '"chords":[%s],"lyrics":[%s]}',
        song.id, jesc(song.name), song.s, song.e, chords_json, lyrics_json)
end

-- ─── Publishing (same chunked pattern as the Jam Room bridge) ────────────────
local s_gen, s_last_json, s_last_chunks = 0, nil, 0

local function publish(json)
    s_gen = s_gen + 1
    local n = math.ceil(#json / CHUNK_SIZE)
    if n > MAX_CHUNKS then
        json = '{"schema":1,"song":null,"error":"payload too large"}'
        n = math.ceil(#json / CHUNK_SIZE)
    end
    for i = 0, n - 1 do
        reaper.SetExtState(SEC, "d" .. i,
            s_gen .. ":" .. json:sub(i * CHUNK_SIZE + 1, (i + 1) * CHUNK_SIZE), false)
    end
    for i = n, s_last_chunks - 1 do
        reaper.SetExtState(SEC, "d" .. i, "", false)
    end
    s_last_chunks = n
    reaper.SetExtState(SEC, "meta", s_gen .. ":" .. n, false)  -- commit record
end

local function clear_all()
    reaper.SetExtState(SEC, "meta", "", false)
    reaper.SetExtState(SEC, "heartbeat", "", false)
    for i = 0, MAX_CHUNKS - 1 do reaper.SetExtState(SEC, "d" .. i, "", false) end
end

-- ─── Main loop ───────────────────────────────────────────────────────────────
local s_hb, s_hb_next, s_last_csc, s_last_proj, s_last_song = 0, 0, -1, nil, nil

local function main_loop()
    local now = reaper.time_precise()
    if now >= s_hb_next then
        s_hb = s_hb + 1
        reaper.SetExtState(SEC, "heartbeat", tostring(s_hb), false)
        s_hb_next = now + HB_PERIOD
    end

    -- Rebuild when the project changed, the tab changed, or the playhead moved
    -- into a different song (the payload only covers the current song).
    local pos = reaper.GetPlayState() > 0 and reaper.GetPlayPosition()
                                          or reaper.GetCursorPosition()
    local song = song_at(pos)
    local song_id = song and song.id or nil
    local proj = reaper.EnumProjects(-1, "")
    local csc = reaper.GetProjectStateChangeCount(0)
    if csc ~= s_last_csc or proj ~= s_last_proj or song_id ~= s_last_song then
        s_last_csc, s_last_proj, s_last_song = csc, proj, song_id
        local ok, json = pcall(build_json)
        if ok and json ~= s_last_json then
            s_last_json = json
            publish(json)
        end
    end

    reaper.defer(main_loop)
end

reaper.atexit(clear_all)
reaper.SetToggleCommandState(({ reaper.get_action_context() })[3],
                             ({ reaper.get_action_context() })[4], 1)
main_loop()
