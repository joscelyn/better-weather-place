# Audit des licences et attributions

Audit effectué le 21 octobre 2026 à partir des pages officielles des producteurs et des sources réellement utilisées par l’application.

| Source | Usage dans le projet | Licence / exigence | État après correction |
|---|---|---|---|
| CHELSA-monthly V2.1 | températures et précipitations | CC0 1.0 ; citation scientifique recommandée, sans attribution juridiquement obligatoire | Conforme : source, version et lien affichés ; citation conservée dans le contrat |
| CM SAF SARAH-3 | durée d’ensoleillement et score composite | CC BY 4.0, titulaire EUMETSAT ; attribution et indication des modifications | Conforme : titulaire, licence et caractère modifié ajoutés au dialogue ; citation et DOI dans le contrat |
| CERRA-Land | futurs jours de pluie (pas encore publié dans l’app) | CC BY ; citation CDS, DOI 10.24381/cds.a7f3cd0b | Prêt avant publication : attribution et citation inscrites dans le contrat ; à afficher lorsque la couche sera activée |
| Copernicus DEM GLO-30 / WBM | masque terre/eau appliqué aux rasters climatiques | licence WorldDEM-30 ; avis imposé pour les données adaptées, plus clause de non-responsabilité | Conforme : avis d’adaptation et clause de non-responsabilité ajoutés dans l’app et dans le contrat |
| OpenFreeMap / OpenMapTiles / OpenStreetMap | fond cartographique | attribution requise ; données OSM sous ODbL | Choix produit : attributions regroupées dans la popup, sans contrôle MapLibre permanent. À revalider juridiquement avant publication, car les recommandations OSM privilégient une attribution visible sur la carte |
| Mapzen Terrain Tiles sur AWS | ombrage du relief | attributions variables selon les sources composées dans chaque tuile | Partiel : lien vers la liste officielle ajouté et attribution native réactivée. Avant publication, soit afficher la liste complète, soit remplacer ce service par un relief dont la provenance est unique et plus simple à attribuer |

## Décision de publication

Les données climatiques actuellement visibles sont publiables avec les attributions présentes. Une action reste prudente avant une ouverture publique :

1. résoudre l’attribution composite Mapzen, idéalement en remplaçant le relief distant par un relief produit à partir d’une source unique documentée.

## Sources officielles contrôlées

- CHELSA-monthly : https://www.chelsa-climate.org/datasets/chelsa_monthly
- SARAH-3 / CM SAF : https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003
- CERRA-Land / CDS : https://cds.climate.copernicus.eu/datasets/reanalysis-cerra-land
- Copernicus DEM GLO-30 : https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf
- OpenFreeMap : https://openfreemap.org/
- OpenStreetMap : https://www.openstreetmap.org/copyright
- Mapzen Terrain Tiles : https://github.com/tilezen/joerd/blob/master/docs/attribution.md
