-- Text to MIDI Bitmap.lua
-- Renderizador de fuente bitmap → notas MIDI (estilo display LED).
-- Convierte texto normal en un bitmap de notas MIDI dentro de la time selection.
--
-- USO:
--   1. Selecciona un track
--   2. Crea una time selection (arrastra en el timeline)
--   3. Ejecuta el script
--   4. Escribe/pega el texto en el diálogo
--   5. Ajusta altura y espaciado si quieres
--
-- Cada "pixel" de la letra = una nota MIDI corta.
-- El texto se escala automáticamente para llenar la time selection.
-- Míralo con zoom en el MIDI Editor (piano roll).
-- ─────────────────────────────────────────────────────────────────────────────

-- ═══════════════════════════════════════════════════════════════════
-- FUENTE BITMAP 5×7
-- Cada carácter: 7 filas de 5 columnas.
-- '#' = pixel encendido (nota MIDI), ' ' = pixel apagado.
-- ═══════════════════════════════════════════════════════════════════

local FONT = {}

-- Mayúsculas
FONT['A'] = {' ### ', '#   #', '#   #', '#####', '#   #', '#   #', '#   #'}
FONT['B'] = {'#### ', '#   #', '#### ', '#   #', '#   #', '#   #', '#### '}
FONT['C'] = {' ### ', '#   #', '#    ', '#    ', '#    ', '#   #', ' ### '}
FONT['D'] = {'#### ', '#   #', '#   #', '#   #', '#   #', '#   #', '#### '}
FONT['E'] = {'#####', '#    ', '#### ', '#    ', '#    ', '#    ', '#####'}
FONT['F'] = {'#####', '#    ', '#### ', '#    ', '#    ', '#    ', '#    '}
FONT['G'] = {' ### ', '#   #', '#    ', '#  ##', '#   #', '#   #', ' ### '}
FONT['H'] = {'#   #', '#   #', '#####', '#   #', '#   #', '#   #', '#   #'}
FONT['I'] = {'#####', '  #  ', '  #  ', '  #  ', '  #  ', '  #  ', '#####'}
FONT['J'] = {'  ###', '   # ', '   # ', '   # ', '#  # ', '#  # ', ' ##  '}
FONT['K'] = {'#   #', '#  # ', '###  ', '# #  ', '#  # ', '#   #', '#   #'}
FONT['L'] = {'#    ', '#    ', '#    ', '#    ', '#    ', '#    ', '#####'}
FONT['M'] = {'#   #', '## ##', '# # #', '# # #', '#   #', '#   #', '#   #'}
FONT['N'] = {'#   #', '##  #', '# # #', '#  ##', '#   #', '#   #', '#   #'}
FONT['O'] = {' ### ', '#   #', '#   #', '#   #', '#   #', '#   #', ' ### '}
FONT['P'] = {'#### ', '#   #', '#   #', '#### ', '#    ', '#    ', '#    '}
FONT['Q'] = {' ### ', '#   #', '#   #', '#   #', '# # #', '#  # ', ' ## #'}
FONT['R'] = {'#### ', '#   #', '#   #', '#### ', '# #  ', '#  # ', '#   #'}
FONT['S'] = {' ### ', '#    ', '#    ', ' ### ', '    #', '    #', ' ### '}
FONT['T'] = {'#####', '  #  ', '  #  ', '  #  ', '  #  ', '  #  ', '  #  '}
FONT['U'] = {'#   #', '#   #', '#   #', '#   #', '#   #', '#   #', ' ### '}
FONT['V'] = {'#   #', '#   #', '#   #', '#   #', ' # # ', ' # # ', '  #  '}
FONT['W'] = {'#   #', '#   #', '#   #', '# # #', '# # #', '## ##', '#   #'}
FONT['X'] = {'#   #', '#   #', ' # # ', '  #  ', ' # # ', '#   #', '#   #'}
FONT['Y'] = {'#   #', '#   #', ' # # ', '  #  ', '  #  ', '  #  ', '  #  '}
FONT['Z'] = {'#####', '    #', '   # ', '  #  ', ' #   ', '#    ', '#####'}

