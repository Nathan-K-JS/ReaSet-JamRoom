-- ReaSet_JamRoom_BuildBuses.lua  — ONE-SHOT PROJECT BUILDER  (GPL v3)
-- ─────────────────────────────────────────────────────────────────────────────
-- Builds the permanent Jam Room track layout in the CURRENT project:
--
--   PB DRUMS            folder, hardware out 1-2, master send OFF
--     [JR:DRUMS] Drums  the bus songs' drum stems live on
--   PB PERC/FX          folder, hardware out 3 (mono), master send OFF
--     [JR:PERC_FX] Perc/FX
--   ... all ten slots ...
--   lyrics              track the Lyrics view reads (item notes)
--   chords              track the Chords view reads (item notes)
--
-- Run it once per project (Actions -> Load ReaScript -> Run), then save the
-- project — ideally as a project template.
--
-- SAFE TO RE-RUN: anything already present is left completely untouched and
-- reported, so it never clobbers routing you have adjusted by hand. Everything
-- it does is a single undo step. No modal dialogs.
--
-- The [JR:...] sub-buses are created empty. An empty bus shows up for no song
-- (the bridge only lists a bus when it has media inside a song's region), and
-- the song importer reuses these by name rather than making duplicates.
--
-- CHECK THE ROUTING against your X32 before relying on it live: hardware
-- outputs are created exactly as if you had added them by hand, so mono buses
-- take the source's channel 1.
-- ─────────────────────────────────────────────────────────────────────────────

-- dst = 0-based first REAPER hardware output channel; mono = single channel.
-- Mirrors docs/JAMROOM_SETUP.md and the SLOTS table in ReaSet_JamRoom.lua.
local SLOTS = {
    { id = "DRUMS",    pb = "PB DRUMS",    label = "Drums",          dst = 0,  mono = false, x32 = "17-18" },
    { id = "PERC_FX",  pb = "PB PERC/FX",  label = "Perc/FX",        dst = 2,  mono = true,  x32 = "19"    },
    { id = "BASS",     pb = "PB BASS",     label = "Bass",           dst = 3,  mono = true,  x32 = "20"    },
    { id = "GTR1",     pb = "PB GTR 1",    label = "Guitar 1",       dst = 4,  mono = false, x32 = "21-22" },
    { id = "GTR2",     pb = "PB GTR 2",    label = "Guitar 2",       dst = 6,  mono = false, x32 = "23-24" },
    { id = "KEYS",     pb = "PB KEYS",     label = "Keys",           dst = 8,  mono = false, x32 = "25-26" },
    { id = "BVS",      pb = "PB BVs",      label = "Backing Vocals", dst = 10, mono = false, x32 = "27-28" },
    { id = "LEAD_VOX", pb = "PB LEAD VOX", label = "Lead Vocals",    dst = 12, mono = true,  x32 = "29"    },
    { id = "CLICK",    pb = "PB CLICK",    label = "Click",          dst = 13, mono = true,  x32 = "30"    },
    { id = "EXTRA",    pb = "PB EXTRA",    label = "Extras",         dst = 14, mono = false, x32 = "31-32" },
}

local report = {}
local function note(s) report[#report + 1] = s end

local function trim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end

local function find_track(name)
    local want = trim(name):lower()
    for i = 0, reaper.CountTracks(0) - 1 do
        local _, n = reaper.GetTrackName(reaper.GetTrack(0, i))
        if trim(n):lower() == want then return reaper.GetTrack(0, i) end
    end
end

-- Append a track at the end of the project and name it.
local function add_track(name, folderdepth)
    local n = reaper.CountTracks(0)
    reaper.InsertTrackAtIndex(n, false)
    local tr = reaper.GetTrack(0, n)
    reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", name, true)
    reaper.SetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH", folderdepth)
    return tr
end

reaper.Undo_BeginBlock()
reaper.PreventUIRefresh(1)

local outs = reaper.GetNumAudioOutputs()
local created, skipped = 0, 0

for _, s in ipairs(SLOTS) do
    if find_track(s.pb) then
        skipped = skipped + 1
        note(string.format("%-12s already exists — left untouched", s.pb))
    else
        -- PB bus: folder, no master send, hardware output.
        local pb = add_track(s.pb, 1)
        reaper.SetMediaTrackInfo_Value(pb, "B_MAINSEND", 0)
        -- Routing is written even if the current audio device cannot reach that
        -- channel yet, so a template built on a laptop still carries correct
        -- routing to the rig. Shortfalls are reported in the summary instead.
        local snd = reaper.CreateTrackSend(pb, nil)   -- nil dest = hardware out
        local dst = s.mono and (s.dst | 1024) or s.dst
        reaper.SetTrackSendInfo_Value(pb, 1, snd, "I_DSTCHAN", dst)
        -- The song bus that lives inside it; closes the PB folder.
        add_track("[JR:" .. s.id .. "] " .. s.label, -1)
        created = created + 1
        note(string.format("%-12s created  out %s (%s)  ->  X32 %s   +  [JR:%s] %s",
            s.pb, s.mono and tostring(s.dst + 1) or (s.dst + 1) .. "-" .. (s.dst + 2),
            s.mono and "mono" or "stereo", s.x32, s.id, s.label))
    end
end

for _, t in ipairs({ "lyrics", "chords" }) do
    if find_track(t) then
        note(string.format("%-12s already exists — left untouched", t))
    else
        add_track(t, 0)
        note(string.format("%-12s created", t))
    end
end

reaper.PreventUIRefresh(-1)
reaper.TrackList_AdjustWindows(false)
reaper.UpdateArrange()
reaper.Undo_EndBlock("Build Jam Room PB buses", -1)

local summary = string.format("%d PB buses created, %d already present. "
    .. "Audio device outputs available: %d.", created, skipped, outs)
if outs < 16 then
    summary = summary .. "  WARNING: fewer than 16 outputs — enable more in "
        .. "Preferences > Audio > Device, then re-check the routing."
end
reaper.SetExtState("ReaSetJR", "buildbuses", summary, false)
reaper.ShowConsoleMsg("[Jam Room bus builder]\n" .. table.concat(report, "\n")
    .. "\n\n" .. summary .. "\nNow SAVE the project (and consider "
    .. "File > Project templates > Save as template).\n")
