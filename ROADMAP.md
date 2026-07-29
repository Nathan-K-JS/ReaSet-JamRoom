# ReaSet Roadmap

---

# English

This is where forward-looking, not-yet-built ideas live — as opposed to
[`CHANGELOG.md`](./CHANGELOG.md), which only records what has actually
shipped. Nothing here is a commitment or a timeline, just documented intent
so decisions aren't re-litigated from scratch later.

## Now: MIDI pedals pair to the computer, not the tablet

**Origin:** an M-Vave Chocolate Bluetooth pedalboard (HID keyboard emulation)
connected directly to an iPad wouldn't reach ReaSet — iPadOS Safari only
dispatches `keydown`/`keyup` while a text field has focus
([WebKit #149054](https://bugs.webkit.org/show_bug.cgi?id=149054), open
since 2015), and ReaSet's Web MIDI module (`navigator.requestMIDIAccess`)
has never been supported by Safari either, on any Apple platform. A plan to
work around this client-side (a hidden always-focused `<input>` to trick
Safari into dispatching events) was reviewed and shelved — it's real,
verified-working WebKit-fighting, but it only fixes the iPad it runs on,
adds a permanent maintenance surface, and treats the symptom instead of the
cause.

**The actual fix needs no ReaSet code at all:** pair the pedalboard's
Bluetooth MIDI directly to the Mac running REAPER instead of to the iPad.
REAPER receives real MIDI natively — no HID keyboard emulation, no Safari
keyboard quirk, no per-device workaround. Every ReaSet instance (the
Director's iPad, every Player's iPad) already sees the *result* of a pedal
press for free, via the existing TRANSPORT polling — that's precisely what
the Director/Player architecture is for. Whatever ReaSet-specific action a
pedal needs to trigger beyond REAPER's own native actions (song skip/chain
logic lives in `ReaSet.html`, not as a REAPER action) is future work for
`Reaset.lua` to bridge, exactly the way the shared setlist sync already
bridges Director edits to Players via ExtState — not yet designed, but a
much smaller problem than a browser workaround.

## Later: a desktop companion client

A standalone app (not a REAPER script, not a browser tab) that would own
three jobs ReaSet.html and Reaset.lua currently split awkwardly between a
browser sandbox and a REAPER ReaScript:

- **MIDI input.** Receive from controllers/pedals directly (native MIDI, not
  Web MIDI — sidesteps every Safari/browser MIDI limitation permanently),
  map to ReaSet-level actions (not just REAPER actions), no per-tablet
  pairing required.
- **Multi-client network management.** Today, Director→Player setlist sync
  is a file Reaset.lua writes and Players poll every few seconds — deliberately
  minimal, chosen so this round of work didn't grow the architecture. A real
  hub process could push state instead of being polled (WebSocket / local
  server), turning "up to a few seconds of staleness" into "instant," and
  giving a real point to add authentication beyond the current PIN-as-deterrent.
- **The REAPER bridge.** Whatever `Reaset.lua` does today (loop engine,
  lyrics/chords bridge, ExtState sync) could be driven by this client instead
  of living entirely inside a REAPER defer loop — more headroom than a
  ReaScript's execution model allows.

This is a real architecture step up from "no server, just files and
ExtState" — a deliberate future trade, not a contradiction of the minimalism
chosen for the current Director/Player release. Not designed yet; recorded
here so the shape of the problem isn't rediscovered from zero when it's time.

## Further out: native/PWA app for iPad/Android

Once a desktop hub exists, a tablet app becomes a thin client talking to
*that* hub instead of driving REAPER's Web Interface directly. This is what
actually retires the Safari-keyboard-focus problem for good, if a pedal
ever does need to reach a tablet directly: the hub, not the tablet's
browser, would own the MIDI input, and the tablet would just be a display +
touch surface receiving pushed state.

---

# Español

Acá viven las ideas futuras, todavía sin construir — a diferencia de
[`CHANGELOG.md`](./CHANGELOG.md), que solo registra lo que ya salió. Nada
de esto es un compromiso ni un cronograma, es intención documentada para no
tener que re-discutir las mismas decisiones desde cero más adelante.

## Ahora: los pedales MIDI se emparejan a la computadora, no a la tablet

