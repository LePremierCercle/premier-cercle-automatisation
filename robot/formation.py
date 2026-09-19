# -*- coding: utf-8 -*-
"""
Montage « motion design » — le robot, côté GitHub.

Il interroge la passerelle « motion design » (un projet Apps Script à part)
et, pour chaque vidéo déposée dans « 1 - Vidéo à monter » :
  - sans transcription : il transcrit (Whisper) et dépose « <nom>.mots.json »
    et « <nom>.texte.txt » dans « 2 - Transcriptions » ;
  - avec un scénario (écrit par la tâche Claude dans « 3 - Scénarios ») et
    sans montage : il fabrique le montage, le dépose dans « 4 - Vidéo montée »
    et range l'originale dans « 5 - Vidéo d'origine traitée ».
Rien n'est publié.

Plusieurs robots peuvent tourner en même temps : chacun prend les vidéos
dont le rang, dans la liste triée, vaut ROBOT_RANG modulo ROBOT_NOMBRE.
"""

import json
import os
import shutil
import sys
import time
import traceback

# Une seule passerelle Apps Script (« Motion design »). Le robot choisit le
# montage d'après la forme de la vidéo :
#   horizontale : formation (écrans en fond, cadre + cartes + mots-clés)
#   verticale   : réel (cartes plein écran + badges)
if os.environ.get("MONTAGE_URL"):
    os.environ["PASSERELLE_URL"] = os.environ["MONTAGE_URL"]

from . import passerelle as P

TRAVAIL = "travail"


def dire(m):
    print(m, flush=True)


def orientation(video):
    import cv2
    cap = cv2.VideoCapture(video)
    w, h = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()
    return "vertical" if h > w else "horizontal"


def transcrire(e):
    from . import transcription as T
    brut = os.path.join(TRAVAIL, "brut.mp4")
    dire("  téléchargement…")
    P.telecharger(e["lien"], brut)
    forme = orientation(brut)
    dire("  vidéo %s" % forme)
    dire("  transcription…")
    debut = time.time()
    r = T.transcrire(brut)
    dire("  %d mots, %.0f s de vidéo, transcrit en %d s" % (len(r["mots"]), r["duree"], round(time.time() - debut)))
    P.deposer_texte(e["base"] + ".mots.json", json.dumps(r, ensure_ascii=False), "TRANSCRIPTIONS")
    P.deposer_texte(e["base"] + ".texte.txt", r["texte"], "TRANSCRIPTIONS")
    P.deposer_texte(e["base"] + ".temps.txt", "FORMAT : %s\n" % forme + minutage(r), "TRANSCRIPTIONS")
    os.remove(brut)


def minutage(r):
    """Le texte découpé par tranches de ~4 s, chacune précédée de son instant :
    c'est ce que lit la tâche Claude pour placer cartes et mots-clés."""
    lignes, courant, t0 = [], [], None
    for m in r["mots"]:
        if t0 is None:
            t0 = m["debut"]
        courant.append(m["mot"])
        if m["fin"] - t0 >= 4.0 or m["mot"].rstrip().endswith((".", "!", "?")):
            lignes.append("%6.1f | %s" % (t0, " ".join(courant)))
            courant, t0 = [], None
    if courant:
        lignes.append("%6.1f | %s" % (t0, " ".join(courant)))
    return "DURÉE TOTALE : %.1f s\n" % r["duree"] + "\n".join(lignes)


def monter(e):
    brut = os.path.join(TRAVAIL, "brut.mp4")
    fini = os.path.join(TRAVAIL, "fini.mp4")
    scenario = os.path.join(TRAVAIL, "scenario.json")
    dire("  téléchargement…")
    P.telecharger(e["lien"], brut)
    if orientation(brut) == "vertical":
        from . import montage_vertical as M
    else:
        from . import montage as M
    P.telecharger(e["scenario_lien"], scenario)
    with open(scenario, encoding="utf-8") as f:
        json.load(f)   # un scénario illisible doit échouer ici, pas après 40 min de rendu
    dire("  montage…")
    debut = time.time()
    M.rendre(brut, scenario, fini)
    dire("  monté en %d min" % round((time.time() - debut) / 60))
    dire("  dépôt dans le Drive…")
    P.deposer_video(e["base"] + ".mp4", fini, "MONTAGES")
    P.ranger(e["id"], "ORIGINES")
    for f in (brut, fini, scenario):
        if os.path.exists(f):
            os.remove(f)


def main():
    os.makedirs(TRAVAIL, exist_ok=True)
    rang = int(os.environ.get("ROBOT_RANG", "0"))
    nombre = max(1, int(os.environ.get("ROBOT_NOMBRE", "1")))
    debut = time.time()

    elements = P.travail()
    elements = [e for k, e in enumerate(elements) if k % nombre == rang]
    if not elements:
        dire("Rien à faire.")
        return 0

    for e in elements:
        dire("\n%s  [%d Mo]" % (e["nom"], e["taille"] // 1048576))
        if time.time() - debut > 300 * 60:
            dire("  temps de passage épuisé, la suite au prochain réveil")
            break
        try:
            if not e["deja"]["transcription"]:
                transcrire(e)
            elif e.get("scenario_lien") and not e["deja"]["montage"]:
                monter(e)
            else:
                dire("  en attente du scénario" if not e["deja"]["scenario"] else "  déjà montée")
        except Exception as err:
            dire("  ÉCHEC : %s" % err)
            traceback.print_exc()
            P.signaler("Échec sur " + e["nom"], "%s\n\n%s" % (err, traceback.format_exc()[:1500]))
        finally:
            shutil.rmtree(TRAVAIL, ignore_errors=True)
            os.makedirs(TRAVAIL, exist_ok=True)

    dire("\nTerminé en %s min." % round((time.time() - debut) / 60, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
