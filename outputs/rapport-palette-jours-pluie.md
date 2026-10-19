# Audit de la palette du nombre de jours de pluie

Date : 19 octobre 2026  
Statut : palette validée sur les séries de référence, grille complète encore requise

## Méthode

Le nombre moyen de jours avec au moins 1 mm de pluie doit être calculé à partir de données quotidiennes. Une grille européenne complète sur trente ans représente un traitement beaucoup plus lourd que les normales mensuelles CHELSA. La palette a donc été contrôlée avant cette production avec toutes les séries 1991–2020 déjà validées :

- 15 points européens CERRA-Land, Canaries exclues ;
- 11 séries de stations GHCN suffisamment complètes, Canaries exclues ;
- 25 cellules CERRA-Land correspondant aux stations marocaines ;
- 25 normales WMO des mêmes stations marocaines.

L’ensemble contient **906 valeurs mensuelles** issues de **76 séries point–source**. Ce n’est pas un échantillon spatial uniforme de l’Europe : les pourcentages décrivent les références disponibles, pas une part du territoire.

## Résultats

- plage observée : **0 à 21,67 jours/mois** ;
- maximum : Mont-Blanc, mai, CERRA-Land ;
- valeurs entre 20 et 25 jours : **4**, soit 0,44 % des références ;
- valeurs au-dessus de 25 jours : **0** ;
- les classes sous 8 jours représentent la majorité des références et justifient les seuils rapprochés 1, 2, 4, 6 et 8 jours.

Les maxima des stations GHCN atteignent 16,27 jours à Tromsø en octobre. Au Maroc, le maximum est de 10,33 jours dans CERRA-Land et de 8,9 jours dans les normales WMO.

## Décision

Conserver tous les points d’arrêt actuels entre 0 et 25 jours, puis ajouter une couleur terminale à **31 jours** :

- 25 jours : `#081d58` ;
- 31 jours : `#020617`.

La valeur 31 correspond au maximum physique d’un mois de 31 jours. Cette extension évite toute saturation future, même si une cellule très humide absente des références dépasse 25 jours. Elle ne modifie pas le rendu de la plage 0–25 déjà testée.

La palette est suffisamment robuste pour la maquette. Sa distribution spatiale devra être contrôlée quand la grille CERRA-Land complète sera produite. Le rapport entre CERRA-Land et les observations reste accompagné de l’avertissement déjà prévu pour le relief complexe, notamment à Ifrane et sur les sommets alpins.

## Fichiers associés

- `analyse-palette-jours-pluie.csv` : 906 valeurs harmonisées ;
- `synthese-palette-jours-pluie.csv` : statistiques par source et par mois ;
- `occupation-palette-jours-pluie.csv` : occupation des intervalles ;
- `analyse-palette-jours-pluie.png` : synthèse graphique ;
- `work/validation/analyze_rainy_days_palette.py` : analyse reproductible.
