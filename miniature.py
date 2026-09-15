# -*- coding: utf-8 -*-
"""
Fabrication de la miniature (couverture de réel).

Entrée  : une image de n'importe quel format (capture d'écran de téléphone,
          arrêt sur image, photo) + un texte en trois parties.
Sortie  : un JPEG 1080 x 1920, à la charte de Bilel.

Règles non négociables, issues de ses retours :
  - format 1080 x 1920 exactement, sinon Instagram ignore la couverture ;
  - marge gauche 95 px minimum, le bloc de texte s'arrête à 1250 px ;
  - AUCUN fond noir, AUCUN voile sombre, AUCUN dégradé assombri :
    la photo reste pleine et intacte, seul un halo doux autour des lettres
    assure la lisibilité ;
  - mots forts en dégradé corail vers ambre, jamais en aplat uni ;
  - police Inter, jamais de substitut.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

from . import reglages as R

# ----------------------------------------------------------------- polices

_DOSSIERS_POLICES = [
    os.path.expanduser("~/.fonts/inter/extras/otf"),
    os.path.expanduser("~/.fonts/inter/extras/ttf"),
    "/usr/share/fonts/truetype/inter",
]


def _police(graisse: str, taille: int) -> ImageFont.FreeTypeFont:
    noms = [f"Inter-{graisse}.otf", f"Inter-{graisse}.ttf"]
    for dossier in _DOSSIERS_POLICES:
        for nom in noms:
            chemin = os.path.join(dossier, nom)
            if os.path.exists(chemin):
                return ImageFont.truetype(chemin, taille)
    raise FileNotFoundError(
        "Police Inter introuvable. Le robot doit l'installer avant de fabriquer une miniature."
    )


# ----------------------------------------------------------------- préparation du fond

def _rogner_bandes_noires(im: Image.Image) -> Image.Image:
    """Enlève les bandes noires d'un export ou d'une capture, en deux passes."""
    for _ in range(2):
        gris = im.convert("L")
        l, h = gris.size
        px = gris.load()

        def ligne_noire(y):
            noirs = sum(1 for x in range(0, l, max(1, l // 120)) if px[x, y] < 26)
            return noirs / max(1, len(range(0, l, max(1, l // 120)))) > 0.55

        def colonne_noire(x):
            noirs = sum(1 for y in range(0, h, max(1, h // 120)) if px[x, y] < 26)
            return noirs / max(1, len(range(0, h, max(1, h // 120)))) > 0.55

        haut = 0
        while haut < h - 1 and ligne_noire(haut):
            haut += 1
        bas = h - 1
        while bas > haut + 1 and ligne_noire(bas):
            bas -= 1
        gauche = 0
        while gauche < l - 1 and colonne_noire(gauche):
            gauche += 1
        droite = l - 1
        while droite > gauche + 1 and colonne_noire(droite):
            droite -= 1

        if (gauche, haut, droite, bas) == (0, 0, l - 1, h - 1):
            break
        im = im.crop((gauche, haut, droite + 1, bas + 1))
    return im


def _centre_du_visage(im: Image.Image):
    """Position horizontale du visage, entre 0 et 1. Renvoie None si aucun visage."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    gris = cv2.cvtColor(np.array(im.convert("RGB")), cv2.COLOR_RGB2GRAY)
    base = cv2.data.haarcascades
    for fichier in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
        cascade = cv2.CascadeClassifier(base + fichier)
        visages = cascade.detectMultiScale(gris, 1.15, 5, minSize=(60, 60))
        if len(visages):
            x, y, w, h = max(visages, key=lambda v: v[2] * v[3])
            return (x + w / 2) / im.width
    return None


