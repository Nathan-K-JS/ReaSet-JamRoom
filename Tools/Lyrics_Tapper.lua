-- Lyrics Tapper.lua  — Interactive synced text tool for ReaSet
-- ─────────────────────────────────────────────────────────────────────────────
-- Supports Lyrics, Chords, and Notes tracks with flexible name matching.
-- Paste text, ARM, tap along to the song — items go to the selected track.
--
-- GUI restyled for a minimal, teleprompter-style flow (paste → ARM → tap),
-- close to Ableset's lyrics tool. The state machine, track matching, section
-- filtering and item-creation logic below are unchanged from the original —
-- only the rendering (from "MAIN LOOP" down) was rewritten.
--
-- DEPENDENCIES:
--   REAPER with ReaImGui extension (reaper_imgui-arm64.dylib)
--   SWS Extension (for ULT_GetMediaItemNote on the bridge side)
-- ─────────────────────────────────────────────────────────────────────────────

package.path = reaper.ImGui_GetBuiltinPath() .. '/?.lua'
local ImGui = require 'imgui' '0.10'

-- ═══════════════════════════════════════════════════════════════════════════
-- COLOR HELPERS
-- ReaImGui colors are packed 0xRRGGBBAA integers — red in the HIGHEST byte,
-- alpha in the LOWEST. (The original version of this helper assumed
-- 0xAARRGGBB — alpha highest, blue lowest — which silently swaps every
-- channel: a green button rendered magenta, and a near-opaque dark window
-- background rendered as an ~8%-alpha red wash, letting REAPER's timeline
-- show straight through it. That mismatch is what produced the illegible,
-- pink-tinted UI — not a bad color choice.)
-- ═══════════════════════════════════════════════════════════════════════════

local function rgba(r, g, b, a)
    a = math.floor((a or 1.0) * 255)
    r = math.floor(r * 255)
    g = math.floor(g * 255)
    b = math.floor(b * 255)
    return (r << 24) | (g << 16) | (b << 8) | a
end

-- ═══════════════════════════════════════════════════════════════════════════
-- THEME  (visual only — a dark, Ableset-inspired palette. Used exclusively by
-- the render section below; nothing here affects state or item creation.)
-- ═══════════════════════════════════════════════════════════════════════════

local THEME = {
    bg              = rgba(0.075, 0.078, 0.086),
    bg_panel        = rgba(0.110, 0.115, 0.125),
    bg_input        = rgba(0.055, 0.058, 0.065),
    bg_input_hov    = rgba(0.085, 0.090, 0.100),
    border          = rgba(0.220, 0.230, 0.250),

    text            = rgba(0.930, 0.935, 0.945),
    text_dim        = rgba(0.560, 0.580, 0.610),
    text_faint      = rgba(0.360, 0.375, 0.400),

    accent          = rgba(0.250, 0.820, 0.560),   -- mint/teal (ARM/TAP/current line)
    accent_hover    = rgba(0.320, 0.880, 0.630),
    accent_active   = rgba(0.190, 0.700, 0.470),
    accent_text     = rgba(0.040, 0.045, 0.045),   -- dark label on bright accent buttons

    warn            = rgba(0.820, 0.660, 0.220),   -- "track will be created"
    ok              = rgba(0.360, 0.780, 0.420),   -- "track found"

    danger          = rgba(0.820, 0.320, 0.320),
    danger_hover    = rgba(0.880, 0.400, 0.400),
    danger_active   = rgba(0.680, 0.250, 0.250),

    ghost           = rgba(1.0, 1.0, 1.0, 0.035),
    ghost_hover     = rgba(1.0, 1.0, 1.0, 0.070),
    ghost_active    = rgba(1.0, 1.0, 1.0, 0.110),
}

-- ═══════════════════════════════════════════════════════════════════════════
-- STATE
-- ═══════════════════════════════════════════════════════════════════════════

local TRACK_TYPES = { [0] = "Lyrics", [1] = "Chords", [2] = "Notes" }

