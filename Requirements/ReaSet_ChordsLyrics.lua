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
--   want       browser command: add/delete/clear a timing checkpoint
--   repair     confirmed command result, polled by the browser
--
-- Timing repairs are PROJECT extstate, so every tablet sees the same result
-- and closing this script cannot lose them.  The source items are deliberately
-- left untouched: Reset is exact, and a correction can never compound another.
--   ReaSetCLRepair/song:<regionId>:lyrics = "source=actual,..." (song-relative)
--   ReaSetCLRepair/song:<regionId>:chords = same
--   ReaSetCLRepair/song:<regionId>:<scope>:reviewed = "1" after human check
-- ─────────────────────────────────────────────────────────────────────────────

local dir = debug.getinfo(1,"S").source:match("@?(.*[\\/])") or ""
local J = dofile(dir .. "ReaSet_JSON.lua")
local SEC        = "ReaSetCL"
local REPAIR_SEC = "ReaSetCLRepair"
local CHUNK_SIZE = 800
local MAX_CHUNKS = 256          -- ~51 KB: ample for one song
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

-- A checkpoint says "the event imported at source seconds should happen at
-- actual seconds".  One point is a plain offset; between two or more points
-- the offset is interpolated, which corrects drift without exposing maths to
-- the musician. Outside the checked range we hold the nearest correction --
-- extrapolating a dubious slope beyond evidence is unsafe.
local function repair_key(song_id, scope)
    return "song:" .. tostring(song_id) .. ":" .. scope
end

local function reviewed_key(song_id, scope)
    return repair_key(song_id, scope) .. ":reviewed"
end

