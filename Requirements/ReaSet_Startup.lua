-- ReaSet_Startup.lua  — LAUNCH EVERYTHING  (GPL v3)
-- ─────────────────────────────────────────────────────────────────────────────
-- ReaSet needs FOUR background scripts running, but REAPER's startup-action
-- slot holds only ONE action. This script launches all four, so a single
-- startup action covers the lot.
--
-- INSTALL (one time):
--   Actions → Show action list → Load ReaScript… → select this file
--   Then either:
--     • Options → Preferences → General → set this as the startup action, or
--     • copy this file to  %APPDATA%\REAPER\Scripts\__startup.lua
--       (REAPER auto-runs a script with that exact name at launch)
--
-- WHAT IT STARTS
--   ReaSet_JamRoom.lua      — Tracks tab / backing-group mute bridge
--   ReaSet_NativeLoop.lua   — REAPER-native looping for ReaSet
--   X-Raym Lyrics …lua      — feeds the Lyrics view
--   X-Raym Chords …lua      — feeds the Chords view
--
-- The two X-Raym scripts abort with a MODAL error box if the project has no
-- track named "lyrics" / "chords" — a modal freezes REAPER and would block the
-- song importer. So this script checks for those tracks first and skips those
-- two (with a console note) rather than risking a hung UI on a project that
-- does not use them.
-- ─────────────────────────────────────────────────────────────────────────────

local dir = debug.getinfo(1, "S").source:match("@?(.*[\\/])") or ""

local function has_track_named(want)
    want = want:lower()
    for i = 0, reaper.CountTracks(0) - 1 do
        local _, name = reaper.GetTrackName(reaper.GetTrack(0, i))
        if name:gsub("^%s+", ""):gsub("%s+$", ""):lower() == want then
            return true
        end
    end
    return false
end

-- Liveness probes. Each background script advertises itself with a
-- NON-persistent flag that its atexit handler clears, so these are reliable
-- across REAPER restarts and crashes.
local function bridge_alive()
    return reaper.GetExtState("ReaSetJR", "heartbeat") ~= ""
end
local function nativeloop_alive()
    return reaper.GetExtState("ReaSet", "nativeLoopReady") == "1"
end
local function chordslyrics_alive()
    return reaper.GetExtState("ReaSetCL", "heartbeat") ~= ""
end
local function tempokey_alive()
    return reaper.GetExtState("ReaSetTK", "heartbeat") ~= ""
end

-- Register a script and run it — but only if it is not already running.
-- Firing the command of a live defer script makes REAPER pop its modal
-- "ReaScript task control" dialog, which would hang an unattended startup
-- and block the song importer's web-API trigger.
local function launch(file, label, alive_fn)
    local path = dir .. file
    local f = io.open(path, "r")
    if not f then
        return false, label .. ": file not found (" .. path .. ")"
    end
    f:close()
    local cmd = reaper.AddRemoveReaScript(true, 0, path, true)
    if cmd == 0 then
        return false, label .. ": could not register"
    end
    -- X-Raym scripts report via toggle state; ours via their own flags.
    local alive
    if alive_fn then alive = alive_fn()
    else alive = (reaper.GetToggleCommandState(cmd) == 1) end
    if alive then
        return true, label .. ": already running"
    end
    reaper.Main_OnCommand(cmd, 0)
    return true, label .. ": started"
end

local report = {}
local function note(ok, msg) report[#report + 1] = (ok and "  [ok] " or "  [--] ") .. msg end

note(launch("ReaSet_JamRoom.lua", "Jam Room bridge", bridge_alive))
note(launch("ReaSet_NativeLoop.lua", "Native loop", nativeloop_alive))
-- Publishes the current song's whole chord/lyric timeline. Safe on any
-- project: with no chords/lyrics tracks it simply publishes nothing.
note(launch("ReaSet_ChordsLyrics.lua", "Chord/lyric timeline", chordslyrics_alive))
-- Per-song tempo (playrate, pitch preserved) and key (item pitch) control.
note(launch("ReaSet_TempoKey.lua", "Tempo/key control", tempokey_alive))

if has_track_named("lyrics") then
    note(launch("X-Raym_Convert Lyrics track items notes for dedicated web browser interface.lua",
                "Lyrics publisher"))
else
    note(false, 'Lyrics publisher: skipped — no track named "lyrics" in this project')
end

if has_track_named("chords") then
    note(launch("X-Raym_Convert Chords track items notes for dedicated web browser interface.lua",
                "Chords publisher"))
else
    note(false, 'Chords publisher: skipped — no track named "chords" in this project')
end

-- Console only; never a modal (this may run unattended at REAPER startup).
-- Also published to extstate so setup tooling can verify without the console.
reaper.ShowConsoleMsg("[ReaSet startup]\n" .. table.concat(report, "\n") .. "\n")
reaper.SetExtState("ReaSetJR", "startup", table.concat(report, " ;; "), false)
