# Production des normales CHELSA 1991–2020

Date : 19 octobre 2026  
Statut : chaîne validée sur des fichiers réels, en attente du téléchargement complet

## Objectif

`work/build_chelsa_normals.py` transforme les 1 440 clips annuels téléchargés en 48 couches mensuelles :

- température moyenne ;
- moyenne des maximales journalières ;
- moyenne des minimales journalières ;
- précipitations mensuelles.

Pour chaque variable et chaque mois, le script exige les 30 années 1991–2020. Un mois incomplet n’est jamais moyenné silencieusement.

## Traitement

- lecture par blocs de 256 × 256 pixels pour limiter la mémoire ;
- application du facteur d’échelle CHELSA ;
- conversion Kelvin → degrés Celsius pour les températures ;
- moyenne des trente années en précision flottante ;
- arrondi au dixième, avec la règle « moitié en s’éloignant de zéro » du contrat ;
- stockage `int16` pour les températures et `uint16` pour les précipitations ;
- production d’un Cloud Optimized GeoTIFF avec vues d’ensemble ;
- manifeste JSON comprenant plage, nombre de pixels, taille et SHA-256 ;
- reprise automatique : un COG terminé et cohérent est ignoré.

Le masque terre/mer final n’est volontairement pas encore appliqué. Les COG portent le marqueur `water_mask_applied=false` afin qu’aucun fichier intermédiaire ne puisse être confondu avec un produit publiable. Le WBM Copernicus sera appliqué lors de l’étape suivante.

## Commandes

Vérifier ce qui est prêt sans produire de fichier :

```bash
work/.venv/bin/python work/build_chelsa_normals.py --dry-run
```

Après la fin du téléchargement CHELSA, produire les 48 normales et échouer si une année manque :

```bash
work/.venv/bin/python work/build_chelsa_normals.py --strict
```

Les résultats sont écrits dans `work/derived/1991-2020/{layer_id}/{month}.tif`. Ce répertoire est reproductible et non versionné.

## Validation effectuée

Le pipeline a été exécuté sur janvier 1991 pour la température moyenne et les précipitations :

- température : COG de 12,3 Mio, plage −32,15 à 21,25 °C ;
- précipitations : COG de 13,8 Mio, plage 0 à 1 128 mm ;
- facteurs d’échelle, valeurs sans donnée, métadonnées et six niveaux de vues d’ensemble vérifiés ;
- cinq pixels de chaque couche comparés à la source après décodage ;
- second lancement sans recalcul des deux fichiers terminés.

Ce test à une seule année valide la mécanique et les unités. Les plages climatiques finales ne seront évaluées qu’avec les trente années.
