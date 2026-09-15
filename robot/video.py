# -*- coding: utf-8 -*-
"""
Preparation des videos : normalisation et choix d'une image de couverture.
"""

import json
import os
import subprocess

from . import reglages as R


def sonder(chemin):
    """Dimensions, duree, debit et rotation d'une video."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", chemin],
        capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    flux = next((f for f in d["streams"] if f["codec_type"] == "video"), {})
    rotation = 0
    for cote in flux.get("side_data_list", []) or []:
        if "rotation" in cote:
            rotation = int(cote["rotation"])
    largeur, hauteur = int(flux.get("width", 0)), int(flux.get("height", 0))
    if abs(rotation) in (90, 270):
        largeur, hauteur = hauteur, largeur
    return {
        "largeur": largeur,
        "hauteur": hauteur,
        "duree": float(d["format"].get("duration", 0)),
        "octets": int(d["format"].get("size", 0)),
        "rotation": rotation,
        "a_du_son": any(f["codec_type"] == "audio" for f in d["streams"]),
    }


def normaliser(entree, sortie, debit=None):
    """Ramene la video au format de travail : H.264, debit raisonnable, rotation appliquee."""
    debit = debit or R.DEBIT_CIBLE
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", entree,
         "-c:v", "libx264", "-preset", "veryfast",
         "-b:v", debit, "-maxrate", debit, "-bufsize", "20M",
         "-pix_fmt", "yuv420p", "-r", "30",
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", sortie],
        check=True)
    return sortie


def _note(chemin):
    """
    Note une image : nettete d'abord, luminosite ensuite.

    On n'utilise plus la detection de visage d'OpenCV : elle n'est pas
    disponible partout, et la nettete suffit a departager les images.
    """
    import numpy as np
    from PIL import Image

    with Image.open(chemin) as img:
        gris = img.convert("L")
        gris.thumbnail((640, 640))
        a = np.asarray(gris, dtype=float)

    if a.size == 0:
        return -1.0

    # Laplacien : plus la variance est haute, plus l'image est nette.
    lap = (a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
           - 4.0 * a[1:-1, 1:-1])
    nettete = float(lap.var())

    # On ecarte les images trop sombres ou cramees.
    moyenne = float(a.mean())
    if moyenne < 35 or moyenne > 225:
        nettete *= 0.3

    return nettete


def meilleure_image(video, destination, candidats=12):
    """
    Choisit l'image la plus nette de la video.
    Sert quand Bilel n'a pas depose de capture.
    """
    infos = sonder(video)
    duree = max(1.0, infos["duree"])
    debut, fin = duree * 0.08, duree * 0.85
    instants = [debut + (fin - debut) * i / max(1, candidats - 1)
                for i in range(candidats)]

    dossier = os.path.dirname(destination) or "."
    meilleure, note_max = None, -1.0

    for i, t in enumerate(instants):
        essai = os.path.join(dossier, "_essai%d.jpg" % i)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % t, "-i", video,
             "-frames:v", "1", "-q:v", "2", essai],
            check=False)
        if not os.path.exists(essai):
            continue

        try:
            note = _note(essai)
        except Exception:
            note = -1.0

        if note > note_max:
            note_max = note
            os.replace(essai, destination)
            meilleure = destination
        else:
            try:
                os.remove(essai)
            except OSError:
                pass

    return meilleure
