#!/usr/bin/env python3
"""
Monitora l'audio di sistema mentre LibreWolf riproduce una diretta TV
(Mediaset Infinity o RaiPlay) e ricarica la pagina quando l'audio resta
in silenzio troppo a lungo.

Perche' via loopback audio e non via Web Audio API dentro la pagina:
alcuni stream (es. Mediaset) possono essere protetti da DRM (Widevine/
EME); i browser bloccano deliberatamente l'estrazione dell'audio via
JavaScript dai contenuti protetti, quindi un AnalyserNode dentro la
pagina leggerebbe sempre "silenzio" anche a stream perfettamente
funzionante. Leggendo invece il device di loopback di sistema
(monitor della sink PulseAudio/PipeWire) si intercetta l'audio dopo
la decodifica, quindi funziona a prescindere dal DRM.

Requisiti (Debian/derivate):
    sudo apt install portaudio19-dev firefox-geckodriver
    pip install --user selenium sounddevice numpy
LibreWolf va installato a parte (pacchetto nativo, non flatpak: il
flatpak non espone un binario utilizzabile da geckodriver).

Il rilevamento del silenzio guarda TUTTO l'audio di sistema: tieni
chiuse altre sorgenti sonore mentre lo script gira, altrimenti falsera'
la lettura.
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

# Su sistemi PipeWire (es. GNOME/Debian moderni) PortAudio non espone un
# device "Monitor of ..." separato: bisogna passare dal device ALSA
# generico "pulse" e dire al layer di compatibilita' PulseAudio quale
# sorgente usare tramite questa variabile d'ambiente. Va impostata PRIMA
# di aprire lo stream (letta a ogni connessione, non solo all'import).
os.environ.setdefault("PULSE_SOURCE", "@DEFAULT_SINK@.monitor")

try:
    import sounddevice as sd
except OSError as exc:
    sys.exit(
        "Impossibile caricare PortAudio. Installa la libreria di sistema:\n"
        "  sudo apt install portaudio19-dev\n"
        f"Dettaglio: {exc}"
    )

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def accept_cookies_mediaset(driver, timeout: float = 8.0) -> None:
    """Banner cookie Iubenda di Mediaset Infinity: apre il pannello
    granulare e accetta solo i cookie strettamente necessari."""
    try:
        open_modal_btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.ID, "rti-privacy-open-modal-btn-id"))
        )
    except TimeoutException:
        return
    open_modal_btn.click()
    try:
        necessary_only_btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.ID, "rti-privacy-close-btn-id"))
        )
        necessary_only_btn.click()
        print("Cookie: accettati solo i necessari.")
    except TimeoutException:
        print("Attenzione: banner cookie aperto ma bottone 'solo necessari' non trovato.")


def accept_cookies_rai(driver, timeout: float = 8.0) -> None:
    """Banner cookie (Avacy) di RaiPlay: 'Continua senza accettare' rifiuta
    tutto il non necessario in un solo click."""
    try:
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".as-js-close-banner"))
        )
        btn.click()
        print("Cookie: consenso rifiutato (solo necessari).")
    except TimeoutException:
        return


def accept_cookies_tv8(driver, timeout: float = 8.0) -> None:
    """Banner cookie di TV8: e' un CMP Sky/Sourcepoint dentro un iframe
    cross-origin (cmp.sky.it). 'Continua senza accettare' rifiuta il non
    necessario in un solo click."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[src*='cmp.sky.it']"))
        )
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".sp_choice_type_13"))
        )
        btn.click()
        print("Cookie: consenso rifiutato (solo necessari).")
    except TimeoutException:
        pass
    finally:
        driver.switch_to.default_content()


def click_play_rai(driver, timeout: float = 15.0) -> None:
    """Su RaiPlay il tag <video> non esiste finche' non si preme il
    pulsante 'Riproduci': il click va simulato prima di aspettare il video."""
    try:
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, "//*[@aria-label='Riproduci']"))
        )
        btn.click()
        print("Player: cliccato 'Riproduci'.")
    except TimeoutException:
        pass


