# Étape 2 — Architecture de la carte climatique

Date : 19 octobre 2026  
Statut : proposition d’architecture, aucun code d’application commencé

## 1. Résultat recherché

La première version doit ouvrir rapidement sur une carte de l’Europe et du bassin méditerranéen, puis permettre de choisir :

- une variable climatique ;
- un mois de janvier à décembre ;
- un point sur la carte pour lire la valeur, la source, la résolution et le niveau de confiance.

La carte reste l’interface principale. Il n’y a ni classement, ni itinéraire, ni compte utilisateur dans cette version.

Variables retenues :

1. température moyenne ;
2. moyenne des maximales journalières ;
3. moyenne des minimales journalières ;
4. précipitations mensuelles ;
5. jours de pluie avec au moins 1 mm ;
6. heures d’ensoleillement.

L’altitude sert au relief et à la fiche du point, pas comme septième carte climatique.

## 2. Architecture recommandée

### Application cartographique

Utiliser **MapLibre GL JS**, moteur libre adapté aux sources raster, aux cartes vectorielles et au relief. Le fond de carte initial peut utiliser le style clair d’**OpenFreeMap**, sans compte ni clé API. Les routes, frontières et noms de lieux doivent être dessinés au-dessus de la couche climatique pour rester lisibles.

Le choix d’un framework d’interface n’influence pas le pipeline de données. Pour le prototype, une application TypeScript légère construite avec Vite est suffisante ; React ne doit être ajouté que si les composants d’interface deviennent assez nombreux pour le justifier.

### Données climatiques affichées

Pré-calculer les normales mensuelles hors ligne. Le navigateur ne doit jamais télécharger trente années de données ni calculer une normale.

Pour chaque couple variable–mois, produire deux fichiers :

1. un raster **PMTiles** WebP destiné à l’affichage rapide ;
2. un **Cloud Optimized GeoTIFF** contenant les valeurs numériques, destiné au clic et aux contrôles futurs.

Les PMTiles sont des archives uniques interrogeables par requêtes partielles HTTP. Elles évitent de publier des centaines de milliers de petits fichiers et ne nécessitent pas de serveur de tuiles. Le COG conserve, lui, la valeur physique avant coloration et évite de déduire une température ou une pluie depuis la couleur d’un pixel.

Organisation proposée :

```text
data/
  1991-2020/
    tavg/01.pmtiles + 01.tif ... 12.pmtiles + 12.tif
    tmax/...
    tmin/...
    precipitation/...
    rainy-days/...
    sunshine/...
  metadata/
    layers.json
    sources.json
    domain.geojson
```

Le manifeste `layers.json` doit être l’unique contrat entre les données et l’application : unité, plage de couleurs, source, résolution, période, limite géographique, niveau de confiance et URL de chaque mois.

### Diffusion des fichiers

Le choix de l’hébergement est volontairement reporté. L’architecture doit fonctionner sans modification des données dans les deux scénarios envisagés : stockage objet avec site statique, ou hébergement sur le VPS existant.

Le seul contrat technique imposé au futur hébergement est :

- servir les fichiers statiques en HTTPS ;
- accepter les requêtes HTTP partielles `Range` pour PMTiles et COG ;
- fournir les en-têtes CORS si les données et l’application utilisent deux domaines différents ;
- permettre une mise en cache longue des fichiers versionnés.

Aucune base de données ni API dynamique n’est nécessaire pour la première version. Le choix entre solution gérée et VPS sera fait après mesure du poids des données et du trafic réel du prototype.

## 3. Résolution et niveaux de zoom

Les tuiles doivent respecter la résolution réelle des sources :

