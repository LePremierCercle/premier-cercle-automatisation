# -*- coding: utf-8 -*-
"""
Transcription de la parole, avec Whisper, en local sur le robot.

Rend deux choses :
  - le texte de ce que dit Bilel, corrigé du vocabulaire métier ;
  - le minutage de chaque mot, qui permet de caler les sous-titres.
"""

import os
import re
import subprocess
import tempfile

from . import reglages as R

# Whisper écorche le vocabulaire du métier. On le lui souffle d'avance,
# puis on répare ce qui reste.
LEXIQUE = (
    "Airbnb, Booking, conciergerie, Superhost, check-in, check-out, "
    "location courte durée, mandat de gestion, ménage, blanchisserie, "
    "Le Premier Cercle, Excellence Nettoyage, Mâcon, propriétaire, "
    "commission, rendement, voyageur, logement, linge, consommables."
)

CORRECTIONS = [
    (r"\bair\s*b\s*n\s*b\b", "Airbnb"),
    (r"\bair\s*bnb\b", "Airbnb"),
    (r"\bairbn?b\b", "Airbnb"),
    (r"\bbooking\.?com\b", "Booking"),
    (r"\bconcierge?rie\b", "conciergerie"),
    (r"\bsuper\s*host\b", "Superhost"),
    (r"\bcheck\s*in\b", "check-in"),
    (r"\bcheck\s*out\b", "check-out"),
    (r"\bmacon\b", "Mâcon"),
    (r"\bcourte\s*duree\b", "courte durée"),
]


def _audio(video):
    """Extrait une piste audio légère : la transcription n'a pas besoin de plus."""
    sortie = os.path.join(tempfile.mkdtemp(prefix="son_"), "son.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", video,
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", sortie],
        check=True)
    return sortie


def _corriger(texte):
    for motif, remplacement in CORRECTIONS:
        texte = re.sub(motif, remplacement, texte, flags=re.IGNORECASE)
    return texte


def transcrire(video, modele=None):
    """
    Renvoie {'texte': str, 'mots': [{'mot','debut','fin'}], 'duree': float}
    """
    from faster_whisper import WhisperModel

    modele = modele or R.SOUSTITRES_MODELE
    son = _audio(video)

    moteur = WhisperModel(modele, device="cpu", compute_type="int8")
    segments, info = moteur.transcribe(
        son,
        language="fr",
        word_timestamps=True,
        initial_prompt=LEXIQUE,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
    )

    mots, morceaux = [], []
    for segment in segments:
        morceaux.append(segment.text.strip())
        for mot in (segment.words or []):
            propre = _corriger(mot.word.strip())
            if propre:
                mots.append({"mot": propre, "debut": mot.start, "fin": mot.end})

    texte = _corriger(" ".join(morceaux).strip())
    texte = re.sub(r"\s+", " ", texte)

    try:
        os.remove(son)
    except OSError:
        pass

    return {"texte": texte, "mots": mots, "duree": float(getattr(info, "duration", 0.0))}
