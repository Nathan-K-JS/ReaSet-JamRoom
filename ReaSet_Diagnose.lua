--[[
 * Script Name: ReaSet_Diagnose.lua — ONE-SHOT DIAGNOSTIC REPORT
 * About: Prints everything ReaSet needs in order to show lyrics/chords, so a
 *        "nothing is showing" problem can be pinpointed in one run instead of
 *        guessing. Safe: reads only, changes nothing in your project.
 *
 * USAGE:
 *   Actions → "ReaScript: Load..." → select ReaSet_Diagnose.lua
 *   Actions → Show action list → find "ReaSet_Diagnose" → Run
 *   Read the report in the ReaScript console window that opens.
 *
 * Licence: GPL v3
--]]

local SEC         = "ReaSet"
local STR_NO_TEXT = "--XR-NO-TEXT--"

local function out(s) reaper.ShowConsoleMsg(tostring(s) .. "\n") end
local function rule() out(string.rep("-", 66)) end

-- Must stay byte-identical to Reaset.lua's matcher, or this report lies.
local function normalize_track_name(name)
    local s = name:lower()
    local prev
    repeat
        prev = s
        s = s:gsub("^[^%w]+", "")
        s = s:gsub("^%d+", "")
    until s == prev
    s = s:gsub("[^%w]+$", "")
    return s
end

-- Byte-identical to Reaset.lua's lookup, so the self-test below proves the
-- real pipeline rather than a lookalike.
local function item_at_pos(track, pos)
    local n = reaper.GetTrackNumMediaItems(track)
    for i = 0, n - 1 do
        local item = reaper.GetTrackMediaItem(track, i)
        local p = reaper.GetMediaItemInfo_Value(item, "D_POSITION")
        if p <= pos then
            local len = reaper.GetMediaItemInfo_Value(item, "D_LENGTH")
            if p + len > pos then return item end
        end
    end
    return nil
end

local function read_note(item)
    if not reaper.ULT_GetMediaItemNote then return "" end
    local ok, n = pcall(reaper.ULT_GetMediaItemNote, item)
    if ok and n then return n end
    return ""
end

local function truncate(s, n)
    s = s:gsub("[\r\n]+", " / ")
    if #s > n then return s:sub(1, n) .. "..." end
    return s
end

-- The report body runs after a short delay so the heartbeat can be sampled
-- twice. A single sample cannot tell a running script from a crashed one.
local HB_SAMPLE_1 = reaper.GetExtState(SEC, "tick")
local HB_T0       = reaper.time_precise()

local function report()

reaper.ClearConsole()
out("")
out("=== ReaSet DIAGNOSTIC REPORT ===")
rule()

-- 1) Environment ------------------------------------------------------------
local has_ult = (reaper.ULT_GetMediaItemNote ~= nil)
out("REAPER version      : " .. tostring(reaper.GetAppVersion()))
out("SWS / ULT available : " .. (has_ult and "YES" or "NO  <-- lyrics/chords CANNOT work"))
local _, proj_name = reaper.EnumProjects(-1, "")
out("Project             : " .. (proj_name ~= "" and proj_name or "(unsaved)"))
out("Track count         : " .. reaper.CountTracks(0))
rule()

-- 2) Is Reaset.lua actually RUNNING (not just "was started once")? ----------
local hb2   = reaper.GetExtState(SEC, "tick")
local alive = (HB_SAMPLE_1 ~= "" and hb2 ~= "" and hb2 ~= HB_SAMPLE_1)

out("LIVENESS (samples the ReaSet/tick counter twice)")
out("  tick sample 1 : '" .. HB_SAMPLE_1 .. "'")
out("  tick sample 2 : '" .. hb2 .. "'")
if alive then
    out("  => Reaset.lua is RUNNING (counter advanced).")
elseif HB_SAMPLE_1 == "" and hb2 == "" then
    out("  => Reaset.lua is NOT RUNNING, or is an old version without a heartbeat.")
    out("     Load and Run the current Reaset.lua.")
else
    out("  => *** FROZEN *** the counter did NOT advance.")
    out("     The script was started but its defer loop has stopped, so every")
    out("     published value below is STALE. Re-run Reaset.lua.")
