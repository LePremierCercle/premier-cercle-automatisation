# -*- coding: utf-8 -*-
"""
Rapprochement des fichiers entre eux.

Une vidéo, sa miniature, sa légende et sa story portent le même nom de base.
Ce module sait retrouver ce nom de base quelles que soient les fantaisies
d'extension : « sujet.mp4.jpg », « sujet. », « sujet  » donnent tous « sujet ».
"""

import re
import unicodedata

EXTENSIONS = (".mp4", ".mov", ".m4v", ".avi", ".mkv",
              ".jpg", ".jpeg", ".png", ".webp", ".txt", ".srt")


def base(nom: str) -> str:
    """Nom de référence d'un fichier, débarrassé de ses extensions et de sa ponctuation de fin."""
    n = str(nom)
    change = True
    while change:
        change = False
        n = n.strip()
        while n and n[-1] in ". ":
            n = n[:-1]
            change = True
        bas = n.lower()
        for ext in EXTENSIONS:
            if bas.endswith(ext):
                n = n[: -len(ext)]
                change = True
                bas = n.lower()
    return n


def cle(nom: str) -> str:
    """
    Version comparable d'un nom : sans accents, sans majuscules, sans ponctuation.
    Sert à rapprocher deux fichiers malgré une apostrophe ou un accent manquant.
    """
    n = base(nom)
    n = unicodedata.normalize("NFD", n)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = n.lower()
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return " ".join(n.split())


def meme_sujet(a: str, b: str) -> bool:
    """Deux fichiers parlent-ils de la même vidéo ?"""
    return cle(a) == cle(b)


def est_video(nom_mime: str) -> bool:
    return str(nom_mime or "").startswith("video/")


def est_image(nom_mime: str) -> bool:
    return str(nom_mime or "").startswith("image/")


def est_texte(nom_mime: str) -> bool:
    m = str(nom_mime or "")
    return m == "text/plain" or m == "application/vnd.google-apps.document"
