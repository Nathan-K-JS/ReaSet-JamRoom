# ReaSet Changelog

---

# English

---

## v2.2 — Live Lyrics Carousel, Reaset.lua Unification & Director/Player Mode
*July 28, 2026*

### Installation & reliability
- **`Reaset.lua`: one script instead of three.** Merges the native-loop engine, the lyrics bridge and the chords bridge into a single persistent background script. Lyrics/chords tracks are now optional — no error box if absent — and `ULT_GetMediaItemNote` is called defensively so a missing SWS install no longer breaks transport/loop control. No Action ID setup needed; the web UI auto-detects it. The original three scripts remain under `Requirements/` as a legacy/advanced path.
- **Wi-Fi drop / reconnect phantom-seek fix.** ReaSet issues absolute `SET/POS` commands based on its last polled position. If the poll stream cuts out (a tablet losing Wi-Fi) while REAPER keeps playing, the first fresh reply on reconnect used to trigger a stale loop/boundary decision that seeked REAPER *backward* to the pre-outage position — indistinguishable from a phantom tap. ReaSet now detects the gap (plus browser online/offline events) and suppresses only its own *automatic* transport commands for a short guard window while silently adopting REAPER's real position; explicit user taps are never suppressed.
- **Decorated track names.** Lyrics/chords tracks no longer need to be named exactly `lyrics`/`chords` — prefixes, numbering and symbol decoration are stripped before matching (`*Lyrics`, `01 - Chords`, `[Lyrics]`, etc.), while names with an extra word (`Backing Lyrics`) are deliberately left alone.
- **Real per-bridge status.** Instead of one generic "make sure you have a track named lyrics" hint for four different causes, the empty-state message now reports the actual one: script not running, no track matched, SWS missing, or track found with no item under the cursor.
- **Fixed two real detection bugs.** A divider/folder track above the real one (e.g. `=== LYRICS ===`) could silently shadow it forever; the bridge now prefers a track that actually has items. Renaming a track used to have no effect until REAPER restarted; it now re-scans every ~2s when the latched track stops matching.
- **Dead-bridge detection.** A crashed (not just absent) script used to keep reporting stale, frozen values as if they were live — nothing distinguished a hung script from a working one. A live tick counter plus error capture now catches this and reports it before any stale data is shown.
- **`ReaSet_Diagnose.lua`**, a new read-only diagnostic script: lists every track with its normalised name and item count, which track each bridge would pick, SWS availability, cursor position, a per-item Notes dump, and a self-test that proves the lookup pipeline works independent of where the playhead happens to sit.

### Live Lyrics & Chords — Cover Flow carousel
- **Three-line verse context.** The lyrics panel now shows the previous and next verse above/below the current one, each independently sized via a new gear-icon settings popover (size, weight, colour, context on/off).
- **Chords get the same context**, laid out horizontally either side of the current chord.
- **A proper 3D carousel**, not a flat slide: verses and chords sit on a drum and turn into place — lyrics vertically, chords horizontally — always facing the viewer square-on (no distracting tilt on the context lines). Tuned down from an initial 380ms turn to a snappy 100ms with a hard landing.
- **Independent size controls**: Global, Principal (current line) and Secundario (context lines) can now be adjusted separately instead of one shared scale.
- **Song-boundary clamping.** Previous/next context lines no longer bleed across song boundaries — the "previous" line from the last song vanishes rather than lingering at the next song's start, and "next" at a song's end shows the upcoming song's name instead of the next lyrics item on the timeline, whatever song that happens to belong to.
- **Constant spacing on wrap.** A two-line current verse no longer crowds its neighbours — spacing now accounts for the verse's actual rendered height.
- **Quieter status messaging.** An empty panel (an instrumental passage, a gap between verses) no longer shows a large centred "no data" block that reads like an error; a faint status strip at the bottom reports it instead, brightening only when something genuinely needs fixing.

