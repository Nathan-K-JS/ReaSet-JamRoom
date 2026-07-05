-- ReaSet_JamRoom_TestProject.lua  — ONE-SHOT TEST/DEMO UTILITY  (GPL v3)
-- ─────────────────────────────────────────────────────────────────────────────
-- Builds a complete Jam Room test project in the CURRENT (empty) project tab:
-- all 10 permanent PB buses, example [JR:...] arrangement buses with dummy
-- MIDI items, two song regions, and several deliberate misconfigurations to
-- exercise the Setup issues diagnostics of ReaSet_JamRoom.lua.
--
-- USE:
--   1. File → New project tab  (must be EMPTY — the script refuses otherwise)
--   2. Actions → Show action list → Load ReaScript → select this file → Run
--   3. Run ReaSet_JamRoom.lua, then open ReaSet.html → TRACKS
--
-- Everything is undoable in one step (Edit → Undo).
--
-- Expected result in ReaSet's Tracks tab:
--   Test Song A (0–60s):   Drums, Acoustic Gtr, Click(click section)
--                          + issue: duplicate KEYS claim (Piano vs Organ)
--   Test Song B (70–130s): Drums, Lead Gtr, Piano, Backing Vocals, Click
--   Global setup issues:   empty label on [JR:BASS], routing mismatch on
--                          [JR:EXTRA] Synth Pad, unknown slot BADSLOT
-- ─────────────────────────────────────────────────────────────────────────────

-- No modal dialogs: results go to the ReaScript console and to the
-- "ReaSetJR/testbuilder" extstate key so remote test tooling can check them.
if reaper.CountTracks(0) > 0 then
    reaper.SetExtState("ReaSetJR", "testbuilder", "refused_not_empty", false)
    reaper.ShowConsoleMsg("[Jam Room test builder] Refused: project tab is not " ..
        "empty.\nFile -> New project tab, then run it again.\n")
    return
end

-- A = items overlapping Test Song A (0-60), B = Test Song B (70-130)
local A, B = { 10, 50 }, { 80, 120 }

-- { name, folderdepth, items... }   folderdepth: 1 opens folder, -1 closes
local DEFS = {
    { "PB DRUMS",                 1        },
    { "[JR:DRUMS] Drums",        -1, A, B  },
    { "PB PERC/FX",               0        },
    { "PB BASS",                  1        },
    { "[JR:BASS]",               -1, A     },  -- error: empty label
    { "PB GTR 1",                 1        },
    { "[jr : gtr1] Acoustic Gtr", 0, A     },  -- sloppy tag spacing: must parse
    { "[JR:GTR1] Lead Gtr",      -1, B     },  -- same slot, other song: valid
    { "PB GTR 2",                 0        },
    { "PB KEYS",                  1        },
    { "[JR:KEYS] Piano",          0, A, B  },  -- valid in B; duplicate in A...
    { "[JR:KEYS] Organ",         -1, A     },  -- ...because Organ also claims A
    { "PB BVs",                   1        },
    { "[JR:BVS] Backing Vocals", -1, B     },
    { "PB LEAD VOX",              0        },
    { "PB CLICK",                 1        },
    { "[JR:CLICK] Click",        -1, A, B  },
    { "PB EXTRA",                 0        },
    { "[JR:EXTRA] Synth Pad",     0, A     },  -- error: not inside PB EXTRA
    { "[JR:BADSLOT] Weird",       0, A     },  -- error: unknown slot ID
}

reaper.Undo_BeginBlock()
reaper.PreventUIRefresh(1)

for i, def in ipairs(DEFS) do
    reaper.InsertTrackAtIndex(i - 1, false)
    local tr = reaper.GetTrack(0, i - 1)
    reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", def[1], true)
    reaper.SetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH", def[2])
    for j = 3, #def do
        reaper.CreateNewMIDIItemInProj(tr, def[j][1], def[j][2], false)
    end
end

reaper.AddProjectMarker2(0, true,  0,  60, "Test Song A", -1, 0)
reaper.AddProjectMarker2(0, true, 70, 130, "Test Song B", -1, 0)

reaper.PreventUIRefresh(-1)
reaper.UpdateArrange()
reaper.Undo_EndBlock("Build Jam Room test project", -1)

reaper.SetExtState("ReaSetJR", "testbuilder", "built", false)
reaper.ShowConsoleMsg("[Jam Room test builder] Test project built: 20 tracks " ..
    "(10 PB buses + JR buses with dummy items), 2 song regions, 4 deliberate " ..
    "setup errors.\nNow run ReaSet_JamRoom.lua and open ReaSet.html -> TRACKS.\n")
