# Étape 1 — Validation des données climatiques

Date de l’analyse : 19 octobre 2026  
Statut : étape de sélection des sources terminée ; contrôles stationnels et cartographiques réalisés ; réserves de publication documentées

## 1. Objectif

Valider une combinaison de sources permettant de publier une carte climatique mensuelle couvrant l’Europe entière, le bassin méditerranéen et les Canaries, avec une représentation crédible des côtes et du relief.

Variables prévues :

- température moyenne ;
- moyenne des maximales journalières ;
- moyenne des minimales journalières ;
- précipitations mensuelles ;
- nombre de jours avec au moins 1 mm de précipitation ;
- heures d’ensoleillement ;
- altitude.

La période de référence privilégiée reste 1991–2020. Une période récente 1996–2025 sera évaluée séparément.

## 2. Sources contrôlées

### CHELSA-monthly V2.1

- Résolution : 30 secondes d’arc, environ 1 km.
- Période : janvier 1979 à décembre 2021.
- Variables utiles : `tas`, `tasmax`, `tasmin`, `pr`.
- Licence : CC0 1.0.
- Format : Cloud Optimized GeoTIFF public.
- DOI : [10.16904/envidat.686](https://doi.org/10.16904/envidat.686).

L’accès partiel aux COG a été vérifié. Il est possible de lire uniquement les blocs correspondant aux zones affichées, sans télécharger les rasters mondiaux complets.

### CERRA et CERRA-Land

- Résolution native : 5,5 km.
- Période : septembre 1984 à aujourd’hui ; CERRA-Land est actuellement documenté jusqu’à décembre 2025.
- Couverture : Europe, Afrique du Nord, Atlantique et est de l’Europe jusqu’à l’Oural.
- Licence : CC-BY-4.0.
- DOI CERRA : [10.24381/cds.622a565a](https://doi.org/10.24381/cds.622a565a).
- DOI CERRA-Land : [10.24381/cds.a7f3cd0b](https://doi.org/10.24381/cds.a7f3cd0b).

CERRA contient les températures et le rayonnement direct nécessaires pour calculer une durée d’ensoleillement. CERRA-Land fournit une analyse quotidienne des précipitations, adaptée au calcul du nombre de jours de pluie.

Le compte Copernicus CDS est configuré, les licences CERRA et CERRA-Land sont acceptées et l’accès API officiel a été testé avec succès le 18 octobre 2026. Un premier fichier CERRA officiel a été téléchargé. Pour la première comparaison ponctuelle, des séries CERRA redistribuées par l’adaptateur historique Open-Meteo ont été utilisées. Cette voie est uniquement un outil de validation et ne sera pas une dépendance de l’application.

### SARAH-3

- Résolution : 0,05°, environ 5 km.
- Période : 1983 à aujourd’hui.
- Couverture : 65° O–65° E et 65° S–65° N.
- Variable utilisée : durée d’ensoleillement, en heures.
- Politique de données : gratuite et sans restriction selon EUMETSAT.
- DOI : [10.5676/EUM_SAF_CM/SARAH/V003](https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003).

Le service officiel [EUMETSAT Climate Anomalies and Normals](https://can.eumetsat.int/) fournit directement les douze normales mensuelles 1991–2020. L’accès ponctuel et cartographique WMS a été vérifié.

### Copernicus DEM GLO-30

- Type : modèle numérique de surface, incluant ponctuellement végétation, bâtiments et infrastructures.
- Résolution : 1 seconde d’arc, environ 30 m.
- Couverture : mondiale.
- Accès testé : Cloud Optimized GeoTIFF public, lecture partielle sans compte AWS.
- Licence : gratuite pour le grand public, avec mention de source obligatoire.
- DOI : [10.5270/ESA-c5d3d65](https://doi.org/10.5270/ESA-c5d3d65).

Les 18 points ont été lus directement dans les COG publics. Les résultats distinguent correctement les reliefs : 449 m à Annecy, 1 040 m à Chamonix, 4 805 m au point du Mont-Blanc, 1 756 m à Font-Romeu et 3 678 m au point du Teide. Le point côtier d’Essaouira tombe à 0 m, ce qui confirme qu’un clic proche du rivage devra être associé explicitement à une cellule terrestre.

### NOAA GHCN-Daily

- Type : observations quotidiennes de stations météorologiques contrôlées par NOAA/NCEI.
- Couverture : mondiale, variable selon les pays et les périodes.
- Variables utilisées : température maximale, température minimale et précipitations quotidiennes.
- Accès : téléchargement HTTPS gratuit, sans clé API.
- Documentation : [GHCN-Daily](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily).

Les inventaires officiels et les séries de 23 stations candidates ont été contrôlés. Pour chaque point, la sélection tient compte de la distance, de l’écart d’altitude et de la couverture effective des trois variables sur 1991–2020. Les valeurs portant un drapeau qualité NOAA sont exclues avant le calcul des normales.

### Normales climatiques WMO/NCEI 1991–2020

- Type : normales mensuelles observées communiquées par les services météorologiques nationaux à l’Organisation météorologique mondiale.
- Variables utilisées : températures moyenne, maximale et minimale (`TAVG`, `TMAX`, `TMIN`), précipitations (`PRCP`), jours avec au moins 1 mm (`DP01`) et ensoleillement (`TSUN`).
- Filtre de qualité retenu : normales calculées avec au moins 24 années sur les 30 de la période.
- Accès : fichiers composites CSV publics maintenus par NOAA/NCEI.
- Documentation : [WMO Climate Normals](https://www.ncei.noaa.gov/products/wmo-climate-normals).

Dix stations complètes entre 65 et 70° N sont disponibles dans le domaine nordique étudié : Akureyri, Luleå, Sodankylä, Utsjoki, Kandalaksha, Murmansk et quatre stations suédoises autour de Kiruna. Elles permettent de contrôler directement CERRA au nord de la limite de SARAH-3, sans extrapoler une validation faite plus au sud. Le même jeu fournit 25 stations marocaines pour les températures et les jours de pluie, ainsi que 24 stations pour les précipitations. Il comble la faiblesse de GHCN-Daily au Maroc.

## 3. Échantillon réalisé

### Points tests

18 points ont été répartis dans sept familles de terrain :

- Alpes : Annecy, Chamonix, Mont-Blanc ;
- Pyrénées : Perpignan, Font-Romeu ;
- Portugal et Galice : Porto, Santiago, Faro ;
- Andalousie : Malaga, Grenade ;
- Maroc : Essaouira, Marrakech, Ifrane ;
- Canaries : La Laguna, Costa Adeje, Teide ;
- Nord : Reykjavik, Tromsø.

### Données extraites

- 240 rasters CHELSA : quatre variables, janvier et juillet, 1991–2020 ;
- normales SARAH-3 : douze mois, 1991–2020, pour les 18 points ;
- séries quotidiennes CERRA : première comparaison homogène 1991–2005 pour les 18 points.
- test officiel CDS : température CERRA du 1er janvier 1991 à 00 h, fichier GRIB de 2,2 Mo correctement ouvert ; grille Lambert conforme de 1 069 × 1 069 cellules, résolution native 5,5 km.
- séries officielles CERRA-Land : précipitations quotidiennes 1991–2020 pour les 18 points, soit 197 244 journées et 216 normales mensuelles ; aucun jour manquant.
- séries NOAA GHCN-Daily : sélection et contrôle de stations pour les 18 points, puis calcul de 216 normales mensuelles stationnelles sur 1991–2020.
- 1 440 rasters CHELSA supplémentaires lus aux coordonnées exactes des 16 stations uniques : quatre variables, douze mois et trente années.
- normales WMO/NCEI d’ensoleillement : 120 couples station–mois sur dix stations situées entre 65 et 70° N, comparés à CERRA sur la même période 1991–2020.
- normales WMO/NCEI marocaines : 1 186 couples valides station–mois pour les températures et les précipitations, sur 25 stations ; extraction CHELSA effectuée aux coordonnées exactes des stations.
- jours de pluie WMO/NCEI marocains : 300 couples station–mois sur 25 stations, comparés à CERRA-Land officiel sur 1991–2020.

La comparaison CERRA 1991–2005 reste provisoire pour les températures et l’ensoleillement dérivé. Elle sert à tester les différences spatiales entre une maille régionale de 5,5 km et CHELSA à environ 1 km. Pour la pluie et les jours de pluie, elle est désormais remplacée par l’extraction officielle CERRA-Land 1991–2020 décrite ci-dessus.

## 4. Résultats préliminaires

### Températures

Sur janvier et juillet, aux 18 points :

- écart absolu moyen CHELSA–CERRA : **1,67 °C** ;
- écart médian signé : **+0,48 °C** pour CHELSA ;
- 90 % des écarts absolus sont inférieurs à **3,32 °C** ;
- les plus fortes divergences se situent dans les reliefs extrêmes.

Exemples :

- Chamonix en juillet : CHELSA est environ **6,9 °C** plus chaud que la cellule CERRA brute ;
- Mont-Blanc en janvier : CHELSA est environ **9,0 °C** plus froid que CERRA ;
- Mont-Blanc en juillet : CHELSA est environ **4,9 °C** plus froid.

Ces écarts ne signifient pas automatiquement que CHELSA est exact au dixième de degré. Ils montrent surtout qu’une cellule CERRA de 5,5 km ne peut pas représenter simultanément un fond de vallée et les sommets qui l’entourent. Une couche CERRA seule ne répond donc pas au besoin exprimé par la capture de référence.

**Décision provisoire : conserver CHELSA comme source cartographique principale pour les trois températures.**

### Précipitations et jours de pluie

La comparaison finale des précipitations utilise maintenant la même période 1991–2020 pour CHELSA et CERRA-Land officiel. Elle couvre les douze mois sur **14 points terrestres** en Europe et dans le bassin méditerranéen. Conformément à la priorité actuelle, les Canaries ne sont pas incluses ; le point d’Essaouira est également exclu parce que le WBM a montré que sa coordonnée tombe dans l’océan.

Sur les **157 couples point–mois** où CERRA-Land mesure au moins 10 mm :

- rapport médian CHELSA/CERRA-Land : **1,24** ;
- intervalle du 10e au 90e percentile : **0,96 à 1,60** ;
- erreur absolue moyenne : **23,4 mm/mois**.

Les **11 couples secs**, sous 10 mm, ont une erreur absolue moyenne de seulement **0,9 mm/mois**. Les écarts les plus importants concernent Tromsø, Reykjavik, Font-Romeu et le massif du Mont-Blanc. La médiane mensuelle reste comprise entre 1,17 et 1,37 : le décalage relatif est donc assez stable au fil de l’année, mais dépend fortement du terrain.

Chaque point contient les 10 958 journées attendues entre 1991 et 2020. La maille régulière de 0,05° sélectionnée par le service se trouve à **2,18 km** du point demandé en médiane et à **3,08 km** au maximum sur l’échantillon. La durée moyenne des séries permet de calculer directement le nombre mensuel de jours avec au moins 1 mm de pluie.

**Décision mise à jour : CERRA-Land est validé comme source du nombre de jours de pluie à 5,5 km. CHELSA reste la source principale des totaux mensuels à environ 1 km : son contrôle indépendant par stations est meilleur que sa comparaison à CERRA-Land. Les écarts en haute latitude et dans le relief devront néanmoins être signalés lors de la publication.**

### Heures d’ensoleillement

SARAH-3 fournit des normales pour 17 des 18 points. Tromsø, à 69,6° N, est hors de la couverture limitée à 65° N.

La comparaison indicative montre que l’ensoleillement dérivé de CERRA est souvent nettement supérieur à SARAH-3, surtout dans les Alpes. À Annecy et Chamonix, les écarts atteignent plusieurs dizaines à plus de cent heures selon le mois testé.

Un premier facteur mensuel a été calculé dans une bande de recouvrement de 59 à 63,5° N. Il réduit l’erreur moyenne contre SARAH-3, mais ne prouve pas que la correction reste valable plus au nord. La valeur SARAH-3 de janvier à Reykjavik est en outre nulle alors que la normale WMO de la station est de **22,6 h** : l’extrême bord de la couverture satellite doit être traité avec prudence.

Le second contrôle compare CERRA et les stations WMO sur exactement la même période 1991–2020, au nord de 65° N :

- erreur absolue moyenne de CERRA brut : **35,6 h/mois** ;
- biais moyen : **+32,3 h/mois**, donc une surestimation générale ;
- erreur annuelle absolue médiane par station : **262 h/an** ;
- la correction multiplicative mensuelle réduit l’erreur à **26,3 h/mois** en validation croisée ;
- elle dégrade toutefois les résultats de février à avril et laisse des erreurs ponctuelles atteignant **128 h/mois** ;
- selon la station, CERRA va d’un total annuel presque exact à une surestimation dépassant **1 200 h/an**. Les écarts les plus forts correspondent notamment à des côtes et à des cellules de relief mal représentées.

Les facteurs calculés dans la bande SARAH-3 et ceux calculés sur les stations nordiques divergent fortement, notamment en hiver et en été. Une multiplication uniforme créerait donc précisément la couture cartographique que l’on cherche à éviter. L’estimation antérieure de Tromsø issue de cette méthode est conservée comme trace expérimentale, mais marquée comme rejetée dans son CSV.

**Décision mise à jour : utiliser SARAH-3 comme source principale au sud de sa limite utile. Au nord de 65° N, afficher CERRA brut comme valeur indicative avec un niveau de confiance réduit. Ne pas appliquer la correction multiplicative unique. Avant publication, adoucir la transition sur une bande dédiée et vérifier le rendu contre les stations WMO ; si l’interface ne peut pas afficher clairement cette incertitude, masquer l’ensoleillement nordique dans la première version.**

### Validation indépendante par stations

La comparaison station/grille est faite aux coordonnées exactes de chaque station, et non aux coordonnées du point test initial. Les couples trop différents sont explicitement exclus : couverture inférieure à 80 %, distance supérieure à 100 km ou écart d’altitude supérieur à 500 m.

Sur les 18 points :

- 8 disposent d’une bonne comparaison ;
- 2 disposent d’une comparaison indicative ;
- 8 sont non comparables, principalement à cause du relief extrême ou de séries marocaines incomplètes.

Pour les 10 points exploitables et les douze mois, soit 120 couples station–mois :

- biais moyen de CHELSA pour la température moyenne : **−0,08 °C** ;
- erreur absolue moyenne : **0,77 °C** ;
- 90 % des erreurs absolues sont inférieures à **1,52 °C** ;
- l’erreur mensuelle moyenne va de **0,50 °C en octobre** à **0,97 °C en janvier** ;
- le biais mensuel reste compris entre **−0,35 °C en janvier** et **+0,14 °C en juillet**.

Pour les 85 couples où la station mesure au moins 10 mm de pluie dans le mois :

- rapport médian CHELSA/station : **1,13** ;
- intervalle du 10e au 90e percentile : **0,96 à 1,60** ;
- erreur absolue moyenne : **15,5 mm/mois**.

Pour les 15 couples secs sous 10 mm, l’erreur absolue moyenne reste faible, **1,94 mm/mois**. Les ratios ne sont pas utilisés dans ce cas, car ils deviennent trompeurs lorsque la référence est proche de zéro.

Deux écarts appellent une vérification complémentaire : CHELSA est environ 3,7 °C plus froid que la station de Tromsø en janvier et surestime sa pluie estivale. Ces résultats ne remettent pas en cause toute la source, mais justifient un contrôle spécifique des hautes latitudes.

**Décision mise à jour : CHELSA est suffisamment convaincant pour rester la source principale des températures et des totaux de précipitations dans le prototype. La validation couvre désormais les douze mois, mais encore sur un petit échantillon ; elle ne justifie pas une publication sans avertissement ni contrôle des cartes complètes.**

### Validation WMO au Maroc

Les normales WMO/NCEI 1991–2020 apportent un contrôle indépendant nettement plus dense que GHCN-Daily au Maroc. CHELSA a été extrait aux coordonnées exactes de 25 stations, pour les douze mois. Les comparaisons valides donnent :

| Variable | Couples station–mois | Biais CHELSA − WMO | Erreur absolue moyenne | 90e percentile de l’erreur |
|---|---:|---:|---:|---:|
| Température moyenne | 300 | −0,12 °C | **0,69 °C** | 1,50 °C |
| Maximale moyenne | 300 | −0,92 °C | **1,25 °C** | 2,23 °C |
| Minimale moyenne | 298 | +0,20 °C | **1,04 °C** | 2,42 °C |
| Précipitations | 288 | −0,68 mm/mois | **3,81 mm/mois** | 9,74 mm/mois |

Pour les mois humides, le rapport médian CHELSA/WMO des précipitations est **1,01**, avec un intervalle du 10e au 90e percentile de **0,86 à 1,15**. Pour les mois secs, l’erreur absolue moyenne est **0,89 mm/mois**. Ces résultats sont sensiblement meilleurs que la comparaison CHELSA/CERRA-Land et confirment que la différence entre ces deux grilles ne doit pas être interprétée comme une erreur directe de CHELSA.

La température moyenne est bien reproduite dans l’ensemble. Les maximales présentent toutefois un biais froid d’environ **0,9 °C**. Marrakech est plus froide dans CHELSA d’environ 1,4 à 2,1 °C selon le mois, tandis qu’Essaouira est plus chaude d’environ 2,5 °C en juillet et août. Le contrôle WBM classe bien les 25 stations sur terre, mais le voisinage d’environ 1 km d’Essaouira ne contient que **30,5 % de terre** : ce cas côtier justifie l’utilisation du masque à 30 m et un avertissement lorsque la cellule climatique mélange fortement terre et mer.

Le nombre de jours de pluie CERRA-Land a également été comparé aux normales WMO `DP01` sur les 25 stations, soit 300 couples mensuels :

- biais moyen : **+0,22 jour/mois** ;
- erreur absolue moyenne : **0,35 jour/mois** ;
- 90 % des erreurs absolues sont inférieures à **0,70 jour/mois** ;
- distance médiane entre la station et le centre de la maille CERRA-Land : **2,12 km**, maximum **3,03 km**.

Ifrane constitue une exception nette : CERRA-Land y ajoute en moyenne environ **2,0 jours de pluie par mois**, avec des écarts surtout marqués d’avril à octobre. Sans Ifrane, l’erreur absolue moyenne tombe à **0,28 jour/mois**. Ce comportement est cohérent avec la difficulté d’une maille de 5,5 km à représenter précisément un site de montagne.

**Décision Maroc : valider CHELSA pour les températures et les précipitations mensuelles, en documentant le biais froid des maximales et les cellules côtières mixtes. Valider CERRA-Land pour les jours de pluie, avec un signal de confiance réduite dans les reliefs où la maille régionale diffère fortement du site local.**

### Validation de fenêtres cartographiques complètes

Cinq fenêtres ont été construites en combinant la température CHELSA moyenne 1991–2020 à environ 1 km et un ombrage du Copernicus DEM GLO-30 à environ 30 m :

- Alpes, d’Annecy au Mont-Blanc ;
- Pyrénées orientales, de Font-Romeu à Perpignan et à la Méditerranée ;
- Atlas marocain, de Marrakech au secteur du Toubkal ;
- Tenerife, de la côte sud au Teide et à La Laguna ;
- Tromsø, avec ses îles, fjords et reliefs côtiers.

Dans les Alpes, le gradient spatial calculé est de **−6,7 °C/1 000 m en janvier** et **−6,0 °C/1 000 m en juillet**. Dans les Pyrénées orientales, il est respectivement de **−6,0** et **−5,8 °C/1 000 m**. Les vallées, crêtes et sommets restent nettement différenciés : CHELSA répond donc bien au besoin de précision illustré par la capture de référence dans ces deux massifs.

L’Atlas marocain conserve lui aussi un contraste topographique crédible, de **−5,2 °C/1 000 m en janvier** et **−3,9 °C/1 000 m en juillet**. La fenêtre de Tromsø montre des gradients de **−4,7** et **−4,5 °C/1 000 m**, avec un découpage correct des îles et des fjords. Ces résultats étendent la validation visuelle aux climats sec méditerranéen et subarctique côtier.

Le test côtier a révélé que les rasters CHELSA contiennent aussi des températures extrapolées sur les cellules marines proches des côtes. La carte ne doit donc pas utiliser la présence d’une valeur CHELSA comme masque terrestre.

Le masque retenu est le **Water Body Mask (WBM) du Copernicus DEM GLO-30**, aligné avec le relief à environ 30 m. Ses classes officielles sont : 0 terre, 1 océan, 2 lac et 3 rivière. Contrairement à un simple seuil d’altitude, il conserve correctement les terres situées à 0 m ou sous le niveau marin.

Le contrôle des 18 points classe 17 points sur terre. Le point d’Essaouira tombe dans l’océan, à seulement **155 m du terrain le plus proche**, avec environ **45 % de terre** dans son voisinage de 1 km. Cela explique l’altitude de 0 m obtenue lors du premier contrôle.

Règle retenue pour la production :

1. conserver le WBM à 30 m pour interpréter précisément un clic ;
2. agréger le masque sur la grille climatique par proportion de terre ;
3. si le clic est terrestre, utiliser la cellule climatique terrestre correspondante ;
4. si le clic tombe sur l’eau à moins de 2 km du terrain, proposer explicitement la cellule terrestre la plus proche ;
5. au-delà de 2 km, afficher « eau » sans inventer de valeur terrestre.

À Tenerife, le gradient est cohérent en hiver, **−5,6 °C/1 000 m en janvier**, mais tombe à **−0,6 °C/1 000 m en juillet**. La comparaison entre les stations Tenerife Sur, à 64 m, et Izaña, à 2 371 m, confirme un affaiblissement saisonnier réel, mais moins extrême :

- stations : **−6,0 °C/1 000 m en janvier**, **−2,4 °C/1 000 m en juillet** ;
- CHELSA aux mêmes coordonnées : **−5,4 °C/1 000 m en janvier**, **−0,7 °C/1 000 m en juillet**.

CHELSA sous-estime ainsi le contraste côte–haute altitude d’environ **1,7 °C/1 000 m en juillet**, soit près de **4 °C** sur les 2 307 m séparant les deux stations. Août présente une anomalie similaire.

**Décision spatiale : utiliser CHELSA directement dans les massifs prioritaires du prototype et appliquer le WBM Copernicus comme masque terre/mer. La correction estivale des Canaries est documentée mais reportée, cette zone n’étant pas prioritaire à ce stade.**

## 5. Conséquences pour la carte hybride

La combinaison actuellement la plus solide est :

| Couche | Source provisoire | Résolution annoncée |
|---|---|---:|
| Température moyenne | CHELSA | ≈ 1 km |
| Maximales moyennes | CHELSA | ≈ 1 km |
| Minimales moyennes | CHELSA | ≈ 1 km |
| Précipitations mensuelles | CHELSA | ≈ 1 km |
| Jours de pluie ≥ 1 mm | CERRA-Land | 5,5 km |
| Heures d’ensoleillement au sud de la limite utile de SARAH-3 | SARAH-3 | ≈ 5 km |
| Heures d’ensoleillement au nord de 65° N | CERRA brut, indicatif et avec confiance réduite | 5,5 km |
| Altitude et relief | Copernicus DEM GLO-30 | ≈ 30 m |

L’interface devra afficher la résolution propre à chaque variable. Il ne faut pas ré-échantillonner une couche à 5 km vers 1 km en laissant croire que sa précision a augmenté.

La limite technique commune retenue est l’emprise native CERRA de 1 069 × 1 069 cellules en projection Lambert conforme conique. Son contour courbe atteint approximativement 58,18° O à 74,18° E et 20,26° N à 75,37° N. Il couvre l’Europe continentale, l’Islande, le bassin méditerranéen, l’Afrique du Nord et les Canaries, mais pas le Svalbard. Le contour exact a été exporté en WGS84 dans `emprise-cerra-officielle.geojson`.

La transition d’ensoleillement ne sera pas lissée artificiellement : SARAH-3 sera affiché jusqu’à 65° N, puis CERRA brut avec un niveau de confiance réduit. La légende et la fiche du point indiqueront le changement de source. La même échelle de couleurs sera conservée, mais aucune interpolation entre les deux jeux ne sera appliquée avant une validation locale plus robuste.

## 6. Décision sur 1991–2025

CHELSA-monthly s’arrête en 2021. Une carte hybride 1991–2025 exigerait donc de compléter 2022–2025 avec les anomalies CERRA, puis de les redistribuer spatialement sur la grille CHELSA.

La période 1996–2025 est méthodologiquement plus cohérente qu’une période de 35 ans 1991–2025 si le but est de montrer un climat plus récent. La stratégie retenue reste :

1. publier 1991–2020 comme normale de référence ;
2. construire et tester 1996–2025 séparément ;
3. n’afficher cette période récente que si la descente d’échelle passe les contrôles sur les reliefs et les précipitations.

## 7. Clôture de l’étape 1 et suites

Le contrôle supplémentaire d’une normale officielle CERRA de température n’est pas poursuivi à ce stade. Le service CERRA ne découpe pas spatialement les champs : même une extraction pour quelques points impose de télécharger la grille complète. Le fichier test d’un seul champ à une échéance pèse 2,2 Mo. Une normale 1991–2020 à huit analyses quotidiennes représente environ 87 660 champs, soit un ordre de grandeur proche de 190 Go pour une seule variable avant les autres traitements. Un sous-échantillonnage de quelques dates serait beaucoup moins coûteux, mais ne constituerait pas une normale climatique défendable.

Cette dépense n’apporterait pas une meilleure référence que les observations directes déjà exploitées : CHELSA est contrôlé contre GHCN-Daily et contre 25 stations WMO marocaines, tandis que les différences spatiales avec CERRA ont déjà été caractérisées sur les reliefs. La décision est donc de réserver une extraction CERRA massive à la préparation effective des tuiles nordiques, si cette couche est retenue pour la publication.

L’étape 1 est considérée comme terminée avec les suites suivantes :

1. pendant le prototype, vérifier le rendu de la coupure SARAH-3/CERRA sur quelques tuiles cartographiques ;
2. mesurer le poids et la vitesse de chargement des tuiles avant de choisir leurs niveaux de zoom ;
3. conserver la correction estivale de haute altitude aux Canaries dans le carnet des améliorations non prioritaires ;
4. n’ouvrir la période récente 1996–2025 qu’après validation de sa méthode de descente d’échelle.

## 8. Fichiers associés

- `catalogue-sources-etape-1.csv` : sources, licences, accès et risques ;
- `resultats-zones-tests-etape-1.csv` : valeurs et écarts pour les 18 points ;
- `normales-cerra-land-1991-2020.csv` : précipitations et jours de pluie pour les douze mois ;
- `controle-mailles-cerra-land.csv` : coordonnées réellement utilisées, distance au point demandé et contrôle des données manquantes ;
- `altitudes-points-tests.csv` : contrôle ponctuel du Copernicus DEM GLO-30 ;
- `diagnostic-sources-etape-1.png` : graphiques de comparaison exploratoire.
- `stations-reference-ghcnd.csv` : station retenue, distance, altitude, couverture et niveau de comparabilité pour chaque point ;
- `normales-stations-ghcnd-1991-2020.csv` : normales mensuelles observées et nombre d’années valides ;
- `comparaison-chelsa-stations.csv` : comparaison CHELSA/station pour les douze mois ;
- `validation-stations-ghcnd.png` : graphique de la validation indépendante.
- `validation-stations-ghcnd-12-mois.png` : synthèse mensuelle des biais et erreurs sur toute l’année.
- `fenetres-cartographiques-hybrides.png` : six cartes température/relief pour les Alpes, les Pyrénées orientales et Tenerife ;
- `controle-fenetres-cartographiques.csv` : étendue thermique, relief et gradient altitudinal des fenêtres ;
- `controle-gradient-altitudinal-tenerife.png` : comparaison mensuelle du gradient observé et de CHELSA ;
- `gradient-altitudinal-tenerife.csv` : valeurs mensuelles utilisées pour ce contrôle.
- `controle-masque-eau-points.csv` : classe WBM, proportion de terre, distance au terrain et comportement recommandé pour les 18 points.
- `comparaison-ensoleillement-nord.csv` et `correction-ensoleillement-nord.csv` : premier test de correction dans la bande de recouvrement SARAH-3/CERRA ;
- `comparaison-cerra-wmo-ensoleillement-nord.csv` : 120 comparaisons mensuelles CERRA/stations WMO au nord de 65° N ;
- `correction-cerra-wmo-ensoleillement-nord.csv` : erreurs brutes, ajustées et en validation croisée pour chaque mois ;
- `synthese-stations-ensoleillement-nord.csv` : biais annuels et erreurs par station ;
- `validation-ensoleillement-nord.png` : diagnostic visuel ayant conduit au rejet de la correction uniforme ;
- `estimation-ensoleillement-tromso.csv` : ancien scénario de correction, explicitement marqué comme rejeté.
- `comparaison-chelsa-cerra-land-12-mois.csv` : 168 comparaisons mensuelles sur 14 points terrestres hors Canaries ;
- `synthese-chelsa-cerra-land-12-mois.csv` : ratios et erreurs de précipitations par mois ;
- `comparaison-chelsa-cerra-land-12-mois.png` : synthèse visuelle annuelle des précipitations.
- `stations-wmo-maroc-1991-2020.csv` : coordonnées et altitudes des 25 stations WMO marocaines retenues ;
- `comparaison-chelsa-wmo-maroc.csv` et `synthese-chelsa-wmo-maroc.csv` : contrôle mensuel des températures et précipitations CHELSA au Maroc ;
- `comparaison-cerra-land-wmo-jours-pluie-maroc.csv` et `synthese-cerra-land-wmo-jours-pluie-maroc.csv` : contrôle mensuel des jours de pluie CERRA-Land ;
- `controle-mailles-cerra-land-stations-wmo-maroc.csv` : position et distance des mailles utilisées pour les stations marocaines ;
- `controle-masque-eau-stations-wmo-maroc.csv` : contrôle WBM des 25 stations, dont la cellule côtière mixte d’Essaouira ;
- `validation-wmo-maroc.png` : synthèse visuelle de la validation marocaine.
- `cadrage-domaine-carte.md` : limite technique de la carte et règle de transition SARAH-3/CERRA ;
- `emprise-cerra-officielle.geojson` : contour exact de la grille CERRA officielle en WGS84.

