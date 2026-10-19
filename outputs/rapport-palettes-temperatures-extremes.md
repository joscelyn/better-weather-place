# Audit des palettes de températures maximales et minimales

Date : 19 octobre 2026  
Statut : extension de la palette validée sur le domaine témoin

## Périmètre

L’analyse utilise les normales CHELSA 1991–2020 des moyennes mensuelles des maximales et minimales journalières. Les douze mois et les trente années ont été calculés sur l’emprise 10° O–8° E et 29–47° N, puis filtrés avec le masque terrestre WBM.

Chaque série mensuelle contient **3 098 918 pixels terrestres**. La palette initialement testée pour la température moyenne allait de −30 à 40 °C.

## Maximales moyennes

- plage observée : **−21,74 à 45,13 °C** ;
- pixels au-dessus de 40 °C : **0,77 % en juin**, **19,91 % en juillet** et **14,02 % en août** ;
- maximum du 99e percentile : **43,27 °C** en juillet ;
- aucun pixel au-dessus de 50 °C.

Une borne terminale à 40 °C écraserait donc une partie importante des contrastes estivaux au Maroc. Ce n’est pas un cas extrême isolé : près d’un pixel sur cinq serait concerné en juillet.

## Minimales moyennes

- plage observée : **−30,03 à 29,21 °C** ;
- sous −30 °C : **un pixel**, soit environ **0,000032 %**, uniquement en janvier ;
- aucun pixel sous −40 °C.

La borne −30 °C suffit presque exactement au domaine témoin. Une marge jusqu’à −40 °C est néanmoins justifiée pour le futur domaine européen, qui inclura la Scandinavie et des secteurs plus continentaux absents de ce test.

## Décision

Employer une seule correspondance couleur–température pour les trois variables thermiques, afin qu’une même température ait toujours la même couleur.

Les points d’arrêt déjà validés entre −30 et 40 °C sont conservés sans modification. Deux couleurs terminales sont ajoutées :

- **−40 °C : `#171747`** ;
- **50 °C : `#31000f`**.

La palette commune devient donc −40 à 50 °C, mais son cœur −30 à 40 °C conserve exactement les couleurs du premier pilote. Cette extension supprime toute saturation sur les températures moyenne, maximale et minimale du domaine témoin.

Les bornes resteront à vérifier sur le domaine européen complet avant la production finale, particulièrement pour les minimales nordiques. Il ne faudra jamais recalculer automatiquement l’échelle selon le mois ou la variable.

## Fichiers associés

- `analyse-palettes-temperatures-extremes.csv` : quantiles et saturations des 24 séries ;
- `analyse-palettes-temperatures-extremes.png` : synthèse graphique ;
- `work/validation/analyze_temperature_extrema_palettes.py` : calcul reproductible ;
- normales mises en cache localement sous `work/validation/cache/pilot_etape_2b/`.
