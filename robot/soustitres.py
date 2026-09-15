# -*- coding: utf-8 -*-
"""
Sous-titres incrustés dans la vidéo.

Style retenu : deux à trois mots à la fois, centrés, un peu sous le menton,
qui changent au rythme de la parole. Le mot fort du groupe passe en dégradé
corail vers ambre.

Sur le robot, les groupes et leur minutage viennent de Whisper.
Ici, la fonction accepte n'importe quelle liste de groupes minutés, ce qui
permet aussi de fabriquer une démonstration sans transcription.
"""

import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter

from . import miniature as M
from . import reglages as R

CORAIL, AMBRE = (0xD6, 0x54, 0x42), (0xEA, 0x9E, 0x68)
IVOIRE = (0xF2, 0xEF, 0xE9)

# mots qui méritent la couleur quand ils apparaissent dans un groupe
MOTS_FORTS = {
    "euros", "mois", "logement", "logements", "conciergerie", "ménage",
    "client", "clients", "propriétaire", "gestion", "commission", "mandat",
    "jamais", "rien", "tout", "seul", "gratuit", "zéro", "argent",
    "réussit", "échoue", "différence", "erreur", "erreurs",
}


def _bande(largeur, hauteur):
    largeur = max(2, largeur)
    bande = Image.new("RGB", (largeur, 1))
    d = ImageDraw.Draw(bande)
    c1, c2 = R.FORT_DEBUT, R.FORT_FIN
    for x in range(largeur):
        k = x / (largeur - 1)
        d.point((x, 0), tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3)))
    return bande.resize((largeur, max(1, hauteur)))


def _degrade_sur_le_mot(masque, largeur, hauteur):
    """
    Le dégradé est calé sur la boîte du mot, pas sur la largeur de l'image :
    sinon le mot n'en traverse qu'une portion et paraît uni.
    """
    boite = masque.getbbox()
    plein = Image.new("RGB", (largeur, hauteur), R.FORT_DEBUT)
    if boite:
        g0, h0, g1, h1 = boite
        plein.paste(_bande(g1 - g0, h1 - h0), (g0, h0))
    return plein


def _serif_italique(taille):
    from PIL import ImageFont
    return ImageFont.truetype(R.POLICE_SERIF_ITALIQUE, taille)


def _calque(groupe, largeur, hauteur, y, taille):
    """Un PNG transparent portant un groupe de mots, centré.

    Les mots ordinaires sont en Inter Bold blanc.
    Le mot fort passe en serif italique, plus gros, en dégradé corail vers ambre,
    exactement comme sur les couvertures de réels.
    """
    im = Image.new("RGBA", (largeur, hauteur), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    mots = groupe.split()

    def est_fort(mot):
        return mot.strip(".,;:!?…»«").lower() in MOTS_FORTS

    def polices(t):
        return M._police("Bold", t), _serif_italique(int(t * R.SOUSTITRES_RATIO_FORT))

    f, f_fort = polices(taille)

    def largeur_totale(fb, ff):
        esp = d.textlength(" ", font=fb)
        return sum(d.textlength(m, font=ff if est_fort(m) else fb) for m in mots) \
            + esp * (len(mots) - 1)

    # on laisse respirer les bords : rien ne s'approche des marges
    while largeur_totale(f, f_fort) > largeur - R.SOUSTITRES_MARGE * 2 and f.size > 34:
        f, f_fort = polices(f.size - 2)

    espace = d.textlength(" ", font=f)
    largeurs = [d.textlength(m, font=f_fort if est_fort(m) else f) for m in mots]
    total = sum(largeurs) + espace * (len(mots) - 1)
    x = (largeur - total) / 2

    m_blanc = Image.new("L", (largeur, hauteur), 0)
    m_fort = Image.new("L", (largeur, hauteur), 0)
    db, df = ImageDraw.Draw(m_blanc), ImageDraw.Draw(m_fort)

    # les deux polices partagent la même ligne de base
    for mot, lg in zip(mots, largeurs):
        if est_fort(mot):
            df.text((x, y), mot, font=f_fort, fill=255, anchor="ls")
        else:
            db.text((x, y), mot, font=f, fill=255, anchor="ls")
        x += lg + espace

    forme = Image.new("L", (largeur, hauteur), 0)
    forme.paste(m_blanc, (0, 0), m_blanc)
    forme.paste(m_fort, (0, 0), m_fort)
    serre = forme.filter(ImageFilter.GaussianBlur(5)).point(lambda v: min(255, int(v * 3.6)))
    large = forme.filter(ImageFilter.GaussianBlur(20)).point(lambda v: min(255, int(v * 2.4)))
    halo = Image.new("L", (largeur, hauteur), 0)
    halo.paste(large, (0, 0))
    halo.paste(serre, (0, 0), serre)

    im.paste((0, 0, 0, 255), (0, 0), halo.point(lambda v: int(v * 0.85)))
    im.paste((255, 255, 255, 255), (0, 0), m_blanc)
    im.paste(_degrade_sur_le_mot(m_fort, largeur, hauteur).convert("RGBA"), (0, 0), m_fort)
    return im


def incruster(video, groupes, sortie, y=None, taille=None):
    """
    groupes : liste de (debut_en_secondes, fin_en_secondes, "deux ou trois mots")
    """
    y = y or R.SOUSTITRES_Y
    taille = taille or R.SOUSTITRES_TAILLE

    info = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", video],
        capture_output=True, text=True, check=True).stdout.strip()
    largeur, hauteur = (int(v) for v in info.split("x"))
    echelle = hauteur / 1920

    dossier = tempfile.mkdtemp(prefix="st_")
    entrees, filtres = ["-i", video], []
    precedent = "0:v"

    for i, (debut, fin, texte) in enumerate(groupes):
        chemin = os.path.join(dossier, f"g{i:03d}.png")
        _calque(texte, largeur, hauteur, int(y * echelle), int(taille * echelle)).save(chemin)
        entrees += ["-i", chemin]
        etiq = f"v{i}"
        filtres.append(
            f"[{precedent}][{i+1}:v]overlay=0:0:enable='between(t,{debut:.2f},{fin:.2f})'[{etiq}]")
        precedent = etiq

    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *entrees,
         "-filter_complex", ";".join(filtres),
         "-map", f"[{precedent}]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", sortie],
        check=True)
    return sortie


def decouper_en_groupes(mots_minutes, par_groupe=3, duree_max=1.2):
    """
    Regroupe des mots minutés (issus de Whisper) par deux ou trois,
    sans jamais laisser un groupe à l'écran plus de `duree_max`.
    """
    groupes, courant = [], []
    for mot in mots_minutes:
        courant.append(mot)
        assez = len(courant) >= par_groupe
        trop_long = courant[-1]["fin"] - courant[0]["debut"] >= duree_max
        ponctue = courant[-1]["mot"].rstrip().endswith((".", "!", "?", ","))
        if assez or trop_long or ponctue:
            groupes.append((courant[0]["debut"], courant[-1]["fin"],
                            " ".join(m["mot"].strip() for m in courant)))
            courant = []
    if courant:
        groupes.append((courant[0]["debut"], courant[-1]["fin"],
                        " ".join(m["mot"].strip() for m in courant)))
    return groupes
