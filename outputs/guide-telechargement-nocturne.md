# Téléchargement nocturne des données

Date : 19 octobre 2026

## Ce que le script récupère

`work/download_overnight.py` télécharge les fenêtres utiles des fichiers CHELSA mensuels 1991–2020 pour :

- température moyenne (`tas`) ;
- maximales moyennes (`tasmax`) ;
- minimales moyennes (`tasmin`) ;
- précipitations mensuelles (`pr`).

Cela représente 1 440 sources. Le script ne copie pas les GeoTIFF mondiaux complets : les quatre fichiers d’un seul mois de 1991 pèsent déjà environ 613 Mo, soit un ordre de grandeur proche de **220 Go** pour les 1 440 fichiers mondiaux. Il lit uniquement la fenêtre Europe–Méditerranée grâce aux requêtes partielles des COG.

Emprise par défaut : **25° O–45° E, 25–72° N**. Elle couvre l’Europe, l’Islande, l’Afrique du Nord et le bassin méditerranéen oriental. Les Canaries sont volontairement exclues de cette passe prioritaire.

Les clips conservent les valeurs brutes, le facteur d’échelle, l’offset et la valeur sans donnée de CHELSA. Ils pourront donc servir aux normales, aux COG finaux et aux contrôles sans nouveau téléchargement.

## Commande recommandée cette nuit

Depuis le dossier du projet :

```bash
mkdir -p work/downloads
caffeinate -i work/.venv/bin/python work/download_overnight.py --hours 10 2>&1 | tee work/downloads/nuit-chelsa.log
```

Le Mac restera éveillé pendant l’exécution. La durée de dix heures est une limite souple : le fichier en cours est terminé avant l’arrêt.

Avant de lancer, vérifier le plan et l’espace disque sans télécharger :

```bash
work/.venv/bin/python work/download_overnight.py --dry-run
```

## Reprise et contrôles

- chaque clip terminé possède un fichier JSON avec sa taille, son empreinte SHA-256, sa source et son emprise ;
- les clips valides sont ignorés au lancement suivant ;
- chaque lecture distante est retentée six fois avec attente croissante ;
- un échec définitif est journalisé puis les autres fichiers continuent ;
- `Ctrl-C` arrête proprement entre les opérations ;
- les fichiers partiels ne sont jamais considérés comme terminés ;
- le script s’arrête si l’espace libre descend sous 20 Gio.

Pour vérifier ensuite ce qui manque :

```bash
work/.venv/bin/python work/download_overnight.py --verify-only
```

Un code de sortie 0 signifie que les 1 440 clips sont présents ; 2 signifie que le téléchargement doit être relancé.

## Volume et durée

La taille exacte dépend de la compression spatiale de chaque fichier. Le test réel du premier mois de 1991 donne **32,2 Mio pour quatre clips** (6,6 à 8,7 Mio chacun), téléchargés en **37 secondes** au total. Si cet ordre de grandeur reste stable, les 1 440 clips occuperont environ **11 à 13 Gio** et demanderont autour de **quatre heures** à 1 Mo/s, hors ralentissements et nouvelles tentatives. La limite de dix heures laisse donc une marge confortable, tout en permettant une reprise automatique la nuit suivante si nécessaire.

## CERRA-Land et SARAH-3

Ces deux sources ne doivent pas être mélangées à la passe CHELSA :

- les jours de pluie exigent les précipitations **quotidiennes** CERRA-Land, soit un volume nettement supérieur ; le nouveau service Copernicus propose un accès Zarr ou des extractions par zone, qui seront traités par blocs après CHELSA ;
- les fichiers numériques SARAH-3 sont gratuits, mais leur téléchargement en masse passe par le CM SAF ou l’EUMETSAT Data Store et nécessite un compte/jeton EUMETSAT distinct. Le WMS public utilisé pendant la validation fournit les normales et des valeurs ponctuelles, mais pas un raster numérique de production.

Le téléchargement nocturne actuel couvre donc quatre des six couches climatiques. Il évite de lancer silencieusement une opération de plusieurs centaines de gigaoctets ou une source pour laquelle les identifiants nécessaires ne sont pas encore disponibles.
