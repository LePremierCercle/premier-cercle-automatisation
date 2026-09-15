# -*- coding: utf-8 -*-
"""
Logo « Le Premier Cercle », dessiné en code.

Anneau de six arcs séparés par des fentes, plus un anneau plein au centre.
Dégradé or rose, conforme à la charte.

Il est dessiné, jamais chargé depuis un fichier : il reste net à toutes
les tailles et le robot n'a aucun fichier à transporter.
"""

from PIL import Image, ImageDraw, ImageFont

OR_CLAIR = (0xE8, 0xB5, 0x84)
OR_FONCE = (0x9C, 0x5F, 0x33)
IVOIRE = (0xF2, 0xEF, 0xE9)

# six arcs, avec une fente entre chacun
_FENTE = 7  # degrés
_ARCS = [(a + _FENTE, a + 60 - _FENTE) for a in range(0, 360, 60)]


def _degrade_dore(taille):
    bande = Image.new("RGB", (taille, 1))
    d = ImageDraw.Draw(bande)
    for x in range(taille):
        k = x / max(1, taille - 1)
        # or foncé -> or clair -> or moyen, comme la charte
        if k < 0.45:
            t = k / 0.45
            c = tuple(int(OR_FONCE[i] + (OR_CLAIR[i] - OR_FONCE[i]) * t) for i in range(3))
        else:
            t = (k - 0.45) / 0.55
            fin = (0xBE, 0x7F, 0x4E)
            c = tuple(int(OR_CLAIR[i] + (fin[i] - OR_CLAIR[i]) * t) for i in range(3))
        d.point((x, 0), c)
    return bande.resize((taille, taille))


def marque(taille=180, epaisseur=None):
    """Le symbole seul, sur fond transparent."""
    e = epaisseur or max(4, taille // 18)
    sur = 4                      # dessin en plus grand puis réduction, pour des bords nets
    t = taille * sur
    ep = e * sur

    masque = Image.new("L", (t, t), 0)
    d = ImageDraw.Draw(masque)

    marge = ep // 2 + 2
    boite = (marge, marge, t - marge, t - marge)
    for debut, fin in _ARCS:
        d.arc(boite, debut, fin, fill=255, width=ep)

    # anneau central
    r = t * 0.17
    c = t / 2
    d.ellipse((c - r, c - r, c + r, c + r), outline=255, width=int(ep * 1.5))

    masque = masque.resize((taille, taille), Image.LANCZOS)
    image = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    image.paste(_degrade_dore(taille).convert("RGBA"), (0, 0), masque)
    return image


def signature(police_titre, police_bas, hauteur_marque=86,
              titre="LE PREMIER CERCLE", bas="CONCIERGERIE & NETTOYAGE",
              couleur=IVOIRE):
    """Le symbole suivi du nom, en une bande horizontale sur fond transparent."""
    m = marque(hauteur_marque)
    mes = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    l_titre = mes.textlength(titre, font=police_titre)
    l_bas = mes.textlength(bas, font=police_bas) if bas else 0

    ecart = hauteur_marque // 4
    largeur = int(hauteur_marque + ecart + max(l_titre, l_bas)) + 4
    image = Image.new("RGBA", (largeur, hauteur_marque), (0, 0, 0, 0))
    image.paste(m, (0, 0), m)

    d = ImageDraw.Draw(image)
    x = hauteur_marque + ecart
    if bas:
        d.text((x, hauteur_marque * 0.44), titre, font=police_titre, fill=couleur, anchor="ls")
        d.text((x, hauteur_marque * 0.88), bas, font=police_bas, fill=couleur + (170,), anchor="ls")
    else:
        d.text((x, hauteur_marque * 0.68), titre, font=police_titre, fill=couleur, anchor="ls")
    return image
