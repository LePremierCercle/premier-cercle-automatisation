# -*- coding: utf-8 -*-
"""
Boîte à outils du motion design « Le Premier Cercle » (charte or rose sur nuit).
Reprise du montage de la VSL validé le 13/09/2026.
"""

import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30
NUIT, IVOIRE, GRIS = (15, 17, 21), (242, 239, 233), (138, 142, 150)
OR, OR_CL, ETEINT = (201, 136, 79), (240, 198, 156), (74, 78, 88)

_PISTES = [os.path.expanduser("~/.fonts/inter/extras/ttf"),
           os.path.expanduser("~/.fonts/inter/extras/otf")]
D = next((p for p in _PISTES if os.path.exists(os.path.join(p, "Inter-Bold.ttf"))
          or os.path.exists(os.path.join(p, "Inter-Bold.otf"))), _PISTES[0])
_EXT = ".ttf" if os.path.exists(os.path.join(D, "Inter-Bold.ttf")) else ".otf"
_CACHE_POLICES = {}


def _police(nom, taille):
    cle = (nom, taille)
    if cle not in _CACHE_POLICES:
        _CACHE_POLICES[cle] = ImageFont.truetype(os.path.join(D, "Inter-%s%s" % (nom, _EXT)), taille)
    return _CACHE_POLICES[cle]


def fb(s): return _police("Bold", s)
def fr(s): return _police("Regular", s)


_m = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def borne(t): return max(0.0, min(1.0, t))
def ph(t, a, b): return borne((t - a) / (b - a)) if b > a else 0.0
def cub(t): return 1 - (1 - t) ** 3
def back(t):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
def inout(t): return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


# ------------------------------------------------------------- fond animé
hw, hh = W // 2, H // 2
yy, xx = np.mgrid[0:hh, 0:hw].astype(np.float32)
_FOND_CACHE = {}


def fond(t):
    """halos dorés qui dérivent lentement ; calculé au dixième de seconde et réutilisé."""
    cle = round(t * 10)
    if cle in _FOND_CACHE:
        return _FOND_CACHE[cle]
    t = cle / 10.0
    base = np.zeros((hh, hw, 3), np.float32); base[:] = NUIT
    for (cx0, cy0, ax, ay, r, force, coul) in (
            (0.34, 0.28, 0.11, 0.06, 0.58, 0.20, OR),
            (0.72, 0.68, 0.09, 0.08, 0.46, 0.11, OR_CL)):
        cx = (cx0 + ax * math.sin(t * 0.5 + cx0 * 9)) * hw
        cy = (cy0 + ay * math.cos(t * 0.38 + cy0 * 7)) * hh
        d2 = ((xx - cx) ** 2 + (yy - cy) ** 2) / ((r * hw) ** 2)
        halo = np.exp(-d2) * force
        for k in range(3):
            base[:, :, k] += halo * coul[k]
    np.clip(base, 0, 255, out=base)
    im = Image.fromarray(base.astype(np.uint8)).resize((W, H), Image.BILINEAR).convert("RGBA")
    anneau_fantome(im, t); particules(im, t)
    if len(_FOND_CACHE) > 40:
        _FOND_CACHE.clear()
    _FOND_CACHE[cle] = im
    return im


rng = np.random.RandomState(7)
PARTS = [(rng.rand(), rng.rand(), 3 + rng.rand() * 7, 0.010 + rng.rand() * 0.022, rng.rand() * 6.28, rng.rand()) for _ in range(46)]
GRAINS = [rng.normal(0, 1, (H, W, 1)).astype(np.float32) for _ in range(6)]
_vx, _vy = np.meshgrid(np.linspace(-1, 1, W, dtype=np.float32), np.linspace(-1, 1, H, dtype=np.float32))
VIGNETTE = (1 - 0.32 * np.clip((_vx ** 2 * 0.9 + _vy ** 2 * 0.55) - 0.25, 0, 1))[:, :, None].astype(np.float32)