| Couche | Résolution source | Zoom natif maximal proposé | Comportement au-delà |
|---|---:|---:|---|
| Températures CHELSA | ≈ 1 km | 7 | agrandissement des pixels, sans nouvelle précision |
| Précipitations CHELSA | ≈ 1 km | 7 | agrandissement des pixels |
| Jours de pluie CERRA-Land | 5,5 km | 5 | agrandissement des pixels |
| Ensoleillement SARAH-3/CERRA | ≈ 5–5,5 km | 5 | agrandissement des pixels |
| Relief visuel | ≈ 1 km aux petits zooms, ≈ 90 m aux zooms élevés | 10 | agrandissement au-delà du zoom 10 |

MapLibre peut continuer à zoomer pour examiner une vallée ou une côte, mais l’interface doit afficher la résolution source. Aucun ré-échantillonnage ne doit être présenté comme un gain de précision.

## 4. Construction visuelle de la carte hybride

Ordre de dessin recommandé, du bas vers le haut :

1. fond de carte clair et peu saturé ;
2. couche climatique colorée ;
3. ombrage du relief, léger et multidirectionnel ;
4. côtes, frontières et routes principales ;
5. noms de lieux ;
6. point sélectionné et panneau de valeurs.

Pour limiter le nombre de requêtes, le premier essai doit comparer deux méthodes :

- relief déjà intégré dans les tuiles climatiques ;
- relief séparé, appliqué par MapLibre au-dessus des couleurs.

Le relief séparé est plus flexible. Le relief intégré est potentiellement plus rapide et garantit un rendu constant. Le benchmark de l’étape 2 doit décider entre les deux.

## 5. Interface minimale

Sur ordinateur :

- carte plein écran ;
- sélecteur de variable en haut à gauche ;
- ligne des douze mois en bas ;
- légende verticale compacte ;
- bouton d’opacité ;
- panneau latéral au clic.

Sur mobile :

- même carte plein écran ;
- variable dans un menu compact ;
- mois dans une réglette horizontale ;
- fiche du point sous forme de panneau remontant depuis le bas.

Le panneau d’un point doit afficher au minimum : valeur, unité, altitude, période 1991–2020, source, résolution et éventuel avertissement. Exemples d’avertissement : cellule côtière mixte, relief complexe, ensoleillement nordique indicatif.

Le changement de mois doit précharger uniquement le mois précédent et le mois suivant. Cela rend la réglette fluide sans télécharger les douze cartes.

## 6. Couleurs et comparabilité

Une variable conserve exactement la même échelle pour les douze mois. Sinon, deux couleurs identiques ne représenteraient pas la même température ou la même pluie au fil de l’année.

Recommandations :

- température : palette divergente perceptuellement régulière, centrée autour de 0 °C ;
- précipitations et jours de pluie : palette séquentielle, avec une classe distincte pour les valeurs proches de zéro ;
- ensoleillement : palette séquentielle sombre vers lumineuse ;
- valeurs hors plage : couleurs terminales fixes, jamais une extension automatique mois par mois ;
- eau et absence de données : transparentes et clairement distinguées.

Les seuils définitifs doivent être calculés sur les distributions complètes 1991–2020, pas choisis sur quelques points tests.

Un audit exact des douze normales 1991–2020 est terminé pour les trois variables thermiques sur le domaine témoin Maroc–Méditerranée occidentale–Alpes. La plage initiale −30 à 40 °C convient à la moyenne, mais saturerait 19,91 % des maximales de juillet. Deux couleurs terminales à −40 et 50 °C ont donc été ajoutées sans modifier les correspondances existantes.

L’audit des précipitations confirme ensuite la plage 0–400 mm/mois sur le témoin, avec un maximum observé de 348,1 mm et aucun pixel saturé. Les seuils fins sous 20 mm sont conservés pour différencier les secteurs secs. Le contrôle du domaine européen complet reste nécessaire avant de figer cette palette de production.

L’audit des jours de pluie réunit 906 valeurs mensuelles provenant de CERRA-Land, GHCN et WMO. Le maximum observé est 21,67 jours/mois. Les seuils 0–25 sont conservés et un point terminal à 31 jours, maximum physique, évite toute saturation future. Comme les références ne forment pas un échantillon spatial uniforme, la distribution devra être vérifiée sur la grille complète.

