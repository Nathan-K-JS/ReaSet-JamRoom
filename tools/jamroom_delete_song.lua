-- jamroom_delete_song.lua  — REMOVE ONE SONG FROM THE PROJECT  (GPL v3)
-- ─────────────────────────────────────────────────────────────────────────────
-- Deletes a song's REGION and every media item that BEGINS inside it: the
-- stems on the [JR:...] buses, and its lyric/chord note items. Nothing else
-- is touched — the PB buses, the [JR:...] buses themselves and every other
-- song stay exactly as they are, so re-importing later drops straight back in.
--
-- Driven by tools/jamroom_pending_delete.txt, written by the importer server:
--     <song name>
--     <region start seconds>
--     <region end seconds>
--
-- The whole deletion is ONE undo step: Ctrl+Z in REAPER puts the song back,
-- audio and all. Reports to the console, a receipt file, and extstate.
-- No modal dialogs (must not block the importer).
--
-- Items are matched by START position rather than overlap, so a neighbouring
-- song can never be caught even if regions were to touch.
-- ─────────────────────────────────────────────────────────────────────────────

local SEC = "ReaSetJR"
local script_dir = debug.getinfo(1, "S").source:match("@?(.*[\\/])") or ""
local pointer = script_dir .. "jamroom_pending_delete.txt"

local function trim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end

local function fail(why)
    reaper.SetExtState(SEC, "deleter", "failed:" .. why, false)
    reaper.ShowConsoleMsg("[JR delete] FAILED: " .. why .. "\n")
end

local f = io.open(pointer, "r")
if not f then return fail("no pending delete request") end
local body = f:read("*a") or ""; f:close()
body = body:gsub("^\239\187\191", "")           -- tolerate a UTF-8 BOM
local lines = {}
for line in body:gmatch("[^\r\n]+") do lines[#lines + 1] = trim(line) end
if #lines < 3 then return fail("malformed delete request") end

local want_name = lines[1]
local want_s, want_e = tonumber(lines[2]), tonumber(lines[3])
if not want_s or not want_e or want_e <= want_s then
    return fail("bad region bounds in delete request")
end

-- Locate the region by name AND position: never delete on a name match alone.
local rgn_idx, rgn_s, rgn_e = nil, nil, nil
do
    local i = 0
    while true do
        local ok, isrgn, s, e, name, idx = reaper.EnumProjectMarkers2(0, i)
        if ok == 0 then break end
        if isrgn and trim(name) == want_name
                 and math.abs(s - want_s) < 0.05 and math.abs(e - want_e) < 0.05 then
            rgn_idx, rgn_s, rgn_e = idx, s, e
            break
        end
        i = i + 1
    end
end
if not rgn_idx then
    return fail('no region named "' .. want_name .. '" at that position — the '
                .. 'project may have changed since the list was loaded')
end

reaper.Undo_BeginBlock()
reaper.PreventUIRefresh(1)

local removed_items, removed_tracks = 0, {}
for ti = reaper.CountTracks(0) - 1, 0, -1 do
    local tr = reaper.GetTrack(0, ti)
    local _, tname = reaper.GetTrackName(tr)
    for ii = reaper.CountTrackMediaItems(tr) - 1, 0, -1 do
        local it = reaper.GetTrackMediaItem(tr, ii)
        local p = reaper.GetMediaItemInfo_Value(it, "D_POSITION")
        if p >= rgn_s - 0.001 and p < rgn_e then
            reaper.DeleteTrackMediaItem(tr, it)
            removed_items = removed_items + 1
            removed_tracks[tname] = (removed_tracks[tname] or 0) + 1
        end
    end
end

reaper.DeleteProjectMarker(0, rgn_idx, true)

-- Drop the song's stashed detected-BPM entry too (tempo/key control).
reaper.SetProjExtState(0, "ReaSetTK", "bpm:" .. want_name, "")

reaper.PreventUIRefresh(-1)
reaper.UpdateArrange()
reaper.Undo_EndBlock("Delete song: " .. want_name, -1)

local detail = {}
for tname, n in pairs(removed_tracks) do
    detail[#detail + 1] = string.format("%s (%d)", tname, n)
end
table.sort(detail)
local summary = string.format('deleted="%s" items=%d region=1', want_name, removed_items)
local rf = io.open(script_dir .. "jamroom_delete_receipt.txt", "w")
if rf then rf:write(summary .. "\n") rf:close() end
os.remove(pointer)
reaper.SetExtState(SEC, "deleter", "deleted:" .. want_name, false)
reaper.ShowConsoleMsg("[JR delete] " .. summary .. "\n  " ..
    table.concat(detail, "\n  ") .. "\n  (one Ctrl+Z in REAPER undoes this)\n")
