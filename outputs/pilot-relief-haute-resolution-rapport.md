# Pilote de relief haute résolution

Date : 19 octobre 2026  
Statut : test ciblé terminé, aucun code d’application

## Objectif

Déterminer la résolution utile et le zoom maximal de la couche de relief séparée, sans générer encore le domaine complet. Trois secteurs contrastés ont été testés :

- Alpes : 5–8° E, 44–47° N ;
- Pyrénées : 2° O–4° E, 41–44° N ;
- Haut Atlas : 10–5° O, 29–33° N.

Le relief provient du Copernicus DEM GLO-30 et le masque terre/eau de son WBM. Pour limiter le volume du pilote tout en restant cohérent avec l’affichage visé, le DEM a été lu à **1 200 pixels par degré**, soit environ **90 m**, puis transformé en ombrage. Les tuiles finales sont des WebP 256 × 256 aux zooms 8 à 10.

## Résultats

- archive : `pilot-etape-2b/relief-separate-90m-montagnes.pmtiles` ;
- format : PMTiles version 3, raster WebP ;
- zooms : 8 à 10 ;
- nombre de tuiles : **679** ;
- taille de l’archive : **6,37 Mio** ;
- taille médiane d’une tuile : **9,0 Kio** ;
- 90e percentile : **17,5 Kio** ;
- opacité de l’ombrage encodée : 88/255, avec eau transparente.

Des tuiles réelles ont été relues dans l’archive à Chamonix, Font-Romeu et au Toubkal. Elles sont bien décodables en 256 × 256, contiennent l’opacité attendue et conservent le masque d’eau.

La durée de construction observée est de 7 min 15 s avec un cache initialement incomplet. Cette mesure décrit le pipeline hors ligne ; elle n’a pas d’effet sur le temps de chargement de l’application.

## Lecture visuelle

La comparaison `pilot-relief-haute-resolution.png` montre un gain net par rapport au relief ramené à environ 1 km :

- les vallées étroites et les crêtes secondaires des Alpes sont mieux séparées ;
- la continuité de la chaîne pyrénéenne est plus fine sans rendre les plaines bruyantes ;
- les structures parallèles de l’Atlas et les transitions vers les plateaux sont mieux définies ;
- le WBM conserve des limites côtières propres et transparentes.

Ce gain est utile pour comprendre pourquoi deux lieux proches peuvent avoir des climats différents, mais il ne change pas la résolution des données climatiques. L’interface devra continuer à annoncer environ 1 km pour CHELSA et 5–5,5 km pour CERRA/SARAH.

## Décision

Retenir une couche de relief séparée et multi-résolution :

- zooms 3 à 7 : relief général calculé à environ 1 km ;
- zooms 8 à 10 : relief calculé depuis le DEM ré-échantillonné à environ 90 m ;
- zoom maximal natif : **10** ;
- au-delà du zoom 10 : agrandissement de la dernière tuile, sans prétendre à une précision supplémentaire.

À 31–46° N, un pixel d’écran au zoom 10 représente environ 105 à 130 m. Le relief à 90 m est donc suffisant. Un zoom natif 11 multiplierait approximativement par quatre le nombre de tuiles de ce niveau tout en dépassant le besoin d’une carte climatique.

Les **6,37 Mio** mesurés concernent uniquement les trois fenêtres montagneuses, soit 47 degrés carrés d’emprise brute. Ils ne doivent pas être extrapolés directement au domaine complet, dont la part de mer et la densité de détails varient. Le poids complet sera mesuré lors de la production du relief, avant celle des 72 couches climatiques.

## Fichiers associés

- `pilot-relief-haute-resolution.png` : comparaison visuelle 1 km / 90 m ;
- `pilot-relief-haute-resolution-metriques.csv` : métriques machine ;
- `pilot-etape-2b/relief-separate-90m-montagnes.pmtiles` : archive témoin ;
- `work/validation/build_high_resolution_relief_pilot.py` : chaîne reproductible.
