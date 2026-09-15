# Robot Le Premier Cercle

Ce robot fabrique les miniatures, les sous-titres et les stories des vidéos
de Bilel Fartas, puis les rend à Google Drive.

Il ne touche jamais à Drive directement : une passerelle Apps Script,
qui tourne chez Google, lui ouvre des accès temporaires et range les résultats.

## Ce qu'il faut renseigner

Dans Paramètres du dépôt > Secrets et variables > Actions :

- `PASSERELLE_URL` : l'adresse de l'application web Apps Script
- `PASSERELLE_JETON` : le même mot de passe que dans les propriétés du script

## Quand il tourne

- dès qu'Apps Script le réveille, c'est-à-dire dans les minutes qui suivent un dépôt ;
- et de toute façon une fois par heure, entre 7 h et 23 h, par sécurité.

## Réglages

Tout est dans `robot/reglages.py`. Les valeurs ont été validées visuellement
avec Bilel le 15 septembre 2026 : ne pas les changer sans lui montrer le rendu.
