# Internxt WebDAV Bridge (asgi-webdav)

Serveur WebDAV basé sur **asgi-webdav** qui fait le pont entre Zerobyte (ou tout autre client WebDAV) et Internxt Drive.

## Pourquoi asgi-webdav?

- ✅ **Moderne et asynchrone** - Bien plus performant que WsgiDAV
- ✅ **Plus simple** - Code plus propre, mieux maintenu
- ✅ **Compatible** - Passé les tests litmus (standard WebDAV)
- ✅ **Docker ready** - Image officielle disponible

## Architecture

```
Zerobyte (restic)
    ↓ WebDAV
asgi-webdav (conteneur Docker)
    ↓ InternxtProvider (custom)
internxt.py (API Internxt + crypto)
    ↓ HTTPS
Internxt Drive (tes 10 To)
```

## Structure

```
internxt-dav/
├── Dockerfile              # Image Docker
├── docker-compose.yml      # Orchestration avec secrets
├── standalone.py           # Launcher avec monkey-patch
├── internxt_provider.py    # Provider custom pour asgi-webdav
├── internxt.py             # Script API Internxt (copié)
├── webdav.toml             # Configuration asgi-webdav
└── README.md
```

## Installation

### 1. Prérequis

- Docker et Docker Compose
- Fichier de credentials Internxt (généré via `python internxt.py login`)

### 2. Générer les credentials Internxt

```bash
cd internxt-sdk-test/internxt_script
python internxt.py login
```

Le fichier sera créé dans `~/.internxt-tools/credentials.json`.

### 3. Configurer le mot de passe WebDAV

Éditer `webdav.toml` et changer le mot de passe par défaut:

```toml
[[account_mapping]]
username = "admin"
password = "ton_mot_de_passe_securise"
permissions = ["+"]
```

### 4. Lancer le conteneur

```bash
cd internxt-dav
docker compose up -d
```

### 5. Vérifier

```bash
docker compose logs -f
```

Le serveur WebDAV est accessible sur `http://localhost:8000`.

## Utilisation avec Zerobyte

Dans Zerobyte, créer un nouveau repository:
- Type: **WebDAV**
- URL: `http://internxt-webdav:8000` (si Zerobyte est dans le même réseau Docker)
- User: `admin`
- Password: celui défini dans `webdav.toml`

## Sécurité

- Les credentials Internxt sont montées via Docker secrets (jamais dans les logs)
- Le fichier credentials contient le **mnemonic en clair** (clé maîtresse)
- Protéger le fichier hôte: `chmod 600 ~/.internxt-tools/credentials.json`
- Utiliser un mot de passe WebDAV fort
- En production, exposer via reverse proxy avec HTTPS

## Fonctionnalités supportées

| Opération | Support | Notes |
|-----------|---------|-------|
| PROPFIND (listing) | ✅ | Complet |
| GET (download) | ✅ | Complet, testé avec fichiers 3MB |
| PUT (upload) | ✅ | Complet |
| MKCOL (create folder) | ✅ | Complet |
| DELETE | ✅ | Complet |
| COPY | ❌ | Non supporté par Internxt |
| MOVE | ❌ | Non supporté par Internxt |
| PROPPATCH | ⚠️ | Ignoré (pas d'erreur) |

**Toutes les opérations essentielles pour Zerobyte/restic sont supportées!**

## Dépannage

### Erreur de credentials

```
Failed to load Internxt credentials
```

Vérifier que:
1. Le fichier existe: `ls -la ~/.internxt-tools/credentials.json`
2. Les permissions sont correctes: `chmod 600 ~/.internxt-tools/credentials.json`
3. Le conteneur a accès au secret: `docker compose exec internxt-webdav ls -la /run/secrets/`

### Erreur d'authentification WebDAV

Vérifier le mot de passe dans `webdav.toml` et redémarrer: `docker compose restart`

### Logs détaillés

```bash
docker compose logs -f internxt-webdav
```

## Développement

Pour tester localement sans Docker:

```bash
cd internxt-dav
pip install asgi-webdav requests cryptography uvicorn
export INTERNXT_CREDENTIALS_FILE=/home/sebastien/.internxt-tools/credentials.json
python standalone.py
```

## Licence

MIT - Utilise:
- [asgi-webdav](https://github.com/rexzhang/asgi-webdav) (MIT)
- [internxt_script](https://github.com/vonsete/internxt_script) (MIT)
