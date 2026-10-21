# Better Weather Place

Projet de carte climatique mensuelle pour l’Europe, le bassin méditerranéen et les Canaries.

## État actuel

L’étape 1 de sélection et de validation des sources gratuites est terminée pour les températures, précipitations, jours de pluie, heures d’ensoleillement et altitude, avec une attention particulière au relief et aux côtes. Aucun code d’application n’a encore été commencé.

L’architecture proposée pour l’étape 2 est documentée dans `outputs/plan-etape-2-architecture.md`. Elle privilégie une carte sans API applicative, avec MapLibre, des archives raster PMTiles pour l’affichage et des COG pour les valeurs au clic. Le choix de l’hébergement est reporté : les mêmes fichiers devront fonctionner sur un stockage objet ou sur un VPS. Le lot témoin de tuiles est terminé et la production des grilles mensuelles est en cours.

Le contrat canonique des couches est défini dans `outputs/contrat-donnees-v1.json` et expliqué dans `outputs/contrat-donnees-v1.md` : disponibilité, unités, arrondis, formats, palettes, résolutions, chemins des fichiers, licences et avertissements. L’application et la chaîne PMTiles lisent directement ce manifeste afin d’éviter les configurations divergentes.

Le lot témoin 2B est terminé sur janvier et juillet entre le Maroc et les Alpes. Les cinq archives PMTiles et deux COG sont dans `outputs/pilot-etape-2b/`, avec le rapport `outputs/pilot-etape-2b-rapport.md`. Le relief séparé est retenu pour la maquette : sa qualité est proche du relief intégré et son coût fixe est amorti après environ huit couches.

Le pilote complémentaire de relief détaillé est également terminé sur les Alpes, les Pyrénées et le Haut Atlas. Le profil retenu utilise environ 1 km aux zooms 3–7 et environ 90 m aux zooms 8–10. Les résultats, dont une archive témoin de 6,37 Mio, sont décrits dans `outputs/pilot-relief-haute-resolution-rapport.md`. Les Canaries restent volontairement hors du périmètre prioritaire.

Les 36 normales mensuelles 1991–2020 des températures moyenne, maximale et minimale sont calculées sur le domaine complet. Leurs valeurs terrestres vont respectivement de −30,7 à 40,5 °C, de −26,9 à 46,5 °C et de −35,2 à 31,8 °C. Pour mieux distinguer les écarts utiles à l’écran, la palette commune est volontairement resserrée à −20–40 °C ; les valeurs au-delà utilisent les couleurs terminales tandis que les COG conservent la valeur exacte.

Les douze normales de précipitations sont également calculées sur le domaine complet. Les rares pics au-dessus de 400 mm/mois représentent au plus 0,201 % des pixels WBM valides et prennent la couleur terminale sans perdre leur valeur numérique. Le contrôle détaillé est documenté dans `outputs/rapport-audit-grilles-production.md`.

La palette des jours de pluie a été contrôlée sur 906 normales mensuelles CERRA-Land, GHCN et WMO. Le maximum observé est 21,67 jours/mois ; une borne terminale à 31 jours a été ajoutée pour respecter le maximum physique sans toucher aux couleurs 0–25. Voir `outputs/rapport-palette-jours-pluie.md`.

Les douze normales SARAH-3 d’ensoleillement sont produites et contrôlées au sud de 65° N. Le maximum terrestre atteint 404,4 h en juillet, mais seuls 0,103 % des pixels dépassent 400 h ; l’échelle 0–400 h est conservée. Le complément CERRA au nord de 65° N reste à produire.

Les 60 COG actuellement disponibles ont passé le contrôle complet de structure et d’intégrité SHA-256. Les 2 138 tuiles du masque WBM, soit environ 141 Mio, sont téléchargées et transformées en fractions terrestres alignées sur CHELSA, SARAH-3 et CERRA. Les 60 copies climatiques publiables sont masquées et leurs 60 archives PMTiles WebP sont générées : environ 76 Mio au total, avec un inventaire dans `outputs/inventaire-pmtiles-production.csv`. Les jours de pluie CERRA-Land sont téléchargés et assemblés progressivement ; les douze COG correspondants seront finalisés lorsque toutes les tuiles seront présentes.

Période de référence : **1991–2020**. Une vue récente **1996–2025** sera étudiée séparément.

## Sources candidates

- CHELSA Monthly V2.1 pour les températures et les précipitations mensuelles ;
- CERRA et CERRA-Land pour la référence régionale, les jours de pluie et le complément nord ;
- SARAH-3 pour la durée d’ensoleillement jusqu’à 65° N ;
- Copernicus DEM GLO-30 pour le relief et l’altitude.
- NOAA GHCN-Daily comme contrôle indépendant par stations.
- normales WMO/NCEI 1991–2020 comme contrôle indépendant de l’ensoleillement nordique ainsi que des températures, précipitations et jours de pluie au Maroc.

Le traitement SARAH-3 est terminé : les 360 sommes mensuelles 1991–2020 de la commande CM SAF ont été contrôlées et transformées par `work/build_sarah_normals.py` en douze COG d’ensoleillement. Voir `outputs/guide-production-normales-sarah3.md`.

## Organisation

- `outputs/` : rapport et résultats lisibles de l’étape 1 ;
- `work/validation/` : scripts, données intermédiaires et caches de validation ;
- `work/.venv/` : environnement Python local non versionné.

Les identifiants Copernicus restent dans le fichier privé `~/.cdsapirc` et ne sont jamais stockés dans ce dépôt.

Le téléchargement reprenable se lance avec `work/run_overnight.py`. Il contrôle SARAH-3 et CHELSA, poursuit les précipitations quotidiennes CERRA-Land par tuiles terrestres de 0,5° (Canaries exclues), puis assemble automatiquement toutes les nouvelles tuiles reçues. Une réserve d’espace disque empêche le remplissage du volume local.

Une fois CHELSA complet, `work/build_chelsa_normals.py --strict` produit les 48 COG mensuels 1991–2020 avec contrôle des trente années, conversion des unités, arrondi conforme au contrat et reprise automatique. Le processus est documenté dans `outputs/guide-production-normales-chelsa.md`.

Les archives quotidiennes CERRA-Land sont traitées de façon incrémentale par `work/build_cerra_rainy_days.py`. La chaîne compte les jours avec au moins 1 mm année par année, reprend au niveau de chaque tuile et ne finalise les douze COG qu’une fois le domaine complet disponible. Voir `outputs/guide-production-jours-pluie.md`.

La validation actuelle comprend les douze mois 1991–2020, un contrôle indépendant par stations GHCN-Daily, une comparaison annuelle CHELSA/CERRA-Land sur 14 points terrestres hors Canaries, cinq fenêtres température/relief couvrant Alpes, Pyrénées, Atlas, Tenerife et Tromsø, ainsi qu’un contrôle CERRA/WMO sur dix stations d’ensoleillement au nord de 65° N. Au Maroc, les normales WMO de 25 stations confirment CHELSA pour les températures et précipitations et CERRA-Land pour les jours de pluie ; Ifrane reste une exception liée au relief et Essaouira un cas côtier mixte. Le masque terre/mer retenu est le WBM du Copernicus DEM GLO-30. L’emprise native CERRA, exportée dans `outputs/emprise-cerra-officielle.geojson`, fixe la limite commune des couches hybrides. CERRA peut servir de complément nordique indicatif, mais la correction multiplicative unique a été rejetée ; la correction estivale des Canaries est documentée mais non prioritaire.

Attribution requise pour le relief adapté : « produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved ».