def accept_cookies_nove(driver, timeout: float = 8.0) -> None:
    """Banner cookie OneTrust di Nove: 'Mostra finalita'' apre il pannello
    granulare, poi 'Solo cookie essenziali' rifiuta il non necessario."""
    try:
        prefs_btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.ID, "onetrust-pc-btn-handler"))
        )
    except TimeoutException:
        return
    prefs_btn.click()
    try:
        only_essential_btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Solo cookie essenziali')]"))
        )
        only_essential_btn.click()
        print("Cookie: accettati solo i necessari.")
    except TimeoutException:
        print("Attenzione: pannello preferenze cookie Nove aperto ma bottone 'solo essenziali' non trovato.")


def click_play_nove(driver, timeout: float = 15.0) -> None:
    """Il player di Nove (Video.js) mostra un grande pulsante 'Play' che
    va cliccato per far partire lo stream. Il player parte pero' muto
    (autoplay silenzioso concesso dal browser): va smutato via JS subito
    dopo, altrimenti il video scorre ma non produce mai audio."""
    try:
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".vjs-big-play-button"))
        )
        btn.click()
        print("Player: cliccato 'Play'.")
    except TimeoutException:
        return
    time.sleep(1.5)
    try:
        driver.execute_script("var v = document.querySelector('video'); if (v) v.muted = false;")
    except WebDriverException:
        pass


def accept_cookies_la7(driver, timeout: float = 8.0) -> None:
    """Banner cookie IAB TCF2 di La7 (CMP custom "la7_iabtcf2"): il
    pulsante di primo livello che rifiuta il non necessario in un solo
    click e' mostrato come "REJECT & CONTINUE" (LibreWolf riporta la UI
    del CMP in inglese anche se il resto del sito e' in italiano, dove
    sarebbe "Continua senza accettare"); il match e' case-insensitive e
    cerca solo "reject"/"senza accettare" cosi' regge variazioni di
    maiuscole/lingua/"and" vs "&". NON va mai aperto "Preferences": il
    pannello granulare blocca l'automazione in modo affidabile (il click
    resta appeso indefinitamente), a differenza di questo pulsante."""
    try:
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//*[self::button or self::a or self::div or self::span]"
                "[contains(translate(text(), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reject')"
                " or contains(translate(text(), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'senza accettare')]",
            ))
        )
        btn.click()
        print("Cookie: consenso rifiutato (solo necessari).")
    except TimeoutException:
        return


