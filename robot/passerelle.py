# -*- coding: utf-8 -*-
"""
Dialogue avec la passerelle Apps Script.

Le robot ne touche jamais à Google Drive directement : c'est Apps Script,
qui tourne chez Google avec les autorisations de Bilel, qui lui ouvre
des accès temporaires et range les résultats.
"""

import json
import os
import time

import requests

PASSERELLE = os.environ.get("PASSERELLE_URL", "")
JETON = os.environ.get("PASSERELLE_JETON", "")

DELAI = 120


def _appel(action, charge=None, fichiers=None):
    if not PASSERELLE or not JETON:
        raise RuntimeError(
            "PASSERELLE_URL et PASSERELLE_JETON doivent être renseignés "
            "dans les secrets du dépôt."
        )
    corps = {"action": action, "jeton": JETON}
    if charge:
        corps.update(charge)

    # Google égare parfois la réponse d'Apps Script : l'adresse de retour
    # renvoie un 404, une page, ou la passerelle nous dit franchement qu'elle
    # s'est perdue. Le travail, lui, a bien été fait. On réessaie donc plutôt
    # que d'abandonner : toutes nos actions supportent d'être refaites (un
    # dépôt remplace l'homonyme, une session d'envoi inutilisée expire seule).
    probleme = ""
    for essai in range(4):
        try:
            r = requests.post(PASSERELLE, json=corps, timeout=DELAI)
            r.raise_for_status()
            reponse = r.json()
        except requests.HTTPError as err:
            code = err.response.status_code if err.response is not None else "?"
            probleme = "Google a répondu %s" % code
        except ValueError:
            probleme = "réponse illisible : " + r.text[:200].replace("\n", " ")
        except requests.RequestException as err:
            probleme = str(err)[:200]
        else:
            if reponse.get("erreur") == "reponse_perdue":
                probleme = "réponse égarée par Google"
            elif not reponse.get("ok", False):
                raise RuntimeError("La passerelle a répondu : " + str(reponse.get("erreur")))
            else:
                return reponse

        time.sleep(3 * (essai + 1))

    raise RuntimeError(
        "La passerelle n'a pas répondu pour l'action « %s » après 4 essais. "
        "Dernier problème : %s" % (action, probleme)
    )


def travail():
    """
    Renvoie la liste de ce qui attend.
    Chaque entrée : {id, nom, type, lien, taille, deja: {...}}
    """
    reponse = _appel("travail")
    if "elements" not in reponse:
        # Mieux vaut un échec bruyant qu'un « rien à faire » mensonger :
        # une liste vide par erreur, et le robot dort pendant que le travail
        # s'accumule.
        raise RuntimeError("La passerelle n'a pas renvoyé la liste du travail.")
    return reponse["elements"]


def telecharger(lien, destination):
    """Récupère un fichier depuis le lien temporaire fourni par la passerelle."""
    with requests.get(lien, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(destination, "wb") as f:
            for morceau in r.iter_content(chunk_size=1 << 20):
                if morceau:
                    f.write(morceau)
    return destination


def deposer_texte(nom, contenu, dossier):
    """Range un fichier texte (légende, transcription) dans un dossier Drive."""
    return _appel("deposer_texte", {
        "nom": nom,
        "dossier": dossier,
        "contenu": contenu,
    })


def deposer_image(nom, chemin, dossier):
    """Range une image. Envoyée en base64 : une miniature pèse moins de 500 Ko."""
    import base64
    with open(chemin, "rb") as f:
        donnees = base64.b64encode(f.read()).decode("ascii")
    return _appel("deposer_image", {
        "nom": nom,
        "dossier": dossier,
        "base64": donnees,
    })


def deposer_video(nom, chemin, dossier):
    """
    Range une vidéo, quelle que soit sa taille.

    Apps Script ne sait pas avaler 70 Mo d'un coup : il se contente donc
    d'ouvrir une session d'envoi chez Google, et le robot y verse les octets
    directement. Apps Script range ensuite le fichier.
    """
    taille = os.path.getsize(chemin)
    session = _appel("ouvrir_envoi", {
        "nom": nom,
        "dossier": dossier,
        "taille": taille,
    })
    url = session.get("url")
    if not url:
        raise RuntimeError("La passerelle n'a pas renvoyé d'adresse d'envoi.")

    envoye = 0
    bloc = 8 * 1024 * 1024          # 8 Mo par morceau
    with open(chemin, "rb") as f:
        while envoye < taille:
            donnees = f.read(bloc)
            if not donnees:
                break
            fin = envoye + len(donnees) - 1
            entetes = {
                "Content-Length": str(len(donnees)),
                "Content-Range": f"bytes {envoye}-{fin}/{taille}",
            }
            for essai in range(4):
                r = requests.put(url, data=donnees, headers=entetes, timeout=600)
                if r.status_code in (200, 201, 308):
                    break
                time.sleep(2 * (essai + 1))
            else:
                raise RuntimeError(f"Envoi interrompu à {envoye} octets sur {taille}.")
            envoye += len(donnees)

    identifiant = None
    try:
        identifiant = json.loads(r.text).get("id")
    except Exception:
        pass
    return _appel("cloturer_envoi", {"id": identifiant, "nom": nom, "dossier": dossier})


def ranger(identifiant, dossier):
    """Déplace un fichier d'origine vers son dossier d'arrivée."""
    return _appel("ranger", {"id": identifiant, "dossier": dossier})


def signaler(sujet, message):
    """Fait envoyer un mail d'alerte par la passerelle."""
    try:
        _appel("signaler", {"sujet": sujet, "message": message})
    except Exception:
        pass
