# Contrat des données cartographiques — version 0.2

Date : 19 octobre 2026  
Statut : manifeste canonique partagé par la production et l’application

Le fichier `contrat-donnees-v1.json` constitue le manifeste lisible par une future chaîne de production et par l’application. Cette note explique les décisions qui ne doivent pas dépendre de la technologie d’hébergement.

Depuis la version 0.2, l’application importe ce manifeste à la compilation. Les couches disponibles, palettes, unités, résolutions, zooms, facteurs d’échelle, chemins PMTiles/COG et version de cache ne sont donc plus recopiés dans le code TypeScript. La chaîne PMTiles lit également la liste des couches et les paramètres WebP dans ce même fichier. Les traductions d’interface restent volontairement séparées : elles ne modifient pas le contrat numérique.

## Principes

- Une couche représente une variable et un mois de la normale 1991–2020.
- Le raster PMTiles sert uniquement à dessiner rapidement la carte.
- Le COG contient la valeur numérique faisant foi.
- La couleur affichée ne doit jamais être reconvertie en valeur climatique.
- Les calculs utilisent la précision stockée ; l’arrondi intervient seulement dans l’interface.
- Les mêmes fichiers doivent pouvoir être servis depuis un VPS ou un stockage objet.

## Unités et précision d’affichage

| Couche | Unité affichée | Précision au clic | Résolution annoncée |
|---|---|---:|---:|
| Température moyenne | °C | 0,1 °C | ≈ 1 km |
| Maximales moyennes | °C | 0,1 °C | ≈ 1 km |
| Minimales moyennes | °C | 0,1 °C | ≈ 1 km |
| Précipitations | mm/mois | 0,1 mm | ≈ 1 km |
| Jours de pluie ≥ 1 mm | jours/mois | 0,1 jour | 5,5 km |
| Ensoleillement | h/mois | 1 h | ≈ 5–5,5 km |
| Altitude au clic | m | 1 m | ≈ 30 m |

Les dixièmes de millimètre ou de jour ne signifient pas que la source est exacte à cette échelle : ils évitent seulement des sauts d’arrondi dans une normale calculée sur trente ans. La résolution et les avertissements restent visibles avec la valeur.

## Valeurs stockées

Les températures utilisent un entier signé avec un facteur 0,1. Les quantités positives utilisent un entier non signé avec un facteur 0,1. Cette représentation réduit la taille des COG tout en gardant plus de précision que nécessaire à l’affichage.

Les COG produits pour l’application utilisent EPSG:4326, des blocs de 256 × 256 pixels, une compression DEFLATE et des vues d’ensemble internes. Les données déjà disponibles sur une grille régulière restent alignées sur leur grille source ; tout ré-échantillonnage nécessaire doit être déclaré et contrôlé. La qualité WebP 85 est seulement une hypothèse du lot témoin et pourra être remplacée par du WebP sans perte si les aplats ou les côtes se dégradent.

La valeur sans donnée est réservée et ne doit jamais être confondue avec zéro. Une cellule marine n’est pas une cellule climatique à zéro : elle est transparente et absente des lectures terrestres.

## Avertissements indépendants

La confiance n’est pas réduite à une seule note opaque. Plusieurs avertissements peuvent coexister :

- **cellule côtière mixte** lorsque la terre occupe moins de 80 % de la maille climatique ;
- **relief complexe** lorsque l’altitude du clic diffère d’au moins 250 m de la médiane de la maille, ou lorsque l’écart P90–P10 d’altitude dépasse 300 m ;
- **bord de couverture satellite** entre 63 et 65° N pour l’ensoleillement SARAH-3 ;
- **estimation indicative** au nord de 65° N, où l’ensoleillement provient de CERRA ;
- **point sur l’eau** selon le WBM à 30 m.

Les seuils de relief sont provisoires. Ils seront testés sur les Alpes, les Pyrénées, l’Atlas et Tromsø avant de devenir définitifs.

## Règle côtière

Le WBM à 30 m décide si le clic est sur terre ou sur l’eau. La proportion de terre dans la maille climatique sert seulement à avertir sur le mélange spatial.

- clic terrestre : afficher la valeur de la maille et l’avertissement côtier éventuel ;
- clic sur l’eau à moins de 2 km de la terre : ne rien substituer automatiquement, mais proposer le point terrestre le plus proche ;
- clic sur l’eau au-delà de 2 km : ne pas afficher de valeur terrestre.

Cette règle permet de conserver des lieux comme Essaouira sans prétendre que leur cellule d’environ 1 km représente uniquement la terre.

## Palettes

Les palettes du manifeste sont des points de départ communs aux douze mois. Elles sont fixes par variable afin que la même couleur conserve la même signification en janvier et en juillet.

