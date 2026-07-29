# TV

Script per guardare le dirette TV italiane (Mediaset Infinity, RaiPlay, La7,
TV8, Nove) nel browser, con ricarica automatica della pagina se l'audio si
interrompe.

## Come funziona

`mediaset-silenzio-refresh.py` apre un browser via Selenium sulla diretta
del canale scelto, gestisce da solo il banner cookie e (dove serve) il
click sul pulsante Play, poi monitora **l'audio di sistema** (loopback
PulseAudio/PipeWire, non l'audio della pagina) per rilevare quando lo
stream si blocca. Se resta in silenzio troppo a lungo, ricarica la
pagina automaticamente; se la finestra era a schermo intero, la
ripristina dopo il ricaricamento.

Il rilevamento passa dal loopback di sistema (non da un `AnalyserNode`
dentro la pagina) perche' alcuni stream sono protetti da DRM/Widevine: i
browser bloccano l'estrazione dell'audio via JavaScript dai contenuti
protetti, quindi leggere l'audio dopo la decodifica a livello di sistema
funziona a prescindere dal DRM.

Ogni sito usa un browser persistente dedicato (profilo separato per
sito, mai versionato — vedi `.gitignore`): **LibreWolf** per la maggior
parte dei siti, **Google Chrome** per La7, il cui stream e' protetto da
Widevine e LibreWolf non include il CDM necessario a decriptarlo (rimosso
per policy di privacy).

## Canali disponibili

| Sito (`--site`) | Canali |
|---|---|
| `mediaset` (default) | canale5, italia1, italia2, rete4, 20mediaset, iris, la5, cine34, focus, topcrime, mediasetextra, tgcom24 |
| `rai` | rai1, rai2, rai3, rai4, rai5, raigulp, raimovie, rainews24, raipremium, rairadio2, raiscuola, raisport, raistoria, raiyoyo |
| `la7` | la7 |
| `tv8` | tv8 |
| `nove` | nove |

## Requisiti

- Debian/derivate, PulseAudio o PipeWire con compatibilita' Pulse
- LibreWolf (pacchetto nativo, non flatpak: il flatpak non espone un
  binario utilizzabile da geckodriver) + geckodriver
- Google Chrome (solo per il sito `la7`)
- Python 3 con `selenium`, `sounddevice`, `numpy` (usare un venv,
  es. `.venv-mediaset/` — ignorato da git)

Installazione delle dipendenze di sistema (portaudio, LibreWolf,
geckodriver):

```sh
./install-mediaset-deps.sh
```

## Uso

```sh
python mediaset-silenzio-refresh.py --site <sito> <canale>
```

Esempio:

```sh
python mediaset-silenzio-refresh.py --site rai rai1
```

Senza `--site` usa `mediaset` come default. Senza indicare il canale,
usa il primo canale del sito. `Ctrl+C` interrompe e chiude il browser.

Opzioni principali (`--help` per l'elenco completo): `--silence-seconds`,
`--silence-threshold-db`, `--startup-grace-seconds`, `--audio-device`,
`--headless`, `--no-maximize`, `--profile-dir`, `--librewolf-path`,
`--chrome-path`.

### Alias di shell

Nel proprio `.zshrc`/`.bashrc` conviene definire una funzione per canale
che richiama lo script (gestendo anche l'accensione/spegnimento di
un'eventuale VPN, se il proprio provider la richiede per alcuni siti).
Esempio minimo:

```sh
function rai1() { python /percorso/a/mediaset-silenzio-refresh.py --site rai rai1 "$@" }
```
