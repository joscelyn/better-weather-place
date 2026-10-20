# Maquette locale

La maquette affiche les PMTiles produits localement. Aucune donnée lourde n’est copiée dans Git.

Depuis la racine du projet :

```bash
mkdir -p app/public/data
ln -s ../../../work/tiles/1991-2020 app/public/data/1991-2020
cd app
npm install
npm run dev
```

Le lien symbolique est ignoré par Git. L’URL des données pourra plus tard pointer vers un stockage objet ou le VPS sans modifier leur format.

Si `npm install` renvoie `ENOTFOUND registry.npmjs.org`, il suffit de relancer la même commande lorsque la résolution DNS est revenue ; les sources de la maquette ne dépendent pas de cette installation incomplète.
