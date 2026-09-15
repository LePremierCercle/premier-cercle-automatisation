# -*- coding: utf-8 -*-
"""
Le robot.

Il demande a la passerelle ce qu'il y a a faire, le fait, et lui rend le resultat.
Il ne decide jamais de publier : c'est Apps Script qui publie.
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


def lire_accroche(chemin):
    """
    Le fichier d'accroche ecrit par la tache Claude.

    Cinq lignes :
      1, 2  le titre
      3     la ligne d'accroche, le mot fort entoure d'asterisques
      4, 5  la chute
    """
    with open(chemin, encoding="utf-8") as f:
        lignes = []
        for l in f:
            l = l.replace("\\", "").rstrip()
            if l.strip():
                lignes.append(l)
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


def etape_transcription(element, fichier, dossier):
    from . import transcription as T

    dire("  transcription...")
    debut = time.time()
    resultat = T.transcrire(fichier)
    dire("  transcrit en %d s, %d mots"
         % (round(time.time() - debut), len(resultat["mots"])))

    P.deposer_texte(element["base"] + ".transcription.txt",
                    resultat["texte"], "A_POSTER")
    return resultat


def etape_miniature(element, fichier, dossier, accroche):
    """Fabrique la couverture. Ne fait jamais echouer le reste du traitement."""
    try:
        fond = os.path.join(dossier, "fond.jpg")

        if element.get("photo"):
            dire("  couverture : a partir de votre capture")
            P.telecharger(element["photo"]["lien"], fond)
        else:
            dire("  couverture : aucune capture, je choisis la meilleure image")
            if not V.meilleure_image(fichier, fond):
                dire("  aucune image exploitable, couverture abandonnee")
                return None

        titre, ligne, chute = accroche
        sortie = os.path.join(dossier, element["base"] + ".jpg")
        M.fabriquer(fond, titre, ligne, chute, sortie)

        etat = M.controler(sortie)
        if not etat.get("valide", False):
            dire("  couverture refusee par le controle : %s" % etat)
            P.signaler("Couverture refusee : " + element["nom"],
                       "Le controle automatique a refuse la couverture.\n\n"
                       + str(etat))
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
    if not mots:
        dire("  pas de parole detectee, aucun sous-titre")
        return None

    groupes = S.decouper_en_groupes(mots, par_groupe=3, duree_max=1.1)
    dire("  %d groupes de sous-titres" % len(groupes))

    sortie = os.path.join(dossier, "sous-titree.mp4")
    debut = time.time()
    S.incruster(fichier, groupes, sortie)
    dire("  incrustes en %d s" % round(time.time() - debut))

    P.deposer_video(element["nom"], sortie, "A_POSTER")
    return sortie


def traiter(element):
    dossier = tempfile.mkdtemp(prefix="vid_", dir=TRAVAIL)
    try:
        taille_mo = element["taille"] / 1048576
        dire("\n%s  [%d Mo]" % (element["nom"], round(taille_mo)))

        deja_transcrit = element["deja"]["transcription"]
        besoin_soustitres = R.SOUSTITRES_ACTIFS and not deja_transcrit
        besoin_miniature = not element["deja"]["miniature"]

        if not besoin_soustitres and not besoin_miniature:
            dire("  rien a faire sur cette video")
            return

        if taille_mo > R.TAILLE_MAX_MO:
            dire("  trop lourde, je n'y touche pas")
            P.signaler("Video trop lourde : " + element["nom"],
                       "Elle pese %d Mo, au-dela de la limite de %d Mo."
                       % (round(taille_mo), R.TAILLE_MAX_MO))
            return

        brut = os.path.join(dossier, "brut.mp4")
        dire("  telechargement...")
        P.telecharger(element["lien"], brut)

        infos = V.sonder(brut)
        dire("  %dx%d, %d s, rotation %s"
             % (infos["largeur"], infos["hauteur"],
                round(infos["duree"]), infos["rotation"]))

        propre = os.path.join(dossier, "propre.mp4")
        dire("  normalisation...")
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
                dire("  couverture en attente du texte de la tache Claude")

        if besoin_soustitres:
            etape_soustitres(element, propre, dossier, resultat["mots"])

    except Exception as e:
        dire("  ECHEC : %s" % e)
        traceback.print_exc()
        P.signaler("Le robot a bute sur " + element.get("nom", "une video"),
                   "%s\n\n%s" % (e, traceback.format_exc()[:1500]))
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def main():
    os.makedirs(TRAVAIL, exist_ok=True)
    debut = time.time()

    elements = P.travail()
    if not elements:
        dire("Rien a faire.")
        return 0

    dire("%d video(s) en attente." % len(elements))
    for element in elements:
        if time.time() - debut > 35 * 60:
            dire("Temps de passage epuise, la suite au prochain reveil.")
            break
        traiter(element)

    dire("\nTermine en %s min." % round((time.time() - debut) / 60, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())# -*- coding: utf-8 -*-
"""
Le robot.