local function parse_anchors(blob)
    local out = {}
    for pair in (blob or ""):gmatch("[^,]+") do
        local s, a = pair:match("^(-?[%d%.]+)=(-?[%d%.]+)$")
        s, a = tonumber(s), tonumber(a)
        if s and a then out[#out + 1] = { s = s, a = a } end
    end
    table.sort(out, function(x, y) return x.s < y.s end)
    return out
end

local function load_anchors(song_id, scope)
    local _, blob = reaper.GetProjExtState(0, REPAIR_SEC,
                                           repair_key(song_id, scope))
    return parse_anchors(blob)
end

local function save_anchors(song_id, scope, anchors)
    local parts = {}
    for _, p in ipairs(anchors) do
        parts[#parts + 1] = string.format("%.3f=%.3f", p.s, p.a)
    end
    reaper.SetProjExtState(0, REPAIR_SEC, repair_key(song_id, scope),
                           table.concat(parts, ","))
end

local function load_reviewed(song_id, scope)
    local _, value = reaper.GetProjExtState(0, REPAIR_SEC,
                                            reviewed_key(song_id, scope))
    return value == "1"
end

local function save_reviewed(song_id, scope, reviewed)
    reaper.SetProjExtState(0, REPAIR_SEC, reviewed_key(song_id, scope),
                           reviewed and "1" or "")
end

local function mapped_relative(t, anchors, duration)
    if #anchors == 0 then return math.max(0, math.min(duration, t)) end
    local delta
    if #anchors == 1 or t <= anchors[1].s then
        delta = anchors[1].a - anchors[1].s
    elseif t >= anchors[#anchors].s then
        local p = anchors[#anchors]
        delta = p.a - p.s
    else
        for i = 1, #anchors - 1 do
            local x, y = anchors[i], anchors[i + 1]
            if t >= x.s and t <= y.s then
                local f = (t - x.s) / math.max(0.001, y.s - x.s)
                local dx, dy = x.a - x.s, y.a - y.s
                delta = dx + (dy - dx) * f
                break
            end
        end
    end
    return math.max(0, math.min(duration, t + (delta or 0)))
end

local function anchors_json(anchors)
    local parts = {}
    for _, p in ipairs(anchors) do
        parts[#parts + 1] = string.format("[%.3f,%.3f]", p.s, p.a)
    end
    return "[" .. table.concat(parts, ",") .. "]"
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

local function apply_timing(items, song, anchors)
    local out, duration = {}, song.e - song.s
    for _, item in ipairs(items) do
        local raw_s, raw_e = item.p - song.s, item.e - song.s
        local s = mapped_relative(raw_s, anchors, duration)
        local e = mapped_relative(raw_e, anchors, duration)
        -- A severe local repair can squeeze an item's old end past its start.
        -- Keep the timeline valid; the next event still determines what is
        -- displayed, so a tiny positive duration is safer than corrupt JSON.
        if e <= s then e = math.min(duration, s + 0.05) end
        out[#out + 1] = {
            p = song.s + s, e = song.s + e, text = item.text,
            raw_p = item.p, raw_e = item.e
        }
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
    local ch_anchors = load_anchors(song.id, "chords")
    local ly_anchors = load_anchors(song.id, "lyrics")
    local ch = apply_timing(items_in(find_track("chords"), song.s, song.e),
                            song, ch_anchors)
    local ly = apply_timing(items_in(find_track("lyrics"), song.s, song.e),
                            song, ly_anchors)

    local parts = {}
    for _, c in ipairs(ch) do
        parts[#parts + 1] = string.format('[%.3f,%.3f,"%s",%.3f,%.3f]',
            c.p, c.e, jesc(c.text), c.raw_p, c.raw_e)
    end
    local chords_json = table.concat(parts, ",")

    parts = {}
    for _, l in ipairs(ly) do
        parts[#parts + 1] = string.format('[%.3f,%.3f,"%s",%.3f,%.3f]',
            l.p, l.e, jesc(l.text), l.raw_p, l.raw_e)
    end
    local lyrics_json = table.concat(parts, ",")

    local _, document = reaper.GetProjExtState(0, "ReaSetSong", "song:" .. song.id .. ":document")
    local _, project = reaper.GetProjExtState(0, "ReaSet", "projectId")
    local chart_json = "null"
    if document ~= "" then
        local doc = J.decode(document)
        -- Legacy checkpoint repairs apply consistently to the displayed words.
        for _, section in ipairs(doc.sections or {}) do
            section.start = mapped_relative(section.start,ly_anchors,song.e-song.s)
            section["end"] = mapped_relative(section["end"],ly_anchors,song.e-song.s)
            for _, row in ipairs(section.rows or {}) do
                if row.start then row.start = mapped_relative(row.start, ly_anchors, song.e-song.s) end
                if row["end"] then row["end"] = mapped_relative(row["end"], ly_anchors, song.e-song.s) end
            end
        end
        chart_json = J.encode(doc)
    end
    return string.format(
        '{"schema":1,"song":{"id":%d,"name":"%s","start":%.3f,"end":%.3f},'
        .. '"chords":[%s],"lyrics":[%s],'
        .. '"document":%s,"project":"%s","repair":{"chords":%s,"lyrics":%s,'
        .. '"reviewed":{"chords":%s,"lyrics":%s}}}',
        song.id, jesc(song.name), song.s, song.e, chords_json, lyrics_json, chart_json, jesc(project),
        anchors_json(ch_anchors), anchors_json(ly_anchors),
        load_reviewed(song.id, "chords") and "true" or "false",
        load_reviewed(song.id, "lyrics") and "true" or "false")
end

-- Validate and persist one browser repair command.  Commands are accepted only
-- for the song currently under the playhead, preventing a stale tablet from
-- changing a different project tab or a song that has moved.
local function command_fields(s)
    local out = {}
    for field in ((s or "") .. "|"):gmatch("(.-)|") do out[#out + 1] = field end
    return out
end

local function repair_reply(nonce, ok, message)
    message = tostring(message or ""):gsub("[|\r\n]", " ")
    reaper.SetExtState(SEC, "repair",
        tostring(nonce or "") .. "|" .. (ok and "ok" or "error") .. "|" .. message,
        false)
end

local function validate_anchors(anchors, duration)
    if #anchors > 32 then return false, "Too many checkpoints; remove one first." end
    for i, p in ipairs(anchors) do
        if p.s < 0 or p.s > duration or p.a < 0 or p.a > duration then
            return false, "That checkpoint is outside this song."
        end
        if i > 1 and (p.s <= anchors[i - 1].s or p.a <= anchors[i - 1].a) then
            return false, "That point would make time run backwards."
        end
    end
    return true
end

local function changed_anchors(song, scope, action, src, actual)
    local anchors = load_anchors(song.id, scope)
    if action == "clear" then
        anchors = {}
    elseif action == "delete" then
        local kept = {}
        for _, p in ipairs(anchors) do
            if math.abs(p.s - src) > 0.01 then kept[#kept + 1] = p end
        end
        anchors = kept
    elseif action == "add" then
        local replaced = false
        for _, p in ipairs(anchors) do
            if math.abs(p.s - src) <= 0.05 then
                p.s, p.a, replaced = src, actual, true
                break
            end
        end
        if not replaced then anchors[#anchors + 1] = { s = src, a = actual } end
        table.sort(anchors, function(x, y) return x.s < y.s end)
    elseif action == "review" then
        -- No timing change: record that a human listened and accepted it.
    else
        return nil, "Unknown timing command."
    end
    local ok, why = validate_anchors(anchors, song.e - song.s)
    if not ok then return nil, why end
    return anchors
end

local function section_command(f, song)
    local key = "song:" .. song.id .. ":"
    local _, project = reaper.GetProjExtState(0,"ReaSet","projectId")
    if project ~= f[11] then return repair_reply(f[1],false,"Project changed; reopen repair.") end
    local _, blob = reaper.GetProjExtState(0,"ReaSetSong",key .. "document")
    local doc = J.decode(blob)
    if doc.revision ~= f[10] then return repair_reply(f[1],false,"Chart changed; reopen repair.") end
    if #load_anchors(song.id,"lyrics") > 0 or #load_anchors(song.id,"chords") > 0 then
        return repair_reply(f[1],false,"This song still has legacy timing fixes. Update it with 'Replace old timing fixes' before editing sections.")
    end
    local index, a, b = tonumber(f[4]), tonumber(f[5]), tonumber(f[6])
    local section = index and doc.sections[index]
    if not section or not a or not b or a < 0 or b <= a or b > song.e-song.s then
        return repair_reply(f[1],false,"Choose valid section boundaries.")
    end
    local previous, following = doc.sections[index-1], doc.sections[index+1]
    if (previous and a <= previous.start) or (following and b >= following["end"]) then
        return repair_reply(f[1],false,"That boundary would cross another section.")
    end
    local old_a, old_b = section.start, section["end"]
    local function retime(part, start, finish)
        part.start,part["end"]=start,finish
    end
    if previous and (math.abs(previous["end"]-old_a)<.01 or a<previous["end"]) then retime(previous,previous.start,a) end
    if following and (math.abs(following.start-old_b)<.01 or b>following.start) then retime(following,b,following["end"]) end
    retime(section,a,b)
    section.label = (f[7] and f[7] ~= "") and f[7] or section.label
    local template = tonumber(f[8]); local pattern = f[12] or ""
    if template and template > 0 and doc.templates[template] then
        local t=doc.templates[template]; section.progression=J.array()
        for _,row in ipairs(t.rows or {}) do
            for repeat_index=1,(row["repeat"] or 1) do
                for _,anchor in ipairs(row.anchors or {}) do
                    section.progression[#section.progression+1]=anchor.symbol
                end
            end
        end
        -- New progression cannot imply word positions on different lyrics.
        for _,row in ipairs(section.rows or {}) do row.anchors=J.array(); row.progression=nil end
        section.evidence="chart"
    end
    if pattern ~= "" then
        section.progression=J.array()
        for symbol in pattern:gmatch("[^,%s]+") do section.progression[#section.progression+1]=symbol end
        for _,row in ipairs(section.rows or {}) do row.anchors=J.array(); row.progression=nil end
        section.evidence="manual"
    end
    section["repeat"] = math.floor(math.max(1,math.min(32,tonumber(f[9]) or 1)))
    section.confidence="section checked"; section.event_timing="unresolved"
    doc.revision=doc.revision .. ":" .. tostring(reaper.time_precise())
    doc.manual=true
    reaper.Undo_BeginBlock()
    reaper.SetProjExtState(0,"ReaSetSong",key .. "document",J.encode(doc))
    reaper.SetProjExtState(0,"ReaSetSong",key .. "revision",doc.revision)
    reaper.MarkProjectDirty(0)
    reaper.Undo_EndBlock("Edit chart section: " .. section.label,-1)
    repair_reply(f[1],true,"Section saved; adjacent boundaries kept aligned.")
    return true
end

local function process_repair_command(want, song)
    local f = command_fields(want)
    local nonce, action, song_id, scope = f[1], f[2], tonumber(f[3]), f[4]
    local src, actual = tonumber(f[5]), tonumber(f[6])
    if not song or not song_id or song.id ~= song_id then
        return repair_reply(nonce, false,
            "Open the song you want to repair, then try again.")
    end
    if action == "layout" or action == "cue" or action == "pagecue" or action == "offset" then
        local _,project=reaper.GetProjExtState(0,'ReaSet','projectId')
        if project~=f[5] then return repair_reply(nonce,false,'Project changed; reopen the chart.') end
        local key='song:'..song.id..':'
        local _,blob=reaper.GetProjExtState(0,'ReaSetSong',key..'document')
        local doc=J.decode(blob)
        if doc.revision~=f[4] then return repair_reply(nonce,false,'Chart changed; reopen the editor before saving.') end
        if #load_anchors(song.id,'lyrics')>0 or #load_anchors(song.id,'chords')>0 then
            return repair_reply(nonce,false,'Replace old timing fixes in Song Library before editing this chart.')
        end
        local payload=f[6] or ''
        local count=tonumber(payload:match('^chunks:(%d+)$'))
        if count then
            if count<1 or count>192 then return repair_reply(nonce,false,'Invalid chart edit size.') end
            local chunks={}
            for i=0,count-1 do
                local key='edit:'..nonce..':'..i
                local hex=reaper.GetExtState(SEC,key)
                reaper.DeleteExtState(SEC,key,false)
                if #hex==0 or #hex>384 or #hex%2~=0 or hex:find('[^%x]') then
                    return repair_reply(nonce,false,'Chart edit was incomplete. Please save again.')
                end
                chunks[#chunks+1]=hex:gsub('%x%x',function(pair)return string.char(tonumber(pair,16))end)
            end
            payload=table.concat(chunks)
        end
        local decoded_ok,data=pcall(J.decode,payload)
        if not decoded_ok then return repair_reply(nonce,false,'Chart edit was incomplete. Please save again.') end
        local editor=dofile(dir..'ReaSet_ChartEdit.lua')
        local ok,result=pcall(editor.apply,doc,action,data,song.e-song.s)
        if not ok then return repair_reply(nonce,false,tostring(result)) end
        result.revision='manual:'..nonce..':'..tostring(reaper.time_precise())
        reaper.Undo_BeginBlock()
        reaper.SetProjExtState(0,'ReaSetSong',key..'document',J.encode(result))
        reaper.SetProjExtState(0,'ReaSetSong',key..'revision',result.revision)
        reaper.MarkProjectDirty(0)
        reaper.Undo_EndBlock('Edit chart '..action,-1)
        repair_reply(nonce,true,action=='layout' and 'Sections saved. Chord positions preserved.' or action=='offset' and 'Whole-song offset saved.' or 'Page timing saved. Chart content preserved.')
        return true
    end
    if action == "section" then return section_command(f,song) end
    local _,project=reaper.GetProjExtState(0,"ReaSet","projectId")
    if f[7] ~= project then return repair_reply(nonce,false,"Project changed or browser needs refreshing; reopen repair.") end
    if scope ~= "lyrics" and scope ~= "chords" and scope ~= "both" then
        return repair_reply(nonce, false, "Choose lyrics, chords, or both.")
    end
    if (action == "add" and (not src or not actual)) or
       (action == "delete" and not src) then
        return repair_reply(nonce, false, "That checkpoint was incomplete.")
    end

    local updates, why = {}, nil
    if scope == "both" then
        updates.lyrics, why = changed_anchors(song, "lyrics", action, src, actual)
        if updates.lyrics then
            updates.chords, why = changed_anchors(song, "chords", action, src, actual)
        end
    else
        updates[scope], why = changed_anchors(song, scope, action, src, actual)
    end
    if not updates[scope == "both" and "chords" or scope] then
        return repair_reply(nonce, false, why)
    end
    -- Validate every requested scope before writing either one. A linked edit
    -- can therefore never leave lyrics changed while chords were rejected.
    reaper.Undo_BeginBlock()
    for target, anchors in pairs(updates) do
        save_anchors(song.id, target, anchors)
        save_reviewed(song.id, target, action ~= "clear")
    end
    reaper.MarkProjectDirty(0)
    reaper.Undo_EndBlock((action == "clear" and "Reset" or
                          action == "review" and "Check" or "Repair") ..
        " chord/lyric timing: " .. song.name, -1)
    repair_reply(nonce, true,
        action == "clear" and "Imported timing restored." or
        action == "review" and "Timing marked as checked." or "Timing saved.")
    return true
end

-- ─── Publishing (same chunked pattern as the Jam Room bridge) ────────────────
local s_gen, s_last_json, s_last_chunks = math.floor(reaper.time_precise()*1000), nil, 0

local function publish(json)
    json = json:gsub("[\128-\255]+", function(part)
        local out={}
        for _, cp in utf8.codes(part) do
            if cp < 65536 then out[#out+1]=string.format("\\u%04x",cp)
            else cp=cp-65536; out[#out+1]=string.format("\\u%04x\\u%04x",55296+math.floor(cp/1024),56320+cp%1024) end
        end
        return table.concat(out)
    end)
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

-- Command-line script launches can bypass REAPER's usual task-control dialog.
-- Let the newest instance own publication; an older instance must not erase it.
local instance=tostring(reaper.time_precise())..':'..tostring({})
local function clear_all()
    if reaper.GetExtState(SEC,'instance')~=instance then return end
    reaper.SetExtState(SEC,'instance','',false)
    reaper.SetExtState(SEC, "meta", "", false)
    reaper.SetExtState(SEC, "heartbeat", "", false)
    reaper.SetExtState(SEC, "want", "", false)
    reaper.SetExtState(SEC, "repair", "", false)
    for i = 0, MAX_CHUNKS - 1 do reaper.SetExtState(SEC, "d" .. i, "", false) end
end

-- ─── Main loop ───────────────────────────────────────────────────────────────
local s_hb, s_hb_next, s_last_csc, s_last_proj, s_last_song = 0, 0, -1, nil, nil
local s_last_want, s_force = nil, false

local function main_loop()
    if reaper.GetExtState(SEC,'instance')~=instance then return end
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
    local want = reaper.GetExtState(SEC, "want")
    if want ~= "" and want ~= s_last_want then
        s_last_want = want
        local ok, result = pcall(process_repair_command,want,song)
        if not ok then
            reaper.ShowConsoleMsg('[ReaSet chart edit] '..tostring(result)..'\n')
            repair_reply(command_fields(want)[1],false,"Chart could not be edited; check the REAPER console.")
        end
        s_force = ok and result and true or false
        -- Consume the command. This prevents an interrupted/restarted script
        -- from replaying a stale request while leaving the separate confirmed
        -- reply available for the browser to read.
        reaper.SetExtState(SEC, "want", "", false)
    end
    local proj = reaper.EnumProjects(-1, "")
    local csc = reaper.GetProjectStateChangeCount(0)
    if s_force or csc ~= s_last_csc or proj ~= s_last_proj or song_id ~= s_last_song then
        s_force = false
        s_last_csc, s_last_proj, s_last_song = csc, proj, song_id
        local ok, json = pcall(build_json)
        if not ok then reaper.ShowConsoleMsg(tostring(json) .. "\n"); json = '{"schema":1,"song":null,"error":"Chart could not be read; check the REAPER console"}' end
        if json ~= s_last_json then
            s_last_json = json
            publish(json)
        end
    end

    reaper.defer(main_loop)
end

reaper.atexit(clear_all)
reaper.SetExtState(SEC,'instance',instance,false)
reaper.SetExtState(SEC, 'build', 'source-pages-2', false)
reaper.SetToggleCommandState(({ reaper.get_action_context() })[3],
                             ({ reaper.get_action_context() })[4], 1)
main_loop()