def anneau_fantome(im, t):
    r = 470; cx, cy = W // 2, H // 2; rot = t * 4.0
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    box = [cx - r, cy - r, cx + r, cy + r]
    for i in range(6):
        a0 = -90 + i * 60 + 6 + rot
        d.arc(box, a0, a0 + 48, fill=OR + (26,), width=3)
    r2 = int(r * 0.41)
    d.arc([cx - r2, cy - r2, cx + r2, cy + r2], 0, 360, fill=OR + (14,), width=2)
    im.alpha_composite(c)


def particules(im, t):
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    for (x0, y0, r, v, ph0, z) in PARTS:
        y = (y0 - t * v) % 1.15 - 0.075
        x = x0 + 0.012 * math.sin(t * 0.7 + ph0)
        px, py = x * W, y * H
        a = int((38 + 70 * z) * (0.6 + 0.4 * math.sin(t * 1.3 + ph0)))
        d.ellipse([px - r, py - r, px + r, py + r], fill=OR_CL + (a,))
    im.alpha_composite(c.filter(ImageFilter.GaussianBlur(2.2)))


def finition(im, i):
    """grain cinéma + vignettage, sur l'image RGB finale."""
    a = np.asarray(im).astype(np.float32)
    a = a * VIGNETTE + GRAINS[i % 6] * 3.0
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def balayage(im, t, t0, duree=0.32):
    u = ph(t, t0, t0 + duree)
    if u <= 0 or u >= 1: return
    x = int(-260 + (W + 520) * inout(u)); a = int(255 * (1 - abs(2 * u - 1)) ** 0.5)
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    for (w, al) in ((3, a), (14, int(a * 0.45)), (40, int(a * 0.16))):
        d.line([(x - 230, H * 0.52), (x + 230, H * 0.48)], fill=OR_CL + (al,), width=w)
    im.alpha_composite(c)


# ------------------------------------------------------------- briques
def lueur(im, calque, rayon=38, force=0.75):
    """calque + son halo. Le flou n'est calculé que sur la boîte utile."""
    boite = calque.getbbox()
    if not boite:
        return
    x0, y0, x1, y1 = boite
    m = rayon * 3
    x0, y0 = max(0, x0 - m), max(0, y0 - m)
    x1, y1 = min(calque.width, x1 + m), min(calque.height, y1 + m)
    morceau = calque.crop((x0, y0, x1, y1))
    halo = morceau.filter(ImageFilter.GaussianBlur(rayon))
    halo.putalpha(halo.split()[3].point(lambda v: int(v * force)))
    im.alpha_composite(halo, (x0, y0))
    im.alpha_composite(morceau, (x0, y0))


_VOILES = {}


def voile_or(lw, lh):
    cle = (lw, lh)
    if cle not in _VOILES:
        g = Image.new("RGB", (lw, lh)); dg = ImageDraw.Draw(g)
        for x in range(lw):
            u = x / max(1, lw - 1)
            dg.line([(x, 0), (x, lh)], fill=tuple(int(OR[i] + (OR_CL[i] - OR[i]) * u) for i in range(3)))
        if len(_VOILES) > 60:
            _VOILES.clear()
        _VOILES[cle] = g
    return _VOILES[cle]


def txt_or(im, xy, s, font, alpha=255):
    if alpha <= 2: return
    lw = int(_m.textlength(s, font=font)) + 6; lh = int(font.size * 1.9)
    m = Image.new("L", (lw, lh), 0); ImageDraw.Draw(m).text((0, 0), s, font=font, fill=alpha)
    g = voile_or(lw, lh).convert("RGBA"); g.putalpha(m)
    im.alpha_composite(g, (int(xy[0]), int(xy[1])))


def carte(w, h, r, fond_c, bord=None, ep=3):
    c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(c).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=fond_c, outline=bord, width=ep if bord else 0)
    return c


def flash(im, p, force=140):
    if p <= 0 or p >= 1: return
    v = int(force * (1 - p) ** 2)
    if v <= 1: return
    im.alpha_composite(Image.new("RGBA", (W, H), (255, 240, 225, v)))


def texte(im, x, y, s, font, coul=IVOIRE, a=255, or_=False, centre_x=False):
    if a <= 2: return
    if centre_x: x = x - _m.textlength(s, font=font) / 2
    if or_: txt_or(im, (x, y), s, font, a)
    else: ImageDraw.Draw(im, "RGBA").text((x, y), s, font=font, fill=coul + (a,))


