# -*- coding: utf-8 -*-
"""
Montage « motion design » d'une vidéo de formation, piloté par un scénario JSON.

Style validé (VSL v3 / test du 16/09/2026) :
  - logo rond du Premier Cercle sur les écrans du décor (ecrans.py) ;
  - jump-cuts : petit zoom à chaque pause de la voix (silences détectés) ;
  - segments « partage » : la vidéo se range dans un cadre arrondi à gauche,
    colonne de cartes à droite, mots-clés en bas ;
  - hors partage : plein cadre, mots-clés en bas au centre.

Scénario (JSON) :
{
  "module": "MODULE 01",                      (facultatif)
  "segments": [
    {"debut": 4.4, "fin": 18.3,
     "entete": ["MODULE 06", "Vendre & se faire connaître"],
     "numeros": {"t": 20.1, "n": 5},          (facultatif : rangée de pastilles)
     "cartes": [
        {"t": 5.3, "icone": "poignee", "titre": "Apprendre à vendre",
         "sous": "aux propriétaires", "coche": true, "or": false}
     ]}
  ],
  "mots": [
    {"t": 8.1, "duree": 1.3, "texte": "NE NÉGLIGEZ PAS CETTE TÂCHE",
     "or": "NE NÉGLIGEZ PAS", "taille": 56}
  ]
}
Les mots-clés se placent seuls : sous le cadre en mode partage, en bas au
centre sinon.

Usage :
    python -m robot.montage entree.mp4 scenario.json sortie.mp4 [--apercu 2,10,30]
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
from PIL import Image, ImageDraw, ImageFilter

from . import design as G
from . import ecrans
from .design import (W, H, IVOIRE, GRIS, OR, ph, back, inout, fb, fr, _m)

ICI = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(ICI, "logo_rond.png")

# cadre vidéo en mode partage
CW, CH, CX0, CY0 = 1250, 703, 50, 60
X = 1340          # colonne design
LC = 530          # largeur des cartes
PCX, PY = CX0 + CW / 2, 905
Y_PLEIN = 930     # mots-clés en plein cadre


# ------------------------------------------------------------- silences
def silences(video, seuil="-32dB", mini=0.25):
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", video, "-af",
                        "silencedetect=noise=%s:d=%.2f" % (seuil, mini), "-f", "null", "-"],
                       capture_output=True, text=True)
    debuts, fins = [], []
    for ligne in r.stderr.splitlines():
        if "silence_start:" in ligne:
            debuts.append(float(ligne.split("silence_start:")[1].split()[0]))
        elif "silence_end:" in ligne:
            fins.append(float(ligne.split("silence_end:")[1].split()[0]))
    coupes = []
    for d in debuts:
        f = next((x for x in fins if x > d), d + mini)
        coupes.append((d + f) / 2)
    # jamais deux coupes à moins de 1,2 s
    out = []
    for c in coupes:
        if not out or c - out[-1] > 1.2:
            out.append(c)
    return out


# ------------------------------------------------------------- scénario
class Scenario:
    def __init__(self, d, coupes):
        self.module = d.get("module", "")
        self.segments = d.get("segments", [])
        self.mots = d.get("mots", [])
        self.coupes = coupes
        self.balayages = []
        for s in self.segments:
            self.balayages += [s["debut"] - 0.1, s["fin"] - 0.1]

    def partage(self, t):
        for s in self.segments:
            ta, tb = s["debut"], s["fin"]
            e = ph(t, ta, ta + 0.55) * (1 - ph(t, tb - 0.5, tb))
            if e > 0:
                return e, s
        return 0.0, None


# ------------------------------------------------------------- cadrage
def cadrage(video, t, coupes):
    seg = sum(1 for c in coupes if t >= c)
    z_cible = 1.0 if seg % 2 == 0 else 1.10
    z_prec = 1.0 if (seg - 1) % 2 == 0 else 1.10
    tc = coupes[seg - 1] if seg > 0 else -1
    u = ph(t, tc, tc + 0.14)
    z = z_prec + (z_cible - z_prec) * inout(u)
    z += 0.012 * (math.sin(t * 0.25) + 1) / 2
    if 0 <= t - tc < 0.6:
        z += 0.03 * (1 - (t - tc) / 0.6) ** 2
    w, h = video.size
    nw, nh = int(w / z), int(h / z); x0, y0 = (w - nw) // 2, int((h - nh) * 0.42)
    return video.crop((x0, y0, x0 + nw, y0 + nh)).resize((w, h), Image.BILINEAR)


_MASQUES = {}


def composer_video(video, t, e):
    if e <= 0:
        return video.convert("RGBA")
    k = back(e) if e < 1 else 1.0
    s = 1 - (1 - CW / W) * k
    nw, nh = int(W * s), int(H * s)
    x, y = int(CX0 * k), int(CY0 * k)
    im = G.fond(t).copy()
    petit = video.resize((nw, nh), Image.BILINEAR if k < 1 else Image.LANCZOS).convert("RGBA")
    r = int(34 * k)
    cle = (nw, nh, r)
    if cle not in _MASQUES:
        m = Image.new("L", (nw, nh), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, nw - 1, nh - 1], radius=r, fill=255)
        om = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(om).rounded_rectangle([x + 6, y + 14, x + nw + 6, y + nh + 14], radius=r, fill=(0, 0, 0, int(150 * k)))
        if len(_MASQUES) > 40: _MASQUES.clear()
        _MASQUES[cle] = (m, om.filter(ImageFilter.GaussianBlur(22)))
    m, ombre = _MASQUES[cle]
    petit.putalpha(m)
    im.alpha_composite(ombre)
    im.alpha_composite(petit, (x, y))
    if k > 0.05:
        ImageDraw.Draw(im, "RGBA").rounded_rectangle([x - 2, y - 2, x + nw + 1, y + nh + 1], radius=r + 2,
                                                     outline=OR + (int(220 * k),), width=4)
    return im


# ------------------------------------------------------------- une image
def image(t, brut, sc):
    e, seg = sc.partage(t)
    im = composer_video(cadrage(brut, t, sc.coupes), t, e)
    dr = math.sin(t * 0.3) * 4
    G.logo_petit(im, 1400, 1012, a=int(170 * ph(t, 0.3, 1.0)))

    if seg is not None and e > 0.5:
        s = 1 - ph(t, seg["fin"] - 0.5, seg["fin"] - 0.1)
        y = 70
        ent = seg.get("entete")
        if ent:
            if len(ent) >= 2:
                c = G.calque_carte(LC, 122, [(ent[0], fb(22), "or", 20), (ent[1], G.ajuste(ent[1], 32, LC - 68), IVOIRE, 56)])
            else:
                c = G.calque_carte(LC, 90, [(ent[0], G.ajuste(ent[0], 32, LC - 68), "or", 26)])
            G.poser(im, c, X, y + dr, ph(t, seg["debut"] + 0.3, seg["debut"] + 0.8), out=s)
            y += c.height + 28
        num = seg.get("numeros")
        if num:
            n = int(num["n"]); t0 = num["t"]
            pas = min(108, (LC - 60) // max(1, n - 1)) if n > 1 else 0
            for k in range(n):
                q = ph(t, t0 + k * 0.18, t0 + 0.4 + k * 0.18)
                G.pastille(im, X + 48 + k * pas, y + 32 + dr, 32, q, out=s)
                G.texte(im, X + 48 + k * pas, y + 14 + dr, str(k + 1), fb(32), a=int(255 * q * s), or_=True, centre_x=True)
                G.flash(im, ph(t, t0 + k * 0.18, t0 + 0.2 + k * 0.18), 20)
            G.barre_progression(im, X, y + 82 + dr, LC, 8, ph(t, t0, t0 + 0.3 + n * 0.18), a=int(255 * ph(t, t0, t0 + 0.4) * s))
            y += 120
        for c_ in seg.get("cartes", []):
            t0 = c_["t"]
            q = ph(t, t0, t0 + 0.5)
            yy = c_.get("y", y) + dr
            y = c_.get("y", y) + 125
            if q <= 0:
                continue
            titre = c_["titre"]; sous = c_.get("sous", "")
            coul = "or" if c_.get("or") else IVOIRE
            if sous:
                c = G.calque_carte(LC, 108, [(titre, G.ajuste(titre, 29, LC - 165), coul, 18), (sous, G.ajuste(sous, 21, LC - 130, gras=False), GRIS, 62)], x0=100)
            else:
                c = G.calque_carte(LC, 90, [(titre, G.ajuste(titre, 30, LC - 165), coul, 26)], x0=100)
            G.poser(im, c, X, yy, q, out=s)
            cy = yy + c.height / 2
            G.pastille(im, X + 50, cy, 34, ph(t, t0 + 0.1, t0 + 0.5), out=s)
            G.poser_icone(im, c_.get("icone", "point"), X + 50, cy, 36, ph(t, t0 + 0.2, t0 + 0.6), out=s,
                          coul=(225, 100, 90) if c_.get("icone") == "croix" else None)
            if c_.get("coche"):
                G.coche(im, X + LC - 44, cy, int(255 * s), r=20, p=ph(t, t0 + 0.5, t0 + 1.1))
            G.flash(im, ph(t, t0, t0 + 0.25), 30)

    for m_ in sc.mots:
        t0 = m_["t"]; duree = m_.get("duree", 1.6)
        if not (t0 - 0.05 <= t <= t0 + duree + 0.05):
            continue
        if e > 0.5:
            G.mot_cle(im, m_["texte"], t, t0, duree, y=PY, taille=m_.get("taille", 60), or_mot=m_.get("or"), cx=PCX, maxw=1180)
        else:
            G.mot_cle(im, m_["texte"], t, t0, duree, y=Y_PLEIN, taille=m_.get("taille", 66), or_mot=m_.get("or"), maxw=1700, voile=True)

    for tc in sc.balayages:
        G.balayage(im, t, tc)
    return im.convert("RGB")


# ------------------------------------------------------------- rendu
def _rendre_tranche(args):
    entree, sc_d, coupes, deb, fin, sortie, fps = args
    sc = Scenario(sc_d, coupes)
    cap = cv2.VideoCapture(entree)
    cap.set(cv2.CAP_PROP_POS_FRAMES, deb)
    R = ecrans.Remplaceur(LOGO)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
           "-r", "%.4f" % fps, "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", sortie]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    i = deb
    while i < fin:
        ok, f = cap.read()
        if not ok:
            break
        f = R.traiter(f)
        if f.shape[1] != W or f.shape[0] != H:
            f = cv2.resize(f, (W, H))
        v = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        proc.stdin.write(G.finition(image(i / fps, v, sc), i).tobytes())
        i += 1
    proc.stdin.close(); proc.wait()
    return sortie, i - deb


def rendre(entree, scenario, sortie, apercu=None, procs=None):
    with open(scenario, encoding="utf-8") as f:
        sc_d = json.load(f)
    coupes = silences(entree)
    cap = cv2.VideoCapture(entree)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    sc = Scenario(sc_d, coupes)

    if apercu:
        cap = cv2.VideoCapture(entree); R = ecrans.Remplaceur(LOGO)
        dossier = os.path.dirname(sortie) or "."
        for tt in apercu:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(tt * fps)); ok, f = cap.read()
            R.n = 0; f = R.traiter(f)
            v = Image.fromarray(cv2.cvtColor(cv2.resize(f, (W, H)), cv2.COLOR_BGR2RGB))
            G.finition(image(tt, v, sc), int(tt * fps)).save(os.path.join(dossier, "_apercu_%05.1f.jpg" % tt), quality=88)
        print("aperçus écrits dans", dossier)
        return

    procs = procs or max(1, os.cpu_count() or 1)
    dossier = tempfile.mkdtemp(prefix="montage_")
    bornes = [round(k * n / procs) for k in range(procs + 1)]
    taches = [(entree, sc_d, coupes, bornes[k], bornes[k + 1], os.path.join(dossier, "t%02d.mp4" % k), fps)
              for k in range(procs) if bornes[k + 1] > bornes[k]]
    debut = time.time()
    print("%d images, %d processus, %d coupes" % (n, len(taches), len(coupes)), flush=True)
    with Pool(len(taches)) as pool:
        res = pool.map(_rendre_tranche, taches)
    print("images rendues en %d s" % round(time.time() - debut), flush=True)

    liste = os.path.join(dossier, "liste.txt")
    with open(liste, "w") as f:
        for chemin, _ in res:
            f.write("file '%s'\n" % chemin)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", liste,
                    "-i", entree, "-map", "0:v", "-map", "1:a?", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", "-movflags", "+faststart", sortie], check=True)
    for chemin, _ in res:
        os.remove(chemin)
    return sortie


if __name__ == "__main__":
    a = sys.argv[1:]
    ap = None
    if "--apercu" in a:
        k = a.index("--apercu"); ap = [float(x) for x in a[k + 1].split(",")]; a = a[:k] + a[k + 2:]
    rendre(a[0], a[1], a[2], apercu=ap)
