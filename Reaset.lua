--[[
 * Script Name: Reaset.lua  — UNIFIED BACKGROUND BRIDGE  (v1.0)
 * About: Single-script companion for the ReaSet web interface (ReaSet.html).
 *        Merges the three former helper scripts into ONE persistent background
 *        script so the whole setup is a single "run once" action:
 *
 *          1) Native A/B loop engine   (was ReaSet_NativeLoop.lua)
 *          2) Lyrics notes → web bridge (was X-Raym Convert Lyrics ...)
 *          3) Chords notes → web bridge (was X-Raym Convert Chords ...)
 *
 * Credits:
 *   - Lyrics/Chords note bridge logic: X-Raym (GPL v3)
 *     https://github.com/X-Raym/REAPER-ReaScripts
 *   - Native loop engine + unification: ReaSet project.
 * Licence: GPL v3 (inherits from the X-Raym components it reuses).
 *
 * INSTALL (one time only):
 *   Actions → "ReaScript: Load..." → select Reaset.lua
 *   Actions → Show action list → find "Reaset" → Run
 *   (Recommended) add it to REAPER startup: Options → Preferences → General
 *                 → Startup actions, OR SWS "Global startup action".
 *
 *   Nothing else to run. No Action ID needs to be pasted into ReaSet.html.
 *   The web interface auto-detects this script via the "nativeLoopReady" flag.
 *
 * DESIGN NOTES:
 *   - Runs forever via a single reaper.defer() tick.
 *   - Lyrics/Chords tracks are OPTIONAL: if a "lyrics" or "chords" track is
 *     missing the bridge for it simply stays idle. The loop engine keeps
 *     working regardless — so a project without lyrics/chords still gets full
 *     transport + loop control (the old scripts aborted with an error box).
 *   - ULT_GetMediaItemNote (SWS/S&M extension) is called defensively: if the
 *     extension is not installed, lyrics/chords are skipped but the loop
 *     engine and the rest of ReaSet keep functioning.
--]]

----------------------------------------------------------------------------
-- SHARED
----------------------------------------------------------------------------

local SEC          = "ReaSet"
local STR_NO_TEXT  = "--XR-NO-TEXT--"
local HAS_ULT      = (reaper.ULT_GetMediaItemNote ~= nil)  -- SWS present?

----------------------------------------------------------------------------
-- 1) NATIVE LOOP ENGINE  (formerly ReaSet_NativeLoop.lua v3)
----------------------------------------------------------------------------

local REGION_NAME  = "ReaSet Loop"
local REGION_COLOR = reaper.ColorToNative(80, 160, 255) | 0x1000000
local IDX_KEY      = "reasetLoopRegionIdx"
local NEAR_END     = 0.08   -- sec before loop_end that arms the crossing detector
local NEAR_START   = 0.30   -- sec after loop_start that confirms the jump landed

local s_active   = false
local s_start    = 0
local s_end      = 0
local s_max      = 0        -- 0 = infinite
local s_crosses  = 0
local s_near_end = false
local s_key      = ""

local function delete_region()
    local idx = tonumber(reaper.GetExtState(SEC, IDX_KEY))
    if idx then
        reaper.DeleteProjectMarker(nil, idx, true)
        reaper.SetExtState(SEC, IDX_KEY, "", false)
    end
    -- safety scan: remove any orphaned "ReaSet Loop" regions
    local i = 0
    while true do
        local ok, isrgn, _, _, name, midx = reaper.EnumProjectMarkers(i)
        if ok == 0 then break end
        if isrgn and name == REGION_NAME then
            reaper.DeleteProjectMarker(nil, midx, true)
            i = 0
        else
            i = i + 1
        end
    end
end

local function loop_cleanup()
    reaper.GetSetRepeat(0)
    reaper.GetSet_LoopTimeRange(true, true, 0, 0, false)
    delete_region()
    reaper.SetExtState(SEC, "nativeLoop", "done", false)
    reaper.UpdateArrange()
    s_active   = false
    s_crosses  = 0
    s_near_end = false
    s_key      = ""
end

local function loop_arm(ls, le, lm)
    if s_active then delete_region() end

    s_start    = ls
    s_end      = le
    s_max      = lm
    s_crosses  = 0
    s_near_end = false
    s_active   = true
    s_key      = string.format("%.5f:%.5f:%d", ls, le, lm)

    local new_idx = reaper.AddProjectMarker2(
        nil, true, ls, le, REGION_NAME, -1, REGION_COLOR)
    reaper.SetExtState(SEC, IDX_KEY, tostring(new_idx), false)

    reaper.GetSet_LoopTimeRange(true, true, ls, le, false)
    reaper.GetSetRepeat(1)
    reaper.UpdateArrange()
