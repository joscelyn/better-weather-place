# Production des normales de jours de pluie

Date : 19 octobre 2026  
Statut : chaîne validée sur une tuile réelle, en attente du téléchargement complet

`work/build_cerra_rainy_days.py` transforme les précipitations quotidiennes CERRA-Land en douze normales mensuelles du nombre de jours avec au moins 1 mm de pluie.

Pour chaque cellule et chaque mois, le script compte les jours pluvieux séparément pour chacune des trente années 1991–2020, puis calcule la moyenne des trente comptes annuels. Les résultats sont stockés au dixième de jour dans des COG `uint16`.

La production est incrémentale : les tuiles déjà calculées sont enregistrées dans un état de travail. Le script peut donc être relancé pendant ou après plusieurs nuits de téléchargement sans retraiter les archives acquises précédemment. Les douze COG finaux ne sont créés que lorsque toutes les tuiles terrestres attendues sont présentes.

Commande de contrôle :

```bash
work/.venv/bin/python work/build_cerra_rainy_days.py --dry-run
```

Commande finale :

```bash
work/.venv/bin/python work/build_cerra_rainy_days.py --strict
```

La chaîne a été validée sur une tuile alpine de 10 × 10 cellules contenant 10 958 jours. Une cellule de janvier donne 10,57 jours/an avant arrondi et 10,6 jours dans le COG, conformément au facteur 0,1.

Comme pour CHELSA, le masque WBM Copernicus final reste une étape distincte. Les produits intermédiaires portent `water_mask_applied=false`.
