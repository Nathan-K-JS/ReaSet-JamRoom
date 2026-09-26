-- ReaSet_JamRoom.lua  v1  — PERSISTENT BACKGROUND SCRIPT  (GPL v3)
-- ─────────────────────────────────────────────────────────────────────────────
-- Part of the ReaSet Jam Room feature. See docs/JAMROOM_DESIGN.md.
--
-- INSTALL (one time only):
--   Actions → Load ReaScript → select this file
--   Then: Actions → Show action list → find "ReaSet_JamRoom" → Run
--   (or add it to REAPER startup: Options → Startup actions)
--
-- ROLE:
--   Runs forever in background via reaper.defer().
--   Discovers song-specific backing-group buses named "[JR:SLOT_ID] Label"
--   nested under permanent PB buses, determines which are active per song
--   region (>=1 descendant media item overlapping the region), validates the
--   setup, and publishes the result as chunked JSON via NON-PERSISTENT global
--   ExtState so ReaSet.html can poll it through REAPER's web interface.
--
--   Click enable commands clear item/subtrack mutes that TRACK cannot see.
--   Mute state & commands travel over the web interface's native TRACK API;
--   REAPER's PB-bus mute is the single source of truth.
--
-- EXTSTATE CONTRACT (section "ReaSetJR", all non-persistent):
--   heartbeat  incrementing integer, ~1/s (browser: stalled => bridge offline)
--   meta       "<generation>:<chunkCount>"     (written LAST after a change)
--   d0..dN     "<generation>:<jsonChunk>"      (<= 800 payload chars each)
-- ─────────────────────────────────────────────────────────────────────────────

local SEC        = "ReaSetJR"
local CHUNK_SIZE = 800
local HB_PERIOD  = 1.0      -- seconds between heartbeat bumps
local LOOP_RGN   = "ReaSet Loop"  -- temporary region created by ReaSet_NativeLoop.lua

-- ─── Fixed semantic playback slots (single source of truth) ──────────────────
-- Encodes the physical wiring: REAPER outs 1-16 → X32 returns 17-32.
local SLOTS = {
    { id = "DRUMS",    pb = "PB DRUMS",    order = 1,  click = false },
    { id = "PERC_FX",  pb = "PB PERC/FX",  order = 2,  click = false },
    { id = "BASS",     pb = "PB BASS",     order = 3,  click = false },
    { id = "GTR1",     pb = "PB GTR 1",    order = 4,  click = false },
    { id = "GTR2",     pb = "PB GTR 2",    order = 5,  click = false },
    { id = "KEYS",     pb = "PB KEYS",     order = 6,  click = false },
    { id = "BVS",      pb = "PB BVs",      order = 7,  click = false },
    { id = "LEAD_VOX", pb = "PB LEAD VOX", order = 8,  click = false },
    { id = "CLICK",    pb = "PB CLICK",    order = 9,  click = true  },
    { id = "EXTRA",    pb = "PB EXTRA",    order = 10, click = false },
}
local SLOT_BY_ID = {}
for _, s in ipairs(SLOTS) do SLOT_BY_ID[s.id] = s end
local click_targets = {}
local click_revision = 0
local click_instance = tostring(reaper.time_precise())

-- ─── Small helpers ────────────────────────────────────────────────────────────
local function trim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end

local function norm(s) return trim(s):upper() end  -- for case-insensitive compare

-- JSON string escaping: quotes, backslash, control chars. Output is one line.
local function jesc(s)
    s = tostring(s)
    s = s:gsub('[\\"]', '\\%0')
    s = s:gsub('%c', function(c)
        local map = { ['\n']='\\n', ['\r']='\\r', ['\t']='\\t' }
        return map[c] or string.format('\\u%04x', c:byte())
    end)
    return s
end

-- Parse "[JR:SLOT_ID] Label". Returns slotId(uppercased), label, or nil.
-- Tolerant of whitespace anywhere; slot id is A-Z, 0-9, underscore.
local function parse_jr_name(name)
    local slot, label = name:match("^%s*%[%s*[Jj][Rr]%s*:%s*([%w_]+)%s*%]%s*(.*)$")
    if not slot then return nil end
    return slot:upper(), trim(label)
end

-- Does this track name look like an attempted JR tag (even if malformed)?
local function looks_like_jr(name)
    return name:match("^%s*%[%s*[Jj][Rr]") ~= nil
