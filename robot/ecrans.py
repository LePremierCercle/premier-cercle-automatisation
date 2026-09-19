# -*- coding: utf-8 -*-
"""
Remplace, image par image, le logo affiché sur les écrans du décor par le
symbole rond du Premier Cercle.

Les écrans sont repérés par leur couleur (fond bleu nuit, ou presque noir
quand ils sont sous-exposés), quelle que soit la position de la caméra :
cadrage large, zoom, plan de trois quarts, écran coupé par le bord de
l'image ou en partie caché par la tête. Seuls les pixels de l'écran sont
repeints : ce qui passe devant reste devant.

La détection se fait sur une image réduite, toutes les quelques images ;
la repeinte ne touche que le voisinage de chaque écran.
"""

import cv2
import numpy as np

ECHELLE = 0.25          # détection sur l'image réduite
DETECTE_TOUTES_LES = 4  # images
LISSAGE = 0.4           # EMA sur la position (1 = brut)

AIRE_MIN = 0.003        # part de l'image
AIRE_MAX = 0.20
RECTANGULARITE_MIN = 0.84
Y_MAX = 0.55            # centre de l'écran dans la moitié haute
LOGO_PART = 0.78        # hauteur du logo / petit côté de l'écran


def _canaux(bgr):
    return (bgr[:, :, 0].astype(np.int16), bgr[:, :, 1].astype(np.int16), bgr[:, :, 2].astype(np.int16))


def _masque_navy(bgr):
    b, g, r = _canaux(bgr)
    m = (r < 80) & (g < 80) & (b > 28) & (b < 120) & (b - r >= 8) & (b - g >= 8) & (np.abs(r - g) < 22)
    return m.astype(np.uint8) * 255


def _masque_sombre(bgr):
    """Écran sous-exposé : presque noir, sans dominante chaude, et plat."""
    b, g, r = _canaux(bgr)
    m = (np.maximum(np.maximum(r, g), b) < 95) & (r - b < 35) & (g - b < 35)
    gris = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    moy = cv2.blur(gris, (5, 5)); var = cv2.blur(gris * gris, (5, 5)) - moy * moy
    return (m & (var < 30)).astype(np.uint8) * 255


def _masque_texte(bgr):
    b, g, r = _canaux(bgr)
    blanc = (r > 160) & (g > 160) & (b > 160)
    rouge = (r > 140) & (g < 100) & (b < 120) & (r - g > 60)
    return ((blanc | rouge).astype(np.uint8)) * 255


