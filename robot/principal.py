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

    Modèle de couverture validé le 15/09/2026 : DEUX lignes, qui se lisent
    comme une seule phrase coupée en deux.
      ligne 1  posée en Inter Bold, blanc ivoire
      ligne 2  posée entièrement en Lora Italic, en dégradé corail vers ambre

    Les lignes suivantes, s'il y en a (ancien format à cinq lignes), sont
    ignorées. Les astérisques de l'ancien format sont retirées : dans ce
    modèle, c'est toute la deuxième ligne qui est en couleur, et plus un
    seul mot au milieu d'une phrase.
    """
    with open(chemin, encoding="utf-8") as f:
        lignes = []
        for l in f:
            l = l.replace("\\", "").replace("*", "").rstrip()
            if l.strip():
                lignes.append(l.strip())

    if len(lignes) < 2:
        return None

    titre = [lignes[0]]
    accent = [(lignes[1], "fort")]
    return titre, accent, []


# --------------------------------------------------------------- étapes

def etape_transcription(element, fichier, dossier):
    """
    Transcrit la parole.

    Le texte n'est PAS déposé ici : il l'est tout à la fin du passage, une
    fois les sous-titres incrustés. C'est lui qui sert de preuve que la
    vidéo est terminée — le déposer trop tôt ferait croire au robot qu'une
    vidéo interrompue en cours de route est finie, et il ne la reprendrait
    jamais (c'est ce qui est arrivé le 15/09/2026).
    """
    from . import transcription as T

    dire("  transcription…")
    debut = time.time()
    resultat = T.transcrire(fichier)
    dire("  transcrit en %d s, %d mots"
         % (round(time.time() - debut), len(resultat["mots"])))
    return resultat


def ranger_la_transcription(element, resultat):
    """Dépose le texte : le passage est terminé, la tâche Claude peut écrire."""
    P.deposer_texte(element["base"] + ".transcription.txt",
                    resultat["texte"], "A_POSTER")


def etape_miniature(element, fichier, dossier, accroche):
    """Fabrique la couverture. Ne fait jamais échouer le reste du traitement."""
    try:
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
            dire("  couverture refusée par le contrôle : %s" % etat)
            P.signaler("Couverture refusée : " + element["nom"],
                       "Le contrôle automatique a refusé la couverture.\n\n"
                       + str(etat)
                       + "\n\nRien n'a été déposé, la publication attend.")
            return None

        dire("  couverture correcte : marges %s / %s, bas %s"
             % (etat["marge_gauche"], etat["marge_droite"], etat["bas_du_texte"]))
        P.deposer_image(element["base"] + ".jpg", sortie, "MINIATURES")
        return sortie

    except Exception as e:
        dire("  couverture impossible : %s" % e)
        traceback.print_exc()
        return None


def etape_soustitres(element, fichier, dossier, mots):
    """Incruste les sous-titres et renvoie la vidéo à sa place."""
    if not mots:
        dire("  pas de parole détectée, aucun sous-titre")
        return None

    groupes = S.decouper_en_groupes(mots, par_groupe=3, duree_max=1.1)
    dire("  %d groupes de sous-titres" % len(groupes))

    sortie = os.path.join(dossier, "sous-titree.mp4")
    debut = time.time()
    S.incruster(fichier, groupes, sortie)
    dire("  incrustés en %d s" % round(time.time() - debut))

    P.deposer_video(element["nom"], sortie, "A_POSTER")
    return sortie


# --------------------------------------------------------------- boucle

def traiter(element):
    dossier = tempfile.mkdtemp(prefix="vid_", dir=TRAVAIL)
    try:
        taille_mo = element["taille"] / 1048576
        dire("\n%s  [%d Mo]" % (element["nom"], round(taille_mo)))

        # Garde-fous : sans eux, une vidéo déjà traitée repartait à chaque
        # réveil et le robot tournait en boucle.
        deja_transcrit = element["deja"]["transcription"]
        besoin_soustitres = R.SOUSTITRES_ACTIFS and not deja_transcrit
        besoin_miniature = not element["deja"]["miniature"]

        if not besoin_soustitres and not besoin_miniature:
            dire("  rien à faire sur cette vidéo")
            return

        if taille_mo > R.TAILLE_MAX_MO:
            dire("  trop lourde, je n'y touche pas")
            P.signaler("Vidéo trop lourde : " + element["nom"],
                       "Elle pèse %d Mo, au-delà de la limite de %d Mo.\n\n"
                       "Exportez plus léger : 1080p, 30 images par seconde, "
                       "10 Mbit/s. Même qualité à l'écran, quatre fois plus léger."
                       % (round(taille_mo), R.TAILLE_MAX_MO))
            return

        brut = os.path.join(dossier, "brut.mp4")
        dire("  téléchargement…")
        P.telecharger(element["lien"], brut)

        infos = V.sonder(brut)
        dire("  %dx%d, %d s, rotation %s"
             % (infos["largeur"], infos["hauteur"],
                round(infos["duree"]), infos["rotation"]))

        # La normalisation redresse l'image : sans elle, tout ce qu'on écrirait
        # dessus partirait de travers.
        propre = os.path.join(dossier, "propre.mp4")
        dire("  normalisation…")
        V.normaliser(brut, propre)
        os.remove(brut)

        resultat = {"mots": [], "texte": ""}
        if besoin_soustitres:
            resultat = etape_transcription(element, propre, dossier)

        accroche = None
        if element.get("accroche_lien"):
            accroche_locale = os.path.join(dossier, "accroche.txt")
            P.telecharger(element["accroche_lien"], accroche_locale)
            accroche = lire_accroche(accroche_locale)

        if besoin_miniature:
            if accroche:
                etape_miniature(element, propre, dossier, accroche)
            else:
                dire("  couverture en attente du texte de la tâche Claude")

        if besoin_soustitres:
            try:
                etape_soustitres(element, propre, dossier, resultat["mots"])
            except Exception as e:
                # On n'insiste pas : sans cela le robot reprendrait la même
                # vidéo à chaque réveil. On prévient, et on considère le
                # passage terminé.
                dire("  sous-titres impossibles : %s" % e)
                traceback.print_exc()
                P.signaler("Sous-titres impossibles : " + element["nom"],
                           "La vidéo est restée sans sous-titres incrustés.\n\n"
                           "%s\n\n%s" % (e, traceback.format_exc()[:1200]))
            ranger_la_transcription(element, resultat)

    except Exception as e:
        dire("  ÉCHEC : %s" % e)
        traceback.print_exc()
        P.signaler("Le robot a buté sur " + element.get("nom", "une vidéo"),
                   "%s\n\n%s" % (e, traceback.format_exc()[:1500]))
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def main():
    os.makedirs(TRAVAIL, exist_ok=True)
    debut = time.time()

    elements = P.travail()
    if not elements:
        dire("Rien à faire.")
        return 0

    dire("%d vidéo(s) en attente." % len(elements))
    for element in elements:
        if time.time() - debut > 35 * 60:
            dire("Temps de passage épuisé, la suite au prochain réveil.")
            break
        traiter(element)

    dire("\nTerminé en %s min." % round((time.time() - debut) / 60, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