def _recadrer(im: Image.Image) -> Image.Image:
    """Recadrage plein cadre en 1080 x 1920, centré sur le visage s'il y en a un."""
    cible = R.LARGEUR / R.HAUTEUR
    actuel = im.width / im.height

    if actuel > cible:
        # image trop large : on coupe sur les côtés
        largeur = int(im.height * cible)
        centre = _centre_du_visage(im)
        milieu = int((centre if centre is not None else 0.5) * im.width)
        gauche = max(0, min(im.width - largeur, milieu - largeur // 2))
        im = im.crop((gauche, 0, gauche + largeur, im.height))
    elif actuel < cible:
        # image trop haute : on coupe en haut et en bas, un peu plus en bas
        hauteur = int(im.width / cible)
        haut = max(0, min(im.height - hauteur, int((im.height - hauteur) * 0.40)))
        im = im.crop((0, haut, im.width, haut + hauteur))

    return im.resize((R.LARGEUR, R.HAUTEUR), Image.LANCZOS)


def _retoucher(im: Image.Image) -> Image.Image:
    im = ImageEnhance.Brightness(im).enhance(R.LUMINOSITE)
    im = ImageEnhance.Contrast(im).enhance(R.CONTRASTE)
    im = ImageEnhance.Color(im).enhance(R.SATURATION)
    return im.filter(ImageFilter.UnsharpMask(radius=2, percent=R.NETTETE, threshold=3))


# ----------------------------------------------------------------- dégradé

def _degrade() -> Image.Image:
    bande = Image.new("RGB", (R.LARGEUR, 1))
    d = ImageDraw.Draw(bande)
    for x in range(R.LARGEUR):
        k = x / (R.LARGEUR - 1)
        d.point((x, 0), tuple(int(R.CORAIL[i] + (R.AMBRE[i] - R.CORAIL[i]) * k) for i in range(3)))
    return bande.resize((R.LARGEUR, R.HAUTEUR))


# ----------------------------------------------------------------- fabrication

def fabriquer(chemin_source: str, titre, ligne, chute, sortie: str,
              trait_stylo: bool = True) -> str:
    """
    titre : liste de 1 à 2 lignes, en gras
    ligne : liste de morceaux (texte, "blanc" ou "fort")
    chute : liste de 1 à 2 lignes, détachées
    """
    im = Image.open(chemin_source).convert("RGB")
    im = _rogner_bandes_noires(im)
    im = _recadrer(im)
    im = _retoucher(im)

    f_titre = _police("Bold", R.TAILLE_TITRE)
    f_reg = _police("Regular", R.TAILLE_TEXTE)
    f_gras = _police("Bold", R.TAILLE_FORT)

    mesureur = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def mesure(t, f):
        b = mesureur.textbbox((0, 0), t, font=f)
        return b, b[2] - b[0], b[3] - b[1]

    largeur_dispo = R.LARGEUR - 2 * R.MARGE_GAUCHE

    # on réduit le texte plutôt que de laisser déborder
    while True:
        trop_large = any(mesure(t, f_titre)[1] > largeur_dispo for t in titre)
        trop_large = trop_large or sum(mesure(t, f_gras if s == "fort" else f_reg)[1]
                                       for t, s in ligne) > largeur_dispo
        trop_large = trop_large or any(mesure(t, f_reg)[1] > largeur_dispo for t in chute)
        if not trop_large or f_titre.size <= 56:
            break
        f_titre = _police("Bold", f_titre.size - 2)
        f_reg = _police("Regular", max(40, f_reg.size - 2))
        f_gras = _police("Bold", max(46, f_gras.size - 2))

    # Tout est posé sur des lignes de base régulières : l'écart entre deux lignes
    # ne dépend plus des lettres écrites, il est constant et réglable.
    def pas(f):
        m, d = f.getmetrics()
        return int((m + d) * R.INTERLIGNE)

    montee = max(f_reg.getmetrics()[0], f_gras.getmetrics()[0])
    descente = max(f_reg.getmetrics()[1], f_gras.getmetrics()[1])

    pas_titre = pas(f_titre)
    pas_chute = pas(f_reg)
    h_ligne = montee + descente
    ESP_BLOC, SOUS = R.ESPACE_ENTRE_BLOCS, 24

    # hauteur exacte : on compte la descente de la toute dernière ligne
    montee_chute, descente_chute = f_reg.getmetrics()
    bloc = (pas_titre * len(titre)
            + ESP_BLOC + h_ligne + SOUS
            + ESP_BLOC + montee_chute + pas_chute * (len(chute) - 1) + descente_chute)
    y = R.BAS_DU_TEXTE - bloc

    masque_blanc = Image.new("L", (R.LARGEUR, R.HAUTEUR), 0)
    masque_fort = Image.new("L", (R.LARGEUR, R.HAUTEUR), 0)
    d_blanc = ImageDraw.Draw(masque_blanc)
    d_fort = ImageDraw.Draw(masque_fort)

    base = y + f_titre.getmetrics()[0]
    for t in titre:
        d_blanc.text((R.MARGE_GAUCHE, base), t, font=f_titre, fill=255, anchor="ls")
        base += pas_titre
    y = base - f_titre.getmetrics()[0] + ESP_BLOC

    # les deux tailles de la ligne partagent la même ligne de base
    x = R.MARGE_GAUCHE
    base_commune = y + montee
    x_fort = None
    for t, style in ligne:
        f = f_gras if style == "fort" else f_reg
        larg = mesureur.textlength(t, font=f)
        cible = d_fort if style == "fort" else d_blanc
        cible.text((x, base_commune), t, font=f, fill=255, anchor="ls")
        if style == "fort" and x_fort is None:
            x_fort = (x, x + larg)
        x += larg
    y += h_ligne + SOUS

    if x_fort:
        trait = Image.new("L", (R.LARGEUR, R.HAUTEUR), 0)
        dt = ImageDraw.Draw(trait)
        y_trait = base_commune + 16
        x0, x1 = x_fort
        if trait_stylo:
            pts = []
            n = 60
            for i in range(n + 1):
                k = i / n
                pts.append((x0 + (x1 - x0) * k,
                            y_trait - math.sin(k * math.pi) * 3,
                            2 + 5 * math.sin(k * math.pi)))
            for i in range(n):
                ep = int((pts[i][2] + pts[i + 1][2]) / 2)
                dt.line([pts[i][:2], pts[i + 1][:2]], fill=255, width=max(2, ep))
        else:
            dt.line([(x0, y_trait), (x1, y_trait)], fill=255, width=6)
        masque_fort.paste(255, (0, 0), trait)

    y += ESP_BLOC
    base = y + f_reg.getmetrics()[0]
    for t in chute:
        d_blanc.text((R.MARGE_GAUCHE, base), t, font=f_reg, fill=255, anchor="ls")
        base += pas_chute

    # halo doux autour des lettres — jamais de bandeau ni de voile sur la photo.
    # Sa densité s'adapte : plus le fond derrière le texte est clair, plus il est marqué.
    forme = Image.new("L", (R.LARGEUR, R.HAUTEUR), 0)
    forme.paste(masque_blanc, (0, 0), masque_blanc)
    forme.paste(masque_fort, (0, 0), masque_fort)

    boite = forme.getbbox()
    if boite:
        zone = im.convert("L").crop(boite)
        clarte = sum(zone.getdata()) / max(1, len(zone.getdata()))
    else:
        clarte = 128
    # fond sombre (40) -> halo léger ; fond très clair (200) -> halo dense
    densite = min(0.92, max(0.55, 0.50 + clarte / 320))

    serre = forme.filter(ImageFilter.GaussianBlur(5)).point(lambda v: min(255, int(v * 3.4)))
    large = forme.filter(ImageFilter.GaussianBlur(20)).point(lambda v: min(255, int(v * 2.3)))
    halo = Image.new("L", (R.LARGEUR, R.HAUTEUR), 0)
    halo.paste(large, (0, 0))
    halo.paste(serre, (0, 0), serre)

    sortie_im = im.convert("RGBA")
    noir = Image.new("RGBA", (R.LARGEUR, R.HAUTEUR), (0, 0, 0, 255))
    sortie_im = Image.composite(noir, sortie_im, halo.point(lambda v: int(v * densite)))
    sortie_im.paste((255, 255, 255, 255), (0, 0), masque_blanc)
    sortie_im.paste(_degrade().convert("RGBA"), (0, 0), masque_fort)

    sortie_im.convert("RGB").save(sortie, quality=92, optimize=True, subsampling=0)

    # le texte réellement posé, pour le contrôle automatique
    _DERNIER_TEXTE.clear()
    _DERNIER_TEXTE.update({"boite": boite, "clarte": round(clarte, 1), "densite": round(densite, 2)})
    return sortie


_DERNIER_TEXTE = {}


def controler(chemin: str) -> dict:
    """
    Contrôle automatique avant dépôt.
    Refuse tout ce qui a déjà posé problème sur la grille Instagram.
    """
    im = Image.open(chemin)
    l, h = im.size
    ratio = l / h
    boite = _DERNIER_TEXTE.get("boite")

    etat = {
        "dimensions": (l, h),
        "taille_ko": round(os.path.getsize(chemin) / 1024),
        "format_ok": abs(ratio - R.RATIO_ATTENDU) <= R.RATIO_TOLERANCE,
    }

    if boite:
        gauche, _, droite, bas = boite
        etat.update({
            "marge_gauche": gauche,
            "marge_droite": l - droite,
            "bas_du_texte": bas,
            "marge_gauche_ok": gauche >= R.MARGE_GAUCHE - 2,
            "marge_droite_ok": (l - droite) >= 60,      # 34 px rognés par la grille + sécurité
            "bas_ok": bas <= R.BAS_DU_TEXTE + 2,
        })

    etat["valide"] = all(v for k, v in etat.items() if k.endswith("_ok"))
    return etat