-- Números
FONT['0'] = {' ### ', '#   #', '#  ##', '# # #', '##  #', '#   #', ' ### '}
FONT['1'] = {'  #  ', ' ##  ', '# #  ', '  #  ', '  #  ', '  #  ', '#####'}
FONT['2'] = {' ### ', '#   #', '    #', '   # ', '  #  ', ' #   ', '#####'}
FONT['3'] = {' ### ', '#   #', '    #', '  ## ', '    #', '#   #', ' ### '}
FONT['4'] = {'   # ', '  ## ', ' # # ', '#  # ', '#####', '   # ', '   # '}
FONT['5'] = {'#####', '#    ', '#### ', '    #', '    #', '#   #', ' ### '}
FONT['6'] = {' ### ', '#    ', '#    ', '#### ', '#   #', '#   #', ' ### '}
FONT['7'] = {'#####', '    #', '   # ', '  #  ', ' #   ', ' #   ', ' #   '}
FONT['8'] = {' ### ', '#   #', '#   #', ' ### ', '#   #', '#   #', ' ### '}
FONT['9'] = {' ### ', '#   #', '#   #', ' ####', '    #', '    #', ' ### '}

-- Espacio y símbolos
FONT[' '] = {'     ', '     ', '     ', '     ', '     ', '     ', '     '}
FONT['!'] = {'  #  ', '  #  ', '  #  ', '  #  ', '  #  ', '     ', '  #  '}
FONT['?'] = {' ### ', '#   #', '    #', '   # ', '  #  ', '     ', '  #  '}
FONT['-'] = {'     ', '     ', '     ', '#####', '     ', '     ', '     '}
FONT['.'] = {'     ', '     ', '     ', '     ', '     ', '     ', '  #  '}
FONT[','] = {'     ', '     ', '     ', '     ', '     ', '  #  ', ' #   '}
FONT["'"] = {'  #  ', '  #  ', '     ', '     ', '     ', '     ', '     '}
FONT['"'] = {' # # ', ' # # ', '     ', '     ', '     ', '     ', '     '}
FONT['('] = {'   # ', '  #  ', ' #   ', ' #   ', ' #   ', '  #  ', '   # '}
FONT[')'] = {' #   ', '  #  ', '   # ', '   # ', '   # ', '  #  ', ' #   '}
FONT['/'] = {'    #', '   # ', '  #  ', ' #   ', '#    ', '     ', '     '}
FONT[':'] = {'     ', '  #  ', '     ', '     ', '     ', '  #  ', '     '}
FONT[';'] = {'     ', '  #  ', '     ', '     ', '     ', '  #  ', ' #   '}
FONT['#'] = {' # # ', ' # # ', '#####', ' # # ', '#####', ' # # ', ' # # '}
FONT['&'] = {' ##  ', '#  # ', '#  # ', ' ##  ', '# # #', '#  # ', ' ## #'}
FONT['*'] = {'     ', ' # # ', '  #  ', '#####', '  #  ', ' # # ', '     '}
FONT['+'] = {'     ', '  #  ', '  #  ', '#####', '  #  ', '  #  ', '     '}
FONT['='] = {'     ', '     ', '#####', '     ', '#####', '     ', '     '}
FONT['<'] = {'   # ', '  #  ', ' #   ', '#    ', ' #   ', '  #  ', '   # '}
FONT['>'] = {' #   ', '  #  ', '   # ', '    #', '   # ', '  #  ', ' #   '}
FONT['@'] = {' ### ', '#   #', '#  ##', '# # #', '# ## ', '#    ', ' ### '}
FONT['^'] = {'  #  ', ' # # ', '#   #', '     ', '     ', '     ', '     '}
FONT['_'] = {'     ', '     ', '     ', '     ', '     ', '     ', '#####'}
FONT['|'] = {'  #  ', '  #  ', '  #  ', '  #  ', '  #  ', '  #  ', '  #  '}
FONT['~'] = {'     ', ' #   ', '# # #', '   # ', '     ', '     ', '     '}
FONT['\\'] = {'#    ', ' #   ', '  #  ', '   # ', '    #', '     ', '     '}
FONT['['] = {' ### ', ' #   ', ' #   ', ' #   ', ' #   ', ' #   ', ' ### '}
FONT[']'] = {' ### ', '   # ', '   # ', '   # ', '   # ', '   # ', ' ### '}

