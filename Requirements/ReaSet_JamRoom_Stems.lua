-- ReaSet_JamRoom_Stems.lua
-- Jam Room Milestone 1: read-only stem status bridge.
--
-- Runs as a deferred background ReaScript and publishes project extstate:
--   Section: ReaSetJamRoom
--   Key: controls
--
-- This script discovers active [JR:SLOT_ID] Display Label folder buses for the
-- current top-level song region, resolves their permanent PB buses, reads PB
-- mute state, and publishes JSON for ReaSet.html. It never changes audio state.

local SECTION = "ReaSetJamRoom"
local KEY = "controls"
local LOOP_REGION_NAME = "ReaSet Loop"

local SLOT_ORDER = {
    "DRUMS",
    "PERC_FX",
    "BASS",
    "GTR1",
    "GTR2",
    "KEYS",
    "BVS",
    "LEAD_VOX",
    "CLICK",
    "EXTRA"
}

local PB_BY_SLOT = {
    DRUMS = "PB DRUMS",
    PERC_FX = "PB PERC/FX",
    BASS = "PB BASS",
    GTR1 = "PB GTR 1",
    GTR2 = "PB GTR 2",
    KEYS = "PB KEYS",
    BVS = "PB BVs",
    LEAD_VOX = "PB LEAD VOX",
    CLICK = "PB CLICK",
    EXTRA = "PB EXTRA"
}

local VALID_SLOT = {}
for _, slot in ipairs(SLOT_ORDER) do
    VALID_SLOT[slot] = true
end

local function json_escape(value)
    value = tostring(value or "")
    value = value:gsub("\\", "\\\\")
    value = value:gsub('"', '\\"')
    value = value:gsub("\b", "\\b")
    value = value:gsub("\f", "\\f")
    value = value:gsub("\n", "\\n")
    value = value:gsub("\r", "\\r")
    value = value:gsub("\t", "\\t")
    value = value:gsub("[%z\1-\31]", function(c)
        return string.format("\\u%04x", string.byte(c))
    end)
    return '"' .. value .. '"'
end

local function json_bool(value)
    return value and "true" or "false"
end

local function json_number(value)
    value = tonumber(value)
    if not value then return "null" end
    return string.format("%.6f", value):gsub("0+$", ""):gsub("%.$", "")
end

