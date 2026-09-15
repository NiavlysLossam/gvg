#!/usr/bin/env bash
# ==============================================================================
# GVG Backend Container Entrypoint
# Automatically runs Alembic migrations before starting the main server command.
# ==============================================================================
set -euo pipefail

echo "[entrypoint] Lancement du conteneur GVG backend..."

# Application des migrations Alembic avec boucle d'attente résiliente si la base démarre
MAX_RETRIES=${MIGRATION_MAX_RETRIES:-15}
RETRY_INTERVAL=${MIGRATION_RETRY_INTERVAL:-2}
COUNT=0
MIGRATIONS_SUCCESS=0

echo "[entrypoint] Application automatique des migrations Alembic..."
until [ "$COUNT" -ge "$MAX_RETRIES" ]; do
    if alembic upgrade head; then
        MIGRATIONS_SUCCESS=1
        break
    fi
    COUNT=$((COUNT + 1))
    if [ "$COUNT" -lt "$MAX_RETRIES" ]; then
        echo "[entrypoint] Base de données non prête, nouvelle tentative dans ${RETRY_INTERVAL}s ($COUNT/$MAX_RETRIES)..."
        sleep "$RETRY_INTERVAL"
    fi
done

if [ "$MIGRATIONS_SUCCESS" -ne 1 ]; then
    echo "[entrypoint] ERREUR : Échec de l'application des migrations Alembic après $MAX_RETRIES tentatives." >&2
    exit 1
fi

echo "[entrypoint] Migrations Alembic appliquées avec succès."

if [ $# -gt 0 ]; then
    echo "[entrypoint] Exécution de la commande principale : $*"
    exec "$@"
else
    echo "[entrypoint] Aucune commande spécifiée, démarrage d'Uvicorn par défaut..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
