# Plan interface — deux étapes

Date : 20 octobre 2026

## Étape 1 — base visuelle fiable

- corriger les coutures entre tuiles par un rendu avec bord tampon avant découpe ;
- resserrer la palette des températures sur −20 à 40 °C ;
- remplacer la palette des précipitations pour distinguer immédiatement la terre de la mer ;
- masquer les routes maritimes et rendre les routes terrestres neutres ;
- ajouter un ombrage de relief léger, indépendant des couleurs climatiques ;
- installer Tailwind CSS comme base des prochains composants d’interface ;
- conserver une échelle fixe par variable pour comparer correctement les mois et les régions.

## Étape 2 — valeurs et échelle locale expérimentale

- lire les valeurs numériques des COG au survol, avec source, unité et résolution ;
- calculer des statistiques spatiales utilisables pour la zone visible ;
- tester une recoloration dont le minimum et le maximum suivent la vue courante ;
- isoler cette échelle adaptative dans un commit dédié afin de pouvoir revenir facilement à l’échelle fixe ;
- décider ensuite si l’interface reste en TypeScript léger avec Tailwind ou passe à React + shadcn/ui.

L’échelle adaptative ne peut pas être appliquée honnêtement aux PMTiles WebP déjà colorés : elle exige des valeurs encodées ou des statistiques par tuile. Modifier uniquement les nombres de la légende donnerait une représentation fausse.
