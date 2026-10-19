# Contrat des données cartographiques — version 0.1

Date : 19 octobre 2026  
Statut : contrat de travail pour le lot témoin, sans code d’application

Le fichier `contrat-donnees-v1.json` constitue le manifeste lisible par une future chaîne de production et par l’application. Cette note explique les décisions qui ne doivent pas dépendre de la technologie d’hébergement.

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

Elles restent provisoires jusqu’au calcul des distributions sur tout le domaine. Le lot témoin vérifiera :

- que les valeurs extrêmes ne saturent pas une part excessive de la carte ;
- que les zones recherchées en hiver restent différenciées ;
- que le relief reste lisible sous les couleurs ;
- que les légendes fonctionnent sur écran mobile ;
- que les couleurs restent compréhensibles en cas de déficience de vision des couleurs.

L’audit des douze mois de température moyenne est terminé sur le témoin Maroc–Méditerranée occidentale–Alpes. Aucun des 3 098 918 pixels terrestres mensuels ne sort de la plage −30 à 40 °C ; le minimum observé est −25,34 °C et le maximum 38,73 °C.

L’audit séparé des maximales et minimales montre toutefois que 19,91 % des maximales moyennes dépassent 40 °C en juillet, tandis qu’un seul pixel de minimale descend légèrement sous −30 °C en janvier. La palette thermique commune reçoit donc deux points terminaux à −40 et 50 °C. Toutes les couleurs déjà définies entre −30 et 40 °C restent inchangées : une température donnée conserve ainsi la même couleur dans les cartes moyenne, maximale et minimale.

La palette thermique étendue ne sature aucun pixel du domaine témoin. Elle reste à contrôler sur la Scandinavie et l’Europe orientale avant la production complète.

L’audit des précipitations est également terminé sur les douze normales du témoin. La plage observée va de 0 à 348,1 mm/mois et aucun pixel ne dépasse la borne de 400 mm. Les seuils rapprochés de 5, 10 et 20 mm sont conservés : en janvier, 23,97 % des pixels sont sous 10 mm, et cette proportion atteint 64,37 % en juillet. La borne humide reste à vérifier sur l’Europe atlantique et la Norvège.

Pour les jours de pluie, 906 normales mensuelles issues des points CERRA-Land, des stations GHCN et des normales WMO ont été réunies. Elles vont de 0 à 21,67 jours/mois et aucune ne dépasse l’ancien maximum de palette à 25 jours. Une couleur terminale à 31 jours est tout de même ajoutée, car 31 est la limite physique d’un mois et garantit l’absence de saturation lors de la future production de la grille complète. Les couleurs entre 0 et 25 restent inchangées.

Pour l’ensoleillement, 408 valeurs mensuelles réunissent SARAH-3 sur le domaine principal, CERRA brut au nord de 65° N et les normales WMO correspondantes. Elles vont de 0 à 389,41 h/mois et aucune ne dépasse la borne de 400 heures. La palette 0–400 h est donc conservée sans modification. La grille complète reste à contrôler et l’avertissement nordique demeure obligatoire, car CERRA surestime plusieurs stations malgré une étendue compatible avec la palette.

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

- seuils définitifs des palettes après analyse du domaine complet ;
- format exact de la petite couche d’avertissements côtiers et topographiques ;
- méthode de lecture ponctuelle du COG dans le navigateur, à tester durant la maquette locale.

Le lot témoin 2B a tranché la composition : le relief restera séparé des tuiles climatiques. Il est réutilisable entre les 72 couches, réglable indépendamment et son surcoût de stockage est amorti après environ huit couches sur l’emprise testée.
