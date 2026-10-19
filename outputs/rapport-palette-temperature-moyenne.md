# Audit de la palette de température moyenne

Date : 19 octobre 2026  
Statut : palette validée sur le domaine témoin, validation européenne encore requise

## Périmètre

L’audit porte sur les douze normales mensuelles CHELSA 1991–2020 calculées pixel par pixel entre 10° O–8° E et 29–47° N. Cette emprise couvre notamment le Maroc, la péninsule Ibérique, la Méditerranée occidentale et les Alpes.

Seuls les pixels terrestres identifiés par le WBM du Copernicus DEM ont été retenus, soit **3 098 918 pixels** par mois. Les valeurs marines présentes dans les fichiers CHELSA ne participent donc pas aux statistiques.

Palette testée : −30 à 40 °C, avec une échelle fixe pour les douze mois.

## Résultats principaux

- minimum absolu du témoin : **−25,34 °C** en janvier ;
- maximum absolu du témoin : **38,73 °C** en juillet ;
- pixels sous −30 °C : **0 %** pour chacun des douze mois ;
- pixels au-dessus de 40 °C : **0 %** pour chacun des douze mois ;
- médiane spatiale : **7,79 °C** en janvier et **26,38 °C** en juillet ;
- intervalle P1–P99 : **−6,34 à 14,03 °C** en janvier et **12,22 à 37,35 °C** en juillet.

En janvier, **47,82 %** des pixels terrestres se trouvent entre 5 et 10 °C et **30,46 %** entre 10 et 15 °C. La partie de la palette la plus importante pour la recherche d’un climat hivernal doux est donc réellement utilisée et n’est pas comprimée dans une couleur terminale.

En juillet, **43,09 %** des pixels sont entre 25 et 35 °C et **16,19 %** entre 35 et 40 °C. La palette conserve une marge jusqu’à 40 °C sans masquer les fortes chaleurs marocaines.

## Décision

Conserver la palette actuelle pour la **température moyenne** dans la maquette :

- bornes fixes −30 et 40 °C ;
- mêmes correspondances couleur–température pendant les douze mois ;
- aucune adaptation automatique à chaque mois ;
- valeurs inférieures ou supérieures éventuelles placées dans les couleurs terminales, jamais supprimées.

Cette décision est validée uniquement sur le témoin occidental et méditerranéen. Le domaine ne contient ni la Scandinavie ni l’Europe orientale : la borne froide doit être contrôlée sur le domaine européen complet avant la production définitive.

La palette ne doit pas encore être déclarée commune aux températures maximales et minimales. Ces deux variables ont des distributions décalées et nécessitent leur propre audit ; les maximales peuvent notamment dépasser la plage de la température moyenne.

## Fichiers associés

- `analyse-palette-temperature-moyenne.csv` : quantiles et saturations par mois ;
- `occupation-palette-temperature-moyenne.csv` : occupation de chaque intervalle ;
- `analyse-palette-temperature-moyenne.png` : synthèse graphique ;
- `work/validation/analyze_tavg_palette.py` : analyse reproductible ;
- `work/validation/cache/pilot_etape_2b/tavg_01_1991_2020.npy` à `tavg_12_1991_2020.npy` : normales mensuelles mises en cache.
