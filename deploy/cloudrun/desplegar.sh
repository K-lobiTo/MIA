#!/usr/bin/env bash
# Despliega la API en Cloud Run con límites que acotan el gasto. Ver docs/OPERACION.md.
#
# Uso (desde cualquier carpeta):
#   PROYECTO=<id del proyecto> deploy/cloudrun/desplegar.sh
set -euo pipefail

PROYECTO="${PROYECTO:?Definir PROYECTO=<id del proyecto de Google Cloud>}"
REGION="${REGION:-us-east1}"   # cerca de Qdrant Cloud (N. Virginia) y con precios del nivel 1
SERVICIO="${SERVICIO:-mia-api}"
ENV_FILE="${ENV_FILE:-.env.cloudrun.yaml}"

cd "$(dirname "$0")/../.."

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Falta $ENV_FILE: copiar deploy/cloudrun/env.cloudrun.example.yaml y completar las credenciales." >&2
  exit 1
fi

# --max-instances 1: nunca corre más de un servidor, aunque lleguen miles de peticiones. Junto con
#   1 vCPU y 1 GiB, el peor caso (ocupado las 24 h) ronda los 2 USD por día; el corte por
#   presupuesto (configurar_corte.sh) lo detiene antes.
# --min-instances 0: sin tráfico no queda nada encendido y no se cobra.
# --cpu-throttling: cobro por petición (solo mientras se responde). Por eso la ingesta corre dentro
#   de la petición (INGESTION_SYNC=true), no en segundo plano.
# --timeout 600: margen para ingerir actas largas dentro de la misma petición.
# --port 8000: el puerto en el que escucha la imagen (Dockerfile).
gcloud run deploy "$SERVICIO" \
  --project "$PROYECTO" \
  --region "$REGION" \
  --source . \
  --port 8000 \
  --cpu 1 \
  --memory 1Gi \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 4 \
  --cpu-throttling \
  --timeout 600 \
  --env-vars-file "$ENV_FILE" \
  --allow-unauthenticated
