# Audit de la palette de durée d’ensoleillement

Date : 19 octobre 2026, complété le 20 octobre 2026
Statut : palette validée sur la grille SARAH-3 de production

> Ce rapport conserve l’audit initial des séries de référence. Le contrôle final de la grille SARAH-3 est résumé dans `rapport-audit-grilles-production.md`.

## Méthode

La grille numérique SARAH-3 complète n’est pas encore téléchargée. La palette a donc été contrôlée avec les séries mensuelles 1991–2020 déjà validées, en excluant les Canaries du périmètre prioritaire :

- 14 points SARAH-3 disponibles au sud de 65° N, soit 168 valeurs de la source principale ;
- 10 points CERRA au nord de 65° N, soit 120 valeurs de la source qui sera affichée comme indicative ;
- les normales WMO des 10 mêmes stations nordiques, soit 120 contrôles indépendants.

L’ensemble contient **408 valeurs mensuelles** issues de **34 séries point–source**. Ce n’est pas un échantillon spatial uniforme : les pourcentages décrivent les références disponibles, pas une part du territoire.

## Résultats

- plage observée : **0 à 389,41 h/mois** ;
- maximum SARAH-3 : Faro, juillet, **389,41 h** ;
- maximum CERRA nordique brut : Abisko, juin, **386,66 h** ;
- maximum WMO nordique : Luleå, juin, **299,4 h** ;
- valeurs au-dessus de 360 h : **8**, soit 1,96 % des références ;
- valeurs au-dessus de la borne de 400 h : **0**.

Les seuils rapprochés sous 120 heures restent utiles pour différencier les hivers peu lumineux. Les seuils de 200 à 360 heures couvrent progressivement les situations printanières, estivales et méditerranéennes sans concentrer toutes les valeurs élevées dans une seule couleur.

## Décision

Conserver sans modification la palette commune **0–400 h/mois** et ses points d’arrêt : 0, 20, 40, 80, 120, 160, 200, 240, 280, 320, 360 et 400 heures.

La borne de 400 heures laisse une marge de 10,59 heures au-dessus du maximum observé. Elle couvre également CERRA brut, malgré sa surestimation connue dans certaines stations nordiques. Il serait trompeur d’étendre dès maintenant la palette jusqu’au maximum physique théorique d’un mois : cela comprimerait les contrastes réellement utiles sur la carte.

Le contrôle final de la grille SARAH-3 masquée par le WBM a trouvé un maximum terrestre de 404,4 h en juillet. Seuls 606 pixels, soit 0,103 % des pixels valides ce mois-là, dépassent 400 h. La palette reste donc inchangée et ces rares dépassements prennent la couleur terminale.

Au nord de 65° N, la validation WMO confirme que le problème principal est l’incertitude de la valeur CERRA, pas l’étendue de la palette. L’avertissement « estimation indicative » reste donc obligatoire.

## Fichiers associés

- `analyse-palette-ensoleillement.csv` : 408 valeurs harmonisées ;
- `synthese-palette-ensoleillement.csv` : statistiques par source et par mois ;
- `occupation-palette-ensoleillement.csv` : occupation des intervalles ;
- `analyse-palette-ensoleillement.png` : synthèse graphique ;
- `work/validation/analyze_sunshine_palette.py` : analyse reproductible.