**Origen:** una pedalera Bluetooth M-Vave Chocolate (emula teclado HID)
conectada directamente a un iPad no llegaba a ReaSet — Safari en iPadOS
solo despacha `keydown`/`keyup` mientras un campo de texto tiene el foco
([WebKit #149054](https://bugs.webkit.org/show_bug.cgi?id=149054), abierto
desde 2015), y el módulo de Web MIDI de ReaSet (`navigator.requestMIDIAccess`)
tampoco lo soporta Safari, en ninguna plataforma de Apple. Se revisó un plan
para resolverlo del lado del cliente (un `<input>` oculto siempre enfocado
para engañar a Safari) y se dejó de lado — es un workaround real y
verificado contra WebKit, pero solo arregla el iPad donde corre, agrega una
superficie de mantenimiento permanente, y ataca el síntoma en vez de la causa.

**La solución real no necesita código de ReaSet:** emparejar el MIDI
Bluetooth de la pedalera directamente a la Mac que corre REAPER, en vez de
al iPad. REAPER recibe MIDI real de forma nativa — sin emulación de teclado
HID, sin la rareza de Safari, sin workaround por dispositivo. Cada instancia
de ReaSet (el iPad del Director, el de cada Player) ya ve el *resultado* de
un pisón del pedal gratis, vía el polling de TRANSPORT existente — para eso
está justamente la arquitectura Director/Player. Lo que haga falta que un
pedal dispare específico de ReaSet más allá de las acciones nativas de
REAPER (la lógica de skip/chain de canciones vive en `ReaSet.html`, no como
acción de REAPER) queda como trabajo futuro para que `Reaset.lua` lo
puentee, tal como el sync de setlist compartido ya puentea las ediciones del
Director hacia los Players vía ExtState — todavía sin diseñar, pero un
problema bastante más chico que un workaround de navegador.

## Más adelante: un cliente de escritorio

Una app independiente (no un script de REAPER, no una pestaña de navegador)
que se haría cargo de tres tareas que hoy `ReaSet.html` y `Reaset.lua`
dividen de forma un poco forzada entre un sandbox de navegador y un
ReaScript de REAPER:

- **Entrada MIDI.** Recibir directo de controladores/pedaleras (MIDI nativo,
  no Web MIDI — evita para siempre cualquier limitación de MIDI en
  navegador/Safari), mapear a acciones de nivel ReaSet (no solo acciones de
  REAPER), sin necesidad de emparejar por tablet.
- **Gestión de red multi-cliente.** Hoy, el sync de setlist Director→Player
  es un archivo que escribe Reaset.lua y que los Players sondean cada pocos
  segundos — deliberadamente mínimo, elegido para que esta ronda de trabajo
  no hiciera crecer la arquitectura. Un proceso hub real podría empujar el
  estado en vez de ser sondeado (WebSocket / servidor local), convirtiendo
  "hasta unos segundos de desfase" en "instantáneo", y dando un punto real
  donde agregar autenticación más allá del PIN actual como disuasivo.
- **El puente con REAPER.** Lo que hoy hace `Reaset.lua` (motor de loop,
  puente de letras/acordes, sync de ExtState) podría manejarlo este cliente
  en vez de vivir enteramente dentro de un defer loop de REAPER — más margen
  del que permite el modelo de ejecución de un ReaScript.

Esto es un salto real de arquitectura respecto de "sin servidor, solo
archivos y ExtState" — un trade-off futuro deliberado, no una contradicción
del minimalismo elegido para el release actual de Director/Player. Todavía
sin diseñar; queda registrado acá para no redescubrir la forma del problema
desde cero cuando llegue el momento.

## Todavía más adelante: app nativa/PWA para iPad/Android

Una vez que exista un hub de escritorio, una app de tablet se vuelve un
cliente delgado que le habla a *ese* hub en vez de manejar el Web Interface
de REAPER directamente. Esto es lo que jubila de verdad el problema del foco
de teclado en Safari, si algún día un pedal necesita llegar directo a una
tablet: el hub, no el navegador de la tablet, sería dueño de la entrada
MIDI, y la tablet sería solo pantalla + superficie táctil recibiendo estado
empujado.
