-- jamroom_rechord.lua  — REPLACE ONE SONG'S CHORDS  (GPL v3)
-- ─────────────────────────────────────────────────────────────────────────────
-- Rewrites the chord items for a single song that is ALREADY in the project,
-- so a song imported with poor chord detection can be corrected without
-- re-importing its stems or paying for anything.
--
-- Driven by tools/jamroom_pending_rechord.lua, written by the importer server:
--     return { region = "Band - Song", start = 160.0, ["end"] = 417.5,
--              chords = { { s = 1.2, e = 2.9, name = "F" }, ... } }
-- Chord times are RELATIVE to the song's region start, so the same chord list
-- works no matter where the song sits on the timeline.
--
-- Touches ONLY chord items inside that region: stems, lyrics, the region
-- itself and every other song are left alone. One undo step.
-- ─────────────────────────────────────────────────────────────────────────────

local SEC = "ReaSetJR"
local dir = debug.getinfo(1, "S").source:match("@?(.*[\\/])") or ""

local function fail(why)
    reaper.SetExtState(SEC, "rechord", "failed:" .. why, false)
    reaper.ShowConsoleMsg("[JR rechord] FAILED: " .. why .. "\n")
end

if not reaper.ULT_SetMediaItemNote then
    return fail("SWS extension missing (ULT_SetMediaItemNote)")
end

local okload, job = pcall(dofile, dir .. "jamroom_pending_rechord.lua")
if not okload or type(job) ~= "table" then
    return fail("no pending chord update (" .. tostring(job) .. ")")
end
if not job.region or not job.start or not job["end"] then
    return fail("malformed chord update")
end

-- The chords track, by the same convention the rest of the rig uses.
local function find_track(name)
    local want = name:lower()
    for i = 0, reaper.CountTracks(0) - 1 do
        local tr = reaper.GetTrack(0, i)
        local _, n = reaper.GetTrackName(tr)
        if n:gsub("^%s+", ""):gsub("%s+$", ""):lower() == want then return tr end
    end
end

-- A song's chords are placed against its lyrics, so a lyric fix has to be able
-- to rewrite both together. Either list may be absent: a chords-only update
-- must not touch the lyrics track, and vice versa.
if job.chords and not find_track("chords") then
    return fail('no track named "chords" in this project')
end
if job.lyrics and not find_track("lyrics") then
    return fail('no track named "lyrics" in this project')
end

-- Confirm the region really is where the server thinks it is, so a stale list
-- can never rewrite the wrong song.
local found = false
do
    local i = 0
    while true do
        local ok, isrgn, s, e, name = reaper.EnumProjectMarkers2(0, i)
        if ok == 0 then break end
        if isrgn and (name or ""):gsub("^%s+", ""):gsub("%s+$", "") == job.region
                 and math.abs(s - job.start) < 0.05 then
            found = true
            break
        end
        i = i + 1
    end
end
if not found then
    return fail('song "' .. job.region .. '" is not at that position any more')
end

reaper.Undo_BeginBlock()
reaper.PreventUIRefresh(1)

-- Out with the old, in with the new — for whichever track this update carries.
-- Items are matched by their START lying inside the song, so neighbouring
-- songs and every other track are untouched.
local function replace(track_name, items)
    local tr = find_track(track_name)
    if not tr or not items then return 0, 0 end
    local removed, added = 0, 0
    for ii = reaper.CountTrackMediaItems(tr) - 1, 0, -1 do
        local it = reaper.GetTrackMediaItem(tr, ii)
        local p = reaper.GetMediaItemInfo_Value(it, "D_POSITION")
        if p >= job.start - 0.001 and p < job["end"] then
            reaper.DeleteTrackMediaItem(tr, it)
            removed = removed + 1
        end
    end
    for _, c in ipairs(items) do
        local s = job.start + (c.s or 0)
        local e = job.start + (c.e or 0)
        local txt = c.name or c.text
        if e > s and txt and txt ~= "" then
            if e > job["end"] then e = job["end"] end
            local it = reaper.AddMediaItemToTrack(tr)
            reaper.SetMediaItemInfo_Value(it, "D_POSITION", s)
            reaper.SetMediaItemInfo_Value(it, "D_LENGTH", e - s)
            reaper.ULT_SetMediaItemNote(it, txt)
            added = added + 1
        end
    end
    return removed, added
end

local removed, added = replace("chords", job.chords)
local lremoved, ladded = replace("lyrics", job.lyrics)

reaper.PreventUIRefresh(-1)
reaper.UpdateArrange()
reaper.Undo_EndBlock((job.lyrics and "Replace lyrics and chords: "
                                 or "Replace chords: ") .. job.region, -1)

local summary = string.format('rechorded="%s" removed=%d added=%d',
                              job.region, removed, added)
if job.lyrics then
    summary = summary .. string.format(' lyrics_removed=%d lyrics_added=%d',
                                       lremoved, ladded)
end
local rf = io.open(dir .. "jamroom_rechord_receipt.txt", "w")
if rf then rf:write(summary .. "\n") rf:close() end
os.remove(dir .. "jamroom_pending_rechord.lua")
reaper.SetExtState(SEC, "rechord", "done:" .. job.region, false)
reaper.ShowConsoleMsg("[JR rechord] " .. summary ..
    "\n  (one Ctrl+Z in REAPER restores the previous chords)\n")