# Slug/base URL verificati direttamente sui siti (pagine SPA renderizzate
# via JS: se un canale non funziona piu', apri il sito e copia lo slug
# dalla barra indirizzi, poi aggiornalo qui sotto).
SITES = {
    "mediaset": {
        "base_url": "https://mediasetinfinity.mediaset.it/diretta/{slug}",
        "channels": {
            "canale5": "canale5_cC5",
            "italia1": "italia1_cI1",
            "italia2": "italia2_cI2",
            "rete4": "rete4_cR4",
            "20mediaset": "20mediaset_cLB",
            "iris": "iris_cKI",
            "la5": "la5_cKA",
            "cine34": "cine34_cB6",
            "focus": "focus_cFU",
            "topcrime": "topcrime_cLT",
            "mediasetextra": "mediasetextra_cKQ",
            "tgcom24": "video_cKF",
        },
        "profile_dirname": ".librewolf-mediaset-profile",
        "accept_cookies": accept_cookies_mediaset,
        "click_play": None,
    },
    "rai": {
        "base_url": "https://www.raiplay.it/dirette/{slug}",
        "channels": {
            "rai1": "rai1",
            "rai2": "rai2",
            "rai3": "rai3",
            "rai4": "rai4",
            "rai5": "rai5",
            "raigulp": "raigulp",
            "raimovie": "raimovie",
            "rainews24": "rainews24",
            "raipremium": "raipremium",
            "rairadio2": "rairadio2",
            "raiscuola": "raiscuola",
            "raisport": "raisport",
            "raistoria": "raistoria",
            "raiyoyo": "raiyoyo",
        },
        "profile_dirname": ".librewolf-rai-profile",
        "accept_cookies": accept_cookies_rai,
        "click_play": click_play_rai,
    },
    # La7: sulla homepage (https://www.la7.it/) c'e' solo un'anteprima
    # decorativa muta senza vero player (nessun .vjs-big-play-button); il
    # player video.js reale della diretta e' su /dirette-tv. Lo stream e'
    # protetto DRM/Widevine: LibreWolf non ha il CDM installabile (rimosso
    # per policy privacy), quindi qui si usa Google Chrome, che lo include
    # gia'. Con --autoplay-policy=no-user-gesture-required (impostato in
    # main per il browser "chrome") lo stream parte gia' con l'audio
    # attivo, senza bisogno di cliccare il pulsante Play del player.
    "la7": {
        "base_url": "https://www.la7.it/{slug}",
        "channels": {"la7": "dirette-tv"},
        "profile_dirname": ".chrome-la7-profile",
        "browser": "chrome",
        "accept_cookies": accept_cookies_la7,
        "click_play": None,
    },
    "tv8": {
        "base_url": "https://www.tv8.it/{slug}",
        "channels": {"tv8": "streaming"},
        "profile_dirname": ".librewolf-tv8-profile",
        "accept_cookies": accept_cookies_tv8,
        "click_play": None,
    },
    # ATTENZIONE: a differenza degli altri siti, Nove NON funziona con la
    # VPN (wg0) attiva - va tenuta spenta (gestito nell'alias di shell).
    # Il dominio nove.it e' un parcheggio pubblicitario scaduto, non il
    # sito vero: quello reale e' nove.tv.
    "nove": {
        "base_url": "https://nove.tv/{slug}",
        "channels": {"nove": "live-streaming-nove"},
        "profile_dirname": ".librewolf-nove-profile",
        "accept_cookies": accept_cookies_nove,
        "click_play": click_play_nove,
    },
}


def find_librewolf_binary(explicit_path: str | None) -> str:
    if explicit_path:
        if not Path(explicit_path).is_file():
            sys.exit(f"Binario LibreWolf non trovato: {explicit_path}")
        return explicit_path
    found = shutil.which("librewolf")
    if found:
        return found
    for candidate in ("/usr/bin/librewolf", "/usr/local/bin/librewolf", "/opt/librewolf/librewolf"):
        if Path(candidate).is_file():
            return candidate
    sys.exit(
        "LibreWolf non trovato nel PATH. Installa il pacchetto nativo "
        "oppure indica il percorso con --librewolf-path."
    )


def find_chrome_binary(explicit_path: str | None) -> str:
    if explicit_path:
        if not Path(explicit_path).is_file():
            sys.exit(f"Binario Chrome non trovato: {explicit_path}")
        return explicit_path
    found = shutil.which("google-chrome")
    if found:
        return found
    for candidate in ("/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/opt/google/chrome/google-chrome"):
        if Path(candidate).is_file():
            return candidate
    sys.exit(
        "Google Chrome non trovato nel PATH. Installa il pacchetto (necessario per i siti "
        "con DRM/Widevine non supportato da LibreWolf) oppure indica il percorso con --chrome-path."
    )


def find_monitor_device(explicit_device: str | None):
    if explicit_device:
        return explicit_device
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        name = dev.get("name", "")
        if dev.get("max_input_channels", 0) > 0 and "monitor" in name.lower():
            return idx
    # Sistemi PipeWire: niente device "Monitor of ...", si passa dal device
    # ALSA "pulse" (PULSE_SOURCE=@DEFAULT_SINK@.monitor impostato in alto).
    for idx, dev in enumerate(devices):
        if dev.get("name", "").lower() == "pulse" and dev.get("max_input_channels", 0) > 0:
            return idx
    sys.exit(
        "Nessun device di loopback trovato (ne' 'Monitor of ...' ne' 'pulse').\n"
        "Elenca i device disponibili con:\n"
        "  python3 -c \"import sounddevice as sd; print(sd.query_devices())\"\n"
        "e passa quello giusto con --audio-device <indice_o_nome>."
    )


