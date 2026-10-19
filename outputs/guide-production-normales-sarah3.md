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

La commande `ORD70729`, soumise le 19 octobre 2026 sans découpe de domaine,
confirme un volume de **2,8 Go** pour les 360 mois. Le pipeline effectuera la
découpe `N 65`, `S 25`, `W -25`, `E 45` localement en conservant la maille native
de `0,05°`. Ce rectangle contient aussi les Canaries, mais aucun traitement
spécifique ne leur est appliqué et elles resteront hors du masque prioritaire de
la première version.

## Préparer les fichiers reçus

La livraison de `ORD70729` contient une archive unique :

- fichier : `ORD70729.tar` ;
- taille : `2 971 361 280` octets, soit 2,8 Gio ;
- contenu annoncé : 360 produits ;
- MD5 : `b253bef2a734e52a4417c1b16a32d5ae`.

Son lien HTTPS est enregistré dans un fichier local ignoré par Git :

```text
work/downloads/sarah3-ORD70729-urls.txt
```

Le mot de passe n’est enregistré nulle part. Le téléchargeur le demande sans
l’afficher au lancement, puis vérifie la taille exacte et le MD5 officiel avant
de valider l’archive. Vérifier le manifeste, puis lancer :

```bash
work/.venv/bin/python work/download_sarah_order.py \
  --url-file work/downloads/sarah3-ORD70729-urls.txt \
  --dry-run

caffeinate -i work/.venv/bin/python work/download_sarah_order.py \
  --url-file work/downloads/sarah3-ORD70729-urls.txt \
  2>&1 | tee work/downloads/sarah3-ORD70729.log
```

Le téléchargeur reprend les fichiers `.part`, effectue six tentatives espacées,
contrôle l’espace disque et vérifie le contenu NetCDF, ZIP ou TAR avant de marquer
un fichier comme terminé. Les paramètres des URL ne sont jamais copiés dans les
journaux ni dans les fichiers de métadonnées.

Après le téléchargement, contrôler puis extraire l’archive de manière reprenable :

```bash
work/.venv/bin/python work/extract_sarah_order.py --dry-run
work/.venv/bin/python work/extract_sarah_order.py
```

Le script refuse les liens et chemins TAR dangereux, exige exactement 360 NetCDF,
contrôle leur taille extraite et vérifie la présence d’une variable de durée
d’ensoleillement dans chaque fichier. Tous les NetCDF se trouvent ensuite,
directement ou dans des sous-dossiers, sous :

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
