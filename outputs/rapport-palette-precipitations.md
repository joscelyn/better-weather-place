# Audit de la palette des précipitations mensuelles

Date : 19 octobre 2026, complété le 20 octobre 2026
Statut : palette validée sur la grille européenne de production

> Ce rapport conserve l’audit initial du domaine témoin. Le contrôle final de la grille complète est résumé dans `rapport-audit-grilles-production.md`.

## Périmètre

L’analyse utilise les douze normales mensuelles CHELSA 1991–2020 calculées entre 10° O–8° E et 29–47° N. Après application du masque WBM, chaque mois contient **3 098 918 pixels terrestres**.

La palette provisoire testée comporte des points d’arrêt à 0, 5, 10, 20, 40, 60, 100, 150, 250 et 400 mm/mois. Les mêmes seuils sont utilisés toute l’année.

## Résultats

- plage observée sur l’ensemble des mois : **0 à 348,1 mm/mois** ;
- aucun pixel au-dessus de 400 mm/mois ;
- maximum du 99e percentile : **231,7 mm/mois** en novembre ;
- maximum absolu : **348,1 mm/mois** en décembre ;
- médiane la plus sèche : **4,77 mm/mois** en juillet ;
- médiane la plus humide : **48,43 mm/mois** en novembre.

Les classes sèches sont fortement sollicitées :

- janvier : **12,89 %** sous 5 mm et **23,97 %** sous 10 mm ;
- juillet : **50,89 %** sous 5 mm et **64,37 %** sous 10 mm ;
- août : **30,74 %** sous 5 mm et **47,23 %** sous 10 mm.

Les seuils 5, 10 et 20 mm sont donc utiles pour distinguer les zones réellement très sèches, au lieu de les regrouper dans une seule grande classe.

## Décision

Conserver la palette 0–400 mm/mois pour la maquette :

- aucun ajustement automatique selon le mois ;
- maintien des seuils rapprochés à 0, 5, 10 et 20 mm ;
- couleur terminale à partir de 400 mm ;
- eau et absence de données transparentes, et non assimilées à zéro pluie.

Le contrôle européen complet a ensuite observé un maximum très local de 1 370,5 mm à Saint-Kilda, mais au plus 0,196 % des pixels terrestres mensuels dépassent 400 mm. La borne de 400 mm est donc conservée : ces rares dépassements prennent la couleur terminale sans modifier la valeur numérique du COG.

## Fichiers associés

- `analyse-palette-precipitations.csv` : quantiles et taux de dépassement par mois ;
- `occupation-palette-precipitations.csv` : occupation des intervalles ;
- `analyse-palette-precipitations.png` : synthèse graphique ;
- `work/validation/analyze_precipitation_palette.py` : calcul reproductible ;
- normales locales mises en cache sous `work/validation/cache/pilot_etape_2b/`.
