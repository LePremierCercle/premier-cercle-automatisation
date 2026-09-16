# -*- coding: utf-8 -*-
"""
Fabrication de la couverture de réel « Le Premier Cercle ».

Entrée  : une image de n'importe quel format (capture d'écran de téléphone,
          arrêt sur image, photo) + deux lignes de texte.
Sortie  : un JPEG 1080 x 1920, à la charte de Bilel.

MODÈLE VALIDÉ LE 15/09/2026, référence visuelle : le compte @fable5.
Il est écrit en dur ici, il ne doit plus changer sans l'accord de Bilel :
  - format 1080 x 1920 exactement, sinon Instagram ignore la couverture ;
  - tout le texte est CENTRÉ, en partie basse, en deux lignes seulement :
      ligne 1  Inter Bold, blanc ivoire
      ligne 2  Lora Italic, ENTIÈREMENT en dégradé corail vers ambre
    les deux lignes se lisent comme une seule phrase coupée en deux ;
  - sous les deux lignes, la signature : le logo du Premier Cercle dessiné
    en code, puis « LE PREMIER CERCLE » ;
  - AUCUNE pastille, AUCUNE étiquette en haut de l'image ;
  - le dégradé est calé sur la largeur DE LA LIGNE, jamais sur celle de
    l'image, sinon la transition ne se voit pas ;
  - aucune lettre à moins de 100 px des bords : la grille Instagram rogne
    34 px de chaque côté ;
  - léger voile sombre global, accepté POUR CE STYLE uniquement, plus un
    halo doux autour des lettres.
"""

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


def _serif_italique(taille: int) -> ImageFont.FreeTypeFont:
    """
    La deuxième ligne de la couverture est en Lora Italic, jamais en Inter :
    c'est ce qui la distingue de la première (modèle validé).
    """
    return ImageFont.truetype(R.POLICE_SERIF_ITALIQUE, taille)


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

def _bande(largeur: int) -> Image.Image:
    largeur = max(2, largeur)
    bande = Image.new("RGB", (largeur, 1))
    d = ImageDraw.Draw(bande)
    for x in range(largeur):
        k = x / (largeur - 1)
        d.point((x, 0), tuple(int(R.CORAIL[i] + (R.AMBRE[i] - R.CORAIL[i]) * k) for i in range(3)))
    return bande.resize((largeur, 1))


def _degrade_sur_le_mot(masque_fort: Image.Image) -> Image.Image:
    """
    Le dégradé est calé sur la boîte du texte en couleur, pas sur la largeur
    de l'image : sinon, selon l'endroit où tombe le texte, on ne voit jamais
    qu'un bout du dégradé (parfois presque uni).
    """
    plein = Image.new("RGB", (R.LARGEUR, R.HAUTEUR), R.CORAIL)
    boite = masque_fort.getbbox()
    if boite:
        gauche, haut, droite, bas = boite
        bande = _bande(droite - gauche).resize((droite - gauche, bas - haut))
        plein.paste(bande, (gauche, haut))
    return plein


# ------------------------------------------------------------- signature de marque

