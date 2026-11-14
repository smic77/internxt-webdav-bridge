# Guide de déploiement sur Portainer

## Architecture simplifiée

Tout est maintenant dans **2 fichiers**:
- `docker-compose.yml` → configuration complète de la stack
- `.env` → mot de passe WebDAV (optionnel, valeur par défaut dans docker-compose.yml)

Les credentials Internxt sont montées via Docker secrets depuis le serveur hôte.

## Étape 1: Préparer les credentials Internxt sur le serveur

### 1.1 Créer le dossier de credentials

```bash
sudo mkdir -p /home/sebastien/.internxt-tools
```

### 1.2 Copier les credentials depuis Windows

**Option A: Via SCP (depuis Windows PowerShell)**
```powershell
scp C:\Users\Sebastien\.internxt-tools\credentials.json sebastien@SERVEUR_IP:/home/sebastien/.internxt-tools/
```

**Option B: Via copier-coller**
```bash
sudo nano /home/sebastien/.internxt-tools/credentials.json
```
Copier le contenu depuis `C:\Users\Sebastien\.internxt-tools\credentials.json`

### 1.3 Sécuriser les permissions

```bash
sudo chmod 600 /home/sebastien/.internxt-tools/credentials.json
sudo chown sebastien:sebastien /home/sebastien/.internxt-tools/credentials.json
```

## Étape 2: Transférer les fichiers du projet

### 2.1 Copier le dossier internxt-dav

**Option A: Via SCP (depuis Windows PowerShell)**
```powershell
scp -r C:\Users\Sebastien\claude_test\internxt-dav sebastien@SERVEUR_IP:/home/sebastien/
```

**Option B: Via rsync**
```bash
rsync -avz C:\Users\Sebastien\claude_test\internxt-dav sebastien@SERVEUR_IP:/home/sebastien/
```

### 2.2 Vérifier les fichiers

```bash
cd /home/sebastien/internxt-dav
ls -la
```

Doit contenir:
- `Dockerfile`
- `docker-compose.yml` ← **configuration complète**
- `standalone.py` ← **génère webdav.toml automatiquement**
- `internxt_provider.py`
- `internxt.py`
- `.env.example` ← **template pour le mot de passe**

## Étape 3: Configurer le mot de passe WebDAV

### 3.1 Créer le fichier .env

```bash
cd /home/sebastien/internxt-dav
cp .env.example .env
nano .env
```

### 3.2 Modifier le mot de passe

```bash
WEBDAV_PASSWORD=ton_mot_de_passe_securise
```

**Générer un mot de passe fort:**
```bash
openssl rand -base64 32
```

### 3.3 Sécuriser .env

```bash
chmod 600 .env
```

## Étape 4: Image Docker (construite par GitHub Actions)

L'image est construite automatiquement par GitHub Actions (`.github/workflows/docker.yml`)
à chaque push sur `main` et publiée sur :

```
ghcr.io/smic77/internxt-webdav-bridge:latest      # dernière version de main
ghcr.io/smic77/internxt-webdav-bridge:sha-<commit> # version figée
```

Plateformes : `linux/amd64` et `linux/arm64`. Aucun build n'est nécessaire sur le serveur.

> Après le premier build, rendre le package public :
> GitHub → profil → Packages → `internxt-webdav-bridge` → Package settings → Change visibility → Public.
> (Sinon, ajouter `ghcr.io` comme registre dans Portainer avec un token GitHub `read:packages`.)

## Étape 5: Déployer via Portainer

### Option A: Via Portainer UI (depuis le dépôt Git)

1. **Stacks → Add stack**, nom : `internxt-webdav`
2. Build method : **Repository**
   - Repository URL : `https://github.com/smic77/internxt-webdav-bridge`
   - Repository reference : `refs/heads/main`
   - Compose path : `docker-compose.yml`
3. **Environment variables** : `WEBDAV_PASSWORD` = ton mot de passe (éviter le caractère `$`)
4. (Optionnel) Activer **GitOps updates** et **Re-pull image** pour suivre les nouvelles versions
5. **Deploy the stack**

Pour mettre à jour après un push : attendre la fin du workflow GitHub Actions, puis
Stack → **Pull and redeploy** (cocher *Re-pull image*).

### Option B: Via ligne de commande

```bash
cd /home/sebastien/internxt-dav
docker-compose up -d
```

## Étape 6: Vérifier le déploiement

### 6.1 Vérifier les logs

```bash
docker logs -f internxt-webdav
```

Doit afficher:
```
Starting ASGI WebDAV with Internxt provider support
Generated config for user: admin
ASGI WebDAV Server(v2.0.1) starting...
Register User: admin, allow:[''], deny:[]
InternxtProvider initialized for user: divers@smic77.fr
Mapping Prefix: / ==> internxt://divers@smic77.fr
ASGI WebDAV Server running on http://0.0.0.0:8000
```

### 6.2 Tester le service

```bash
# Tester PROPFIND (listing)
curl -X PROPFIND -u admin:TON_MOT_DE_PASSE http://localhost:8000/

# Doit retourner une liste XML des dossiers Internxt
```

### 6.3 Vérifier via Portainer

- Menu: Containers
- Chercher `internxt-webdav`
- Statut: Running
- Health: healthy

## Sauvegarde et restauration

### Ce qui est sauvegardé dans Portainer