end
local last_err = reaper.GetExtState(SEC, "error")
if last_err ~= "" then
    out("  Last error reported by Reaset.lua:")
    out("    " .. last_err)
end
rule()
out("Presence flag (ReaSet/nativeLoopReady) : '" ..
    reaper.GetExtState(SEC, "nativeLoopReady") ..
    "'  (NOTE: never expires - not proof of life)")
out("Published lyrics status (ReaSet/lyricsTrack)  : '" ..
    reaper.GetExtState(SEC, "lyricsTrack") .. "'")
out("Published chords status (ReaSet/chordsTrack)  : '" ..
    reaper.GetExtState(SEC, "chordsTrack") .. "'")
rule()

-- 3) Full track table -------------------------------------------------------
out("ALL TRACKS  (idx | items | normalised | raw name)")
out("A track matches only when 'normalised' is exactly 'lyrics' or 'chords'.")
rule()

local matches = { lyrics = {}, chords = {} }

for i = 0, reaper.CountTracks(0) - 1 do
    local tr        = reaper.GetTrack(0, i)
    local _, raw    = reaper.GetTrackName(tr)
    local norm      = normalize_track_name(raw)
    local n_items   = reaper.GetTrackNumMediaItems(tr)
    local flag      = ""
    if norm == "lyrics" or norm == "chords" then
        flag = "   <== MATCHES '" .. norm .. "'"
        table.insert(matches[norm], { idx = i, tr = tr, raw = raw, items = n_items })
    end
    out(string.format("%3d | %5d | %-22s | %s%s",
        i + 1, n_items, "'" .. norm .. "'", raw, flag))
end
rule()