end

-- Returns false when the caller should skip the rest of this tick (a cleanup
-- + defer already happened is NOT done here; caller just continues normally).
local function loop_tick()
    local ctrl = reaper.GetExtState(SEC, "nativeLoop")

    if ctrl == "on" then
        local ls = tonumber(reaper.GetExtState(SEC, "loopStart"))
        local le = tonumber(reaper.GetExtState(SEC, "loopEnd"))
        local lm = tonumber(reaper.GetExtState(SEC, "loopMax")) or 0
        if ls and le and le > ls then
            local new_key = string.format("%.5f:%.5f:%d", ls, le, lm)
            if new_key ~= s_key then loop_arm(ls, le, lm) end
        end
    end

    if s_active then
        if ctrl == "off" then loop_cleanup(); return end

        local ps = reaper.GetPlayState()  -- 0=stop 1=play 2=pause 4=rec 5=rec+play
        if ps == 0 then loop_cleanup(); return end

        if ps ~= 2 then
            local pos = reaper.GetPlayPosition()
            if not s_near_end then
                if pos >= (s_end - NEAR_END) then s_near_end = true end
            else
                if pos >= (s_start - 0.10) and pos <= (s_start + NEAR_START) then
                    s_crosses  = s_crosses + 1
                    s_near_end = false
                    if s_max > 0 and s_crosses >= s_max then loop_cleanup(); return end
                elseif pos > s_start + NEAR_START then
                    s_near_end = false
                end
            end
        end
    end
end

----------------------------------------------------------------------------
-- 2) + 3)  LYRICS / CHORDS NOTE BRIDGE  (formerly X-Raym scripts)
----------------------------------------------------------------------------
-- One reusable bridge object per named track. Sends the item-note text under
-- the play/edit cursor to a Project ExtState the web interface polls.

local NEXT_SUPPORT = false  -- keep parity with shipped scripts (next item preview off)

local function bridge_new(track_name, ext_name, status_key)
    return {
        track_name = track_name,
        ext_name   = ext_name,
        status_key = status_key,  -- ExtState key ReaSet.html polls for diagnostics
        track      = nil,
        text       = nil,
        next_text  = nil,
        status     = nil,
    }
end

-- Publishes what this bridge is actually doing, so the web UI can tell apart
-- the failure modes that otherwise all look like "no lyrics showing":
--   ""          → key absent/cleared: this script is not running at all
--   "!NOTRACK"  → script alive, but no track matched the keyword
--   "!NOSWS"    → track found, but SWS/ULT_GetMediaItemNote is unavailable
--   "<name>"    → track found and readable (shows the real REAPER track name)
-- Written as non-persistent global ExtState so it dies with REAPER and is
-- never baked into the project file (which would strand a stale status).
local function bridge_publish_status(b, value)
    if b.status ~= value then
        b.status = value
        reaper.SetExtState(SEC, b.status_key, value, false)
    end
end

-- Normalises a track name for matching. The track must still BE the keyword —
-- we only strip decoration around it, so detection stays predictable:
--   • case is ignored            → "LYRICS", "Lyrics", "lyrics"
--   • leading symbols are ignored → "*Lyrics", "##Chords", "-- lyrics", "[Chords]"
--   • leading numbering ignored   → "01 Lyrics", "3 - Chords"
--   • trailing symbols ignored    → "Lyrics*", "Chords --", "[Lyrics]"
-- Anything that leaves extra WORDS behind does NOT match, on purpose:
-- "Backing Lyrics" or "Lyrics Bus" stay ordinary audio tracks.
local function normalize_track_name(name)
    local s = name:lower()
    -- Strip leading decoration repeatedly so mixed prefixes like "* 01 - " unwind
    -- in any order. Each pass can only shorten s, so this always terminates.
    local prev
    repeat
        prev = s
        s = s:gsub("^[^%w]+", "")   -- symbols / spaces: * # - _ > / [ .
        s = s:gsub("^%d+", "")      -- numbering: 01, 3, 12
    until s == prev
    s = s:gsub("[^%w]+$", "")       -- trailing symbols / spaces
    return s
end