Il demande a la passerelle ce qu'il y a a faire, le fait, et lui rend le resultat.
Il ne decide jamais de publier : c'est Apps Script qui publie.
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


def lire_accroche(chemin):
    """
    Le fichier d'accroche ecrit par la tache Claude.

    Cinq lignes :
      1, 2  le titre
      3     la ligne d'accroche, le mot fort entoure d'asterisques
      4, 5  la chute
    """
    with open(chemin, encoding="utf-8") as f:
        lignes = []
        for l in f:
            l = l.replace("\\", "").rstrip()
            if l.strip():
                lignes.append(l)
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


def etape_transcription(element, fichier, dossier):
    from . import transcription as T

    dire("  transcription...")
    debut = time.time()
    resultat = T.transcrire(fichier)
    dire("  transcrit en %d s, %d mots"
         % (round(time.time() - debut), len(resultat["mots"])))

    P.deposer_texte(element["base"] + ".transcription.txt",
                    resultat["texte"], "A_POSTER")
    return resultat


def etape_miniature(element, fichier, dossier, accroche):
    """Fabrique la couverture. Ne fait jamais echouer le reste du traitement."""
    try:
        fond = os.path.join(dossier, "fond.jpg")

        if element.get("photo"):
            dire("  couverture : a partir de votre capture")
            P.telecharger(element["photo"]["lien"], fond)
        else:
            dire("  couverture : aucune capture, je choisis la meilleure image")
            if not V.meilleure_image(fichier, fond):
                dire("  aucune image exploitable, couverture abandonnee")
                return None

        titre, ligne, chute = accroche
        sortie = os.path.join(dossier, element["base"] + ".jpg")
        M.fabriquer(fond, titre, ligne, chute, sortie)

        etat = M.controler(sortie)
        if not etat.get("valide", False):
            dire("  couverture refusee par le controle : %s" % etat)
            P.signaler("Couverture refusee : " + element["nom"],
                       "Le controle automatique a refuse la couverture.\n\n"
                       + str(etat))
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
    if not mots:
        dire("  pas de parole detectee, aucun sous-titre")
        return None

    groupes = S.decouper_en_groupes(mots, par_groupe=3, duree_max=1.1)
    dire("  %d groupes de sous-titres" % len(groupes))

    sortie = os.path.join(dossier, "sous-titree.mp4")
    debut = time.time()
    S.incruster(fichier, groupes, sortie)
    dire("  incrustes en %d s" % round(time.time() - debut))

    P.deposer_video(element["nom"], sortie, "A_POSTER")
    return sortie


def traiter(element):
    dossier = tempfile.mkdtemp(prefix="vid_", dir=TRAVAIL)
    try:
        taille_mo = element["taille"] / 1048576
        dire("\n%s  [%d Mo]" % (element["nom"], round(taille_mo)))

        deja_transcrit = element["deja"]["transcription"]
        besoin_soustitres = R.SOUSTITRES_ACTIFS and not deja_transcrit
        besoin_miniature = not element["deja"]["miniature"]

        if not besoin_soustitres and not besoin_miniature:
            dire("  rien a faire sur cette video")
            return

        if taille_mo > R.TAILLE_MAX_MO:
            dire("  trop lourde, je n'y touche pas")
            P.signaler("Video trop lourde : " + element["nom"],
                       "Elle pese %d Mo, au-dela de la limite de %d Mo."
                       % (round(taille_mo), R.TAILLE_MAX_MO))
            return

        brut = os.path.join(dossier, "brut.mp4")
        dire("  telechargement...")
        P.telecharger(element["lien"], brut)

        infos = V.sonder(brut)
        dire("  %dx%d, %d s, rotation %s"
             % (infos["largeur"], infos["hauteur"],
                round(infos["duree"]), infos["rotation"]))

        propre = os.path.join(dossier, "propre.mp4")
        dire("  normalisation...")
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
                dire("  couverture en attente du texte de la tache Claude")

        if besoin_soustitres:
            etape_soustitres(element, propre, dossier, resultat["mots"])

    except Exception as e:
        dire("  ECHEC : %s" % e)
        traceback.print_exc()
        P.signaler("Le robot a bute sur " + element.get("nom", "une video"),
                   "%s\n\n%s" % (e, traceback.format_exc()[:1500]))
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def main():
    os.makedirs(TRAVAIL, exist_ok=True)
    debut = time.time()

    elements = P.travail()
    if not elements:
        dire("Rien a faire.")
        return 0

    dire("%d video(s) en attente." % len(elements))
    for element in elements:
        if time.time() - debut > 35 * 60:
            dire("Temps de passage epuise, la suite au prochain reveil.")
            break
        traiter(element)

    dire("\nTermine en %s min." % round((time.time() - debut) / 60, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