-- 4) Which track would each bridge pick? ------------------------------------
-- cur_pos is passed in: it is declared below this function, so referencing it
-- directly would compile to a global lookup and arrive as nil.
local function report_bridge(keyword, ext_name, cur_pos)
    out("")
    out(">>> " .. keyword:upper() .. " BRIDGE")

    local list = matches[keyword]
    if #list == 0 then
        out("  RESULT: no track matches '" .. keyword .. "'.")
        out("  FIX: rename a track to '" .. keyword .. "' (prefixes are fine: *" ..
            keyword .. ", 01 " .. keyword .. ", [" .. keyword .. "]).")
        out("       Extra words do NOT match, e.g. 'Backing " .. keyword .. "'.")
        return
    end

    out("  Matching tracks: " .. #list)
    for _, m in ipairs(list) do
        out(string.format("    - track %d  '%s'  (%d items)", m.idx + 1, m.raw, m.items))
    end
    if #list > 1 then
        out("  WARNING: more than one track matches. Reaset.lua prefers the first")
        out("           one that HAS items. Rename the others to avoid ambiguity.")
    end

    -- Same selection rule as Reaset.lua: prefer a track that has items.
    local chosen
    for _, m in ipairs(list) do
        if m.items > 0 then chosen = m; break end
    end
    chosen = chosen or list[1]
    out(string.format("  CHOSEN: track %d '%s' (%d items)", chosen.idx + 1, chosen.raw, chosen.items))

    if chosen.items == 0 then
        out("  PROBLEM: the chosen track has NO items -> nothing can ever display.")
        out("  FIX: put empty MIDI/text items on this track covering each section,")
        out("       and write the text in each item's Notes (double-click > Notes).")
        return
    end

    -- Inspect the notes on that track.
    local empty_notes, with_notes = 0, 0
    out("  Items (pos | length | note preview):")
    for k = 0, math.min(chosen.items, 12) - 1 do
        local it   = reaper.GetTrackMediaItem(chosen.tr, k)
        local pos  = reaper.GetMediaItemInfo_Value(it, "D_POSITION")
        local len  = reaper.GetMediaItemInfo_Value(it, "D_LENGTH")
        local note = ""
        if has_ult then
            local ok, n = pcall(reaper.ULT_GetMediaItemNote, it)
            if ok and n then note = n end
        end
        if note == "" then empty_notes = empty_notes + 1 else with_notes = with_notes + 1 end
        out(string.format("    %7.2fs | %6.2fs | %s",
            pos, len, note == "" and "(EMPTY - nothing to show)" or truncate(note, 40)))
    end
    if chosen.items > 12 then out("    ... (" .. (chosen.items - 12) .. " more items)") end

    out(string.format("  Items with notes: %d   empty: %d", with_notes, empty_notes))
    if with_notes == 0 then
        out("  PROBLEM: no item on this track has text in its Notes field.")
        out("  FIX: double-click an item > Notes, and type the text there.")
    end

    -- Where is the cursor relative to this track's items? "No data" is the
    -- CORRECT answer whenever nothing covers the cursor, so spell that out
    -- instead of leaving it as arithmetic for the reader.
    local covering = item_at_pos(chosen.tr, cur_pos)
    if covering then
        local note = read_note(covering)
        out("  CURSOR: inside an item -> should be showing:")
        out("    " .. (note == "" and "(item has EMPTY notes)" or truncate(note, 50)))
    else
        local best_gap, best_pos, best_dir
        for k = 0, chosen.items - 1 do
            local it  = reaper.GetTrackMediaItem(chosen.tr, k)
            local p   = reaper.GetMediaItemInfo_Value(it, "D_POSITION")
            local l   = reaper.GetMediaItemInfo_Value(it, "D_LENGTH")
            local gap, dir
            if p > cur_pos then gap, dir = p - cur_pos, "AFTER the cursor"
            else                gap, dir = cur_pos - (p + l), "BEFORE the cursor" end
            if gap >= 0 and (not best_gap or gap < best_gap) then
                best_gap, best_pos, best_dir = gap, p, dir
            end
        end
        out("  CURSOR: NOT inside any item -> 'no data' is CORRECT right now.")
        if best_gap then
            out(string.format("    nearest item starts at %.2fs — %.2fs %s",
                best_pos, best_gap, best_dir))
            out("    Move the playhead into an item (or press play) to see text.")
        end
    end

    -- Prove the lookup works at a position we KNOW is inside an item, so a
    -- badly-parked cursor can never be mistaken for a broken bridge.
    local it0 = reaper.GetTrackMediaItem(chosen.tr, 0)
    local p0  = reaper.GetMediaItemInfo_Value(it0, "D_POSITION")
    local l0  = reaper.GetMediaItemInfo_Value(it0, "D_LENGTH")
    local mid = p0 + l0 / 2
    if item_at_pos(chosen.tr, mid) then
        out(string.format("  SELF-TEST at %.2fs (middle of item 1): PASS -> '%s'",
            mid, truncate(read_note(item_at_pos(chosen.tr, mid)), 40)))
    else
        out(string.format("  SELF-TEST at %.2fs: FAIL — the item lookup is broken.", mid))
    end

    -- What is currently published to the web interface?
    local _, cur = reaper.GetProjExtState(0, ext_name, "text")
    if cur == STR_NO_TEXT then
        cur = "(nothing — matches the CURSOR line above)"
    elseif cur == "" then
        cur = "(nothing published yet - is Reaset.lua running?)"
    else
        cur = truncate(cur, 50)
    end
    out("  Currently published to ReaSet.html: " .. cur)
end

-- Cursor context matters: the bridge only publishes the item under the cursor.
local play_state = reaper.GetPlayState()
local cur_pos = play_state > 0 and reaper.GetPlayPosition() or reaper.GetCursorPosition()
out(string.format("Cursor position used by the bridges: %.2fs  (%s)",
    cur_pos, play_state > 0 and "play cursor" or "edit cursor"))
out("Only the item UNDER this position is published. If no item covers it,")
out("the panel correctly shows 'no data'.")

report_bridge("lyrics", "XR_Lyrics", cur_pos)
report_bridge("chords", "XR_Chords", cur_pos)

out("")
rule()
out("Copy this whole report when asking for help.")
out("=== END OF REPORT ===")

end  -- report()

-- Wait ~0.6 s before reporting so the heartbeat has time to advance.
local function wait_then_report()
    if reaper.time_precise() - HB_T0 < 0.6 then
        reaper.defer(wait_then_report)
    else
        report()
    end
end

reaper.ShowConsoleMsg("")   -- open/focus the console
wait_then_report()
