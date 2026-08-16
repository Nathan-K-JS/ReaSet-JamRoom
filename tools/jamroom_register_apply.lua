-- jamroom_register_apply.lua  — ONE-TIME SETUP  (GPL v3)
-- Registers tools/jamroom_import_apply.lua as a REAPER action and stores its
-- named command id in persistent extstate ("ReaSetJR" / "import_cmd") so the
-- import orchestrator can trigger applies through the web API of the running
-- instance (robust: no second-process race, unlike `reaper.exe -nonewinst`).
-- Run once from the Action list, or via -nonewinst; safe to re-run.

local dir = debug.getinfo(1, "S").source:match("@?(.*[\\/])") or ""
local target = dir .. "jamroom_import_apply.lua"
local cid = reaper.AddRemoveReaScript(true, 0, target, true)
if cid == 0 then
    reaper.SetExtState("ReaSetJR", "import_cmd", "", true)
    reaper.ShowConsoleMsg("[JR import] FAILED to register apply script: " ..
                          target .. "\n")
    return
end
local named = reaper.ReverseNamedCommandLookup(cid)
local cmd = named and ("_" .. named) or tostring(cid)
reaper.SetExtState("ReaSetJR", "import_cmd", cmd, true)  -- persists across restarts
reaper.ShowConsoleMsg("[JR import] Apply script registered as action " ..
                      cmd .. " (stored in extstate ReaSetJR/import_cmd)\n")
