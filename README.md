# Better Weather Place

Projet de carte climatique mensuelle pour l’Europe, le bassin méditerranéen et les Canaries.

## État actuel

L’étape 1 de sélection et de validation des sources gratuites est terminée pour les températures, précipitations, jours de pluie, heures d’ensoleillement et altitude, avec une attention particulière au relief et aux côtes. Aucun code d’application n’a encore été commencé.

L’architecture proposée pour l’étape 2 est documentée dans `outputs/plan-etape-2-architecture.md`. Elle privilégie une carte sans API applicative, avec MapLibre, des archives raster PMTiles pour l’affichage et des COG pour les valeurs au clic. Le choix de l’hébergement est reporté : les mêmes fichiers devront fonctionner sur un stockage objet ou sur un VPS. La prochaine expérimentation prévue est un petit lot de tuiles témoin, pas la génération complète des 72 couches mensuelles.

Le contrat de travail des couches est défini dans `outputs/contrat-donnees-v1.json` et expliqué dans `outputs/contrat-donnees-v1.md` : unités, arrondis, formats, palettes provisoires, résolutions et avertissements côtiers, topographiques et nordiques.

Le lot témoin 2B est terminé sur janvier et juillet entre le Maroc et les Alpes. Les cinq archives PMTiles et deux COG sont dans `outputs/pilot-etape-2b/`, avec le rapport `outputs/pilot-etape-2b-rapport.md`. Le relief séparé est retenu pour la maquette : sa qualité est proche du relief intégré et son coût fixe est amorti après environ huit couches.

Le pilote complémentaire de relief détaillé est également terminé sur les Alpes, les Pyrénées et le Haut Atlas. Le profil retenu utilise environ 1 km aux zooms 3–7 et environ 90 m aux zooms 8–10. Les résultats, dont une archive témoin de 6,37 Mio, sont décrits dans `outputs/pilot-relief-haute-resolution-rapport.md`. Les Canaries restent volontairement hors du périmètre prioritaire.

Les douze normales mensuelles 1991–2020 des températures moyenne, maximale et minimale sont maintenant calculées sur le domaine témoin. La moyenne tient dans la plage −30 à 40 °C, mais cette borne saturerait près de 20 % des maximales de juillet. La palette thermique commune est donc étendue à −40–50 °C en conservant toutes les couleurs intermédiaires. Les détails se trouvent dans `outputs/rapport-palette-temperature-moyenne.md` et `outputs/rapport-palettes-temperatures-extremes.md`.

Les douze normales de précipitations sont également calculées. La plage 0–400 mm/mois ne sature aucun pixel du témoin et les seuils rapprochés sous 20 mm distinguent correctement les zones sèches recherchées. Le contrôle détaillé est documenté dans `outputs/rapport-palette-precipitations.md`.

La palette des jours de pluie a été contrôlée sur 906 normales mensuelles CERRA-Land, GHCN et WMO. Le maximum observé est 21,67 jours/mois ; une borne terminale à 31 jours a été ajoutée pour respecter le maximum physique sans toucher aux couleurs 0–25. Voir `outputs/rapport-palette-jours-pluie.md`.

La palette d’ensoleillement a été contrôlée sur 408 valeurs mensuelles SARAH-3, CERRA et WMO, hors Canaries. Le maximum observé est 389,41 h/mois : l’échelle 0–400 h est conservée sans modification, avec un contrôle spatial complet encore nécessaire. Voir `outputs/rapport-palette-ensoleillement.md`.

Période de référence : **1991–2020**. Une vue récente **1996–2025** sera étudiée séparément.

## Sources candidates

- CHELSA Monthly V2.1 pour les températures et les précipitations mensuelles ;
- CERRA et CERRA-Land pour la référence régionale, les jours de pluie et le complément nord ;
- SARAH-3 pour la durée d’ensoleillement jusqu’à 65° N ;
- Copernicus DEM GLO-30 pour le relief et l’altitude.
- NOAA GHCN-Daily comme contrôle indépendant par stations.
- normales WMO/NCEI 1991–2020 comme contrôle indépendant de l’ensoleillement nordique ainsi que des températures, précipitations et jours de pluie au Maroc.

## Organisation

- `outputs/` : rapport et résultats lisibles de l’étape 1 ;
- `work/validation/` : scripts, données intermédiaires et caches de validation ;
- `work/.venv/` : environnement Python local non versionné.

Les identifiants Copernicus restent dans le fichier privé `~/.cdsapirc` et ne sont jamais stockés dans ce dépôt.

Le téléchargement reprenable se lance avec `work/run_overnight.py`. Il récupère d’abord les quatre variables CHELSA, puis les précipitations quotidiennes CERRA-Land par tuiles terrestres de 0,5°, Canaries exclues. Une réserve d’espace disque empêche le remplissage du volume local.

Une fois CHELSA complet, `work/build_chelsa_normals.py --strict` produit les 48 COG mensuels 1991–2020 avec contrôle des trente années, conversion des unités, arrondi conforme au contrat et reprise automatique. Le processus est documenté dans `outputs/guide-production-normales-chelsa.md`.

Les archives quotidiennes CERRA-Land sont traitées de façon incrémentale par `work/build_cerra_rainy_days.py`. La chaîne compte les jours avec au moins 1 mm année par année, reprend au niveau de chaque tuile et ne finalise les douze COG qu’une fois le domaine complet disponible. Voir `outputs/guide-production-jours-pluie.md`.

La validation actuelle comprend les douze mois 1991–2020, un contrôle indépendant par stations GHCN-Daily, une comparaison annuelle CHELSA/CERRA-Land sur 14 points terrestres hors Canaries, cinq fenêtres température/relief couvrant Alpes, Pyrénées, Atlas, Tenerife et Tromsø, ainsi qu’un contrôle CERRA/WMO sur dix stations d’ensoleillement au nord de 65° N. Au Maroc, les normales WMO de 25 stations confirment CHELSA pour les températures et précipitations et CERRA-Land pour les jours de pluie ; Ifrane reste une exception liée au relief et Essaouira un cas côtier mixte. Le masque terre/mer retenu est le WBM du Copernicus DEM GLO-30. L’emprise native CERRA, exportée dans `outputs/emprise-cerra-officielle.geojson`, fixe la limite commune des couches hybrides. CERRA peut servir de complément nordique indicatif, mais la correction multiplicative unique a été rejetée ; la correction estivale des Canaries est documentée mais non prioritaire.

Attribution requise pour le relief adapté : « produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved ».
