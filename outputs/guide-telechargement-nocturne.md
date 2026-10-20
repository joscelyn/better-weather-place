# Téléchargement nocturne des données

Date : 19 octobre 2026

## Ce que le script récupère

`work/run_overnight.py` enchaîne jusqu’à trois phases reprenables :

1. la commande SARAH-3, si le manifeste
   `work/downloads/sarah3-ORD70729-urls.txt` existe ;

2. les fenêtres utiles des fichiers CHELSA mensuels 1991–2020 pour :

- température moyenne (`tas`) ;
- maximales moyennes (`tasmax`) ;
- minimales moyennes (`tasmin`) ;
- précipitations mensuelles (`pr`) ;

3. les précipitations **quotidiennes** CERRA-Land 1991–2020, nécessaires au calcul des jours avec au moins 1 mm de pluie.

Cela représente 1 440 sources. Le script ne copie pas les GeoTIFF mondiaux complets : les quatre fichiers d’un seul mois de 1991 pèsent déjà environ 613 Mo, soit un ordre de grandeur proche de **220 Go** pour les 1 440 fichiers mondiaux. Il lit uniquement la fenêtre Europe–Méditerranée grâce aux requêtes partielles des COG.

Emprise rectangulaire CHELSA par défaut : **25° O–45° E, 25–72° N**. Elle couvre l’Europe, l’Islande, l’Afrique du Nord et le bassin méditerranéen oriental. Le clip brut contient géographiquement les Canaries, mais elles restent exclues du masque et de la production prioritaire. Les tuiles CERRA-Land des Canaries ne sont pas téléchargées.

Les clips conservent les valeurs brutes, le facteur d’échelle, l’offset et la valeur sans donnée de CHELSA. Ils pourront donc servir aux normales, aux COG finaux et aux contrôles sans nouveau téléchargement.

## Commande recommandée cette nuit

Depuis le dossier du projet :

```bash
mkdir -p work/downloads
caffeinate -i work/.venv/bin/python work/run_overnight.py --hours 10 2>&1 | tee work/downloads/nuit-complete.log
```

Le Mac restera éveillé pendant l’exécution. La durée de dix heures est une limite souple : le fichier en cours est terminé avant l’arrêt.

SARAH-3 passe en premier lorsque ses liens sont disponibles, car les liens de
livraison peuvent être temporaires. En l’absence du manifeste, le lanceur indique
que la phase est ignorée puis continue normalement avec CHELSA et CERRA-Land.

Avant de lancer, vérifier le plan et l’espace disque sans télécharger :

```bash
work/.venv/bin/python work/download_overnight.py --dry-run
work/.venv/bin/python work/download_cerra_rain.py --dry-run
```

## Reprise et contrôles

- chaque clip terminé possède un fichier JSON avec sa taille, son empreinte SHA-256, sa source et son emprise ;
- les clips valides sont ignorés au lancement suivant ;
- chaque lecture distante est retentée six fois avec un backoff de 5 s, 30 s,
  120 s, 500 s puis 1 800 s entre les échecs successifs ;
- un échec définitif est journalisé puis les autres fichiers continuent ;
- `Ctrl-C` arrête proprement entre les opérations ;
- les fichiers partiels ne sont jamais considérés comme terminés ;
- le lanceur complet s’arrête si l’espace libre descend sous la réserve de 15 Gio.

Pour vérifier ensuite ce qui manque :

```bash
work/.venv/bin/python work/download_overnight.py --verify-only
work/.venv/bin/python work/download_cerra_rain.py --verify-only
```

Un code de sortie 0 signifie que la phase contrôlée est complète ; 2 signifie que le téléchargement doit être relancé.

## Volume et durée

La taille exacte dépend de la compression spatiale de chaque fichier. Le test réel du premier mois de 1991 donne **32,2 Mio pour quatre clips CHELSA** (6,6 à 8,7 Mio chacun), téléchargés en **37 secondes** au total. Si cet ordre de grandeur reste stable, les 1 440 clips occuperont environ **11 à 13 Gio** et demanderont autour de **quatre heures** à 1 Mo/s.

Copernicus limite chaque extraction CERRA-Land à 0,5° × 0,5°. Le script ne demande que les tuiles rencontrant les terres Natural Earth, traite le sud en premier et lance huit requêtes parallèles. Un test alpin complet sur trente ans pèse **4,28 Mio**. L’ordre de grandeur de la pluie quotidienne complète est d’environ **33 Gio supplémentaires**. Elle pourra donc demander plus d’une nuit et sera reprise automatiquement.

Le disque contient actuellement environ **31 Gio libres**, moins que les 44–46 Gio estimés pour les deux phases complètes. Le lanceur conserve par défaut **15 Gio libres** : il privilégiera CHELSA, téléchargera ensuite autant de pluie quotidienne que possible, puis s’arrêtera proprement. Il faudra libérer environ 30 Gio supplémentaires ou déplacer `work/downloads/` vers un disque plus grand pour terminer l’ensemble.

## SARAH-3

La grille d’ensoleillement reste séparée. Le compte CM SAF est désormais créé et
la commande manuelle peut être préparée :

- produit mensuel `SDU — Sunshine Duration`, statistique `Sum`, maille `0,05°` ;
- période 1991-01-01 à 2020-12-01, NetCDF4 ;
- 2,8 Go confirmés pour la commande complète sans découpe de domaine ;
- procédure et traitement local : `outputs/guide-production-normales-sarah3.md`.

Le lanceur nocturne couvre les quatre couches CHELSA, la matière première des
jours de pluie et, dès que le manifeste de livraison existe, SARAH-3. Le WUI doit
tout de même préparer la commande et fournir ses liens HTTPS au préalable. Les
fichiers récupérés sont transformés par `work/build_sarah_normals.py`.