-- Minúsculas
FONT['a'] = FONT['A']
FONT['b'] = FONT['B']
FONT['c'] = FONT['C']
FONT['d'] = FONT['D']
FONT['e'] = FONT['E']
FONT['f'] = FONT['F']
FONT['g'] = FONT['G']
FONT['h'] = FONT['H']
FONT['i'] = FONT['I']
FONT['j'] = FONT['J']
FONT['k'] = FONT['K']
FONT['l'] = FONT['L']
FONT['m'] = FONT['M']
FONT['n'] = FONT['N']
FONT['o'] = FONT['O']
FONT['p'] = FONT['P']
FONT['q'] = FONT['Q']
FONT['r'] = FONT['R']
FONT['s'] = FONT['S']
FONT['t'] = FONT['T']
FONT['u'] = FONT['U']
FONT['v'] = FONT['V']
FONT['w'] = FONT['W']
FONT['x'] = FONT['X']
FONT['y'] = FONT['Y']
FONT['z'] = FONT['Z']

-- Caracteres con acentos (mapean a su versión sin acento)
FONT['Á'] = FONT['A']; FONT['Ä'] = FONT['A']; FONT['À'] = FONT['A']; FONT['Â'] = FONT['A']
FONT['É'] = FONT['E']; FONT['Ë'] = FONT['E']; FONT['È'] = FONT['E']; FONT['Ê'] = FONT['E']
FONT['Í'] = FONT['I']; FONT['Ï'] = FONT['I']; FONT['Ì'] = FONT['I']; FONT['Î'] = FONT['I']
FONT['Ó'] = FONT['O']; FONT['Ö'] = FONT['O']; FONT['Ò'] = FONT['O']; FONT['Ô'] = FONT['O']
FONT['Ú'] = FONT['U']; FONT['Ü'] = FONT['U']; FONT['Ù'] = FONT['U']; FONT['Û'] = FONT['U']

-- Ñ/ñ con virgulilla propia (tilde arriba, N abajo)
local N_WITH_TILDE = {' # # ', '#   #', '##  #', '# # #', '#  ##', '#   #', '#   #'}
FONT['Ñ'] = N_WITH_TILDE
FONT['ñ'] = N_WITH_TILDE
FONT['á'] = FONT['A']; FONT['ä'] = FONT['A']; FONT['à'] = FONT['A']; FONT['â'] = FONT['A']
FONT['é'] = FONT['E']; FONT['ë'] = FONT['E']; FONT['è'] = FONT['E']; FONT['ê'] = FONT['E']
FONT['í'] = FONT['I']; FONT['ï'] = FONT['I']; FONT['ì'] = FONT['I']; FONT['î'] = FONT['I']
FONT['ó'] = FONT['O']; FONT['ö'] = FONT['O']; FONT['ò'] = FONT['O']; FONT['ô'] = FONT['O']
FONT['ú'] = FONT['U']; FONT['ü'] = FONT['U']; FONT['ù'] = FONT['U']; FONT['û'] = FONT['U']

-- ═══════════════════════════════════════════════════════════════════
-- CONSTANTES DE LA FUENTE
-- ═══════════════════════════════════════════════════════════════════

local FONT_WIDTH  = 5    -- columnas por carácter
local FONT_HEIGHT = 7    -- filas por carácter

