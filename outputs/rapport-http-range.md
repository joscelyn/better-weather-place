# Test des requêtes HTTP Range

Serveur testé : `http://127.0.0.1:5173/`

Chaque réponse est comparée octet par octet au fichier local correspondant.

| Format | Portion | HTTP | Content-Range | Octets | Résultat |
|---|---|---:|---|---:|---|
| PMTiles | début | 206 | `bytes 0-63/1392162` | 64 | OK |
| PMTiles | milieu | 206 | `bytes 696081-696144/1392162` | 64 | OK |
| COG | début | 206 | `bytes 0-63/11712356` | 64 | OK |
| COG | milieu | 206 | `bytes 5856178-5856241/11712356` | 64 | OK |
