# Vérifications reportées pour avancer plus vite

Ces contrôles ne bloquent pas le prototype. Ils seront repris avant une publication publique :

- inspection visuelle systématique des 60 archives PMTiles sur plusieurs côtes et massifs ;
- comparaison pixel à pixel entre quelques tuiles colorées et leurs COG numériques ;
- test du chargement PMTiles, des requêtes HTTP Range et du cache dans les navigateurs mobiles ciblés ;
- mesure du temps de premier affichage sur une connexion lente et ajustement éventuel de la qualité WebP ;
- audit complet de la palette des jours de pluie quand la grille CERRA-Land sera terminée ;
- décision finale sur l’ensoleillement au nord de 65° N, encore absent des archives actuelles.
- compilation et aperçu navigateur de la maquette locale ; l’installation npm était bloquée le 20 octobre par une indisponibilité DNS de `registry.npmjs.org`.

Les contrôles conservés pendant le prototype restent courts : fichier source présent, archive lisible, nombre de tuiles cohérent, checksum et reprise sans recalcul.