local function issue_to_json(issue)
    local parts = {
        '"type":' .. json_escape(issue.type),
        '"severity":' .. json_escape(issue.severity or "error"),
        '"message":' .. json_escape(issue.message)
    }
    if issue.track then parts[#parts + 1] = '"track":' .. json_escape(issue.track) end
    if issue.slot then parts[#parts + 1] = '"slot":' .. json_escape(issue.slot) end
    if issue.pb then parts[#parts + 1] = '"pb":' .. json_escape(issue.pb) end
    return "{" .. table.concat(parts, ",") .. "}"
end

local function control_to_json(control)
    return "{"
        .. '"slot":' .. json_escape(control.slot) .. ","
        .. '"label":' .. json_escape(control.label) .. ","
        .. '"pb":' .. json_escape(control.pb) .. ","
        .. '"muted":' .. json_bool(control.muted)
        .. "}"
end

local function publish(status, song, controls, issues)
    local control_json = {}
    for _, control in ipairs(controls or {}) do
        control_json[#control_json + 1] = control_to_json(control)
    end

    local issue_json = {}
    for _, issue in ipairs(issues or {}) do
        issue_json[#issue_json + 1] = issue_to_json(issue)
    end

    local song_json = "null"
    if song then
        song_json = "{"
            .. '"id":' .. json_escape(song.id or "") .. ","
            .. '"name":' .. json_escape(song.name or "") .. ","
            .. '"start":' .. json_number(song.start) .. ","
            .. '"end":' .. json_number(song["end"])
            .. "}"
    end

    local payload = "{"
        .. '"schema":1,'
        .. '"heartbeat":' .. json_number(reaper.time_precise()) .. ","
        .. '"status":' .. json_escape(status or "ok") .. ","
        .. '"song":' .. song_json .. ","
        .. '"controls":[' .. table.concat(control_json, ",") .. "],"
        .. '"issues":[' .. table.concat(issue_json, ",") .. "]"
        .. "}"

    reaper.SetProjExtState(0, SECTION, KEY, payload)
end

local function get_position()
    local play_state = reaper.GetPlayState()
    if (play_state & 1) == 1 or (play_state & 4) == 4 then
        return reaper.GetPlayPosition()
    end
    return reaper.GetCursorPosition()
end

local function find_active_song_region(pos)
    local best = nil
    local i = 0
    while true do
        local ok, is_region, start_pos, end_pos, name, marker_index = reaper.EnumProjectMarkers(i)
        if ok == 0 then break end
        if is_region and name ~= LOOP_REGION_NAME and pos >= start_pos and pos < end_pos then
            local duration = end_pos - start_pos
            if duration > 0 and (not best or duration > best.duration) then
                best = {
                    id = tostring(marker_index),
                    name = name,
                    start = start_pos,
                    ["end"] = end_pos,
                    duration = duration
                }
            end
        end
        i = i + 1
    end
    return best
end

local function track_name(track)
    local _, name = reaper.GetTrackName(track, "")
    return name or ""
end

local function parse_jr_name(name)
    if not name:match("^%s*%[[Jj][Rr]") then
        return nil, nil, "not_jr"
    end
    local slot, label = name:match("^%s*%[[Jj][Rr]:([^%]]+)%]%s*(.*)$")
    if not slot then
        return nil, nil, "malformed_tag"
    end
    local normalized = slot:upper()
    if label == "" then
        return normalized, label, "missing_label"
    end
    return normalized, label, nil
end

local function find_tracks_by_name(name)
    local matches = {}
    local count = reaper.CountTracks(0)
    for i = 0, count - 1 do
        local track = reaper.GetTrack(0, i)
        if track_name(track) == name then
            matches[#matches + 1] = track
        end
    end
    return matches
end

local function descendant_range(parent_index)
    local count = reaper.CountTracks(0)
    local parent = reaper.GetTrack(0, parent_index)
    if not parent then return parent_index + 1, parent_index end

    local depth = reaper.GetMediaTrackInfo_Value(parent, "I_FOLDERDEPTH")
    if depth <= 0 then return parent_index + 1, parent_index end

    local folder_depth = 1
    local first_child = parent_index + 1
    local last_child = parent_index
    for i = first_child, count - 1 do
        local track = reaper.GetTrack(0, i)
        if not track then break end
        last_child = i
        folder_depth = folder_depth + reaper.GetMediaTrackInfo_Value(track, "I_FOLDERDEPTH")
        if folder_depth <= 0 then
            break
        end
    end
    return first_child, last_child
end

local function item_overlaps_region(item, region_start, region_end)
    local item_start = reaper.GetMediaItemInfo_Value(item, "D_POSITION")
    local item_len = reaper.GetMediaItemInfo_Value(item, "D_LENGTH")
    local item_end = item_start + item_len
    return item_start < region_end and item_end > region_start
end

local function has_descendant_overlap(parent_index, song)
    local first_child, last_child = descendant_range(parent_index)
    if last_child < first_child then return false end

    for i = first_child, last_child do
        local track = reaper.GetTrack(0, i)
        if track then
            local item_count = reaper.CountTrackMediaItems(track)
            for item_index = 0, item_count - 1 do
                local item = reaper.GetTrackMediaItem(track, item_index)
                if item and item_overlaps_region(item, song.start, song["end"]) then
                    return true
                end
            end
        end
    end
    return false
end

local function discover(song)
    local issues = {}
    local candidates_by_slot = {}
    local active_candidates = {}
    local track_count = reaper.CountTracks(0)

    for i = 0, track_count - 1 do
        local track = reaper.GetTrack(0, i)
        local name = track_name(track)
        if name:match("^%s*%[[Jj][Rr]") then
            local first_child, last_child = descendant_range(i)
            if last_child >= first_child and has_descendant_overlap(i, song) then
                local slot, label, parse_error = parse_jr_name(name)
                local candidate = {
                    track = track,
                    track_name = name,
                    slot = slot,
                    label = label,
                    parse_error = parse_error
                }
                active_candidates[#active_candidates + 1] = candidate

                if parse_error == "malformed_tag" then
                    issues[#issues + 1] = {
                        type = "malformed_tag",
                        track = name,
                        message = "Malformed Jam Room tag on active bus: " .. name
                    }
                elseif parse_error == "missing_label" then
                    issues[#issues + 1] = {
                        type = "missing_label",
                        track = name,
                        slot = slot,
                        message = "Missing display label on active Jam Room bus: " .. name
                    }
                elseif slot and not VALID_SLOT[slot] then
                    issues[#issues + 1] = {
                        type = "invalid_slot",
                        track = name,
                        slot = slot,
                        message = "Invalid Jam Room slot on active bus: " .. slot
                    }
                elseif slot then
                    candidates_by_slot[slot] = candidates_by_slot[slot] or {}
                    candidates_by_slot[slot][#candidates_by_slot[slot] + 1] = candidate
                end
            end
        end
    end

    local controls_by_slot = {}
    for slot, candidates in pairs(candidates_by_slot) do
        if #candidates > 1 then
            for _, candidate in ipairs(candidates) do
                issues[#issues + 1] = {
                    type = "duplicate_slot",
                    track = candidate.track_name,
                    slot = slot,
                    message = "Duplicate active Jam Room slot claim: " .. slot
                }
            end
        else
            local candidate = candidates[1]
            local pb_name = PB_BY_SLOT[slot]
            local pb_tracks = pb_name and find_tracks_by_name(pb_name) or {}
            if #pb_tracks == 0 then
                issues[#issues + 1] = {
                    type = "missing_pb",
                    track = candidate.track_name,
                    slot = slot,
                    pb = pb_name,
                    message = "Missing permanent PB bus: " .. tostring(pb_name)
                }
            elseif #pb_tracks > 1 then
                issues[#issues + 1] = {
                    type = "duplicate_pb",
                    track = candidate.track_name,
                    slot = slot,
                    pb = pb_name,
                    message = "Duplicate permanent PB bus: " .. tostring(pb_name)
                }
            else
                local pb_track = pb_tracks[1]
                controls_by_slot[slot] = {
                    slot = slot,
                    label = candidate.label,
                    pb = pb_name,
                    muted = reaper.GetMediaTrackInfo_Value(pb_track, "B_MUTE") == 1
                }
            end
        end
    end

    local controls = {}
    for _, slot in ipairs(SLOT_ORDER) do
        if controls_by_slot[slot] then
            controls[#controls + 1] = controls_by_slot[slot]
        end
    end

    return controls, issues, active_candidates
end

local last_payload_clock = 0
local function main_loop()
    local now = reaper.time_precise()
    if now - last_payload_clock >= 0.50 then
        last_payload_clock = now
        local song = find_active_song_region(get_position())
        if not song then
            publish("no_active_song", nil, {}, {})
        else
            local ok, controls, issues = pcall(function()
                local discovered_controls, discovered_issues = discover(song)
                return discovered_controls, discovered_issues
            end)
            if ok then
                publish("ok", song, controls or {}, issues or {})
            else
                publish("error", song, {}, {
                    {
                        type = "bridge_error",
                        message = tostring(controls)
                    }
                })
            end
        end
    end

    reaper.defer(main_loop)
end

publish("starting", nil, {}, {})
reaper.defer(main_loop)
