# -*- coding: utf-8 -*-
"""
Montage « motion design » d'une vidéo VERTICALE (réel), piloté par un scénario.

Style (inspiré des réels à cartes plein écran) :
  - jump-cuts : petit zoom à chaque pause de la voix ;
  - « coupures » : cartes plein écran, fond ivoire, grand mot en or rose et
    grande icône, qui remplacent l'image 1,5 à 2,5 s ;
  - « badges » : petite pastille de texte qui surgit en haut de l'image ;
  - logo discret en bas.

Scénario JSON :
{
  "coupures": [{"t": 1.5, "duree": 1.8, "ligne1": "un euro doit t'en", "accent": "RAPPORTER DEUX", "icone": "euro"}],
  "badges":   [{"t": 6.5, "duree": 2.2, "texte": "PRATIQUE QUOTIDIENNE", "icone": "coche"}]
}
"""

import json
import math
import os
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import design as G
from .design import NUIT, IVOIRE, GRIS, OR, OR_CL, ETEINT, ph, back, inout, cub, fb, fr, _m

W, H = 1080, 1920
G.W, G.H = W, H          # les briques de design travaillent en plein cadre

ICI = os.path.dirname(os.path.abspath(__file__))
rng = np.random.RandomState(11)
GRAINS = [rng.normal(0, 1, (H, W, 1)).astype(np.float32) for _ in range(6)]
_vx, _vy = np.meshgrid(np.linspace(-1, 1, W, dtype=np.float32), np.linspace(-1, 1, H, dtype=np.float32))
VIGNETTE = (1 - 0.22 * np.clip((_vx ** 2 * 0.7 + _vy ** 2 * 0.9) - 0.35, 0, 1))[:, :, None].astype(np.float32)


def finition(im, i):
    a = np.asarray(im).astype(np.float32)
    a = a * VIGNETTE + GRAINS[i % 6] * 2.5
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ------------------------------------------------------------- pauses de la voix
def coupes_voix(video):
    """Milieux des creux de volume (marche même avec une musique de fond)."""
    d = tempfile.mkdtemp(prefix="son_")
    raw = os.path.join(d, "son.raw")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", raw], check=True)
    a = np.fromfile(raw, dtype=np.int16).astype(np.float32) / 32768
    os.remove(raw)
    w = 1600; n = len(a) // w
    if n < 10:
        return []
    db = 20 * np.log10(np.array([np.sqrt(np.mean(a[i * w:(i + 1) * w] ** 2)) for i in range(n)]) + 1e-6)
    seuil = np.percentile(db, 25); bas = db < seuil
    coupes, i = [], 0
    while i < n:
        if bas[i]:
            j = i
            while j < n and bas[j]: j += 1
            if j - i >= 3: coupes.append((i + j) / 2 / 10)
            i = j
        else:
            i += 1
    out = []
    for c in coupes:
        if not out or c - out[-1] > 1.2: out.append(c)
    return out


# ------------------------------------------------------------- cadrage
def cadrage(video, t, coupes):
    seg = sum(1 for c in coupes if t >= c)
    z_cible = 1.0 if seg % 2 == 0 else 1.09
    z_prec = 1.0 if (seg - 1) % 2 == 0 else 1.09
    tc = coupes[seg - 1] if seg > 0 else -1
    u = ph(t, tc, tc + 0.14)
    z = z_prec + (z_cible - z_prec) * inout(u)
    z += 0.01 * (math.sin(t * 0.25) + 1) / 2
    if 0 <= t - tc < 0.6:
        z += 0.025 * (1 - (t - tc) / 0.6) ** 2
    w, h = video.size
    nw, nh = int(w / z), int(h / z); x0, y0 = (w - nw) // 2, int((h - nh) * 0.35)
    return video.crop((x0, y0, x0 + nw, y0 + nh)).resize((w, h), Image.BILINEAR)


# ------------------------------------------------------------- coupure plein écran
_FONDS = {}


