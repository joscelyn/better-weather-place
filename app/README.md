# Application React locale

L’application React, construite avec Vite, affiche les PMTiles produits localement. Aucune donnée lourde n’est copiée dans Git.

Depuis la racine du projet :

```bash
mkdir -p app/public/data
ln -s ../../../work/tiles/1991-2020 app/public/data/1991-2020
ln -s ../../derived/1991-2020-masked work/tiles/1991-2020/raw
cd app
npm install
npm run lint
npm run dev
```

Les liens symboliques sont ignorés par Git. Les PMTiles servent l’affichage, tandis que les COG sous `raw/` permettent la lecture exacte du pixel au survol avec des requêtes HTTP partielles. Ces URL pourront plus tard pointer vers un stockage objet ou le VPS sans modifier leur format.

## Thème d’affichage

L’interface suit automatiquement le thème clair ou sombre configuré sur l’appareil via `prefers-color-scheme`. Un changement de préférence pendant que l’application est ouverte est appliqué immédiatement à l’interface, aux contrôles et au fond de carte, sans modifier les palettes des données climatiques.

Le score météo composite se régénère à partir des quatre couches sources, puis se transforme en PMTiles avec :

```bash
work/.venv/bin/python work/build_comfort_score.py
work/.venv/bin/python work/build_climate_pmtiles.py --layers comfort
```

L’URL du dépôt affichée dans la fenêtre À propos peut être définie au build avec `VITE_GITHUB_URL`. Sans cette variable, le bouton ouvre la page d’accueil de GitHub.