-- ═══════════════════════════════════════════════════════════════════
-- FUNCIONES AUXILIARES
-- ═══════════════════════════════════════════════════════════════════

--- Intenta obtener el glifo para un carácter.
--- Si no existe, retorna nil.
local function get_glyph(char)
  return FONT[char]
end

--- Cuenta el total de columnas que ocupará el texto renderizado.
--- Incluye columnas de espaciado entre caracteres.
local function calc_total_columns(text, spacing)
  local total = 0
  local char_count = 0
  for i = 1, #text do
    local c = text:sub(i, i)
    local glyph = get_glyph(c)
    if glyph then
      total = total + FONT_WIDTH
      char_count = char_count + 1
    end
  end
  -- Agregar espaciado entre caracteres (no al final)
  if char_count > 1 then
    total = total + spacing * (char_count - 1)
  end
  return total, char_count
end

-- ═══════════════════════════════════════════════════════════════════
-- 1. DIÁLOGO DE ENTRADA
-- ═══════════════════════════════════════════════════════════════════

local ok, inputs = reaper.GetUserInputs(
  "Text to MIDI Bitmap",
  9,
  "Texto:,Paso vertical (1-3):,Espaciado (0-3 col):,Pitch base (0-127):,Velocity (1-127):,Canal MIDI (1-16):,Octavas (1-4):,Margen lateral % (0-20):,Tamaño fijo ms/col (0=auto):",
  "HELLO WORLD,1,1,48,100,1,1,5,0"
)

if not ok then return end  -- usuario canceló

-- Parse robusto: el texto puede contener comas (ej: "INTRO, VERSE")
-- ^(.*) es greedy → captura todo hasta los últimos 8 campos numéricos
local text, step_str, spacing_str, pitch_str, velocity_str, chan_str, octaves_str, margin_str, fixed_ms_str =
  inputs:match("^(.*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*)$")

-- Validar y sanitizar inputs
local vertical_step  = math.max(1, math.min(3, tonumber(step_str) or 1))
local spacing         = math.max(0, math.min(3, tonumber(spacing_str) or 1))
local base_pitch      = math.max(0, math.min(127, tonumber(pitch_str) or 48))
local note_velocity   = math.max(1, math.min(127, tonumber(velocity_str) or 100))
local midi_chan       = math.max(1, math.min(16, tonumber(chan_str) or 1)) - 1  -- 0-based
local octaves         = math.max(1, math.min(4, tonumber(octaves_str) or 1))
local margin_pct      = math.max(0, math.min(20, tonumber(margin_str) or 5))
local fixed_ms        = math.max(0, math.min(2000, tonumber(fixed_ms_str) or 0))

-- Limpiar texto: quitar saltos de línea, espacios extremos
text = text:gsub("[\r\n]", " "):gsub("%s+", " "):gsub("^%s+", ""):gsub("%s+$", "")

if text == "" then
  reaper.MB("❌ El texto está vacío.", "Text to MIDI Bitmap", 0)
  return
end

-- Contar caracteres renderizables
local total_columns, char_count = calc_total_columns(text, spacing)
if total_columns == 0 then
  reaper.MB("❌ El texto no contiene caracteres soportados.", "Text to MIDI Bitmap", 0)
  return
end

-- ═══════════════════════════════════════════════════════════════════
-- 2. TIME SELECTION
-- ═══════════════════════════════════════════════════════════════════

local start_time, end_time = reaper.GetSet_LoopTimeRange(false, false, 0, 0, false)

-- Fallback: loop selection si no hay time selection
if not start_time or not end_time or end_time <= start_time then
  start_time, end_time = reaper.GetSet_LoopTimeRange(false, true, 0, 0, false)
end

if not start_time or not end_time or end_time <= start_time then
  reaper.MB(
    "❌ Debes crear una time selection primero.\n\n" ..
    "Arrastra en el timeline para definir el área donde\n" ..
    "aparecerá el texto renderizado.",
    "Text to MIDI Bitmap", 0
  )
  return