def fond_nuit(t):
    """fond nuit du Premier Cercle, halos or rose qui dérivent, anneau fantôme qui tourne."""
    cle = round(t * 8)
    if cle in _FONDS:
        return _FONDS[cle]
    tt = cle / 8.0
    im = Image.new("RGBA", (W, H), NUIT + (255,))
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(halo)
    for (cx0, cy0, r, a, coul) in ((0.22, 0.28, 560, 95, OR), (0.82, 0.74, 500, 70, OR_CL)):
        cx = (cx0 + 0.06 * math.sin(tt * 0.6 + cx0 * 7)) * W; cy = (cy0 + 0.05 * math.cos(tt * 0.5 + cy0 * 5)) * H
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=coul + (a,))
    im.alpha_composite(halo.filter(ImageFilter.GaussianBlur(170)))
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    r = 640; cx, cy = W // 2, H // 2 + 40; rot = tt * 5
    for i in range(6):
        a0 = -90 + i * 60 + 6 + rot
        d.arc([cx - r, cy - r, cx + r, cy + r], a0, a0 + 48, fill=OR + (46,), width=4)
    ri = int(r * 0.41)
    d.arc([cx - ri, cy - ri, cx + ri, cy + ri], 0, 360, fill=OR + (22,), width=3)
    im.alpha_composite(c)
    # particules qui montent doucement
    pc = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(pc)
    for (x0, y0, rr, v, ph0, z) in PARTS:
        y = (y0 - tt * v) % 1.15 - 0.075; x = x0 + 0.012 * math.sin(tt * 0.7 + ph0)
        px, py = x * W, y * H; a = int((40 + 70 * z) * (0.6 + 0.4 * math.sin(tt * 1.3 + ph0)))
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=OR_CL + (a,))
    im.alpha_composite(pc.filter(ImageFilter.GaussianBlur(2)))
    if len(_FONDS) > 40: _FONDS.clear()
    _FONDS[cle] = im
    return im


PARTS = [(rng.rand(), rng.rand(), 3 + rng.rand() * 6, 0.010 + rng.rand() * 0.02, rng.rand() * 6.28, rng.rand()) for _ in range(40)]


def texte_or(im, s, font, cx, y, a=255):
    lw = int(_m.textlength(s, font=font)) + 8; lh = int(font.size * 1.6)
    m = Image.new("L", (lw, lh), 0); ImageDraw.Draw(m).text((4, 0), s, font=font, fill=a)
    g = G.voile_or(lw, lh).convert("RGBA"); g.putalpha(m)
    im.alpha_composite(g, (int(cx - lw / 2), int(y)))


def ajuste(s, taille, maxw, gras=True):
    f = fb(taille) if gras else fr(taille)
    while _m.textlength(s, font=f) > maxw and f.size > 40:
        f = fb(f.size - 2) if gras else fr(f.size - 2)
    return f


