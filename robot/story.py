# -*- coding: utf-8 -*-
"""
La story Instagram.

C'est la vidéo déjà sous-titrée, avec l'appel à l'action posé en bas :
la story sert à faire écrire les gens en message privé, pas à raconter
une seconde fois ce que dit le réel.

Les vidéos trop longues n'ont pas de story : Instagram les découperait.
"""

import hashlib
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter

from . import miniature as M
from . import reglages as R


def choisir_appel(base):
    """
    Toujours le même appel pour une vidéo donnée — on ne veut pas qu'il
    change d'un passage à l'autre — mais pas le même d'une vidéo à l'autre.
    """
    n = int(hashlib.md5(base.encode("utf-8")).hexdigest(), 16)
    return R.APPELS_ACTION[n % len(R.APPELS_ACTION)]


def _calque(texte, largeur, hauteur, y, taille):
    """L'appel à l'action, centré, avec un halo qui le garde lisible sur tout fond."""
    im = Image.new("RGBA", (largeur, hauteur), (0, 0, 0, 0))
    mesureur = ImageDraw.Draw(im)

    f = M._police("Bold", taille)
    dispo = largeur - 2 * R.SOUSTITRES_MARGE
    while mesureur.textlength(texte, font=f) > dispo and f.size > 30:
        f = M._police("Bold", f.size - 2)

    x = (largeur - mesureur.textlength(texte, font=f)) / 2

    masque = Image.new("L", (largeur, hauteur), 0)
    ImageDraw.Draw(masque).text((x, y), texte, font=f, fill=255, anchor="ls")

    serre = masque.filter(ImageFilter.GaussianBlur(5)).point(lambda v: min(255, int(v * 3.6)))
    large = masque.filter(ImageFilter.GaussianBlur(20)).point(lambda v: min(255, int(v * 2.4)))
    halo = Image.new("L", (largeur, hauteur), 0)
    halo.paste(large, (0, 0))
    halo.paste(serre, (0, 0), serre)

    im.paste((0, 0, 0, 255), (0, 0), halo.point(lambda v: int(v * 0.85)))
    im.paste(R.COUVERTURE_IVOIRE + (255,), (0, 0), masque)
    return im


def trop_longue(duree):
    return duree > R.STORY_DUREE_MAX_S


def fabriquer(video, base, sortie):
    """Repose l'appel à l'action sur la vidéo, sans rien toucher d'autre."""
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", video],
        capture_output=True, text=True, check=True).stdout.strip()
    largeur, hauteur = (int(v) for v in info.split("x"))
    echelle = hauteur / 1920

    dossier = tempfile.mkdtemp(prefix="story_")
    calque = os.path.join(dossier, "appel.png")
    _calque(choisir_appel(base), largeur, hauteur,
            int(R.STORY_Y * echelle), int(R.STORY_TAILLE * echelle)).save(calque)

    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", video, "-i", calque,
         "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
         "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", sortie],
        check=True)
    return sortie