def _candidats(bgr, masque, texte, strict=False, ref=None):
    h, w = bgr.shape[:2]
    rect_min = 0.86 if strict else RECTANGULARITE_MIN
    aire_max = 0.08 if strict else AIRE_MAX
    y_max = 0.45 if strict else Y_MAX
    if strict:
        # les rainures noires du mur à lattes sont fines : une ouverture les efface
        masque = cv2.morphologyEx(masque, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    masque = cv2.morphologyEx(masque, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(masque, connectivity=8)
    out = []
    for i in range(1, n):
        aire = stats[i, cv2.CC_STAT_AREA]
        if aire < AIRE_MIN * w * h or aire > aire_max * w * h or cent[i][1] > y_max * h:
            continue
        comp = (lab == i).astype(np.uint8) * 255
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        coque = cv2.convexHull(max(cnts, key=cv2.contourArea))
        rect = cv2.minAreaRect(coque)
        (cx, cy), (rw, rh), ang = rect
        if min(rw, rh) < 7:
            continue
        aire_rect = rw * rh
        plein = np.zeros_like(comp)
        cv2.fillConvexPoly(plein, coque, 255)
        if cv2.countNonZero(plein) / max(1.0, aire_rect) < rect_min:
            continue
        ratio = max(rw, rh) / max(1.0, min(rw, rh))
        if ratio > 6 or (strict and not (1.3 <= ratio <= 4.5)):
            continue
        if ref is not None and not (0.65 <= min(rw, rh) / max(1.0, min(ref)) <= 1.4
                                    and 0.65 <= max(rw, rh) / max(1.0, max(ref)) <= 1.4):
            continue
        # un écran porte toujours le texte à effacer
        if cv2.countNonZero(cv2.bitwise_and(plein, texte)) < 0.004 * aire_rect:
            continue
        couleur = cv2.mean(bgr, mask=comp)[:3]
        # un écran est un rectangle : on garde le rectangle englobant plutôt que la
        # coque, qui perd un coin dès qu'un reflet éclaircit l'écran
        boite = cv2.boxPoints(rect).astype(np.int32).reshape(-1, 1, 2)
        out.append({"rect": rect, "coque": boite, "couleur": couleur})
    return out


def detecter(bgr_petit):
    texte = _masque_texte(bgr_petit)
    ecrans = _candidats(bgr_petit, _masque_navy(bgr_petit), texte)
    if len(ecrans) < 2:
        ref = ecrans[0]["rect"][1] if ecrans else None
        for e in _candidats(bgr_petit, _masque_sombre(bgr_petit), texte, strict=True, ref=ref):
            if all(abs(e["rect"][0][0] - f["rect"][0][0]) > 15 for f in ecrans):
                ecrans.append(e)
    ecrans.sort(key=lambda e: e["rect"][0][0])
    return ecrans


def _agrandir(e, k):
    (cx, cy), (rw, rh), ang = e["rect"]
    return {"rect": ((cx * k, cy * k), (rw * k, rh * k), ang),
            "coque": (e["coque"].astype(np.float32) * k).astype(np.int32),
            "couleur": e["couleur"]}


def _ordonner(pts):
    pts = np.array(pts, np.float32)
    s = pts.sum(axis=1); d = np.diff(pts, axis=1).ravel()
    return np.float32([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]])


class Remplaceur:
    def __init__(self, chemin_logo):
        logo = cv2.imread(chemin_logo, cv2.IMREAD_UNCHANGED)
        if logo is None or logo.shape[2] != 4:
            raise RuntimeError("logo introuvable ou sans transparence : " + chemin_logo)
        a = logo[:, :, 3]
        ys, xs = np.where(a > 8)
        self.logo = logo[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        self.suivi = []
        self.n = 0
        self.derniers = []

    def _lisser(self, ecrans):
        if len(self.suivi) != len(ecrans):
            self.suivi = ecrans
            return ecrans
        out = []
        for s, e in zip(self.suivi, ecrans):
            (cx, cy), (rw, rh), ang = e["rect"]
            (sx, sy), (sw, sh), sang = s["rect"]
            if abs(cx - sx) > 40 or abs(cy - sy) > 40 or abs(rw - sw) > 40:
                out.append(e)
                continue
            if abs(ang - sang) > 45:
                ang, rw, rh = (ang + 90 if ang < sang else ang - 90), rh, rw
            k = LISSAGE
            out.append({"rect": ((sx + k * (cx - sx), sy + k * (cy - sy)),
                                 (sw + k * (rw - sw), sh + k * (rh - sh)), sang + k * (ang - sang)),
                        "coque": e["coque"], "couleur": e["couleur"]})
        self.suivi = out
        return out

    def traiter(self, bgr):
        h, w = bgr.shape[:2]
        if self.n % DETECTE_TOUTES_LES == 0:
            petit = cv2.resize(bgr, None, fx=ECHELLE, fy=ECHELLE, interpolation=cv2.INTER_AREA)
            self.derniers = self._lisser([_agrandir(e, 1 / ECHELLE) for e in detecter(petit)])
        self.n += 1
        if not self.derniers:
            return bgr

        out = bgr.copy()
        for e in self.derniers:
            x0, y0, bw, bh = cv2.boundingRect(e["coque"])
            x0 = max(0, x0 - 8); y0 = max(0, y0 - 8)
            x1 = min(w, x0 + bw + 16); y1 = min(h, y0 + bh + 16)
            roi = bgr[y0:y1, x0:x1]
            rh_, rw_ = roi.shape[:2]
            if rh_ < 4 or rw_ < 4:
                continue
            coque = e["coque"] - np.array([x0, y0])
            plein = np.zeros((rh_, rw_), np.uint8)
            cv2.fillConvexPoly(plein, coque.astype(np.int32), 255)

            texte = _masque_texte(roi)
            b, g, r = _canaux(roi)
            froid = ((b >= r - 6) & (b >= g - 6) & (np.maximum(np.maximum(r, g), b) > 45)).astype(np.uint8) * 255
            clair = cv2.bitwise_and(cv2.bitwise_or(texte, froid), cv2.dilate(plein, np.ones((25, 25), np.uint8)))
            # les traits lumineux qui débordent de l'écran (barres LED) ne sont pas du texte
            nc, labc = cv2.connectedComponents(clair, connectivity=8)
            dedans = np.zeros_like(clair)
            proche = cv2.dilate(plein, np.ones((13, 13), np.uint8))
            for j in range(1, nc):
                comp = labc == j
                nb = int(comp.sum())
                if not nb:
                    continue
                # du texte : presque tout dans l'écran, ou rien qui s'en éloigne
                if int((plein[comp] > 0).sum()) >= 0.8 * nb or int((proche[comp] == 0).sum()) == 0:
                    dedans[comp] = 255
            dedans = cv2.dilate(dedans, np.ones((3, 3), np.uint8))
            fond = cv2.bitwise_or(_masque_navy(roi), _masque_sombre(roi))
            zone = cv2.bitwise_and(plein, cv2.bitwise_or(fond, dedans))
            zone = cv2.morphologyEx(zone, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
            zone = cv2.bitwise_and(zone, plein)

            # 1. aplat de la couleur de l'écran
            zf = (cv2.GaussianBlur(zone, (5, 5), 0).astype(np.float32) / 255.0)[:, :, None]
            couleur = np.array(e["couleur"], np.float32)
            res = roi.astype(np.float32) * (1 - zf) + couleur * zf

            # 2. le logo, tourné comme l'écran
            (cx, cy), (rw, rh), ang = e["rect"]
            taille = LOGO_PART * min(rw, rh)
            lw, lh = self.logo.shape[1], self.logo.shape[0]
            box = cv2.boxPoints(((cx - x0, cy - y0), (taille * lw / lh, taille), ang if rw >= rh else ang + 90))
            src = np.float32([[0, 0], [lw, 0], [lw, lh], [0, lh]])
            M = cv2.getPerspectiveTransform(src, _ordonner(box))
            calque = cv2.warpPerspective(self.logo, M, (rw_, rh_), flags=cv2.INTER_LINEAR,
                                         borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            alpha = (calque[:, :, 3].astype(np.float32) / 255.0) * (zone.astype(np.float32) / 255.0)
            alpha = alpha[:, :, None]
            res = res * (1 - alpha) + calque[:, :, :3].astype(np.float32) * alpha
            out[y0:y1, x0:x1] = np.clip(res, 0, 255).astype(np.uint8)
        return out