def coupure(t, c):
    """carte plein écran : ligne1 (ivoire) / accent (or rose, gras) / icône animée."""
    t0, duree = c["t"], c.get("duree", 1.8)
    p = ph(t, t0, t0 + 0.42); out = 1 - ph(t, t0 + duree - 0.25, t0 + duree)
    im = fond_nuit(t).copy()
    e = back(min(1, p * 1.25)); so = inout(out)
    a = int(255 * min(1, p * 3) * so)
    dy = int(60 * (1 - e)) + int(-40 * (1 - so))

    l1 = c.get("ligne1", "")
    acc = c["accent"]
    f1 = ajuste(l1, 72, W - 160, gras=False)
    f2 = ajuste(acc, 128, W - 120)
    y = 520 + dy
    if l1:
        cal = Image.new("RGBA", (W, 140), (0, 0, 0, 0))
        ImageDraw.Draw(cal).text(((W - _m.textlength(l1, font=f1)) / 2, 20), l1, font=f1, fill=IVOIRE + (a,))
        im.alpha_composite(cal, (0, y))
        y += 120
    cal = Image.new("RGBA", (W, 220), (0, 0, 0, 0))
    ech = 0.7 + 0.3 * e
    texte_or(cal, acc, f2, W / 2, 20, a)
    nw, nh = max(1, int(W * ech)), max(1, int(220 * ech))
    if ech != 1:
        cal = cal.resize((nw, nh), Image.LANCZOS)
    G.lueur(im, _plein(cal, int((W - nw) / 2), int(y + (220 - nh) / 2)), 30, 0.35 * so)
    y += 270

    ic = c.get("icone")
    if ic:
        q = ph(t, t0 + 0.12, t0 + 0.6)
        eb = back(min(1, q * 1.1))
        tl = t - t0
        # respiration et flottement, doux
        resp = 1 + 0.035 * math.sin(tl * 3.1)
        flot = 10 * math.sin(tl * 2.2)
        taille = int(330 * (0.5 + 0.5 * eb) * resp)
        cx, cy = W / 2, y + 210 + flot
        if taille > 4 and q > 0:
            # anneau segmenté qui tourne autour de l'icône, se trace à l'arrivée
            an = Image.new("L", (W, H), 0); d = ImageDraw.Draw(an)
            r = int(taille * 0.78); rot = tl * 40
            trace = cub(ph(t, t0 + 0.2, t0 + 0.9))
            for i in range(6):
                a0 = -90 + i * 60 + 8 + rot
                d.arc([cx - r, cy - r, cx + r, cy + r], a0, a0 + 44 * trace, fill=int(a * (0.9 if i == 0 else 0.45)), width=6)
            g = G.voile_or(W, H).convert("RGBA"); g.putalpha(an)
            im.alpha_composite(g)
            m = G.icone(ic, taille)
            cal = Image.new("L", (W, H), 0); cal.paste(m, (int(cx - taille / 2), int(cy - taille / 2)))
            g = G.voile_or(W, H).convert("RGBA"); g.putalpha(cal.point(lambda v: int(v * a / 255)))
            G.lueur(im, g, 30, 0.45 + 0.25 * math.sin(tl * 3.1))
    d = ImageDraw.Draw(im, "RGBA")
    lw = int(360 * cub(p))
    d.rounded_rectangle([W / 2 - lw / 2, 1440 + dy, W / 2 + lw / 2, 1448 + dy], radius=4, fill=OR + (a,))
    return im.convert("RGB")


def _plein(calque, x, y):
    cal = Image.new("RGBA", (W, H), (0, 0, 0, 0)); cal.alpha_composite(calque, (x, y)); return cal