def ajuste(s, taille, maxw, gras=True):
    f = fb(taille) if gras else fr(taille)
    while _m.textlength(s, font=f) > maxw and f.size > 16:
        f = fb(f.size - 1) if gras else fr(f.size - 1)
    return f


def calque_carte(w, h, lignes, r=26, x0=34):
    c = carte(w, h, r, (22, 24, 30, 236), OR + (200,), 2)
    for (s, f, coul, dy) in lignes:
        if coul == "or": txt_or(c, (x0, dy), s, f, 255)
        else: ImageDraw.Draw(c, "RGBA").text((x0, dy), s, font=f, fill=coul + (255,))
    return c


def poser(im, calque, x, y, p, out=1.0, glisse=70, halo=0.45):
    if p <= 0 or out <= 0: return
    e = back(min(1, p * 1.5)); so = inout(out)
    ech = (0.84 + 0.16 * e) * (0.94 + 0.06 * so)
    a = int(255 * min(1, p * 2.5) * so)
    c = calque
    if ech != 1.0:
        c = c.resize((max(1, int(c.width * ech)), max(1, int(c.height * ech))), Image.LANCZOS)
    if a < 255:
        c = c.copy(); c.putalpha(c.split()[3].point(lambda v: int(v * a / 255)))
    dx = int(glisse * (1 - e)); dy = int(-30 * (1 - so))
    cal = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cal.alpha_composite(c, (int(x + dx + (calque.width - c.width) / 2), int(y + dy + (calque.height - c.height) / 2)))
    if halo > 0: lueur(im, cal, 30, halo)
    else: im.alpha_composite(cal)


def coche(im, cx, cy, a, r=26, p=1.0):
    if a <= 2 or p <= 0: return
    m = Image.new("L", (W, H), 0); md = ImageDraw.Draw(m)
    md.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * min(1, p * 1.4), fill=a, width=4)
    q = borne((p - 0.4) / 0.6)
    if q > 0:
        md.line([cx - 11, cy + 1, cx - 11 + 8 * min(1, q * 2), cy + 1 + 9 * min(1, q * 2)], fill=a, width=5)
        if q > 0.5: md.line([cx - 3, cy + 10, cx - 3 + 16 * (q - 0.5) * 2, cy + 10 - 20 * (q - 0.5) * 2], fill=a, width=5)
    g = voile_or(W, H).convert("RGBA"); g.putalpha(m); lueur(im, g, 14, 0.5)


def logo_petit(im, x, y, r=26, a=170, baseline="CONCIERGERIE AIRBNB"):
    if a <= 2: return
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    box = [x - r, y - r, x + r, y + r]
    for i in range(6):
        a0 = -90 + i * 60 + 6; d.arc(box, a0, a0 + 48, fill=(OR_CL if i == 0 else ETEINT) + (a,), width=4)
    ri = int(r * 0.41); d.arc([x - ri, y - ri, x + ri, y + ri], 0, 360, fill=OR_CL + (a,), width=6)
    d.text((x + r + 16, y - 14), "LE PREMIER CERCLE", font=fb(22), fill=IVOIRE + (a,))
    d.text((x + r + 17, y + 12), " ".join(baseline), font=fr(12), fill=GRIS + (a,))
    im.alpha_composite(c)


