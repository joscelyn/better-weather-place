# Maquette locale

La maquette affiche les PMTiles produits localement. Aucune donnée lourde n’est copiée dans Git.

Depuis la racine du projet :

```bash
mkdir -p app/public/data
ln -s ../../../work/tiles/1991-2020 app/public/data/1991-2020
ln -s ../../derived/1991-2020-masked work/tiles/1991-2020/raw
cd app
npm install
npm run dev
```

Les liens symboliques sont ignorés par Git. Les PMTiles servent l’affichage, tandis que les COG sous `raw/` permettent la lecture exacte du pixel au survol avec des requêtes HTTP partielles. Ces URL pourront plus tard pointer vers un stockage objet ou le VPS sans modifier leur format.