# ------------------------------------------------------------- badge
def badge(im, t, b):
    t0, duree = b["t"], b.get("duree", 2.0)
    p = ph(t, t0, t0 + 0.35); out = 1 - ph(t, t0 + duree - 0.3, t0 + duree)
    if p <= 0 or out <= 0: return
    e = back(min(1, p * 1.3)); so = inout(out)
    a = int(255 * min(1, p * 3) * so)
    f = ajuste(b["texte"], 46, W - 260)
    tw = _m.textlength(b["texte"], font=f)
    ic = b.get("icone")
    ih = 52 if ic else 0
    w = int(tw + 70 + (ih + 22 if ic else 0)); h = 96
    c = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=48, fill=(22, 24, 30, 232), outline=OR + (210,), width=3)
    x = 34
    if ic:
        tl = t - t0
        ih2 = int(ih * (1 + 0.08 * math.sin(tl * 4.0)))
        m = G.icone(ic, ih2); g = G.voile_or(ih2, ih2).convert("RGBA"); g.putalpha(m)
        c.alpha_composite(g, (x + (ih - ih2) // 2, (h - ih2) // 2)); x += ih + 22
    d.text((x, (h - f.size) / 2 - 4), b["texte"], font=f, fill=IVOIRE + (255,))
    ech = 0.7 + 0.3 * e
    c = c.resize((max(1, int(w * ech)), max(1, int(h * ech))), Image.LANCZOS)
    c.putalpha(c.split()[3].point(lambda v: int(v * a / 255)))
    y = b.get("y", 300) + int(-30 * (1 - so)) + int(5 * math.sin((t - t0) * 2.5))
    cal = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cal.alpha_composite(c, (int((W - c.width) / 2), int(y - (c.height - h) / 2)))
    G.lueur(im, cal, 24, 0.4)


def logo_bas(im, a=150, t=0.0):
    x, y, r = 80, 1820, 22
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    for i in range(6):
        a0 = -90 + i * 60 + 6 + t * 12; d.arc([x - r, y - r, x + r, y + r], a0, a0 + 48, fill=(OR_CL if i == 0 else (200, 200, 200)) + (a,), width=4)
    ri = int(r * 0.41); d.arc([x - ri, y - ri, x + ri, y + ri], 0, 360, fill=OR_CL + (a,), width=5)
    d.text((x + r + 14, y - 13), "LE PREMIER CERCLE", font=fb(20), fill=(255, 255, 255, a))
    im.alpha_composite(c)


# ------------------------------------------------------------- une image
def image(t, brut, sc, coupes):
    for c in sc.get("coupures", []):
        if c["t"] <= t < c["t"] + c.get("duree", 1.8):
            return coupure(t, c)
    im = cadrage(brut, t, coupes).convert("RGBA")
    for b in sc.get("badges", []):
        if b["t"] - 0.05 <= t <= b["t"] + b.get("duree", 2.0) + 0.05:
            badge(im, t, b)
    logo_bas(im, a=int(150 * ph(t, 0.3, 1.0)), t=t)
    # flash blanc bref à la sortie d'une coupure
    for c in sc.get("coupures", []):
        fin = c["t"] + c.get("duree", 1.8)
        G.flash(im, ph(t, fin, fin + 0.25), 70)
    return im.convert("RGB")


# ------------------------------------------------------------- rendu
def _tranche(args):
    entree, sc, coupes, deb, fin, sortie, fps = args
    cap = cv2.VideoCapture(entree); cap.set(cv2.CAP_PROP_POS_FRAMES, deb)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
           "-r", "%.4f" % fps, "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", sortie]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    i = deb
    while i < fin:
        ok, f = cap.read()
        if not ok: break
        if f.shape[1] != W or f.shape[0] != H:
            f = cv2.resize(f, (W, H))
        v = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        proc.stdin.write(finition(image(i / fps, v, sc, coupes), i).tobytes())
        i += 1
    proc.stdin.close(); proc.wait()
    return sortie


def rendre(entree, scenario, sortie, apercu=None, procs=None):
    with open(scenario, encoding="utf-8") as f:
        sc = json.load(f)
    coupes = coupes_voix(entree)
    cap = cv2.VideoCapture(entree)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if apercu:
        dossier = os.path.dirname(sortie) or "."
        for tt in apercu:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(tt * fps)); ok, f = cap.read()
            v = Image.fromarray(cv2.cvtColor(cv2.resize(f, (W, H)), cv2.COLOR_BGR2RGB))
            finition(image(tt, v, sc, coupes), int(tt * fps)).save(os.path.join(dossier, "_v_%05.1f.jpg" % tt), quality=88)
        print("aperçus écrits dans", dossier); return
    cap.release()
    procs = procs or max(1, os.cpu_count() or 1)
    d = tempfile.mkdtemp(prefix="mv_")
    bornes = [round(k * n / procs) for k in range(procs + 1)]
    taches = [(entree, sc, coupes, bornes[k], bornes[k + 1], os.path.join(d, "t%02d.mp4" % k), fps) for k in range(procs) if bornes[k + 1] > bornes[k]]
    debut = time.time(); print("%d images, %d processus, %d coupes" % (n, len(taches), len(coupes)), flush=True)
    with Pool(len(taches)) as pool:
        res = pool.map(_tranche, taches)
    print("rendu en %d s" % round(time.time() - debut), flush=True)
    liste = os.path.join(d, "liste.txt")
    with open(liste, "w") as f:
        for ch in res: f.write("file '%s'\n" % ch)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", liste, "-i", entree,
                    "-map", "0:v", "-map", "1:a?", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", sortie], check=True)
    for ch in res: os.remove(ch)
    return sortie


if __name__ == "__main__":
    a = sys.argv[1:]; ap = None
    if "--apercu" in a:
        k = a.index("--apercu"); ap = [float(x) for x in a[k + 1].split(",")]; a = a[:k] + a[k + 2:]
    rendre(a[0], a[1], a[2], apercu=ap)
