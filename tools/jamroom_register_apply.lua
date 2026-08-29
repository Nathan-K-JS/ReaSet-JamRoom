-- jamroom_register_apply.lua  — ONE-TIME SETUP  (GPL v3)
-- Registers the importer's REAPER-side scripts as actions and stores their
-- named command ids in persistent extstate, so the importer can trigger them
-- through the web API of the RUNNING instance (robust: no second-process race,
-- unlike `reaper.exe -nonewinst`).
-- Run once from the Action list, or via -nonewinst; safe to re-run.

local dir = debug.getinfo(1, "S").source:match("@?(.*[\\/])") or ""
local report = {}

local function register(file, key, label)
    local target = dir .. file
    local fh = io.open(target, "r")
    if not fh then
        report[#report + 1] = label .. ": file not found (" .. target .. ")"
        return
    end
    fh:close()
    local cid = reaper.AddRemoveReaScript(true, 0, target, true)
    if cid == 0 then
        reaper.SetExtState("ReaSetJR", key, "", true)
        report[#report + 1] = label .. ": FAILED to register"
        return
    end
    local named = reaper.ReverseNamedCommandLookup(cid)
    local cmd = named and ("_" .. named) or tostring(cid)
    reaper.SetExtState("ReaSetJR", key, cmd, true)   -- persists across restarts
    report[#report + 1] = label .. ": " .. cmd
end

register("jamroom_import_apply.lua", "import_cmd",  "Apply import")
register("jamroom_delete_song.lua",  "delete_cmd",  "Delete song")
register("jamroom_rechord.lua",      "rechord_cmd", "Replace chords")

reaper.ShowConsoleMsg("[JR import] registered actions:\n  " ..
                      table.concat(report, "\n  ") .. "\n")
