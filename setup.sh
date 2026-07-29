#!/usr/bin/env bash
# Installa tutto il necessario per guardare le dirette TV (silenzio-refresh.py)
# e aggiunge gli alias di shell a ~/.zshrc. Idempotente: si puo' rilanciare
# quante volte si vuole, salta cio' che e' gia' installato/presente.
set -euo pipefail

TV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$TV_DIR/.venv"
ZSHRC="$HOME/.zshrc"

echo "== Cartella TV: $TV_DIR =="

# --- 1. Dipendenze di sistema ---

echo "== portaudio19-dev (serve a sounddevice per leggere l'audio di sistema) =="
if ! dpkg -s portaudio19-dev &>/dev/null; then
    sudo apt update
    sudo apt install -y portaudio19-dev
else
    echo "gia' installato."
fi

echo "== LibreWolf (pacchetto nativo, non flatpak) =="
if ! command -v librewolf &>/dev/null; then
    sudo apt update
    sudo apt install -y extrepo
    sudo extrepo enable librewolf
    sudo apt update
    sudo apt install -y librewolf
else
    echo "gia' installato."
fi

echo "== geckodriver (da Mozilla, per pilotare LibreWolf) =="
if ! command -v geckodriver &>/dev/null; then
    GECKO_VER=$(curl -fsSL https://api.github.com/repos/mozilla/geckodriver/releases/latest | grep -oP '"tag_name": "\K[^"]+')
    echo "Versione: $GECKO_VER"
    curl -fsSL -o /tmp/geckodriver.tar.gz "https://github.com/mozilla/geckodriver/releases/download/${GECKO_VER}/geckodriver-${GECKO_VER}-linux64.tar.gz"
    sudo tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin
    sudo chmod +x /usr/local/bin/geckodriver
    rm /tmp/geckodriver.tar.gz
else
    echo "gia' installato."
fi

echo "== Google Chrome (solo per La7: DRM/Widevine, assente in LibreWolf) =="
if ! command -v google-chrome &>/dev/null; then
    curl -fsSL -o /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt install -y /tmp/google-chrome.deb
    rm /tmp/google-chrome.deb
else
    echo "gia' installato."
fi

# --- 2. Virtualenv Python ---

echo "== venv Python ($VENV_DIR) =="
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -q selenium sounddevice numpy
echo "venv pronto."

# --- 3. Alias di shell ---

echo "== Alias in $ZSHRC =="
if grep -q "^function la7()" "$ZSHRC" 2>/dev/null; then
    echo "Gli alias sembrano gia' presenti (trovata la funzione 'la7'), non tocco $ZSHRC."
else
    cat >> "$ZSHRC" <<EOF

# >>> Dirette TV (auto-generato da TV/setup.sh) >>>
# La VPN, se serve al tuo provider per qualche sito, va accesa/spenta a
# mano (vpnon/vpnoff) prima di lanciare il canale.
_mediaset_diretta() {
    "$VENV_DIR/bin/python" "$TV_DIR/silenzio-refresh.py" "\$@"
}
function canale5()       { _mediaset_diretta canale5 "\$@" }
function italia1()       { _mediaset_diretta italia1 "\$@" }
function italia2()       { _mediaset_diretta italia2 "\$@" }
function rete4()         { _mediaset_diretta rete4 "\$@" }
function canale20()      { _mediaset_diretta 20mediaset "\$@" }
function iris()          { _mediaset_diretta iris "\$@" }
function la5()           { _mediaset_diretta la5 "\$@" }
function cine34()        { _mediaset_diretta cine34 "\$@" }
function focus()         { _mediaset_diretta focus "\$@" }
function topcrime()      { _mediaset_diretta topcrime "\$@" }
function mediasetextra() { _mediaset_diretta mediasetextra "\$@" }
function tgcom24()       { _mediaset_diretta tgcom24 "\$@" }

_rai_diretta() {
    "$VENV_DIR/bin/python" "$TV_DIR/silenzio-refresh.py" --site rai "\$@"
}
function rai1()       { _rai_diretta rai1 "\$@" }
function rai2()       { _rai_diretta rai2 "\$@" }
function rai3()       { _rai_diretta rai3 "\$@" }
function rai4()       { _rai_diretta rai4 "\$@" }
function rai5()       { _rai_diretta rai5 "\$@" }
function raigulp()    { _rai_diretta raigulp "\$@" }
function raimovie()   { _rai_diretta raimovie "\$@" }
function rainews24()  { _rai_diretta rainews24 "\$@" }
function raipremium() { _rai_diretta raipremium "\$@" }
function rairadio2()  { _rai_diretta rairadio2 "\$@" }
function raiscuola()  { _rai_diretta raiscuola "\$@" }
function raisport()   { _rai_diretta raisport "\$@" }
function raistoria()  { _rai_diretta raistoria "\$@" }
function raiyoyo()    { _rai_diretta raiyoyo "\$@" }

_la7_diretta() {
    "$VENV_DIR/bin/python" "$TV_DIR/silenzio-refresh.py" --site la7 "\$@"
}
function la7() { _la7_diretta la7 "\$@" }

_tv8_diretta() {
    "$VENV_DIR/bin/python" "$TV_DIR/silenzio-refresh.py" --site tv8 "\$@"
}
function tv8() { _tv8_diretta tv8 "\$@" }

# Nove: con la VPN accesa il video resta bloccato in caricamento
# (probabile blocco geografico) -> tienila spenta con vpnoff.
_nove_diretta() {
    "$VENV_DIR/bin/python" "$TV_DIR/silenzio-refresh.py" --site nove "\$@"
}
function nove() { _nove_diretta nove "\$@" }
# <<< Dirette TV <<<
EOF
    echo "Alias aggiunti. Esegui 'source ~/.zshrc' (o apri un nuovo terminale) per usarli subito."
fi

echo "== Fatto: canale5, rai1, la7, tv8, nove ecc. sono pronti =="
