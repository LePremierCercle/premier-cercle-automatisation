# -*- coding: utf-8 -*-
"""
Préparation des vidéos : normalisation et choix d'une image de couverture.
"""

import json
import os
import subprocess

from . import reglages as R


def sonder(chemin):
    """Dimensions, durée, débit et rotation d'une vidéo."""
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
    """
    Ramène la vidéo au format de travail : H.264, débit raisonnable, rotation appliquée.

    Cette étape est obligatoire avant toute incrustation : le téléphone de Bilel
    enregistre en 1920x1080 avec une consigne de rotation, et écrire sur l'image
    sans l'avoir redressée poserait le texte de travers.
    """
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


def meilleure_image(video, destination, candidats=12):
    """
    Choisit l'image la plus nette de la vidéo, en préférant celles où
    un visage est bien cadré. Sert quand Bilel n'a pas déposé de capture.
    """
    import cv2
    import numpy as np

    infos = sonder(video)
    duree = max(1.0, infos["duree"])
    debut, fin = duree * 0.08, duree * 0.85
    instants = [debut + (fin - debut) * i / max(1, candidats - 1) for i in range(candidats)]

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    meilleure, note_max = None, -1.0
    dossier = os.path.dirname(destination) or "."

    for i, t in enumerate(instants):
        essai = os.path.join(dossier, f"_essai{i}.jpg")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", video,
             "-frames:v", "1", "-q:v", "2", essai],
            check=False)
        if not os.path.exists(essai):
            continue

        image = cv2.imread(essai)
        if image is None:
            os.remove(essai)
            continue

        gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        nettete = cv2.Laplacian(gris, cv2.CV_64F).var()
        visages = cascade.detectMultiScale(gris, 1.2, 5, minSize=(80, 80))
        prime = 1.0
        if len(visages):
            x, y, w, h = max(visages, key=lambda v: v[2] * v[3])
            part = (w * h) / float(image.shape[0] * image.shape[1])
            # un visage présent mais pas énorme : c'est le bon plan
            prime = 1.8 if 0.02 < part < 0.35 else 1.2

        note = nettete * prime
        if note > note_max:
            note_max = note
            if meilleure and os.path.exists(meilleure):
                os.remove(meilleure)
            os.replace(essai, destination)
            meilleure = destination
        else:
            os.remove(essai)

    return meilleure