L’audit de l’ensoleillement réunit 408 valeurs mensuelles SARAH-3, CERRA nordique brut et WMO. Le maximum observé est 389,41 h/mois et aucune valeur ne dépasse 400 heures. La palette 0–400 h est conservée ; elle devra être confirmée sur la grille SARAH-3 complète.

## 7. Découpage de l’étape 2

### 2A — Contrat de données

- définir le schéma de `layers.json` ;
- figer les unités et les règles d’arrondi ;
- définir les avertissements et niveaux de confiance ;
- définir les palettes et seuils provisoires.

Livrable : manifeste documenté, sans interface.

### 2B — Petit lot de tuiles témoin — terminé

Produire uniquement :

- température moyenne de janvier et juillet ;
- une zone Alpes–Méditerranée occidentale–Maroc ;
- zooms 3 à 7 ;
- version avec relief intégré et version avec relief séparé.

Mesurer : poids total, taille médiane d’une tuile, requêtes au premier affichage, délai de changement de mois, lisibilité des côtes et du relief.

Livrable : données témoins et rapport de benchmark. Toujours aucun produit complet.

Résultat obtenu : cinq archives PMTiles et deux COG ont été produits sur 10° O–8° E et 29–47° N. Les deux variantes présentent une qualité visuelle proche. Le relief séparé est amorti après environ huit couches et a été retenu pour la maquette.

Le test complémentaire sur les Alpes, les Pyrénées et le Haut Atlas fixe le relief final à environ 1 km pour les zooms 3–7, puis environ 90 m pour les zooms 8–10. L’archive témoin haute résolution contient 679 tuiles et pèse 6,37 Mio. Le zoom natif 10 donne déjà environ 105 à 130 m par pixel d’écran dans ces régions ; le zoom 11 n’est donc pas retenu.

### 2C — Maquette interactive locale

Construire ensuite la carte minimale avec une seule variable et deux mois. Valider les interactions et le rendu mobile avant de générer les 72 couches mensuelles.

### 2D — Production des données complètes

Seulement après validation du témoin : produire les six variables et les douze mois, contrôler automatiquement les valeurs, les métadonnées et les trous spatiaux, puis publier les archives.

## 8. Critères de réussite avant production complète

- première carte utile visible en moins de deux secondes sur une connexion correcte ;
- changement de mois perçu comme immédiat lorsque le voisin a été préchargé ;
- moins de 2 Mo transférés pour le premier écran climatique, fond de carte exclu ;
- aucune valeur climatique affichée sur l’eau ;
- valeur au clic conforme au COG source ;
- relief et littoral lisibles à Annecy, Chamonix, Font-Romeu, Essaouira et Ifrane ;
- source, période et résolution accessibles sans quitter la carte ;
- fonctionnement complet sans clé d’API payante.

## 9. Décision recommandée

Retenir pour le prototype : **MapLibre GL JS + OpenFreeMap + PMTiles raster + COG**, sans décision d’hébergement à ce stade.

Cette combinaison limite le nombre de composants et reste portable entre un stockage objet et le VPS. Son risque principal est le poids des 72 archives cartographiques ; c’est pourquoi la prochaine action doit être le lot témoin 2B, et non la génération complète des données.

## 10. Références techniques vérifiées

- [MapLibre GL JS — sources raster](https://maplibre.org/maplibre-gl-js/docs/API/classes/RasterTileSource/) ;
- [MapLibre GL JS — ombrage du relief](https://maplibre.org/maplibre-gl-js/docs/examples/add-a-hillshade-layer/) ;
- [PMTiles raster avec MapLibre](https://docs.protomaps.com/pmtiles/maplibre) ;
- [OpenFreeMap — démarrage rapide](https://openfreemap.org/quick_start/) ;