-- Returns the first track (top-down) whose normalised name equals the keyword.
local function bridge_find_track(b)
    local n = reaper.CountTracks(0)
    for i = 0, n - 1 do
        local tr = reaper.GetTrack(0, i)
        local _, name = reaper.GetTrackName(tr)
        if normalize_track_name(name) == b.track_name then return tr end
    end
    return nil
end

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

local function next_item(track, pos)
    local n = reaper.GetTrackNumMediaItems(track)
    for i = 0, n - 1 do
        local item = reaper.GetTrackMediaItem(track, i)
        if reaper.GetMediaItemInfo_Value(item, "D_POSITION") > pos then return item end
    end
    return nil
end

-- Reads note, writes ExtState only on change. Returns the new cached text.
local function process_notes(ext_name, ext_key, item, cached)
    if not item then
        if cached ~= STR_NO_TEXT then
            reaper.SetProjExtState(0, ext_name, ext_key, STR_NO_TEXT)
        end
        return STR_NO_TEXT
    end
    if not HAS_ULT then return cached end
    local ok, note = pcall(reaper.ULT_GetMediaItemNote, item)
    if not ok or note == nil then return cached end
    note = note:gsub("\r?\n", "<br>")
    if note ~= cached then
        local out = (note == "") and STR_NO_TEXT or note
        reaper.SetProjExtState(0, ext_name, ext_key, out)
        return out
    end
    return cached
end

local function bridge_tick(b, cur_pos)
    if not reaper.ValidatePtr(b.track, 'MediaTrack*') then
        b.track = bridge_find_track(b)   -- (re)acquire; stays nil if track absent
        if not b.track then
            bridge_publish_status(b, "!NOTRACK")
            return
        end
    end
    if not HAS_ULT then
        -- Track exists but item notes cannot be read without SWS.
        bridge_publish_status(b, "!NOSWS")
        return
    end
    local _, tname = reaper.GetTrackName(b.track)
    bridge_publish_status(b, tname)
    local item = item_at_pos(b.track, cur_pos)
    b.text = process_notes(b.ext_name, "text", item, b.text)
    if NEXT_SUPPORT then
        b.next_text = process_notes(b.ext_name, "next", next_item(b.track, cur_pos), b.next_text)
    end
end

local lyrics = bridge_new("lyrics", "XR_Lyrics", "lyricsTrack")
local chords = bridge_new("chords", "XR_Chords", "chordsTrack")

----------------------------------------------------------------------------
-- MAIN DEFER LOOP  — drives all three subsystems from one tick
----------------------------------------------------------------------------

local _hb_tick = 0

local function main()
    -- Heartbeat so ReaSet.html auto-detects this script is alive (~5 s).
    _hb_tick = _hb_tick + 1
    if _hb_tick % 150 == 0 then
        reaper.SetExtState(SEC, "nativeLoopReady", "1", false)
    end

    -- 1) Loop engine
    loop_tick()

    -- 2/3) Lyrics + Chords note bridges (share the same cursor position)
    local cur_pos = reaper.GetPlayState() > 0
        and reaper.GetPlayPosition() or reaper.GetCursorPosition()
    bridge_tick(lyrics, cur_pos)
    bridge_tick(chords, cur_pos)

    reaper.defer(main)
end

----------------------------------------------------------------------------
-- CLEAN EXIT  — clear published note state so the web UI shows "not running"
----------------------------------------------------------------------------

local function on_exit()
    reaper.SetProjExtState(0, "XR_Lyrics", "text", "")
    reaper.SetProjExtState(0, "XR_Lyrics", "next", "")
    reaper.SetProjExtState(0, "XR_Chords", "text", "")
    reaper.SetProjExtState(0, "XR_Chords", "next", "")
    -- Clear bridge diagnostics so the UI reports "script not running".
    reaper.SetExtState(SEC, "lyricsTrack", "", false)
    reaper.SetExtState(SEC, "chordsTrack", "", false)
    if s_active then loop_cleanup() end
    -- Drop the presence flag so ReaSet falls back to JS loop next session.
    reaper.SetExtState(SEC, "nativeLoopReady", "0", false)
end

----------------------------------------------------------------------------
-- BOOT
----------------------------------------------------------------------------

-- Clear any stale "on" loop state left over from a previous REAPER session.
if reaper.GetExtState(SEC, "nativeLoop") == "on" then
    reaper.SetExtState(SEC, "nativeLoop", "done", false)
end

-- Announce presence immediately (non-persistent: vanishes when REAPER closes).
reaper.SetExtState(SEC, "nativeLoopReady", "1", false)

reaper.atexit(on_exit)
reaper.defer(main)
