# 📺 TV

**Le dirette TV italiane, in un comando.** Un canale, un browser, zero
clic — cookie accettati da soli, audio sempre attivo, e se lo stream si
pianta se ne accorge lui e ricarica la pagina al posto tuo.

```sh
git clone https://github.com/franmuzi1/TV.git && cd TV
./setup.sh
rai1
```

Tutto qui.

---

## 🎬 Come funziona

`silenzio-refresh.py` apre un browser via Selenium sulla diretta del
canale scelto, si accolla da solo il banner cookie e (dove serve) il
click sul pulsante Play, poi monitora **l'audio di sistema** (loopback
PulseAudio/PipeWire, non l'audio della pagina) per capire quando lo
stream si e' impallato. Se resta muto troppo a lungo, ricarica la
pagina da solo — e se stavi guardando a schermo intero, ce lo riporta
subito dopo, cursore del mouse spostato fuori dai piedi.

Il rilevamento passa dal loopback di sistema, non da un `AnalyserNode`
dentro la pagina, perche' alcuni stream sono protetti da DRM/Widevine:
i browser bloccano deliberatamente l'estrazione dell'audio via
JavaScript dai contenuti protetti, quindi leggere l'audio dopo la
decodifica a livello di sistema funziona a prescindere dal DRM.

Ogni sito ha un browser persistente dedicato (profilo separato per
sito, mai versionato — vedi `.gitignore`): **LibreWolf** per la
maggior parte, **Google Chrome** per La7, il cui stream e' protetto da
Widevine e LibreWolf non include il CDM necessario a decriptarlo
(rimosso per policy di privacy).

## 📡 Canali disponibili

| Sito | Canali |
|---|---|
| **Mediaset Infinity** | canale5 · italia1 · italia2 · rete4 · canale20 · iris · la5 · cine34 · focus · topcrime · mediasetextra · tgcom24 |
| **RaiPlay** | rai1 · rai2 · rai3 · rai4 · rai5 · raigulp · raimovie · rainews24 · raipremium · rairadio2 · raiscuola · raisport · raistoria · raiyoyo |
| **La7** | la7 |
| **TV8** | tv8 |
| **Nove** | nove |

29 canali, tutti richiamabili per nome dopo `./setup.sh`.

## ⚙️ Installazione

```sh
./setup.sh
```

Un colpo solo, e si puo' rilanciare quante volte si vuole (idempotente,
salta cio' che c'e' gia'):

- installa quello che manca — `curl`, `ca-certificates`, `python3-venv`,
  `zsh`, LibreWolf + geckodriver, Google Chrome (solo per `la7`),
  portaudio
- crea il venv Python (`.venv/`) con `selenium`, `sounddevice`, `numpy`
- aggiunge gli alias (`canale5`, `rai1`, `la7`, ...) a `~/.zshrc`

Dopo il primo lancio: `source ~/.zshrc` (o un nuovo terminale) e i
canali sono pronti.

**Prerequisiti che invece deve avere gia' la macchina** (non installabili
da uno script):

- Debian/derivate con un **ambiente desktop gia' attivo** (X11 o
  Wayland) — si aprono finestre di browser vere, niente server headless
- un **server audio funzionante** (PipeWire-pulse o PulseAudio) — quasi
  certo su qualunque desktop, ma non forziamo l'installazione per non
  scavalcare quello gia' in uso
- `git`, per clonare il repo

## ▶️ Uso

```sh
rai1
```

oppure, senza alias:

```sh
python silenzio-refresh.py --site <sito> <canale>
python silenzio-refresh.py --site rai rai1
```

Senza `--site` usa `mediaset`; senza canale, il primo del sito.
`Ctrl+C` interrompe e chiude il browser.

> **VPN**: se il tuo provider ne richiede una per qualche sito, va
> accesa/spenta a mano (es. `sudo wg-quick up wg0`) prima di lanciare il
> canale — lo script non la gestisce.

Opzioni principali (`--help` per l'elenco completo): `--silence-seconds`,
`--silence-threshold-db`, `--startup-grace-seconds`, `--audio-device`,
`--headless`, `--no-maximize`, `--profile-dir`, `--librewolf-path`,
`--chrome-path`.

## 🪟 Versione Windows

Cartella `windows/`: stessa idea (cookie/play automatici, reload sul
silenzio, schermo intero ripristinato, volume di sistema controllato),
ma solo **Google Chrome** (niente LibreWolf) e un **eseguibile con
finestra grafica** al posto degli alias di shell — apri `TV.exe`,
scegli sito e canale da una lista, premi "Guarda".

Il file `.exe` viene compilato automaticamente da GitHub Actions
(workflow `build-windows.yml`, gira su `windows-latest`): dopo ogni
push che tocca `windows/`, lo trovi come artifact nella scheda
**Actions** del repo. Richiede Google Chrome gia' installato sul PC
Windows di destinazione.

> ⚠️ Non testato su una vera macchina Windows (sviluppato da un
> ambiente Linux, verificato solo per sintassi e impacchettamento via
> CI): in particolare la cattura audio WASAPI loopback e il controllo
> mute via `pycaw` potrebbero aver bisogno di aggiustamenti. Se qualcosa
> non va, segnalalo.
