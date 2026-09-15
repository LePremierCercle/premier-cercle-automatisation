# -*- coding: utf-8 -*-
"""
Installe les polices dont le robot a besoin : Inter et Lora.

Lancé une fois au démarrage. Si les polices sont déjà en cache, il ne
télécharge rien.
"""

import io
import os
import sys
import urllib.request
import zipfile

DOSSIER = os.path.expanduser("~/.fonts")

INTER = "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip"
LORA = "https://github.com/google/fonts/raw/main/ofl/lora/Lora%5Bwght%5D.ttf"
LORA_ITALIQUE = "https://github.com/google/fonts/raw/main/ofl/lora/Lora-Italic%5Bwght%5D.ttf"


def _telecharger(url, destination):
    demande = urllib.request.Request(url, headers={"User-Agent": "robot-premier-cercle"})
    with urllib.request.urlopen(demande, timeout=120) as reponse:
        donnees = reponse.read()
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "wb") as f:
        f.write(donnees)
    return destination


def installer():
    os.makedirs(DOSSIER, exist_ok=True)

    inter = os.path.join(DOSSIER, "inter")
    if not os.path.exists(os.path.join(inter, "extras", "otf", "Inter-Bold.otf")):
        print("Téléchargement d'Inter…")
        demande = urllib.request.Request(INTER, headers={"User-Agent": "robot"})
        with urllib.request.urlopen(demande, timeout=180) as reponse:
            archive = zipfile.ZipFile(io.BytesIO(reponse.read()))
        archive.extractall(inter)
        print("Inter installée.")
    else:
        print("Inter déjà présente.")

    lora = os.path.join(DOSSIER, "lora")
    cible = os.path.join(lora, "Lora-Italic-Variable.ttf")
    if not os.path.exists(cible):
        print("Téléchargement de Lora…")
        _telecharger(LORA, os.path.join(lora, "Lora-Variable.ttf"))
        _telecharger(LORA_ITALIQUE, cible)
        print("Lora installée.")
    else:
        print("Lora déjà présente.")

    return True


if __name__ == "__main__":
    try:
        installer()
    except Exception as e:
        print("Installation des polices impossible :", e, file=sys.stderr)
        sys.exit(1)
