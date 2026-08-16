-- jamroom_import_apply.lua  — ONE-SHOT IMPORT APPLY  (GPL v3)
-- ─────────────────────────────────────────────────────────────────────────────
-- Part of the ReaSet Jam Room one-shot song import (see docs/JAMROOM_IMPORT.md).
--
-- Consumes a job folder produced by tools/jamroom_import.py and mutates the
-- CURRENT project: places stem items on [JR:...] buses under the permanent PB
-- buses, adds the "{Band} - {Song}" region, and creates timed text items on
-- the "lyrics" / "chords" tracks (item NOTES, as the X-Raym publisher scripts
-- read them).
--
-- Job selection: reads tools/jamroom_pending_job.txt (absolute path to the job
-- folder, written by jamroom_import.py). The whole mutation is ONE undo step.
-- Results: ReaScript console + "<job>/applied.txt" + extstate ReaSetJR/importer
-- (non-persistent) so the orchestrator can confirm without guessing.
-- No modal dialogs ever (automation-safe).
-- ─────────────────────────────────────────────────────────────────────────────

local SEC = "ReaSetJR"

-- PB bus names per slot — must match ReaSet_JamRoom.lua SLOTS (single source of
-- truth there; duplicated here because this is a standalone one-shot script).
local PB_BY_SLOT = {
    DRUMS = "PB DRUMS", PERC_FX = "PB PERC/FX", BASS = "PB BASS",
    GTR1 = "PB GTR 1", GTR2 = "PB GTR 2", KEYS = "PB KEYS",
    BVS = "PB BVs", LEAD_VOX = "PB LEAD VOX", CLICK = "PB CLICK",
    EXTRA = "PB EXTRA",
}

