# -*- coding: utf-8 -*-
"""
Le robot.

Il demande à la passerelle ce qu'il y a à faire, le fait, et lui rend le résultat.
Il ne décide jamais de publier : c'est Apps Script qui publie.

Répartition des rôles, pensée pour que chacun fasse ce qu'il sait faire :
  - le robot entend, calcule, fabrique des images et des vidéos ;
  - la tâche Claude écrit les textes, à partir de la transcription ;
  - Apps Script garde les dossiers et publie.
"""

import os
import shutil
import sys
import tempfile
import time
import traceback

from . import miniature as M
from . import noms
from . import passerelle as P
from . import reglages as R
from . import soustitres as S
from . import video as V

TRAVAIL = "travail"
JOURNAL = []


def dire(message):
    print(message, flush=True)
    JOURNAL.append(message)


# --------------------------------------------------------------- textes

def lire_accroche(chemin):
    """
    Le fichier d'accroche écrit par la tâche Claude.

    Cinq lignes :
      1, 2  le titre, en gras
      3     la ligne d'accroche, le mot fort entouré d'astérisques
      4, 5  la chute
    """
    with open(chemin, encoding="utf-8") as f:
        lignes = [l.rstrip("\n") for l in f if l.strip()]
    if len(lignes) < 3:
        return None

    titre = lignes[:2]
    brut = lignes[2]
    chute = lignes[3:5] if len(lignes) > 3 else []

    morceaux, reste = [], brut
    while "*" in reste:
        avant, _, suite = reste.partition("*")
        fort, _, apres = suite.partition("*")
        if avant:
            morceaux.append((avant, "blanc"))
        if fort:
            morceaux.append((fort, "fort"))
        reste = apres
    if reste:
        morceaux.append((reste, "blanc"))
    if not morceaux:
        morceaux = [(brut, "blanc")]

    return titre, morceaux, chute


# --------------------------------------------------------------- étapes

def etape_transcription(element, fichier, dossier):
    """Transcrit et range le texte. C'est lui qui nourrit la tâche Claude."""
    from . import transcription as T

    dire(f"  transcription…")
    debut = time.time()
    resultat = T.transcrire(fichier)
    dire(f"  transcrit en {round(time.time() - debut)} s, "
         f"{len(resultat['mots'])} mots")

    P.deposer_texte(element["base"] + ".transcription.txt",
                    resultat["texte"], "A_POSTER")
    return resultat


def etape_miniature(element, fichier, dossier, accroche):
    """Fabrique la couverture, à partir de la photo fournie ou d'une image de la vidéo."""
    fond = os.path.join(dossier, "fond.jpg")

    if element.get("photo"):
        dire("  couverture : à partir de votre capture")
        P.telecharger(element["photo"]["lien"], fond)
    else:
        dire("  couverture : aucune capture, je choisis la meilleure image")
        if not V.meilleure_image(fichier, fond):
            dire("  aucune image exploitable, couverture abandonnée")
            return None

    titre, ligne, chute = accroche
    sortie = os.path.join(dossier, element["base"] + ".jpg")
    M.fabriquer(fond, titre, ligne, chute, sortie)

    etat = M.controler(sortie)
    if not etat.get("valide", False):
        dire(f"  couverture refusée par le contrôle : {etat}")
        P.signaler("Couverture refusée : " + element["nom"],
                   "Le contrôle automatique a refusé la couverture.\n\n"
                   + str(etat) +
                   "\n\nRien n'a été déposé, la publication attend.")
        return None

    dire(f"  couverture correcte : marges {etat['marge_gauche']} / "
         f"{etat['marge_droite']}, bas {etat['bas_du_texte']}")
    P.deposer_image(element["base"] + ".jpg", sortie, "MINIATURES")
    return sortie


def etape_soustitres(element, fichier, dossier, mots):
    """Incruste les sous-titres et renvoie la vidéo à sa place."""
    if not mots:
        dire("  pas de parole détectée, aucun sous-titre")
        return None

    groupes = S.decouper_en_groupes(mots, par_groupe=3, duree_max=1.1)
    dire(f"  {len(groupes)} groupes de sous-titres")

    sortie = os.path.join(dossier, "sous-titree.mp4")
    debut = time.time()
    S.incruster(fichier, groupes, sortie)
    dire(f"  incrustés en {round(time.time() - debut)} s")

    P.deposer_video(element["nom"], sortie, "A_POSTER")
    return sortie


# --------------------------------------------------------------- boucle

def traiter(element):
    dossier = tempfile.mkdtemp(prefix="vid_", dir=TRAVAIL)
    try:
        taille_mo = element["taille"] / 1048576
        dire(f"\n{element['nom']}  [{round(taille_mo)} Mo]")

        if taille_mo > R.TAILLE_MAX_MO:
            dire("  trop lourde, je n'y touche pas")
            P.signaler("Vidéo trop lourde : " + element["nom"],
                       f"Elle pèse {round(taille_mo)} Mo, au-delà de la limite de "
                       f"{R.TAILLE_MAX_MO} Mo.\n\n"
                       "Exportez plus léger : 1080p, 30 images par seconde, "
                       "10 Mbit/s. Même qualité à l'écran, quatre fois plus léger.")
            return

        brut = os.path.join(dossier, "brut.mp4")
        dire("  téléchargement…")
        P.telecharger(element["lien"], brut)

        infos = V.sonder(brut)
        dire(f"  {infos['largeur']}x{infos['hauteur']}, "
             f"{round(infos['duree'])} s, rotation {infos['rotation']}")

        # La normalisation redresse l'image : sans elle, tout ce qu'on écrirait
        # dessus partirait de travers.
        propre = os.path.join(dossier, "propre.mp4")
        dire("  normalisation…")
        V.normaliser(brut, propre)
        os.remove(brut)

        resultat = {"mots": [], "texte": ""}
        besoin_texte = not element["deja"]["legende"]
        besoin_soustitres = R.SOUSTITRES_ACTIFS

        if besoin_texte or besoin_soustitres:
            resultat = etape_transcription(element, propre, dossier)

        accroche_locale = os.path.join(dossier, "accroche.txt")
        accroche = None
        if element.get("accroche_lien"):
            P.telecharger(element["accroche_lien"], accroche_locale)
            accroche = lire_accroche(accroche_locale)

        if not element["deja"]["miniature"]:
            if accroche:
                etape_miniature(element, propre, dossier, accroche)
            else:
                dire("  couverture en attente du texte de la tâche Claude")

        if besoin_soustitres:
            etape_soustitres(element, propre, dossier, resultat["mots"])

    except Exception as e:
        dire(f"  ÉCHEC : {e}")
        traceback.print_exc()
        P.signaler("Le robot a buté sur " + element.get("nom", "une vidéo"),
                   f"{e}\n\n{traceback.format_exc()[:1500]}")
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def main():
    os.makedirs(TRAVAIL, exist_ok=True)
    debut = time.time()

    elements = P.travail()
    if not elements:
        dire("Rien à faire.")
        return 0

    dire(f"{len(elements)} vidéo(s) en attente.")
    for element in elements:
        if time.time() - debut > 35 * 60:
            dire("Temps de passage épuisé, la suite au prochain réveil.")
            break
        traiter(element)

    dire(f"\nTerminé en {round((time.time() - debut) / 60, 1)} min.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
