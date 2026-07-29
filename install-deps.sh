#!/usr/bin/env bash
# Installa le dipendenze di sistema per silenzio-refresh.py:
# portaudio (per sounddevice), LibreWolf (via extrepo) e geckodriver (da Mozilla).
# Google Chrome (necessario solo per il canale la7, DRM/Widevine) va
# installato a parte.
set -euo pipefail

echo "== apt update =="
sudo apt update

echo "== portaudio19-dev + extrepo =="
sudo apt install -y portaudio19-dev extrepo

echo "== abilito repo LibreWolf =="
sudo extrepo enable librewolf

echo "== apt update (nuovo repo) =="
sudo apt update

echo "== installo librewolf =="
sudo apt install -y librewolf

echo "== scarico geckodriver da Mozilla =="
GECKO_VER=$(curl -fsSL https://api.github.com/repos/mozilla/geckodriver/releases/latest | grep -oP '"tag_name": "\K[^"]+')
echo "Versione: $GECKO_VER"
curl -fsSL -o /tmp/geckodriver.tar.gz "https://github.com/mozilla/geckodriver/releases/download/${GECKO_VER}/geckodriver-${GECKO_VER}-linux64.tar.gz"
sudo tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin
sudo chmod +x /usr/local/bin/geckodriver
rm /tmp/geckodriver.tar.gz

echo "== fatto =="
librewolf --version || true
geckodriver --version || true
dpkg -l portaudio19-dev | tail -1