local SONG_GAP = 30       -- silence between the previous project end and the new song
local msgs = {}
local function log(s) msgs[#msgs + 1] = s end

local function fail(why)
    reaper.SetExtState(SEC, "importer", "failed:" .. why, false)
    reaper.ShowConsoleMsg("[JR import apply] FAILED: " .. why .. "\n" ..
        table.concat(msgs, "\n") .. "\n")
end

local function trim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end

-- ─── Locate and load the job ─────────────────────────────────────────────────

local script_dir = debug.getinfo(1, "S").source:match("@?(.*[\\/])") or ""
local pointer = script_dir .. "jamroom_pending_job.txt"
local f = io.open(pointer, "r")
if not f then return fail("no pending job (missing " .. pointer .. ")") end
local job_dir = trim(f:read("*a") or ""); f:close()
if job_dir == "" then return fail("empty pending-job pointer") end
job_dir = job_dir:gsub("\\", "/"):gsub("/$", "")

local okload, job = pcall(dofile, job_dir .. "/job_for_reaper.lua")
if not okload or type(job) ~= "table" then
    return fail("could not load job_for_reaper.lua: " .. tostring(job))
end

-- ─── Track helpers (folder-depth math mirrors ReaSet_JamRoom.lua) ────────────

local function scan_tracks()
    local tracks, d = {}, 0
    for i = 0, reaper.CountTracks(0) - 1 do
        local tr = reaper.GetTrack(0, i)
        local _, name = reaper.GetTrackName(tr)
        tracks[#tracks + 1] = { tr = tr, name = name, depth = d, idx = i }
        local fd = reaper.GetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH")
        d = d + (fd > 0 and 1 or fd)
        if d < 0 then d = 0 end
    end
    return tracks
end

local function find_track_named(tracks, name)
    local want = name:lower()
    for _, t in ipairs(tracks) do
        if trim(t.name):lower() == want then return t end
    end
end

-- Last index of the subtree rooted at tracks[i] (same-depth walk).
local function subtree_last(tracks, i)
    local last = i
    for j = i + 1, #tracks do
        if tracks[j].depth <= tracks[i].depth then break end
        last = j
    end
    return last
end

-- Get-or-create the "[JR:SLOT] Label" bus nested under its PB folder.
-- Only reuses a bus with our exact label (operator-made custom buses stay
-- untouched). Returns the MediaTrack, or nil + reason.
local function jr_bus(slot, label)
    local tracks = scan_tracks()
    local pbname = PB_BY_SLOT[slot]
    local pb = find_track_named(tracks, pbname)
    if not pb then return nil, "PB bus missing: " .. pbname end
    local last = subtree_last(tracks, pb.idx + 1 and pb.idx + 1 or 1)
    -- (indices in `tracks` are 1-based; pb.idx is 0-based REAPER index)
    local pbi
    for k, t in ipairs(tracks) do if t.tr == pb.tr then pbi = k break end end
    last = subtree_last(tracks, pbi)
    local want = ("[JR:" .. slot .. "] " .. label):lower()
    for k = pbi + 1, last do
        if trim(tracks[k].name):lower() == want then return tracks[k].tr end
    end
    -- Create as new last child of the PB folder.
    local pbfd = reaper.GetMediaTrackInfo_Value(pb.tr, "I_FOLDERDEPTH")
    local newidx  -- 0-based insert position
    local newfd
    if pbfd == 1 then
        local lasttr = tracks[last].tr
        newidx = tracks[last].idx + 1
        newfd = reaper.GetMediaTrackInfo_Value(lasttr, "I_FOLDERDEPTH")
        reaper.SetMediaTrackInfo_Value(lasttr, "I_FOLDERDEPTH", 0)
    else
        newidx = pb.idx + 1
        newfd = pbfd - 1
        reaper.SetMediaTrackInfo_Value(pb.tr, "I_FOLDERDEPTH", 1)
    end
    reaper.InsertTrackAtIndex(newidx, false)
    local tr = reaper.GetTrack(0, newidx)
    reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", "[JR:" .. slot .. "] " .. label, true)
    reaper.SetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH", newfd)
    log("created bus [JR:" .. slot .. "] " .. label)
    return tr
end

-- Get-or-create a top-level utility track (lyrics / chords) at project end.
local function util_track(name)
    local t = find_track_named(scan_tracks(), name)
    if t then return t.tr end
    local n = reaper.CountTracks(0)
    reaper.InsertTrackAtIndex(n, false)
    local tr = reaper.GetTrack(0, n)
    reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", name, true)
    reaper.SetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH", 0)
    log("created track: " .. name)
    return tr
end

-- Empty item with notes (what the X-Raym publisher scripts read).
local function note_item(tr, pos, len, text)
    local it = reaper.AddMediaItemToTrack(tr)
    reaper.SetMediaItemInfo_Value(it, "D_POSITION", pos)
    reaper.SetMediaItemInfo_Value(it, "D_LENGTH", len)
    reaper.ULT_SetMediaItemNote(it, text)
    return it
end

-- ─── Preconditions ───────────────────────────────────────────────────────────

if not reaper.ULT_SetMediaItemNote then
    return fail("SWS extension missing (ULT_SetMediaItemNote) — required for " ..
                "lyrics/chords items")
end
if not job.region_name or job.region_name == "" then
    return fail("job has no region_name")
end

-- The ACTIVE project tab must actually be the Jam Room project. Without this
-- check a wrong/empty active tab silently swallows the whole import.
do
    local found = false
    local tracks = scan_tracks()
    for _, pb in pairs(PB_BY_SLOT) do
        if find_track_named(tracks, pb) then found = true break end
    end
    if not found then
        return fail("the active project tab has no PB buses - switch REAPER " ..
                    "to the Jam Room project tab, then apply again")
    end
end

-- Refuse a duplicate import: a region with this exact name already exists.
do
    local i = 0
    while true do
        local ok, isrgn, _, _, name = reaper.EnumProjectMarkers2(0, i)
        if ok == 0 then break end
        if isrgn and trim(name) == job.region_name then
            return fail("region already exists: \"" .. job.region_name ..
                        "\" — delete it (and its items) first, or rename")
        end
        i = i + 1
    end
end

-- ─── Compute insert position: after everything, plus a gap ───────────────────

local proj_end = 0
do
    local i = 0
    while true do
        local ok, isrgn, pos, rgnend = reaper.EnumProjectMarkers2(0, i)
        if ok == 0 then break end
        if isrgn and rgnend > proj_end then proj_end = rgnend end
        i = i + 1
    end
    for ti = 0, reaper.CountTracks(0) - 1 do
        local tr = reaper.GetTrack(0, ti)
        for ii = 0, reaper.CountTrackMediaItems(tr) - 1 do
            local it = reaper.GetTrackMediaItem(tr, ii)
            local e = reaper.GetMediaItemInfo_Value(it, "D_POSITION") +
                      reaper.GetMediaItemInfo_Value(it, "D_LENGTH")
            if e > proj_end then proj_end = e end
        end
    end
end
local song_pos = proj_end == 0 and 0 or (math.ceil(proj_end) + SONG_GAP)

-- ─── Apply (single undo step) ────────────────────────────────────────────────

reaper.Undo_BeginBlock()
reaper.PreventUIRefresh(1)

local placed, skipped = 0, {}
local song_len = job.duration or 0

for _, s in ipairs(job.slots or {}) do
    local tr, why = jr_bus(s.slot, s.label)
    if not tr then
        skipped[#skipped + 1] = s.slot .. " (" .. why .. ")"
    else
        local src = reaper.PCM_Source_CreateFromFile(s.file)
        local srclen = src and reaper.GetMediaSourceLength(src) or 0
        if not src or srclen < 0.1 then
            -- refuse to place an invisible zero-length item (this happens
            -- when the file isn't really the format its extension claims)
            skipped[#skipped + 1] = s.slot .. " (unreadable/zero-length: " ..
                                    s.file .. ")"
        else
            local it = reaper.AddMediaItemToTrack(tr)
            reaper.SetMediaItemInfo_Value(it, "D_POSITION", song_pos)
            local take = reaper.AddTakeToMediaItem(it)
            reaper.SetMediaItemTake_Source(take, src)
            local len = srclen
            reaper.SetMediaItemInfo_Value(it, "D_LENGTH", len)
            reaper.GetSetMediaItemTakeInfo_String(take, "P_NAME",
                job.region_name .. " — " .. s.label, true)
            if len > song_len then song_len = len end
            placed = placed + 1
        end
    end
end

if song_len == 0 then
    reaper.PreventUIRefresh(-1)
    reaper.Undo_EndBlock("JR import (aborted)", -1)
    return fail("no stems placed and no duration in job — nothing to import")
end

reaper.AddProjectMarker2(0, true, song_pos, song_pos + song_len,
                         job.region_name, -1, 0)
log(string.format("region \"%s\" at %.1fs-%.1fs", job.region_name, song_pos,
                  song_pos + song_len))

-- Lyrics: one note-item per synced line, extended to the next line's
-- timestamp (empty lines act as gap terminators only). Plain fallback: one
-- item spanning the song.
local nlyr = 0
if job.lyrics_lines and #job.lyrics_lines > 0 then
    local tr = util_track("lyrics")
    for i, ln in ipairs(job.lyrics_lines) do
        if ln.text and ln.text ~= "" then
            local s = ln.t
            -- until the next line, but never linger more than 15s (a stale
            -- line during an instrumental break reads as wrong, not helpful)
            local e = job.lyrics_lines[i + 1] and job.lyrics_lines[i + 1].t
                      or song_len
            e = math.min(e, s + 15, song_len)
            if e > s then
                note_item(tr, song_pos + s, e - s, ln.text)
                nlyr = nlyr + 1
            end
        end
    end
elseif job.lyrics_plain and job.lyrics_plain ~= "" then
    note_item(util_track("lyrics"), song_pos, song_len, job.lyrics_plain)
    nlyr = 1
    log("plain (unsynced) lyrics imported as one block")
end

local nch = 0
if job.chords and #job.chords > 0 then
    local tr = util_track("chords")
    for _, c in ipairs(job.chords) do
        if c.name and c.name ~= "" and c.e > c.s then
            note_item(tr, song_pos + c.s, c.e - c.s, c.name)
            nch = nch + 1
        end
    end
end

reaper.PreventUIRefresh(-1)
reaper.UpdateArrange()
reaper.Undo_EndBlock("JR import: " .. job.region_name, -1)

-- ─── Report (console + applied.txt + extstate; never modal) ──────────────────

local summary = string.format(
    "region=\"%s\" pos=%.1f stems=%d lyrics_items=%d chord_items=%d%s",
    job.region_name, song_pos, placed, nlyr, nch,
    #skipped > 0 and (" SKIPPED: " .. table.concat(skipped, ", ")) or "")
local af = io.open(job_dir .. "/applied.txt", "w")
if af then af:write(summary .. "\n") af:close() end
os.remove(pointer)
reaper.SetExtState(SEC, "importer", "applied:" .. job.region_name, false)
reaper.ShowConsoleMsg("[JR import apply] " .. summary .. "\n" ..
    (#msgs > 0 and (table.concat(msgs, "\n") .. "\n") or ""))