end

local item_length = end_time - start_time

-- ═══════════════════════════════════════════════════════════════════
-- 3. OBTENER O CREAR TRACK
-- ═══════════════════════════════════════════════════════════════════

local track = reaper.GetSelectedTrack(0, 0)
if not track then
  reaper.InsertTrackAtIndex(0, true)
  track = reaper.GetTrack(0, 0)
end

-- ═══════════════════════════════════════════════════════════════════
-- 4. CREAR ITEM MIDI
-- ═══════════════════════════════════════════════════════════════════

reaper.PreventUIRefresh(1)
reaper.Undo_BeginBlock()

-- Crear item vacío en el track
local item = reaper.AddMediaItemToTrack(track)
reaper.SetMediaItemInfo_Value(item, "D_POSITION", start_time)
reaper.SetMediaItemInfo_Value(item, "D_LENGTH", item_length)

-- Seleccionarlo y ejecutar "Insert empty MIDI item" (command 40214)
reaper.SetMediaItemSelected(item, true)
reaper.Main_OnCommand(40214, 0)

-- Reobtener item y take (la referencia se invalida)
item = reaper.GetSelectedMediaItem(0, 0)
if not item then
  reaper.PreventUIRefresh(-1)
  reaper.Undo_EndBlock2(0, "", -1)
  reaper.MB("❌ No se pudo crear el item MIDI.", "Text to MIDI Bitmap", 0)
  return
end

-- Ajustar posición y largo
reaper.SetMediaItemInfo_Value(item, "D_POSITION", start_time)
reaper.SetMediaItemInfo_Value(item, "D_LENGTH", item_length)

-- Nombrar el item para identificarlo fácil
reaper.GetSetMediaItemInfo_String(item, "P_NOTES", text, true)

local take = reaper.GetActiveTake(item)
if not take then
  reaper.PreventUIRefresh(-1)
  reaper.Undo_EndBlock2(0, "", -1)
  reaper.MB("❌ No se pudo acceder al take MIDI.", "Text to MIDI Bitmap", 0)
  return
end

-- ═══════════════════════════════════════════════════════════════════
-- 5. RENDERIZAR BITMAP → NOTAS MIDI
-- ═══════════════════════════════════════════════════════════════════

-- Calcular tiempo por columna: auto-escala o tamaño fijo
local column_time
local effective_start
local is_fixed = fixed_ms > 0

if is_fixed then
  -- Modo tamaño fijo: texto a tamaño constante, centrado en el item
  column_time = fixed_ms / 1000
  local text_width = total_columns * column_time
  local margin_time = item_length * margin_pct / 100
  local available_width = item_length - 2 * margin_time
  if available_width <= 0 then available_width = item_length * 0.01 end
  -- Centrar texto en el área con márgenes
  if text_width < available_width then
    effective_start = start_time + margin_time + (available_width - text_width) / 2
  else
    effective_start = start_time + margin_time
  end
else
  -- Modo auto-escala: texto llena el área disponible (comportamiento original)
  local margin_time = item_length * margin_pct / 100
  effective_start = start_time + margin_time
  local effective_length = item_length - 2 * margin_time
  if effective_length <= 0 then effective_length = item_length * 0.01 end
  column_time = effective_length / total_columns
end

local note_duration_ratio = 0.85  -- pequeño gap entre notas

-- Verificar que el pitch máximo no exceda 127
-- El pitch más alto = base + última fila + octava más alta
local max_pitch = base_pitch + vertical_step * (FONT_HEIGHT - 1) + (octaves - 1) * 12
if max_pitch > 127 then
  base_pitch = 127 - vertical_step * (FONT_HEIGHT - 1) - (octaves - 1) * 12
end
if base_pitch < 0 then base_pitch = 0 end

local columns_placed = 0  -- contador de columnas ya dibujadas
local notes_inserted = 0