local state          = "idle"    -- "idle" | "tapping"
local track_type_idx = 0        -- index into TRACK_TYPES (0-based: 0=Lyrics)
local lines          = {}        -- parsed lines from pasted text
local current_idx    = 0         -- 0 = none yet, 1..n = next to insert
local last_item      = nil       -- most recently created item
local arm_pos        = 0         -- position when ARM was pressed
local tap_count      = 0
local target_track   = nil       -- the REAPER track we're writing to
local full_text      = ""
local ui_msg         = "Paste your text and press ARM to start."

-- ═══════════════════════════════════════════════════════════════════════════
-- HELPERS
-- ═══════════════════════════════════════════════════════════════════════════

local function get_current_pos()
    if reaper.GetPlayState() > 0 then
        return reaper.GetPlayPosition()
    end
    return reaper.GetCursorPosition()
end

-- ─── Flexible track name matching ──────────────────────────────────────────
-- This MUST stay byte-identical to normalize_track_name() in Reaset.lua.
-- If the two diverge, the web bridge and this tapper can disagree on which
-- track is "the lyrics track" — the tapper writes to one, the bridge reads
-- from another, and it doesn't surface until a show. Confirmed concretely:
-- the previous version of this function only stripped a fixed set of leading
-- symbols (`*-#~.`) and never stripped leading digits, so a track literally
-- named "3 - Chords" matched in Reaset.lua's bridge (which strips leading
-- numbering) but NOT here — the tapper would have silently created a
-- duplicate "Chords" track next to it.
--
-- The track must still BE the keyword, not just contain it — decoration
-- around it is stripped, extra words are not:
--   • case is ignored             → "LYRICS", "Lyrics", "lyrics"
--   • leading symbols ignored     → "*Lyrics", "##Chords", "_Lyrics", ">Lyrics"
--   • leading numbering ignored   → "01 Lyrics", "3 - Chords"
--   • trailing symbols ignored    → "Lyrics*", "Chords --", "[Lyrics]"
-- "Backing Lyrics" or "Lyrics Bus" stay ordinary tracks, on purpose.
local function normalize_track_name(name)
    local s = (name or ""):lower()
    local prev
    repeat
        prev = s
        s = s:gsub("^[^%w]+", "")   -- leading symbols / spaces
        s = s:gsub("^%d+", "")      -- leading numbering: 01, 3, 12
    until s == prev
    s = s:gsub("[^%w]+$", "")       -- trailing symbols / spaces
    return s
end

