# Guide Opérationnel de Sécurité - GVG

Ce document présente l'architecture de sécurité opérationnelle et les procédures de maintenance de la plateforme GVG (Gestion de Vide-Greniers).

---

## 1. Architecture Réseau et En-têtes HTTP

Le reverse proxy Nginx est la première ligne de défense de l'application :
- **Masquage de version** : `server_tokens off;` est activé pour neutraliser la reconnaissance automatisée.
- **En-têtes de sécurité stricts** :
  - `X-Frame-Options: "DENY"` (protection contre le clickjacking)
  - `X-Content-Type-Options: "nosniff"` (neutralisation du MIME sniffing)
  - `Referrer-Policy: "strict-origin-when-cross-origin"` (protection des URLs internes)
  - `Permissions-Policy: "camera=(), microphone=(), geolocation=()"` (désactivation des API navigateur intrusives)
  - `Content-Security-Policy: "default-src 'none'; sandbox"` appliqué spécifiquement au répertoire `/uploads/` pour neutraliser l'exécution de scripts ou de contenu actif HTML/SVG.

---

## 2. Limitation de Débit (Rate Limiting) & Protection Anti-Bruteforce

### Couche Nginx
Deux zones de limitation de débit sont configurées au niveau du reverse proxy :
- **Zone Générale API** (`api_general_limit`) : 30 requêtes par seconde par IP client (`rate=30r/s`), avec une rafale autorisée de 20 requêtes (`burst=20 nodelay`).
- **Zone Authentification** (`auth_limit`) : 5 requêtes par minute par IP client (`rate=5r/m`), avec une rafale autorisée de 5 requêtes (`burst=5 nodelay`).
- Toute requête excédant le quota reçoit immédiatement une réponse HTTP `429 Too Many Requests`.

### Couche Applicative (Défense en profondeur)
Dans FastAPI (`app/api/v1/endpoints/auth.py`), un contrôleur de débit glissant (sliding window) sur 60 secondes suit les échecs d'authentification :
- **Plafond par compte** : Maximum 5 échecs par adresse email (`MAX_FAILED_ATTEMPTS_PER_ACCOUNT = 5`).
- **Plafond par IP** : Maximum 20 échecs par adresse IP (`MAX_FAILED_ATTEMPTS_PER_IP = 20`) pour bloquer le password spraying horizontal.
- En cas de verrouillage, un en-tête `Retry-After: <secondes>` est retourné avec un code HTTP 429.

---

## 3. Procédure de Rotation des Secrets (`scripts/rotate-secrets.sh`)

La rotation de la clé secrète JWT (`JWT_SECRET_KEY`) doit être effectuée périodiquement ou immédiatement en cas de suspicion de compromission :

```bash
sudo /opt/gvg/scripts/rotate-secrets.sh
```

**Actions réalisées par le script :**
1. Vérification des privilèges administrateur (`root` / `sudo`).
2. Création d'une sauvegarde horodatée du fichier `.env` avec permissions restreintes (`chmod 600`) : `.env.bak.YYYYMMDD_HHMMSS`.
3. Génération cryptographique aléatoire d'une nouvelle clé secrète de 32 octets (64 caractères hexadécimaux) via `openssl rand -hex 32`.
4. Remplacement atomique de la valeur dans le `.env` et application des droits `chmod 600`.
5. Redémarrage propre du service backend `systemctl restart gvg.service`.

> [!NOTE]
> La rotation de la clé JWT invalide immédiatement l'ensemble des sessions et tokens d'accès administrateurs en cours, obligeant les utilisateurs à se ré-authentifier.

---

## 4. Intégration Fail2ban

Pour un déploiement Ubuntu natif avec exposition publique, l'installation de Fail2ban est recommandée pour bannir au niveau pare-feu (iptables/nftables) les attaquants répétés.

Exemple de filtre `/etc/fail2ban/filter.d/nginx-ratelimit.conf` :
```ini
[Definition]
failregex = limiting requests, error: 429.*client: <HOST>
ignoreregex =
```

Exemple de prison `/etc/fail2ban/jail.d/gvg-nginx.conf` :
```ini
[gvg-nginx-ratelimit]
enabled = true
port = http,https
filter = nginx-ratelimit
logpath = /var/log/nginx/error.log
maxretry = 3
findtime = 600
bantime = 3600
```