✅ **docker-compose.yml** → toute la configuration de la stack  
✅ **Variables d'environnement** → mot de passe WebDAV (si défini dans Portainer)  
✅ **Image Docker** → ghcr.io/smic77/internxt-webdav-bridge:latest (construite par GitHub Actions)

### Ce qui doit être sauvegardé séparément

⚠️ **Credentials Internxt** → `/home/sebastien/.internxt-tools/credentials.json`

```bash
# Sauvegarder les credentials
sudo tar -czf internxt-credentials-backup-$(date +%Y%m%d).tar.gz \
  /home/sebastien/.internxt-tools/credentials.json

# Sauvegarder sur un autre support
scp /home/sebastien/internxt-credentials-backup-*.tar.gz backup@backup-server:/backups/
```

### Restauration complète

```bash
# 1. Restaurer les credentials
sudo tar -xzf internxt-credentials-backup-YYYYMMDD.tar.gz -C /
sudo chmod 600 /home/sebastien/.internxt-tools/credentials.json

# 2. Redéployer la stack depuis Portainer
# (la stack est sauvegardée dans Portainer)

# 3. Redémarrer (Portainer : Stack → Pull and redeploy)
docker compose pull && docker compose up -d
```

## Étape 7: Configurer Zerobyte

### 7.1 Accéder à Zerobyte

- URL: `https://ZEROBYTE_URL`

### 7.2 Ajouter un nouveau repository

1. **Repositories** → **Add repository**

2. **Configuration**
   - Name: `Internxt Backup`
   - Type: `WebDAV`
   - URL: `http://internxt-webdav:8000`
   - Username: `admin`
   - Password: `TON_MOT_DE_PASSE`

3. **Initialiser le repository**
   - Cliquer sur "Initialize repository"

### 7.3 Créer un volume

1. **Volumes** → **Add volume**

2. **Configuration**
   - Name: `Photos`
   - Type: `Directory`
   - Path: `/images_lisible`

### 7.4 Créer un job de backup

1. **Backups** → **Add backup**

2. **Configuration**
   - Name: `Photos Backup`
   - Repository: `Internxt Backup`
   - Volume: `Photos`
   - Schedule: `0 2 * * *` (tous les jours à 2h)
   - Retention:
     - Keep last: 7
     - Keep daily: 14
     - Keep weekly: 8
     - Keep monthly: 12

## Dépannage

### Problème: Le conteneur ne démarre pas

```bash
# Vérifier les logs
docker logs internxt-webdav

# Vérifier les permissions des credentials
ls -la /home/sebastien/.internxt-tools/credentials.json

# Doit être: -rw------- (600)
```

### Problème: Authentification WebDAV échoue

```bash
# Vérifier le mot de passe dans .env
cat /home/sebastien/internxt-dav/.env

# Ou dans Portainer: Stack → internxt-webdav → Environment variables

# Tester manuellement
curl -u admin:TON_MOT_DE_PASSE http://localhost:8000/
```

### Problème: Credentials Internxt invalides

```bash
# Vérifier le token
cat /home/sebastien/.internxt-tools/credentials.json | jq .token

# Si expiré, regénérer les credentials
cd /home/sebastien/internxt-dav
python3 internxt.py login
```

### Problème: Zerobyte ne peut pas se connecter

```bash
# Vérifier que le conteneur est accessible depuis le réseau Docker
docker exec zerobyte curl http://internxt-webdav:8000/

# Vérifier les logs Zerobyte
docker logs zerobyte | grep -i webdav
```

## Maintenance

### Rotation du mot de passe WebDAV

1. Modifier `.env`:
```bash
nano /home/sebastien/internxt-dav/.env
WEBDAV_PASSWORD=nouveau_mot_de_passe
```

2. Redémarrer:
```bash
docker-compose restart
```

3. Mettre à jour dans Zerobyte

### Rotation des credentials Internxt

```bash
# Régénérer les credentials
cd /home/sebastien/internxt-dav
python3 internxt.py login

# Redémarrer le service
docker restart internxt-webdav
```

### Mise à jour du code

```bash
cd /home/sebastien/internxt-dav

# Pousser les modifications sur main → GitHub Actions construit l'image
# Puis sur le serveur (ou Portainer → Pull and redeploy) :
docker compose pull
docker compose up -d
```

## Monitoring

### Health check

```bash
docker inspect --format='{{.State.Health.Status}}' internxt-webdav
```

### Logs

```bash
# Logs en temps réel
docker logs -f internxt-webdav

# Dernières 100 lignes
docker logs --tail 100 internxt-webdav
```

### Statistiques

```bash
docker stats internxt-webdav
```

## Sécurité

### Checklist

- [ ] Credentials Internxt: permissions 600
- [ ] Fichier .env: permissions 600
- [ ] Mot de passe WebDAV: fort (32+ caractères)
- [ ] Firewall: port 8000 bloqué en externe (sauf reverse proxy HTTPS)
- [ ] Backup des credentials: régulier et testé

### Firewall

```bash
# Bloquer l'accès externe direct
sudo ufw deny 8000/tcp

# Utiliser un reverse proxy avec HTTPS
# Voir documentation reverse proxy (Caddy, Traefik, Nginx)
```

## Support

- Documentation asgi-webdav: https://github.com/rexzhang/asgi-webdav
- Documentation Internxt: https://drive.internxt.com
- Logs Portainer: Menu → Containers → internxt-webdav → Logs