-- Returns every track whose normalized name matches, and separately which
-- one wins if the caller needs exactly one. Mirrors bridge_find_track() in
-- Reaset.lua: a track WITH items wins over one that has none, even if the
-- empty one comes first — otherwise a divider/folder track like "*LYRICS*"
-- sitting above the real lyrics track silently shadows it forever, because
-- it matches the keyword and simply has no items to place.
local function find_matching_track(canonical)
    local n = reaper.CountTracks(0)
    local matches, with_items = {}, nil
    for i = 0, n - 1 do
        local tr = reaper.GetTrack(0, i)
        local _, name = reaper.GetTrackName(tr)
        if normalize_track_name(name) == canonical:lower() then
            matches[#matches + 1] = tr
            if not with_items and reaper.GetTrackNumMediaItems(tr) > 0 then
                with_items = tr
            end
        end
    end
    return matches, (with_items or matches[1])
end

local function ensure_target_track()
    local canonical = TRACK_TYPES[track_type_idx]

    -- Check cached track still valid
    if target_track and reaper.ValidatePtr(target_track, 'MediaTrack*') then
        local _, name = reaper.GetTrackName(target_track)
        if normalize_track_name(name) == canonical:lower() then
            return target_track
        end
    end
    target_track = nil

    -- Search for existing matching track
    local matches, preferred = find_matching_track(canonical)
    if #matches > 0 then
        target_track = preferred
        return target_track
    end

    -- Create new track with the canonical name
    reaper.InsertTrackAtIndex(reaper.CountTracks(0), true)
    target_track = reaper.GetTrack(0, reaper.CountTracks(0) - 1)
    reaper.GetSetMediaTrackInfo_String(target_track, "P_NAME", canonical, true)
    return target_track
end

-- ─── Smart section filtering ───────────────────────────────────────────────
-- Lines that match these patterns are treated as section headers and skipped.
-- Matching is case-insensitive and applies to the whole trimmed line.

local SECTION_PATTERNS = {
    -- English (bare words, optional number suffix)
    "^chorus[%s%d]*x?$", "^pre%-?chorus[%s%d]*$", "^post%-?chorus[%s%d]*$",
    "^verse[%s%d]*$", "^bridge[%s%d]*$",
    "^intro[%s%d]*$", "^outro[%s%d]*$", "^ending[%s%d]*$",
    "^hook[%s%d]*$", "^refrain[%s%d]*$",
    "^interlude[%s%d]*$", "^instrumental[%s%d]*$", "^solo[%s%d]*$",
    "^break[%s%d]*$", "^drop[%s%d]*$", "^tag[%s%d]*$",
    "^section[%s%d]*$", "^part[%s%d]*$",

    -- English 2-word forms: "pre chorus", "post chorus", etc.
    "^pre chorus[%s%d]*x?$", "^post chorus[%s%d]*x?$",
    "^pre%-?chorus[%s%d]*x?$", "^post%-?chorus[%s%d]*x?$",

    -- Spanish
    "^coro[%s%d]*x?$", "^estribillo[%s%d]*x?$",
    "^verso[%s%d]*$", "^estrofa[%s%d]*$",
    "^puente[%s%d]*$", "^intro[%s%d]*$", "^outro[%s%d]*$",
    "^final[%s%d]*$", "^interludio[%s%d]*$", "^solo[%s%d]*$",

    -- Spanish 2-word forms: "pre coro", "post coro", "pre estribillo", etc.
    "^pre coro[%s%d]*x?$", "^post coro[%s%d]*x?$",
    "^pre estribillo[%s%d]*x?$", "^post estribillo[%s%d]*x?$",
    "^pre%-?coro[%s%d]*x?$", "^post%-?coro[%s%d]*x?$",
    "^pre%-?estribillo[%s%d]*x?$", "^post%-?estribillo[%s%d]*x?$",

    -- Combined words
    "^chorus%s+%d*x?%d*$", "^verse%s+%d+$",

    -- Bracketed/parenthesized English
    "^[%[%(]-chorus[%]%)%}]*$", "^[%[%(]-verse[%s%d]*[%]%)%}]*$",
    "^[%[%(]-bridge[%]%)%}]*$", "^[%[%(]-intro[%]%)%}]*$",
    "^[%[%(]-outro[%]%)%}]*$", "^[%[%(]-solo[%]%)%}]*$",
    "^[%[%(]-hook[%]%)%}]*$", "^[%[%(]-refrain[%]%)%}]*$",
    "^[%[%(]-interlude[%]%)%}]*$",
    "^[%[%(]-pre[%s%-]*chorus[%s%d]*[%]%)%}]*$",
    "^[%[%(]-post[%s%-]*chorus[%s%d]*[%]%)%}]*$",

    -- Bracketed/parenthesized Spanish
    "^[%[%(]-coro[%s%d]*[%]%)%}]*$", "^[%[%(]-estribillo[%s%d]*[%]%)%}]*$",
    "^[%[%(]-verso[%s%d]*[%]%)%}]*$", "^[%[%(]-estrofa[%s%d]*[%]%)%}]*$",
    "^[%[%(]-puente[%s%d]*[%]%)%}]*$",
    "^[%[%(]-pre[%s%-]*coro[%s%d]*[%]%)%}]*$", "^[%[%(]-post[%s%-]*coro[%s%d]*[%]%)%}]*$",
    "^[%[%(]-pre[%s%-]*estribillo[%s%d]*[%]%)%}]*$",
    "^[%[%(]-post[%s%-]*estribillo[%s%d]*[%]%)%}]*$",
}

local function is_section_header(line)
    for _, pattern in ipairs(SECTION_PATTERNS) do
        if line:lower():match(pattern) then
            return true
        end
    end
    return false
end

local function parse_lines(text)
    local result = {}
    local skipped = 0
    for line in text:gmatch("[^\r\n]+") do
        local trimmed = line:match("^%s*(.-)%s*$")
        if trimmed and trimmed ~= "" then
            if not is_section_header(trimmed) then
                result[#result + 1] = trimmed
            else
                skipped = skipped + 1
            end
        end
    end
    return result, skipped
end

-- ═══════════════════════════════════════════════════════════════════════════
-- FLOW  (N = #lines):
--   ARM      → armed, nothing created. "Tap to start first verse..."
--   TAP 1    → creates item #1 at current pos (placeholder). "✓ 1/N"
--   TAP 2    → closes item #1 + creates item #2. "✓ 2/N"
--   ...
--   TAP N    → closes item #(N-1) + creates item #N (the last one). "N/N — tap
--              once more to close it and finish."
--   TAP N+1  → closes item #N and finishes the take right there — same effect
--              as pressing Stop, just one tap instead of reaching for a button.
--   STOP     → always available: closes whatever's currently open (with a more
--              generous minimum length, since it's an unplanned/manual finish)
--              and ends the take early, from any point in the sequence.
--
-- Every tap except the very first closes the item that's currently open; the
-- FIRST tap is the cue "vocals start HERE," nothing to close yet. So each tap
-- from #2 onward is a close, and taps #2..N ALSO open the next item — except
-- the final, (N+1)th tap, which only closes: there's nothing left to open.

local function create_item_at(track, pos, text)
    local item = reaper.AddMediaItemToTrack(track)
    reaper.SetMediaItemInfo_Value(item, "D_POSITION", pos)
    reaper.SetMediaItemInfo_Value(item, "D_LENGTH", 0.1)
    reaper.GetSetMediaItemInfo_String(item, "P_NOTES", text, true)
    return item
end

-- Forward-declared: do_tap()'s final closing tap calls do_stop() to finish
-- the take. Both are top-level locals, so this is safe as long as neither is
-- CALLED before the whole file finishes loading — true here, since both only
-- ever run later, from a button click or the Space shortcut.
local do_stop

local function do_tap()
    local track = ensure_target_track()
    if not track then return end

    local now_pos = get_current_pos()

    -- Close the item currently open, if any. The very first tap has none —
    -- it's the cue "vocals start HERE," nothing to close yet.
    if last_item and reaper.ValidatePtr(last_item, 'MediaItem*') then
        local item_start = reaper.GetMediaItemInfo_Value(last_item, "D_POSITION")
        local duration = now_pos - item_start
        if duration < 0.05 then duration = 0.05 end
        reaper.SetMediaItemInfo_Value(last_item, "D_LENGTH", duration)
        tap_count = tap_count + 1
        last_item = nil
    end

    if current_idx >= #lines then
        -- Every line was already placed, and the tap above just closed the
        -- last one at the exact moment the performer marked its end. Nothing
        -- left to open, so finish right here — do_stop() sees last_item==nil
        -- and skips its own closing step, just doing the undo/finish bookkeeping.
        do_stop()
        return
    end

    -- Create next item at current position
    current_idx = current_idx + 1
    last_item = create_item_at(track, now_pos, lines[current_idx])

    local remaining = #lines - current_idx
    if remaining > 0 then
        ui_msg = string.format("✓ %d/%d  |  Next: \"%s\"",
            current_idx, #lines, lines[current_idx] or "")
    else
        ui_msg = string.format("✓ %d/%d — last line placed. Tap once more (or Space) to close it and finish.",
            current_idx, #lines)
    end

    reaper.UpdateArrange()
end

local function do_arm()
    if #lines == 0 then
        ui_msg = "Paste some text first!"
        return
    end
    if not ensure_target_track() then
        ui_msg = "ERROR: could not find or create target track"
        return
    end

    arm_pos = get_current_pos()
    current_idx = 0
    tap_count = 0
    last_item = nil
    state = "tapping"

    reaper.Undo_BeginBlock()
    local canonical = TRACK_TYPES[track_type_idx]
    ui_msg = string.format("✓ ARMED at %.2fs → %s track. Tap to place: \"%s\"",
        arm_pos, canonical, lines[1] or "")
end

-- No `local` here on purpose — do_stop was already forward-declared above
-- (`local do_stop`) so do_tap()'s closure could call it. Writing
-- `local function do_stop()` here would silently create a SECOND, unrelated
-- local that shadows the forward-declared one, leaving do_tap() forever
-- calling nil. This assigns into the existing upvalue instead.
function do_stop()
    if last_item and reaper.ValidatePtr(last_item, 'MediaItem*') then
        local item_start = reaper.GetMediaItemInfo_Value(last_item, "D_POSITION")
        local now_pos = get_current_pos()
        local duration = now_pos - item_start
        if duration < 0.5 then duration = 2.0 end
        reaper.SetMediaItemInfo_Value(last_item, "D_LENGTH", duration)
        tap_count = tap_count + 1
        last_item = nil
    end

    local canonical = TRACK_TYPES[track_type_idx]
    reaper.Undo_EndBlock(
        "Lyrics Tapper: placed " .. tap_count .. " items on " .. canonical, -1)
    reaper.UpdateArrange()

    state = "idle"
    ui_msg = string.format("✓ Stopped. %d items placed on '%s' track.",
        current_idx, canonical)
end

local function do_reset()
    if state == "tapping" then
        reaper.Undo_EndBlock2(0, "", -1)
        reaper.UpdateArrange()
    end
    state = "idle"
    lines = {}
    current_idx = 0
    tap_count = 0
    last_item = nil
    target_track = nil
    full_text = ""
    ui_msg = "Paste your text and press ARM to start."
end

-- ═══════════════════════════════════════════════════════════════════════════
-- MAIN LOOP (ReaImGui)
-- ═══════════════════════════════════════════════════════════════════════════

local ctx         = reaper.ImGui_CreateContext('Lyrics Tapper')
local first_frame = true

-- ── Fonts ────────────────────────────────────────────────────────────────
-- Two extra sizes on top of the default UI font: a big bold one for the
-- current teleprompter line (the whole point of the redesign — the line
-- being tapped in right now must be unmistakable at a glance), and the same
-- weight for the big ARM/TAP button label. 'sans-serif' is ReaImGui's
-- cross-platform alias for the system default font; ReaImGui reads style
-- hints appended directly to the family string ('b' = bold, 'i' = italic —
-- e.g. 'sans-serifb'), NOT a separate flags argument: reaper.ImGui_CreateFont
-- takes exactly 2 arguments (family, size) on this install.
--
-- This ReaImGui build also requires the render size to be passed again on
-- EVERY PushFont call (reaper.ImGui_PushFont(ctx, font, size) — 3 args
-- minimum, the "scalable fonts" API), rather than only at creation time. So
-- each FONT.x entry carries its own {font, size} pair, and push_font()
-- destructures it instead of taking a bare font handle.
--
-- Creation is wrapped in pcall regardless: if it fails for any reason,
-- FONT.x stays nil and every push site below just skips it (see
-- push_font/pop_font), falling back to the default font instead of erroring
-- the whole script out.
local FONT = {}
local function safe_create_font(size, bold)
    local ok, font = pcall(function()
        local family = bold and 'sans-serifb' or 'sans-serif'
        local f = reaper.ImGui_CreateFont(family, size)
        reaper.ImGui_Attach(ctx, f)
        return f
    end)
    if ok then return { font = font, size = size } end
    return nil
end
FONT.current = safe_create_font(28, true)
FONT.tap     = safe_create_font(19, true)

local function push_font(f) if f then reaper.ImGui_PushFont(ctx, f.font, f.size) end end
local function pop_font(f)  if f then reaper.ImGui_PopFont(ctx)                  end end

local function main_loop()
    -- Global keyboard shortcut: Space to tap
    if state == "tapping" and reaper.ImGui_IsKeyPressed(ctx, ImGui.Key_Space) then
        do_tap()
    end

    -- Set initial window size on first frame only (roomier than before — the
    -- teleprompter view wants vertical room).
    if first_frame then
        ImGui.SetNextWindowSize(ctx, 820, 620, ImGui.Cond_FirstUseEver)
        first_frame = false
    end

    local visible, open = ImGui.Begin(ctx, 'Lyrics Tapper###LyricsTapper', true,
        ImGui.WindowFlags_NoDocking)

    if visible then
        -- ── Theme: pushed once for the whole window, popped once at the end.
        -- Counters (not hardcoded numbers) drive the final Pop calls, so the
        -- push/pop pair stays balanced automatically no matter how many
        -- entries are added above — the classic ImGui foot-gun is a literal
        -- pop count drifting out of sync with the push list.
        local var_n, col_n = 0, 0
        local function pvar(id, a, b)
            if b then ImGui.PushStyleVar(ctx, id, a, b) else ImGui.PushStyleVar(ctx, id, a) end
            var_n = var_n + 1
        end
        local function pcol(id, v) ImGui.PushStyleColor(ctx, id, v); col_n = col_n + 1 end

        pvar(ImGui.StyleVar_WindowPadding,     16, 14)
        pvar(ImGui.StyleVar_FramePadding,      10, 8)
        pvar(ImGui.StyleVar_ItemSpacing,       10, 10)
        pvar(ImGui.StyleVar_FrameRounding,     6)
        pvar(ImGui.StyleVar_GrabRounding,      6)
        pvar(ImGui.StyleVar_ChildRounding,     8)
        pvar(ImGui.StyleVar_ScrollbarRounding, 8)

        pcol(ImGui.Col_WindowBg,             THEME.bg)
        pcol(ImGui.Col_ChildBg,              THEME.bg_panel)
        pcol(ImGui.Col_PopupBg,              THEME.bg_panel)
        pcol(ImGui.Col_Border,               THEME.border)
        pcol(ImGui.Col_Separator,            THEME.border)
        pcol(ImGui.Col_FrameBg,              THEME.bg_input)
        pcol(ImGui.Col_FrameBgHovered,       THEME.bg_input_hov)
        pcol(ImGui.Col_FrameBgActive,        THEME.bg_input_hov)
        pcol(ImGui.Col_Text,                 THEME.text)
        pcol(ImGui.Col_Button,               THEME.ghost)
        pcol(ImGui.Col_ButtonHovered,        THEME.ghost_hover)
        pcol(ImGui.Col_ButtonActive,         THEME.ghost_active)
        pcol(ImGui.Col_Header,               THEME.ghost_hover)
        pcol(ImGui.Col_HeaderHovered,        THEME.ghost_active)
        pcol(ImGui.Col_HeaderActive,         THEME.accent)
        pcol(ImGui.Col_ScrollbarBg,          THEME.bg)
        pcol(ImGui.Col_ScrollbarGrab,        THEME.border)
        pcol(ImGui.Col_ScrollbarGrabHovered, THEME.text_faint)
        pcol(ImGui.Col_ScrollbarGrabActive,  THEME.text_dim)
        pcol(ImGui.Col_PlotHistogram,        THEME.accent)

        -- ── Top bar: track selector + found/created status ─────────────────
        ImGui.AlignTextToFramePadding(ctx)
        ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.text_dim)
        ImGui.Text(ctx, "TRACK")
        ImGui.PopStyleColor(ctx, 1)
        ImGui.SameLine(ctx)
        ImGui.SetNextItemWidth(ctx, 130)
        local changed_type
        changed_type, track_type_idx = ImGui.Combo(ctx, "##track_type",
            track_type_idx, "Lyrics\0Chords\0Notes\0")
        if changed_type then
            target_track = nil  -- invalidate cache so we re-search
            ui_msg = string.format("Target: %s. Paste your text and press ARM.",
                TRACK_TYPES[track_type_idx])
        end

        local canonical = TRACK_TYPES[track_type_idx]
        local matches = find_matching_track(canonical)
        ImGui.SameLine(ctx)
        if #matches > 0 then
            local _, name = reaper.GetTrackName(matches[1])
            ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.ok)
            ImGui.Text(ctx, string.format("%s  found", name))
            ImGui.PopStyleColor(ctx, 1)
        else
            ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.warn)
            ImGui.Text(ctx, string.format("%s  will be created", canonical))
            ImGui.PopStyleColor(ctx, 1)
        end

        -- ── Status line ──────────────────────────────────────────────────
        ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.text_dim)
        ImGui.TextWrapped(ctx, ui_msg)
        ImGui.PopStyleColor(ctx, 1)

        ImGui.Spacing(ctx)
        ImGui.Separator(ctx)
        ImGui.Spacing(ctx)

        -- ── Main content: paste box (idle) or teleprompter (tapping/done) ──
        if state == "idle" then
            ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.text_dim)
            ImGui.Text(ctx, "PASTE LYRICS  (one line = one item)")
            ImGui.PopStyleColor(ctx, 1)

            local _, avail_h = ImGui.GetContentRegionAvail(ctx)
            local reserved = 92   -- line-count label + spacing + ARM button
            local box_h = math.max(120, avail_h - reserved)

            local changed
            changed, full_text = ImGui.InputTextMultiline(ctx, "##taper_text", full_text,
                -1, box_h, ImGui.InputTextFlags_AllowTabInput)
            if changed then
                local skipped
                lines, skipped = parse_lines(full_text)
                if #lines > 0 then
                    if skipped > 0 then
                        ui_msg = string.format("%d lines (%d section headers skipped). Press ARM.", #lines, skipped)
                    else
                        ui_msg = string.format("%d lines detected. Press ARM.", #lines)
                    end
                end
            end

            ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.text_faint)
            if #lines > 0 then
                ImGui.Text(ctx, string.format("%d lines ready", #lines))
            else
                ImGui.Text(ctx, " ")
            end
            ImGui.PopStyleColor(ctx, 1)

            -- ── ARM: the big primary call-to-action ──────────────────────
            local no_lines = (#lines == 0)
            local disabled_open = false
            if no_lines and ImGui.BeginDisabled then
                ImGui.BeginDisabled(ctx, true)
                disabled_open = true
            end
            ImGui.PushStyleColor(ctx, ImGui.Col_Button,        THEME.accent)
            ImGui.PushStyleColor(ctx, ImGui.Col_ButtonHovered, THEME.accent_hover)
            ImGui.PushStyleColor(ctx, ImGui.Col_ButtonActive,  THEME.accent_active)
            ImGui.PushStyleColor(ctx, ImGui.Col_Text,          THEME.accent_text)
            push_font(FONT.tap)
            if ImGui.Button(ctx, "ARM", -1, 54) then
                do_arm()
            end
            pop_font(FONT.tap)
            ImGui.PopStyleColor(ctx, 4)
            if disabled_open then ImGui.EndDisabled(ctx) end

        else
            -- ── Teleprompter (tapping / done) ────────────────────────────
            ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.text_dim)
            ImGui.Text(ctx, string.format("%d / %d placed", current_idx, #lines))
            ImGui.PopStyleColor(ctx, 1)

            local _, avail_h = ImGui.GetContentRegionAvail(ctx)
            local view_h = math.max(140, avail_h - 128)  -- reserve room for the TAP button + progress bar

            if ImGui.BeginChild(ctx, "##lyrics_view", -1, view_h, ImGui.ChildFlags_Borders) then
                -- Role per line: "past" (already placed), "current" (the one
                -- being tapped in — including after the LAST line, where it
                -- stays "current" rather than going dim, until the closing
                -- tap finishes the take), "next" (about to be tapped — shown
                -- a touch brighter, like Ableset's upcoming-line cue), or
                -- plain "future". Before the first tap (current_idx == 0),
                -- line 1 is naturally "next" and nothing is "current" yet.
                for i = 1, #lines do
                    local role = "future"
                    if i < current_idx then role = "past"
                    elseif i == current_idx then role = "current"
                    elseif i == current_idx + 1 then role = "next"
                    end

                    if role == "current" then
                        ImGui.Spacing(ctx)
                        push_font(FONT.current)
                        ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.accent)
                        ImGui.TextWrapped(ctx, lines[i])
                        ImGui.PopStyleColor(ctx, 1)
                        pop_font(FONT.current)
                        ImGui.SetScrollHereY(ctx, 0.35)
                        ImGui.Spacing(ctx)
                    elseif role == "past" then
                        ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.text_faint)
                        ImGui.TextWrapped(ctx, "✓ " .. lines[i])
                        ImGui.PopStyleColor(ctx, 1)
                    elseif role == "next" then
                        ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.text)
                        ImGui.TextWrapped(ctx, lines[i])
                        ImGui.PopStyleColor(ctx, 1)
                    else -- future
                        ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.text_faint)
                        ImGui.TextWrapped(ctx, lines[i])
                        ImGui.PopStyleColor(ctx, 1)
                    end
                end
            end
            -- EndChild SIEMPRE necesario, incluso si BeginChild devolvió false
            ImGui.EndChild(ctx)

            ImGui.Spacing(ctx)
            ImGui.PushStyleColor(ctx, ImGui.Col_Button,        THEME.accent)
            ImGui.PushStyleColor(ctx, ImGui.Col_ButtonHovered, THEME.accent_hover)
            ImGui.PushStyleColor(ctx, ImGui.Col_ButtonActive,  THEME.accent_active)
            ImGui.PushStyleColor(ctx, ImGui.Col_Text,          THEME.accent_text)
            push_font(FONT.tap)
            -- The very last tap only CLOSES (there's nothing left to open and
            -- finish the take), so the label says so instead of implying
            -- another line is about to start.
            local tap_label = (current_idx >= #lines) and "TAP TO FINISH · SPACE" or "TAP · SPACE"
            if ImGui.Button(ctx, tap_label, -1, 58) then
                do_tap()
            end
            pop_font(FONT.tap)
            ImGui.PopStyleColor(ctx, 4)

            if #lines > 0 then
                local frac = current_idx / #lines
                ImGui.ProgressBar(ctx, frac, -1, 10,
                    string.format("%d / %d", current_idx, #lines))
            end
        end

        -- ── Position readout ─────────────────────────────────────────────
        ImGui.Spacing(ctx)
        local now_str = string.format("%.2f", get_current_pos())
        ImGui.PushStyleColor(ctx, ImGui.Col_Text, THEME.text_faint)
        if state == "tapping" then
            ImGui.Text(ctx, string.format("Armed at %.2fs  ·  now %ss", arm_pos, now_str))
        else
            ImGui.Text(ctx, string.format("Cursor: %ss", now_str))
        end
        ImGui.PopStyleColor(ctx, 1)

        ImGui.Spacing(ctx)
        ImGui.Separator(ctx)
        ImGui.Spacing(ctx)

        -- ── Secondary controls ───────────────────────────────────────────
        if state == "idle" then
            if ImGui.Button(ctx, "Reset", 110, 32) then
                do_reset()
            end
        elseif state == "tapping" then
            ImGui.PushStyleColor(ctx, ImGui.Col_Button,        THEME.danger)
            ImGui.PushStyleColor(ctx, ImGui.Col_ButtonHovered, THEME.danger_hover)
            ImGui.PushStyleColor(ctx, ImGui.Col_ButtonActive,  THEME.danger_active)
            if ImGui.Button(ctx, "Stop", 110, 32) then
                do_stop()
            end
            ImGui.PopStyleColor(ctx, 3)
            ImGui.SameLine(ctx)
            if ImGui.Button(ctx, "Reset", 110, 32) then
                do_reset()
            end
        end

        ImGui.PopStyleColor(ctx, col_n)
        ImGui.PopStyleVar(ctx, var_n)

        ImGui.End(ctx)
    end

    if not open then
        if state == "tapping" then do_stop() end
        return
    end

    reaper.defer(main_loop)
end

-- ═══════════════════════════════════════════════════════════════════════════
-- BOOT
-- ═══════════════════════════════════════════════════════════════════════════

reaper.defer(main_loop)