def punch_x(im, s, font, cx, y, p, coul=IVOIRE, or_mot=None, out=1.0, maxw=None):
    if p <= 0 or out <= 0: return
    if maxw:
        tw = _m.textlength(s, font=font)
        if tw > maxw: font = fb(max(20, int(font.size * maxw / tw)))
    e = back(min(1.0, p * 1.9)); so = inout(out)
    ech = (0.55 + 0.45 * e) * (0.90 + 0.10 * so); y = y - 46 * (1 - so)
    a = int(255 * min(1.0, p * 3.2) * so)
    lw = int(_m.textlength(s, font=font)) + 12; lh = int(font.size * 1.7)
    cal = Image.new("RGBA", (lw, lh), (0, 0, 0, 0)); dd = ImageDraw.Draw(cal, "RGBA")
    if or_mot and or_mot in s:
        i = s.index(or_mot); av = s[:i]
        dd.text((6, 0), av, font=font, fill=coul + (a,)); x = 6 + _m.textlength(av, font=font)
        m = Image.new("L", (lw, lh), 0); ImageDraw.Draw(m).text((x, 0), or_mot, font=font, fill=a)
        g = voile_or(lw, lh).convert("RGBA"); g.putalpha(m); cal.alpha_composite(g)
        x += _m.textlength(or_mot, font=font); dd.text((x, 0), s[i + len(or_mot):], font=font, fill=coul + (a,))
    else: dd.text((6, 0), s, font=font, fill=coul + (a,))
    nw, nh = max(1, int(lw * ech)), max(1, int(lh * ech))
    cal = cal.resize((nw, nh), Image.LANCZOS)
    im.alpha_composite(cal, (int(cx - nw / 2), int(y - (nh - lh) / 2)))


def voile_bas(im, a, y0=780):
    if a <= 2: return
    g = Image.new("L", (1, H), 0); d = ImageDraw.Draw(g)
    for y in range(H): d.point((0, y), fill=int(255 * borne((y - y0) / 200) ** 1.2))
    v = Image.new("RGBA", (W, H), NUIT + (255,)); v.putalpha(g.resize((W, H)).point(lambda v: int(v * a / 255)))
    im.alpha_composite(v)


def mot_cle(im, s, t, t0, duree=1.6, y=930, taille=64, or_mot=None, cx=None, maxw=None, voile=False):
    p = ph(t, t0, t0 + 0.35); out = 1 - ph(t, t0 + duree - 0.3, t0 + duree)
    if p <= 0 or out <= 0: return
    if voile: voile_bas(im, int(130 * min(1, p * 2) * out), 800)
    if cx is None: cx = W / 2
    punch_x(im, s, fb(taille), cx, y, p, out=out, or_mot=or_mot, maxw=maxw)
    flash(im, ph(t, t0, t0 + 0.3), 45)