Les distributions sont désormais contrôlées sur les grilles de production disponibles. La vérification porte notamment sur :

- que les valeurs extrêmes ne saturent pas une part excessive de la carte ;
- que les zones recherchées en hiver restent différenciées ;
- que le relief reste lisible sous les couleurs ;
- que les légendes fonctionnent sur écran mobile ;
- que les couleurs restent compréhensibles en cas de déficience de vision des couleurs.

L’audit des trois températures est terminé sur les 24 524 605 pixels comportant de la terre selon le WBM dans la grille CHELSA de production. Les plages observées sont −30,7 à 40,5 °C pour la moyenne, −26,9 à 46,5 °C pour les maximales et −35,2 à 31,8 °C pour les minimales.

La palette thermique commune est resserrée à −20 à 40 °C pour mieux distinguer les écarts courants à l’écran. Les valeurs plus froides ou plus chaudes prennent la couleur terminale ; leur valeur numérique exacte reste conservée dans le COG. Une température donnée garde la même couleur dans les cartes moyenne, maximale et minimale.

Les valeurs hors plage, si une source future en introduit, doivent prendre la couleur terminale sans modifier la valeur numérique affichée au clic.

L’audit des précipitations est terminé sur la grille CHELSA masquée par le WBM. La plage terrestre va de 0 à 1 370,5 mm/mois. Le maximum, en janvier sur Saint-Kilda, est un pic orographique très local confirmé dans les trente fichiers annuels. Le 99e percentile mensuel ne dépasse pas 273,4 mm et, au mois le plus concerné, seulement 0,201 % des pixels comportant de la terre dépassent 400 mm. La plage 0–400 mm est conservée, mais la progression bleue est remplacée par une palette crème–orange–violet afin de distinguer immédiatement les terres sèches du fond marin ; les rares valeurs supérieures prennent la couleur terminale et leur valeur exacte reste accessible au clic.

Pour les jours de pluie, 906 normales mensuelles issues des points CERRA-Land, des stations GHCN et des normales WMO ont été réunies. Elles vont de 0 à 21,67 jours/mois et aucune ne dépasse l’ancien maximum de palette à 25 jours. Une couleur terminale à 31 jours est tout de même ajoutée, car 31 est la limite physique d’un mois et garantit l’absence de saturation lors de la future production de la grille complète. Les couleurs entre 0 et 25 restent inchangées.

Pour l’ensoleillement, la grille SARAH-3 masquée par le WBM au sud de 65° N va de 0 à 404,4 h/mois. Seuls 606 pixels dépassent 400 h en juillet, soit 0,103 % ; aucun autre mois ne dépasse cette borne. La palette 0–400 h est donc conservée et les rares dépassements prennent la couleur terminale. Le complément CERRA au nord de 65° N reste à produire et l’avertissement nordique demeure obligatoire, car sa validation contre les stations montre une surestimation locale.

## Contrôles exigés pour chaque fichier final

1. douze mois présents pour chaque variable ;
2. période et source identiques au manifeste ;
3. unité, type entier, facteur d’échelle et valeur sans donnée conformes ;
4. aucun pixel climatique visible sur l’eau ;
5. emprise incluse dans `emprise-cerra-officielle.geojson` ;
6. valeurs minimales et maximales plausibles ;
7. correspondance entre cinq points de contrôle du COG et la source amont ;
8. correspondance de la couleur PMTiles avec la valeur et la palette ;
9. attribution et niveau de confiance disponibles ;
10. empreinte de fichier enregistrée pour détecter toute modification accidentelle.

## Relief séparé

Le pilote détaillé sur les Alpes, les Pyrénées et le Haut Atlas a fixé le profil de production :

- relief général dérivé à environ 1 km pour les zooms 3 à 7 ;
- relief détaillé dérivé à environ 90 m pour les zooms 8 à 10 ;
- zoom natif maximal 10, puis simple agrandissement ;
- raster WebP transparent sur l’eau, dans une archive PMTiles commune à toutes les couches climatiques.

La résolution détaillée décrit uniquement l’ombrage topographique. Elle ne doit jamais être présentée comme la résolution de la température, de la pluie ou de l’ensoleillement.

## Décisions encore ouvertes

- contrôle final de la palette des jours de pluie après achèvement de la grille CERRA-Land ;
- format exact de la petite couche d’avertissements côtiers et topographiques ;
- méthode de lecture ponctuelle du COG dans le navigateur, à tester durant la maquette locale.

Le lot témoin 2B a tranché la composition : le relief restera séparé des tuiles climatiques. Il est réutilisable entre les 72 couches, réglable indépendamment et son surcoût de stockage est amorti après environ huit couches sur l’emprise testée.
