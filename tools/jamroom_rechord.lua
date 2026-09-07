-- Song text transaction entry point. GPL-3.0.
local dir = debug.getinfo(1,"S").source:match("@?(.*[\\/])") or ""
dofile(dir .. "jamroom_song_transaction.lua")
