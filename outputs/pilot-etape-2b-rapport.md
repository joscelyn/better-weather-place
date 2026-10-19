# Étape 2B — Lot de tuiles témoin

Date : 19 octobre 2026

## Périmètre

- variable : température moyenne CHELSA 1991–2020 ;
- mois : janvier et juillet ;
- emprise : 10° O–8° E et 29–47° N ;
- tuiles : zooms 3 à 7, WebP qualité 85, archives PMTiles ;
- masque terre/eau et relief : Copernicus DEM GLO-30 ré-échantillonné à environ 1 km pour ce témoin.

## Résultats de volume

- deux archives avec relief intégré : **0.44 Mio** ;
- deux archives climatiques sans relief : **0.35 Mio** ;
- archive de relief séparée et réutilisable : **0.31 Mio** ;
- option séparée complète pour les deux mois : **0.66 Mio** ;
- durée de l’exécution courante, dépendante de l’état du cache local : **1.5 min**.

Le poids d’une archive entière n’est pas le volume chargé à l’ouverture : PMTiles récupère uniquement l’index et les plages d’octets correspondant aux tuiles visibles.

Chaque archive contient **91 tuiles**. La taille médiane va d’environ **1,4 à 2,4 ko** selon la variante. Les deux COG numériques occupent ensemble **4.07 Mio**.

## Contrôles techniques

- les cinq archives sont des PMTiles version 3 contenant des tuiles WebP, zooms 3 à 7 ;
- les deux fichiers numériques sont des COG stricts : **oui** ;
- le contrôle sur Essaouira, Marrakech, Ifrane, Font-Romeu et Chamonix donne un écart maximal COG/source de **0.043 °C**, entièrement expliqué par l’arrondi au dixième ;
- deux points marins de contrôle sont sans donnée tandis que Madrid et Marrakech restent terrestres ;
- la comparaison détaillée des Alpes, des Pyrénées et du Haut Atlas est fournie dans `pilot-etape-2b-details-relief.png`.

## Interprétation

Le relief intégré économise une source et une requête par tuile, mais il faut recalculer le relief dans chaque mois et il ne peut plus être réglé indépendamment. Le relief séparé ajoute une archive commune, réutilisable par toutes les variables et tous les mois. La comparaison visuelle de `pilot-etape-2b-apercu.png` doit guider le choix, en complément des tailles détaillées du CSV.

Sur ce témoin, le surcoût fixe du relief séparé est amorti après environ **7.3 couches**. Le produit final en prévoit 72. Les détails montrent une qualité visuelle très proche entre les deux variantes.

**Décision pour la maquette : conserver le relief dans une couche séparée.** Le premier affichage demande une source supplémentaire, mais elle reste ensuite en cache lors des changements de mois ou de variable. Cette solution réduit la répétition des données, permet de régler l’intensité du relief et évite de recalculer le même ombrage dans chaque archive climatique.

Ce témoin ne sert pas encore de couche de production : le relief a été ramené à la grille climatique d’environ 1 km.

Le test complémentaire haute résolution est maintenant terminé sur les Alpes, les Pyrénées et le Haut Atlas. Il confirme l’intérêt d’un relief séparé multi-résolution : environ 1 km aux zooms 3–7, puis environ 90 m aux zooms 8–10. L’archive ciblée contient 679 tuiles et pèse 6,37 Mio. Le zoom natif maximal est fixé à 10 ; le détail supplémentaire du zoom 11 ne justifierait pas son coût pour une carte climatique. Voir `pilot-relief-haute-resolution-rapport.md`.