def icone(nom, taille=64):
    m = Image.new("L", (taille, taille), 0); d = ImageDraw.Draw(m); s = taille
    if nom == "maison":
        d.polygon([(s * .5, s * .08), (s * .95, s * .48), (s * .05, s * .48)], fill=255)
        d.rectangle([s * .18, s * .48, s * .82, s * .92], fill=255)
        d.rectangle([s * .42, s * .62, s * .58, s * .92], fill=0)
    elif nom == "globe":
        d.ellipse([s * .06, s * .06, s * .94, s * .94], outline=255, width=int(s * .07))
        d.ellipse([s * .30, s * .06, s * .70, s * .94], outline=255, width=int(s * .06))
        d.line([s * .06, s * .5, s * .94, s * .5], fill=255, width=int(s * .06))
        d.line([s * .12, s * .3, s * .88, s * .3], fill=255, width=int(s * .05))
        d.line([s * .12, s * .7, s * .88, s * .7], fill=255, width=int(s * .05))
    elif nom == "euro":
        f = fb(int(s * .95))
        w = _m.textlength("€", font=f); d.text(((s - w) / 2, -s * .12), "€", font=f, fill=255)
    elif nom == "cle":
        d.ellipse([s * .08, s * .3, s * .48, s * .7], outline=255, width=int(s * .09))
        d.line([s * .46, s * .5, s * .92, s * .5], fill=255, width=int(s * .09))
        d.line([s * .78, s * .5, s * .78, s * .68], fill=255, width=int(s * .09))
        d.line([s * .9, s * .5, s * .9, s * .64], fill=255, width=int(s * .09))
    elif nom == "personnes":
        for (cx, r) in ((s * .32, s * .13), (s * .68, s * .13)):
            d.ellipse([cx - r, s * .18 - r, cx + r, s * .18 + r], fill=255)
            d.rounded_rectangle([cx - s * .2, s * .4, cx + s * .2, s * .9], radius=int(s * .12), fill=255)
    elif nom == "coche":
        d.line([s * .15, s * .52, s * .4, s * .78], fill=255, width=int(s * .12)); d.line([s * .4, s * .78, s * .88, s * .25], fill=255, width=int(s * .12))
    elif nom == "croix":
        d.line([s * .2, s * .2, s * .8, s * .8], fill=255, width=int(s * .12)); d.line([s * .8, s * .2, s * .2, s * .8], fill=255, width=int(s * .12))
    elif nom == "fleche":
        d.line([s * .1, s * .5, s * .8, s * .5], fill=255, width=int(s * .12))
        d.line([s * .55, s * .25, s * .85, s * .5], fill=255, width=int(s * .12)); d.line([s * .55, s * .75, s * .85, s * .5], fill=255, width=int(s * .12))
    elif nom == "megaphone":
        d.polygon([(s * .1, s * .38), (s * .55, s * .18), (s * .55, s * .82), (s * .1, s * .62)], fill=255)
        d.rectangle([s * .18, s * .62, s * .32, s * .88], fill=255)
        d.arc([s * .5, s * .22, s * .92, s * .78], -60, 60, fill=255, width=int(s * .07))
        d.arc([s * .58, s * .34, s * .82, s * .66], -60, 60, fill=255, width=int(s * .07))
    elif nom == "cible":
        d.ellipse([s * .06, s * .06, s * .94, s * .94], outline=255, width=int(s * .08))
        d.ellipse([s * .28, s * .28, s * .72, s * .72], outline=255, width=int(s * .08))
        d.ellipse([s * .43, s * .43, s * .57, s * .57], fill=255)
    elif nom == "crayon":
        d.line([s * .2, s * .8, s * .75, s * .25], fill=255, width=int(s * .16))
        d.polygon([(s * .12, s * .9), (s * .2, s * .72), (s * .3, s * .82)], fill=255)
        d.rectangle([s * .1, s * .86, s * .9, s * .94], fill=255)
    elif nom == "poignee":
        d.line([s * .1, s * .5, s * .9, s * .5], fill=255, width=int(s * .16))
        d.ellipse([s * .38, s * .36, s * .62, s * .64], fill=255)
    elif nom == "calendrier":
        d.rounded_rectangle([s * .08, s * .18, s * .92, s * .92], radius=int(s * .08), outline=255, width=int(s * .07))
        d.rectangle([s * .08, s * .18, s * .92, s * .36], fill=255)
        for i in range(3):
            for j in range(2): d.rectangle([s * (.22 + i * .2), s * (.48 + j * .2), s * (.32 + i * .2), s * (.58 + j * .2)], fill=255)
    elif nom == "lecture":
        d.polygon([(s * .3, s * .15), (s * .3, s * .85), (s * .9, s * .5)], fill=255)
    elif nom == "robot":
        cx = cy = s / 2
        for k in range(8):
            ang = k * math.pi / 4
            d.line([cx + math.cos(ang) * s * .25, cy + math.sin(ang) * s * .25, cx + math.cos(ang) * s * .46, cy + math.sin(ang) * s * .46], fill=255, width=int(s * .14))
        d.ellipse([s * .2, s * .2, s * .8, s * .8], fill=255); d.ellipse([s * .36, s * .36, s * .64, s * .64], fill=0)
    elif nom == "poche":
        d.rounded_rectangle([s * .08, s * .25, s * .92, s * .8], radius=int(s * .1), outline=255, width=int(s * .08))
        d.rectangle([s * .62, s * .44, s * .92, s * .62], fill=255)
    elif nom == "etoile":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5; r = s * .46 if i % 2 == 0 else s * .2
            pts.append((s / 2 + r * math.cos(a), s / 2 + r * math.sin(a)))
        d.polygon(pts, fill=255)
    elif nom == "balance":
        d.line([s * .5, s * .12, s * .5, s * .88], fill=255, width=int(s * .08))
        d.line([s * .12, s * .3, s * .88, s * .3], fill=255, width=int(s * .08))
        d.arc([s * .02, s * .3, s * .38, s * .66], 0, 180, fill=255, width=int(s * .07))
        d.arc([s * .62, s * .3, s * .98, s * .66], 0, 180, fill=255, width=int(s * .07))
        d.line([s * .3, s * .88, s * .7, s * .88], fill=255, width=int(s * .08))
    elif nom == "graphique":
        for k, hgt in enumerate((.35, .55, .8)):
            d.rectangle([s * (.12 + k * .3), s * (.9 - hgt), s * (.32 + k * .3), s * .9], fill=255)
    elif nom == "telephone":
        d.rounded_rectangle([s * .28, s * .06, s * .72, s * .94], radius=int(s * .1), outline=255, width=int(s * .08))
        d.rectangle([s * .42, s * .82, s * .58, s * .86], fill=255)
    elif nom == "loupe":
        d.ellipse([s * .08, s * .08, s * .66, s * .66], outline=255, width=int(s * .1))
        d.line([s * .58, s * .58, s * .92, s * .92], fill=255, width=int(s * .13))
    elif nom == "document":
        d.rounded_rectangle([s * .18, s * .08, s * .82, s * .92], radius=int(s * .06), outline=255, width=int(s * .07))
        for k in range(3): d.line([s * .32, s * (.34 + k * .16), s * .68, s * (.34 + k * .16)], fill=255, width=int(s * .06))
    elif nom == "bouclier":
        d.polygon([(s * .5, s * .06), (s * .9, s * .22), (s * .84, s * .62), (s * .5, s * .94), (s * .16, s * .62), (s * .1, s * .22)], outline=255, fill=0, width=int(s * .08))
        d.line([s * .33, s * .5, s * .46, s * .64], fill=255, width=int(s * .09)); d.line([s * .46, s * .64, s * .7, s * .36], fill=255, width=int(s * .09))
    else:
        d.ellipse([s * .2, s * .2, s * .8, s * .8], fill=255)
    return m