def _logo(taille: int) -> Image.Image:
    """
    Le symbole « Le Premier Cercle » : un anneau de six arcs (un cercle
    brisé) et un petit anneau central, en dégradé rose vers or. Dessiné en
    code, jamais chargé depuis un fichier, pour rester net à toute taille.
    """
    echelle = 4
    grand = taille * echelle
    masque = Image.new("L", (grand, grand), 0)
    d = ImageDraw.Draw(masque)

    epaisseur = max(2, grand // 14)
    boite_ext = (epaisseur, epaisseur, grand - epaisseur, grand - epaisseur)
    ecart_deg, pas = 18, 360 / 6
    for i in range(6):
        d.arc(boite_ext, i * pas + ecart_deg / 2, (i + 1) * pas - ecart_deg / 2,
              fill=255, width=epaisseur)

    r = grand * 0.24
    cx = cy = grand / 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=255, width=max(2, epaisseur // 2))

    degrade = Image.new("RGB", (grand, grand), R.COUVERTURE_LOGO_ROSE)
    dg = ImageDraw.Draw(degrade)
    for x in range(grand):
        k = x / (grand - 1)
        c = tuple(int(R.COUVERTURE_LOGO_ROSE[i]
                      + (R.COUVERTURE_LOGO_OR[i] - R.COUVERTURE_LOGO_ROSE[i]) * k) for i in range(3))
        dg.line([(x, 0), (x, grand)], fill=c)

    logo = Image.new("RGBA", (grand, grand), (0, 0, 0, 0))
    logo.paste(degrade, (0, 0), masque)
    return logo.resize((taille, taille), Image.LANCZOS)


def _signature(largeur_page: int) -> Image.Image:
    """Le logo suivi de « LE PREMIER CERCLE », centrés comme un seul bloc."""
    f_sig = _police("Bold", R.COUVERTURE_SIGNATURE_TAILLE)
    texte = "LE PREMIER CERCLE"
    mesureur = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    boite_texte = mesureur.textbbox((0, 0), texte, font=f_sig)
    largeur_texte = boite_texte[2] - boite_texte[0]

    logo = _logo(R.COUVERTURE_LOGO_TAILLE)
    largeur_totale = logo.width + R.COUVERTURE_SIGNATURE_ECART + largeur_texte
    x0 = int((largeur_page - largeur_totale) / 2)

    calque = Image.new("RGBA", (largeur_page, logo.height), (0, 0, 0, 0))
    calque.paste(logo, (x0, 0), logo)
    d = ImageDraw.Draw(calque)
    d.text((x0 + logo.width + R.COUVERTURE_SIGNATURE_ECART, logo.height / 2),
           texte, font=f_sig, fill=R.COUVERTURE_IVOIRE + (255,), anchor="lm")
    return calque


# ----------------------------------------------------------------- fabrication

def fabriquer(chemin_source: str, titre, ligne, chute, sortie: str,
              trait_stylo: bool = True) -> str:
    """
    Couverture « Le Premier Cercle », modèle validé le 15/09/2026 :
    tout est centré horizontalement, en deux lignes seulement — une ligne
    blanc ivoire, puis une ligne ENTIÈRE en Lora Italic dégradée — suivies
    de la signature de la marque. Plus de bloc aligné à gauche, plus de
    pastille en haut.

    titre : liste de lignes ; seule la première est gardée, en blanc ivoire
    ligne : liste de morceaux (texte, style) — recomposée en une seule
            phrase, posée entièrement en italique dégradée
    chute : ignorée dans ce modèle, remplacée par la signature de marque
    """
    im = Image.open(chemin_source).convert("RGB")
    im = _rogner_bandes_noires(im)
    im = _recadrer(im)
    im = _retoucher(im)

    ligne_titre = (titre[0] if titre else "").strip()
    ligne_accent = "".join(t for t, _ in ligne).strip()

    f_titre = _police("Bold", R.COUVERTURE_TITRE_TAILLE)
    f_accent = _serif_italique(R.COUVERTURE_ACCENT_TAILLE)

    mesureur = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    largeur_dispo = R.LARGEUR - 2 * R.COUVERTURE_MARGE_SECURITE

    def largeur_texte(t, f):
        b = mesureur.textbbox((0, 0), t, font=f)
        return b[2] - b[0]

    while (largeur_texte(ligne_titre, f_titre) > largeur_dispo
           or largeur_texte(ligne_accent, f_accent) > largeur_dispo) and f_titre.size > 56:
        f_titre = _police("Bold", f_titre.size - 2)
        f_accent = _serif_italique(max(56, f_accent.size - 2))

    masque_blanc = Image.new("L", (R.LARGEUR, R.HAUTEUR), 0)
    masque_fort = Image.new("L", (R.LARGEUR, R.HAUTEUR), 0)
    d_blanc = ImageDraw.Draw(masque_blanc)
    d_fort = ImageDraw.Draw(masque_fort)

    y_titre = R.COUVERTURE_TITRE_HAUT
    x_titre = (R.LARGEUR - largeur_texte(ligne_titre, f_titre)) / 2
    d_blanc.text((x_titre, y_titre), ligne_titre, font=f_titre, fill=255, anchor="la")

    ecart = int(R.COUVERTURE_TITRE_TAILLE * R.COUVERTURE_SERRAGE)
    y_accent = y_titre + ecart
    x_accent = (R.LARGEUR - largeur_texte(ligne_accent, f_accent)) / 2
    d_fort.text((x_accent, y_accent), ligne_accent, font=f_accent, fill=255, anchor="la")

    boite_accent = mesureur.textbbox((x_accent, y_accent), ligne_accent, font=f_accent, anchor="la")
    y_signature = boite_accent[3] + 46

    # halo doux autour des lettres, plus un léger voile global — accepté
    # uniquement pour ce style, exception à la règle « aucun voile sombre ».
    forme = Image.new("L", (R.LARGEUR, R.HAUTEUR), 0)
    forme.paste(masque_blanc, (0, 0), masque_blanc)
    forme.paste(masque_fort, (0, 0), masque_fort)

    serre = forme.filter(ImageFilter.GaussianBlur(5)).point(lambda v: min(255, int(v * 3.4)))
    large = forme.filter(ImageFilter.GaussianBlur(20)).point(lambda v: min(255, int(v * 2.2)))
    halo = Image.new("L", (R.LARGEUR, R.HAUTEUR), 0)
    halo.paste(large, (0, 0))
    halo.paste(serre, (0, 0), serre)

    sortie_im = im.convert("RGBA")
    noir = Image.new("RGBA", (R.LARGEUR, R.HAUTEUR), (0, 0, 0, 255))
    voile = Image.new("L", (R.LARGEUR, R.HAUTEUR), int(255 * R.COUVERTURE_ASSOMBRISSEMENT))
    sortie_im = Image.composite(noir, sortie_im, voile)
    sortie_im = Image.composite(noir, sortie_im, halo.point(lambda v: min(255, int(v * 0.65))))

    sortie_im.paste(R.COUVERTURE_IVOIRE + (255,), (0, 0), masque_blanc)
    sortie_im.paste(_degrade_sur_le_mot(masque_fort).convert("RGBA"), (0, 0), masque_fort)

    signature = _signature(R.LARGEUR)
    sortie_im.alpha_composite(signature, (0, int(y_signature)))

    sortie_im.convert("RGB").save(sortie, quality=92, optimize=True, subsampling=0)

    # le texte réellement posé, pour le contrôle automatique
    boite = forme.getbbox()
    bas_reel = int(y_signature + signature.height)
    _DERNIER_TEXTE.clear()
    _DERNIER_TEXTE.update({"boite": boite, "bas_reel": bas_reel})
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

    bas_reel = _DERNIER_TEXTE.get("bas_reel")
    if boite:
        gauche, _, droite, bas = boite
        etat.update({
            "marge_gauche": gauche,
            "marge_droite": l - droite,
            "bas_du_texte": bas_reel if bas_reel is not None else bas,
            "marge_gauche_ok": gauche >= R.COUVERTURE_MARGE_SECURITE - 2,
            "marge_droite_ok": (l - droite) >= R.COUVERTURE_MARGE_SECURITE - 2,
            "bas_ok": (bas_reel if bas_reel is not None else bas) <= R.COUVERTURE_BAS_MAX,
        })

    etat["valide"] = all(v for k, v in etat.items() if k.endswith("_ok"))
    return etat
