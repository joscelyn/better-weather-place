# Production des normales d’ensoleillement SARAH-3

Date : 19 octobre 2026

## Commande CM SAF à créer

Dans le WUI CM SAF, choisir exactement :

- groupe : **Climate Data Records** ;
- famille : **SARAH ed. 3.0** ;
- produit : **SDU — Sunshine Duration** ;
- résolution temporelle : **Monthly** ;
- statistique : **Sum** ;
- grille : **Latitude/longitude grid, 0.05° × 0.05°** ;
- début : **1991-01-01** ;
- fin : **2020-12-01** (le produit mensuel est daté au premier jour du mois) ;
- format : **NetCDF4** ;
- type : commande unique, et non « standing order ».

La fiche officielle annonce 4,0 Go pour 1983–2026. Par prorata, les 360 mois de
1991–2020 représentent environ **2,7 Go** sur le disque Meteosat complet. Si le WUI
propose l’adaptation de domaine, demander `N 65`, `S 25`, `W -25`, `E 45` en
conservant la maille native de `0,05°`. Ce rectangle contient aussi les Canaries,
mais aucun traitement spécifique ne leur est appliqué et elles resteront hors du
masque prioritaire de la première version.

## Préparer les fichiers reçus

Décompresser tous les fichiers NetCDF dans :

```text
work/downloads/sarah3-monthly/
```

Les sous-dossiers sont acceptés. Le script détecte les extensions `.nc` et `.nc4`,
la variable `SDU`, les coordonnées et les dates à partir des métadonnées NetCDF ;
il ne dépend donc pas du nom attribué aux fichiers par la commande.

Contrôler que les 360 couples année–mois sont présents, sans produire de raster :

```bash
work/.venv/bin/python work/build_sarah_normals.py --dry-run
```

Puis construire les douze normales mensuelles :

```bash
caffeinate -i work/.venv/bin/python work/build_sarah_normals.py
```

## Résultat et contrôles

Les COG sont écrits dans `work/derived/1991-2020/sunshine/01.tif` à `12.tif`.
Chaque pixel est la moyenne des trente sommes mensuelles 1991–2020, en heures par
mois. Le stockage utilise un entier non signé, un facteur d’échelle de `0,1 h` et
la valeur sans donnée `65535`.

Par défaut, un pixel doit posséder les trente années pour être conservé. Le script :

- refuse les mois absents ou en double ;
- refuse une grille qui change entre les fichiers ;
- convertit automatiquement les secondes ou minutes en heures si nécessaire ;
- refuse les valeurs hors de la plage physique 0–744 h/mois ;
- génère des aperçus internes, une empreinte SHA-256 et un fichier JSON par mois ;
- ignore les mois déjà terminés et valides lors d’une reprise.

Si la source présente exceptionnellement des années manquantes pour quelques
pixels, `--minimum-valid-years 24` permet une normale partielle. Cette option ne
doit être utilisée qu’après examen du nombre et de la localisation des pixels
concernés.
