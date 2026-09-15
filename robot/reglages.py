# -*- coding: utf-8 -*-
"""
Tous les réglages du robot au même endroit.
Rien d'autre dans le projet ne contient de valeur en dur.
"""

# ---------------------------------------------------------------- Drive
DOSSIERS = {
    "videos":            "1TyXCbsDkYGT6DvkrSoyZQbIsKv9VOSNd",  # Vidéo à poster
    "videos_postees":    "1qcea53yP3BUeWZ7tOkFrTnYneYL5F5Wp",  # Vidéo déjà postée
    "miniatures":        "1A_ekGFKEp_ChFJsrk-qzfW98o5wBIgNf",  # Miniature à poster
    "miniatures_postees":"1_IrX_PugAwLep-SoCd-i7eCF-O3IZChm",  # Miniature déjà postée
    "stories":           "1sBQLVpSSjkgswxe2sbc3pS48f8Rzg1ZL",  # Story à poster
    "stories_postees":   "1ZxDOWN7yfrc223Ib7x8tFzp9O9qQYRUr",  # Story déjà postée
    "photos_brutes":     "1QzLxhdiXHQL048TkP_pGbI5ayo6OcLmR",  # Photos pour miniatures
    "erreur":            "11v1gMtcdwaSO4AMKPl_1W5bCtP7RajB_",  # Erreur
}

# ---------------------------------------------------------------- Publication
PLATEFORMES = ["instagram", "facebook", "tiktok", "youtube"]
EXCLURE_COMPTE = "excellence"        # la page de l'agence ne reçoit jamais le personal branding
INSTAGRAM_SUR_GRILLE = True
API_POSTFORME = "https://api.postforme.dev/v1"

# ---------------------------------------------------------------- Délais
STABILITE_MIN = 5        # une vidéo doit être posée depuis 5 min avant d'être touchée
ATTENTE_MAX_MIN = 180    # au-delà, on considère qu'il manque quelque chose

# ---------------------------------------------------------------- Vidéo
DEBIT_CIBLE = "10M"      # Instagram recommande 8 à 12 Mbit/s ; le téléphone envoie 18
TAILLE_MAX_MO = 450      # au-delà, on ne télécharge pas : on alerte

# ---------------------------------------------------------------- Miniature
# Format imposé par Instagram pour une couverture de réel.
LARGEUR, HAUTEUR = 1080, 1920
RATIO_ATTENDU = LARGEUR / HAUTEUR          # 0.5625
RATIO_TOLERANCE = 0.02

MARGE_GAUCHE = 95        # validé le 15/09/2026 — jamais moins
BAS_DU_TEXTE = 1250      # le bloc de texte s'arrête là, au-dessus du compteur de vues
TAILLE_TITRE = 96
TAILLE_TEXTE = 62
TAILLE_FORT = 74      # le mot en couleur est plus gros que le reste de la ligne

# Interligne : 1.00 = hauteur naturelle de la police. En dessous, les lignes se rapprochent.
INTERLIGNE = 0.90
ESPACE_ENTRE_BLOCS = 44

CORAIL = (0xD6, 0x54, 0x42)
AMBRE  = (0xEA, 0x9E, 0x68)

# Retouche validée par Bilel
LUMINOSITE, CONTRASTE, SATURATION, NETTETE = 1.06, 1.14, 1.08, 35

# ---------------------------------------------------------------- Story
STORY_Y = 1560           # la phrase est posée là, sous ses propres sous-titres
STORY_TAILLE = 60
STORY_DUREE_MAX_S = 60   # au-delà, pas de story du tout

APPELS_ACTION = [
    "Envoie-moi FORMATION en DM.",
    "Écris FORMATION, je t'envoie la formation gratuite.",
    "Un mot en DM : FORMATION.",
    "Tape FORMATION, je t'envoie le lien.",
    "FORMATION en DM, et elle est à toi.",
]

# ---------------------------------------------------------------- Légende
HASHTAGS = [
    "#conciergerie", "#conciergerieairbnb", "#entreprisedenettoyage",
    "#nettoyage", "#locationcourteduree", "#entrepreneuriat",
    "#creationdentreprise", "#mindset", "#discipline",
]

LEGENDE_PAR_DEFAUT = (
    "Je partage ce que je vis, sans filtre.\n\n"
    "Si ça te parle, tout est dans le lien en bio.\n\n"
    + " ".join(HASHTAGS[:7])
)

# ---------------------------------------------------------------- Sous-titres
SOUSTITRES_ACTIFS = True       # mettre à False pour publier sans sous-titres
SOUSTITRES_MODELE = "small"    # le bon compromis en français
SOUSTITRES_Y = 1330            # ligne de base, sous le menton (validé 15/09/2026)
SOUSTITRES_TAILLE = 66         # mots ordinaires, en Inter Bold
SOUSTITRES_RATIO_FORT = 1.42   # le mot en couleur est 42 % plus gros (validé 15/09/2026)
SOUSTITRES_MARGE = 170         # air laissé de chaque côté

# Dégradé du mot fort, calé sur la largeur DU MOT et non sur celle de l'image,
# pour que la transition soit entièrement visible (validé 15/09/2026, essai n°3).
FORT_DEBUT = (0xE8, 0x73, 0x0F)   # orange franc
FORT_FIN   = (0xF5, 0xB8, 0x5A)   # ambre doré

# La serif italique est cherchée là où elle se trouve, selon la machine.
import os as _os
_PISTES_SERIF = [
    _os.path.expanduser("~/.fonts/lora/Lora-Italic-Variable.ttf"),
    "/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf",
    _os.path.expanduser("~/.fonts/lora/Lora-Italic[wght].ttf"),
]
POLICE_SERIF_ITALIQUE = next((c for c in _PISTES_SERIF if _os.path.exists(c)), _PISTES_SERIF[0])

# ---------------------------------------------------------------- Alertes
EMAIL_ALERTE = "nettoyagexcellence@gmail.com"
