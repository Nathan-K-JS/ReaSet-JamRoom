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

local function truncate(s, n)
    s = s:gsub("[\r\n]+", " / ")
    if #s > n then return s:sub(1, n) .. "..." end
    return s
end

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

-- 2) Is Reaset.lua running? -------------------------------------------------
out("Reaset.lua heartbeat (ReaSet/nativeLoopReady) : '" ..
    reaper.GetExtState(SEC, "nativeLoopReady") .. "'   (expect '1' while running)")
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
local function report_bridge(keyword, ext_name)
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

    -- What is currently published to the web interface?
    local _, cur = reaper.GetProjExtState(0, ext_name, "text")
    if cur == STR_NO_TEXT then
        cur = "(no item under the cursor right now)"
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

report_bridge("lyrics", "XR_Lyrics")
report_bridge("chords", "XR_Chords")

out("")
rule()
out("Copy this whole report when asking for help.")
out("=== END OF REPORT ===")