### New tool: `Lyrics_Tapper.lua`
- A companion authoring tool for building the lyrics/chords/notes items ReaSet reads: paste text, arm, tap along (mouse or Space) to place one item per line — teleprompter-style, in the spirit of Ableset's lyrics tool.
- Restyled with a dark, Ableset-inspired theme; the tapping/timing logic itself is untouched.
- Fixed three real runtime bugs surfaced by actually running it: two ReaImGui API mismatches (`CreateFont`/`PushFont` argument counts) and a color-packing bug (ARGB vs. the RGBA REAPER's ReaImGui actually expects) that was producing an unreadable pink/transparent UI.
- **One more tap now finishes the take.** Tapping through the last line used to require a separate "Stop & Save" click; the (N+1)th tap now closes the last item and finishes automatically.

### Director / Player mode
- **A mode picker on first load.** Every device choosing to open ReaSet picks **Director** (full control) or **Player/Músico** (read-only: live song, progress, lyrics, chords — nothing that reaches REAPER). The choice is remembered per device and doesn't re-ask on a refresh.
- **Enforced at the network layer**, not just the UI: every command ReaSet could send to REAPER passes through one function, and Player mode drops anything that isn't a plain read — a stray click or leftover keyboard shortcut cannot move REAPER's transport.
- **Shared setlist sync.** A Director's setlist (order, skip/loop/chain flags) auto-pushes to a small file `Reaset.lua` writes next to `ReaSet.html`; Players read it automatically, Directors pull manually with a confirmation. A pulled setlist that doesn't match the currently open REAPER project is rejected rather than silently applied.
- **Optional Director PIN.** A Director can set a PIN from the sidebar; from then on, actively choosing Director (not recalling an already-stored choice) asks for it first. Stored as a hash in REAPER's own persisted state — no server, survives a REAPER restart.
- **Two-Directors-at-once warning.** Each Director quietly re-announces itself every few seconds; a second device choosing Director while one is already active is warned before switching, and a banner appears if a second Director shows up later, mid-show.
- None of this is a real security boundary — REAPER's own Web Interface has no authentication — and the README says so explicitly.

### Also
- **Smooth Seek preference**, per project: toggle whether manual song/section/MIDI navigation lets REAPER apply its own smooth-seek behaviour while playing, or always forces an immediate hard jump.

---

# Español

---

## v2.2 — Carrusel de letras en vivo, unificación de Reaset.lua y modo Director/Player
*28 de julio de 2026*

### Instalación y fiabilidad
- **`Reaset.lua`: un script en vez de tres.** Combina el motor de loop nativo, el puente de letras y el puente de acordes en un único script de fondo persistente. Los tracks de letras/acordes ahora son opcionales — sin cuadro de error si no existen — y `ULT_GetMediaItemNote` se llama defensivamente para que la falta de SWS ya no rompa el control de transporte/loop. No requiere configurar un Action ID; la web lo detecta sola. Los tres scripts originales siguen disponibles en `Requirements/` como ruta legacy/avanzada.
- **Corrección del salto fantasma al reconectar Wi-Fi.** ReaSet emite comandos `SET/POS` absolutos basados en la última posición sondeada. Si el flujo de sondeo se corta (una tablet que pierde Wi-Fi) mientras REAPER sigue reproduciendo, la primera respuesta fresca al reconectar solía disparar una decisión de loop/límite obsoleta que saltaba REAPER *hacia atrás* a la posición previa al corte — indistinguible de un tap fantasma. Ahora ReaSet detecta el corte (además de los eventos online/offline del navegador) y suprime solo sus propios comandos de transporte *automáticos* durante una ventana breve, adoptando en silencio la posición real de REAPER; los taps explícitos del usuario nunca se suprimen.
- **Nombres de track decorados.** Los tracks de letras/acordes ya no necesitan llamarse exactamente `lyrics`/`chords` — prefijos, numeración y símbolos decorativos se eliminan antes de comparar (`*Lyrics`, `01 - Chords`, `[Lyrics]`, etc.), mientras que nombres con una palabra extra (`Backing Lyrics`) se dejan intencionalmente sin marcar.
- **Estado real por puente.** En vez de un único aviso genérico "asegurate de tener un track llamado lyrics" para cuatro causas distintas, el mensaje de estado vacío ahora informa la causa real: script no corriendo, ningún track coincide, falta SWS, o track encontrado sin ítem bajo el cursor.
- **Dos bugs de detección reales corregidos.** Un track divisor/carpeta por encima del real (ej. `=== LYRICS ===`) podía taparlo para siempre en silencio; el puente ahora prefiere un track que realmente tenga ítems. Renombrar un track no tenía efecto hasta reiniciar REAPER; ahora se re-escanea cada ~2s cuando el track enganchado deja de coincidir.
- **Detección de puente muerto.** Un script crasheado (no solo ausente) seguía reportando valores obsoletos y congelados como si estuvieran en vivo — nada distinguía un script colgado de uno funcionando. Un contador de tick en vivo más captura de errores detecta esto ahora y lo reporta antes de mostrar cualquier dato obsoleto.
- **`ReaSet_Diagnose.lua`**, un nuevo script de diagnóstico de solo lectura: lista cada track con su nombre normalizado y cantidad de ítems, qué track elegiría cada puente, disponibilidad de SWS, posición del cursor, un volcado de Notes por ítem, y un self-test que prueba que el pipeline de búsqueda funciona sin importar dónde esté el cursor.

### Letras y acordes en vivo — carrusel Cover Flow
- **Contexto de tres líneas.** El panel de letras ahora muestra la estrofa anterior y la siguiente arriba/abajo de la actual, cada una ajustable independientemente desde un nuevo popover de configuración (ícono de engranaje): tamaño, peso, color, contexto on/off.
- **Los acordes reciben el mismo contexto**, distribuidos horizontalmente a los lados del acorde actual.
- **Un carrusel 3D real, no un slide plano**: las estrofas y acordes viven en un tambor y giran hasta su lugar — letras verticalmente, acordes horizontalmente — siempre de frente al espectador, sin inclinación que distraiga en las líneas de contexto. Afinado desde un giro inicial de 380ms hasta uno rápido de 100ms con aterrizaje firme.
- **Controles de tamaño independientes**: Global, Principal (línea actual) y Secundario (líneas de contexto) ahora se ajustan por separado en vez de una escala compartida.
- **Límite de canción respetado.** Las líneas de contexto previa/siguiente ya no se filtran entre canciones — la línea "previa" de la canción anterior desaparece en vez de seguir apareciendo al inicio de la siguiente, y "siguiente" al final de una canción muestra el nombre de la próxima canción en vez del siguiente ítem de letra en la línea de tiempo, sin importar a qué canción pertenezca.
- **Espaciado constante al hacer wrap.** Una estrofa actual de dos líneas ya no se amontona con sus vecinas — el espaciado ahora considera la altura real renderizada de la estrofa.
- **Mensajes de estado más discretos.** Un panel vacío (un pasaje instrumental, un hueco entre estrofas) ya no muestra un bloque grande centrado de "sin datos" que parece un error; una franja de estado tenue al pie lo informa en su lugar, aclarándose solo cuando algo realmente necesita corrección.

### Nueva herramienta: `Lyrics_Tapper.lua`
- Herramienta complementaria de autoría para construir los ítems de letras/acordes/notas que ReaSet lee: pegá el texto, armá, tapeá al ritmo (mouse o Space) para colocar un ítem por línea — estilo teleprompter, en la línea de la herramienta de letras de Ableset.
- Reestilizada con un tema oscuro inspirado en Ableset; la lógica de tapeo/timing en sí no se tocó.
- Corregidos tres bugs reales de runtime detectados al correrla de verdad: dos incompatibilidades de la API de ReaImGui (cantidad de argumentos de `CreateFont`/`PushFont`) y un bug de empaquetado de color (ARGB en vez del RGBA que realmente espera el ReaImGui de REAPER) que producía una interfaz rosa/transparente ilegible.
- **Un tap más ahora termina la toma.** Tapear la última línea antes requería un click aparte en "Stop & Save"; el tap N+1 ahora cierra el último ítem y termina automáticamente.

### Modo Director / Player
- **Selector de modo al cargar por primera vez.** Todo dispositivo que abre ReaSet elige **Director** (control total) o **Player/Músico** (solo lectura: canción en vivo, progreso, letras, acordes — nada que llegue a REAPER). La elección se recuerda por dispositivo y no vuelve a preguntar en cada refresco.
- **Aplicado a nivel de red**, no solo en la interfaz: todo comando que ReaSet pudiera mandarle a REAPER pasa por una sola función, y el modo Player descarta cualquier cosa que no sea una lectura simple — un click perdido o un atajo de teclado que quedó activo no puede mover el transporte de REAPER.
- **Sincronización de setlist compartido.** El setlist del Director (orden, banderas de skip/loop/chain) se empuja automáticamente a un archivo chico que `Reaset.lua` escribe junto a `ReaSet.html`; los Players lo leen automáticamente, los Directores lo traen manualmente con confirmación previa. Un setlist compartido que no coincide con el proyecto de REAPER actualmente abierto se rechaza en vez de aplicarse en silencio.
- **PIN de Director opcional.** Un Director puede fijar un PIN desde el sidebar; a partir de ahí, elegir Director activamente (no recordar una elección ya guardada) lo pide primero. Se guarda como hash en el estado persistido del propio REAPER — sin servidor, sobrevive un reinicio de REAPER.
- **Aviso de dos Directores a la vez.** Cada Director se reanuncia discretamente cada pocos segundos; un segundo dispositivo que elige Director mientras uno ya está activo recibe un aviso antes de cambiar, y aparece un banner si un segundo Director surge más tarde, en medio de un show.
- Nada de esto es una barrera de seguridad real — el propio Web Interface de REAPER no tiene autenticación — y el README lo dice explícitamente.

### También
- **Preferencia de Smooth Seek**, por proyecto: alterna si la navegación manual de canción/sección/MIDI deja que REAPER aplique su propio comportamiento de seek suave mientras reproduce, o siempre fuerza un salto duro inmediato.