def rms_dbfs(samples: np.ndarray) -> float:
    rms = np.sqrt(np.mean(np.square(samples), dtype=np.float64))
    if rms <= 1e-9:
        return -120.0
    return 20 * np.log10(rms)


def wait_for_video_element(driver, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            driver.find_element("tag name", "video")
            return True
        except NoSuchElementException:
            time.sleep(1)
    return False


def is_fullscreen(driver) -> bool:
    """Rileva sia lo schermo intero nativo del browser (F11/gestito dal
    window manager, non esposto come API di pagina: si approssima
    confrontando le dimensioni esterne della finestra con lo schermo) sia
    quello innescato dal player via Fullscreen API (document.fullscreenElement,
    es. il pulsante di espansione di video.js)."""
    try:
        return bool(driver.execute_script(
            "return !!document.fullscreenElement || "
            "(window.outerWidth === screen.width && window.outerHeight === screen.height);"
        ))
    except WebDriverException:
        return False


def load_page(driver, url: str, site_cfg: dict) -> None:
    driver.get(url)
    accept_cookies = site_cfg.get("accept_cookies")
    if accept_cookies:
        accept_cookies(driver)
    click_play = site_cfg.get("click_play")
    if click_play:
        click_play(driver)
    if not wait_for_video_element(driver, timeout=30):
        print("Attenzione: nessun tag <video> individuato entro 30s (potrebbe essere in un iframe o dietro un consenso cookie). Proseguo comunque.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--site",
        choices=sorted(SITES),
        default="mediaset",
        help="Sito da guardare (default: mediaset)",
    )
    parser.add_argument(
        "channel",
        nargs="?",
        default=None,
        help="Nome canale del sito scelto, oppure slug/URL diretto (default: primo canale del sito)",
    )
    parser.add_argument(
        "--profile-dir",
        default=None,
        help="Profilo LibreWolf persistente da usare (default: uno specifico per sito, mantiene DRM/Widevine, cookie e login tra un lancio e l'altro)",
    )
    parser.add_argument("--no-maximize", action="store_true", help="Non massimizzare la finestra all'avvio")
    parser.add_argument("--librewolf-path", default=None, help="Percorso del binario LibreWolf")
    parser.add_argument("--geckodriver-path", default=None, help="Percorso di geckodriver se non e' nel PATH")
    parser.add_argument("--chrome-path", default=None, help="Percorso del binario Google Chrome (siti con DRM/Widevine, es. la7)")
    parser.add_argument("--chromedriver-path", default=None, help="Percorso di chromedriver se non e' nel PATH (default: scaricato automaticamente da Selenium Manager)")
    parser.add_argument("--audio-device", default=None, help="Indice o nome del device di loopback da usare")
    parser.add_argument("--silence-threshold-db", type=float, default=-50.0, help="Soglia sotto la quale l'audio e' considerato silenzio (dBFS, default -50)")
    parser.add_argument("--silence-seconds", type=float, default=5.0, help="Silenzio continuo (secondi) prima di ricaricare la pagina (default 5)")
    parser.add_argument("--startup-grace-seconds", type=float, default=12.0, help="Tempo dopo ogni caricamento/reload in cui il silenzio non viene contato, per dare tempo allo stream di partire davvero (default 12)")
    parser.add_argument("--check-interval", type=float, default=0.5, help="Intervallo di campionamento audio in secondi (default 0.5)")
    parser.add_argument("--headless", action="store_true", help="Avvia LibreWolf in modalita' headless (sconsigliato: alcuni player si rifiutano di partire senza finestra visibile)")
    args = parser.parse_args()

    site_cfg = SITES[args.site]
    channels = site_cfg["channels"]
    channel = args.channel or next(iter(channels))

    slug = channels.get(channel, channel)
    if slug.startswith("http"):
        url = slug
    else:
        url = site_cfg["base_url"].format(slug=slug)

    browser = site_cfg.get("browser", "firefox")
    device = find_monitor_device(args.audio_device)
    device_info = sd.query_devices(device)
    samplerate = int(device_info["default_samplerate"])

    profile_dir = Path(args.profile_dir) if args.profile_dir else Path.home() / "TV" / site_cfg["profile_dirname"]
    profile_dir.mkdir(parents=True, exist_ok=True)

    if browser == "chrome":
        binary = find_chrome_binary(args.chrome_path)
        options = ChromeOptions()
        options.binary_location = binary
        options.add_argument(f"--user-data-dir={profile_dir}")
        # Un click Selenium conta come gesture utente vera, ma questo
        # evita comunque qualunque prompt/blocco extra sull'autoplay.
        options.add_argument("--autoplay-policy=no-user-gesture-required")
        options.add_argument("--no-first-run")
        if args.headless:
            options.add_argument("--headless=new")

        service_kwargs = {}
        if args.chromedriver_path:
            service_kwargs["executable_path"] = args.chromedriver_path
        service = ChromeService(**service_kwargs)

        print(f"Avvio Google Chrome ({binary}) su {url}")
        driver = webdriver.Chrome(options=options, service=service)
    else:
        binary = find_librewolf_binary(args.librewolf_path)
        options = FirefoxOptions()
        options.binary_location = binary
        options.add_argument("-profile")
        options.add_argument(str(profile_dir))
        # Permette l'autoplay con audio senza doverlo abilitare a mano dal
        # pannello about:preferences ad ogni nuovo profilo (0 = consenti
        # sempre audio e video).
        options.set_preference("media.autoplay.default", 0)
        if args.headless:
            options.add_argument("-headless")

        service_kwargs = {}
        if args.geckodriver_path:
            service_kwargs["executable_path"] = args.geckodriver_path
        service = FirefoxService(**service_kwargs)

        print(f"Avvio LibreWolf ({binary}) su {url}")
        driver = webdriver.Firefox(options=options, service=service)
    if not args.headless and not args.no_maximize:
        # Finestra massimizzata (non fullscreen esclusivo): su Wayland un
        # fullscreen vero non puo' essere coperto da nient'altro, nemmeno
        # dal terminale. Massimizzata invece resta una finestra normale,
        # richiamabile in qualsiasi momento con un click o Alt+Tab.
        driver.maximize_window()

    try:
        load_page(driver, url, site_cfg)
        stream_ready_at = time.monotonic() + args.startup_grace_seconds

        print(f"Monitoraggio audio di sistema su device #{device} ({device_info['name']}, {samplerate} Hz)")
        print(f"Soglia silenzio: {args.silence_threshold_db} dBFS per {args.silence_seconds}s -> ricarico la pagina")

        silence_started = None
        block_size = max(1, int(samplerate * args.check_interval))

        with sd.InputStream(device=device, channels=1, samplerate=samplerate, blocksize=block_size) as stream:
            while True:
                samples, _ = stream.read(block_size)
                level_db = rms_dbfs(samples[:, 0])
                now = time.monotonic()

                if now < stream_ready_at:
                    continue

                if level_db < args.silence_threshold_db:
                    if silence_started is None:
                        silence_started = now
                    elapsed = now - silence_started
                    if elapsed >= args.silence_seconds:
                        print(f"[{time.strftime('%H:%M:%S')}] Silenzio da {elapsed:.0f}s ({level_db:.1f} dBFS) -> reload pagina")
                        was_fullscreen = is_fullscreen(driver)
                        try:
                            driver.get(url)
                            accept_cookies = site_cfg.get("accept_cookies")
                            if accept_cookies:
                                accept_cookies(driver)
                            click_play = site_cfg.get("click_play")
                            if click_play:
                                click_play(driver)
                            wait_for_video_element(driver, timeout=30)
                            if was_fullscreen:
                                driver.fullscreen_window()
                                print("Schermo intero ripristinato.")
                        except WebDriverException as exc:
                            print(f"Errore durante il reload: {exc}")
                        silence_started = None
                        stream_ready_at = time.monotonic() + args.startup_grace_seconds
                else:
                    silence_started = None
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