def poser_icone(im, nom, cx, cy, taille, p, out=1.0, halo=True, coul=None):
    if p <= 0 or out <= 0: return
    e = back(min(1, p * 1.4)); a = int(255 * min(1, p * 2.5) * out)
    tl = max(2, int(taille * (0.5 + 0.5 * e)))
    m = icone(nom, tl)
    cal = Image.new("L", (W, H), 0); cal.paste(m, (int(cx - tl / 2), int(cy - tl / 2)))
    if coul:
        g = Image.new("RGBA", (W, H), coul + (255,)); g.putalpha(cal.point(lambda v: int(v * a / 255)))
        im.alpha_composite(g)
    else:
        g = voile_or(W, H).convert("RGBA"); g.putalpha(cal.point(lambda v: int(v * a / 255)))
        if halo: lueur(im, g, 18, 0.55)
        else: im.alpha_composite(g)


def pastille(im, cx, cy, r, p, out=1.0):
    if p <= 0 or out <= 0: return
    e = back(min(1, p * 1.4)); a = int(255 * min(1, p * 2.5) * out); rr = int(r * (0.5 + 0.5 * e))
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(22, 24, 30, int(236 * a / 255)), outline=OR + (int(200 * a / 255),), width=3)
    im.alpha_composite(c)


def barre_progression(im, x, y, w, h, p, a=255, n=None, k=None):
    if a <= 2: return
    d = ImageDraw.Draw(im, "RGBA")
    m = Image.new("L", (W, H), 0); md = ImageDraw.Draw(m)
    if n:
        seg = (w - (n - 1) * 8) / n
        for i in range(n):
            x0 = x + i * (seg + 8)
            d.rounded_rectangle([x0, y, x0 + seg, y + h], radius=h / 2, fill=ETEINT + (int(a * .7),))
            if i < k: md.rounded_rectangle([x0, y, x0 + seg, y + h], radius=h / 2, fill=a)
            elif i == k and p > 0.02: md.rounded_rectangle([x0, y, x0 + seg * p, y + h], radius=h / 2, fill=a)
    else:
        d.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=ETEINT + (int(a * .7),))
        if p > 0.02: md.rounded_rectangle([x, y, x + w * p, y + h], radius=h / 2, fill=a)
    g = voile_or(W, H).convert("RGBA"); g.putalpha(m); lueur(im, g, 12, 0.5)
