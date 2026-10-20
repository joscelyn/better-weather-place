# Audit des grilles climatiques de production

Date : 20 octobre 2026  
Période : normales mensuelles 1991–2020

## Périmètre et méthode

L’audit porte sur les 48 COG CHELSA déjà produits (température moyenne, maximales, minimales et précipitations) et les 12 COG SARAH-3 d’ensoleillement. Les statistiques terrestres utilisent le masque Natural Earth 1:10m. Le fichier détaillé `audit-grilles-production.csv` contient les quantiles, extrêmes, coordonnées des maxima et taux de dépassement pour chaque couche et chaque mois.

## Résultats

| Couche | Plage terrestre observée | Occupation hors palette |
|---|---:|---:|
| Température moyenne | −30,7 à 40,5 °C | 0 % hors −40–50 °C |
| Maximales moyennes | −26,9 à 46,5 °C | 0 % hors −40–50 °C |
| Minimales moyennes | −35,2 à 31,8 °C | 0 % hors −40–50 °C |
| Précipitations | 0 à 1 370,5 mm/mois | au plus 0,196 % au-dessus de 400 mm |
| Ensoleillement SARAH-3 | 0 à 404,1 h/mois | 0,036 % au-dessus de 400 h en juillet uniquement |

Le maximum de précipitations se situe à Saint-Kilda, à 57,820694° N et 8,579306° O. Les trente sources annuelles de janvier donnent 674 à 2 374 mm et une moyenne exacte de 1 370,5 mm : il ne s’agit pas d’un fichier corrompu, mais d’un pic orographique très local dans CHELSA. Le 99e percentile mensuel maximal reste à 269,5 mm.

Le maximum d’ensoleillement terrestre atteint 404,1 h en juillet à 36,375437° N et 25,774952° E. Seuls 208 pixels terrestres dépassent 400 h ce mois-là, et aucun autre mois ne dépasse la borne.

## Décision cartographique

Les palettes existantes sont conservées. Étendre les échelles jusqu’aux maxima absolus comprimerait les contrastes utiles sur presque toute la carte. Les valeurs sous ou au-dessus des points terminaux prennent donc la couleur terminale, tandis que le COG conserve la valeur exacte pour l’affichage au clic.

Cette validation ne couvre pas encore la couche des jours de pluie, dont le téléchargement CERRA-Land est en cours, ni le complément d’ensoleillement CERRA au nord de 65° N.

## Reproduction

```bash
work/.venv/bin/python work/validation/audit_production_grids.py
```