for i = 1, #text do
  local c = text:sub(i, i)
  local glyph = get_glyph(c)

  if glyph then
    -- Renderizar este glifo
    for row = 1, FONT_HEIGHT do
      local glyph_row = glyph[row]
      for col = 1, FONT_WIDTH do
        local pixel = glyph_row:sub(col, col)
        if pixel == '#' then
          -- Calcular posición en tiempo
          local note_start_t = effective_start + (columns_placed + col - 1) * column_time
          local note_end_t   = note_start_t + column_time * note_duration_ratio

          -- Convertir a PPQ (ticks MIDI)
          local ppq_start = reaper.MIDI_GetPPQPosFromProjTime(take, note_start_t)
          local ppq_end   = reaper.MIDI_GetPPQPosFromProjTime(take, note_end_t)

          -- Pitch base de esta fila
          local base_row_pitch = base_pitch + vertical_step * (FONT_HEIGHT - row)

          -- Duplicar en octavas hacia arriba
          for o = 0, octaves - 1 do
            local pitch = base_row_pitch + o * 12
            if pitch <= 127 then
              reaper.MIDI_InsertNote(
                take,
                false,
                false,
                ppq_start,
                ppq_end,
                midi_chan,
                pitch,
                note_velocity,
                true
              )
              notes_inserted = notes_inserted + 1
            end
          end
        end
      end
    end

    -- Avanzar columnas: ancho del glifo + espaciado
    columns_placed = columns_placed + FONT_WIDTH + spacing
  end
end

-- Ordenar todas las notas
reaper.MIDI_Sort(take)

-- ═══════════════════════════════════════════════════════════════════
-- 6. AJUSTES VISUALES DEL TRACK
-- ═══════════════════════════════════════════════════════════════════

-- Nombrar el track si es nuevo (sin nombre)
local _, track_name = reaper.GetTrackName(track)
if track_name == "" then
  reaper.GetSetMediaTrackInfo_String(track, "P_NAME", "TEXT: " .. text:sub(1, 30), true)
end

-- Expandir altura del track para que se vean las notas
-- I_MEDIATRACKHEIGHT: 0=min, 1=small, 2=medium, 3=large
reaper.SetMediaTrackInfo_Value(track, "I_HEIGHTOVERRIDE", 2)

-- ═══════════════════════════════════════════════════════════════════
-- 7. FINALIZAR
-- ═══════════════════════════════════════════════════════════════════

reaper.PreventUIRefresh(-1)
reaper.UpdateArrange()

reaper.Undo_EndBlock("Text to MIDI Bitmap: " .. char_count .. " chars → " .. notes_inserted .. " notes", -1)

-- Calcular preview del texto
local preview = #text > 40 and (text:sub(1, 40) .. "...") or text

reaper.MB(string.format(
  "✓ Texto renderizado como MIDI bitmap\n\n" ..
  "Texto: \"%s\"\n" ..
  "Modo: %s\n" ..
  "Caracteres: %d\n" ..
  "Notas MIDI: %d\n" ..
  "Columnas: %d\n" ..
  "Tamaño col: %.1f ms\n" ..
  "Duración: %.1fs\n" ..
  "Rango pitch: %d–%d\n\n" ..
  "Tips:\n" ..
  "• Abre el MIDI Editor (doble clic en el item)\n" ..
  "• Haz zoom vertical para ver el texto\n" ..
  "• Para uniformar tamaños: usa Tamaño fijo > 0\n" ..
  "• Ctrl+Z para deshacer y probar otros parámetros",
  preview,
  is_fixed and ("Fijo " .. fixed_ms .. " ms/col") or "Auto-escala",
  char_count, notes_inserted, total_columns,
  column_time * 1000, item_length,
  base_pitch, base_pitch + vertical_step * (FONT_HEIGHT - 1) + (octaves - 1) * 12
), "Text to MIDI Bitmap", 0)
