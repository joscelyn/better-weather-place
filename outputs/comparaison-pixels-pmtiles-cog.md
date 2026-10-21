# Comparaison PMTiles / COG

Contrôle déterministe de blocs 3 × 3 pixels autour de six lieux. La valeur COG est ré-échantillonnée exactement comme lors de la génération des tuiles, puis convertie avec la palette du contrat. Une petite différence RGB est normale à cause de la compression WebP avec pertes.

Résultat : **51/51 pixels conformes**, tolérance maximale de 12 niveaux par canal.

| Lieu | Couche | Mois | Valeur COG centrale | RGB attendu | RGB PMTiles | Écart max | Écart moyen | Statut |
|---|---:|---:|---:|---|---|---:|---:|---|
| Lisbonne | comfort | 01 | 54.923 | 226,205,96 | 225,206,96 | 3 | 1.05 | OK |
| Annecy | tavg | 01 | 1.835 | 235,247,227 | 235,247,229 | 4 | 1.33 | OK |
| Athènes | tmax | 07 | 33.448 | 173,7,38 | 173,6,37 | 5 | 1.74 | OK |
| Stockholm | tmin | 01 | -3.508 | 187,225,237 | 187,226,238 | 2 | 0.70 | OK |
| Valence | precipitation | 10 | 71.369 | 199,87,76 | 201,87,78 | 2 | 0.78 | OK |
| Marrakech | sunshine | 07 | 347.745 | 244,155,50 | 241,156,48 | 5 | 2.44 | OK |

Le détail pixel par pixel est dans `outputs/comparaison-pixels-pmtiles-cog.csv`.
