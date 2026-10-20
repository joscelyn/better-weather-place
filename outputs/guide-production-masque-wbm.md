# Production du masque terre/eau WBM

Date : 20 octobre 2026

## Source et inventaire

Le masque utilise le Water Body Mask du Copernicus DEM GLO-30. Ses classes sont 0 terre, 1 océan, 2 lac et 3 rivière. Les COG publics sont accessibles sans compte sur le stockage S3 Copernicus.

Le catalogue du domaine 25° O–45° E et 25–72° N contient 2 138 tuiles, Canaries exclues. Leur volume total est de 148 215 185 octets, soit environ 141 Mio. Les tailles et ETag MD5 sont enregistrés dans `catalogue-wbm-copdem.csv`.

## Commandes

```bash
work/.venv/bin/python work/catalog_copdem_wbm.py
work/.venv/bin/python work/download_copdem_wbm.py --hours 2 --workers 4
work/.venv/bin/python work/build_wbm_masks.py
work/.venv/bin/python work/apply_wbm_masks.py
```

Le téléchargement est reprenable, conserve les fichiers partiels et valide chaque tuile avec sa taille et son MD5. Le lanceur nocturne exécute désormais cette petite phase avant le téléchargement CERRA-Land.

## Produits dérivés

Quatre COG de fraction terrestre sont créés dans `work/derived/1991-2020/masks/` :

- `wbm-land-fraction-1km.tif` : grille intermédiaire à 120 pixels par degré ;
- `chelsa-land-fraction.tif` : alignée exactement sur les COG CHELSA ;
- `sarah-land-fraction.tif` : alignée exactement sur SARAH-3 ;
- `cerra-land-fraction.tif` : alignée exactement sur la grille d’assemblage CERRA.

La fraction est stockée dans un entier `uint16` avec un facteur 0,0001 : 0 représente une maille entièrement aquatique et 10 000 une maille entièrement terrestre. Les classes lac et rivière sont considérées comme de l’eau.

## Deux usages distincts

La fraction terrestre de la maille climatique sert à masquer les cellules entièrement aquatiques et à signaler les cellules mixtes. Une cellule ayant une fraction non nulle conserve sa valeur climatique, même si elle contient beaucoup d’eau.

La classe WBM native à environ 30 m reste la référence pour un clic précis. Ainsi, un clic marin à l’intérieur d’une maille climatique mixte n’affichera pas de valeur terrestre ; il pourra proposer la terre la plus proche lorsqu’elle est située à moins de 2 km.

Les Canaries n’étant pas prioritaires, leurs tuiles ne figurent pas au catalogue et leur fraction terrestre reste à zéro dans les produits actuels.

## COG climatiques publiables

`work/apply_wbm_masks.py` conserve les sources non masquées et écrit les copies publiables dans `work/derived/1991-2020-masked/`. Une maille est conservée dès que sa fraction terrestre est supérieure à zéro. Sous 80 % de terre, elle reçoit l’indicateur de cellule côtière mixte dans les métadonnées.

Les 60 COG disponibles représentent 737 691 647 octets après masquage. Leur structure, leurs métadonnées et leurs SHA-256 ont été contrôlés avec :

```bash
work/.venv/bin/python work/validate_production_cogs.py \
  --input work/derived/1991-2020-masked \
  --inventory outputs/inventaire-cogs-production-masques.csv \
  --summary outputs/validation-cogs-production-masques.json \
  --expect-water-mask
```
