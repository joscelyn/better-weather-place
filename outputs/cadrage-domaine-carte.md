# Cadrage du domaine cartographique

Date : 19 octobre 2026  
Statut : décision proposée pour la première version, Canaries différées

## Domaine de données

La carte hybride doit utiliser comme limite technique commune l’emprise native de CERRA. C’est la plus petite emprise parmi les sources principales et elle contient l’Europe continentale, l’Islande, l’ensemble du bassin méditerranéen, l’Afrique du Nord et une grande partie de l’Atlantique proche.

L’emprise est un carré de 1 069 × 1 069 cellules dans la projection Lambert conforme conique de CERRA, avec un pas de 5 500 m. Son contour n’est pas un rectangle en latitude/longitude. Les extrêmes calculés à partir du GRIB officiel sont :

- longitude : environ 58,18° O à 74,18° E ;
- latitude : environ 20,26° N à 75,37° N ;
- milieu du bord ouest : 43,23° N, 29,60° O ;
- milieu du bord est : 43,23° N, 45,60° E ;
- milieu du bord sud : 24,36° N, 8,00° E ;
- milieu du bord nord : 75,37° N, 8,00° E.

Le fichier `emprise-cerra-officielle.geojson` contient le contour courbe échantillonné dans le système WGS84. Il doit servir de masque de disponibilité pour les jours de pluie et pour l’ensoleillement nordique, sans promettre de données hybrides complètes au-delà.

Cette limite inclut les Canaries au bord sud-ouest, mais leur traitement spécifique reste différé. Elle n’inclut pas le Svalbard, situé au nord du domaine : l’expression « Europe entière » désigne donc, pour la première version, l’Europe couverte par CERRA et accessible de façon homogène par toutes les variables retenues.

## Zone présentée à l’utilisateur

La carte peut rester librement navigable, mais son cadrage initial doit montrer l’Europe et la Méditerranée, pas l’intégralité du vaste domaine CERRA. La disponibilité des couches climatiques est limitée par le contour GeoJSON et par le masque terre/eau WBM.

Règles proposées :

1. afficher les données uniquement sur terre, selon le WBM Copernicus à 30 m agrégé à la résolution de chaque couche ;
2. conserver les mers comme fond cartographique sans valeurs climatiques ;
3. ne pas découper arbitrairement les pays situés aux marges : le contour CERRA est la seule limite externe ;
4. traiter les Canaries comme une sous-zone désactivée dans la première version, sans empêcher leur ajout ultérieur ;
5. signaler clairement toute variable indisponible ou moins fiable près des limites de sa source.

## Transition de l’ensoleillement à 65° N

SARAH-3 reste la référence au sud de 65° N. Le contrôle contre les stations WMO montre que CERRA surestime généralement l’ensoleillement au nord et qu’une correction multiplicative uniforme est instable. Un mélange numérique entre les deux sources créerait des valeurs artificielles et n’est donc pas retenu.

Pour la première version :

- jusqu’à 65° N : afficher SARAH-3 ;
- au nord de 65° N : afficher CERRA brut comme estimation indicative ;
- matérialiser la limite de source discrètement dans la légende et dans la fiche du point ;
- afficher une confiance réduite pour l’ensoleillement CERRA nordique ;
- utiliser la même échelle de couleurs des deux côtés, sans interpolation destinée à masquer la coupure ;
- évaluer visuellement la couture sur des tuiles tests avant publication.

Cette solution privilégie la traçabilité des données. Une transition lissée ne pourra être ajoutée qu’après validation locale sur davantage de stations, sans modifier artificiellement les normales observées.