end

-- ─── Project scan ─────────────────────────────────────────────────────────────

-- Snapshot all tracks with folder depth. depth[i] = nesting level (0 = top).
local function scan_tracks()
    local tracks = {}
    local d = 0
    local n = reaper.CountTracks(0)
    for i = 0, n - 1 do
        local tr = reaper.GetTrack(0, i)
        local _, name = reaper.GetTrackName(tr)
        tracks[#tracks + 1] = { tr = tr, name = name, depth = d, idx = i }
        local fd = reaper.GetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH")
        d = d + (fd > 0 and 1 or fd)   -- fd: 1 opens a folder, -N closes N
        if d < 0 then d = 0 end
    end
    return tracks
end

-- Top-level song regions: not strictly contained in another region, and not
-- the temporary loop region. Returns { {id,name,s,e}, ... }
local function scan_song_regions()
    local all = {}
    local i = 0
    while true do
        local ok, isrgn, pos, rgnend, name, idx = reaper.EnumProjectMarkers2(0, i)
        if ok == 0 then break end
        if isrgn and name ~= LOOP_RGN then
            all[#all + 1] = { id = idx, name = name, s = pos, e = rgnend }
        end
        i = i + 1
    end
    local songs = {}
    for _, r in ipairs(all) do
        local contained = false
        for _, o in ipairs(all) do
            if o ~= r and o.s <= r.s and o.e >= r.e and (o.s < r.s or o.e > r.e) then
                contained = true; break
            end
        end
        if not contained then songs[#songs + 1] = r end
    end
    return songs
end

-- Any media item on tracks[from..to] overlapping (s, e) by a non-zero amount?
local function subtree_overlaps(tracks, from, to, s, e)
    for ti = from, to do
        local tr = tracks[ti].tr
        local cnt = reaper.CountTrackMediaItems(tr)
        for ii = 0, cnt - 1 do
            local it = reaper.GetTrackMediaItem(tr, ii)
            local p = reaper.GetMediaItemInfo_Value(it, "D_POSITION")
            local l = reaper.GetMediaItemInfo_Value(it, "D_LENGTH")
            if p < e and (p + l) > s then return true end
        end
    end
    return false
end

-- Full discovery pass. Returns the payload JSON string (single line).
local function discover()
    click_targets = {}
    click_revision = click_revision + 1
    local tracks = scan_tracks()
    local songs  = scan_song_regions()
    local global_issues = {}

    local function gissue(typ, msg)
        global_issues[#global_issues + 1] =
            '{"type":"' .. jesc(typ) .. '","msg":"' .. jesc(msg) .. '"}'
    end

    -- Locate PB buses by (trimmed, case-insensitive) exact name.
    local pb_by_norm = {}
    local pb_dup = {}     -- slots whose PB name appears more than once
    for i, t in ipairs(tracks) do
        for _, s in ipairs(SLOTS) do
            if norm(t.name) == norm(s.pb) then
                if pb_by_norm[s.id] then
                    if not pb_dup[s.id] then
                        pb_dup[s.id] = true
                        gissue("duplicate_pb", 'Duplicate permanent PB bus name: "'
                            .. s.pb .. '" — its mute state/control would be ambiguous, '
                            .. 'so its controls are disabled. Remove one.')
                    end
                else
                    pb_by_norm[s.id] = i
                end
            end
        end
    end

    -- Locate JR buses; compute each one's subtree range [i..last].
    -- jr = { ti, name, slot, label, last, pbOk }
    local jrs = {}
    for i, t in ipairs(tracks) do
        local slot, label = parse_jr_name(t.name)
        if slot then
            local last = i
            for j = i + 1, #tracks do
                if tracks[j].depth > t.depth then last = j else break end
            end
            jrs[#jrs + 1] = { ti = i, name = t.name, slot = slot,
                              label = label, last = last }
        elseif looks_like_jr(t.name) then
            gissue("malformed_tag", 'Track name looks like a JR tag but could not '
                .. 'be parsed: "' .. t.name .. '". Expected "[JR:SLOT_ID] Label".')
        end
    end

    -- Structural validation per JR bus.
    for _, jr in ipairs(jrs) do
        local slotdef = SLOT_BY_ID[jr.slot]
        if not slotdef then
            gissue("unknown_slot", 'Unknown slot ID "' .. jr.slot .. '" in "'
                .. jr.name .. '".')
            jr.invalid = true
        elseif jr.label == "" then
            gissue("empty_label", 'Missing display label after the tag in "'
                .. jr.name .. '".')
            jr.invalid = true
        elseif pb_dup[jr.slot] then
            jr.invalid = true   -- ambiguous mute target; issue already reported
        else
            local pbi = pb_by_norm[jr.slot]
            if not pbi then
                gissue("missing_pb", 'Missing permanent PB bus "' .. slotdef.pb
                    .. '" required by "' .. jr.name .. '".')
                jr.invalid = true
            else
                -- Routing check: JR bus must be a DESCENDANT of its PB folder,
                -- otherwise its audio does not pass through the mute target.
                local pb = tracks[pbi]
                local inside = jr.ti > pbi and tracks[jr.ti].depth > pb.depth
                if inside then
                    for j = pbi + 1, jr.ti do
                        if tracks[j].depth <= pb.depth then inside = false; break end
                    end
                end
                if not inside then
                    gissue("routing_mismatch", '"' .. jr.name .. '" is not inside '
                        .. 'the "' .. slotdef.pb .. '" folder — muting would not '
                        .. 'affect it. Move it under that folder.')
                    jr.invalid = true
                end
            end
        end
    end

    -- Per-song: which valid JR buses are active (media overlap)?
    local song_parts = {}
    for _, song in ipairs(songs) do
        local active = {}           -- slot -> list of jr
        for _, jr in ipairs(jrs) do
            if not jr.invalid
               and subtree_overlaps(tracks, jr.ti, jr.last, song.s, song.e) then
                active[jr.slot] = active[jr.slot] or {}
                table.insert(active[jr.slot], jr)
            end
        end

        local controls, issues = {}, {}
        for _, slotdef in ipairs(SLOTS) do
            local claim = active[slotdef.id]
            if claim then
                if #claim > 1 then
                    local names = {}
                    for _, jr in ipairs(claim) do names[#names + 1] = '"' .. jr.name .. '"' end
                    issues[#issues + 1] = '{"type":"duplicate_slot","msg":"'
                        .. jesc('Slot ' .. slotdef.id .. ' claimed by multiple active buses in this song: '
                        .. table.concat(names, ", ") .. '. Neither is shown until resolved.') .. '"}'
                else
                    local jr = claim[1]
                    local click_fields = ''
                    if slotdef.click then
                        local key = click_instance .. ':' .. click_revision .. ':' .. song.id
                        local target = { tracks = {}, items = {}, pb = tracks[pb_by_norm.CLICK].tr }
                        local blocked = false
                        for ti = jr.ti, jr.last do
                            local tr = tracks[ti].tr
                            target.tracks[#target.tracks + 1] = tr
                            if reaper.GetMediaTrackInfo_Value(tr, 'B_MUTE') ~= 0 then blocked = true end
                            for ii = 0, reaper.CountTrackMediaItems(tr) - 1 do
                                local it = reaper.GetTrackMediaItem(tr, ii)
                                local p = reaper.GetMediaItemInfo_Value(it, 'D_POSITION')
                                if p < song.e and p + reaper.GetMediaItemInfo_Value(it, 'D_LENGTH') > song.s then
                                    target.items[#target.items + 1] = it
                                    if reaper.GetMediaItemInfo_Value(it, 'B_MUTE') ~= 0 then blocked = true end
                                end
                            end
                        end
                        click_targets[key] = target
                        click_fields = ',"clickKey":"' .. jesc(key) .. '","clickBlocked":' .. tostring(blocked)
                    end
                    controls[#controls + 1] = '{"slot":"' .. slotdef.id
                        .. '","order":' .. slotdef.order
                        .. ',"label":"' .. jesc(jr.label)
                        .. '","pb":"' .. jesc(slotdef.pb)
                        .. '","click":' .. tostring(slotdef.click) .. click_fields .. '}'
                end
            end
        end

        if #controls > 0 or #issues > 0 then
            song_parts[#song_parts + 1] = '"' .. jesc(tostring(song.id)) .. '":{'
                .. '"name":"' .. jesc(song.name) .. '"'
                .. ',"start":' .. string.format("%.6f", song.s)
                .. ',"end":' .. string.format("%.6f", song.e)
                .. ',"controls":[' .. table.concat(controls, ",") .. ']'
                .. ',"issues":[' .. table.concat(issues, ",") .. ']}'
        end
    end

    return '{"schema":1,"songs":{' .. table.concat(song_parts, ",")
        .. '},"globalIssues":[' .. table.concat(global_issues, ",") .. ']}'
end

-- ─── Publishing ───────────────────────────────────────────────────────────────
local s_generation  = 0
local s_last_json   = nil
local s_last_chunks = 0

local function publish(json)
    s_generation = s_generation + 1
    local n = math.ceil(#json / CHUNK_SIZE)
    -- Publish every song. The browser reads bounded batches, so a larger library
    -- needs more chunks, not an empty replacement payload.
    for i = 0, n - 1 do
        local chunk = json:sub(i * CHUNK_SIZE + 1, (i + 1) * CHUNK_SIZE)
        reaper.SetExtState(SEC, "d" .. i, s_generation .. ":" .. chunk, false)
    end
    -- Clear leftovers from a previously longer payload
    for i = n, s_last_chunks - 1 do
        reaper.SetExtState(SEC, "d" .. i, "", false)
    end
    s_last_chunks = n
    -- meta written LAST: readers treat it as the commit record
    reaper.SetExtState(SEC, "meta", s_generation .. ":" .. n, false)
end

local function clear_all_keys()
    local previous = tonumber(reaper.GetExtState(SEC, 'meta'):match(':(%d+)$')) or 0
    reaper.SetExtState(SEC, "clickWant", "", false)
    reaper.SetExtState(SEC, "meta", "", false)
    reaper.SetExtState(SEC, "heartbeat", "", false)
    for i = 0, math.max(s_last_chunks, previous) - 1 do
        reaper.SetExtState(SEC, "d" .. i, "", false)
    end
end

-- ─── Main defer loop ──────────────────────────────────────────────────────────
local s_hb        = 0
local s_hb_next   = 0
local s_last_csc  = -1        -- project state change count
local s_last_proj = nil

local function main_loop()
    local now = reaper.time_precise()

    -- Heartbeat ~1/s (non-persistent: vanishes with REAPER, so the browser
    -- can never mistake a dead bridge for a live one)
    if now >= s_hb_next then
        s_hb = s_hb + 1
        reaper.SetExtState(SEC, "heartbeat", tostring(s_hb), false)
        s_hb_next = now + HB_PERIOD
    end

    -- Rescan only when the project actually changed (or project tab switched)
    local proj = reaper.EnumProjects(-1, "")
    local csc  = reaper.GetProjectStateChangeCount(0)
    if csc ~= s_last_csc or proj ~= s_last_proj then
        s_last_csc, s_last_proj = csc, proj
        local ok, json = pcall(discover)
        if not ok then
            json = '{"schema":1,"songs":{},"globalIssues":[{"type":"bridge_error",'
                .. '"msg":"' .. jesc(tostring(json)) .. '"}]}'
        end
        if json ~= s_last_json then
            s_last_json = json
            publish(json)
        end
    end

    -- A rescan invalidates the key before handling a moved song/project.
    local request = reaper.GetExtState(SEC, 'clickWant')
    if request ~= '' then
        reaper.SetExtState(SEC, 'clickWant', '', false)
        local key, mute = request:match('^(.-)|([01])$')
        local target = click_targets[key]
        if target then
            reaper.Undo_BeginBlock()
            if mute == '0' then
                for _, tr in ipairs(target.tracks) do reaper.SetMediaTrackInfo_Value(tr, 'B_MUTE', 0) end
                for _, it in ipairs(target.items) do reaper.SetMediaItemInfo_Value(it, 'B_MUTE', 0) end
            end
            reaper.SetMediaTrackInfo_Value(target.pb, 'B_MUTE', tonumber(mute))
            reaper.UpdateArrange()
            reaper.Undo_EndBlock('ReaSet: set click playback', -1)
            s_last_csc = -1
        end
    end

    reaper.defer(main_loop)
end

-- ─── Boot ─────────────────────────────────────────────────────────────────────
clear_all_keys()               -- never let a previous run's data look current
reaper.atexit(clear_all_keys)  -- browser sees offline immediately on stop
reaper.defer(main_loop)
